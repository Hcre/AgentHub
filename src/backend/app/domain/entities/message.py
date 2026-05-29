"""Message 实体：会话内的一条消息，支持富媒体产物（content_type + metadata）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.enums import ContentType, MessageRole, MessageStatus


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Message:
    session_id: UUID
    role: MessageRole
    content: str
    id: UUID = field(default_factory=uuid4)
    content_type: ContentType = ContentType.TEXT
    sender_agent_id: UUID | None = None  # assistant 消息的来源 Agent
    mentions: list[str] = field(default_factory=list)  # @ 的 Agent name
    reply_to: UUID | None = None
    pinned: bool = False
    status: MessageStatus = MessageStatus.COMPLETED
    metadata: dict = field(default_factory=dict)  # diff/preview/task_plan 附加数据
    created_at: datetime = field(default_factory=_now)

    def pin(self) -> None:
        self.pinned = True

    def unpin(self) -> None:
        self.pinned = False
