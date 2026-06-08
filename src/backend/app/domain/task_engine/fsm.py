"""任务状态机（DAG 驱动 v2，coordinator-dag-driven-design-v2 §2.3）。

事件溯源：状态变更只能通过 transition()，产出 TaskStateChanged 事件，
不直接 set Task.status；持久化由调用方负责。

v2 关键不变量：
- RUNNING 不能直达 COMPLETED——必须过 VERIFYING（FSM 层强制验证闸门）。
- VERIFYING 验收通过 → COMPLETED（= 已验证）；失败 → FAILED。
- BLOCKED 不是 FAILED——上游 FAILED 时下游 PENDING→BLOCKED，上游修复后 BLOCKED→PENDING。
- COMPLETED 即设计文档里的 VERIFIED 终态（复用现有 enum，不另立）。

v4 变更（R1）：删 PAUSED/QUEUED/AWAITING_APPROVAL 三态（详见 coordinator-v4-R1 §8）。
- PENDING 直达 RUNNING（无 QUEUED 中间态）。
- not_done（worker 没交卷）不转移——节点停在 RUNNING 等 feed，不需要 PAUSED。
"""

from __future__ import annotations

from app.core.exceptions import InvalidTransitionError
from app.domain.enums import TaskStatus

# 合法转换表（v4）
VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {
        TaskStatus.VERIFYING,  # 必经验证闸门，不直达 COMPLETED
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.VERIFYING: {
        TaskStatus.COMPLETED,  # 验收通过 = VERIFIED
        TaskStatus.FAILED,  # 验收不通过 → 回灌重试/replan
        TaskStatus.CANCELLED,
    },
    TaskStatus.FAILED: {TaskStatus.PENDING, TaskStatus.CANCELLED},  # retry → PENDING（frontier 重捡）；CANCELLED 保留
    TaskStatus.BLOCKED: {TaskStatus.PENDING, TaskStatus.CANCELLED},  # 上游修复 → 复活
    TaskStatus.COMPLETED: set(),  # 终态（= VERIFIED）
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
            raise InvalidTransitionError(f"非法状态转换：{from_state} → {to_state}")

    @staticmethod
    def is_terminal(state: TaskStatus) -> bool:
        return state in TERMINAL_STATES

    @staticmethod
    def can_retry(retry_count: int) -> bool:
        return retry_count < MAX_RETRY
