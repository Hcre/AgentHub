"""任务状态机（架构文档 S15）。

事件溯源：状态变更只能通过 transition()，产出 TaskStateChanged 事件，
不直接 set Task.status；持久化由调用方负责。
"""

from __future__ import annotations

from app.core.exceptions import InvalidTransitionError
from app.domain.enums import TaskStatus

# 合法转换表（S15）
VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.QUEUED, TaskStatus.CANCELLED},
    TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.AWAITING_APPROVAL,
        TaskStatus.PAUSED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.AWAITING_APPROVAL: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.PAUSED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.FAILED: {TaskStatus.QUEUED, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),  # 终态
    TaskStatus.CANCELLED: set(),  # 终态
}

TERMINAL_STATES: set[TaskStatus] = {TaskStatus.COMPLETED, TaskStatus.CANCELLED}

MAX_RETRY = 3


class TaskFSM:
    """无状态校验器：判断状态转换是否合法。"""

    @staticmethod
    def can_transition(from_state: TaskStatus, to_state: TaskStatus) -> bool:
        return to_state in VALID_TRANSITIONS.get(from_state, set())

    @staticmethod
    def assert_transition(from_state: TaskStatus, to_state: TaskStatus) -> None:
        if not TaskFSM.can_transition(from_state, to_state):
            raise InvalidTransitionError(
                f"非法状态转换：{from_state} → {to_state}"
            )

    @staticmethod
    def is_terminal(state: TaskStatus) -> bool:
        return state in TERMINAL_STATES

    @staticmethod
    def can_retry(retry_count: int) -> bool:
        return retry_count < MAX_RETRY
