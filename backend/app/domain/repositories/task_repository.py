"""TaskRepository 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.task import Task


class TaskFilter:
    """任务筛选条件（对应 ListTasksCommand）。"""

    def __init__(
        self,
        *,
        status: list[str] | None = None,
        priority: list[str] | None = None,
        assignee_id: UUID | None = None,
        due_before: datetime | None = None,
        due_after: datetime | None = None,
        tags: list[str] | None = None,
        parent_task_id: UUID | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> None:
        self.status = status
        self.priority = priority
        self.assignee_id = assignee_id
        self.due_before = due_before
        self.due_after = due_after
        self.tags = tags
        self.parent_task_id = parent_task_id
        self.sort_by = sort_by
        self.sort_order = sort_order
        self.page = page
        self.page_size = min(page_size, 100)


class TaskRepository(ABC):
    @abstractmethod
    async def save(self, task: Task) -> None: ...

    @abstractmethod
    async def get_by_id(self, task_id: UUID) -> Task | None: ...

    @abstractmethod
    async def filter(self, flt: TaskFilter) -> list[Task]: ...

    @abstractmethod
    async def list_subtasks(self, parent_task_id: UUID) -> list[Task]: ...
