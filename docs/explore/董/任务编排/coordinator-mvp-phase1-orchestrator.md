# Phase 1 详细实现方案 — Orchestrator 串行循环（脊柱）

> 日期：2026-06-05 | 属于：[[coordinator-mvp-implementation-plan]] Phase 0+1
> 粒度：照着就能写。含 Phase 0 必需类型，自包含可直接落代码。
> 脊柱：用 fake 协作者把已建的 dag/scheduler/fsm 串成完整串行循环。达成即 M1（控制面端到端跑通）。

---

## 0. 本相先拍的决策：retry → PENDING

`fsm.py` 改一行 + `test_fsm.py` 改一行：

```python
# fsm.py
TaskStatus.FAILED: {TaskStatus.PENDING, TaskStatus.CANCELLED},  # retry → PENDING（frontier 重捡）
# test_fsm.py LEGAL 列
(TaskStatus.FAILED, TaskStatus.PENDING),   # 原 (FAILED, QUEUED)
```

理由：串行循环靠 `compute_frontier` 捡 PENDING 任务；retry 回 PENDING 最简，无需 dispatcher 额外拉 QUEUED。

---

## 1. 新建 `ports.py`（Phase 0，完整）

```python
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from app.domain.task_engine.dag import TaskDef, TaskNode, TaskGraph


@dataclass(frozen=True)
class Verdict:
    passed: bool
    reason: str = ""


@dataclass(frozen=True)
class WorkerOutcome:
    ok: bool                  # False = worker 自身崩/超时；True = 产出了结果（自称完成）
    output: str = ""


class ExitReason(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"             # 某任务 retry 耗尽
    UNREACHABLE = "unreachable"   # 下游被 BLOCKED 堵死（无 FAILED 时的兜底）
    BUDGET_EXCEEDED = "budget_exceeded"  # 步数上限（防死循环）


@dataclass(frozen=True)
class RunResult:
    reason: ExitReason
    summary: str = ""


@dataclass(frozen=True)
class PlanContext:
    task: str
    workers: tuple[str, ...]      # 可用 worker 名（build_graph 校验用）
    repo_tree: str = ""           # MVP 种子；fake 测试可空


class Planner(Protocol):
    async def plan(self, ctx: PlanContext) -> list[TaskDef]: ...
    async def final_answer(self, graph: TaskGraph) -> str: ...


class Executor(Protocol):
    async def run(self, node: TaskNode) -> WorkerOutcome: ...


class Verifier(Protocol):
    async def verify(self, node: TaskNode) -> Verdict: ...
```

---

## 2. 新建 `tests/fakes.py`（Phase 0）

```python
from app.domain.task_engine.dag import TaskNode
from app.domain.task_engine.ports import Verdict, WorkerOutcome


class FakePlanner:
    def __init__(self, task_defs):
        self._tasks = task_defs
        self.final_called = False

    async def plan(self, ctx):
        return self._tasks

    async def final_answer(self, graph):
        self.final_called = True
        return "done"


class FakeExecutor:
    """outcomes: {task_id: WorkerOutcome}；缺省 ok。记录 dispatched 顺序。"""
    def __init__(self, outcomes=None):
        self.outcomes = outcomes or {}
        self.dispatched: list[str] = []

    async def run(self, node: TaskNode) -> WorkerOutcome:
        self.dispatched.append(node.task.id)
        return self.outcomes.get(node.task.id, WorkerOutcome(ok=True, output="ok"))


class FakeVerifier:
    """verdicts: {task_id: Verdict | list[Verdict]}。list 按 node.retries 取（支持失败后重试）。"""
    def __init__(self, verdicts=None):
        self.verdicts = verdicts or {}

    async def verify(self, node: TaskNode) -> Verdict:
        v = self.verdicts.get(node.task.id, Verdict(True))
        if isinstance(v, list):
            return v[min(node.retries, len(v) - 1)]
        return v
```

---

## 3. 新建 `orchestrator.py`（Phase 1 核心）

