"""Tasks 看板 CRUD + Inbox 审批流测试（L3 service + L1 repo）。

覆盖三路径（T-03）：正常 / 异常 / 边界。
- Tasks：create → list → get → update(状态流转 + 清空 assignee) → delete → get 404
- Inbox：create → list(排除 resolved) → unread_count → mark_read → resolve → 终态隔离
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services import InboxService, TaskService
from app.core.exceptions import NotFoundError
from app.domain.enums import (
    InboxItemStatus,
    InboxResolution,
    NotificationCategory,
    TaskPriority,
    TaskStatus,
)
from app.infrastructure.repositories import (
    PostgresInboxRepository,
    PostgresTaskRepository,
)


def _task_svc(db):  # type: ignore[no-untyped-def]
    return TaskService(PostgresTaskRepository(db))


def _inbox_svc(db):  # type: ignore[no-untyped-def]
    return InboxService(PostgresInboxRepository(db))


# ============ Tasks ============


@pytest.mark.asyncio
async def test_task_create_and_get(db_session):  # type: ignore[no-untyped-def]
    svc = _task_svc(db_session)
    t = await svc.create(
        title="写答辩稿",
        priority=TaskPriority.HIGH,
        assignee="a1",
        due_label="周三",
    )
    fetched = await svc.get(t.id)
    assert fetched.title == "写答辩稿"
    assert fetched.priority == TaskPriority.HIGH
    assert fetched.assignee_label == "a1"
    assert fetched.due_label == "周三"
    assert fetched.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_task_list_and_status_filter(db_session):  # type: ignore[no-untyped-def]
    svc = _task_svc(db_session)
    await svc.create(title="A", status=TaskStatus.PENDING)
    await svc.create(title="B", status=TaskStatus.RUNNING)
    all_tasks = await svc.list()
    assert len(all_tasks) == 2
    running = await svc.list(status=["running"])
    assert [t.title for t in running] == ["B"]


@pytest.mark.asyncio
async def test_task_update_status_and_clear_assignee(db_session):  # type: ignore[no-untyped-def]
    svc = _task_svc(db_session)
    t = await svc.create(title="X", assignee="a1")
    moved = await svc.update(t.id, status=TaskStatus.COMPLETED)
    assert moved.status == TaskStatus.COMPLETED
    # 边界：显式清空 assignee（assignee_set=True + None）
    cleared = await svc.update(t.id, assignee=None, assignee_set=True)
    assert cleared.assignee_label is None


@pytest.mark.asyncio
async def test_task_delete_then_get_raises(db_session):  # type: ignore[no-untyped-def]
    svc = _task_svc(db_session)
    t = await svc.create(title="临时")
    await svc.delete(t.id)
    with pytest.raises(NotFoundError):
        await svc.get(t.id)


@pytest.mark.asyncio
async def test_task_delete_missing_raises(db_session):  # type: ignore[no-untyped-def]
    svc = _task_svc(db_session)
    with pytest.raises(NotFoundError):
        await svc.delete(uuid4())


# ============ Inbox ============


@pytest.mark.asyncio
async def test_inbox_create_list_unread(db_session):  # type: ignore[no-untyped-def]
    svc = _inbox_svc(db_session)
    await svc.create(title="审批", type_=NotificationCategory.APPROVAL, summary="批准部署")
    await svc.create(title="通知", type_=NotificationCategory.SYSTEM)
    items = await svc.list()
    assert len(items) == 2
    assert await svc.unread_count() == 2


@pytest.mark.asyncio
async def test_inbox_mark_read_decrements_unread(db_session):  # type: ignore[no-untyped-def]
    svc = _inbox_svc(db_session)
    item = await svc.create(title="审批", type_=NotificationCategory.APPROVAL)
    read = await svc.mark_read(item.id)
    assert read.status == InboxItemStatus.READ
    assert await svc.unread_count() == 0


@pytest.mark.asyncio
async def test_inbox_resolve_excludes_from_default_list(db_session):  # type: ignore[no-untyped-def]
    svc = _inbox_svc(db_session)
    item = await svc.create(title="审批", type_=NotificationCategory.APPROVAL)
    resolved = await svc.resolve(item.id, InboxResolution.APPROVED)
    assert resolved.status == InboxItemStatus.RESOLVED
    assert resolved.resolution == InboxResolution.APPROVED
    # 默认列表排除 resolved
    assert await svc.list() == []
    # include_resolved 仍可见
    all_items = await svc.list(include_resolved=True)
    assert len(all_items) == 1


@pytest.mark.asyncio
async def test_inbox_resolve_missing_raises(db_session):  # type: ignore[no-untyped-def]
    svc = _inbox_svc(db_session)
    with pytest.raises(NotFoundError):
        await svc.resolve(uuid4(), InboxResolution.REJECTED)
