"""Response DTO：L3 返回给 L4 的数据传输对象（与领域实体解耦）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.agent import Agent
from app.domain.entities.message import Message
from app.domain.entities.session import Session


@dataclass
class AgentResponse:
    id: UUID
    name: str
    avatar: str
    role: str
    agent_system: str
    status: str
    skills: list[str]
    capability_tags: list[str]
    is_system: bool
    created_at: datetime
    settings: dict
    template_name: str | None = None
    created_from_template_id: UUID | None = None

    @classmethod
    def from_domain(cls, a: Agent) -> AgentResponse:
        return cls(
            id=a.id,
            name=a.name,
            avatar=a.avatar,
            role=a.role,
            agent_system=str(a.agent_system),
            status=str(a.status),
            skills=a.skills,
            capability_tags=a.capability_tags,
            is_system=a.is_system,
            created_at=a.created_at,
            settings=a.settings,
            template_name=a.template_name,
            created_from_template_id=a.created_from_template_id,
        )


@dataclass
class SessionResponse:
    id: UUID
    type: str
    title: str
    group_id: UUID | None
    agent_id: UUID | None
    workspace_path: str
    pinned: bool
    archived: bool = False  # M1#2
    created_at: datetime
    updated_at: datetime | None = None  # M1#1 前端排序用

    @classmethod
    def from_domain(cls, s: Session) -> SessionResponse:
        return cls(
            id=s.id,
            type=str(s.type),
            title=s.title,
            group_id=s.group_id,
            agent_id=s.agent_id,
            workspace_path=s.workspace_path or "",
            pinned=s.pinned,
            archived=s.archived,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )


@dataclass
class MessageResponse:
    id: UUID
    session_id: UUID
    role: str
    content: str
    content_type: str
    sender_agent_id: UUID | None
    mentions: list[str]
    reply_to: UUID | None
    pinned: bool
    status: str
    metadata: dict
    created_at: datetime

    @classmethod
    def from_domain(cls, m: Message) -> MessageResponse:
        return cls(
            id=m.id,
            session_id=m.session_id,
            role=str(m.role),
            content=m.content,
            content_type=str(m.content_type),
            sender_agent_id=m.sender_agent_id,
            mentions=m.mentions,
            reply_to=m.reply_to,
            pinned=m.pinned,
            status=str(m.status),
            metadata=m.metadata,
            created_at=m.created_at,
        )


@dataclass
class GroupCoordinatorResponse:
    id: UUID
    name: str
    role: str
    agent_system: str
    is_system: bool


@dataclass
class GroupMemberResponse:
    id: UUID
    name: str
    role: str


@dataclass
class GroupResponse:
    id: UUID
    name: str
    description: str
    coordinator: GroupCoordinatorResponse
    members: list[GroupMemberResponse]
    created_at: datetime
