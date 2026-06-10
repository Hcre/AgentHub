"""任务路由（架构 §4.4）。M3 持久化 CRUD（完整 FSM/DAG 派发编排走 task_engine）。

REST 端点（AP-01 kebab + AP-02 `{error:{code,message}}`）：
- GET    /api/tasks          列任务（query: status / priority 可多值）
- POST   /api/tasks          创建任务
- GET    /api/tasks/{id}     查单个
- PATCH  /api/tasks/{id}     改字段（含状态流转 / 看板拖拽）
- DELETE /api/tasks/{id}     删除
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_task_service
from app.application.services.task_service import TaskService
from app.domain.enums import TaskPriority, TaskStatus
from app.schemas.task import (
    TaskCreate,
    TaskEventListOut,
    TaskEventOut,
    TaskListOut,
    TaskOut,
    TaskUpdate,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

ServiceDep = Annotated[TaskService, Depends(get_task_service)]


def _to_out(task) -> TaskOut:  # type: ignore[no-untyped-def]
    return TaskOut(
        id=task.id,
        title=task.title,
        description=task.description,
        status=task.status.value,
        priority=task.priority.value,
        assignee=task.assignee_label,
        due=task.due_label,
        source=task.source.value,
        session_id=task.session_id,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
    )


@router.get("", response_model=TaskListOut)
async def list_tasks(
    svc: ServiceDep,
    status_: Annotated[list[str] | None, Query(alias="status")] = None,
    priority: Annotated[list[str] | None, Query()] = None,
) -> TaskListOut:
    items = await svc.list(status=status_, priority=priority)
    out = [_to_out(t) for t in items]
    return TaskListOut(items=out, total=len(out))


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskCreate, svc: ServiceDep) -> TaskOut:
    task = await svc.create(
        title=body.title,
        description=body.description,
        status=TaskStatus(body.status),
        priority=TaskPriority(body.priority),
        assignee=body.assignee,
        due_label=body.due,
        session_id=body.session_id,
    )
    return _to_out(task)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: UUID, svc: ServiceDep) -> TaskOut:
    return _to_out(await svc.get(task_id))


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(task_id: UUID, body: TaskUpdate, svc: ServiceDep) -> TaskOut:
    fields = body.model_fields_set
    task = await svc.update(
        task_id,
        title=body.title,
        description=body.description,
        status=TaskStatus(body.status) if body.status is not None else None,
        priority=TaskPriority(body.priority) if body.priority is not None else None,
        assignee=body.assignee,
        due_label=body.due,
        assignee_set="assignee" in fields,
        due_set="due" in fields,
    )
    return _to_out(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, svc: ServiceDep) -> Response:
    await svc.delete(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{task_id}/dispatch", response_model=TaskOut)
async def dispatch_task(task_id: UUID, svc: ServiceDep) -> TaskOut:
    """把看板任务派给编排引擎真跑（M3+）。返回置 RUNNING 后的任务；终态后台回写。"""
    task = await svc.dispatch(task_id)
    return _to_out(task)


@router.get("/{task_id}/events", response_model=TaskEventListOut)
async def list_task_events(task_id: UUID, svc: ServiceDep) -> TaskEventListOut:
    """某任务的编排事件流（AR-05 事件溯源，append-only）。"""
    events = await svc.events(task_id)
    return TaskEventListOut(
        items=[
            TaskEventOut(
                id=e.id,
                event_type=e.event_type,
                event_data=e.event_data,
                actor=e.actor,
                created_at=e.created_at.isoformat(),
            )
            for e in events
        ],
        total=len(events),
    )
