"""R5 replan 测试：diff（认 workspace 不认节点）+ 换图 + 破坏性确认 + abort_inflight。"""

from __future__ import annotations

import pytest

from app.domain.enums import TaskStatus
from app.domain.task_engine.dag import Check, TaskDef, build_graph
from app.domain.task_engine.orchestrator import (
    Orchestrator,
    ReplanNeedsConfirmationError,
    compute_replan_diff,
)
from app.domain.task_engine.ports import PlanContext, RunResult
from tests.fakes import FakeExecutor, FakePlanner, FakeVerifier


def _t(tid: str, deps: list[str] | None = None) -> TaskDef:
    return TaskDef(id=tid, title=tid, suggested_worker="w",
                   depends_on=deps or [], acceptance=[Check("mechanical", "true")])


class _Capture:
    def __init__(self) -> None:
        self.results: list[RunResult] = []

    async def __call__(self, r: RunResult) -> None:
        self.results.append(r)


def _orch(*, executor=None, planner=None) -> Orchestrator:
    orch = Orchestrator(
        planner=planner or FakePlanner([]), executor=executor or FakeExecutor(),
        verifier=FakeVerifier(), ctx=PlanContext(task="原任务", workers=("w",)),
    )
    orch._on_finish = _Capture()
    return orch


# ── diff（D1：只读旧图状态，不按 id 匹配；D3：running 才破坏性）──


def test_compute_replan_diff() -> None:
    orch = _orch()
    orch.graph = build_graph([_t("a"), _t("b"), _t("c")], {"w"})
    orch.graph.nodes["a"].status = TaskStatus.COMPLETED
    orch.graph.nodes["b"].status = TaskStatus.RUNNING
    diff = compute_replan_diff(orch.graph, [_t("x"), _t("y")])
    assert diff.completed == ["a"]
    assert diff.running == ["b"]
    assert diff.new_count == 2
    assert diff.is_destructive is True  # 有 running


def test_diff_not_destructive_without_running() -> None:
    """只有 PENDING/COMPLETED、无 running → 非破坏性（完成成果不丢）。"""
    orch = _orch()
    orch.graph = build_graph([_t("a"), _t("b")], {"w"})
    orch.graph.nodes["a"].status = TaskStatus.COMPLETED  # 完成不算破坏
    diff = compute_replan_diff(orch.graph, [_t("x")])
    assert diff.is_destructive is False


# ── 换图 ──


@pytest.mark.asyncio
async def test_replan_destructive_without_force_raises() -> None:
    orch = _orch()
    orch.graph = build_graph([_t("a")], {"w"})
    orch.graph.nodes["a"].status = TaskStatus.RUNNING
    with pytest.raises(ReplanNeedsConfirmationError):
        await orch.replan([_t("x")], force=False)


@pytest.mark.asyncio
async def test_replan_swaps_to_fresh_graph_and_drives() -> None:
    """非破坏性 → 直接换全新图（全 PENDING）→ drive 跑新任务。"""
    orch = _orch()
    orch.graph = build_graph([_t("a")], {"w"})  # a PENDING（非破坏）
    await orch.replan([_t("x"), _t("y")])
    assert set(orch.graph.nodes) == {"x", "y"}  # 全新图
    assert all(n.status == TaskStatus.COMPLETED for n in orch.graph.nodes.values())


@pytest.mark.asyncio
async def test_replan_force_swaps_despite_running() -> None:
    orch = _orch()
    orch.graph = build_graph([_t("a")], {"w"})
    orch.graph.nodes["a"].status = TaskStatus.RUNNING
    await orch.replan([_t("x")], force=True)  # 确认过 → 强制换
    assert set(orch.graph.nodes) == {"x"}


# ── plan_replan：喂 requirement + 已完成摘要给 Planner ──


@pytest.mark.asyncio
async def test_plan_replan_feeds_requirement_and_done() -> None:
    captured: dict = {}

    class RecordingPlanner:
        async def plan(self, ctx):  # type: ignore[no-untyped-def]
            captured["task"] = ctx.task
            return [_t("new1")]

    orch = _orch(planner=RecordingPlanner())
    orch.graph = build_graph([_t("a")], {"w"})
    orch.graph.nodes["a"].status = TaskStatus.COMPLETED
    orch.graph.nodes["a"].output = "建好了后端 API"
    new_tasks, diff = await orch.plan_replan("改成微服务")
    assert "改成微服务" in captured["task"]
    assert "建好了后端 API" in captured["task"]  # 已完成喂进 prompt（勿重做）
    assert [t.id for t in new_tasks] == ["new1"]
    assert diff.completed == ["a"]


# ── abort_inflight ──


@pytest.mark.asyncio
async def test_abort_inflight_aborts_only_running() -> None:
    aborted: list[str] = []

    class AbortExecutor(FakeExecutor):
        async def abort(self, node_id: str) -> bool:
            aborted.append(node_id)
            return True

    orch = _orch(executor=AbortExecutor())
    orch.graph = build_graph([_t("a"), _t("b")], {"w"})
    orch.graph.nodes["a"].status = TaskStatus.RUNNING
    # b PENDING
    await orch.abort_inflight()
    assert aborted == ["a"]
