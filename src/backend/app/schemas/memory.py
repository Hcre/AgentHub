"""Memory Pydantic 请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MemoryCreate(BaseModel):
    name: str = Field(max_length=150)
    description: str = Field(max_length=300)
    memory_type: Literal["facts", "preferences", "procedures", "context"]
    content: str
    scope: Literal["agent", "group"] = "agent"
    group_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    content: str | None = None
    memory_type: Literal["facts", "preferences", "procedures", "context"] | None = None
    pinned: bool | None = None
    metadata: dict | None = None


class MemoryOut(BaseModel):
    id: UUID
    agent_id: UUID
    group_id: UUID | None
    user_id: UUID
    scope: str
    name: str
    description: str
    memory_type: str
    content: str
    source: str
    pinned: bool
    hits: int
    metadata: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemoryStatsOut(BaseModel):
    total: int
    by_type: dict[str, int]
    oldest: datetime | None
    newest: datetime | None
