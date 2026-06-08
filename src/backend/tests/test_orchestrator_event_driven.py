"""Orchestrator 事件驱动控制流测试（R0+R1）.

验证 v4 事件驱动架构替换 v3 轮询循环的核心契约：
- 串行驱动：_drive 派一个→settle→下一个，无 ready 时 break（park）
- park 不释放 run：_check_terminal 只在全完成时调 _finish
- on_feed 续跑：外部 feed → resume 节点 → 续驱链条
- 卡死通报不释放：FAILED 挡死下游 → 通报群聊，run 留存
R1 适配：not_done 替代 waiting/needs_reprompt，删 PAUSED/AskInfo。
"""

import asyncio

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
    """Async _on_finish callback：捕获 RunResult 供测试断言。"""

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


# ── R0.1: 线性全完成 ──


@pytest.mark.asyncio
async def test_linear_all_complete():
    """start → t1 完成 → t2 完成 → _finish(COMPLETED) → run 释放"""
    planner = FakePlanner([_t("t1"), _t("t2", deps=["t1"])])
    executor = FakeExecutor()
    verifier = FakeVerifier()
    capture = _Capture()

    orch = _orch(planner, executor, verifier, on_finish=capture)
    await orch.start()

    assert len(capture.results) == 1
    assert capture.results[0].reason == ExitReason.COMPLETED
    assert all(n.status == TaskStatus.COMPLETED for n in orch.graph.nodes.values())
    assert executor.dispatched == ["t1", "t2"]


# ── R0.2: not_done 挂起（park）──


@pytest.mark.asyncio
async def test_not_done_parks_without_finish():
    """worker 未调 task_complete → not_done → RUNNING 不动 → _drive break → _finish 不调 → run 留存"""
    capture = _Capture()

    class NotDoneOnceExecutor:
        def __init__(self) -> None:
            self.dispatched: list[str] = []

        async def run(self, node):
            self.dispatched.append(node.task.id)
            if node.pending_answer is None:
                # v4 R1: worker 流结束未交卷 → not_done（ok=True，不是失败）
                return WorkerOutcome(ok=True, status="not_done", output="worker 还在想……")
            return WorkerOutcome(ok=True, status="completed", output="done")

    orch = _orch(
        FakePlanner([_t("t1")]), NotDoneOnceExecutor(), FakeVerifier(),
        on_finish=capture,
    )
    await orch.start()

    # 核心契约：park 不调 _finish（run 留存）
    assert len(capture.results) == 0
    assert orch.graph.nodes["t1"].status == TaskStatus.RUNNING  # v4: not_done 保持 RUNNING，不转 PAUSED
    # R0 删除 _waiting_node_key
    assert not hasattr(orch, "_waiting_node_key") or orch._waiting_node_key is None


# ── R0.3: feed 续跑 ──


@pytest.mark.asyncio
async def test_feed_resumes_parked_node_and_continues_chain():
    """park 后 on_feed → resume → 完成 → 续驱下游链条"""
    capture = _Capture()

    class NotDoneThenCompleteExecutor:
        """仅 t1 首次派发时 not_done，resume 后完成；其他节点直接完成。"""
        def __init__(self) -> None:
            self.dispatched: list[str] = []
            self.answers: list[str | None] = []

        async def run(self, node):
            self.dispatched.append(node.task.id)
            self.answers.append(node.pending_answer)
            # 只有 t1 首次派发时 not_done（worker 流结束未交卷）
            if node.task.id == "t1" and node.pending_answer is None:
                return WorkerOutcome(ok=True, status="not_done", output="worker 还在想……")
            return WorkerOutcome(ok=True, status="completed", output="done")

    executor = NotDoneThenCompleteExecutor()
    orch = _orch(
        FakePlanner([_t("t1"), _t("t2", deps=["t1"])]),
        executor, FakeVerifier(),
        on_finish=capture,
    )

    # start → t1 not_done → park（节点停在 RUNNING）
    await orch.start()
    assert len(capture.results) == 0
    assert orch.graph.nodes["t1"].status == TaskStatus.RUNNING

    # feed 回答 → resume t1 → 完成 → 续派 t2
    await orch.on_feed("t1", "Python")

    assert len(capture.results) == 1
    assert capture.results[0].reason == ExitReason.COMPLETED
    assert orch.graph.nodes["t1"].status == TaskStatus.COMPLETED
    assert orch.graph.nodes["t2"].status == TaskStatus.COMPLETED
    # t1 首派无答案 → not_done，resume 注入 "Python" → completed
    # t2 首派无答案（不需要交互）→ completed
    assert executor.answers[:2] == [None, "Python"]


