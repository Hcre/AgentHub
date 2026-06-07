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

import asyncio as _asyncio
import logging
from collections.abc import AsyncIterator
from uuid import UUID

from app.application.services.context_builder import ContextBuilder
from app.application.services.selector import Selector, SelectorDecision
from app.application.services.usage_service import UsageService
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
        usage_service: UsageService | None = None,
    ) -> None:
        self._messages = message_repo
        self._agents = agent_repo
        self._l1 = l1_memory
        self._wm = watermarks
        self._ctx = context_builder
        self._sel = selector
        self._bus = event_bus
        self._usage = usage_service  # P1-2 token 监控；None 时降级为 no-op
        self._flush_lock = _asyncio.Lock()  # 多 Agent 并发写 DB 的串行锁

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
        pending_mentions: list[UUID] = []
        last_msg_for_history: Message = trigger

        for round_no in range(max_round):
            # 1. 取候选成员
            members = await self._load_members(group)
            if not members:
                logger.debug("讨论中止：群组 %s 无成员", group.id)
                return

            # 2. 取最近 history（含本轮已发言）
            history = await self._fetch_history(session, since=trigger)

            # 3. Selector 决策（pending_mentions 非空时优先出队）
            decision: SelectorDecision | None = None
            while pending_mentions:
                next_id = pending_mentions.pop(0)
                if next_id in already_spoken:
                    continue
                hit = await self._agents.get_by_id(next_id)
                if hit is None:
                    continue
                decision = SelectorDecision.pick(
                    next_id,
                    reason="@mention queue",
                    mention_queue=tuple(pending_mentions),
                )
                break

            if decision is None:
                decision = await self._sel.pick(
                    members=members,
                    history=history,
                    already_spoken=already_spoken,
                )

            # 合并 Selector 返回的新 mention_queue 到 pending
            if decision.mention_queue:
                # 去重：已在 pending 或已发言的不重复入队
                for mid in decision.mention_queue:
                    if mid not in pending_mentions and mid not in already_spoken:
                        pending_mentions.append(mid)

            # 用户消息首轮不能落空：Selector 判 DONE 时随机选一人兜底
            if round_no == 0 and decision.done and decision.picks == ():
                import random as _random

                fallback = _random.choice(members)
                logger.info("讨论 round=0 Selector=DONE，随机兜底 agent=%s", fallback.name)
                decision = SelectorDecision.pick(
                    fallback.id, reason="fallback: selector done, random pick"
                )

            logger.info(
                "讨论 round=%d session=%s decision=%s reason=%s pending=%d",
                round_no,
                session.id,
                decision.next_agent_id or "DONE",
                decision.reason,
                len(pending_mentions),
            )
            # 4. 分支：多选（picks）vs 单选
            if decision.picks:
                # 同回合多人并行
                pick_ids = list(dict.fromkeys(decision.picks))  # 去重保序
                pick_targets: list[Agent] = []
                for pid in pick_ids:
                    t = await self._agents.get_by_id(pid)
                    if t is not None:
                        pick_targets.append(t)
                    else:
                        logger.warning("讨论 multi-pick 目标 %s 不存在，跳过", pid)

                if not pick_targets:
                    return

                logger.info(
                    "讨论 round=%d multi-pick=%d agents=%s",
                    round_no,
                    len(pick_targets),
                    [t.name for t in pick_targets],
                )

                # 并行流式：用 asyncio.Queue 合并多路 StreamEvent
                queue: _asyncio.Queue[StreamEvent | None] = _asyncio.Queue()

                async def _stream_into_q(agent: Agent) -> None:
                    try:
                        async for evt in self._stream_one(
                            session=session,
                            group=group,
                            target=agent,
                            trigger=last_msg_for_history,
                        ):
                            await queue.put(evt)  # noqa: B023
                    except Exception:
                        logger.exception("multi-pick 流式失败 agent=%s", agent.id)
                    finally:
                        await queue.put(None)  # noqa: B023

                tasks = [_asyncio.create_task(_stream_into_q(a)) for a in pick_targets]
                finished = 0
                while finished < len(tasks):
                    evt = await queue.get()
                    if evt is None:
                        finished += 1
                        continue
                    yield evt
                await _asyncio.gather(*tasks, return_exceptions=True)

                for t in pick_targets:
                    already_spoken.add(t.id)
                return  # multi-pick 消耗完整回合，不继续循环

            if decision.done or decision.next_agent_id is None:
                return

            # 5. 取目标 Agent（单人）
            target = await self._agents.get_by_id(decision.next_agent_id)
            if target is None:
                logger.warning("讨论中目标 Agent %s 不存在，跳过", decision.next_agent_id)
                continue

            # 6. 单 Agent 流式
            async for evt in self._stream_one(
                session=session,
                group=group,
                target=target,
                trigger=last_msg_for_history,
            ):
                yield evt

            # 7. 标记已发言
            already_spoken.add(target.id)

        logger.info("讨论达到 max_round=%d，自然结束 session=%s", max_round, session.id)

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
        async with self._flush_lock:  # 多 Agent 并发时串行落库
            await self._messages.save(assistant_msg)
            await self._l1.append(session.id, {"role": "assistant", "content": full})
            await self._wm.set(group.id, target.id, assistant_msg.id)

        # P1-2 token 消耗监控触发点（讨论模式 LLM 完成路径）
        if self._usage is not None:
            try:
                last_meta = last_event.metadata if last_event else None
                model = last_meta.get("model") if last_meta else None
                await self._usage.record_completion(
                    session_id=session.id,
                    message_id=assistant_msg.id,
                    agent_id=target.id,
                    content=full,
                    metadata=last_meta,
                    model=model,
                )
            except Exception:
                logger.exception(
                    "record_completion failed (non-fatal) session=%s", session.id
                )

        await self._bus.publish(
            StreamingCompleted(session_id=session.id, message_id=assistant_msg.id)
        )

    # --- helpers ---

    async def _load_members(self, group: Group) -> list[Agent]:
        """加载群成员（不含协调者）。协调者负责任务分解，不参与自由讨论。"""
        ids = list(group.member_ids)  # member_ids 不含协调者
        members: list[Agent] = []
        for aid in ids:
            a = await self._agents.get_by_id(aid)
            if a is not None:
                members.append(a)
        return members

    async def _fetch_history(self, session: Session, *, since: Message) -> list[Message]:
        # 取最近 N 条作为讨论快照；since 仅用于上下文，不做时间裁剪
        recent = await self._messages.list_by_session(session.id, limit=settings.l1_window_size)
        return recent


__all__ = ["DiscussionOrchestrator", "SelectorDecision"]
