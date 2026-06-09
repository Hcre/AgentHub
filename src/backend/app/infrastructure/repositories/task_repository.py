"""PostgresTaskRepository：TaskRepository 的 SQLAlchemy 实现。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.task import Task
from app.domain.enums import TaskPriority, TaskSource, TaskStatus
from app.domain.repositories.task_repository import TaskFilter, TaskRepository
from app.infrastructure.db.models import TaskModel


def _to_domain(m: TaskModel) -> Task:
    return Task(
        id=m.id,
        title=m.title,
        description=m.description or "",
        status=TaskStatus(m.status),
        priority=TaskPriority(m.priority),
        assignee_id=m.assignee_id,
        assignee_label=m.assignee_label,
        due_label=m.due_label,
        source=TaskSource(m.source),
        session_id=m.session_id,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _apply(m: TaskModel, t: Task) -> None:
    m.title = t.title
    m.description = t.description
    m.status = t.status.value
    m.priority = t.priority.value
    m.assignee_label = t.assignee_label
    m.assignee_id = t.assignee_id
    m.due_label = t.due_label
    m.source = t.source.value
    m.session_id = t.session_id
    m.updated_at = t.updated_at


class PostgresTaskRepository(TaskRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, task: Task) -> None:
        existing = await self._s.get(TaskModel, task.id)
        if existing is None:
            m = TaskModel(id=task.id, created_at=task.created_at)
            _apply(m, task)
            self._s.add(m)
        else:
            _apply(existing, task)
        await self._s.flush()

    async def get_by_id(self, task_id: UUID) -> Task | None:
        m = await self._s.get(TaskModel, task_id)
        return _to_domain(m) if m is not None else None

    async def filter(self, flt: TaskFilter) -> list[Task]:
        stmt = select(TaskModel)
        if flt.status:
            stmt = stmt.where(TaskModel.status.in_(flt.status))
        if flt.priority:
            stmt = stmt.where(TaskModel.priority.in_(flt.priority))
        if flt.assignee_id is not None:
            stmt = stmt.where(TaskModel.assignee_id == flt.assignee_id)
        if flt.parent_task_id is not None:
            # parent 不持久化于本期 CRUD 表；恒空集合
            return []

        col = getattr(TaskModel, flt.sort_by, TaskModel.created_at)
        stmt = stmt.order_by(col.desc() if flt.sort_order == "desc" else col.asc())
        stmt = stmt.offset((flt.page - 1) * flt.page_size).limit(flt.page_size)

        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def list_subtasks(self, parent_task_id: UUID) -> list[Task]:
        # 本期 CRUD 看板不建父子层级；编排引擎落地时再扩展。
        return []

    async def delete(self, task_id: UUID) -> bool:
        result = await self._s.execute(
            sa_delete(TaskModel).where(TaskModel.id == task_id)
        )
        await self._s.flush()
        return (result.rowcount or 0) > 0
