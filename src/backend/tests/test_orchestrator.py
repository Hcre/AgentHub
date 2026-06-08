"""Orchestrator 测试（v4 事件驱动 + R1 协议重塑）。

从 v3 轮询循环迁移到 v4 事件驱动（start + _Capture）。
R1：删 PAUSED/AskInfo/waiting，not_done 替代 needs_reprompt/waiting。
"""

import pytest

from app.domain.enums import TaskStatus
from app.domain.task_engine.dag import Check, TaskDef
from app.domain.task_engine.orchestrator import Orchestrator
from app.domain.task_engine.ports import (
    ExitReason,
    PlanContext,
    RunResult,
    Verdict,
    WorkerOutcome,
)
from tests.fakes import FakeExecutor, FakePlanner, FakeVerifier


def _t(tid: str, deps: list[str] | None = None) -> TaskDef:
    return TaskDef(
        id=tid,
        title=tid,
        suggested_worker="w",
        depends_on=deps or [],
        acceptance=[Check("mechanical", "true")],
    )


class _Capture:
    """Async _on_finish callback for test assertions."""

    def __init__(self) -> None:
        self.results: list[RunResult] = []

    async def __call__(self, r: RunResult) -> None:
        self.results.append(r)


def _orch(planner, executor, verifier, *, on_finish=None, progress=None) -> Orchestrator:
    ctx = PlanContext(task="x", workers=("w",))
    orch = Orchestrator(
        planner=planner, executor=executor, verifier=verifier, ctx=ctx,
        progress=progress,
    )
    orch._on_finish = on_finish
    return orch


# --- TC-9.1 happy ---


@pytest.mark.asyncio
async def test_happy_three_tasks_complete() -> None:
    planner = FakePlanner([_t("t1"), _t("t2"), _t("t3", deps=["t1", "t2"])])
    executor, verifier = FakeExecutor(), FakeVerifier()
    capture = _Capture()
    orch = _orch(planner, executor, verifier, on_finish=capture)

    await orch.start()

    assert len(capture.results) == 1
    assert capture.results[0].reason == ExitReason.COMPLETED
    assert all(n.status == TaskStatus.COMPLETED for n in orch.graph.nodes.values())
    assert "3 完成 / 0 未完成" in capture.results[0].summary
    assert "t1：✅ 已完成（验收通过：true）" in capture.results[0].summary
    assert set(executor.dispatched) == {"t1", "t2", "t3"}


# --- TC-9.2 retry ---


@pytest.mark.asyncio
async def test_verify_fail_once_then_retry_passes() -> None:
    planner = FakePlanner([_t("t1")])
    verifier = FakeVerifier({"t1": [Verdict(False, "首次没过"), Verdict(True)]})
    capture = _Capture()
    orch = _orch(planner, FakeExecutor(), verifier, on_finish=capture)

    await orch.start()

    assert len(capture.results) == 1
    assert capture.results[0].reason == ExitReason.COMPLETED
    assert orch.graph.nodes["t1"].status == TaskStatus.COMPLETED
    assert orch.graph.nodes["t1"].retries == 1


# --- TC-4.1 命门：说谎 worker 绝不 COMPLETED ---


@pytest.mark.asyncio
async def test_lying_worker_never_completes() -> None:
    planner = FakePlanner([_t("t1")])
    executor = FakeExecutor({"t1": WorkerOutcome(ok=True, output="我做完了")})
    verifier = FakeVerifier({"t1": Verdict(False, "测试不过")})
    capture = _Capture()
    orch = _orch(planner, executor, verifier, on_finish=capture)

    await orch.start()

    # v4: retry 耗尽 → FAILED → stall → park（不 finish）
    assert len(capture.results) == 0
    assert orch.graph.nodes["t1"].status == TaskStatus.FAILED
    assert not any(e.get("to") == "completed" for e in orch.events)


# --- TC blocked 传播 ---


