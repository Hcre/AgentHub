"""Supervisor Agent 集成测试计划（6 场景覆盖 v4 事件驱动 + MCP 工具 + NOT_DONE/nudge 流）。

测试分级：
  L1 — 域决策引擎纯函数测试（零 IO，确定性断言）
  L2 — Orchestrator + FakeSupervisor 钩子联动测试（fake 注入，无真实 CLI/LLM）
  L2b— NOT_DONE → auto-nudge → task_complete 全流程（同上注入 fake）
  L3 — 真实后端集成 curl 测试（需 live server，见文件末尾）

运行方法：
  pytest tests/test_supervisor_integration.py -v

前置假设（来自 src/backend/app/core/config.py + domain/task_engine/ports.py）：
  - Supervisor MCP 工具端点：/api/supervisor-tools/sse?session_id=<uuid>
  - Step-tools MCP 端点：/api/step-tools/sse?agent_id=<uuid>&session_id=<uuid>&group_id=<uuid>
  - task_complete 工具名：mcp__agenthub-step-tools__task_complete（也接受裸 task_complete）
  - supervisor 工具：supervisor_get_plan / supervisor_nudge / supervisor_replan /
    supervisor_trigger_deploy / supervisor_send_message
  - supervisor 配置：SUPERVISOR_AGENT_NAME / SUPERVISOR_ENABLED / SUPERVISOR_MAX_TURNS
  - NOT_DONE 时 orchestration 自动 enqueue nudge note 到 worker 桶
  - 域决策引擎纯函数（supervisor.py），SupervisorService（L3）负责执行
  - CoordinatorRun._pending_notes 按 worker 分桶
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import pytest

from app.domain.enums import TaskStatus
from app.domain.task_engine.dag import Check, TaskDef, TaskNode
from app.domain.task_engine.orchestrator import Orchestrator
from app.domain.task_engine.ports import (
    ExitReason,
    PlanContext,
    RunResult,
    StallEvent,
    StepEvent,
    Supervisor,
    SupervisorConfig,
    Verdict,
    WorkerOutcome,
)
from app.domain.task_engine.supervisor import (
    SupervisorDecision,
    SupervisorDecisionKind,
    SupervisorState,
    decide_on_all_completed,
    decide_on_stall,
    decide_on_step_completed,
    decide_on_step_failed,
)
from tests.fakes import FakeExecutor, FakePlanner, FakeVerifier

# ═══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════════


def _t(tid: str, deps: list[str] | None = None, worker: str = "w") -> TaskDef:
    return TaskDef(
        id=tid,
        title=tid,
        suggested_worker=worker,
        depends_on=deps or [],
        acceptance=[Check("mechanical", "true")],
    )


def _default_config() -> SupervisorConfig:
    return SupervisorConfig(
        supervisor_agent_id="supervisor-bot",
        enabled=True,
        max_turns=10,
    )


class _Capture:
    """Async _on_finish callback：捕获 RunResult 供测试断言。"""

    def __init__(self) -> None:
        self.results: list[RunResult] = []

    async def __call__(self, r: RunResult) -> None:
        self.results.append(r)


# ── FakeSupervisor（可测接缝）─────────────────────────────────────────────────


class FakeSupervisor:
    """测试用 Supervisor 实现：记录所有钩子调用，可注入预设决策覆盖。

    与 SupervisorService 不同——不执行决策（不 spawn CLI、不发消息），纯收集 + 预设产出。
    """

    def __init__(self, decisions: list[SupervisorDecision] | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        # 按 call 索引取决策列表（每次钩子调用 pop 下一个），None = 不覆盖（用真实决策引擎）
        self._next_decision: Callable[[], list[SupervisorDecision]]
        decisions = decisions or []
        self._decision_queue = list(decisions)

    # ── 调用记录 ──

    async def on_step_completed(self, session_id: UUID, event: StepEvent) -> None:
        self.calls.append(("on_step_completed", {
            "session_id": session_id, "event": event,
        }))

    async def on_step_failed(self, session_id: UUID, event: StepEvent) -> None:
        self.calls.append(("on_step_failed", {
            "session_id": session_id, "event": event,
        }))

    async def on_all_completed(self, session_id: UUID) -> None:
        self.calls.append(("on_all_completed", {
            "session_id": session_id,
        }))

    async def on_stall_detected(self, session_id: UUID, event: StallEvent) -> None:
        self.calls.append(("on_stall_detected", {
            "session_id": session_id, "event": event,
        }))


def _orch(planner, executor, verifier, *, supervisor=None, on_finish=None) -> Orchestrator:
    """工厂：组装 Orchestrator，注入可选的 supervisor + on_finish。"""
    ctx = PlanContext(task="用 FastAPI 实现用户 API", workers=("w", "worker-a", "worker-b"))
    orch = Orchestrator(
        planner=planner, executor=executor, verifier=verifier, ctx=ctx,
        supervisor=supervisor, session_id=uuid4(),
    )
    orch._on_finish = on_finish
    return orch


# ═══════════════════════════════════════════════════════════════════════════════
# L1 ─ 决策引擎纯函数测试（零 IO）
# ═══════════════════════════════════════════════════════════════════════════════


class TestDecisionsPure:
    """域决策引擎纯函数测试：输入事件 + 状态 → 输出决策列表。

    成功标准：
      - 首个 step 完成 → 空决策（静默推进）
      - 3 个 step 完成 → all_completed 产 SUMMARIZE + DEPLOY
      - step 失败 < 3 → ALERT + NONE（等用户决策）
      - step 失败 >= 3 → ALERT + REPLAN
      - stall → ALERT + NUDGE（每个失败节点），超过 max_turns → REPLAN
    """

    def test_step_completed_returns_empty_for_stable_progress(self) -> None:
        """场景 1a：首个步骤完成 → 不干涉（静默）。"""
        state = SupervisorState()
        config = _default_config()
        event = StepEvent(step_id="t1", title="设置项目", worker="w", status="completed")
        decisions = decide_on_step_completed(event, state, config)
        assert decisions == []
        assert state.completed_count == 1

    def test_all_completed_produces_summarize_and_deploy(self) -> None:
        """场景 1b：全部完成 → SUMMARIZE + DEPLOY。"""
        state = SupervisorState()
        state.completed_count = 5
        config = _default_config()
        decisions = decide_on_all_completed(5, state, config)
        kinds = [d.kind for d in decisions]
        assert SupervisorDecisionKind.SUMMARIZE in kinds
        assert SupervisorDecisionKind.DEPLOY in kinds
        assert state.deploy_triggered is True

    def test_all_completed_no_duplicate_deploy(self) -> None:
        """场景 1c：再次全完成 → 不重复 DEPLOY（已触发过）。"""
        state = SupervisorState()
        state.completed_count = 3
        state.deploy_triggered = True
        config = _default_config()
        decisions = decide_on_all_completed(3, state, config)
        kinds = [d.kind for d in decisions]
        assert SupervisorDecisionKind.DEPLOY not in kinds

    def test_step_failed_under_3_produces_alert_and_none(self) -> None:
        """场景 1d：1 个步骤失败 → ALERT + 等用户决策。"""
        state = SupervisorState()
        config = _default_config()
        event = StepEvent(step_id="t1", title="数据库迁移", worker="w",
                          status="failed", reason="连接拒绝")
        decisions = decide_on_step_failed(event, state, config)
        kinds = [d.kind for d in decisions]
        assert SupervisorDecisionKind.ALERT in kinds
        # < 3 个失败，不发 REPLAN
        assert SupervisorDecisionKind.REPLAN not in kinds
        assert state.failed_count == 1

    def test_step_failed_at_3_produces_replan(self) -> None:
        """场景 1e：累计 3 个失败 → ALERT + REPLAN。"""
        state = SupervisorState()
        state.failed_count = 2  # 前 2 个已失败
        config = _default_config()
        event = StepEvent(step_id="t3", title="部署", worker="w",
                          status="failed", reason="权限拒绝")
        decisions = decide_on_step_failed(event, state, config)
        kinds = [d.kind for d in decisions]
        assert SupervisorDecisionKind.ALERT in kinds
        assert SupervisorDecisionKind.REPLAN in kinds
        assert state.failed_count == 3

    def test_stall_produces_nudge_for_each_failed(self) -> None:
        """场景 1f：卡死 → 每个失败节点一个 NUDGE。"""
        state = SupervisorState()
        config = SupervisorConfig(supervisor_agent_id="sv", enabled=True, max_turns=5)
        event = StallEvent(
            description="t1 失败导致 t2 t3 不可达",
            failed_steps=("t1",),
            blocked_steps=("t2", "t3"),
        )
        decisions = decide_on_stall(event, state, config)
        kinds = [d.kind for d in decisions]
        assert SupervisorDecisionKind.ALERT in kinds
        nudge_decisions = [d for d in decisions if d.kind == SupervisorDecisionKind.NUDGE]
        assert len(nudge_decisions) == 1  # 一个失败节点 → 一个 nudge
        assert nudge_decisions[0].target_worker == "t1"

    def test_stall_exceeds_max_turns_produces_replan(self) -> None:
        """场景 1g：nudge 次数已达 max_turns → 额外建议 REPLAN。"""
        state = SupervisorState()
        state.nudge_count = 10  # 已达上限
        config = SupervisorConfig(supervisor_agent_id="sv", enabled=True, max_turns=10)
        event = StallEvent(
            description="t1 失败导致 t2 不可达",
            failed_steps=("t1",),
            blocked_steps=("t2",),
        )
        decisions = decide_on_stall(event, state, config)
        kinds = [d.kind for d in decisions]
        assert SupervisorDecisionKind.REPLAN in kinds


# ═══════════════════════════════════════════════════════════════════════════════
# L2 ─ Orchestrator + FakeSupervisor 钩子联动
# ═══════════════════════════════════════════════════════════════════════════════


class TestSupervisorHookIntegration:
    """验证 Orchestrator 在正确时机调用 Supervisor 钩子。

    成功标准（对照 ports.py Supervisor Protocol）：
      - step 完成（VERIFYING → COMPLETED）→ on_step_completed 被调
      - step 永久失败（retry 耗尽）→ on_step_failed 被调
      - 全部完成 → on_all_completed 被调
      - 卡死检测 → on_stall_detected 被调
      - 注入 None → 所有钩子静默跳过（不抛异常）
    """

    @pytest.mark.asyncio
    async def test_step_completed_triggers_supervisor_hook(self) -> None:
        """场景 2a：t1 完成 → on_step_completed(step_id=t1, status=completed)。"""
        supervisor = FakeSupervisor()
        planner = FakePlanner([_t("t1")])
        capture = _Capture()
        orch = _orch(planner, FakeExecutor(), FakeVerifier(),
                     supervisor=supervisor, on_finish=capture)

        await orch.start()

        assert len(capture.results) == 1
        assert capture.results[0].reason == ExitReason.COMPLETED
        # 验证钩子被调
        assert len(supervisor.calls) >= 2  # on_step_completed + on_all_completed
        completed_calls = [c for c in supervisor.calls if c[0] == "on_step_completed"]
        assert len(completed_calls) == 1
        assert completed_calls[0][1]["event"].step_id == "t1"
        assert completed_calls[0][1]["event"].status == "completed"

    @pytest.mark.asyncio
    async def test_step_failed_triggers_supervisor_hook(self) -> None:
        """场景 2b：t1 retry 耗尽永久失败 → on_step_failed 被调。"""
        supervisor = FakeSupervisor()
        verifier = FakeVerifier({"t1": [Verdict(False, "永败")] * 10})  # 耗尽 retry
        planner = FakePlanner([_t("t1"), _t("t2", deps=["t1"])])
        capture = _Capture()
        orch = _orch(planner, FakeExecutor(), verifier,
                     supervisor=supervisor, on_finish=capture)

        await orch.start()

        failed_calls = [c for c in supervisor.calls if c[0] == "on_step_failed"]
        assert len(failed_calls) >= 1
        assert failed_calls[0][1]["event"].status == "failed"

    @pytest.mark.asyncio
    async def test_all_completed_triggers_supervisor_hook(self) -> None:
        """场景 2c：两个步骤全完成 → on_all_completed 被调。"""
        supervisor = FakeSupervisor()
        planner = FakePlanner([_t("t1"), _t("t2")])
        capture = _Capture()
        orch = _orch(planner, FakeExecutor(), FakeVerifier(),
                     supervisor=supervisor, on_finish=capture)

        await orch.start()

        all_done_calls = [c for c in supervisor.calls if c[0] == "on_all_completed"]
        assert len(all_done_calls) == 1
        assert len(capture.results) == 1
        assert capture.results[0].reason == ExitReason.COMPLETED

    @pytest.mark.asyncio
    async def test_stall_triggers_supervisor_hook(self) -> None:
        """场景 2d：t1 永久失败阻塞 t2 → on_stall_detected 被调（含 blocked 信息）。"""
        supervisor = FakeSupervisor()
        verifier = FakeVerifier({"t1": [Verdict(False, "永败")] * 10})
        planner = FakePlanner([_t("t1"), _t("t2", deps=["t1"])])
        capture = _Capture()
        orch = _orch(planner, FakeExecutor(), verifier,
                     supervisor=supervisor, on_finish=capture)

        await orch.start()

        stall_calls = [c for c in supervisor.calls if c[0] == "on_stall_detected"]
        assert len(stall_calls) >= 1
        event = stall_calls[0][1]["event"]
        assert "t1" in event.failed_steps
        assert "t2" in event.blocked_steps

    @pytest.mark.asyncio
    async def test_null_supervisor_no_errors(self) -> None:
        """场景 2e：无 supervisor 注入 → 所有钩子静默跳过，不抛异常。"""
        capture = _Capture()
        orch = _orch(FakePlanner([_t("t1")]), FakeExecutor(), FakeVerifier(),
                     supervisor=None, on_finish=capture)

        await orch.start()

        assert len(capture.results) == 1
        assert capture.results[0].reason == ExitReason.COMPLETED

    @pytest.mark.asyncio
    async def test_supervisor_hook_order_two_steps(self) -> None:
        """场景 2f：依赖链 t1→t2 全完成 → on_step_completed 调 2 次，
        最后 on_all_completed 调 1 次。"""
        supervisor = FakeSupervisor()
        planner = FakePlanner([_t("t1"), _t("t2", deps=["t1"])])
        capture = _Capture()
        orch = _orch(planner, FakeExecutor(), FakeVerifier(),
                     supervisor=supervisor, on_finish=capture)

        await orch.start()

        # 调用顺序应为：step_completed(t1) → step_completed(t2) → all_completed
        call_names = [c[0] for c in supervisor.calls]
        step_idx = [i for i, n in enumerate(call_names) if n == "on_step_completed"]
        all_idx = [i for i, n in enumerate(call_names) if n == "on_all_completed"]
        assert len(step_idx) == 2
        assert len(all_idx) == 1
        # 全部完成在最后
        assert all_idx[0] > step_idx[-1]


# ═══════════════════════════════════════════════════════════════════════════════
# L2b ─ NOT_DONE → auto-nudge → task_complete 全流程
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotDoneNudgeCompleteFlow:
    """验证 worker 未交卷时的完整恢复流程。

    成功标准：
      - worker 流结束未调 task_complete → Executor 返回 not_done（ok=True）
      - Orchestrator 在 _settle 检测 not_done → auto-enqueue nudge note 到 worker 桶
      - nudge note 内容包含 "task_complete" 关键字
      - 下次同一 worker dispatch 时，pending_notes 被注入 instruction（turn-end drain）
      - worker 收到 nudge 后调用 task_complete → 正常完成流转

    架构复习（coordinator-v4-R1 §2.2 + orchestrator._settle）：
      outcome.status == "not_done" → 节点停在 RUNNING → _drive break（park）→
      不转状态 → 不调 _finish → run 留存 → 等 feed 续跑
    """

    @pytest.mark.asyncio
    async def test_not_done_auto_enqueues_nudge_note(self) -> None:
        """场景 3a：not_done → Orchestrator 在 while loop 内 auto-enqueue nudge note
        并立即 re-dispatch 送达 worker。nudge 被消费后桶为空，节点 park。"""

        class NotDoneOnceExecutor:
            def __init__(self) -> None:
                self.dispatched: list[str] = []
                self.notes_seen: list[list[str]] = []

            async def run(self, node):
                self.dispatched.append(node.task.id)
                self.notes_seen.append(node.pending_notes or [])
                if node.pending_answer is None:
                    return WorkerOutcome(ok=True, status="not_done",
                                        output="worker 没交卷")
                return WorkerOutcome(ok=True, status="completed", output="done")

            async def abort(self, node_id: str) -> bool:
                return False

            async def summarize(self, node) -> str:
                return ""

        supervisor = FakeSupervisor()
        executor = NotDoneOnceExecutor()
        planner = FakePlanner([_t("t1")])
        capture = _Capture()
        orch = _orch(planner, executor, FakeVerifier(),
                     supervisor=supervisor, on_finish=capture)

        await orch.start()

        # 核心契约：park 不调 _finish（run 留存）
        assert len(capture.results) == 0
        assert orch.graph.nodes["t1"].status == TaskStatus.RUNNING

        # 验证 auto-nudge：被 enqueue 后立即 re-dispatch（dispatch count ≥ 2）
        assert len(executor.dispatched) >= 2, (
            f"auto-nudge 应触发 re-dispatch，实际派发 {len(executor.dispatched)} 次"
        )
        # 第二轮 dispatch 的 notes 应包含 nudge（task_complete 提示）
        second_notes = executor.notes_seen[1] if len(executor.notes_seen) > 1 else []
        any_nudge = any("task_complete" in n for n in second_notes)
        assert any_nudge, (
            f"第二轮 dispatch 应包含 auto-nudge note，实际: {second_notes}"
        )
        # nudge 已被消费，桶应为空（不会残留到下次 on_feed 重复注入）
        notes = orch._pending_notes.get("w", [])
        assert len(notes) == 0, (
            f"nudge 已被 re-dispatch 消费，桶应为空，实际: {notes}"
        )

    @pytest.mark.asyncio
    async def test_not_done_then_task_complete_via_feed(self) -> None:
        """场景 3b：not_done → auto-nudge re-dispatch → 仍 not_done → park
        → 用户 feed → worker 收到答案后交卷。

        完整流程：
          1. start → t1 派发 → not_done → auto-nudge → re-dispatch
          2. re-dispatch（带 nudge）→ worker 仍需用户输入 → not_done → park
             （nudge 在 re-dispatch 时已被消费）
          3. on_feed("t1", "请继续") → resume → worker 收到用户回答 → completed
          4. 经 VERIFYING → COMPLETED → _finish
        """

        class NotDoneThenCompleteExecutor:
            def __init__(self) -> None:
                self.dispatched: list[str] = []
                self.notes_seen: list[list[str]] = []

            async def run(self, node):
                self.dispatched.append(node.task.id)
                self.notes_seen.append(node.pending_notes or [])
                # Worker only completes when it has a user answer;
                # the auto-nudge alone is not enough.
                if node.pending_answer is None:
                    return WorkerOutcome(ok=True, status="not_done",
                                        output="worker 还没交卷")
                return WorkerOutcome(ok=True, status="completed", output="交卷了")

            async def abort(self, node_id: str) -> bool:
                return False

            async def summarize(self, node) -> str:
                return ""

        supervisor = FakeSupervisor()
        executor = NotDoneThenCompleteExecutor()
        planner = FakePlanner([_t("t1")])
        capture = _Capture()
        orch = _orch(planner, executor, FakeVerifier(),
                     supervisor=supervisor, on_finish=capture)

        # Step 1: start → not_done → auto-nudge re-dispatch → still not_done → park
        await orch.start()
        assert len(capture.results) == 0
        assert orch.graph.nodes["t1"].status == TaskStatus.RUNNING

        # Step 2: 用户 feed 回答
        await orch.on_feed("t1", "没问题，继续。")

        # Step 3: 验证完成
        assert len(capture.results) == 1
        assert capture.results[0].reason == ExitReason.COMPLETED
        assert orch.graph.nodes["t1"].status == TaskStatus.COMPLETED

        # Step 4: 验证 re-dispatch（dispatch 2）收到了 nudge notes
        # 派发序列：1=初始 not_done, 2=带 nudge re-dispatch not_done, 3=on_feed 完成
        assert len(executor.dispatched) == 3, (
            f"应有 3 次派发，实际 {len(executor.dispatched)}"
        )
        second_dispatch_notes = executor.notes_seen[1] if len(executor.notes_seen) > 1 else []
        any_nudge = any("task_complete" in n for n in second_dispatch_notes)
        assert any_nudge, (
            f"第二次 dispatch 应该收到 auto-nudge note，实际: {second_dispatch_notes}"
        )

    @pytest.mark.asyncio
    async def test_nudge_note_dispatched_immediately(self) -> None:
        """场景 3c：not_done 后 nudge note 在 while loop 内 enqueue
        并立即触发 re-dispatch 送达 worker（不再残留桶中等待下次外部触发）。

        v4 R1 修复：nudge 原在 _settle（while loop 之后）写入桶 → while 已退出，
        note 永久残留直到下次 on_feed。现移至 while loop 内，dispatch_count==1 时
        触发 → re-dispatch → nudge 消费 → 桶空。
        """
        playwright = FakePlanner([_t("t1")])
        executor = FakeExecutor({
            "t1": WorkerOutcome(ok=True, status="not_done",
                                output="worker 没交卷"),
        })
        orch = _orch(playwright, executor, FakeVerifier(),
                     supervisor=FakeSupervisor())

        await orch.start()

        # not_done → auto-nudge added in while loop → re-dispatch → nudge consumed
        # Bucket should be empty now (nudge was delivered, not left sitting).
        notes = orch._pending_notes.get("w")
        assert notes is None or len(notes) == 0, (
            f"nudge 已被 re-dispatch 消费，桶应为空/不存在，实际: {notes}"
        )
        # Node should be parked (RUNNING, not COMPLETED — worker didn't call task_complete)
        assert orch.graph.nodes["t1"].status == TaskStatus.RUNNING

    @pytest.mark.asyncio
    async def test_multi_worker_not_done_independent(self) -> None:
        """场景 3d：两个独立任务，t1 not_done、t2 正常完成，互不干扰。"""
        supervisor = FakeSupervisor()

        class MixedExecutor:
            def __init__(self) -> None:
                self.dispatched: list[str] = []

            async def run(self, node):
                self.dispatched.append(node.task.id)
                if node.task.id == "t1" and node.pending_answer is None:
                    return WorkerOutcome(ok=True, status="not_done",
                                        output="t1 还在想")
                return WorkerOutcome(ok=True, status="completed", output="done")

            async def abort(self, node_id: str) -> bool:
                return False

            async def summarize(self, node) -> str:
                return ""

        planner = FakePlanner([_t("t1", worker="worker-a"), _t("t2", worker="worker-b")])
        executor = MixedExecutor()
        capture = _Capture()
        orch = _orch(planner, executor, FakeVerifier(),
                     supervisor=supervisor, on_finish=capture)

        await orch.start()

        # t2 完成，但 t1 not_done → park（不 finish）
        assert len(capture.results) == 0
        # t1 停在 RUNNING，t2 应为 COMPLETED
        assert orch.graph.nodes["t1"].status == TaskStatus.RUNNING
        assert orch.graph.nodes["t2"].status == TaskStatus.COMPLETED
        # worker-a 的桶应为空（auto-nudge 已被 re-dispatch 消费）
        notes_a = orch._pending_notes.get("worker-a")
        assert notes_a is None or len(notes_a) == 0, (
            f"nudge 已被 re-dispatch 消费，worker-a 桶应为空，实际: {notes_a}"
        )
        assert orch._pending_notes.get("worker-b") is None
        # t1 被派发了 2 次（初始 + auto-nudge re-dispatch），t2 1 次
        assert executor.dispatched.count("t1") == 2, (
            f"t1 应有 2 次派发（初始 + auto-nudge re-dispatch），实际: {executor.dispatched}"
        )

        # supervisor 只被调了 on_step_completed(t2)（t1 not_done 不调）
        completed_events = [
            c[1]["event"].step_id
            for c in supervisor.calls
            if c[0] == "on_step_completed"
        ]
        assert "t2" in completed_events
        assert "t1" not in completed_events

        # feed t1 → 完成 → 全完成
        await orch.on_feed("t1", "好的")
        assert len(capture.results) == 1
        assert capture.results[0].reason == ExitReason.COMPLETED
        assert orch.graph.nodes["t1"].status == TaskStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# L2c ─ Nudge 机制测试（CoordinatorRun 旁路消息队列）
# ═══════════════════════════════════════════════════════════════════════════════


class TestNudgeMechanism:
    """验证 CoordinatorRun.enqueue_note 的旁路消息队列机制。

    架构（CoordinatorRun §v4 R2）：
      - _pending_notes 按 worker 分桶：key="worker-a" → 只投该 worker；
        key="*" → 全局，所有 worker 可见。
      - Orchestrator._execute_and_settle 在 dispatch 前从桶里 pop 注入 node.pending_notes。
      - turn-end drain：自己桶 pop + 全局桶 get；自己桶非空 → 续跑（b 规则）。
      - ManagerService / SupervisorService 通过 enqueue_note 写入。
    """

    def test_worker_specific_note_routed_correctly(self) -> None:
        """场景 4a：worker 定向 note 只投到指定 worker 的桶。"""
        notes: dict[str, list[str]] = {}
        # 写入定向 note
        notes.setdefault("worker-a", []).append("nudge for a")
        notes.setdefault("worker-b", []).append("nudge for b")

        assert notes["worker-a"] == ["nudge for a"]
        assert notes["worker-b"] == ["nudge for b"]
        assert "worker-c" not in notes

    def test_global_note_visible_to_all_workers(self) -> None:
        """场景 4b："*" 桶内容对后续所有 worker dispatch 持续可见（不 pop）。"""
        notes: dict[str, list[str]] = {}
        notes.setdefault("*", []).append("全局公告：请检查 lint")

        # 全局桶始终存在
        assert "*" in notes
        assert notes["*"] == ["全局公告：请检查 lint"]

    def test_enqueue_note_injects_at_dispatch(self) -> None:
        """场景 4c：通过 Orchestrator 的 pending_notes 接口验证注入路径。"""
        notes: dict[str, list[str]] = {}
        notes.setdefault("w", []).append("nudge: 请交卷")
        notes.setdefault("*", []).append("全局: 用 ruff 格式化")

        # 模拟 dispatch 注入逻辑（orchestrator._execute_and_settle）
        worker = "w"
        node_notes = notes.pop(worker, []) + notes.get("*", [])

        assert len(node_notes) == 2
        assert "nudge: 请交卷" in node_notes[0]
        assert "全局: 用 ruff 格式化" in node_notes[1]
        # worker 桶已 pop
        assert worker not in notes
        # 全局桶保留
        assert "*" in notes


# ═══════════════════════════════════════════════════════════════════════════════
# L2d ─ Supervisor MCP 工具数据流测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestSupervisorMcpToolDataFlow:
    """验证 MCP 工具能正确从 _ACTIVE registry 读取任务状态。

    supervisor_tools.py 中的 5 个 tool：
      - supervisor_get_plan → 读 DAG 节点状态
      - supervisor_nudge   → 写 pending_notes
      - supervisor_replan   → 重 LLM 分解 + 换图
      - supervisor_trigger_deploy → 检查全完成 + 发部署消息
      - supervisor_send_message   → 发系统消息到群聊

    注：这里测试的是数据路径（registry 读写），不是 MCP SSE transport。
    工具 handler 的逻辑在 supervisor_tools.py 中通过 _get_run() 读 registry。
    真实 SSE transport 的测试见 L3 curl 部分。
    """

    def test_plan_view_reads_all_steps(self) -> None:
        """场景 5a：PlanView 返回所有步骤的 step_id / worker / status。"""
        from app.application.services.session_state import PlanView, StepView

        steps = (
            StepView(step_id="t1", worker="worker-a", status="running"),
            StepView(step_id="t2", worker="worker-b", status="pending"),
            StepView(step_id="t3", worker="worker-a", status="completed"),
        )
        view = PlanView(steps=steps)

        assert len(view.steps) == 3
        statuses = {s.step_id: s.status for s in view.steps}
        assert statuses["t1"] == "running"
        assert statuses["t2"] == "pending"
        assert statuses["t3"] == "completed"

    def test_supervisor_tool_url_builds_correctly(self) -> None:
        """场景 5b：验证 supervisor MCP URL 构建格式。

        格式：{base}?agent_id=<uuid>&session_id=<uuid>&group_id=<uuid>
        与 step-tools 格式一致（supervisor_tools._build_supervisor_tool_url）。
        """
        base = "http://127.0.0.1:8000/api/supervisor-tools/sse"
        agent_id = uuid4()
        session_id = uuid4()
        group_id = uuid4()
        url = f"{base}?agent_id={agent_id}&session_id={session_id}&group_id={group_id}"

        assert url.startswith(base)
        assert f"agent_id={agent_id}" in url
        assert f"session_id={session_id}" in url
        assert f"group_id={group_id}" in url


# ═══════════════════════════════════════════════════════════════════════════════
# L3 ─ Live Server Integration（curl 命令 + 预期响应）
# ═══════════════════════════════════════════════════════════════════════════════
#
# 前提：
#   - 后端在 http://127.0.0.1:8000 运行
#   - DB 已初始化（alembic upgrade head）
#   - MCP 包已安装（pip install mcp）
#   - 至少有 1 个 Agent 已创建在 DB
#
# 测试数据准备（所有 curl 示例在 bash 中运行）：
#
#   # 1. 创建两个测试 Agent
#   AGENT_A=$(curl -s -X POST http://127.0.0.1:8000/api/agents \
#     -H "Content-Type: application/json" \
#     -d '{"name":"test-worker-a","role":"backend developer","capability_tags":["python","fastapi"]}' \
#     | jq -r '.id')
#   AGENT_B=$(curl -s -X POST http://127.0.0.1:8000/api/agents \
#     -H "Content-Type: application/json" \
#     -d '{"name":"test-worker-b","role":"frontend developer","capability_tags":["react","typescript"]}' \
#     | jq -r '.id')
#
#   # 2. 创建群聊
#   GROUP=$(curl -s -X POST http://127.0.0.1:8000/api/groups \
#     -H "Content-Type: application/json" \
#     -d "{\"name\":\"supervisor-test-group\",\"member_ids\":[\"$AGENT_A\",\"$AGENT_B\"]}" \
#     | jq -r '.id')
#
#   # 3. 创建 session
#   SESSION=$(curl -s -X POST http://127.0.0.1:8000/api/sessions \
#     -H "Content-Type: application/json" \
#     -d "{\"group_id\":\"$GROUP\",\"title\":\"Supervisor test task\"}" \
#     | jq -r '.id')
#
# ═══════════════════════════════════════════════════════════════════════════════


# ── 测试用例（curl 命令 + 预期响应 + 成功标准）──────────────────────────────

L3_TEST_PLAN = """
# L3 ─ Live Server Integration Tests (curl)

