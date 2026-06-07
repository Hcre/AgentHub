"""CoordinatorOrchestrator 失败降级测试（P2 B-2-P2-F01）。

覆盖三路径（T-03）：
1. 全部成功：3 Agent 并行 → 全部 success
2. 单 Agent 失败降级：1 失败 + 2 成功 → 整体 partial
3. 全部失败：3 全部失败 → 整体 failed + 降级为手动 @Agent 模式

降级矩阵：
    all success   → status="success", degraded=False, mode="auto"
    1 fail 降级   → status="partial",  degraded=False, mode="auto"
    全 fail       → status="failed",   degraded=True,  mode="manual"
    decompose fail → status="decompose_failed", degraded=True, mode="manual"

状态字段（ADR-05 attach 模式）：
    - tasks: per_subtask 状态（task_id, agent_id, status, output, error_code）
    - per_agent_status: per_agent 聚合（task_count, success_count, failed_count）
"""

from __future__ import annotations

import asyncio

import pytest

from app.application.services.coordinator_orchestrator import (
    CoordinatorOrchestrator,
    CoordinatorStatus,
    SubTaskStatus,
)
from app.domain.task_engine.coordinator import Coordinator
from app.domain.task_engine.harness import PlannedTask, TaskPlan

# --- Mock Coordinator（可控的 LLM 分解）---


class MockCoordinator(Coordinator):
    """Mock 协调者：固定返回 3 个子任务（不调真实 LLM）。"""

    def __init__(self, plan: TaskPlan) -> None:
        # 不调 super().__init__（避免需要 UnifiedAgent + Harness 实例）
        self._plan = plan

    async def decompose(self, message, available_agents, conversation_history=None):  # type: ignore[no-untyped-def, override]
        return self._plan


def _make_plan(n_tasks: int = 3) -> TaskPlan:
    return TaskPlan(
        tasks=[
            PlannedTask(
                title=f"task-{i}",
                description=f"desc-{i}",
                suggested_worker="any",
            )
            for i in range(n_tasks)
        ],
        rationale="test plan",
    )


# --- Mock Worker Dispatch（按 agent_id 行为可控）---


def _make_dispatch(behavior: dict[str, str], *, fail_on: set | None = None):
    """behavior: agent_id_str → output（成功）或 raises（失败）。

    fail_on: 显式指定要 raise 的 agent_id 集合（用于更细控制）。
    """
    fail_on = fail_on or set()

    async def _dispatch(task: PlannedTask, agent_id) -> str:  # type: ignore[no-untyped-def]
        if str(agent_id) in fail_on:
            err = behavior.get(str(agent_id), "E_FAIL")
            raise RuntimeError(err)
        # 模拟小延迟，避免完全零时
        await asyncio.sleep(0.001)
        return behavior.get(str(agent_id), f"out-{task.title}")

    return _dispatch


# ============ 1. 全部成功 ============


@pytest.mark.asyncio
async def test_all_agents_succeed_no_degrade() -> None:
    """3 Agent 全成功 → status=success, degraded=False, mode=auto。"""
    plan = _make_plan(3)
    agent_ids = [f"agent-{i}" for i in range(3)]  # type: ignore[list-item]
    orch = CoordinatorOrchestrator(
        coordinator=MockCoordinator(plan),  # type: ignore[arg-type]
        worker_dispatch=_make_dispatch(
            {a: f"ok-{a}" for a in agent_ids}  # type: ignore[arg-type]
        ),
    )
    outcome = await orch.run(
        user_message="refactor utils.ts",
        agent_ids=agent_ids,  # type: ignore[arg-type]
    )

    assert outcome.status == CoordinatorStatus.SUCCESS
    assert outcome.degraded is False
    assert outcome.mode == "auto"
    assert outcome.success_count == 3
    assert outcome.failed_count == 0
    assert len(outcome.tasks) == 3
    assert all(t.status == SubTaskStatus.SUCCESS for t in outcome.tasks)
    # per_agent_status：3 个 agent 都 ok
    assert len(outcome.per_agent_status) == 3
    for aid in agent_ids:
        bucket = outcome.per_agent_status[str(aid)]
        assert bucket["status"] == "ok"
        assert bucket["success_count"] == 1
        assert bucket["failed_count"] == 0


# ============ 2. 单 Agent 失败降级 ============


@pytest.mark.asyncio
async def test_one_agent_fails_partial_no_full_degrade() -> None:
    """1 失败 + 2 成功 → status=partial, degraded=False（不降级）。"""
    plan = _make_plan(3)
    agent_ids = [f"agent-{i}" for i in range(3)]  # type: ignore[list-item]
    # agent-1 失败
    fail_set = {agent_ids[1]}  # type: ignore[index]
    orch = CoordinatorOrchestrator(
        coordinator=MockCoordinator(plan),  # type: ignore[arg-type]
        worker_dispatch=_make_dispatch(
            {a: f"ok-{a}" for a in agent_ids},  # type: ignore[arg-type]
            fail_on=fail_set,
        ),
    )
    outcome = await orch.run(
        user_message="refactor utils.ts",
        agent_ids=agent_ids,  # type: ignore[arg-type]
    )

    assert outcome.status == CoordinatorStatus.PARTIAL
    assert outcome.degraded is False
    assert outcome.mode == "auto"
    assert outcome.success_count == 2
    assert outcome.failed_count == 1
    # 失败子任务的 error_code 被记录
    failed = [t for t in outcome.tasks if t.status == SubTaskStatus.FAILED]
    assert len(failed) == 1
    assert failed[0].error_code == "RuntimeError"
    # 失败 agent 在 per_agent_status 中标 failed
    failed_agent_id = failed[0].agent_id
    assert outcome.per_agent_status[str(failed_agent_id)]["status"] == "failed"
    # 成功 agent 标 ok
    success_ids = [str(t.agent_id) for t in outcome.tasks if t.status == SubTaskStatus.SUCCESS]
    for sid in success_ids:
        assert outcome.per_agent_status[sid]["status"] == "ok"


