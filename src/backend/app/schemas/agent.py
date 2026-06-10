"""Agent 相关 Schema。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import AgentSystem


class AgentCreateRequest(BaseModel):
    model_config = {"populate_by_name": True}

    name: str = Field(min_length=1, max_length=128)
    avatar: str = Field(max_length=512)
    role: str = Field(max_length=256)
    agent_system: AgentSystem = AgentSystem.MOCK
    skills: list[str] = []
    capability_tags: list[str] = []
    system_prompt: str | None = None
    template_name: str | None = None
    created_from_template_id: UUID | None = Field(default=None, alias="template_id")
    settings: dict | None = None


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    avatar: str | None = None
    role: str | None = None
    agent_system: AgentSystem | None = None
    skills: list[str] | None = None
    capability_tags: list[str] | None = None
    settings: dict | None = None
    system_prompt: str | None = None


class AgentOut(BaseModel):
    id: UUID
    name: str
    avatar: str
    role: str
    agent_system: str
    status: str
    skills: list[str]
    capability_tags: list[str]
    system_prompt: str | None = None
    is_system: bool
    settings: dict | None = None
    template_name: str | None = None
    created_from_template_id: UUID | None = None
    created_at: datetime


class AgentDraftRequest(BaseModel):
    """对话式创建：自然语言描述 → 抽取草稿。"""

    description: str = Field(min_length=1, max_length=2000)


class AgentDraftOut(BaseModel):
    name: str
    role: str
    avatar: str
    system_prompt: str
    capability_tags: list[str]
