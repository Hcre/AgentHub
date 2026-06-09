"""InboxService（L3）：收件箱审批流用例编排。

支持：列表（按 type 过滤）/ 未读计数 / 标记已读 / resolve（批准|驳回）。
审批类条目 resolve 后置 RESOLVED 终态，默认列表不再返回（与群聊
requiresApproval 流程对接）。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.domain.entities.inbox import InboxItem
from app.domain.enums import InboxResolution, NotificationCategory
from app.domain.repositories.inbox_repository import InboxRepository


class InboxService:
    def __init__(self, repo: InboxRepository) -> None:
        self._repo = repo

    async def create(
        self,
        *,
        title: str,
        type_: NotificationCategory = NotificationCategory.SYSTEM,
        summary: str = "",
        actor: str | None = None,
        actor_name: str | None = None,
        when_label: str | None = None,
        payload: dict[str, Any] | None = None,
        session_id: UUID | None = None,
    ) -> InboxItem:
        item = InboxItem(
            title=title,
            type=type_,
            summary=summary,
            actor=actor,
            actor_name=actor_name,
            when_label=when_label,
            payload=payload or {},
            session_id=session_id,
        )
        await self._repo.save(item)
        return item

    async def list(
        self, *, type_: str | None = None, include_resolved: bool = False
    ) -> list[InboxItem]:
        return await self._repo.list_items(
            type_=type_, include_resolved=include_resolved
        )

    async def unread_count(self) -> int:
        return await self._repo.unread_count()

    async def get(self, item_id: UUID) -> InboxItem:
        item = await self._repo.get_by_id(item_id)
        if item is None:
            raise NotFoundError(f"收件箱条目 {item_id} 不存在")
        return item

    async def mark_read(self, item_id: UUID) -> InboxItem:
        item = await self.get(item_id)
        item.mark_read()
        await self._repo.save(item)
        return item

    async def resolve(self, item_id: UUID, resolution: InboxResolution) -> InboxItem:
        item = await self.get(item_id)
        item.resolve(resolution)
        await self._repo.save(item)
        return item
