"""DAG 构建与校验单测（coordinator-test-plan §1）。

纯逻辑，无 IO。测 plumbing——挡住坏 plan，不验证 LLM 产出好 plan。
"""

import pytest

from app.domain.enums import TaskStatus
from app.domain.task_engine.dag import (
    Check,
    DagValidationError,
    TaskDef,
    build_graph,
)

WORKERS = {"前端Agent", "后端Agent", "测试Agent"}


def _task(
    tid: str,
    worker: str = "前端Agent",
    deps: list[str] | None = None,
    *,
    acceptance: list[Check] | None = None,
    no_verify: bool = False,
) -> TaskDef:
    return TaskDef(
        id=tid,
        title=f"task {tid}",
        suggested_worker=worker,
        depends_on=deps or [],
        acceptance=acceptance if acceptance is not None else [Check("mechanical", "true")],
        no_verify=no_verify,
    )


# --- TC-1.1 合法 plan 编译为正确 DAG ---


def test_valid_plan_builds_graph() -> None:
    tasks = [
        _task("t1"),
        _task("t2", "后端Agent"),
        _task("t3", "测试Agent", deps=["t1", "t2"]),
    ]
    graph = build_graph(tasks, WORKERS)

    assert set(graph.nodes) == {"t1", "t2", "t3"}
    assert graph.nodes["t3"].task.depends_on == ["t1", "t2"]
    assert all(n.status == TaskStatus.PENDING for n in graph.nodes.values())


# --- TC-1.2 环 → 拒绝 ---


def test_cycle_rejected() -> None:
    tasks = [
        _task("t1", deps=["t2"]),
        _task("t2", deps=["t1"]),
    ]
    with pytest.raises(DagValidationError, match="循环|环|cycle"):
        build_graph(tasks, WORKERS)


def test_self_cycle_rejected() -> None:
    with pytest.raises(DagValidationError):
        build_graph([_task("t1", deps=["t1"])], WORKERS)


# --- TC-1.3 悬空依赖 → 拒绝 ---


def test_dangling_dependency_rejected() -> None:
    tasks = [_task("t3", deps=["t99"])]
    with pytest.raises(DagValidationError, match="t99"):
        build_graph(tasks, WORKERS)


# --- TC-1.4 worker 不存在 → 拒绝 ---


def test_unknown_worker_rejected() -> None:
    tasks = [_task("t1", worker="不存在Agent")]
    with pytest.raises(DagValidationError, match="不存在Agent"):
        build_graph(tasks, WORKERS)


# --- 重复 id → 拒绝 ---


def test_duplicate_id_rejected() -> None:
    tasks = [_task("t1"), _task("t1", "后端Agent")]
    with pytest.raises(DagValidationError, match="重复|duplicate|t1"):
        build_graph(tasks, WORKERS)


# --- TC-1.6 无 acceptance → 拒绝（不静默通过）---


def test_no_acceptance_rejected() -> None:
    tasks = [_task("t1", acceptance=[])]
    with pytest.raises(DagValidationError, match="acceptance|验收|no_verify"):
        build_graph(tasks, WORKERS)


def test_no_acceptance_with_explicit_no_verify_allowed() -> None:
    tasks = [_task("t1", acceptance=[], no_verify=True)]
    graph = build_graph(tasks, WORKERS)
    assert graph.nodes["t1"].task.no_verify is True
