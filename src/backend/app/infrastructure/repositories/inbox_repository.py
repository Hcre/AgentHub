"""PostgresInboxRepository：InboxRepository 的 SQLAlchemy 实现。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.inbox import InboxItem
from app.domain.enums import (
    InboxItemStatus,
    InboxResolution,
    NotificationCategory,
)
from app.domain.repositories.inbox_repository import InboxRepository
from app.infrastructure.db.models import InboxItemModel


def _to_domain(m: InboxItemModel) -> InboxItem:
    return InboxItem(
        id=m.id,
        title=m.title,
        type=NotificationCategory(m.type),
        summary=m.summary or "",
        actor=m.actor,
        actor_name=m.actor_name,
        when_label=m.when_label,
        payload=dict(m.payload or {}),
        status=InboxItemStatus(m.status),
        resolution=InboxResolution(m.resolution) if m.resolution else None,
        session_id=m.session_id,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _apply(m: InboxItemModel, item: InboxItem) -> None:
    m.type = item.type.value
    m.title = item.title
    m.summary = item.summary
    m.actor = item.actor
    m.actor_name = item.actor_name
    m.when_label = item.when_label
    m.payload = dict(item.payload)
    m.status = item.status.value
    m.resolution = item.resolution.value if item.resolution else None
    m.session_id = item.session_id
    m.updated_at = item.updated_at


class PostgresInboxRepository(InboxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, item: InboxItem) -> None:
        existing = await self._s.get(InboxItemModel, item.id)
        if existing is None:
            m = InboxItemModel(id=item.id, created_at=item.created_at)
            _apply(m, item)
            self._s.add(m)
        else:
            _apply(existing, item)
        await self._s.flush()

    async def get_by_id(self, item_id: UUID) -> InboxItem | None:
        m = await self._s.get(InboxItemModel, item_id)
        return _to_domain(m) if m is not None else None

    async def list_items(
        self,
        *,
        type_: str | None = None,
        include_resolved: bool = False,
    ) -> list[InboxItem]:
        stmt = select(InboxItemModel)
        if type_:
            stmt = stmt.where(InboxItemModel.type == type_)
        if not include_resolved:
            stmt = stmt.where(
                InboxItemModel.status != InboxItemStatus.RESOLVED.value
            )
        stmt = stmt.order_by(InboxItemModel.created_at.desc())
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def unread_count(self) -> int:
        stmt = select(func.count()).select_from(InboxItemModel).where(
            InboxItemModel.status == InboxItemStatus.UNREAD.value
        )
        return int((await self._s.execute(stmt)).scalar_one())
