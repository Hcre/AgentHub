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
    func,
    text,
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
    created_from_template_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    template_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
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
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
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
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid, nullable=True, index=True
    )  # P0-4 alembic 0012
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    content_type: Mapped[str] = mapped_column(String(32), default="text")
    sender_agent_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    mentions: Mapped[list] = mapped_column(JSON, default=list)
    reply_to: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    pinned_by_user_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)  # P0-4 alembic 0012
    pinned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # P0-4 alembic 0012
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
    # 展示层自由文本（看板 CRUD）：assignee_label 容纳任意 Agent id/标签，
    # due_label 为自由截止文本（"Today"/"Wed"/"05-30"），与 assignee_id/due_date 解耦。
    assignee_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
    scope: Mapped[str] = mapped_column(String(10))  # agent | group
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(String(300))
    memory_type: Mapped[str] = mapped_column(String(20))  # facts|preferences|procedures|context
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

    P2：唯一性改为 status='active' 的**部分唯一**——同 (agent, installation) 至多 1 条
    active，但解绑（removed）后可再次绑定（解决 F1 rebind 冲突，见 alembic 0010）。
    """

    __tablename__ = "agent_mcp_bindings"
    __table_args__ = (
        Index(
            "uq_agent_mcp_bindings_active",
            "agent_id",
            "installation_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
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


# --- 部署卡（P2 §4.2.4 + BDD B-5-P2-DP01，alembic 0013）---


class DeploymentModel(Base):
    """部署卡（deployments）。每行 = 一次部署（queued/building/ready/failed/deleted）。"""

    __tablename__ = "deployments"
    __table_args__ = (
        Index("ix_deployments_session_id", "session_id"),
        Index("idx_deployments_session_status", "session_id", "status"),
        Index("idx_deployments_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(Uuid)  # R1 裸 Uuid 无 FK
    owner_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)  # R2 JWT sub
    target: Mapped[str] = mapped_column(String(32))
    entry_file: Mapped[str | None] = mapped_column(String(256), nullable=True)
    framework: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    progress: Mapped[float] = mapped_column(default=0.0)
    preview_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    download_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    build_logs: Mapped[list] = mapped_column(JSON, default=list)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ttl: Mapped[int] = mapped_column(Integer, default=3600)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


# --- 收件箱（M4 审批流，alembic 0020）---


class InboxItemModel(Base):
    """收件箱条目（inbox_items）。审批 / 任务 / 系统通知统一表。"""

    __tablename__ = "inbox_items"
    __table_args__ = (
        Index("ix_inbox_items_status", "status"),
        Index("ix_inbox_items_type", "type"),
        Index("idx_inbox_items_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    type: Mapped[str] = mapped_column(String(16), default="system")
    title: Mapped[str] = mapped_column(String(256))
    summary: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    when_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="unread")
    resolution: Mapped[str | None] = mapped_column(String(16), nullable=True)
    session_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


# --- Token 消耗监控（P1-2，alembic 0012）---


class UsageRecordModel(Base):
    """Token 消耗日志（usage_records，append-only）。"""

    __tablename__ = "usage_records"
    __table_args__ = (
        Index("ix_usage_records_agent_id", "agent_id"),
        Index("ix_usage_records_session_id", "session_id"),
        Index("ix_usage_records_created_at", "created_at"),
        Index("idx_usage_records_agent_created", "agent_id", "created_at"),
        Index("idx_usage_records_session_created", "session_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    agent_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    session_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    message_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# --- Agent 模板系统 ---


class TemplateModel(Base):
    """Agent 模板（从 wshobson/skills 等源仓库同步）。"""

    __tablename__ = "templates"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(16), default="wshobson")
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    model_tier: Mapped[str] = mapped_column(String(16), default="inherit")
    tools: Mapped[list] = mapped_column(JSON, default=list)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    display_name_zh: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_skills: Mapped[list] = mapped_column(JSON, default=list)
    compatible_agent_systems: Mapped[list] = mapped_column(JSON, default=list)
    compatible_providers: Mapped[list] = mapped_column(JSON, default=list)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    favorite_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    favorite_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    favorite_order: Mapped[int] = mapped_column(Integer, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TemplateSourceModel(Base):
    """模板源注册信息（如 wshobson/skills 仓库）。"""

    __tablename__ = "template_sources"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    branch: Mapped[str] = mapped_column(String(128), default="main")
    description_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    template_count: Mapped[int] = mapped_column(Integer, default=0)
    last_synced: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
