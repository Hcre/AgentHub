"""TaskEventRepository 抽象接口（append-only 事件溯源）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.task_event import TaskEvent


class TaskEventRepository(ABC):
    @abstractmethod
    async def append(self, event: TaskEvent) -> None:
        """追加一条事件（不可更新/删除）。"""

    @abstractmethod
    async def list_for_task(self, task_id: UUID) -> list[TaskEvent]:
        """按时间升序返回某 task 的全部事件（用于重放/审计）。"""
