"""Task FSM 单测（v4 R1：删 PAUSED/QUEUED/AWAITING_APPROVAL）。

v4 状态语义（coordinator-v4-R1 §2.4）：
    PENDING ──→ RUNNING ──→ VERIFYING ──→ COMPLETED(=VERIFIED)
                       ↘ FAILED          ↘ FAILED
    PENDING ──→ BLOCKED（上游 FAILED 不可达）──→ PENDING（上游修复后复活）
    FAILED ──→ PENDING（retry）

关键不变量：
- RUNNING 不能直达 COMPLETED——必须过 VERIFYING（强制验证闸门）。
- BLOCKED 不是 FAILED——上游修复后可回 PENDING。
- PENDING 直达 RUNNING（v4 删 QUEUED 中间态）。
"""

import pytest

from app.core.exceptions import InvalidTransitionError
from app.domain.enums import TaskStatus
from app.domain.task_engine.fsm import TaskFSM

# --- TC-3.1 合法转移放行 ---

LEGAL = [
    (TaskStatus.PENDING, TaskStatus.RUNNING),  # v4: 直达，无 QUEUED
    (TaskStatus.PENDING, TaskStatus.BLOCKED),
    (TaskStatus.RUNNING, TaskStatus.VERIFYING),
    (TaskStatus.RUNNING, TaskStatus.FAILED),
    (TaskStatus.VERIFYING, TaskStatus.COMPLETED),
    (TaskStatus.VERIFYING, TaskStatus.FAILED),
    (TaskStatus.FAILED, TaskStatus.PENDING),  # retry → 回 frontier
    (TaskStatus.BLOCKED, TaskStatus.PENDING),  # 上游修复复活
]


@pytest.mark.parametrize("from_state,to_state", LEGAL)
def test_legal_transitions(from_state: TaskStatus, to_state: TaskStatus) -> None:
    assert TaskFSM.can_transition(from_state, to_state)


# --- TC-3.2 非法转移拒绝 ---

ILLEGAL = [
    (TaskStatus.PENDING, TaskStatus.COMPLETED),  # 不能跳过执行
    (TaskStatus.RUNNING, TaskStatus.COMPLETED),  # 必须经 VERIFYING（验证闸门）
    (TaskStatus.COMPLETED, TaskStatus.RUNNING),  # 终态
    (TaskStatus.BLOCKED, TaskStatus.RUNNING),  # 复活只能回 PENDING
]


@pytest.mark.parametrize("from_state,to_state", ILLEGAL)
def test_illegal_transitions(from_state: TaskStatus, to_state: TaskStatus) -> None:
    assert not TaskFSM.can_transition(from_state, to_state)


def test_assert_transition_raises() -> None:
    with pytest.raises(InvalidTransitionError):
        TaskFSM.assert_transition(TaskStatus.RUNNING, TaskStatus.COMPLETED)


# --- TC-3.4 终态 ---


def test_terminal_states() -> None:
    assert TaskFSM.is_terminal(TaskStatus.COMPLETED)
    assert TaskFSM.is_terminal(TaskStatus.CANCELLED)
    assert not TaskFSM.is_terminal(TaskStatus.VERIFYING)
    assert not TaskFSM.is_terminal(TaskStatus.BLOCKED)


# --- TC-3.3 retry 上限 ---


def test_retry_limit() -> None:
    assert TaskFSM.can_retry(0)
    assert TaskFSM.can_retry(2)
    assert not TaskFSM.can_retry(3)
