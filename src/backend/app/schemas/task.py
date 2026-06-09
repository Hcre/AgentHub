"""Task Pydantic 请求/响应模型（M3 看板持久化 CRUD）。"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import TaskPriority, TaskStatus

# 领域枚举值（status: 7 态；priority: 4 级）。前端 4 列看板词表在前端 api 层映射。
_STATUS = "pending|running|verifying|blocked|completed|failed|cancelled"
_PRIORITY = "critical|high|medium|low"
_VALID_STATUS = {s.value for s in TaskStatus}
_VALID_PRIORITY = {p.value for p in TaskPriority}


def _check_status(v: str | None) -> str | None:
    if v is not None and v not in _VALID_STATUS:
        raise ValueError(f"status 必须是 {_STATUS} 之一")
    return v


def _check_priority(v: str | None) -> str | None:
    if v is not None and v not in _VALID_PRIORITY:
        raise ValueError(f"priority 必须是 {_PRIORITY} 之一")
    return v


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=4000)
    status: str = Field(default="pending", description=_STATUS)
    priority: str = Field(default="medium", description=_PRIORITY)
    assignee: str | None = Field(default=None, max_length=128)
    due: str | None = Field(default=None, max_length=64)
    session_id: UUID | None = None

    _v_status = field_validator("status")(_check_status)
    _v_priority = field_validator("priority")(_check_priority)


class TaskUpdate(BaseModel):
    """PATCH：仅传需改字段。assignee/due 显式传 null 可清空。"""

    title: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default=None, description=_STATUS)
    priority: str | None = Field(default=None, description=_PRIORITY)
    assignee: str | None = Field(default=None, max_length=128)
    due: str | None = Field(default=None, max_length=64)

    model_config = {"extra": "forbid"}

    _v_status = field_validator("status")(_check_status)
    _v_priority = field_validator("priority")(_check_priority)


class TaskOut(BaseModel):
    id: UUID
    title: str
    description: str
    status: str
    priority: str
    assignee: str | None = None
    due: str | None = None
    source: str
    session_id: UUID | None = None
    created_at: str
    updated_at: str


class TaskListOut(BaseModel):
    items: list[TaskOut]
    total: int
