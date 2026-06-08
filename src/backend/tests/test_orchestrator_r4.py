"""R4 测试：上游摘要注入 + 关键事件入 transcript（message_sink）+ turn-end drain。"""

from __future__ import annotations

import pytest

from app.domain.enums import TaskStatus
from app.domain.task_engine.dag import Check, TaskDef, TaskNode, build_graph
from app.domain.task_engine.executor import build_task_instruction
from app.domain.task_engine.orchestrator import Orchestrator, _collect_upstream_summaries
from app.domain.task_engine.ports import PlanContext, RunResult, Verdict, WorkerOutcome
from tests.fakes import FakeExecutor, FakePlanner, FakeVerifier


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


def _orch(planner, executor, verifier, *, sink=None, on_finish=None) -> Orchestrator:
    orch = Orchestrator(
        planner=planner, executor=executor, verifier=verifier,
        ctx=PlanContext(task="x", workers=("w",)), message_sink=sink,
    )
    orch._on_finish = on_finish
    return orch


# ── R4-1：上游摘要 ──


def test_build_instruction_injects_upstream_summary() -> None:
    node = TaskNode(task=_t("B", deps=["A"]))
    node.upstream_summaries = {"A": "FastAPI，端口 8000，接口见 api/v1/"}
    text = build_task_instruction(node)
    assert "## 上游任务完成摘要" in text
    assert "端口 8000" in text


def test_build_instruction_no_upstream_section_when_none() -> None:
    node = TaskNode(task=_t("A"))
    assert "上游任务完成摘要" not in build_task_instruction(node)


def test_collect_upstream_only_completed_with_output() -> None:
    graph = build_graph([_t("A"), _t("B", deps=["A"])], {"w"})
    b = graph.nodes["B"]
    # A 未完成 → None
    assert _collect_upstream_summaries(b, graph) is None
    # A COMPLETED + output → 收集
    graph.nodes["A"].status = TaskStatus.COMPLETED
    graph.nodes["A"].output = "done A"
    assert _collect_upstream_summaries(b, graph) == {"A": "done A"}


@pytest.mark.asyncio
async def test_upstream_summary_flows_to_dependent_worker() -> None:
    """A 完成后 B 派发时，node.upstream_summaries 被填上 A 的 output。"""
    seen: dict[str, dict | None] = {}

    class RecordingExecutor:
        def __init__(self) -> None:
            self.dispatched: list[str] = []

        async def run(self, node):
            self.dispatched.append(node.task.id)
            seen[node.task.id] = node.upstream_summaries
            return WorkerOutcome(ok=True, status="completed", output=f"{node.task.id} 产出")

    planner = FakePlanner([_t("A"), _t("B", deps=["A"])])
    orch = _orch(planner, RecordingExecutor(), FakeVerifier(), on_finish=_Capture())
    await orch.start()
    assert seen["A"] is None  # A 无上游
    assert seen["B"] == {"A": "A 产出"}  # B 看到 A 的 summary


# ── R4-2：关键事件入 transcript ──


@pytest.mark.asyncio
async def test_post_plan_and_step_done() -> None:
    sink = _MsgSink()
    orch = _orch(FakePlanner([_t("t1")]), FakeExecutor(), FakeVerifier(),
                 sink=sink, on_finish=_Capture())
    await orch.start()
    assert any("开始执行" in p for p in sink.posts)
    assert any("✅" in p and "已完成" in p for p in sink.posts)


@pytest.mark.asyncio
async def test_post_step_failed_only_on_permanent() -> None:
    """retry 期间不通报；retry 耗尽永久失败才 ❌。"""
    sink = _MsgSink()
    verifier = FakeVerifier({"t1": Verdict(False, "永败")})
    orch = _orch(FakePlanner([_t("t1")]), FakeExecutor(), verifier,
                 sink=sink, on_finish=_Capture())
    await orch.start()
    failed_posts = [p for p in sink.posts if "❌" in p]
    assert len(failed_posts) == 1  # 只在永久失败那一刻通报一次
    assert "重试 3 次不通过" in failed_posts[0]


@pytest.mark.asyncio
async def test_post_stall_to_transcript() -> None:
    sink = _MsgSink()
    verifier = FakeVerifier({"t1": Verdict(False, "永败")})
    orch = _orch(FakePlanner([_t("t1"), _t("t2", deps=["t1"])]), FakeExecutor(), verifier,
                 sink=sink, on_finish=_Capture())
    await orch.start()
    assert any("卡死" in p for p in sink.posts)


# ── turn-end drain（design §7.3）──


@pytest.mark.asyncio
async def test_turn_end_drain_reruns_on_pending_bucket() -> None:
    """worker 这轮跑完(即便 task_complete)、自己桶又有消息 → 续跑第二轮，桶空才结算。"""
    orch_ref: list[Orchestrator] = []

    class DrainExecutor:
        def __init__(self) -> None:
            self.calls = 0

        async def run(self, node):
            self.calls += 1
            if self.calls == 1:
                # 模拟执行期 relay：往自己桶塞一条
                orch_ref[0]._pending_notes.setdefault("w", []).append("注意改成 React")
                return WorkerOutcome(ok=True, status="completed", output="turn1")
            # 第二轮应看到注入的 note
            assert node.pending_notes == ["注意改成 React"]
            return WorkerOutcome(ok=True, status="completed", output="turn2")

    executor = DrainExecutor()
    capture = _Capture()
    orch = _orch(FakePlanner([_t("t1")]), executor, FakeVerifier(), on_finish=capture)
    orch_ref.append(orch)

    await orch.start()
    assert executor.calls == 2  # task_complete + 桶非空 → 续了第二轮
    assert orch.graph.nodes["t1"].status == TaskStatus.COMPLETED
    assert orch.graph.nodes["t1"].output == "turn2"  # 第二轮的产出
    assert orch._pending_notes.get("w") in (None, [])  # 桶已清空


@pytest.mark.asyncio
async def test_global_bucket_does_not_trigger_rerun() -> None:
    """全局桶 '*' 非空不触发续跑（只搭便车注入，不放大成 N 轮）。"""

    class GlobalNoteExecutor:
        def __init__(self) -> None:
            self.calls = 0
            self.orch: Orchestrator | None = None

        async def run(self, node):
            self.calls += 1
            if self.calls == 1 and self.orch is not None:
                self.orch._pending_notes.setdefault("*", []).append("全局约束")
            return WorkerOutcome(ok=True, status="completed", output="done")

    executor = GlobalNoteExecutor()
    orch = _orch(FakePlanner([_t("t1")]), executor, FakeVerifier(), on_finish=_Capture())
    executor.orch = orch
    await orch.start()
    assert executor.calls == 1  # 全局桶不触发续跑