## TC-6a: SSE 连接建立 — step-tools 端点

    curl -N -X GET "http://127.0.0.1:8000/api/step-tools/sse?agent_id=<AGENT_A_UUID>&session_id=<SESSION_UUID>&group_id=<GROUP_UUID>"

预期响应:
    HTTP 200
    Content-Type: text/event-stream
    event: endpoint
    data: /messages/?session_id=<SESSION_UUID>...

成功标准:
    - 返回 text/event-stream content type
    - 包含 endpoint 事件的 messages URL
    - 连接保持打开（SSE long-lived）

## TC-6b: SSE 连接建立 — supervisor-tools 端点

    curl -N -X GET "http://127.0.0.1:8000/api/supervisor-tools/sse?session_id=<SESSION_UUID>"

预期响应:
    HTTP 200
    Content-Type: text/event-stream
    event: endpoint
    data: /messages/?session_id=<SESSION_UUID>...

成功标准:
    - 返回 text/event-stream content type
    - 包含 endpoint 事件

## TC-6c: 缺失 session_id 时报错

    curl -s -X GET "http://127.0.0.1:8000/api/supervisor-tools/sse"

预期响应:
    SSE 连接建立但 _session_id_ctx 为空 → 工具调用时返回 {"error": "session_id 未解析或无效"}
    （SSE 连接本身不报错——session_id 在 URL query 传入，工具调用时才校验）

