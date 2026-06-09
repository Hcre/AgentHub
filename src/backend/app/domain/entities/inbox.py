"""收件箱条目（InboxItem）：审批 / 任务 / 系统通知的统一载体。

审批类条目（type=approval）支持 resolve（批准/驳回）后置 RESOLVED 终态，
与群聊 requiresApproval 流程对接。状态流转走 mark_read / resolve 方法。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.enums import (
    InboxItemStatus,
    InboxResolution,
    NotificationCategory,
)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class InboxItem:
    title: str
    id: UUID = field(default_factory=uuid4)
    type: NotificationCategory = NotificationCategory.SYSTEM
    summary: str = ""
    actor: str | None = None
    actor_name: str | None = None
    when_label: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    status: InboxItemStatus = InboxItemStatus.UNREAD
    resolution: InboxResolution | None = None
    session_id: UUID | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @property
    def unread(self) -> bool:
        return self.status == InboxItemStatus.UNREAD

    def touch(self) -> None:
        self.updated_at = _now()

    def mark_read(self) -> None:
        if self.status == InboxItemStatus.UNREAD:
            self.status = InboxItemStatus.READ
            self.touch()

    def resolve(self, resolution: InboxResolution) -> None:
        """批准/驳回 → 置 RESOLVED 终态（幂等）。"""
        if self.status == InboxItemStatus.RESOLVED:
            return
        self.status = InboxItemStatus.RESOLVED
        self.resolution = resolution
        self.touch()
