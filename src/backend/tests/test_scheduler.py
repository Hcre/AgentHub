"""调度纯函数单测（coordinator-test-plan §2）。

调度是 DAG 的纯函数（零 LLM）：给定图状态算就绪集 / 不可达集 / 可派发集。
不改状态——状态变更由事件循环经 FSM 施加（单写者）。
"""

from app.domain.enums import TaskStatus
from app.domain.task_engine.dag import Check, TaskDef, TaskGraph, TaskNode
from app.domain.task_engine.scheduler import (
    compute_frontier,
    select_dispatchable,
    unreachable_pending,
)


def _graph(specs: dict[str, tuple[list[str], TaskStatus]]) -> TaskGraph:
    """specs: id -> (depends_on, status)。"""
    nodes = {}
    for tid, (deps, status) in specs.items():
        task = TaskDef(
            id=tid,
            title=tid,
            suggested_worker="w",
            depends_on=deps,
            acceptance=[Check("mechanical", "true")],
        )
        nodes[tid] = TaskNode(task=task, status=status)
    return TaskGraph(nodes=nodes)


# --- TC-2.1 无依赖全就绪 ---


def test_no_deps_all_ready() -> None:
    g = _graph({
        "t1": ([], TaskStatus.PENDING),
        "t2": ([], TaskStatus.PENDING),
        "t3": ([], TaskStatus.PENDING),
    })
    assert compute_frontier(g) == ["t1", "t2", "t3"]


# --- TC-2.2 依赖未满足则阻塞（不在 frontier）---


def test_unsatisfied_deps_excluded() -> None:
    g = _graph({
        "t1": ([], TaskStatus.PENDING),
        "t2": ([], TaskStatus.PENDING),
        "t3": (["t1", "t2"], TaskStatus.PENDING),
    })
    assert compute_frontier(g) == ["t1", "t2"]


# --- TC-2.3 部分完成解锁下游 ---


def test_partial_completion_unlocks() -> None:
    g = _graph({
        "t1": ([], TaskStatus.COMPLETED),
        "t2": ([], TaskStatus.COMPLETED),
        "t3": (["t1", "t2"], TaskStatus.PENDING),
    })
    assert compute_frontier(g) == ["t3"]


def test_partial_completion_one_dep_pending() -> None:
    g = _graph({
        "t1": ([], TaskStatus.COMPLETED),
        "t2": ([], TaskStatus.RUNNING),
        "t3": (["t1", "t2"], TaskStatus.PENDING),
    })
    assert compute_frontier(g) == []  # t2 未 COMPLETED → t3 不就绪


# --- TC-2.4 串行 MVP：并发=1 只派一个 ---


def test_serial_dispatch_one() -> None:
    frontier = ["t1", "t2"]
    assert select_dispatchable(frontier, running_count=0, max_concurrency=1) == ["t1"]


def test_concurrency_full_dispatch_none() -> None:
    frontier = ["t1", "t2"]
    assert select_dispatchable(frontier, running_count=1, max_concurrency=1) == []


def test_concurrency_partial_slot() -> None:
    frontier = ["t1", "t2", "t3"]
    assert select_dispatchable(frontier, running_count=1, max_concurrency=3) == ["t1", "t2"]


# --- TC-2.5 上游失败 → 下游不可达（BLOCKED 候选，非 FAILED）---


def test_upstream_failed_marks_downstream_unreachable() -> None:
    g = _graph({
        "t1": ([], TaskStatus.FAILED),
        "t3": (["t1"], TaskStatus.PENDING),
    })
    assert unreachable_pending(g) == ["t3"]
    assert compute_frontier(g) == []  # 不可达任务不进 frontier


def test_healthy_upstream_not_unreachable() -> None:
    g = _graph({
        "t1": ([], TaskStatus.RUNNING),
        "t3": (["t1"], TaskStatus.PENDING),
    })
    assert unreachable_pending(g) == []  # t1 还在跑，t3 只是 waiting，不是 blocked


# --- TC-2.6 确定性（property）---


def test_frontier_deterministic_regardless_of_insertion_order() -> None:
    specs = {
        "t3": ([], TaskStatus.PENDING),
        "t1": ([], TaskStatus.PENDING),
        "t2": ([], TaskStatus.PENDING),
    }
    g1 = _graph(specs)
    g2 = _graph(dict(reversed(list(specs.items()))))
    assert compute_frontier(g1) == compute_frontier(g2) == ["t1", "t2", "t3"]
