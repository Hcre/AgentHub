"""ChatService（L3）：MVP 核心 —— 发送消息 + 流式输出。

CLI 模式：CLI 通过 --resume 管理自己的对话历史，AgentHub 不维护 L1。
API 模式（未实现）：由适配器自行管理消息上下文。
"""

from __future__ import annotations

import logging
import os
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
    StreamEvent,
    StreamEventType,
    UnifiedAgent,
)
from app.domain.repositories import (
    AgentRepository,
    MessageRepository,
    SessionRepository,
)
from app.infrastructure.llm.factory import build_adapter_for_agent

logger = logging.getLogger(__name__)

SKILLS_DIR = "/skills"


def _load_skill_content(skill_names: list[str]) -> str:
    """读取 skill 文件内容，拼接为 system prompt 片段。"""
    if not skill_names or not os.path.isdir(SKILLS_DIR):
        return ""
    parts: list[str] = []
    for name in skill_names:
        path = os.path.join(SKILLS_DIR, name, "SKILL.md")
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
        llm: UnifiedAgent,
        event_bus: EventBus,
    ) -> None:
        self._sessions = session_repo
        self._messages = message_repo
        self._agents = agent_repo
        self._llm = llm
        self._bus = event_bus

    async def send_and_stream(self, cmd: SendMessageCommand) -> AsyncIterator[StreamEvent]:
        """发送用户消息并流式返回 Agent 响应。"""
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

        # 3. 按 Agent 构造适配器（per-agent 路由）
        agent = await self._agents.get_by_id(agent_id)
        if agent is None:
            raise NotFoundError(f"Agent 不存在: {agent_id}")
        adapter = build_adapter_for_agent(agent)

        # 4. 构造请求（CLI 模式由 --resume 管理历史，API 模式由适配器管理）
        # 注入 skill 内容到 system prompt
        skill_content = _load_skill_content(agent.skills or [])
        system_prompt = agent.system_prompt or ""
        if skill_content:
            system_prompt = f"{system_prompt}\n\n{skill_content}".strip()

        request = AgentRequest(
            request_id=str(uuid.uuid4()),
            session_id=cmd.session_id,
            messages=[{"role": "user", "content": cmd.content}],
            system_prompt=system_prompt,
            max_tokens=settings_max_tokens(),
        )

        # 5. 流式执行
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
        last_event: StreamEvent | None = None
        try:
            async for event in adapter.stream(request):
                if event.type == StreamEventType.TEXT and event.content:
                    buffer.append(event.content)
                last_event = event
                yield event
        except Exception as exc:
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

        # 6. 权限阻断检测
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
                    "session_id": str(cmd.session_id),
                    "denied_ops": last_event.metadata["permission_denials"],
                },
            )

        # 7. 完成：落库
        full = "".join(buffer)
        assistant_msg.content = full
        assistant_msg.status = MessageStatus.COMPLETED
        await self._messages.save(assistant_msg)
        await self._bus.publish(
            StreamingCompleted(session_id=cmd.session_id, message_id=assistant_msg.id)
        )

    @staticmethod
    def _resolve_target_agent(session) -> uuid.UUID:  # type: ignore[no-untyped-def]
        if session.type == SessionType.PRIVATE and session.agent_id:
            return session.agent_id
        raise DomainError("MVP 仅支持私聊单 Agent；群聊路由待 M3")


def settings_max_tokens() -> int:
    return settings.max_tokens
