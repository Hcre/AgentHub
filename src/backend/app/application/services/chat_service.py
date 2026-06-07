"""ChatService（L3）：私聊 + 群聊统一入口。

数据流（架构文档 S11/S12/S22 + group-chat 设计文档 §3）：
  持久化用户消息 → 写 L1 滑动窗口 → 路由目标 Agent(s)
  → 对每个 Agent: ContextBuilder.build_for_agent → 适配器流式
  → 完成时落库 + 推进 watermark + 重写 L1
  → 触发 token 消耗监控（P1-2 record_completion / record_user_message）

群聊路由：
  - 用户 @ Agent → V1 串行执行（list[Agent]）
  - 群组 dispatch_mode == DISCUSSION 且无 @ → 进入讨论循环（Phase 6 接入）
  - 其余 → 死群静默（仅广播用户消息）
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import AsyncIterator

from app.application.commands import SendMessageCommand
from app.application.services.context_builder import ContextBuilder
from app.application.services.discussion_orchestrator import DiscussionOrchestrator
from app.application.services.usage_service import UsageService
from app.core.events import EventBus
from app.core.exceptions import NotFoundError
from app.domain.entities.agent import Agent
from app.domain.entities.group import Group
from app.domain.entities.message import Message
from app.domain.entities.session import Session
from app.domain.enums import DispatchMode, MessageRole, MessageStatus, SessionType
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
from app.infrastructure.cache.memory_l1 import L1MemoryStore
from app.infrastructure.cache.watermark_store import WatermarkStore
from app.infrastructure.llm.factory import build_adapter_for_agent

logger = logging.getLogger(__name__)


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
        discussion: DiscussionOrchestrator,
        llm: UnifiedAgent,
        event_bus: EventBus,
        usage_service: UsageService | None = None,
    ) -> None:
        self._sessions = session_repo
        self._messages = message_repo
        self._agents = agent_repo
        self._groups = group_repo
        self._l1 = l1_memory
        self._wm = watermarks
        self._ctx = context_builder
        self._discussion = discussion
        self._llm = llm  # 全局默认，per-agent 覆盖时优先
        self._bus = event_bus
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

        # 无 @：根据群组模式决定
        mode = group.dispatch_mode
        if mode == DispatchMode.DISCUSSION:
            async for evt in self._discussion.run_discussion(
                session=session, group=group, trigger=trigger
            ):
                yield evt
            return

        # AT_ROUTING / 其他：死群静默（设计决策见实施计划 §六）
        logger.debug("群组 %s 无 @ 提及，静默处理", group.id)

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
        try:
            async for raw_event in adapter.stream(request):
                event = self._tag_sender(raw_event, target.id)
                if event.type == StreamEventType.TEXT and event.content:
                    buffer.append(event.content)
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