# ============ 3. 全部失败 → 降级为手动 @Agent 模式 ============


@pytest.mark.asyncio
async def test_all_agents_fail_full_degrade_to_manual() -> None:
    """3 Agent 全失败 → status=failed, degraded=True, mode=manual。"""
    plan = _make_plan(3)
    agent_ids = [f"agent-{i}" for i in range(3)]  # type: ignore[list-item]
    orch = CoordinatorOrchestrator(
        coordinator=MockCoordinator(plan),  # type: ignore[arg-type]
        worker_dispatch=_make_dispatch(
            {},  # 空 output 映射，所有 agent 走 fail_on 分支
            fail_on=set(agent_ids),  # type: ignore[arg-type]
        ),
    )
    outcome = await orch.run(
        user_message="refactor utils.ts",
        agent_ids=agent_ids,  # type: ignore[arg-type]
    )

    assert outcome.status == CoordinatorStatus.FAILED
    assert outcome.degraded is True
    assert outcome.mode == "manual"
    assert outcome.success_count == 0
    assert outcome.failed_count == 3
    # 摘要提示用户手动 @Agent
    assert "手动" in outcome.summary or "@Agent" in outcome.summary
    # per_agent_status 全部 failed
    for aid in agent_ids:
        bucket = outcome.per_agent_status[str(aid)]
        assert bucket["status"] == "failed"
        assert bucket["failed_count"] == 1


# ============ 4. 边界：任务分解本身失败 → 降级 ============


class FailingCoordinator(Coordinator):
    """Mock 协调者：decompose 抛异常。"""

    def __init__(self) -> None:
        pass  # 不调 super

    async def decompose(self, message, available_agents, conversation_history=None):  # type: ignore[no-untyped-def, override]
        raise RuntimeError("LLM service unavailable")


@pytest.mark.asyncio
async def test_decompose_failure_triggers_manual_degrade() -> None:
    """Coordinator.decompose() 抛错 → 整体降级为手动 @Agent 模式。"""
    orch = CoordinatorOrchestrator(
        coordinator=FailingCoordinator(),  # type: ignore[arg-type]
        worker_dispatch=_make_dispatch({}),
    )
    agent_ids = ["a1", "a2"]  # type: ignore[list-item]
    outcome = await orch.run(
        user_message="fix bug",
        agent_ids=agent_ids,  # type: ignore[arg-type]
    )

    assert outcome.status == CoordinatorStatus.DECOMPOSE_FAILED
    assert outcome.degraded is True
    assert outcome.mode == "manual"
    # 全部子任务 SKIPPED
    assert all(t.status == SubTaskStatus.SKIPPED for t in outcome.tasks)
    assert "任务分解失败" in outcome.summary


# ============ 5. 边界：无可用 Agent → 全部 SKIPPED ============


@pytest.mark.asyncio
async def test_no_available_agents_all_skipped() -> None:
    """agent_ids=[] → 全部 SKIPPED。"""
    plan = _make_plan(3)
    orch = CoordinatorOrchestrator(
        coordinator=MockCoordinator(plan),  # type: ignore[arg-type]
        worker_dispatch=_make_dispatch({}),
    )
    outcome = await orch.run(
        user_message="refactor",
        agent_ids=[],  # type: ignore[arg-type]
    )

    # 任务被 decompose → plan.rationale 设置；但全部 SKIPPED
    assert outcome.plan_rationale == "test plan"
    assert len(outcome.tasks) == 3
    assert all(t.status == SubTaskStatus.SKIPPED for t in outcome.tasks)
    # 0 成功 0 失败（SKIPPED 不算 success 也不算 failed）
    assert outcome.success_count == 0
    assert outcome.failed_count == 0


# ============ 6. 并行性验证：3 子任务并发执行 ============


@pytest.mark.asyncio
async def test_tasks_run_in_parallel() -> None:
    """3 个子任务 wall time ≈ 单个任务耗时（验证并行，非串行）。"""
    plan = _make_plan(3)
    agent_ids = ["a1", "a2", "a3"]  # type: ignore[list-item]

    async def _slow_dispatch(task: PlannedTask, agent_id) -> str:  # type: ignore[no-untyped-def]
        await asyncio.sleep(0.1)  # 100ms × 3
        return f"ok-{agent_id}"

    orch = CoordinatorOrchestrator(
        coordinator=MockCoordinator(plan),  # type: ignore[arg-type]
        worker_dispatch=_slow_dispatch,
    )
    import time as _t

    start = _t.time()
    outcome = await orch.run(
        user_message="parallel test",
        agent_ids=agent_ids,  # type: ignore[arg-type]
    )
    elapsed = _t.time() - start
    assert outcome.status == CoordinatorStatus.SUCCESS
    # 串行需 ~300ms，并行应 ≤200ms（容差 100ms）
    assert elapsed < 0.2, f"疑似串行：{elapsed:.3f}s"