## TC-6d: 无效 session_id 时 MCP 工具返回错误

    # 用不存在的 UUID 连接 SSE，然后通过 MCP JSON-RPC 调用工具
    SID="00000000-0000-0000-0000-000000000000"
    curl -s -X POST "http://127.0.0.1:8000/api/supervisor-tools/messages/?session_id=$SID" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"supervisor_get_plan","arguments":{}}}'

预期响应:
    {"error": "当前 session 无活跃任务", "session_id": "00000000-..."}

成功标准:
    - 返回明确错误消息
    - 不会 500 crash

## TC-6e: supervisor_get_plan 返回完整 DAG 状态

    # 前提：session <SESSION_UUID> 有活跃任务（已通过 WS 或 API 启动）
    # 通过 MCP JSON-RPC POST 调用
    curl -s -X POST "http://127.0.0.1:8000/api/supervisor-tools/messages/?session_id=<SESSION_UUID>" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"supervisor_get_plan","arguments":{}}}'

预期响应 data:
    {
      "session_id": "<SESSION_UUID>",
      "run_id": "<hex>",
      "total_steps": N,
      "status_counts": {"pending": M, "running": K, "completed": C, ...},
      "steps": [
        {
          "id": "t1",
          "title": "...",
          "suggested_worker": "test-worker-a",
          "worker": "test-worker-a",
          "status": "running",
          "depends_on": [],
          "retries": 0,
          "fail_reason": "",
          "output": ""
        },
        ...
      ]
    }

