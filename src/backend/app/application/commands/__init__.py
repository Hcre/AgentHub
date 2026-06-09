"""Command 对象目录（架构文档 §2.2）。L4 校验后构造，传给 L3 Service。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.enums import DispatchMode

# === Agent Commands ===


@dataclass
class CreateAgentCommand:
    name: str
    avatar: str
    role: str
    agent_system: str = "mock"
    skills: list[str] = field(default_factory=list)
    capability_tags: list[str] = field(default_factory=list)
    system_prompt: str | None = None
    template_name: str | None = None
    template_id: UUID | None = None
    settings: dict | None = None


@dataclass
class UpdateAgentCommand:
    agent_id: UUID
    name: str | None = None
    avatar: str | None = None
    role: str | None = None
    agent_system: str | None = None
    skills: list[str] | None = None
    capability_tags: list[str] | None = None
    system_prompt: str | None = None
    settings: dict | None = None


@dataclass
class DeleteAgentCommand:
    agent_id: UUID


# === Group Commands ===


@dataclass
class CreateGroupCommand:
    name: str
    description: str = ""
    member_ids: list[UUID] = field(default_factory=list)
    workspace_path: str = ""


@dataclass
class RenameGroupCommand:
    group_id: UUID
    name: str


@dataclass
class DeleteGroupCommand:
    group_id: UUID


# === Memory Commands ===


@dataclass
class CreateMemoryCommand:
    name: str
    description: str
    memory_type: str  # facts | preferences | procedures | context
    content: str
    source: str = "manual"  # manual | chat | system
    group_id: UUID | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class UpdateMemoryCommand:
    content: str | None = None
    memory_type: str | None = None
    pinned: bool | None = None
    metadata: dict | None = None


# === Session / Chat Commands ===


@dataclass
class CreateSessionCommand:
    type: str  # "group" | "private"
    group_id: UUID | None = None
    agent_id: UUID | None = None
    title: str = ""
    workspace_path: str = ""


@dataclass
class SendMessageCommand:
    session_id: UUID
    content: str
    content_type: str = "text"
    mentions: list[str] = field(default_factory=list)
    reply_to: UUID | None = None
    dispatch_mode: DispatchMode = DispatchMode.AUTO


@dataclass
class PinMessageCommand:
    session_id: UUID
    message_id: UUID


@dataclass
class UnpinMessageCommand:
    session_id: UUID
    message_id: UUID


@dataclass
class UpdateSessionCommand:
    session_id: UUID
    title: str | None = None
    workspace_path: str | None = None
    pinned: bool | None = None  # t7 B-4-P2-CL01：会话置顶开关


# === Task Commands ===


@dataclass
class CreateTaskCommand:
    title: str
    description: str = ""
    assignee_id: UUID | None = None
    assignee_type: str | None = None
    due_date: datetime | None = None
    priority: str = "medium"
    tags: list[str] = field(default_factory=list)
    parent_task_id: UUID | None = None


@dataclass
class UpdateTaskCommand:
    task_id: UUID
    status: str | None = None
    priority: str | None = None
    assignee_id: UUID | None = None
    due_date: datetime | None = None
    tags: list[str] | None = None
