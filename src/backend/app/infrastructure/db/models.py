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
    Index,
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
    workspace_path: Mapped[str] = mapped_column(Text, default="")
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


# --- 记忆系统（董）---


class MemoryModel(Base):
    __tablename__ = "memories"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("groups.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    scope: Mapped[str] = mapped_column(String(10))              # agent | group
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(String(300))
    memory_type: Mapped[str] = mapped_column(String(20))        # facts|preferences|procedures|context
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual|chat|system
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    # "metadata" 是 SQLAlchemy 保留属性名，列名保留，属性名用 metadata_
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


# --- MCP 接入（4 表，二次对账口径：R1/R2 裸 Uuid 无 FK，R10 可移植类型）---
# 权威：docs/specs/03-data-model §MCP；MD-MCP-V1.0 §1；README-REVISION §9。


class McpServerModel(Base):
    """MCP 市场元数据（mcp_servers）。args_hash 由 config_json 派生。"""

    __tablename__ = "mcp_servers"
    __table_args__ = (Index("idx_mcp_servers_status_latest", "status", "latest"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    transport: Mapped[str] = mapped_column(String(32))
    config_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    args_hash: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    latest: Mapped[bool] = mapped_column(Boolean, default=True)
    official: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)  # R10: TEXT[]→JSON（无 GIN）
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    created_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)  # R2 裸 Uuid 无 FK
    dry_run_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    dry_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    install_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class WorkspaceMcpInstallationModel(Base):
    """workspace 维度安装（workspace_mcp_installations）。

    R1：workspace_id 暂存 session_id，裸 Uuid 无 FK。安装幂等键
    (workspace_id + mcp_id + args_hash)。
    """

    __tablename__ = "workspace_mcp_installations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "instance_name",
            name="uq_workspace_mcp_installations_workspace_mcp_name",
        ),
        Index("idx_workspace_mcp_installations_workspace", "workspace_id", "status"),
        Index("idx_workspace_mcp_installations_idempotent", "workspace_id", "mcp_id", "args_hash"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid)  # R1 session_id 裸 Uuid 无 FK
    mcp_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("mcp_servers.id", ondelete="CASCADE"), index=True
    )
    installed_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)  # R2 裸 Uuid 无 FK
    instance_name: Mapped[str] = mapped_column(String(128))
    config_overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    args_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="installing")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    last_health_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AgentMcpBindingModel(Base):
    """Agent 绑定（agent_mcp_bindings）。解绑软删（status=removed + unbound_at）。

    NOTE(P2)：唯一约束 (agent_id, installation_id) 与软删并存时，解绑后无法再绑定同一
    installation——P2 实现绑定端点时需改为 status=active 的部分唯一，或解绑改硬删。
    """

    __tablename__ = "agent_mcp_bindings"
    __table_args__ = (
        UniqueConstraint(
            "agent_id", "installation_id", name="uq_agent_mcp_bindings_agent_installation"
        ),
        Index("idx_agent_mcp_bindings_agent", "agent_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("agents.id", ondelete="CASCADE"))
    installation_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspace_mcp_installations.id", ondelete="CASCADE"),
        index=True,
    )
    tool_subset: Mapped[list] = mapped_column(JSON, default=list)  # 空=全选
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    unbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class McpToolCallLogModel(Base):
    """工具调用日志（mcp_tool_call_logs，F-014 + F-017）。

    R1：workspace_id 暂存 session_id 裸 Uuid。R4：trace_id 为净新增（非既有设施）。
    """

    __tablename__ = "mcp_tool_call_logs"
    __table_args__ = (
        Index("idx_mcp_tool_call_logs_workspace_created", "workspace_id", "created_at"),
        Index("idx_mcp_tool_call_logs_agent_created", "agent_id", "created_at"),
        Index("idx_mcp_tool_call_logs_trace", "trace_id"),
    )

    # BigSerial（PG）；SQLite 测试退回 Integer 自增（同 GroupMemberModel）
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    trace_id: Mapped[str] = mapped_column(String(32))  # R4 净新增，P4 生成
    binding_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agent_mcp_bindings.id", ondelete="CASCADE")
    )
    agent_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("agents.id", ondelete="CASCADE"))
    workspace_id: Mapped[UUID] = mapped_column(Uuid)  # R1 session_id 裸 Uuid 无 FK
    mcp_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("mcp_servers.id", ondelete="CASCADE"))
    tool_name: Mapped[str] = mapped_column(String(128))
    args_hash: Mapped[str] = mapped_column(String(64))
    result_code: Mapped[str] = mapped_column(String(32))
    duration_ms: Mapped[int] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
