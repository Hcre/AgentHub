"""ChatService（L3）：私聊 + 群聊统一入口。

数据流（架构文档 S11/S12/S22 + group-chat 设计文档 §3）：
  持久化用户消息 → 写 L1 滑动窗口 → 路由目标 Agent(s)
  → 对每个 Agent: ContextBuilder.build_for_agent → 适配器流式
  → 完成时落库 + 推进 watermark + 重写 L1
  → 触发 token 消耗监控（P1-2 record_completion / record_user_message）

群聊路由：
  - 用户 @ Agent → V1 串行执行（list[Agent]）
  - 无 @ 无广播 → 统一路由循环 decide → relay/task/replan/done
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

from app.application.commands import SendMessageCommand
from app.application.services.context_builder import ContextBuilder
from app.application.services.coordinator_run import (
    CoordinatorRegistry,
    CoordinatorRun,
    build_default_orchestrator,
    post_system_background,
)
from app.application.services.reactive_router import ReactiveRouter
from app.application.services.session_state import SessionState
from app.application.services.usage_service import UsageService
from app.core.config import settings
from app.core.events import EventBus
from app.core.exceptions import NotFoundError
from app.domain.entities.agent import Agent
from app.domain.entities.group import Group
from app.domain.entities.message import Message
from app.domain.entities.session import Session
from app.domain.enums import MessageRole, MessageStatus, SessionType
from app.domain.events import (
    MessageSent,
    StreamingCompleted,
    StreamingFailed,
    StreamingStarted,
)
from app.domain.llm.protocol import StreamEvent, StreamEventType, UnifiedAgent
from app.domain.repositories import (
    AgentRepository,
    GroupRepository,
    MessageRepository,
    SessionRepository,
)
from app.domain.task_engine.orchestrator import Orchestrator, ReplanDiff
from app.infrastructure.cache.memory_l1 import L1MemoryStore
from app.infrastructure.cache.watermark_store import WatermarkStore
from app.infrastructure.llm.factory import build_adapter_for_agent

logger = logging.getLogger(__name__)


# v3 步1 前门机械反射（零 LLM）。broadcast 从 Selector L1.5 提升。
_BROADCAST_RE = re.compile(r"大家|各位|所有人|全员|全体|在座的|你们都说说|都来说说")

# v4 R5：破坏性 replan 的确认词（零 LLM 反射，跟 control 同级）。确认词在开头、后面跟什么都算
# ——中文 \b 不可靠（依赖 \w），用 [\s\S]*$。
_CONFIRM_RE = re.compile(
    r"^(继续|确认|行|可以|ok|yes|好|嗯|对|搞|干|做|没问题|来吧|开始|执行|没错|是的|"
    r"对的|同意|当然|好的|行吧|好吧)[\s\S]*$",
    re.IGNORECASE,
)

# v4 R3：多轮讨论无机械上限（防循环只靠 LLM 判 done）。仅软观察口——
# 超过此轮数打 warning 供运维发现异常，绝不截断正常讨论。
_DISCUSS_SOFT_LIMIT = 10

# Phase 5 接线：可注入的协作者组装器 + 后台系统消息 sink（生产默认在 coordinator_run）
OrchestratorBuilder = Callable[..., Awaitable[Orchestrator]]
SystemMessageSink = Callable[..., Awaitable[None]]


def _format_replan_confirmation(diff: ReplanDiff, requirement: str) -> str:
    """破坏性 replan 确认文案。running 才是需确认的；completed 仅信息（成果保留）。"""
    lines = [f"⚠️ 计划变更「{requirement}」将影响："]
    if diff.running:
        lines.append(f"- 正在进行的会被打断并取消：{', '.join(diff.running)}")
    if diff.completed:
        lines.append(f"- 已完成的成果保留在仓库，但不再属于新计划：{', '.join(diff.completed)}")
    lines.append(f"- 新计划共 {diff.new_count} 项")
    lines.append("回复「继续」确认变更，或直接说新的想法。")
    return "\n".join(lines)


def _load_skill_content(skill_names: list[str], skills_dir: str | None = None) -> str:
    """读取 skill 文件内容，拼接为 system prompt 片段。"""
    if skills_dir is None:
        from app.core.config import settings

        skills_dir = str(settings.skills_dir_path)
    if not skill_names or not os.path.isdir(skills_dir):
        return ""
    parts: list[str] = []
    for name in skill_names:
        path = os.path.join(skills_dir, name, "SKILL.md")
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        parts.append(f"## Skill: {name}\n\n{content}")
            except OSError:
                logger.warning("无法读取 skill 文件: %s", path)
    return "\n\n---\n\n".join(parts) if parts else ""


class ChatService:
    def __init__(
        self,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        agent_repo: AgentRepository,
        group_repo: GroupRepository,
        l1_memory: L1MemoryStore,
        watermarks: WatermarkStore,
        context_builder: ContextBuilder,
        llm: UnifiedAgent,
        event_bus: EventBus,
        reactive_router: ReactiveRouter | None = None,
        orchestrator_builder: OrchestratorBuilder = build_default_orchestrator,
        system_message_sink: SystemMessageSink = post_system_background,
        usage_service: UsageService | None = None,
    ) -> None:
        self._sessions = session_repo
        self._messages = message_repo
        self._agents = agent_repo
        self._groups = group_repo
        self._l1 = l1_memory
        self._wm = watermarks
        self._ctx = context_builder
        self._llm = llm  # 全局默认，per-agent 覆盖时优先
        self._bus = event_bus
        # v3 统一前门路由（步1）：取代 CoordinatorGate + Selector L3
        self._router = reactive_router or ReactiveRouter()
        self._registry = CoordinatorRegistry()  # 薄包装，共享进程级 registry
        self._build_orch = orchestrator_builder
        self._coord_post = system_message_sink  # 后台系统消息（独立 session）
        self._usage = usage_service  # P1-2 token 监控；None 时降级为 no-op

    async def send_and_stream(self, cmd: SendMessageCommand) -> AsyncIterator[StreamEvent]:
        """发送用户消息并流式返回 Agent 响应。"""
        session = await self._sessions.get_by_id(cmd.session_id)
        if session is None:
            raise NotFoundError(f"会话不存在: {cmd.session_id}")

        # 1. 持久化用户消息 + L1 + 广播
        user_msg = await self._persist_user_message(session, cmd)

        # 2. 分流：私聊 / 群聊
        if session.type == SessionType.PRIVATE:
            async for evt in self._handle_private(session, user_msg):
                yield evt
            return

        # 群聊：必须能查到 Group
        if session.group_id is None:
            logger.warning("群聊 session 无 group_id: %s", session.id)
            return
        group = await self._groups.get_by_id(session.group_id)
        if group is None:
            logger.warning("群组不存在: %s", session.group_id)
            return

        async for evt in self._handle_group(session, group, user_msg):
            yield evt

    # --- 私聊路径（向后兼容） ---

    async def _handle_private(
        self, session: Session, trigger: Message
    ) -> AsyncIterator[StreamEvent]:
        if session.agent_id is None:
            raise NotFoundError(f"私聊会话缺少 agent_id: {session.id}")
        agent = await self._agents.get_by_id(session.agent_id)
        if agent is None:
            raise NotFoundError(f"Agent 不存在: {session.agent_id}")
        async for evt in self._stream_one_agent(
            session=session, group=None, target=agent, trigger=trigger
        ):
            yield evt

    # --- 群聊路径 ---

    async def _handle_group(
        self, session: Session, group: Group, trigger: Message
    ) -> AsyncIterator[StreamEvent]:
        # 解析 @ 提及
        targets = await self._resolve_mentions(trigger.mentions, group)

        if targets:
            # V1 串行：逐个 Agent 处理
            for target in targets:
                async for evt in self._stream_one_agent(
                    session=session, group=group, target=target, trigger=trigger
                ):
                    yield evt
            return

        # --- v4 R2 统一前门：机械反射 → 一次 reactive decide → dispatch ---
        text = trigger.content or ""
        run = self._registry.get(session.id)

        # 反射②b：破坏性 replan 待确认（零 LLM）。确认 → 执行换图；非确认 → 不清不吞，
        # fall through 到统一循环（用户可能在改新需求，或闲聊两句后再回来确认）。
        if run is not None and run.pending_replan is not None and self._is_confirmation(text):
            pending = run.pending_replan
            run.clear_pending_replan()
            await run.replan(pending.new_tasks, force=True)
            await self._post_system_sync(session, f"✅ 计划已变更：{pending.requirement}。")
            return

        members = await self._group_members(group)

        # 反射③：全体意图 → 全员（零 LLM）。
        if self._is_broadcast(trigger):
            for target in members:
                async for evt in self._stream_one_agent(
                    session=session, group=group, target=target, trigger=trigger
                ):
                    yield evt
            return

        # ── 统一路由循环（design §4「一扇门，一条路」；§2.3 零模式）──
        # active_plan 是 decide 的输入字段，不是分支条件。
        # 唯一的 if action== 是对 decide 输出的分发：
        rounds = 0
        responded: set[str] = set()  # 本轮已在排队回复的成员，避免 router 重复选
        while True:
            active_plan = run.plan_view() if run is not None else None
            state = await SessionState.from_session(
                session_id=session.id, members=members,
                message_repo=self._messages, window=settings.l1_window_size,
                active_plan=active_plan, responded=frozenset(responded),
            )
            decision = await self._router.decide(state)
            rounds += 1
            logger.info(
                "decide session=%s round=%d action=%s who=%s has_plan=%s reason=%s",
                session.id, rounds, decision.action, decision.who,
                active_plan is not None, decision.reason,
            )

            if decision.action == "task":
                if active_plan is not None:
                    # 已有 DAG 在跑 → 新任务降级 note（单 Orchestrator/session，design §7）
                    logger.info("执行态 decide=task，降级 note session=%s", session.id)
                    run.enqueue_note(text)
                    yield StreamEvent(
                        type=StreamEventType.TEXT,
                        seq=0,
                        content="📋 已追加到当前任务队列",
                    )
                else:
                    yield StreamEvent(
                        type=StreamEventType.TEXT,
                        seq=0,
                        content="✅ 任务已受理，正在规划…",
                        sender_agent_id=group.coordinator_id,  # 协调者身份，避免前端 unknown
                    )
                    await self._start_coordinator(session, group, trigger)
                return

            if decision.action == "replan":
                if run is None:
                    # 纯对话态误判 replan（无任务在跑）→ 当新任务起
                    yield StreamEvent(
                        type=StreamEventType.TEXT,
                        seq=0,
                        content="✅ 已受理，正在重新规划…",
                    )
                    await self._start_coordinator(session, group, trigger)
                else:
                    await self._handle_replan(session, group, run, decision.requirement or text)
                return

            if decision.action == "cancel":
                if run is not None:
                    await self._cancel_coordinator(session, run)
                return

            if decision.action == "relay":
                active_workers = (
                    {s.worker for s in active_plan.steps if s.status == "running"}
                    if active_plan else set()
                )
                streamed_idle = False
                for w in decision.who:
                    if run is not None and w in active_workers:
                        # 在干活 → 投递层：in-flight 进桶 / parked 当答复 resume
                        responded.add(w)  # router 下轮不再选
                        await run.relay(w, text)
                    else:
                        member = next((m for m in members if m.name == w), None)
                        if member is None:
                            continue  # 幻觉名 → 跳过
                        streamed_idle = True
                        responded.add(w)  # 标记已回，router 下轮不再选
                        async for evt in self._stream_one_agent(
                            session=session, group=group, target=member, trigger=trigger
                        ):
                            yield evt
                if not streamed_idle:
                    return  # 纯后台投递（全是在干活的成员）→ 不回环
                if rounds >= _DISCUSS_SOFT_LIMIT:
                    logger.warning(
                        "讨论 session=%s 已达 %d 轮仍未收敛（仅观察，不截断）", session.id, rounds
                    )
                continue  # 回完群聊讨论 → 再 decide（多轮）

            # done → 收敛退出。但如果原因是路由错误（LLM 失败/非法 action），
            # 必须告知用户，不能静默吞掉。
            if decision.reason and (
                decision.reason.startswith("llm error")
                or decision.reason.startswith("invalid action")
            ):
                yield StreamEvent(
                    type=StreamEventType.TEXT,
                    seq=0,
                    content="⚠️ 消息路由暂时不可用，请稍后重试或 @ 指定成员。",
                )
            return

    # --- v3 前门反射 + 轻执行（步1）---

    @staticmethod
    def _is_broadcast(trigger: Message) -> bool:
        """全体意图（大家/各位…），仅用户消息触发。从 Selector L1.5 提升。"""
        if trigger.sender_agent_id is not None:
            return False
        return bool(_BROADCAST_RE.search(trigger.content or ""))

    @staticmethod
    def _is_confirmation(text: str) -> bool:
        """破坏性 replan 的确认词（零 LLM）。"""
        return bool(_CONFIRM_RE.match(text.strip()))

    async def _group_members(self, group: Group) -> list[Agent]:
        """群成员 Agent 列表（decide 候选 + broadcast 目标）。"""
        return [
            a for mid in group.member_ids if (a := await self._agents.get_by_id(mid)) is not None
        ]

    # --- 任务编排接线（Phase 5）---

    async def _start_coordinator(
        self, session: Session, group: Group, trigger: Message
    ) -> None:
        """收 decompose → 起后台 Orchestrator。fire-and-forget，异常不上抛。"""
        run = CoordinatorRun(session_id=session.id)
        if not self._registry.try_reserve(session.id, run):  # 同步占位，先于任何 await
            await self._post_system_sync(session, "已有任务执行中，请等待或发送「取消」")
            return
        try:
            members = [
                a
                for mid in group.member_ids
                if (a := await self._agents.get_by_id(mid)) is not None
            ]
            orchestrator = await self._build_orch(
                task=trigger.content or "", members=members, session=session, group=group
            )
        except Exception as exc:
            self._registry.release(session.id)
            logger.exception("Coordinator 组装失败 session=%s", session.id)
            await self._post_system_sync(session, f"任务启动失败: {exc}")
            return

        run.start(
            orchestrator,
            on_done=lambda r: self._coord_post(
                session.id, r.summary or f"任务结束: {r.reason}", group.coordinator_id
            ),
            on_error=lambda e: self._coord_post(
                session.id, f"任务执行失败: {e}", group.coordinator_id
            ),
            registry=self._registry,
        )
        logger.info("Coordinator 启动 run=%s session=%s", run.run_id, session.id)

    async def _cancel_coordinator(self, session: Session, run: CoordinatorRun) -> None:
        await run.cancel()
        self._registry.release(session.id)
        await self._post_system_sync(session, "已取消当前任务（已完成的成果保留）")

    # --- v4 R5：replan（DAG 手术 + 破坏性确认）---

    async def _handle_replan(
        self, session: Session, group: Group, run: CoordinatorRun, requirement: str
    ) -> None:
        """执行期改方案：重分解 → diff → 破坏性发确认/非破坏性直接换图。"""
        try:
            planned = await run.plan_replan(requirement)
        except Exception as exc:
            logger.exception("replan 重分解失败 session=%s", session.id)
            await self._post_system_sync(session, f"计划变更失败：{exc}")
            return
        if planned is None:
            return
        new_tasks, diff = planned

        if diff.is_destructive:
            await self._post_system_sync(session, _format_replan_confirmation(diff, requirement))
            run.stash_replan(requirement, new_tasks, diff)
            logger.info("replan 破坏性，等待确认 session=%s running=%s", session.id, diff.running)
            return

        await run.replan(new_tasks)
        await self._post_system_sync(session, f"✅ 计划已更新：新计划 {diff.new_count} 项。")
        logger.info("replan 非破坏性，直接换图 session=%s", session.id)

    async def _post_system_sync(self, session: Session, content: str) -> None:
        """请求作用域内落系统消息（用本请求的 repo/bus）。后台路径用 _coord_post。"""
        msg = Message(
            session_id=session.id, role=MessageRole.SYSTEM, content=content
        )
        await self._messages.save(msg)
        await self._bus.publish(
            MessageSent(
                session_id=session.id,
                message_id=msg.id,
                role="system",
                content_type="text",
            )
        )

    async def _resolve_mentions(self, mention_names: list[str], group: Group) -> list[Agent]:
        """按 @name 解析为 Agent 实体（跳过不存在 / 不在群成员的）。"""
        if not mention_names:
            return []
        valid_ids = {*group.member_ids, group.coordinator_id}
        resolved: list[Agent] = []
        seen: set[uuid.UUID] = set()
        for name in mention_names:
            agent = await self._agents.get_by_name(name)
            if agent is None:
                logger.debug("@%s 解析失败：Agent 不存在", name)
                continue
            if agent.id not in valid_ids:
                logger.debug("@%s 解析失败：Agent 不在群成员", name)
                continue
            if agent.id in seen:
                continue
            resolved.append(agent)
            seen.add(agent.id)
        return resolved

    # --- 公共：单 Agent 流式执行 + 落库 + 推 watermark ---

    async def _stream_one_agent(
        self,
        *,
        session: Session,
        group: Group | None,
        target: Agent,
        trigger: Message,
    ) -> AsyncIterator[StreamEvent]:
        request = await self._ctx.build_for_agent(
            session=session, group=group, target_agent=target, trigger=trigger
        )
        adapter = build_adapter_for_agent(target)

        assistant_msg = Message(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content="",
            sender_agent_id=target.id,
            status=MessageStatus.STREAMING,
        )
        await self._bus.publish(
            StreamingStarted(session_id=session.id, message_id=assistant_msg.id)
        )

        buffer: list[str] = []
        last_event: StreamEvent | None = None
        accumulated_meta: dict = {}  # 收集所有事件的 token_usage/usage
        try:
            async for raw_event in adapter.stream(request):
                event = self._tag_sender(raw_event, target.id)
                if event.type == StreamEventType.TEXT and event.content:
                    buffer.append(event.content)
                # 收集所有事件的 token 元数据（某些 runtime 不放 DONE 事件里）
                if event.metadata:
                    for k in ("token_usage", "usage", "model"):
                        if k in (event.metadata or {}):
                            accumulated_meta[k] = event.metadata[k]
                last_event = event
                yield event
        except Exception as exc:
            logger.exception("流式执行失败 agent=%s", target.id)
            assistant_msg.status = MessageStatus.FAILED
            await self._bus.publish(
                StreamingFailed(
                    session_id=session.id,
                    message_id=assistant_msg.id,
                    error=str(exc),
                )
            )
            raise

        # 权限阻断
        if (
            last_event
            and last_event.type == StreamEventType.DONE
            and last_event.metadata.get("permission_denials")
        ):
            yield StreamEvent(
                type=StreamEventType.REQUEST_APPROVAL,
                seq=last_event.seq + 1,
                content="以下操作被安全策略阻断",
                metadata={
                    "message_id": str(assistant_msg.id),
                    "session_id": str(session.id),
                    "denied_ops": last_event.metadata["permission_denials"],
                },
                sender_agent_id=target.id,
            )

        # 落库 + 推进 watermark + L1
        full = "".join(buffer)
        assistant_msg.content = full
        assistant_msg.status = MessageStatus.COMPLETED
        await self._messages.save(assistant_msg)
        await self._l1.append(session.id, {"role": "assistant", "content": full})
        if group is not None:
            await self._wm.set(group.id, target.id, assistant_msg.id)

        # P1-2 token 消耗监控触发点（LLM 完成路径）
        if self._usage is not None:
            try:
                # 优先用 last_event（DONE 事件通常含最全 metadata），
                # 再合并 accumulated_meta（兜底非 DONE 事件里的 token_usage）
                last_meta = dict(last_event.metadata) if last_event and last_event.metadata else {}
                last_meta = {**accumulated_meta, **last_meta}  # last_event 优先
                model = last_meta.get("model")
                await self._usage.record_completion(
                    session_id=session.id,
                    message_id=assistant_msg.id,
                    agent_id=target.id,
                    content=full,
                    metadata=last_meta if last_meta else None,
                    model=model,
                )
            except Exception:
                logger.exception("record_completion failed (non-fatal) session=%s", session.id)

        await self._bus.publish(
            StreamingCompleted(session_id=session.id, message_id=assistant_msg.id)
        )

    # --- 工具 ---

    async def _persist_user_message(self, session: Session, cmd: SendMessageCommand) -> Message:
        msg = Message(
            session_id=session.id,
            role=MessageRole.USER,
            content=cmd.content,
            mentions=cmd.mentions,
            reply_to=cmd.reply_to,
        )
        await self._messages.save(msg)
        await self._l1.append(session.id, {"role": "user", "content": cmd.content})
        # P1-2 token 消耗监控触发点（用户消息路径）
        if self._usage is not None:
            try:
                await self._usage.record_user_message(
                    session_id=session.id, message_id=msg.id, content=cmd.content
                )
            except Exception:
                logger.exception("record_user_message failed (non-fatal) session=%s", session.id)
        await self._bus.publish(
            MessageSent(
                session_id=session.id,
                message_id=msg.id,
                role="user",
                content_type="text",
            )
        )
        return msg

    @staticmethod
    def _tag_sender(event: StreamEvent, sender_id: uuid.UUID) -> StreamEvent:
        if event.sender_agent_id is None:
            return event.model_copy(update={"sender_agent_id": sender_id})
        return event
