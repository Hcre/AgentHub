"""会话与消息路由。"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, get_session_service
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
            workspace_path=body.workspace_path or "",
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
async def update_session(session_id: UUID, body: dict, svc: ServiceDep) -> SessionOut:
    resp = await svc.update(
        UpdateSessionCommand(
            session_id=session_id,
            title=body.get("title"),
            workspace_path=body.get("workspace_path"),
        )
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
    message_id: UUID,
    session_id: UUID,
    svc: ServiceDep,
    current_user: CurrentUser,
) -> Response:
    """P0-4 Pin 消息 — M5 鉴权降级。

    鉴权链 (M5 简化契约 per docs/specs/04-commands §6.1.6 + plan_agenthub-m5-m6 brief):
    - session_id query 必传 (M5 之前就有, 现仍然)
    - Authorization header 可选 (有则解析, 无则不强求)
    - 无 JWT 时 service 层用 msg.user_id 作 implicit owner (dev mode auto-trust)
    - 仅"无 JWT + msg 无 user_id (system message)"才 401
    - session_id 与 msg.session_id 不匹配 → 422 E_MESSAGE_PIN_SESSION_MISMATCH
    - 有 JWT 但 ≠ msg.user_id → 403 E_MESSAGE_PIN_NOT_OWNER
    """
    await svc.pin_message(
        PinMessageCommand(session_id=session_id, message_id=message_id),
        current_user=current_user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/messages/{message_id}/pin", status_code=status.HTTP_204_NO_CONTENT)
async def unpin_message(
    message_id: UUID,
    session_id: UUID,
    svc: ServiceDep,
    current_user: CurrentUser,
) -> Response:
    """P0-4 Unpin 消息 — 与 pin 对称, M5 鉴权降级一致."""
    await svc.unpin_message(
        UnpinMessageCommand(session_id=session_id, message_id=message_id),
        current_user=current_user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
