"""Group 相关 Schema。名称格式非法 → 422（Pydantic pattern）；成员超 20 → 422。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# 名称规则：首字符为字母或中文，后可跟字母/中文/数字/连字符/下划线，2-32 字符
NAME_PATTERN = r"^[一-鿿a-zA-Z][一-鿿a-zA-Z0-9_-]{1,31}$"


class GroupCreateRequest(BaseModel):
    name: str = Field(pattern=NAME_PATTERN)
    description: str = Field(default="", max_length=2000)
    member_ids: list[UUID] = Field(default_factory=list, max_length=20)
    workdir: str = Field(default="", max_length=1000, alias="workdir")


class GroupCoordinatorOut(BaseModel):
    id: UUID
    name: str
    role: str
    agent_system: str
    is_system: bool


class GroupMemberOut(BaseModel):
    id: UUID
    name: str
    role: str


class GroupRenameRequest(BaseModel):
    name: str = Field(pattern=NAME_PATTERN)


class GroupOut(BaseModel):
    id: UUID
    name: str
    description: str
    coordinator: GroupCoordinatorOut
    members: list[GroupMemberOut]
    created_at: datetime
    # 快速方案：复用 backing Session.pinned（避免给 Group 实体加列 + alembic 0024）
    pinned: bool = False
    session_id: UUID | None = None


class NameCheckOut(BaseModel):
    available: bool
    reason: str | None = None