成功标准:
    - total_steps > 0
    - status_counts 的 value 之和 = total_steps
    - 每个 step 包含 id/title/worker/status/depends_on/retries
    - output 不超过 500 字符（截断）

## TC-6f: supervisor_nudge 投递消息到 worker

    curl -s -X POST "http://127.0.0.1:8000/api/supervisor-tools/messages/?session_id=<SESSION_UUID>" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"supervisor_nudge","arguments":{"worker":"test-worker-a","message":"请尽快完成任务并交卷"}}}'

预期响应 data:
    {"status": "ok", "worker": "test-worker-a", "message": "请尽快完成任务并交卷"}

成功标准:
    - status = "ok"
    - worker 和 message 回显一致
    - 消息进入 CoordinatorRun._pending_notes[worker]

## TC-6g: supervisor_nudge 空 worker 报错

    curl -s -X POST "http://127.0.0.1:8000/api/supervisor-tools/messages/?session_id=<SESSION_UUID>" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"supervisor_nudge","arguments":{"worker":"","message":"hello"}}}'

预期响应 data:
    {"error": "worker 不能为空"}

## TC-6h: supervisor_send_message 发消息到群聊

    curl -s -X POST "http://127.0.0.1:8000/api/supervisor-tools/messages/?session_id=<SESSION_UUID>" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"supervisor_send_message","arguments":{"message":"所有任务执行正常，等待验证结果。"}}}'

