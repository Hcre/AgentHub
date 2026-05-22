"""ChatService（L3）：MVP 核心 —— 发送消息 + 流式输出 + L1 记忆。

数据流（架构文档 S11/S12/S22）：
  持久化用户消息 → 写入 L1 滑动窗口 → 构造带记忆的 AgentRequest
  → 适配器流式产出 StreamEvent（逐事件 yield 给 WS）
  → 完成时落库 assistant 消息 + 写入 L1。
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator

from app.application.commands import SendMessageCommand
from app.core.config import settings
from app.core.events import EventBus
from app.core.exceptions import DomainError, NotFoundError
from app.domain.entities.message import Message
from app.domain.enums import MessageRole, MessageStatus, SessionType
from app.domain.events import (
    MessageSent,
    StreamingCompleted,
    StreamingFailed,
    StreamingStarted,
)
from app.domain.llm.protocol import (
    AgentRequest,
    MemoryContext,
    StreamEvent,
    StreamEventType,
    UnifiedAgent,
)
from app.domain.repositories import (
    AgentRepository,
    MessageRepository,
    SessionRepository,
)
from app.infrastructure.cache.memory_l1 import L1MemoryStore

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        agent_repo: AgentRepository,
        l1_memory: L1MemoryStore,
        llm: UnifiedAgent,
        event_bus: EventBus,
    ) -> None:
        self._sessions = session_repo
        self._messages = message_repo
        self._agents = agent_repo
        self._l1 = l1_memory
        self._llm = llm
        self._bus = event_bus

    async def send_and_stream(
        self, cmd: SendMessageCommand
    ) -> AsyncIterator[StreamEvent]:
        """发送用户消息并流式返回 Agent 响应。供 WS 处理器消费后推送前端。"""
        session = await self._sessions.get_by_id(cmd.session_id)
        if session is None:
            raise NotFoundError(f"会话不存在: {cmd.session_id}")

        # 1. 持久化用户消息
        user_msg = Message(
            session_id=cmd.session_id,
            role=MessageRole.USER,
            content=cmd.content,
            mentions=cmd.mentions,
            reply_to=cmd.reply_to,
        )
        await self._messages.save(user_msg)
        await self._l1.append(
            cmd.session_id, {"role": "user", "content": cmd.content}
        )
        await self._bus.publish(
            MessageSent(
                session_id=cmd.session_id,
                message_id=user_msg.id,
                role="user",
                content_type="text",
            )
        )

        # 2. 解析目标 Agent（MVP：私聊固定 session.agent_id）
        agent_id = self._resolve_target_agent(session)

        # 3. 构造带 L1 记忆的请求
        window = await self._l1.get_window(cmd.session_id)
        request = AgentRequest(
            request_id=str(uuid.uuid4()),
            session_id=cmd.session_id,
            messages=window,
            memory=MemoryContext(l1_working=window),
            max_tokens=settings_max_tokens(),
        )

        # 4. 流式执行
        assistant_msg = Message(
            session_id=cmd.session_id,
            role=MessageRole.ASSISTANT,
            content="",
            sender_agent_id=agent_id,
            status=MessageStatus.STREAMING,
        )
        await self._bus.publish(
            StreamingStarted(session_id=cmd.session_id, message_id=assistant_msg.id)
        )

        buffer: list[str] = []
        try:
            async for event in self._llm.stream(request):
                if event.type == StreamEventType.TEXT and event.content:
                    buffer.append(event.content)
                yield event
        except Exception as exc:  # noqa: BLE001 - 边界统一兜底
            logger.exception("流式执行失败")
            assistant_msg.status = MessageStatus.FAILED
            await self._bus.publish(
                StreamingFailed(
                    session_id=cmd.session_id,
                    message_id=assistant_msg.id,
                    error=str(exc),
                )
            )
            raise

        # 5. 完成：落库 + 写 L1
        full = "".join(buffer)
        assistant_msg.content = full
        assistant_msg.status = MessageStatus.COMPLETED
        await self._messages.save(assistant_msg)
        await self._l1.append(
            cmd.session_id, {"role": "assistant", "content": full}
        )
        await self._bus.publish(
            StreamingCompleted(
                session_id=cmd.session_id, message_id=assistant_msg.id
            )
        )

    @staticmethod
    def _resolve_target_agent(session) -> uuid.UUID:  # type: ignore[no-untyped-def]
        if session.type == SessionType.PRIVATE and session.agent_id:
            return session.agent_id
        # 群聊路由（@指定 / @协调者 / 自动检测）在 M3 实现
        raise DomainError("MVP 仅支持私聊单 Agent；群聊路由待 M3")


def settings_max_tokens() -> int:
    return settings.max_tokens
