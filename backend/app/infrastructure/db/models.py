"""ORM 模型（PRD §5.2 最简 MVP 表）。

使用 SQLAlchemy 2.0 Mapped 风格与可移植类型（Uuid/JSON），
便于在 PostgreSQL（生产）与 SQLite（测试）间共用。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class AgentModel(Base):
    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(128), index=True)
    avatar: Mapped[str] = mapped_column(String(512), default="")
    role: Mapped[str] = mapped_column(String(256), default="")
    agent_system: Mapped[str] = mapped_column(String(32), default="mock")
    provider: Mapped[str] = mapped_column(String(32), default="anthropic")
    model: Mapped[str] = mapped_column(String(128), default="")
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="")
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="offline")
    workload: Mapped[int] = mapped_column(Integer, default=0)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    capability_tags: Mapped[list] = mapped_column(JSON, default=list)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    type: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    group_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    agent_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    content_type: Mapped[str] = mapped_column(String(32), default="text")
    sender_agent_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    mentions: Mapped[list] = mapped_column(JSON, default=list)
    reply_to: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="completed")
    extra: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class TaskModel(Base):
    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    assignee_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    assignee_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    parent_task_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    session_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class TaskEventModel(Base):
    """事件溯源：任务状态变更只追加，不更新。"""

    __tablename__ = "task_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    event_type: Mapped[str] = mapped_column(String(48))
    event_data: Mapped[dict] = mapped_column(JSON, default=dict)
    actor: Mapped[str] = mapped_column(String(64), default="system")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class NotificationModel(Base):
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    category: Mapped[str] = mapped_column(String(24), index=True)
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text, default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    action_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class GroupModel(Base):
    __tablename__ = "groups"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    coordinator_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    coordinator_config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class GroupMemberModel(Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "agent_id", name="uq_group_member"),)

    # BigSerial（PG）；SQLite 测试退回 Integer 以支持自增主键
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    group_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