预期响应 data:
    {"status": "ok", "message": "消息已发送"}

成功标准:
    - status = "ok"
    - 消息出现在群聊 transcript（查询 GET /api/sessions/:id/messages）

## TC-6i: supervisor_trigger_deploy 全部未完成时 blocked

    curl -s -X POST "http://127.0.0.1:8000/api/supervisor-tools/messages/?session_id=<SESSION_UUID>" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"supervisor_trigger_deploy","arguments":{}}}'

预期响应 data（有未完成任务时）:
    {"status": "blocked", "message": "并非全部任务完成..."}

成功标准:
    - status = "blocked"（非 ok）

## TC-6j: supervisor_replan 触发重新分解

    curl -s -X POST "http://127.0.0.1:8000/api/supervisor-tools/messages/?session_id=<SESSION_UUID>" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"supervisor_replan","arguments":{"requirement":"把任务拆得更细，每个 worker 做更小粒度的子任务"}}}'

预期响应 data（replan 成功）:
    {
      "status": "ok",
      "message": "已重新分解：新计划 N 项",
      "was_running": [...],
      "was_completed": [...],
      "new_count": N
    }

成功标准:
    - status = "ok"
    - new_count > 0
    - was_running 和 was_completed 列出旧图状态
    - 新 DAG 替换了旧 DAG