```python
from __future__ import annotations
import logging
from app.domain.enums import TaskStatus
from app.domain.task_engine.dag import TaskGraph, TaskNode, build_graph
from app.domain.task_engine.fsm import TaskFSM
from app.domain.task_engine.scheduler import (
    compute_frontier, select_dispatchable, unreachable_pending,
)
from app.domain.task_engine.ports import (
    Planner, Executor, Verifier, PlanContext, RunResult, ExitReason,
)

logger = logging.getLogger(__name__)


class Orchestrator:
    """串行 MVP 指挥：唯一改状态者。无事件总线（串行 await 即可）。"""

    def __init__(self, *, planner: Planner, executor: Executor,
                 verifier: Verifier, ctx: PlanContext) -> None:
        self._planner, self._executor, self._verifier = planner, executor, verifier
        self._ctx = ctx
        self.graph: TaskGraph | None = None
        self.events: list[dict] = []          # MVP：内存事件（= task_events 雏形）

    async def run(self) -> RunResult:
        defs = await self._planner.plan(self._ctx)
        self.graph = build_graph(defs, set(self._ctx.workers))   # Scheduler 校验，非法抛
        self._record("plan_created", "", n=len(defs))

        max_steps = len(defs) * (TaskFSM.MAX_RETRY + 1) + 2      # 防死循环兜底
        for _ in range(max_steps):
            self._propagate_blocked()
            ready = select_dispatchable(
                compute_frontier(self.graph), running_count=0, max_concurrency=1)
            if not ready:
                return await self._terminal()
            await self._execute_and_settle(self.graph.nodes[ready[0]])
        return RunResult(ExitReason.BUDGET_EXCEEDED)

    # --- 单任务执行 + 结算 ---
    async def _execute_and_settle(self, node: TaskNode) -> None:
        self._transition(node, TaskStatus.QUEUED)
        self._transition(node, TaskStatus.RUNNING)
        node.worker = node.task.suggested_worker

        outcome = await self._executor.run(node)
        if not outcome.ok:
            return self._handle_failure(node, "worker 自身失败/超时")

        node.output = outcome.output
        self._transition(node, TaskStatus.VERIFYING)
        verdict = await self._verifier.verify(node)              # 裁决独立于 worker
        if verdict.passed:
            self._transition(node, TaskStatus.COMPLETED)
        else:
            self._handle_failure(node, verdict.reason)

    def _handle_failure(self, node: TaskNode, reason: str) -> None:
        node.fail_reason = reason
        self._transition(node, TaskStatus.FAILED)
        node.retries += 1
        if TaskFSM.can_retry(node.retries):
            self._transition(node, TaskStatus.PENDING)          # retry → 回 frontier

    # --- 阻塞传播 ---
    def _propagate_blocked(self) -> None:
        for tid in unreachable_pending(self.graph):
            self._transition(self.graph.nodes[tid], TaskStatus.BLOCKED)

    # --- 终止判定 ---
    async def _terminal(self) -> RunResult:
        nodes = list(self.graph.nodes.values())
        if all(n.status == TaskStatus.COMPLETED for n in nodes):
            return RunResult(ExitReason.COMPLETED, await self._planner.final_answer(self.graph))
        if any(n.status == TaskStatus.FAILED for n in nodes):
            return RunResult(ExitReason.FAILED)
        return RunResult(ExitReason.UNREACHABLE)

    # --- 状态变更（唯一写者）---
    def _transition(self, node: TaskNode, to: TaskStatus) -> None:
        TaskFSM.assert_transition(node.status, to)               # 非法转移抛
        frm, node.status = node.status, to
        self._record("transition", node.task.id, frm=str(frm), to=str(to))

    def _record(self, kind: str, task_id: str, **data) -> None:
        self.events.append({"kind": kind, "task": task_id, **data})
```

> `TaskFSM.MAX_RETRY` 需暴露（现 `fsm.py` 有模块级 `MAX_RETRY=3`，把它挂到类上或直接 import）。

---

## 4. 退出逻辑表

