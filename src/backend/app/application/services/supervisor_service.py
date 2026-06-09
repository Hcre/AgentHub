"""SupervisorService（L3）：监督者事件处理 + CLI turn 调度。

实现 Supervisor Protocol，在收到域事件时：
  1. 调用域决策引擎（supervisor.py）产决策建议
  2. 对需要执行的决定（nudge/replan/deploy），通过 event_sink 发消息
  3. 对需要 CLI 推理的决定，spawn 后台 CLI turn 让 supervisor agent 审阅

设计约束：
  - 所有操作不阻塞 orchestrator 主循环（fire-and-forget + try/except）
  - 通过 _ACTIVE registry 读取/写入任务状态
  - 若 supervisor_agent 不存在或配置 disabled，静默跳过
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from app.domain.entities.agent import Agent
from app.domain.llm.protocol import AgentRequest, StreamEventType
from app.domain.task_engine.ports import (
    StallEvent,
    StepEvent,
    Supervisor,
    SupervisorConfig,
)
from app.domain.task_engine.supervisor import (
    SupervisorDecision,
    SupervisorDecisionKind,
    SupervisorState,
    decide_on_all_completed,
    decide_on_stall,
    decide_on_step_completed,
    decide_on_step_failed,
)

logger = logging.getLogger(__name__)

# 按 supervisor agent 的 CLI turn：单次最长时间（秒）
_SUPERVISOR_TURN_TIMEOUT = 120.0

# 注入：agent 名 → Agent 实体的 lookup
ResolveAgent = Callable[[str], Agent | None]
# 注入：Agent → 适配器工厂（复用 build_adapter_for_agent）
AdapterFactory = Callable[[Agent], object]


def _build_supervisor_tool_url(agent_id: UUID, session_id: UUID, group_id: UUID) -> str:
    """构建 supervisor MCP 工具 SSE URL（agent_id/session_id/group_id 注入）。"""
    from app.core.config import settings
    base = getattr(settings, "mcp_supervisor_tools_url", "") or ""
    if not base:
        logger.warning("mcp_supervisor_tools_url 未配置，supervisor 工具不可用")
        return ""
    return f"{base}?agent_id={agent_id}&session_id={session_id}&group_id={group_id}"


_SUPERVISOR_SYSTEM_PROMPT = """你是 AgentHub 任务监督者。你的职责是观察任务执行进度，在必要时做出判断。

你有以下工具可用：
- `supervisor_get_plan` — 查看当前任务计划和各步骤状态
- `supervisor_nudge` — 轻推某个 worker（提示继续/交卷）
- `supervisor_replan` — 建议重新分解任务
- `supervisor_trigger_deploy` — 触发部署
- `supervisor_send_message` — 发送消息到群聊

