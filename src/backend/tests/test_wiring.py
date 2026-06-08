"""Phase 5 接线 e2e — CoordinatorRun 后台运行 + registry（全 fake 链路）。

不碰 DB / 真 LLM / 真 CLI：用 tests/fakes.py 的 FakePlanner/Executor/Verifier 组 Orchestrator，
注入 fake 系统消息 sink。验证：跑到 COMPLETED → 汇总消息落 sink → registry 释放；
失败 → 错误消息；取消 → registry 释放；防重 reserve。
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.application.services.coordinator_run import (
    CoordinatorRegistry,
    CoordinatorRun,
)
from app.domain.enums import TaskStatus
from app.domain.task_engine.dag import TaskDef
from app.domain.task_engine.orchestrator import Orchestrator
from app.domain.task_engine.ports import PlanContext, Verdict, WorkerOutcome
from tests.fakes import FakeExecutor, FakePlanner, FakeVerifier


@pytest.fixture(autouse=True)
def _clear_registry():  # type: ignore[no-untyped-def]
    CoordinatorRegistry.clear()
    yield
    CoordinatorRegistry.clear()


def _task(tid: str, deps: list[str] | None = None) -> TaskDef:
    return TaskDef(
        id=tid,
        title=tid,
        description="",
        suggested_worker="w1",
        depends_on=deps or [],
        acceptance=[],
        no_verify=True,
    )


def _orchestrator(planner, executor, verifier) -> Orchestrator:  # type: ignore[no-untyped-def]
    ctx = PlanContext(task="t", workers=("w1",))
    return Orchestrator(planner=planner, executor=executor, verifier=verifier, ctx=ctx)


class _Sink:
    def __init__(self) -> None:
        self.messages: list[tuple] = []
        self.done = asyncio.Event()

    async def __call__(self, session_id, content) -> None:  # type: ignore[no-untyped-def]
        self.messages.append((session_id, content))
        self.done.set()


# ── happy path ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_to_completed_posts_summary_and_releases() -> None:
    planner = FakePlanner([_task("t1"), _task("t2", ["t1"])])
    orch = _orchestrator(planner, FakeExecutor(), FakeVerifier())
    reg, sink = CoordinatorRegistry(), _Sink()
    sid = uuid4()
    run = CoordinatorRun(session_id=sid)

    assert reg.try_reserve(sid, run) is True
    run.start(
        orch,
        on_done=lambda r: sink(sid, r.summary or str(r.reason)),
        on_error=lambda e: sink(sid, f"err: {e}"),
        registry=reg,
    )
    await asyncio.wait_for(sink.done.wait(), timeout=2)

    assert sink.messages[0][0] == sid
    assert "完成" in sink.messages[0][1]  # 机械 summary（B 方案）
    assert reg.get(sid) is None  # 释放


# ── 失败路径（v4：failure → stall → park，不调 on_done，不释放）──────


@pytest.mark.asyncio
async def test_run_failure_stalls_and_keeps_registry() -> None:
    """v4: verifier 永远 fail → retry 耗尽 → FAILED → stall → park。
    on_done 不调（只有 COMPLETED 才 finish），registry 保留等用户决策。"""
    planner = FakePlanner([_task("t1")])
    verifier = FakeVerifier({"t1": Verdict(False, "boom")})
    orch = _orchestrator(planner, FakeExecutor(), verifier)
    reg, sink = CoordinatorRegistry(), _Sink()
    sid = uuid4()
    run = CoordinatorRun(session_id=sid)
    reg.try_reserve(sid, run)
    run.start(
        orch,
        on_done=lambda r: sink(sid, str(r.reason)),
        on_error=lambda e: sink(sid, f"err: {e}"),
        registry=reg,
    )

    # 等 orchestrator 跑到 stall + park
    await asyncio.sleep(0.1)

    # v4: failure 不调 on_done（sink 不触发），registry 保留
    assert len(sink.messages) == 0
    assert orch.graph.nodes["t1"].status == TaskStatus.FAILED
    assert reg.get(sid) is not None  # run 留存，等用户决策

    # 用户取消 → 释放
    await run.cancel()
    await asyncio.sleep(0.05)
    assert reg.get(sid) is None


# ── 防重 ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reserve_rejects_second() -> None:
    reg = CoordinatorRegistry()
    sid = uuid4()
    assert reg.try_reserve(sid, CoordinatorRun(session_id=sid)) is True
    assert reg.try_reserve(sid, CoordinatorRun(session_id=sid)) is False


# ── 取消 ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_releases() -> None:
    # 用一个慢 executor 模拟在飞任务
    class _SlowExec(FakeExecutor):
        async def run(self, node):  # type: ignore[no-untyped-def]
            await asyncio.sleep(5)
            return WorkerOutcome(ok=True)

    planner = FakePlanner([_task("t1")])
    orch = _orchestrator(planner, _SlowExec(), FakeVerifier())
    reg, sink = CoordinatorRegistry(), _Sink()
    sid = uuid4()
    run = CoordinatorRun(session_id=sid)
    reg.try_reserve(sid, run)
    run.start(
        orch,
        on_done=lambda r: sink(sid, "done"),
        on_error=lambda e: sink(sid, "err"),
        registry=reg,
    )
    await asyncio.sleep(0.05)  # 让任务进入 executor.run 的 sleep
    await run.cancel()
    await asyncio.sleep(0.05)  # 让 finally 跑完
    assert reg.get(sid) is None  # 取消后释放


# ── WS 带外推送：进度 sink 广播 ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ws_progress_sink_broadcasts(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """make_ws_progress_sink 把进度包成 StreamEvent JSON，经 ws_manager 广播到 session。"""
    from app.application.services import coordinator_run as cr

    captured: list[tuple] = []

    async def fake_broadcast(session_id, payload):  # type: ignore[no-untyped-def]
        captured.append((session_id, payload))

    monkeypatch.setattr(cr.ws_manager, "broadcast", fake_broadcast)

    sid, coord = uuid4(), uuid4()
    worker_ids = {"DocWriter": "agent-id-123"}  # 名 → id
    sink = cr.make_ws_progress_sink(sid, coord, worker_ids)
    await sink("task_plan", {"plan": {"steps": [{"id": "t1", "who": "DocWriter", "label": "写"}]}})
    await sink("task_update", {"taskId": "t1", "title": "x", "status": "running"})
    await sink("text", {"content": "汇总"})

    assert [c[0] for c in captured] == [sid, sid, sid]            # 都广播到该 session
    p_plan, p_upd, p_txt = (c[1] for c in captured)
    assert p_plan["type"] == "task_plan"
    assert p_plan["sender_agent_id"] == str(coord)               # sender = 协调者
    # step.who 翻译成 agent id（前端 lookupActor 按 id 查），不是名字
    assert p_plan["metadata"]["plan"]["steps"][0]["who"] == "agent-id-123"
    assert p_upd["type"] == "task_update" and p_upd["metadata"]["taskId"] == "t1"
    assert p_txt["type"] == "text" and p_txt["content"] == "汇总"  # 末尾汇总走 content


@pytest.mark.asyncio
async def test_ws_progress_sink_unknown_worker_keeps_name(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """worker 名不在映射里（如 Planner 拼错）→ 保留原值，不崩，前端走 fallback。"""
    from app.application.services import coordinator_run as cr

    captured: list[dict] = []

    async def fake_broadcast(session_id, payload):  # type: ignore[no-untyped-def]
        captured.append(payload)

    monkeypatch.setattr(cr.ws_manager, "broadcast", fake_broadcast)
    sink = cr.make_ws_progress_sink(uuid4(), uuid4(), {"Known": "id-1"})
    await sink("task_plan", {"plan": {"steps": [{"id": "t1", "who": "Unknown", "label": "x"}]}})
    assert captured[0]["metadata"]["plan"]["steps"][0]["who"] == "Unknown"