| 到达 `_terminal` 时 | 退出码 |
|---|---|
| 全部 COMPLETED | `COMPLETED` + final_answer |
| 有任意 FAILED（retry 耗尽） | `FAILED` |
| 无 FAILED 但有 BLOCKED（兜底） | `UNREACHABLE` |
| 步数超 `max_steps` | `BUDGET_EXCEEDED` |

---

## 5. 新建 `tests/test_orchestrator.py`

```python
import pytest
from app.domain.task_engine.dag import TaskDef, Check
from app.domain.task_engine.ports import Verdict, WorkerOutcome, ExitReason, PlanContext
from app.domain.task_engine.orchestrator import Orchestrator
from app.domain.enums import TaskStatus
from tests.fakes import FakePlanner, FakeExecutor, FakeVerifier


def _t(tid, deps=None):
    return TaskDef(id=tid, title=tid, suggested_worker="w",
                   depends_on=deps or [], acceptance=[Check("mechanical", "true")])


def _orch(planner, executor, verifier):
    ctx = PlanContext(task="x", workers=("w",))
    return Orchestrator(planner=planner, executor=executor, verifier=verifier, ctx=ctx)
```

| TC | Given | When | Then |
|----|-------|------|------|
| **9.1 happy** | FakePlanner [t1,t2,t3(deps t1,t2)]，executor 全 ok，verifier 全 pass | `await run()` | `reason==COMPLETED`；三节点 status==COMPLETED；`planner.final_called`；executor.dispatched 含全部 |
| **9.2 retry** | verifier t1 = `[Verdict(False), Verdict(True)]`（首败后过） | run | COMPLETED；`graph.nodes["t1"].retries==1` |
| **4.1 命门** | executor t1 ok=True（自称完成），verifier t1 = Verdict(False)（永败） | run | `reason==FAILED`；`t1.status==FAILED`；**t1 从未 COMPLETED** |
| **blocked** | t1 永败，t2 deps=[t1] | run | reason==FAILED；`t2.status==BLOCKED`（非 FAILED） |
| **worker 崩** | executor t1 = WorkerOutcome(ok=False) | run | t1 进 FAILED→retry，耗尽后 FAILED |

命门示例：

```python
@pytest.mark.asyncio
async def test_lying_worker_never_completes():
    planner = FakePlanner([_t("t1")])
    executor = FakeExecutor({"t1": WorkerOutcome(ok=True, output="我做完了")})  # 自称完成
    verifier = FakeVerifier({"t1": Verdict(False, "测试不过")})                 # 真相：没过
    orch = _orch(planner, executor, verifier)
    result = await orch.run()
    assert result.reason == ExitReason.FAILED
    assert orch.graph.nodes["t1"].status == TaskStatus.FAILED
    # t1 从未 COMPLETED：transition 事件里无 to=="completed"
    assert not any(e.get("to") == "completed" for e in orch.events)
```

> 需 `pytest-asyncio`（项目已有 async 测试，确认 marker 配置）。

---

## 6. 验收

```bash
V=/home/huishuohuademao/workspace/AgentHub/src/backend/.venv
$V/bin/python -m pytest tests/test_orchestrator.py tests/test_fsm.py \
    tests/test_dag.py tests/test_scheduler.py -q --no-cov
$V/bin/ruff check app/domain/task_engine/ tests/
```

**通过标准**：5 类用例全绿 + ruff 干净。此刻 **M1 达成**——控制面端到端跑通（纯 fake 证明），之后每相只是把一个 fake 换成真实现。

---

## 7. 文件增量小结

| 文件 | 动作 |
|------|------|
| `fsm.py` / `test_fsm.py` | 改一行（FAILED→PENDING） |
| `ports.py` | 新建（DTO + Protocol） |
| `tests/fakes.py` | 新建（3 个 fake） |
| `orchestrator.py` | 新建（核心循环） |
| `tests/test_orchestrator.py` | 新建（5 类用例） |

---

## 关联文档

- [[coordinator-mvp-implementation-plan]] 6 相总体方案（本文是 Phase 0+1 展开）
- [[coordinator-test-plan]] 各 TC 的 given/when/then
- [[coordinator-subsystem-collaborators]] 协作者职责
