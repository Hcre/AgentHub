"""Inbox Pydantic 请求/响应模型（M4 审批流）。"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class InboxItemOut(BaseModel):
    id: UUID
    type: str
    title: str
    summary: str
    actor: str | None = None
    actor_name: str | None = None
    when: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str
    resolution: str | None = None
    unread: bool
    created_at: str
    updated_at: str


class InboxListOut(BaseModel):
    items: list[InboxItemOut]
    unread_count: int


class InboxResolveRequest(BaseModel):
    action: Literal["approve", "reject"]


class InboxItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    type: Literal["approval", "task", "system", "calendar"] = "system"
    summary: str = Field(default="", max_length=4000)
    actor: str | None = Field(default=None, max_length=128)
    actor_name: str | None = Field(default=None, max_length=128)
    when: str | None = Field(default=None, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)
    session_id: UUID | None = None