# ── R0.4: 卡死通报 ──


@pytest.mark.asyncio
async def test_stall_reported_but_run_kept():
    """t1 永久 FAILED → t2 BLOCKED → 通报卡死 → _finish 不调"""
    capture = _Capture()
    events: list[tuple[str, dict]] = []

    async def sink(etype: str, payload: dict) -> None:
        events.append((etype, payload))

    planner = FakePlanner([_t("t1"), _t("t2", deps=["t1"])])
    verifier = FakeVerifier({"t1": Verdict(False, "永败")})

    orch = _orch(
        planner, FakeExecutor(), verifier,
        on_finish=capture,
        progress=sink,
    )
    await orch.start()

    # 卡死不 finish（run 留存等用户决策）
    assert len(capture.results) == 0
    assert orch.graph.nodes["t1"].status == TaskStatus.FAILED
    assert orch.graph.nodes["t2"].status == TaskStatus.BLOCKED
    # 通报进群聊
    texts = [p.get("content", "") for t, p in events if t == "text"]
    assert any("卡死" in txt for txt in texts)


# ── R0.5: 卡死后 feed 重试 ──


@pytest.mark.asyncio
async def test_feed_after_stall_retries_failed_node():
    """卡死后 on_feed 失败节点 → 手动重试 → 重跑"""
    capture = _Capture()
    call_count = 0

    class FailThenSucceedExecutor:
        def __init__(self) -> None:
            self.dispatched: list[str] = []

        async def run(self, node):
            nonlocal call_count
            self.dispatched.append(node.task.id)
            call_count += 1
            # MAX_RETRY=3 → 前 3 次 dispatch 失败（retry 耗尽），第 4 次（on_feed 手动重试）成功
            if call_count <= 3:
                return WorkerOutcome(ok=False, status="error", output="boom")
            return WorkerOutcome(ok=True, status="completed", output="终于好了")

    planner = FakePlanner([_t("t1"), _t("t2", deps=["t1"])])
    orch = _orch(
        planner, FailThenSucceedExecutor(), FakeVerifier(),
        on_finish=capture,
    )

    await orch.start()
    # t1 retry 耗尽 → FAILED，t2 BLOCKED → stall
    assert len(capture.results) == 0
    assert orch.graph.nodes["t1"].status == TaskStatus.FAILED

    # 用户 feed 失败节点 → 手动重试（FAILED→PENDING→_drive 重捡）
    await orch.on_feed("t1", "再试一次")

    # 这次 executor 返回 completed → t1 COMPLETED → t2 续派
    assert len(capture.results) == 1
    assert capture.results[0].reason == ExitReason.COMPLETED


# ── R0.6: 并发占位 ──


@pytest.mark.asyncio
async def test_max_concurrency_one():
    """max_concurrency=1 → 同时只有一个节点 RUNNING"""
    planner = FakePlanner([_t("t1"), _t("t2")])  # 两个独立任务
    running: list[str] = []

    class TrackingExecutor:
        def __init__(self) -> None:
            self.dispatched: list[str] = []

        async def run(self, node):
            self.dispatched.append(node.task.id)
            running.append(node.task.id)
            assert len(running) == 1, f"并发超限: {running}"
            await asyncio.sleep(0)  # yield event loop
            running.remove(node.task.id)
            return WorkerOutcome(ok=True, status="completed", output="ok")

    capture = _Capture()
    orch = _orch(
        planner, TrackingExecutor(), FakeVerifier(),
        on_finish=capture,
    )

    await orch.start()

    assert len(capture.results) == 1
    assert capture.results[0].reason == ExitReason.COMPLETED
    assert orch.graph.nodes["t1"].status == TaskStatus.COMPLETED
    assert orch.graph.nodes["t2"].status == TaskStatus.COMPLETED


# ── R0.7: progress sink 在事件驱动下的事件顺序 ──


@pytest.mark.asyncio
async def test_progress_events_event_driven():
    """事件驱动下 progress 事件顺序正确：plan → running/done → text/done"""
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
    # 末尾汇总 text + done
    assert types[-2:] == ["text", "done"]
    pairs = {(p["taskId"], p["status"]) for t, p in events if t == "task_update"}
    assert {("t1", "running"), ("t1", "done"), ("t2", "running"), ("t2", "done")} <= pairs