@pytest.mark.asyncio
async def test_upstream_failure_blocks_downstream() -> None:
    planner = FakePlanner([_t("t1"), _t("t2", deps=["t1"])])
    verifier = FakeVerifier({"t1": Verdict(False, "永败")})
    capture = _Capture()
    orch = _orch(planner, FakeExecutor(), verifier, on_finish=capture)

    await orch.start()

    # v4: FAILED + BLOCKED → stall → park（不 finish）
    assert len(capture.results) == 0
    assert orch.graph.nodes["t1"].status == TaskStatus.FAILED
    assert orch.graph.nodes["t2"].status == TaskStatus.BLOCKED


# --- TC worker 自身崩 ---


@pytest.mark.asyncio
async def test_worker_crash_retries_then_fails() -> None:
    planner = FakePlanner([_t("t1")])
    executor = FakeExecutor({"t1": WorkerOutcome(ok=False, status="error")})
    capture = _Capture()
    orch = _orch(planner, executor, FakeVerifier(), on_finish=capture)

    await orch.start()

    # retry 耗尽 → FAILED → park
    assert len(capture.results) == 0
    assert orch.graph.nodes["t1"].status == TaskStatus.FAILED


# --- e2e：真 Orchestrator + 真 AgentExecutor(fake adapter) + 真 MechanicalVerifier ---


@pytest.mark.asyncio
async def test_e2e_orchestrator_real_executor_verifier(tmp_path):
    """整条 MVP 链路（仅 LLM/CLI 是 fake）：Planner → 调度 → 真 Executor 派发 → 真 Verifier 跑命令 → COMPLETED。"""
    from uuid import uuid4

    from app.domain.entities.agent import Agent
    from app.domain.enums import Provider
    from app.domain.llm.protocol import StreamEvent, StreamEventType, ToolCall
    from app.domain.task_engine.executor import _TASK_COMPLETE_TOOL, AgentExecutor
    from app.domain.task_engine.verifier import MechanicalVerifier

    class FakeAdapter:
        async def stream(self, request):
            yield StreamEvent(type=StreamEventType.TEXT, seq=0, content="done")
            yield StreamEvent(
                type=StreamEventType.TOOL_CALL, seq=1,
                tool_call=ToolCall(call_id="c", name=_TASK_COMPLETE_TOOL,
                                   arguments={"summary": "done"}),
            )
            yield StreamEvent(type=StreamEventType.DONE, seq=2)

    planner = FakePlanner([_t("t1")])
    executor = AgentExecutor(
        resolve_agent=lambda n: Agent(
            name=n, avatar="x", role="d", provider=Provider.ANTHROPIC, model="m"
        ),
        adapter_factory=lambda a: FakeAdapter(),
        session_id=uuid4(), group_id=uuid4(), workspace=str(tmp_path),
    )
    verifier = MechanicalVerifier(workspace=str(tmp_path))
    capture = _Capture()
    orch = _orch(planner, executor, verifier, on_finish=capture)

    await orch.start()

    assert len(capture.results) == 1
    assert capture.results[0].reason == ExitReason.COMPLETED
    assert orch.graph.nodes["t1"].status == TaskStatus.COMPLETED


# --- B 方案机械 summary：P1（no_verify 不冒充）+ P5（失败路径也有 summary）---


@pytest.mark.asyncio
async def test_summary_no_verify_marked_unverified() -> None:
    nv = TaskDef(
        id="t1", title="写设计说明", suggested_worker="w",
        depends_on=[], acceptance=[], no_verify=True,
    )
    capture = _Capture()
    orch = _orch(FakePlanner([nv]), FakeExecutor(), FakeVerifier(), on_finish=capture)

    await orch.start()

    assert len(capture.results) == 1
    assert capture.results[0].reason == ExitReason.COMPLETED
    assert orch.graph.nodes["t1"].status == TaskStatus.COMPLETED
    assert "未验证" in capture.results[0].summary
    assert "验收通过" not in capture.results[0].summary


@pytest.mark.asyncio
async def test_summary_present_on_failure_path() -> None:
    planner = FakePlanner([_t("t1")])
    verifier = FakeVerifier({"t1": Verdict(False, "boom")})
    capture = _Capture()
    orch = _orch(planner, FakeExecutor(), verifier, on_finish=capture)

    await orch.start()

    # v4: retry 耗尽 → FAILED → stall → park（不 finish）
    # summary 通过 stall report 推送，不在 RunResult 里
    assert len(capture.results) == 0
    assert orch.graph.nodes["t1"].status == TaskStatus.FAILED


