"""Session 聚合根：群聊或私聊会话。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.exceptions import DomainError
from app.domain.enums import SessionType


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Session:
    type: SessionType
    title: str = ""
    id: UUID = field(default_factory=uuid4)
    group_id: UUID | None = None  # 群聊时必填
    agent_id: UUID | None = None  # 私聊时必填
    workspace_path: str = ""  # Agent 工作目录（宿主机绝对路径）
    pinned: bool = False  # t7 B-4-P2-CL01：会话置顶
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if self.type == SessionType.GROUP and self.group_id is None:
            raise DomainError("群聊会话必须指定 group_id")
        if self.type == SessionType.PRIVATE and self.agent_id is None:
            raise DomainError("私聊会话必须指定 agent_id")
