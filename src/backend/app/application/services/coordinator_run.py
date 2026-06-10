"""CoordinatorRun — task_engine 后台运行 + session 级 registry（v4 事件驱动）。

接线铁律：
- registry 是**进程级**（deps 每请求新建 ChatService，实例级 registry 形同虚设）。
- CoordinatorRun 是 spawn-on-demand 后台任务：start 时 spawn，park 后 task 自然结束，
  feed 时再 spawn。run 生命周期 ≠ 单个 asyncio.Task 生命周期。
- 完成/失败回调用独立 session_factory 落系统消息（见 post_system_background）。
- registry 只在 _finish（全完成）或 cancel（用户终止）时释放，park 态不释放。
"""

from __future__ import annotations

import asyncio
import itertools
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.application.services.session_state import PlanView, StepView
from app.application.services.supervisor_service import SupervisorService
from app.core.config import settings
from app.core.events import get_event_bus
from app.domain.entities.agent import Agent
from app.domain.entities.group import Group
from app.domain.entities.message import Message
from app.domain.entities.session import Session
from app.domain.enums import MessageRole
from app.domain.events import MessageSent
from app.domain.llm.protocol import StreamEvent, StreamEventType
from app.domain.task_engine.context import gather_context
from app.domain.task_engine.dag import TaskDef
from app.domain.task_engine.executor import AgentExecutor
from app.domain.task_engine.orchestrator import Orchestrator, ReplanDiff
from app.domain.task_engine.planner import SeedPlanner
from app.domain.task_engine.ports import ProgressSink, RunResult, Supervisor, SupervisorConfig
from app.domain.task_engine.verifier import MechanicalVerifier
from app.infrastructure.db.base import session_factory
from app.infrastructure.llm.factory import build_adapter_for_agent
from app.infrastructure.llm.text_llm_adapter import build_text_llm
from app.infrastructure.repositories.message_repository import PostgresMessageRepository
from app.infrastructure.ws.connection_manager import ws_manager

logger = logging.getLogger(__name__)

ResultSink = Callable[[RunResult], Awaitable[None]]
ErrorSink = Callable[[Exception], Awaitable[None]]


# ── 进程级 registry（防重 + 取消句柄）───────────────────────────────────────

_ACTIVE: dict[UUID, CoordinatorRun] = {}


class CoordinatorRegistry:
    """薄包装，共享进程级 _ACTIVE。多个 ChatService 实例看到同一份。"""

    def get(self, session_id: UUID) -> CoordinatorRun | None:
        return _ACTIVE.get(session_id)

    def try_reserve(self, session_id: UUID, run: CoordinatorRun) -> bool:
        """同步 check+insert（无 await → asyncio 单线程内原子）。已有 → False。"""
        if session_id in _ACTIVE:
            return False
        _ACTIVE[session_id] = run
        return True

    def release(self, session_id: UUID) -> None:
        _ACTIVE.pop(session_id, None)

    @staticmethod
    def clear() -> None:  # 测试隔离用
        _ACTIVE.clear()


# ── 后台运行句柄 ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PendingReplan:
    """破坏性 replan 待用户确认时暂存。"""

    requirement: str
    new_tasks: list[TaskDef]
    diff: ReplanDiff


