"""TaskService（L3）：任务看板持久化 CRUD 用例编排。

本期口径：持久化 CRUD（创建 / 列表 / 筛选 / 改状态 / 删除）。
完整 FSM/DAG 派发编排走 task_engine（M3+，本服务不触发真实派发）。
"""

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import NotFoundError
from app.domain.entities.task import Task
from app.domain.enums import TaskPriority, TaskStatus
from app.domain.repositories.task_repository import TaskFilter, TaskRepository


class TaskService:
    def __init__(self, repo: TaskRepository) -> None:
        self._repo = repo

    async def create(
        self,
        *,
        title: str,
        description: str = "",
        status: TaskStatus = TaskStatus.PENDING,
        priority: TaskPriority = TaskPriority.MEDIUM,
        assignee: str | None = None,
        due_label: str | None = None,
        session_id: UUID | None = None,
    ) -> Task:
        task = Task(
            title=title,
            description=description,
            status=status,
            priority=priority,
            assignee_label=assignee,
            due_label=due_label,
            session_id=session_id,
        )
        await self._repo.save(task)
        return task

    async def get(self, task_id: UUID) -> Task:
        task = await self._repo.get_by_id(task_id)
        if task is None:
            raise NotFoundError(f"任务 {task_id} 不存在")
        return task

    async def list(
        self,
        *,
        status: list[str] | None = None,
        priority: list[str] | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> list[Task]:
        flt = TaskFilter(
            status=status,
            priority=priority,
            page=page,
            page_size=page_size,
        )
        return await self._repo.filter(flt)

    async def update(
        self,
        task_id: UUID,
        *,
        title: str | None = None,
        description: str | None = None,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee: str | None = None,
        due_label: str | None = None,
        assignee_set: bool = False,
        due_set: bool = False,
    ) -> Task:
        task = await self.get(task_id)
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if status is not None:
            task.status = status
        if priority is not None:
            task.priority = priority
        if assignee_set:
            task.assignee_label = assignee
        if due_set:
            task.due_label = due_label
        task.touch()
        await self._repo.save(task)
        return task

    async def delete(self, task_id: UUID) -> None:
        deleted = await self._repo.delete(task_id)
        if not deleted:
            raise NotFoundError(f"任务 {task_id} 不存在")