原则：
1. 观察为主，干预为辅。推进顺利时不说话。
2. 发现卡死/失败时，先轻推 worker，无效再建议 replan。
3. 全部完成时，产出简短总结（1-3 句），可选建议部署。
4. 保持消息简短、可操作。不要猜测或过度解释。
"""


class SupervisorService:
    """监督者事件处理 + CLI turn 调度。

    实现 Supervisor Protocol。每个事件到达时：
      - 调决策引擎 → 决策列表
      - ALERT/NUDGE/SUMMARIZE → 直接发 system 消息到群聊（轻量）
      - REPLAN/DEPLOY → spawn 后台 CLI turn 让 supervisor agent 执行工具
    """

    def __init__(
        self,
        *,
        session_id: UUID,
        group_id: UUID,
        coordinator_id: UUID,
        config: SupervisorConfig | None = None,
        resolve_agent: ResolveAgent | None = None,
        adapter_factory: AdapterFactory | None = None,
    ) -> None:
        self._session_id = session_id
        self._group_id = group_id
        self._coordinator_id = coordinator_id
        self._config = config or SupervisorConfig(
            supervisor_agent_id="", enabled=False
        )
        self._resolve = resolve_agent
        self._adapter_factory = adapter_factory
        self._state = SupervisorState()
        self._active_tasks: set[asyncio.Task] = set()

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def _can_spawn(self) -> bool:
        """是否可 spawn CLI turn：必须有 agent 和 adapter factory。"""
        return (
            self._config.enabled
            and bool(self._config.supervisor_agent_id)
            and self._resolve is not None
            and self._adapter_factory is not None
        )

    async def _resolve_supervisor_agent(self) -> Agent | None:
        """解析 supervisor agent。"""
        if self._resolve is None:
            return None
        agent = self._resolve(self._config.supervisor_agent_id)
        if agent is None:
            logger.warning(
                "Supervisor agent %s 不存在，跳过", self._config.supervisor_agent_id
            )
        return agent

    async def _post_message(self, content: str) -> None:
        """发系统消息到群聊（独立 DB session）。"""
        from app.application.services.coordinator_run import post_system_background
        try:
            await post_system_background(
                self._session_id, content, self._coordinator_id
            )
        except Exception:
            logger.exception("Supervisor 发送消息失败 session=%s", self._session_id)

    def _run_decisions(
        self, decisions: list[SupervisorDecision]
    ) -> None:
        """执行决策列表：轻量操作直接执行，重量操作 spawn CLI turn。"""
        for d in decisions:
            if d.kind == SupervisorDecisionKind.NONE:
                continue
            elif d.kind == SupervisorDecisionKind.ALERT:
                asyncio.create_task(self._post_message(d.message))
            elif d.kind == SupervisorDecisionKind.NUDGE:
                asyncio.create_task(self._execute_nudge(d))
            elif d.kind == SupervisorDecisionKind.SUMMARIZE:
                asyncio.create_task(self._post_message(d.message))
            elif d.kind in (
                SupervisorDecisionKind.REPLAN,
                SupervisorDecisionKind.DEPLOY,
            ):
                self._spawn_supervisor_turn(d)
            else:
                logger.debug("Supervisor 未知决策 kind=%s", d.kind)

    async def _execute_nudge(self, decision: SupervisorDecision) -> None:
        """轻推某个 worker：通过 relay 机制投递消息到 worker 的桶。"""
        if not decision.target_worker:
            return
        from app.application.services.coordinator_run import _ACTIVE
        run = _ACTIVE.get(self._session_id)
        if run is None:
            return
        try:
            run.enqueue_note(decision.message, decision.target_worker)
        except Exception:
            logger.exception(
                "Supervisor nudge 失败 session=%s worker=%s",
                self._session_id, decision.target_worker,
            )

    def _spawn_supervisor_turn(self, decision: SupervisorDecision) -> None:
        """后台启动一个 supervisor CLI turn 执行重量决策。

        用 fire-and-forget 模式：不阻塞 orchestrator，异常由内部 try/except 吞掉。
        """
        if not self._can_spawn():
            logger.debug(
                "Supervisor: 不能 spawn turn (enabled=%s agent=%s resolve=%s factory=%s)",
                self._config.enabled,
                self._config.supervisor_agent_id,
                self._resolve is not None,
                self._adapter_factory is not None,
            )
            return
        # 限制并发 turn 数
        if len(self._active_tasks) >= self._config.max_turns:
            logger.info(
                "Supervisor: 已达 max_turns=%s，丢弃决策 kind=%s",
                self._config.max_turns, decision.kind,
            )
            return
        task = asyncio.create_task(self._run_supervisor_turn(decision))
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)

    async def _run_supervisor_turn(self, decision: SupervisorDecision) -> None:
        """执行一次 supervisor CLI turn。

        构建 prompt → adapter.stream → 等待 DONE。所有异常在内部捕获，
        绝不传播到 orchestrator。
        """
        from app.application.services.coordinator_run import post_system_background

        try:
            agent = await self._resolve_supervisor_agent()
            if agent is None:
                return

            prompt = self._build_turn_prompt(decision)
            tool_url = _build_supervisor_tool_url(
                agent.id, self._session_id, self._group_id
            )
            mcp_servers: list[dict] = []
            if tool_url:
                mcp_servers.append({
                    "name": "agenthub-supervisor-tools",
                    "type": "sse",
                    "url": tool_url,
                })

            request = AgentRequest(
                request_id=f"supervisor-{self._session_id.hex[:8]}-{decision.kind}",
                session_id=self._session_id,
                messages=[{"role": "user", "content": prompt}],
                system_prompt=_SUPERVISOR_SYSTEM_PROMPT,
                agent_id=agent.id,
                group_id=self._group_id,
                is_group_chat=True,
                has_history=False,
                mcp_servers=mcp_servers,
            )

            adapter = self._adapter_factory(agent)  # type: ignore[misc]
            logger.info(
                "Supervisor CLI turn 启动 session=%s decision=%s agent=%s",
                self._session_id, decision.kind, agent.name,
            )

            try:
                async for evt in adapter.stream(request):  # type: ignore[attr-defined]
                    # supervisor 输出经 system 通道入群聊
                    if evt.type == StreamEventType.TEXT and evt.content:
                        try:
                            await post_system_background(
                                self._session_id, evt.content, self._coordinator_id
                            )
                        except Exception:
                            logger.exception("Supervisor 输出落库失败")
                    elif evt.type == StreamEventType.ERROR:
                        logger.warning(
                            "Supervisor turn 错误: %s", evt.content
                        )
            except TimeoutError:
                logger.warning("Supervisor turn 超时 session=%s", self._session_id)
            except Exception:
                logger.exception("Supervisor turn 流异常 session=%s", self._session_id)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Supervisor turn 致命异常 session=%s", self._session_id
            )

    @staticmethod
    def _build_turn_prompt(decision: SupervisorDecision) -> str:
        """根据决策类型构建 supervisor 的 CLI turn prompt。"""
        if decision.kind == SupervisorDecisionKind.REPLAN:
            return (
                f"任务执行出现问题：{decision.reason}\n\n"
                f"详情：{decision.detail}\n\n"
                f"请使用 `supervisor_get_plan` 查看当前计划状态，"
                f"然后用 `supervisor_replan` 或 `supervisor_send_message` 处理。"
            )
        elif decision.kind == SupervisorDecisionKind.DEPLOY:
            return (
                f"所有任务已完成：{decision.reason}\n\n"
                f"请使用 `supervisor_get_plan` 确认状态，"
                f"若确认无误，调用 `supervisor_trigger_deploy` 触发部署。"
            )
        else:
            return (
                f"需要你的关注：{decision.reason}\n\n"
                f"请使用 `supervisor_get_plan` 查看当前状态，"
                f"用 `supervisor_send_message` 或其他工具执行后续操作。"
            )

    # ── Supervisor Protocol 实现 ──────────────────────────────────────────────

    async def on_step_completed(self, session_id: UUID, event: StepEvent) -> None:
        if not self._config.enabled:
            return
        try:
            decisions = decide_on_step_completed(event, self._state, self._config)
            self._run_decisions(decisions)
        except Exception:
            logger.exception("on_step_completed 处理异常 session=%s", session_id)

    async def on_step_failed(self, session_id: UUID, event: StepEvent) -> None:
        if not self._config.enabled:
            return
        try:
            decisions = decide_on_step_failed(event, self._state, self._config)
            self._run_decisions(decisions)
        except Exception:
            logger.exception("on_step_failed 处理异常 session=%s", session_id)

    async def on_all_completed(self, session_id: UUID) -> None:
        if not self._config.enabled:
            return
        try:
            completed = self._state.completed_count
            decisions = decide_on_all_completed(completed, self._state, self._config)
            self._run_decisions(decisions)
        except Exception:
            logger.exception("on_all_completed 处理异常 session=%s", session_id)

    async def on_stall_detected(self, session_id: UUID, event: StallEvent) -> None:
        if not self._config.enabled:
            return
        try:
            decisions = decide_on_stall(event, self._state, self._config)
            self._run_decisions(decisions)
        except Exception:
            logger.exception("on_stall_detected 处理异常 session=%s", session_id)
