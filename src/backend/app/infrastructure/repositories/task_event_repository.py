"""PostgresTaskEventRepository（L1）：把 TaskEvent 落 task_events（append-only）。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.task_event import TaskEvent
from app.domain.repositories.task_event_repository import TaskEventRepository
from app.infrastructure.db.models import TaskEventModel


class PostgresTaskEventRepository(TaskEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, event: TaskEvent) -> None:
        self._session.add(
            TaskEventModel(
                id=event.id,
                task_id=event.task_id,
                event_type=event.event_type,
                event_data=event.event_data,
                actor=event.actor,
                created_at=event.created_at,
            )
        )
        await self._session.flush()

    async def list_for_task(self, task_id: UUID) -> list[TaskEvent]:
        rows = (
            await self._session.execute(
                select(TaskEventModel)
                .where(TaskEventModel.task_id == task_id)
                .order_by(TaskEventModel.created_at.asc())
            )
        ).scalars().all()
        return [
            TaskEvent(
                id=r.id,
                task_id=r.task_id,
                event_type=r.event_type,
                event_data=r.event_data,
                actor=r.actor,
                created_at=r.created_at,
            )
            for r in rows
        ]