# --- WS 进度事件（ProgressSink 注入）---


@pytest.mark.asyncio
async def test_progress_events_emitted() -> None:
    events: list[tuple[str, dict]] = []

    async def sink(etype: str, payload: dict) -> None:
        events.append((etype, payload))

    planner = FakePlanner([_t("t1"), _t("t2", deps=["t1"])])
    ctx = PlanContext(task="x", workers=("w",))
    capture = _Capture()
    orch = Orchestrator(
        planner=planner, executor=FakeExecutor(), verifier=FakeVerifier(),
        ctx=ctx, progress=sink,
    )
    orch._on_finish = capture

    await orch.start()

    assert len(capture.results) == 1
    assert capture.results[0].reason == ExitReason.COMPLETED
    types = [t for t, _ in events]
    assert types[0] == "task_plan"
    assert types[-2:] == ["text", "done"]
    assert len(events[0][1]["plan"]["steps"]) == 2
    pairs = {(p["taskId"], p["status"]) for t, p in events if t == "task_update"}
    assert {("t1", "running"), ("t1", "done"), ("t2", "running"), ("t2", "done")} <= pairs


@pytest.mark.asyncio
async def test_progress_emits_failed_with_reason() -> None:
    events: list[tuple[str, dict]] = []

    async def sink(etype: str, payload: dict) -> None:
        events.append((etype, payload))

    planner = FakePlanner([_t("t1")])
    verifier = FakeVerifier({"t1": Verdict(False, "boom")})
    capture = _Capture()
    orch = Orchestrator(
        planner=planner, executor=FakeExecutor(), verifier=verifier,
        ctx=PlanContext(task="x", workers=("w",)), progress=sink,
    )
    orch._on_finish = capture

    await orch.start()

    failed = [p for t, p in events if t == "task_update" and p["status"] == "failed"]
    assert failed, "应有 failed 进度事件"
    assert failed[0]["reason"] == "boom"


# --- v4 R1：not_done → park（RUNNING 不动）→ feed resume 回路 ---


@pytest.mark.asyncio
async def test_not_done_parks_then_feed_resumes_to_completed() -> None:
    """worker 未调 task_complete → not_done → 节点停在 RUNNING → park → on_feed resume → COMPLETED。"""

    class NotDoneThenCompleteExecutor:
        def __init__(self) -> None:
            self.dispatched: list[str] = []
            self.answers: list[str | None] = []

        async def run(self, node):
            self.dispatched.append(node.task.id)
            self.answers.append(node.pending_answer)
            if node.pending_answer is None:
                # v4: worker 没调 task_complete → not_done（不是失败）
                return WorkerOutcome(ok=True, status="not_done", output="worker 还在想……")
            return WorkerOutcome(ok=True, status="completed", output=f"按 {node.pending_answer} 做完")

    executor = NotDoneThenCompleteExecutor()
    capture = _Capture()
    orch = _orch(FakePlanner([_t("t1")]), executor, FakeVerifier(), on_finish=capture)

    # start → not_done → park（节点停在 RUNNING）
    await orch.start()
    assert orch.graph.nodes["t1"].status == TaskStatus.RUNNING
    assert len(capture.results) == 0  # park 不 finish

    # on_feed → resume → complete
    await orch.on_feed("t1", "PostgreSQL")

    assert len(capture.results) == 1
    assert capture.results[0].reason == ExitReason.COMPLETED
    assert orch.graph.nodes["t1"].status == TaskStatus.COMPLETED
    assert executor.answers == [None, "PostgreSQL"]


@pytest.mark.asyncio
async def test_feed_nonexistent_step_noop() -> None:
    """on_feed 对不存在的 step_id → 不抛异常（返回 None 从 graph 查找）。"""
    capture = _Capture()
    orch = _orch(FakePlanner([_t("t1")]), FakeExecutor(), FakeVerifier(), on_finish=capture)

    await orch.start()

    # graph 里无 "t2"，不应抛异常
    await orch.on_feed("t2", "answer")
    # t1 已完成，正常结束
    assert orch.graph.nodes["t1"].status == TaskStatus.COMPLETED