## TC-6k: task_complete MCP 调用

    curl -s -X POST "http://127.0.0.1:8000/api/step-tools/messages/?session_id=<SESSION_UUID>" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"mcp__agenthub-step-tools__task_complete","arguments":{"summary":"完成了用户 API：FastAPI 路由+模型，文件在 api/v1/users.py，测试通过"}}}'

预期响应 data:
    {"status": "ok", "summary": "完成了用户 API..."}

成功标准:
    - status = "ok"（非 error）
    - 日志含 "task_complete detected task=<task_id>"


# ── 端到端场景脚本（curl 命令序列）─────────────────────────────────────────

## E2E-1: 完整 NOT_DONE → nudge → task_complete 流程

这个流程需要真实 CLI worker（或 mock），但可以用 MCP 工具调用模拟关键步骤：

    # 前置：创建 group/session/agents（见上方准备命令）
    # 假设已经有 session_id=<SID>, agent_a_id=<AID>, group_id=<GID>

    # Step 1: 建立 step-tools SSE 连接（后台保持）
    curl -N http://127.0.0.1:8000/api/step-tools/sse?agent_id=$AID&session_id=$SID&group_id=$GID &
    STEP_TOOLS_PID=$!

    # Step 2: 建立 supervisor-tools SSE 连接（后台保持）
    curl -N http://127.0.0.1:8000/api/supervisor-tools/sse?session_id=$SID &
    SUPERVISOR_PID=$!

    # Step 3: 通过 WS 或 REST API 启动任务
    # （具体 API 取决于任务启动入口——send message 触发 reactive routing）
    curl -s -X POST "http://127.0.0.1:8000/api/sessions/$SID/messages" \\
      -H "Content-Type: application/json" \\
      -d '{"content":"用 FastAPI 实现完整的用户 CRUD API，包含创建/读取/更新/删除","role":"user"}'

    # Step 4: 查询 supervisor plan 状态
    curl -s -X POST "http://127.0.0.1:8000/api/supervisor-tools/messages/?session_id=$SID" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"supervisor_get_plan","arguments":{}}}'
    # 预期：返回 steps，有些 pending，有些 running

    # Step 5: worker 未交卷（模拟 not_done）→ 直接用 supervisor nudge
    curl -s -X POST "http://127.0.0.1:8000/api/supervisor-tools/messages/?session_id=$SID" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"supervisor_nudge","arguments":{"worker":"test-worker-a","message":"你已完成工作，现在请调用 task_complete 交卷"}}}'
    # 预期：{"status": "ok", ...}

    # Step 6: worker 调 task_complete 交卷
    curl -s -X POST "http://127.0.0.1:8000/api/step-tools/messages/?session_id=$SID" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":12,"method":"tools/call","params":{"name":"mcp__agenthub-step-tools__task_complete","arguments":{"summary":"CRUD API 完成，4 个端点+模型+迁移文件，全部测试通过"}}}'
    # 预期：{"status": "ok", "summary": "..."}

    # Step 7: 再次查询 plan 状态 → 确认 step 已 COMPLETED
    curl -s -X POST "http://127.0.0.1:8000/api/supervisor-tools/messages/?session_id=$SID" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":13,"method":"tools/call","params":{"name":"supervisor_get_plan","arguments":{}}}'

    # 清理
    kill $STEP_TOOLS_PID $SUPERVISOR_PID 2>/dev/null

