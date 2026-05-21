"""领域事件目录（对应架构文档 §2.3）。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.events.base import DomainEvent

# === Agent Events ===


@dataclass(frozen=True, kw_only=True)
class AgentCreated(DomainEvent):
    agent_id: UUID
    name: str
    provider: str
    model: str


@dataclass(frozen=True, kw_only=True)
class AgentUpdated(DomainEvent):
    agent_id: UUID
    changed_fields: list[str]


@dataclass(frozen=True, kw_only=True)
class AgentDeleted(DomainEvent):
    agent_id: UUID


# === Session / Message Events ===


@dataclass(frozen=True, kw_only=True)
class SessionCreated(DomainEvent):
    session_id: UUID
    type: str
    participants: list[UUID]


@dataclass(frozen=True, kw_only=True)
class MessageSent(DomainEvent):
    session_id: UUID
    message_id: UUID
    role: str
    content_type: str


@dataclass(frozen=True, kw_only=True)
class MessagePinned(DomainEvent):
    session_id: UUID
    message_id: UUID


# === Streaming Events (S12) ===


@dataclass(frozen=True, kw_only=True)
class StreamingStarted(DomainEvent):
    session_id: UUID
    message_id: UUID


@dataclass(frozen=True, kw_only=True)
class StreamingToken(DomainEvent):
    session_id: UUID
    message_id: UUID
    token: str
    seq: int


@dataclass(frozen=True, kw_only=True)
class StreamingCompleted(DomainEvent):
    session_id: UUID
    message_id: UUID


@dataclass(frozen=True, kw_only=True)
class StreamingFailed(DomainEvent):
    session_id: UUID
    message_id: UUID
    error: str


# === Task Events ===


@dataclass(frozen=True, kw_only=True)
class TaskCreated(DomainEvent):
    task_id: UUID
    parent_task_id: UUID | None
    title: str
    priority: str
    assignee: UUID | None


@dataclass(frozen=True, kw_only=True)
class TaskStateChanged(DomainEvent):
    task_id: UUID
    from_state: str
    to_state: str
    actor: str


# === Approval Events ===


@dataclass(frozen=True, kw_only=True)
class ApprovalRequested(DomainEvent):
    task_id: UUID
    agent_id: UUID
    action: str
    reason: str
    checkpoint: dict


@dataclass(frozen=True, kw_only=True)
class ApprovalResolved(DomainEvent):
    task_id: UUID
    decision: str
    by_user: UUID


# === Inbox Events ===


@dataclass(frozen=True, kw_only=True)
class NotificationCreated(DomainEvent):
    notification_id: UUID
    user_id: UUID
    category: str
    title: str
