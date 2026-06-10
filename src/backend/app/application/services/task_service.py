"""TaskService（L3）：任务看板持久化 CRUD + 派发编排。

CRUD：创建 / 列表 / 筛选 / 改状态 / 删除。
派发（M3+）：dispatch() 把看板 Task → 编排引擎真跑（CoordinatorRun），
            状态变更 append 到 task_events（AR-05 事件溯源）+ 回写 TaskModel.status。
            真实 run 由注入的 TaskDispatcher 驱动（DI；测试用 fake，生产用引擎接线）。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.task import Task
from app.domain.entities.task_event import TaskEvent
from app.domain.enums import TaskPriority, TaskStatus
from app.domain.repositories.task_event_repository import TaskEventRepository
from app.domain.repositories.task_repository import TaskFilter, TaskRepository

# 派发期回调：把引擎事件落 task_events / 把节点状态回写看板 Task。
RecordEvent = Callable[[str, dict], Awaitable[None]]
SetStatus = Callable[[TaskStatus, str | None], Awaitable[None]]

# 派发完成的终态（dispatch 不再接受派发）。
_ACTIVE = {TaskStatus.RUNNING}


class TaskDispatcher(Protocol):
    """驱动一个看板 Task 的真实编排 run。实现负责调 record_event/set_status 上报进度。"""

    async def run(self, task: Task, *, record_event: RecordEvent, set_status: SetStatus) -> None:
        ...


class TaskService:
    def __init__(
        self,
        repo: TaskRepository,
        *,
        event_repo: TaskEventRepository | None = None,
        dispatcher: TaskDispatcher | None = None,
    ) -> None:
        self._repo = repo
        self._event_repo = event_repo
        self._dispatcher = dispatcher

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

    async def dispatch(self, task_id: UUID) -> Task:
        """把看板 Task 派给编排引擎真跑（M3+）。

        - 需配置 dispatcher（否则 ValidationError，避免静默 no-op）。
        - 已在运行中 → ValidationError（防重复派发）。
        - 流程：置 RUNNING + append `dispatched` → dispatcher.run（期间 record_event /
          set_status 落 task_events + 回写状态）→ run 结束的终态由 dispatcher 通过
          set_status 决定（completed / failed）。
        """
        if self._dispatcher is None:
            raise ValidationError("E_TASK_DISPATCH_UNAVAILABLE: 未配置派发引擎")
        task = await self.get(task_id)
        if task.status in _ACTIVE:
            raise ValidationError(f"E_TASK_ALREADY_RUNNING: 任务 {task_id} 正在执行")

        await self._append(task_id, "dispatched", {"title": task.title})
        await self._set_status(task, TaskStatus.RUNNING, None)

        async def record_event(event_type: str, data: dict) -> None:
            await self._append(task_id, event_type, data)

        async def set_status(status: TaskStatus, reason: str | None) -> None:
            await self._set_status(task, status, reason)

        await self._dispatcher.run(task, record_event=record_event, set_status=set_status)
        return task

    async def events(self, task_id: UUID) -> list[TaskEvent]:
        """某 task 的事件流（审计/重放）。无 event_repo → 空。"""
        if self._event_repo is None:
            return []
        await self.get(task_id)  # 404 校验
        return await self._event_repo.list_for_task(task_id)

    async def _set_status(self, task: Task, status: TaskStatus, reason: str | None) -> None:
        prev = task.status
        task.status = status
        task.touch()
        await self._repo.save(task)
        await self._append(
            task.id, "transition", {"from": prev.value, "to": status.value, "reason": reason}
        )

    async def _append(self, task_id: UUID, event_type: str, data: dict) -> None:
        if self._event_repo is None:
            return
        await self._event_repo.append(
            TaskEvent(task_id=task_id, event_type=event_type, event_data=data)
        )