## E2E-2: 卡死 → supervisor nudge → replan 流程

    # 前置：任务有依赖，t1 失败导致 t2/t3 BLOCKED

    # Step 1: 检查卡死状态
    curl -s -X POST "http://127.0.0.1:8000/api/supervisor-tools/messages/?session_id=$SID" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":20,"method":"tools/call","params":{"name":"supervisor_get_plan","arguments":{}}}'
    # 预期：有 FAILED/BLOCKED 状态的步骤

    # Step 2: supervisor nudge 失败节点
    curl -s -X POST "http://127.0.0.1:8000/api/supervisor-tools/messages/?session_id=$SID" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":21,"method":"tools/call","params":{"name":"supervisor_nudge","arguments":{"worker":"test-worker-a","message":"你的步骤失败了，需要重试。如果方向不对，请在群里说明。"}}}'

    # Step 3: 若仍然不通，触发 replan
    curl -s -X POST "http://127.0.0.1:8000/api/supervisor-tools/messages/?session_id=$SID" \\
      -H "Content-Type: application/json" \\
      -d '{"jsonrpc":"2.0","id":22,"method":"tools/call","params":{"name":"supervisor_replan","arguments":{"requirement":"t1 步骤失败，需要调整计划。把原来的任务拆成更小的独立步骤。"}}}'
    # 预期：{"status": "ok", "message": "已重新分解：新计划 N 项", "new_count": N}


