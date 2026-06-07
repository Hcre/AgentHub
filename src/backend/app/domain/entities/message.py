"""Message 实体：会话内的一条消息。"""

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
    sender_agent_id: UUID | None = None
    mentions: list[str] = field(default_factory=list)
    reply_to: UUID | None = None
    pinned: bool = False
    status: MessageStatus = MessageStatus.COMPLETED
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    # P0-4: 消息发送者 + Pin 审计
    user_id: UUID | None = None
    pinned_by_user_id: UUID | None = None
    pinned_at: datetime | None = None

    def pin(self, by_user_id: UUID | None = None) -> None:
        self.pinned = True
        self.pinned_by_user_id = by_user_id
        self.pinned_at = _now()

    def unpin(self) -> None:
        self.pinned = False
        self.pinned_by_user_id = None
        self.pinned_at = None
