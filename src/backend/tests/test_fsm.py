"""Task FSM 单测（架构 S15）。"""

import pytest

from app.core.exceptions import InvalidTransitionError
from app.domain.enums import TaskStatus
from app.domain.task_engine.fsm import TaskFSM


def test_valid_transition() -> None:
    assert TaskFSM.can_transition(TaskStatus.PENDING, TaskStatus.QUEUED)
    assert TaskFSM.can_transition(TaskStatus.RUNNING, TaskStatus.COMPLETED)
    assert TaskFSM.can_transition(TaskStatus.FAILED, TaskStatus.QUEUED)


def test_invalid_transition() -> None:
    assert not TaskFSM.can_transition(TaskStatus.PENDING, TaskStatus.RUNNING)
    assert not TaskFSM.can_transition(TaskStatus.COMPLETED, TaskStatus.RUNNING)
    with pytest.raises(InvalidTransitionError):
        TaskFSM.assert_transition(TaskStatus.COMPLETED, TaskStatus.QUEUED)


def test_terminal_states() -> None:
    assert TaskFSM.is_terminal(TaskStatus.COMPLETED)
    assert TaskFSM.is_terminal(TaskStatus.CANCELLED)
    assert not TaskFSM.is_terminal(TaskStatus.RUNNING)


def test_retry_limit() -> None:
    assert TaskFSM.can_retry(0)
    assert TaskFSM.can_retry(2)
    assert not TaskFSM.can_retry(3)
