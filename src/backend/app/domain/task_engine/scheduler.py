"""调度纯函数（coordinator-dag-driven-design-v2 §2.2）。

调度 = 给定 DAG 状态算就绪集，纯函数、零 LLM、确定性。
**不改状态**——这些函数只返回决策 id，状态变更由事件循环经 FSM 施加（单写者）。

术语：设计文档的 VERIFIED 在 enum 里是 COMPLETED（依赖满足 = 上游 COMPLETED）。
"""

from __future__ import annotations

from app.domain.enums import TaskStatus
from app.domain.task_engine.dag import TaskGraph

# 上游处于这些状态 → 下游永远等不到，应判 BLOCKED
_UNREACHABLE_STATES: frozenset[TaskStatus] = frozenset(
    {TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.CANCELLED}
)


def compute_frontier(graph: TaskGraph) -> list[str]:
    """就绪集：status==PENDING 且所有依赖已 COMPLETED。按 id 排序（确定性）。"""
    ready = [
        tid
        for tid, node in graph.nodes.items()
        if node.status == TaskStatus.PENDING
        and all(
            graph.nodes[dep].status == TaskStatus.COMPLETED
            for dep in node.task.depends_on
        )
    ]
    return sorted(ready)


def unreachable_pending(graph: TaskGraph) -> list[str]:
    """应判 BLOCKED 的 PENDING 任务：存在不可达上游（FAILED/BLOCKED/CANCELLED）。

    与 frontier 互补——frontier 是"可推进"，本函数是"永远推不动"。
    返回决策，不改状态。
    """
    blocked = [
        tid
        for tid, node in graph.nodes.items()
        if node.status == TaskStatus.PENDING
        and any(
            graph.nodes[dep].status in _UNREACHABLE_STATES
            for dep in node.task.depends_on
        )
    ]
    return sorted(blocked)


def select_dispatchable(
    frontier: list[str], *, running_count: int, max_concurrency: int
) -> list[str]:
    """在并发上限内从就绪集取可派发任务。MVP 串行 = max_concurrency=1。"""
    slots = max_concurrency - running_count
    if slots <= 0:
        return []
    return frontier[:slots]
