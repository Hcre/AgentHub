"""CoordinatorRun + SessionState R2 单元测试（路由统一）。

覆盖 R2 新增的纯内存逻辑（不起 DB / LLM）：
- plan_view() 从 Orchestrator.graph 投影 PlanView
- enqueue_note 按 worker 分桶（"*"=全局）
- orchestrator 消费 pending_notes：本 worker 桶一次性 pop，全局桶持续注入
- SessionState.from_session 工厂（fake message_repo）
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.application.services.coordinator_run import CoordinatorRun
from app.application.services.session_state import PlanView, SessionState, StepView
from app.domain.enums import TaskStatus
from app.domain.task_engine.dag import Check, TaskDef
from app.domain.task_engine.orchestrator import Orchestrator
from app.domain.task_engine.ports import PlanContext
from tests.fakes import FakeExecutor, FakePlanner, FakeVerifier


def _t(tid: str, worker: str = "w", deps: list[str] | None = None) -> TaskDef:
    return TaskDef(
        id=tid, title=tid, suggested_worker=worker,
        depends_on=deps or [], acceptance=[Check("mechanical", "true")],
    )


def _orch_with_graph(tasks: list[TaskDef], workers: tuple[str, ...]) -> Orchestrator:
    orch = Orchestrator(
        planner=FakePlanner(tasks), executor=FakeExecutor(), verifier=FakeVerifier(),
        ctx=PlanContext(task="x", workers=workers),
    )
    from app.domain.task_engine.dag import build_graph
    orch.graph = build_graph(tasks, set(workers))
    return orch


# ── plan_view ──


def test_plan_view_none_without_orchestrator() -> None:
    run = CoordinatorRun(session_id=uuid.uuid4())
    assert run.plan_view() is None


def test_plan_view_projects_graph() -> None:
    run = CoordinatorRun(session_id=uuid.uuid4())
    run._orchestrator = _orch_with_graph(
        [_t("t1", "前端"), _t("t2", "后端", deps=["t1"])], ("前端", "后端")
    )
    pv = run.plan_view()
    assert pv is not None
    assert {s.step_id for s in pv.steps} == {"t1", "t2"}
    by_id = {s.step_id: s for s in pv.steps}
    assert by_id["t1"].worker == "前端"
    assert by_id["t1"].status == TaskStatus.PENDING.value


# ── enqueue_note 分桶 ──


def test_enqueue_note_global_bucket() -> None:
    run = CoordinatorRun(session_id=uuid.uuid4())
    run.enqueue_note("错误提示用中文")
    assert run._pending_notes == {"*": ["错误提示用中文"]}


def test_enqueue_note_per_worker_bucket() -> None:
    run = CoordinatorRun(session_id=uuid.uuid4())
    run.enqueue_note("前端用 React", worker="前端小美")
    run.enqueue_note("再补一条", worker="前端小美")
    assert run._pending_notes == {"前端小美": ["前端用 React", "再补一条"]}


# ── orchestrator 消费分桶 ──


@pytest.mark.asyncio
async def test_orchestrator_consumes_worker_bucket_once_global_persists() -> None:
    """本 worker 桶 pop 一次性消费；全局桶持续注入后续 dispatch。"""
    orch = _orch_with_graph([_t("t1", "前端"), _t("t2", "前端")], ("前端",))
    orch._pending_notes = {"前端": ["给前端的"], "*": ["全局约束"]}

    n1 = orch.graph.nodes["t1"]
    await orch._execute_and_settle(n1)
    # t1 拿到 worker 桶 + 全局桶
    assert n1.pending_notes == ["给前端的", "全局约束"]
    # worker 桶已 pop 清空，全局桶仍在
    assert "前端" not in orch._pending_notes
    assert orch._pending_notes.get("*") == ["全局约束"]

    n2 = orch.graph.nodes["t2"]
    await orch._execute_and_settle(n2)
    # t2 只剩全局桶（worker 桶已被 t1 消费）
    assert n2.pending_notes == ["全局约束"]


# ── SessionState.from_session ──


class _FakeMessageRepo:
    def __init__(self, messages: list) -> None:
        self._messages = messages

    async def list_by_session(self, session_id, limit):  # type: ignore[no-untyped-def]
        return self._messages[:limit]


@pytest.mark.asyncio
async def test_from_session_without_plan() -> None:
    sid = uuid.uuid4()
    state = await SessionState.from_session(
        session_id=sid, members=(), message_repo=_FakeMessageRepo([]),
        window=15, active_plan=None,
    )
    assert state.active_plan is None
    assert state.session_id == sid


@pytest.mark.asyncio
async def test_relay_parked_resumes_via_on_feed() -> None:
    """relay 给 parked 成员（run 已休眠 _task=None）→ 当答复 → on_feed(step)。"""
    from types import SimpleNamespace

    run = CoordinatorRun(session_id=uuid.uuid4())
    fed: list[tuple[str, str]] = []

    async def _on_feed(step_id, answer):  # type: ignore[no-untyped-def]
        fed.append((step_id, answer))

    run._orchestrator = SimpleNamespace(  # type: ignore[assignment]
        graph=SimpleNamespace(nodes={
            "t1": SimpleNamespace(
                task=SimpleNamespace(id="t1", suggested_worker="前端小美"),
                status=SimpleNamespace(value="running"),
            )
        }),
        on_feed=_on_feed,
    )
    run._task = None  # parked

    await run.relay("前端小美", "用 PG")
    await asyncio.sleep(0.02)  # 等 spawn 的 on_feed
    assert fed == [("t1", "用 PG")]
    assert run._pending_notes == {}  # parked 不进桶


@pytest.mark.asyncio
async def test_relay_in_flight_buffers_to_bucket() -> None:
    """relay 给 in-flight 成员（_task 未结束）→ 进桶，不调 on_feed。"""
    from types import SimpleNamespace

    run = CoordinatorRun(session_id=uuid.uuid4())
    fed: list = []
    run._orchestrator = SimpleNamespace(  # type: ignore[assignment]
        graph=SimpleNamespace(nodes={}), on_feed=lambda *a: fed.append(a),
    )
    # 造一个未结束的 task 模拟 in-flight
    async def _busy():
        await asyncio.sleep(0.2)
    run._task = asyncio.create_task(_busy())

    await run.relay("前端小美", "注意用 React")
    assert run._pending_notes == {"前端小美": ["注意用 React"]}  # 进桶
    assert fed == []  # 不 resume
    run._task.cancel()


@pytest.mark.asyncio
async def test_from_session_with_plan_reverses_transcript() -> None:
    from app.domain.entities.message import Message
    from app.domain.enums import MessageRole

    # 仓库返回倒序（最新在前）
    m_new = Message(session_id=uuid.uuid4(), role=MessageRole.USER, content="新")
    m_old = Message(session_id=uuid.uuid4(), role=MessageRole.USER, content="旧")
    plan = PlanView(steps=(StepView("t1", "前端", "running"),))
    state = await SessionState.from_session(
        session_id=uuid.uuid4(), members=(),
        message_repo=_FakeMessageRepo([m_new, m_old]),
        window=15, active_plan=plan,
    )
    # from_session 翻成时间正序：旧 → 新
    assert [m.content for m in state.transcript] == ["旧", "新"]
    assert state.active_plan is plan
    assert state.in_execution is True
