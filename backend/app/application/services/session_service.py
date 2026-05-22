"""SessionService（L3）：会话创建与消息历史查询。"""

from __future__ import annotations

from uuid import UUID

from app.application.commands import (
    CreateSessionCommand,
    PinMessageCommand,
    UnpinMessageCommand,
    UpdateSessionCommand,
)
from app.application.dto import MessageResponse, SessionResponse
from app.core.events import EventBus
from app.core.exceptions import NotFoundError
from app.domain.entities.session import Session
from app.domain.enums import SessionType
from app.domain.events import MessagePinned, SessionCreated
from app.domain.repositories import MessageRepository, SessionRepository


class SessionService:
    def __init__(
        self,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        event_bus: EventBus,
    ) -> None:
        self._sessions = session_repo
        self._messages = message_repo
        self._bus = event_bus

    async def create(self, cmd: CreateSessionCommand) -> SessionResponse:
        session = Session(
            type=SessionType(cmd.type),
            group_id=cmd.group_id,
            agent_id=cmd.agent_id,
            title=cmd.title,
        )
        await self._sessions.save(session)
        participants = [p for p in (cmd.group_id, cmd.agent_id) if p is not None]
        await self._bus.publish(
            SessionCreated(
                session_id=session.id, type=str(session.type), participants=participants
            )
        )
        return SessionResponse.from_domain(session)

    async def list(self, *, type: str | None = None, query: str | None = None) -> list[SessionResponse]:
        sessions = await self._sessions.list(type=type, query=query)
        return [SessionResponse.from_domain(s) for s in sessions]

    async def get(self, session_id: UUID) -> SessionResponse:
        session = await self._sessions.get_by_id(session_id)
        if session is None:
            raise NotFoundError(f"会话不存在: {session_id}")
        return SessionResponse.from_domain(session)

    async def list_messages(
        self, session_id: UUID, *, before: UUID | None = None, limit: int = 50
    ) -> list[MessageResponse]:
        msgs = await self._messages.list_by_session(
            session_id, before=before, limit=limit
        )
        return [MessageResponse.from_domain(m) for m in msgs]

    async def update(self, cmd: UpdateSessionCommand) -> SessionResponse:
        session = await self._sessions.get_by_id(cmd.session_id)
        if session is None:
            raise NotFoundError(f"会话不存在: {cmd.session_id}")
        if cmd.title is not None:
            session.title = cmd.title
        await self._sessions.save(session)
        return SessionResponse.from_domain(session)

    async def delete_session(self, session_id: UUID) -> None:
        session = await self._sessions.get_by_id(session_id)
        if session is None:
            raise NotFoundError(f"会话不存在: {session_id}")
        await self._sessions.delete(session_id)

    async def delete_message(self, message_id: UUID) -> None:
        msg = await self._messages.get_by_id(message_id)
        if msg is None:
            raise NotFoundError(f"消息不存在: {message_id}")
        await self._messages.delete(message_id)

    async def pin_message(self, cmd: PinMessageCommand) -> None:
        msg = await self._messages.get_by_id(cmd.message_id)
        if msg is None:
            raise NotFoundError(f"消息不存在: {cmd.message_id}")
        await self._messages.set_pinned(cmd.message_id, True)
        await self._bus.publish(
            MessagePinned(session_id=cmd.session_id, message_id=cmd.message_id)
        )

    async def unpin_message(self, cmd: UnpinMessageCommand) -> None:
        msg = await self._messages.get_by_id(cmd.message_id)
        if msg is None:
            raise NotFoundError(f"消息不存在: {cmd.message_id}")
        await self._messages.set_pinned(cmd.message_id, False)
