"""收件箱路由（架构 §4.6）。M4 审批流 + 通知持久化。

REST 端点（AP-01 kebab + AP-02 `{error:{code,message}}`）：
- GET   /api/inbox               列条目（query: type 过滤；默认排除 resolved）
- GET   /api/inbox/unread-count  未读计数
- POST  /api/inbox               创建条目（群聊审批请求等内部写入）
- POST  /api/inbox/{id}/read     标记已读
- POST  /api/inbox/{id}/resolve  批准/驳回（action: approve|reject）
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_inbox_service
from app.application.services.inbox_service import InboxService
from app.domain.enums import InboxResolution, NotificationCategory
from app.schemas.inbox import (
    InboxItemCreate,
    InboxItemOut,
    InboxListOut,
    InboxResolveRequest,
)

router = APIRouter(prefix="/api/inbox", tags=["inbox"])

ServiceDep = Annotated[InboxService, Depends(get_inbox_service)]


def _to_out(item) -> InboxItemOut:  # type: ignore[no-untyped-def]
    return InboxItemOut(
        id=item.id,
        type=item.type.value,
        title=item.title,
        summary=item.summary,
        actor=item.actor,
        actor_name=item.actor_name,
        when=item.when_label,
        payload=item.payload,
        status=item.status.value,
        resolution=item.resolution.value if item.resolution else None,
        unread=item.unread,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.get("", response_model=InboxListOut)
async def list_inbox(
    svc: ServiceDep,
    type_: Annotated[str | None, Query(alias="type")] = None,
    include_resolved: Annotated[bool, Query()] = False,
) -> InboxListOut:
    items = await svc.list(type_=type_, include_resolved=include_resolved)
    return InboxListOut(
        items=[_to_out(i) for i in items],
        unread_count=await svc.unread_count(),
    )


@router.get("/unread-count")
async def unread_count(svc: ServiceDep) -> dict:
    return {"unread_count": await svc.unread_count()}


@router.post("", response_model=InboxItemOut, status_code=status.HTTP_201_CREATED)
async def create_inbox_item(body: InboxItemCreate, svc: ServiceDep) -> InboxItemOut:
    item = await svc.create(
        title=body.title,
        type_=NotificationCategory(body.type),
        summary=body.summary,
        actor=body.actor,
        actor_name=body.actor_name,
        when_label=body.when,
        payload=body.payload,
        session_id=body.session_id,
    )
    return _to_out(item)


@router.post("/{item_id}/read", response_model=InboxItemOut)
async def mark_read(item_id: UUID, svc: ServiceDep) -> InboxItemOut:
    return _to_out(await svc.mark_read(item_id))


@router.post("/{item_id}/resolve", response_model=InboxItemOut)
async def resolve_inbox_item(
    item_id: UUID, body: InboxResolveRequest, svc: ServiceDep
) -> InboxItemOut:
    resolution = (
        InboxResolution.APPROVED if body.action == "approve" else InboxResolution.REJECTED
    )
    return _to_out(await svc.resolve(item_id, resolution))
