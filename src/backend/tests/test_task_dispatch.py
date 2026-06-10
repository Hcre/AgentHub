"""TaskService.dispatch + task_events 持久化测试（M3+ 看板→真派发接线）。

用真 Postgres 仓储（in-memory sqlite）+ fake dispatcher 模拟一次编排 run，
断言：状态机回写 + 事件 append-only 落 task_events（AR-05）。
"""

from __future__ import annotations

import pytest

from app.application.services.task_service import RecordEvent, SetStatus, TaskService
from app.core.exceptions import ValidationError
from app.domain.entities.task import Task
from app.domain.enums import TaskStatus
from app.infrastructure.repositories.task_event_repository import PostgresTaskEventRepository
from app.infrastructure.repositories.task_repository import PostgresTaskRepository


class _FakeDispatcher:
    """模拟编排 run：派一个节点 → 完成。"""

    def __init__(self, *, final: TaskStatus = TaskStatus.COMPLETED) -> None:
        self.final = final
        self.ran_for: list[str] = []

    async def run(self, task: Task, *, record_event: RecordEvent, set_status: SetStatus) -> None:
        self.ran_for.append(task.title)
        await record_event("node_started", {"node": "t1", "who": "工程师"})
        await record_event("node_done", {"node": "t1"})
        await set_status(self.final, None if self.final == TaskStatus.COMPLETED else "boom")


def _svc(db_session, dispatcher=None) -> TaskService:
    return TaskService(
        PostgresTaskRepository(db_session),
        event_repo=PostgresTaskEventRepository(db_session),
        dispatcher=dispatcher,
    )


@pytest.mark.asyncio
async def test_dispatch_runs_and_persists_events(db_session) -> None:  # type: ignore[no-untyped-def]
    repo = PostgresTaskRepository(db_session)
    task = Task(title="实现登录页")
    await repo.save(task)

    disp = _FakeDispatcher()
    svc = _svc(db_session, disp)
    result = await svc.dispatch(task.id)

    assert disp.ran_for == ["实现登录页"]
    assert result.status == TaskStatus.COMPLETED
    # 看板真值回写
    after = await repo.get_by_id(task.id)
    assert after.status == TaskStatus.COMPLETED

    # 事件 append-only：dispatched → transition(RUNNING) → node_started → node_done → transition(COMPLETED)
    events = await svc.events(task.id)
    types = [e.event_type for e in events]
    assert types == ["dispatched", "transition", "node_started", "node_done", "transition"]
    # 首尾 transition 的 from/to 正确
    assert events[1].event_data["to"] == "running"
    assert events[-1].event_data["to"] == "completed"


@pytest.mark.asyncio
async def test_dispatch_failed_run_writes_failed_status(db_session) -> None:  # type: ignore[no-untyped-def]
    repo = PostgresTaskRepository(db_session)
    task = Task(title="会失败的任务")
    await repo.save(task)
    svc = _svc(db_session, _FakeDispatcher(final=TaskStatus.FAILED))
    result = await svc.dispatch(task.id)
    assert result.status == TaskStatus.FAILED
    last = (await svc.events(task.id))[-1]
    assert last.event_data["to"] == "failed"
    assert last.event_data["reason"] == "boom"


@pytest.mark.asyncio
async def test_dispatch_rejects_already_running(db_session) -> None:  # type: ignore[no-untyped-def]
    repo = PostgresTaskRepository(db_session)
    task = Task(title="跑着的任务", status=TaskStatus.RUNNING)
    await repo.save(task)
    svc = _svc(db_session, _FakeDispatcher())
    with pytest.raises(ValidationError, match="E_TASK_ALREADY_RUNNING"):
        await svc.dispatch(task.id)


@pytest.mark.asyncio
async def test_dispatch_without_dispatcher_raises(db_session) -> None:  # type: ignore[no-untyped-def]
    repo = PostgresTaskRepository(db_session)
    task = Task(title="无引擎")
    await repo.save(task)
    svc = TaskService(repo, event_repo=PostgresTaskEventRepository(db_session))  # no dispatcher
    with pytest.raises(ValidationError, match="E_TASK_DISPATCH_UNAVAILABLE"):
        await svc.dispatch(task.id)


@pytest.mark.asyncio
async def test_events_append_only_ordering(db_session) -> None:  # type: ignore[no-untyped-def]
    repo = PostgresTaskRepository(db_session)
    task = Task(title="审计")
    await repo.save(task)
    svc = _svc(db_session, _FakeDispatcher())
    await svc.dispatch(task.id)
    events = await svc.events(task.id)
    # created_at 单调不降（append-only 时间序）
    ts = [e.created_at for e in events]
    assert ts == sorted(ts)
