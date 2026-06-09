"""Task 聚合根：支持父子任务（嵌套深度 ≤ 1）。

状态流转委托给 task_engine.fsm（事件溯源，不直接改状态）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.enums import TaskPriority, TaskSource, TaskStatus


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Task:
    title: str
    id: UUID = field(default_factory=uuid4)
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: UUID | None = None
    assignee_type: str | None = None  # "agent" | "group"
    due_date: datetime | None = None
    tags: list[str] = field(default_factory=list)
    parent_task_id: UUID | None = None
    subtask_ids: list[UUID] = field(default_factory=list)
    source: TaskSource = TaskSource.MANUAL
    session_id: UUID | None = None
    retry_count: int = 0
    assigned_worker: UUID | None = None
    # 展示层字段（看板 CRUD 用）：assignee 可为任意 Agent id / 标签字符串，
    # due 为自由文本（"Today" / "Wed" / "05-30"），与 assignee_id/due_date 解耦，
    # 编排引擎不依赖这两个字段（追加可选，默认空）。
    assignee_label: str | None = None
    due_label: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @property
    def is_root(self) -> bool:
        return self.parent_task_id is None

    def touch(self) -> None:
        self.updated_at = _now()
