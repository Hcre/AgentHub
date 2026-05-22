"""会话与消息路由（PRD §6.3，架构 §4.3）。

注意：发送消息的实时流式走 WS `/ws/sessions/{id}`；
此处 REST POST 仅用于无 WS 场景的兜底（非流式，一次性返回完整回复）。
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_session_service
from app.application.commands import (
    CreateSessionCommand,
    PinMessageCommand,
    UnpinMessageCommand,
    UpdateSessionCommand,
)
from app.application.services import SessionService
from app.schemas.session import MessageOut, SessionCreateRequest, SessionOut

router = APIRouter(prefix="/api", tags=["sessions"])

ServiceDep = Annotated[SessionService, Depends(get_session_service)]


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(body: SessionCreateRequest, svc: ServiceDep) -> SessionOut:
    resp = await svc.create(
        CreateSessionCommand(
            type=str(body.type),
            group_id=body.group_id,
            agent_id=body.agent_id,
            title=body.title,
        )
    )
    return SessionOut(**resp.__dict__)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    svc: ServiceDep, type: str | None = None, q: str | None = None
) -> list[SessionOut]:
    items = await svc.list(type=type, query=q)
    return [SessionOut(**i.__dict__) for i in items]


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session_detail(session_id: UUID, svc: ServiceDep) -> SessionOut:
    return SessionOut(**(await svc.get(session_id)).__dict__)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(
    session_id: UUID,
    svc: ServiceDep,
    before: UUID | None = None,
    limit: int = Query(default=50, le=200),
) -> list[MessageOut]:
    items = await svc.list_messages(session_id, before=before, limit=limit)
    return [MessageOut(**i.__dict__) for i in items]


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def update_session(
    session_id: UUID, body: dict, svc: ServiceDep
) -> SessionOut:
    resp = await svc.update(
        UpdateSessionCommand(session_id=session_id, title=body.get("title"))
    )
    return SessionOut(**resp.__dict__)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: UUID, svc: ServiceDep) -> Response:
    await svc.delete_session(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(message_id: UUID, svc: ServiceDep) -> Response:
    await svc.delete_message(message_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/messages/{message_id}/pin", status_code=status.HTTP_204_NO_CONTENT)
async def pin_message(
    message_id: UUID, session_id: UUID, svc: ServiceDep
) -> Response:
    await svc.pin_message(
        PinMessageCommand(session_id=session_id, message_id=message_id)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/messages/{message_id}/pin", status_code=status.HTTP_204_NO_CONTENT)
async def unpin_message(
    message_id: UUID, session_id: UUID, svc: ServiceDep
) -> Response:
    await svc.unpin_message(
        UnpinMessageCommand(session_id=session_id, message_id=message_id)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
