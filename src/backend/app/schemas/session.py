"""Session / Message 相关 Schema。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import DispatchMode, SessionType


class SessionCreateRequest(BaseModel):
    type: SessionType
    group_id: UUID | None = None
    agent_id: UUID | None = None
    title: str = ""
    workspace_path: str = ""

    @model_validator(mode="after")
    def _check_target(self) -> SessionCreateRequest:
        if self.type == SessionType.GROUP and self.group_id is None:
            raise ValueError("群聊必须提供 group_id")
        if self.type == SessionType.PRIVATE and self.agent_id is None:
            raise ValueError("私聊必须提供 agent_id")
        return self


class SessionOut(BaseModel):
    id: UUID
    type: str
    title: str
    group_id: UUID | None
    agent_id: UUID | None
    workspace_path: str
    pinned: bool = False
    archived: bool = False  # M1#2 会话归档
    created_at: datetime
    updated_at: datetime | None = None  # 前端排序用


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)
    content_type: str = "text"
    mentions: list[str] = []
    reply_to: UUID | None = None
    dispatch_mode: DispatchMode = DispatchMode.AUTO


class MessageOut(BaseModel):
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
