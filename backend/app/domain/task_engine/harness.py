"""Harness：纯代码编排（不含 LLM 调用）。

职责：校验协调者决策、检测循环依赖、路由 Worker、编译 DAG、预算管控。
MVP 阶段为骨架，DAG 编译/Celery Canvas 在 M3 落地。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class PlannedTask:
    """协调者产出的单个子任务。"""

    title: str
    description: str
    suggested_worker: str               # 建议的 Agent name
    depends_on: list[int] = field(default_factory=list)  # 依赖的子任务索引
    assigned_worker: UUID | None = None  # Harness 路由后的实际 Agent id


@dataclass
class TaskPlan:
    """任务分解计划。"""

    tasks: list[PlannedTask]
    rationale: str = ""


class RejectDecisionError(Exception):
    """协调者决策被 Harness 拒绝（如循环依赖）。"""


def detect_cycle(plan: TaskPlan) -> bool:
    """基于 depends_on 索引做拓扑环检测。"""
    n = len(plan.tasks)
    graph = {i: plan.tasks[i].depends_on for i in range(n)}
    visited: dict[int, int] = {}  # 0=未访问 1=在栈 2=完成

    def dfs(node: int) -> bool:
        visited[node] = 1
        for dep in graph.get(node, []):
            if dep < 0 or dep >= n:
                continue
            state = visited.get(dep, 0)
            if state == 1:
                return True
            if state == 0 and dfs(dep):
                return True
        visited[node] = 2
        return False

    return any(visited.get(i, 0) == 0 and dfs(i) for i in range(n))


class Harness:
    """MVP 骨架。M3 接入 Blackboard worker 负载与 Celery Canvas。"""

    def validate(self, plan: TaskPlan) -> TaskPlan:
        if detect_cycle(plan):
            raise RejectDecisionError("检测到循环依赖")
        return plan

    def route_worker(self, suggested: str, available: dict[str, UUID]) -> UUID | None:
        """按建议名称路由到 Agent id；MVP 不做负载均衡。"""
        return available.get(suggested)