@dataclass
class CoordinatorRun:
    session_id: UUID
    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    _task: asyncio.Task | None = field(default=None, repr=False)
    _orchestrator: Orchestrator | None = field(default=None, repr=False)
    pending_replan: PendingReplan | None = field(default=None, repr=False)
    # v4 R2：按 worker 分桶。key=worker 名（只投该 worker）或 "*"（全局，所有 worker 可见）。
    _pending_notes: dict[str, list[str]] = field(default_factory=dict, repr=False)
    _registry: CoordinatorRegistry | None = field(default=None, repr=False)
    _on_done: ResultSink | None = field(default=None, repr=False)
    _on_error: ErrorSink | None = field(default=None, repr=False)

    def enqueue_note(self, text: str, worker: str | None = None) -> None:
        """执行期旁路消息入队（§11.6）：worker 占线中，消息暂存，dispatch 边界投递。

        worker 指定 → 只投该 worker 的桶；None → "*" 全局桶（所有后续 dispatch 可见）。
        """
        self._pending_notes.setdefault(worker or "*", []).append(text)

    def plan_view(self) -> PlanView | None:
        """从 Orchestrator 当前 DAG 投影 PlanView。无任务/未建图 → None。纯只读，不写 graph。"""
        if self._orchestrator is None or self._orchestrator.graph is None:
            return None
        steps = tuple(
            StepView(
                step_id=n.task.id,
                worker=n.task.suggested_worker,
                status=n.status.value,
            )
            for n in self._orchestrator.graph.nodes.values()
        )
        return PlanView(steps=steps)

    def start(
        self,
        orchestrator: Orchestrator,
        *,
        on_done: ResultSink,
        on_error: ErrorSink,
        registry: CoordinatorRegistry,
    ) -> None:
        """v4 事件驱动：注入回调 → spawn orchestrator.start()。
        park 后 task 自然结束，registry 不释放；续跑时 on_feed 再 spawn。
        """
        self._orchestrator = orchestrator
        self._registry = registry
        self._on_done = on_done
        self._on_error = on_error
        orchestrator._pending_notes = self._pending_notes

        async def on_finish(result: RunResult) -> None:
            await on_done(result)
            registry.release(self.session_id)

        orchestrator._on_finish = on_finish
        self._spawn(orchestrator.start())

    # ── v4 feed 接口 ─────────────────────────────────────────────────────

    async def on_feed(self, step_id: str, answer: str) -> bool:
        """用户回话续跑挂起的 run。spawn orchestrator.on_feed 后台执行。"""
        if self._orchestrator is None:
            return False
        self._spawn(self._orchestrator.on_feed(step_id, answer))
        return True

    async def relay(self, worker: str, text: str) -> None:
        """投递一条消息给在干活的成员（design §4 relay）。投递层按运行态分流：

        - in-flight（执行任务在飞，CLI 占线）→ 进桶；turn-end/下次 dispatch 注入，不中途打断。
        - parked（流结束未交卷，进程已退、run 已休眠）→ 当作答复，--resume 续跑。
        """
        in_flight = self._task is not None and not self._task.done()
        if in_flight:
            self.enqueue_note(text, worker)
            return
        # parked：找该 worker 的 RUNNING 节点，当答复 resume
        pv = self.plan_view()
        step = next(
            (s.step_id for s in (pv.steps if pv else ())
             if s.worker == worker and s.status == "running"),
            None,
        )
        if step is not None:
            await self.on_feed(step, text)
        else:
            self.enqueue_note(text, worker)  # 兜底：没在跑节点就进桶，下次 dispatch 注入

    # ── replan 接口 ──────────────────────────────────────────────────────

    @property
    def orchestrator(self) -> Orchestrator | None:
        return self._orchestrator

    async def plan_replan(self, requirement: str) -> tuple[list[TaskDef], ReplanDiff] | None:
        """重分解 + 算 diff（只读，不改图）。无活跃图 → None。"""
        if self._orchestrator is None or self._orchestrator.graph is None:
            return None
        return await self._orchestrator.plan_replan(requirement)

    def stash_replan(self, requirement: str, new_tasks: list[TaskDef], diff: ReplanDiff) -> None:
        self.pending_replan = PendingReplan(requirement, new_tasks, diff)

    def clear_pending_replan(self) -> None:
        self.pending_replan = None

    async def replan(self, new_tasks: list[TaskDef], *, force: bool = False) -> None:
        """换图：先静默在飞 worker（D2）→ 等 drive 收尾 → spawn 新的换图+drive。"""
        if self._orchestrator is None:
            return
        await self._quiesce()
        self._spawn(self._orchestrator.replan(new_tasks, force=force))

    async def _quiesce(self) -> None:
        """静默 orchestrator：abort 在飞 worker + 等 drive 任务收尾，确保换图时无并发写者。"""
        if self._task is not None and not self._task.done():
            await self._orchestrator.abort_inflight()
            try:
                await self._task
            except Exception:  # drive 收尾异常不阻断 replan
                logger.exception("quiesce 等待 drive 收尾异常 run=%s", self.run_id)

    # ── spawn 模型 ───────────────────────────────────────────────────────

    def _spawn(self, coro) -> None:
        """创建后台 task，异常由 _guard 捕获并回调 on_error。"""
        self._task = asyncio.create_task(self._guard(coro))

    async def _guard(self, coro) -> None:
        """包装协程：异常不抛崩调用方，走 on_error 回调。"""
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Orchestrator task 失败 run=%s", self.run_id)
            if self._on_error is not None:
                try:
                    await self._on_error(exc)
                except Exception:
                    logger.exception("on_error 回调失败 run=%s", self.run_id)

    async def cancel(self) -> None:
        """取消当前 task + 释放 registry。"""
        if self._task is not None and not self._task.done():
            self._task.cancel()
        if self._registry is not None:
            self._registry.release(self.session_id)


