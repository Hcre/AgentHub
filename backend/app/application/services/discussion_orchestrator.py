"""DiscussionOrchestrator：群聊讨论模式回合循环。

设计依据：
- docs/design/group-chat-discussion-mode_群聊讨论模式设计方案.md §二、§6
- docs/design/group-chat-implementation-plan_群聊实施计划.md Phase 6

回合循环：
    while round < MAX_ROUND:
        decision = Selector.pick(history, members)
        if decision.done: break
        adapter.stream(target) → yield events → 落库 + 推 watermark
        round += 1

防循环三件套：
1. Selector DONE（主力）
2. MAX_ROUND 硬上限（默认 3，本期硬编码）
3. 人在环中断（由 ChatService 收新用户消息时 cancel）
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from uuid import UUID

from app.application.services.context_builder import ContextBuilder
from app.application.services.selector import Selector, SelectorDecision
from app.core.config import settings
from app.core.events import EventBus
from app.domain.entities.agent import Agent
from app.domain.entities.group import Group
from app.domain.entities.message import Message
from app.domain.entities.session import Session
from app.domain.enums import MessageRole, MessageStatus
from app.domain.events import StreamingCompleted, StreamingFailed, StreamingStarted
from app.domain.llm.protocol import StreamEvent, StreamEventType
from app.domain.repositories import AgentRepository, MessageRepository
from app.infrastructure.cache.memory_l1 import L1MemoryStore
from app.infrastructure.cache.watermark_store import WatermarkStore
from app.infrastructure.llm.factory import build_adapter_for_agent

logger = logging.getLogger(__name__)


class DiscussionOrchestrator:
    """讨论模式回合循环（无状态服务）。"""

    def __init__(
        self,
        *,
        message_repo: MessageRepository,
        agent_repo: AgentRepository,
        l1_memory: L1MemoryStore,
        watermarks: WatermarkStore,
        context_builder: ContextBuilder,
        selector: Selector,
        event_bus: EventBus,
    ) -> None:
        self._messages = message_repo
        self._agents = agent_repo
        self._l1 = l1_memory
        self._wm = watermarks
        self._ctx = context_builder
        self._sel = selector
        self._bus = event_bus

    async def run_discussion(
        self,
        *,
        session: Session,
        group: Group,
        trigger: Message,
    ) -> AsyncIterator[StreamEvent]:
        """运行讨论循环，逐 StreamEvent yield。"""
        max_round = settings.max_discussion_rounds
        already_spoken: set[UUID] = set()
        last_msg_for_history: Message = trigger

        for round_no in range(max_round):
            # 1. 取候选成员
            members = await self._load_members(group)
            if not members:
                logger.debug("讨论中止：群组 %s 无成员", group.id)
                return

            # 2. 取最近 history（含本轮已发言）
            history = await self._fetch_history(session, since=trigger)

            # 3. Selector 决策
            decision = await self._sel.pick(
                members=members,
                history=history,
                already_spoken=already_spoken,
            )
            logger.info(
                "讨论 round=%d session=%s decision=%s reason=%s",
                round_no,
                session.id,
                decision.next_agent_id or "DONE",
                decision.reason,
            )
            if decision.done or decision.next_agent_id is None:
                return

            # 4. 取目标 Agent
            target = await self._agents.get_by_id(decision.next_agent_id)
            if target is None:
                logger.warning(
                    "讨论中目标 Agent %s 不存在，跳过", decision.next_agent_id
                )
                continue

            # 5. 单 Agent 流式
            async for evt in self._stream_one(
                session=session,
                group=group,
                target=target,
                trigger=last_msg_for_history,
            ):
                yield evt

            # 6. 标记已发言
            already_spoken.add(target.id)

        logger.info(
            "讨论达到 max_round=%d，自然结束 session=%s", max_round, session.id
        )

    # --- 流式单 Agent（与 ChatService._stream_one_agent 同构，避免循环依赖单独实现） ---

    async def _stream_one(
        self,
        *,
        session: Session,
        group: Group,
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
        try:
            async for raw in adapter.stream(request):
                evt = (
                    raw
                    if raw.sender_agent_id is not None
                    else raw.model_copy(update={"sender_agent_id": target.id})
                )
                if evt.type == StreamEventType.TEXT and evt.content:
                    buffer.append(evt.content)
                last_event = evt
                yield evt
        except Exception as exc:
            logger.exception("讨论流式失败 agent=%s", target.id)
            assistant_msg.status = MessageStatus.FAILED
            await self._bus.publish(
                StreamingFailed(
                    session_id=session.id,
                    message_id=assistant_msg.id,
                    error=str(exc),
                )
            )
            raise

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

        full = "".join(buffer)
        assistant_msg.content = full
        assistant_msg.status = MessageStatus.COMPLETED
        await self._messages.save(assistant_msg)
        await self._l1.append(session.id, {"role": "assistant", "content": full})
        await self._wm.set(group.id, target.id, assistant_msg.id)
        await self._bus.publish(
            StreamingCompleted(session_id=session.id, message_id=assistant_msg.id)
        )

    # --- helpers ---

    async def _load_members(self, group: Group) -> list[Agent]:
        ids = list({*group.member_ids, group.coordinator_id})
        members: list[Agent] = []
        for aid in ids:
            a = await self._agents.get_by_id(aid)
            if a is not None:
                members.append(a)
        return members

    async def _fetch_history(
        self, session: Session, *, since: Message
    ) -> list[Message]:
        # 取最近 N 条作为讨论快照；since 仅用于上下文，不做时间裁剪
        recent = await self._messages.list_by_session(
            session.id, limit=settings.l1_window_size
        )
        return recent


__all__ = ["DiscussionOrchestrator", "SelectorDecision"]
