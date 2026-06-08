"""协作者 fake（test-plan §0 可测接缝）。隔离 LLM/CLI，确定性。"""

from __future__ import annotations

from app.domain.task_engine.dag import TaskDef, TaskNode
from app.domain.task_engine.ports import Verdict, WorkerOutcome


class FakePlanner:
    def __init__(self, task_defs: list[TaskDef]) -> None:
        self._tasks = task_defs

    async def plan(self, ctx) -> list[TaskDef]:
        return self._tasks


class FakeExecutor:
    """outcomes: {task_id: WorkerOutcome}；缺省 ok。记录 dispatched 顺序。"""

    def __init__(self, outcomes: dict[str, WorkerOutcome] | None = None) -> None:
        self.outcomes = outcomes or {}
        self.dispatched: list[str] = []

    async def run(self, node: TaskNode) -> WorkerOutcome:
        self.dispatched.append(node.task.id)
        return self.outcomes.get(node.task.id, WorkerOutcome(ok=True, output="ok"))

    async def abort(self, node_id: str) -> bool:
        return False  # 默认无在飞执行

    async def summarize(self, node: TaskNode) -> str:
        return ""  # 默认无复盘


class FakeVerifier:
    """verdicts: {task_id: Verdict | list[Verdict]}。list 按 node.retries 取（支持失败后重试）。"""

    def __init__(self, verdicts: dict[str, object] | None = None) -> None:
        self.verdicts = verdicts or {}

    async def verify(self, node: TaskNode) -> Verdict:
        v = self.verdicts.get(node.task.id, Verdict(True))
        if isinstance(v, list):
            return v[min(node.retries, len(v) - 1)]
        return v