# ── WS 带外推送（后台 CoordinatorRun → 已连接客户端）─────────────────────────


def _plan_who_to_id(payload: dict, worker_ids: dict[str, str]) -> dict:
    """task_plan 的 step.who 从 worker 名翻译成 agent id —— 前端 lookupActor 按 id 查。

    Orchestrator 域内只有 worker 名（suggested_worker），name→id 是前端适配关注点，放这层。
    未命中（如名字打错）保留原值，前端走 fallback 渲染。
    """
    plan = payload.get("plan", {})
    steps = [{**s, "who": worker_ids.get(s.get("who"), s.get("who"))} for s in plan.get("steps", [])]
    return {**payload, "plan": {**plan, "steps": steps}}


def make_ws_progress_sink(
    session_id: UUID, coordinator_id: UUID, worker_ids: dict[str, str] | None = None
) -> ProgressSink:
    """把 Orchestrator 的进度事件包成 StreamEvent，经 ws_manager 广播给该 session 的客户端。

    后台任务与 WS 在同一进程/事件循环，ws_manager 是进程级单例 → 可直接 broadcast。
    payload 约定：task_plan→{plan}，task_update→{taskId,...}，text→{content}，done→{}。
    worker_ids: worker 名 → agent id（str），用于把 plan step.who 翻成前端可查的 id。
    """
    counter = itertools.count()
    name_to_id = worker_ids or {}

    async def sink(event_type: str, payload: dict) -> None:
        if event_type == "task_plan":
            payload = _plan_who_to_id(payload, name_to_id)
        content = payload.get("content")
        metadata = {k: v for k, v in payload.items() if k != "content"}
        evt = StreamEvent(
            type=StreamEventType(event_type),
            seq=next(counter),
            content=content,
            metadata=metadata,
            sender_agent_id=coordinator_id,
        )
        await ws_manager.broadcast(session_id, evt.model_dump(mode="json"))

    return sink


# ── worker 发言入群聊（event_sink）─────────────────────────────────────────────