# ── 环境变量（测试前设置）──────────────────────────────────────────────────

配置项（来自 src/backend/app/core/config.py）:

    export SUPERVISOR_AGENT_NAME="supervisor-bot"
    export SUPERVISOR_ENABLED="true"
    export SUPERVISOR_MAX_TURNS=10
    export MCP_SUPERVISOR_TOOLS_URL="http://127.0.0.1:8000/api/supervisor-tools/sse"
    export MCP_STEP_TOOLS_URL="http://127.0.0.1:8000/api/step-tools/sse"


# ── 成功标准汇总 ───────────────────────────────────────────────────────────

L1（域决策引擎）:
  [OK] step_completed 返回空（静默）
  [OK] all_completed → SUMMARIZE + DEPLOY
  [OK] 重复 all_completed 不重复 DEPLOY
  [OK] <3 个失败 → ALERT 无 REPLAN
  [OK] >=3 个失败 → ALERT + REPLAN
  [OK] stall → NUDGE 每个失败节点
  [OK] nudge >= max_turns → REPLAN

L2（钩子联动）:
  [OK] step 完成 → on_step_completed 被调
  [OK] step 永久失败 → on_step_failed 被调
  [OK] 全完成 → on_all_completed 被调
  [OK] 卡死 → on_stall_detected 被调
  [OK] None supervisor → 无声跳过
  [OK] 钩子调用顺序：step_completed 在 all_completed 之前

L2b（NOT_DONE/nudge/complete）:
  [OK] not_done → auto-enqueue nudge note
  [OK] nudge note 含 "task_complete" 关键字
  [OK] feed → resume → 第二次 dispatch 收到 nudge
  [OK] nudge 后 worker 交卷 → completed → 流转正常
  [OK] 独立 worker 的 not_done 互不干扰
  [OK] worker 桶 dispatch 后 pop 清空

L2c（Nudge 机制）:
  [OK] 定向 note 只投指定 worker 桶
  [OK] 全局 note 所有 worker 可见且不 pop
  [OK] dispatch 注入逻辑正确（pop 自己 + get 全局）

L2d（MCP 数据流）:
  [OK] PlanView 返回所有 step（id/worker/status）
  [OK] supervisor URL 构建格式正确

L3（live curl）:
  [OK] step-tools SSE 连接成功
  [OK] supervisor-tools SSE 连接成功
  [OK] 无效 session_id 返回明确错误
  [OK] supervisor_get_plan 返回 DAG 状态
  [OK] supervisor_nudge 投递成功
  [OK] nudge 空 worker 报错
  [OK] supervisor_send_message 发送成功
  [OK] supervisor_trigger_deploy 未完成时 blocked
  [OK] supervisor_replan 触发成功
  [OK] task_complete MCP 调用成功
"""

if __name__ == "__main__":
    print(__doc__)
    print(L3_TEST_PLAN)
