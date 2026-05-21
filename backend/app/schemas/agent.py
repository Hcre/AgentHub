"""Agent 相关 Schema。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import Provider


class AgentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    avatar: str = Field(max_length=512)
    role: str = Field(max_length=256)
    provider: Provider
    model: str = Field(min_length=1, max_length=128)
    api_key: str = Field(min_length=1, repr=False)  # 密码模式，不回显
    skills: list[str] = []
    system_prompt: str | None = None


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    avatar: str | None = None
    role: str | None = None
    provider: Provider | None = None
    model: str | None = None
    api_key: str | None = Field(default=None, repr=False)
    skills: list[str] | None = None
    capability_tags: list[str] | None = None
    settings: dict | None = None
    system_prompt: str | None = None


class AgentOut(BaseModel):
    id: UUID
    name: str
    avatar: str
    role: str
    provider: str
    model: str
    status: str
    skills: list[str]
    capability_tags: list[str]
    is_system: bool
    created_at: datetime