def make_worker_event_sink(
    session_id: UUID,
    coordinator_id: UUID | None = None,
    *,
    persist: Callable[[object, str], Awaitable[None]] | None = None,
) -> Callable[[StreamEvent], Awaitable[None]]:
    """worker 流 event_sink：双通道分流。

    **聊天通道（干净叙事，保守版 §2）**：worker 动手前的开场白（首个 tool_call 前的文本）→
    一条「报到」消息进 transcript；turn 结束（DONE）的收尾文本 → 一条「交卷」消息。
    中间穿插的旁白不入聊天，只进步骤详情，避免刷屏。

    **步骤活动通道（Claude Code 风格实时进度）**：每个 TEXT/TOOL_CALL/TOOL_RESULT 都打上
    taskId 广播为 `task_activity`，前端归到对应步骤的实时进度 feed（点开步骤卡片可见）。
    """
    _persist = persist or (
        lambda agent_id, text: post_worker_message_background(session_id, agent_id, text)
    )
    run_buf: dict[object, list[str]] = {}   # 当前连续文本段（遇 tool_call 清空）
    announced: dict[object, bool] = {}       # 是否已发过开场白

    async def _activity(task_id: object, payload: dict) -> None:
        if coordinator_id is None or not task_id:
            return
        evt = StreamEvent(
            type=StreamEventType.TASK_ACTIVITY,
            seq=0,
            metadata={"taskId": task_id, **payload},
            sender_agent_id=coordinator_id,
        )
        await ws_manager.broadcast(session_id, evt.model_dump(mode="json"))

    async def sink(evt: StreamEvent) -> None:
        who = evt.sender_agent_id
        task_id = evt.metadata.get("taskId")

        if evt.type == StreamEventType.TEXT and evt.content:
            run_buf.setdefault(who, []).append(evt.content)
            await _activity(task_id, {"kind": "text", "text": evt.content})

        elif evt.type == StreamEventType.TOOL_CALL and evt.tool_call:
            # 首个工具调用前的开场白 → 报到（仅一次）。中段旁白只进 feed，不刷聊天。
            if not announced.get(who):
                text = "".join(run_buf.get(who, [])).strip()
                if text:
                    await _persist(who, text)
                    announced[who] = True
            run_buf[who] = []
            await _activity(task_id, {
                "kind": "tool_call",
                "callId": evt.tool_call.call_id,
                "name": evt.tool_call.name,
            })

        elif evt.type == StreamEventType.TOOL_RESULT and evt.tool_result:
            await _activity(task_id, {
                "kind": "tool_result",
                "callId": evt.tool_result.call_id,
                "ok": evt.tool_result.success,
            })

        elif evt.type == StreamEventType.DONE:
            text = "".join(run_buf.pop(who, [])).strip()
            announced.pop(who, None)
            if text:
                await _persist(who, text)

    return sink


async def _broadcast_chat_message(session_id: UUID, agent_id: object, content: str) -> None:
    """后台任务里把一条完整发言实时推给前端 WS（单条 TEXT 带 final 标记，前端 append 成独立消息）。

    必须直接 broadcast：后台 Orchestrator 的发言无法走已结束的 HTTP 流，而 MessageSent
    事件无 WS 订阅者（只落库），不 broadcast 就只能刷新页面才看得到（本会话「组员不说话」根因）。
    用 metadata.final 让前端直接落一条完成消息，避免与流式哨兵粘连。
    """
    await ws_manager.broadcast(
        session_id,
        StreamEvent(
            type=StreamEventType.TEXT, seq=0, content=content,
            sender_agent_id=agent_id,  # type: ignore[arg-type]
            metadata={"final": True},
        ).model_dump(mode="json"),
    )


async def post_worker_message_background(session_id: UUID, agent_id: object, content: str) -> None:
    """后台落 worker 发言（role=ASSISTANT, sender=worker）→ 进 transcript + 实时广播前端。"""
    msg = Message(
        session_id=session_id, role=MessageRole.ASSISTANT, content=content,
        sender_agent_id=agent_id,  # type: ignore[arg-type]
    )
    async with session_factory() as db:
        await PostgresMessageRepository(db).save(msg)
        await db.commit()
    await _broadcast_chat_message(session_id, agent_id, content)  # 实时进群聊
    await get_event_bus().publish(
        MessageSent(
            session_id=session_id, message_id=msg.id, role="assistant", content_type="text"
        )
    )


# ── 协作者组装（生产默认，可注入替换以便测试）────────────────────────────────


