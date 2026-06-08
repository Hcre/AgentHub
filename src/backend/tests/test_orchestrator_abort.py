"""中断（abort）测试：杀在飞 worker → 节点强制 park（可续）+ 通报。"""

from __future__ import annotations

import asyncio

import pytest

from app.domain.enums import TaskStatus
from app.domain.task_engine.dag import Check, TaskDef
from app.domain.task_engine.orchestrator import Orchestrator
from app.domain.task_engine.ports import PlanContext, RunResult, WorkerOutcome
from tests.fakes import FakePlanner, FakeVerifier


def _t(tid: str, deps: list[str] | None = None) -> TaskDef:
    return TaskDef(id=tid, title=tid, suggested_worker="w",
                   depends_on=deps or [], acceptance=[Check("mechanical", "true")])


class _Capture:
    def __init__(self) -> None:
        self.results: list[RunResult] = []

    async def __call__(self, r: RunResult) -> None:
        self.results.append(r)


class _MsgSink:
    def __init__(self) -> None:
        self.posts: list[str] = []

    async def __call__(self, content: str) -> None:
        self.posts.append(content)


class _BlockingExecutor:
    """run() 阻塞直到 abort()；abort 杀进程语义 → 返回 not_done。summarize 返回复盘文本。"""

    def __init__(self, summary: str = "停在写 LoginForm，已建文件，还差样式；有半截 tsx 残留") -> None:
        self.dispatched: list[str] = []
        self.aborted: list[str] = []
        self._released = asyncio.Event()
        self._summary = summary

    async def run(self, node):  # type: ignore[no-untyped-def]
        self.dispatched.append(node.task.id)
        await self._released.wait()
        return WorkerOutcome(ok=True, status="not_done", output="被中断")

    async def abort(self, node_id: str) -> bool:
        self.aborted.append(node_id)
        self._released.set()
        return True

    async def summarize(self, node) -> str:  # type: ignore[no-untyped-def]
        return self._summary


def _orch(executor, *, sink=None) -> Orchestrator:
    orch = Orchestrator(
        planner=FakePlanner([_t("t1")]), executor=executor, verifier=FakeVerifier(),
        ctx=PlanContext(task="x", workers=("w",)), message_sink=sink,
    )
    orch._on_finish = _Capture()
    return orch


@pytest.mark.asyncio
async def test_abort_step_kills_inflight_and_parks() -> None:
    sink = _MsgSink()
    executor = _BlockingExecutor()
    orch = _orch(executor, sink=sink)

    start_task = asyncio.create_task(orch.start())
    # 等 worker 进入在飞
    for _ in range(200):
        if executor.dispatched:
            break
        await asyncio.sleep(0.005)

    ok = await orch.abort_step("t1")
    await asyncio.wait_for(start_task, timeout=2)

    assert ok is True
    assert executor.aborted == ["t1"]  # 杀了在飞 worker
    node = orch.graph.nodes["t1"]
    assert node.status == TaskStatus.RUNNING  # 强制 park（不是终态），可续
    assert node.aborted is True
    assert any("已中断" in p for p in sink.posts)
    # 复盘不静默：worker 汇报停在哪/做了啥/剩啥
    assert any("复盘" in p and "LoginForm" in p for p in sink.posts)


@pytest.mark.asyncio
async def test_abort_summary_fallback_when_worker_silent() -> None:
    """复盘为空（resume 失败/worker 没说）→ 机械兜底提示 git status，不完全静默。"""
    sink = _MsgSink()
    executor = _BlockingExecutor(summary="")  # 复盘空
    orch = _orch(executor, sink=sink)

    start_task = asyncio.create_task(orch.start())
    for _ in range(200):
        if executor.dispatched:
            break
        await asyncio.sleep(0.005)
    await orch.abort_step("t1")
    await asyncio.wait_for(start_task, timeout=2)

    assert any("git status" in p for p in sink.posts)


@pytest.mark.asyncio
async def test_abort_step_noop_when_not_inflight() -> None:
    """节点没在飞（executor.abort 返回 False）→ abort_step 返回 False，不通报。"""

    class NoInflightExecutor:
        async def run(self, node):  # type: ignore[no-untyped-def]
            return WorkerOutcome(ok=True, status="completed", output="done")

        async def abort(self, node_id: str) -> bool:
            return False

    sink = _MsgSink()
    orch = _orch(NoInflightExecutor(), sink=sink)
    await orch.start()  # t1 直接完成

    ok = await orch.abort_step("t1")
    assert ok is False
    assert not any("已中断" in p for p in sink.posts)


@pytest.mark.asyncio
async def test_abort_unknown_step_returns_false() -> None:
    orch = _orch(_BlockingExecutor())
    orch.graph = None
    assert await orch.abort_step("nope") is False
