"""EngineTaskDispatcher（L3）：看板 Task → 真实编排引擎（CoordinatorRun）。

把一条看板任务派给编排引擎后台真跑：复用 chat 同款 build_default_orchestrator +
CoordinatorRun。引擎每次状态变更经 event_sink 落 task_events（AR-05），run 终态回写
TaskModel.status。后台运行用独立 session（请求已结束，不能复用其 session）。

校验：任务须绑定群组会话 + 群组有成员，否则即时 FAILED（清晰原因，不静默）。
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.application.services.coordinator_run import (
    CoordinatorRegistry,
    CoordinatorRun,
    build_default_orchestrator,
)
from app.application.services.task_service import RecordEvent, SetStatus
from app.domain.entities.task import Task
from app.domain.entities.task_event import TaskEvent
from app.domain.enums import TaskStatus
from app.infrastructure.db.base import session_factory
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresGroupRepository,
    PostgresSessionRepository,
)
from app.infrastructure.repositories.task_event_repository import PostgresTaskEventRepository
from app.infrastructure.repositories.task_repository import PostgresTaskRepository

logger = logging.getLogger(__name__)


class EngineTaskDispatcher:
    def __init__(self, *, registry: CoordinatorRegistry | None = None, builder=build_default_orchestrator) -> None:
        self._registry = registry or CoordinatorRegistry()
        self._builder = builder
        # 持有后台任务引用防 GC（RUF006）；完成即移除。
        self._bg: set[asyncio.Task] = set()

    def _spawn(self, coro) -> None:  # type: ignore[no-untyped-def]
        t = asyncio.create_task(coro)
        self._bg.add(t)
        t.add_done_callback(self._bg.discard)

    async def run(self, task: Task, *, record_event: RecordEvent, set_status: SetStatus) -> None:
        """校验通过则后台起引擎并立即返回（task 保持 RUNNING，终态后台回写）。"""
        if task.session_id is None:
            await set_status(TaskStatus.FAILED, "派发需要绑定会话")
            return
        async with session_factory() as db:
            session = await PostgresSessionRepository(db).get_by_id(task.session_id)
            if session is None or session.group_id is None:
                await set_status(TaskStatus.FAILED, "派发需要绑定群组会话")
                return
            group = await PostgresGroupRepository(db).get_by_id(session.group_id)
            if group is None or not group.member_ids:
                await set_status(TaskStatus.FAILED, "群组无成员，无法派发")
                return
        requirement = f"{task.title}\n\n{task.description}".strip()
        # 后台真跑（独立 session）；不在请求里 await 完成。
        self._spawn(self._run_bg(task.id, task.session_id, session.group_id, requirement))

    async def _run_bg(self, task_id: UUID, session_id: UUID, group_id: UUID, requirement: str) -> None:
        run = CoordinatorRun(session_id=session_id)
        if not self._registry.try_reserve(session_id, run):
            await self._writeback(task_id, TaskStatus.FAILED, "该会话已有任务在执行")
            return
        try:
            async with session_factory() as db:
                session = await PostgresSessionRepository(db).get_by_id(session_id)
                group = await PostgresGroupRepository(db).get_by_id(group_id)
                agent_repo = PostgresAgentRepository(db)
                members = [
                    a for mid in group.member_ids if (a := await agent_repo.get_by_id(mid)) is not None
                ]
                orchestrator = await self._builder(
                    task=requirement, members=members, session=session, group=group
                )
            orchestrator._event_sink = self._make_event_sink(task_id)
            run.start(
                orchestrator,
                on_done=lambda r: self._writeback(
                    task_id, TaskStatus.COMPLETED, getattr(r, "summary", "") or "任务完成"
                ),
                on_error=lambda e: self._writeback(task_id, TaskStatus.FAILED, str(e)),
                registry=self._registry,
            )
        except Exception as exc:
            self._registry.release(session_id)
            logger.exception("引擎派发启动失败 task=%s", task_id)
            await self._writeback(task_id, TaskStatus.FAILED, f"启动失败: {exc}")

    def _make_event_sink(self, task_id: UUID):
        """引擎 _record 同步外抛 → fire-and-forget 落 task_events。"""

        def sink(event: dict) -> None:
            self._spawn(self._persist_event(task_id, event))

        return sink

    async def _persist_event(self, task_id: UUID, event: dict) -> None:
        try:
            async with session_factory() as db:
                await PostgresTaskEventRepository(db).append(
                    TaskEvent(
                        task_id=task_id,
                        event_type=str(event.get("kind", "event")),
                        event_data={k: str(v) for k, v in event.items()},
                        actor="orchestrator",
                    )
                )
                await db.commit()
        except Exception:
            logger.exception("持久化 task_event 失败 task=%s", task_id)

    async def _writeback(self, task_id: UUID, status: TaskStatus, reason: str | None) -> None:
        try:
            async with session_factory() as db:
                repo = PostgresTaskRepository(db)
                task = await repo.get_by_id(task_id)
                if task is None:
                    return
                prev = task.status
                task.status = status
                task.touch()
                await repo.save(task)
                await PostgresTaskEventRepository(db).append(
                    TaskEvent(
                        task_id=task_id,
                        event_type="transition",
                        event_data={"from": prev.value, "to": status.value, "reason": reason or ""},
                        actor="orchestrator",
                    )
                )
                await db.commit()
        except Exception:
            logger.exception("回写 task 状态失败 task=%s", task_id)