async def build_default_orchestrator(
    *, task: str, members: list[Agent], session: Session, group: Group,
    supervisor_agent: Agent | None = None,
) -> Orchestrator:
    """组装 5 协作者 → Orchestrator。gather_context 走 to_thread（只读 IO）。"""
    by_name = {a.name: a for a in members}
    workspace = session.workspace_path or None
    # 富描述：名+角色+能力 → planner 按能力选 worker，不再只看名字盲选
    agents_desc = "\n".join(
        f"- {a.name}（角色：{a.role or '未指定'}；能力：{', '.join(a.capability_tags) or '通用'}）"
        for a in members
    )
    ctx = await asyncio.to_thread(
        gather_context, task, list(by_name), workspace, agents_desc=agents_desc
    )
    planner = SeedPlanner(build_text_llm())  # provider/model 全由 settings 决定
    executor = AgentExecutor(
        resolve_agent=by_name.get,
        adapter_factory=build_adapter_for_agent,
        session_id=session.id,
        group_id=group.id,
        workspace=workspace,
        event_sink=make_worker_event_sink(session.id, group.coordinator_id),  # 发言进群聊 + 活动进步骤 feed
    )
    verifier = MechanicalVerifier(workspace=workspace)
    worker_ids = {a.name: str(a.id) for a in members}  # 给 plan step.who 翻译用

    # ── Supervisor 接线（可选）────────────────────────────────────────────
    supervisor: Supervisor | None = None
    sv_config = SupervisorConfig(
        supervisor_agent_id=settings.supervisor_agent_name,
        enabled=settings.supervisor_enabled and bool(settings.supervisor_agent_name),
        max_turns=settings.supervisor_max_turns,
    )
    if sv_config.enabled and supervisor_agent is not None:
        # Merge supervisor into lookup: supervisor may not be a group member,
        # but resolve_agent must find it.  by_name covers group members;
        # the pre-resolved supervisor_agent covers the system-level supervisor.
        _sv_lookup = dict(by_name)
        _sv_lookup[supervisor_agent.name] = supervisor_agent
        supervisor = SupervisorService(
            session_id=session.id,
            group_id=group.id,
            coordinator_id=group.coordinator_id,
            config=sv_config,
            resolve_agent=_sv_lookup.get,
            adapter_factory=build_adapter_for_agent,
        )
        logger.info(
            "Supervisor 已接线 session=%s agent=%s max_turns=%s",
            session.id, sv_config.supervisor_agent_id, sv_config.max_turns,
        )
    elif sv_config.enabled:
        logger.warning(
            "Supervisor 配置已启用但 agent '%s' 未在 DB 中找到，跳过接线",
            settings.supervisor_agent_name,
        )

    return Orchestrator(
        planner=planner,
        executor=executor,
        verifier=verifier,
        ctx=ctx,
        supervisor=supervisor,
        session_id=session.id,
        # WS 带外推送；worker_ids 让 plan step.who 是 agent id（前端 lookupActor 按 id 查）
        progress=make_ws_progress_sink(session.id, group.coordinator_id, worker_ids),
        # R4：关键事件入 transcript（独立 DB session 落 SYSTEM 消息 + 实时广播，挂协调者身份）
        message_sink=lambda content: post_system_background(session.id, content, group.coordinator_id),
    )


# ── 后台系统消息落库（独立 session，不用请求作用域）──────────────────────────


async def post_system_background(
    session_id: UUID, content: str, coordinator_id: UUID | None = None
) -> None:
    """后台任务专用：开独立 DB session 落系统消息 + 实时广播。请求已结束，不能复用其 session。

    coordinator_id：里程碑通报（开始执行/✅完成/❌失败/卡死）挂协调者身份，前端才能
    识别为协调者消息渲染成里程碑分隔线（否则 sender=None → unknown）。
    """
    msg = Message(
        session_id=session_id, role=MessageRole.SYSTEM, content=content,
        sender_agent_id=coordinator_id,  # type: ignore[arg-type]
    )
    async with session_factory() as db:
        await PostgresMessageRepository(db).save(msg)
        await db.commit()
    await _broadcast_chat_message(session_id, coordinator_id, content)  # 实时进群聊
    await get_event_bus().publish(
        MessageSent(
            session_id=session_id, message_id=msg.id, role="system", content_type="text"
        )
    )
