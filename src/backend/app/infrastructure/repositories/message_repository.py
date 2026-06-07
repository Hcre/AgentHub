"""PostgresMessageRepository。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.message import Message
from app.domain.enums import ContentType, MessageRole, MessageStatus
from app.domain.repositories import MessageRepository
from app.infrastructure.db.models import MessageModel


def _to_domain(m: MessageModel) -> Message:
    return Message(
        id=m.id,
        session_id=m.session_id,
        role=MessageRole(m.role),
        content=m.content,
        content_type=ContentType(m.content_type),
        sender_agent_id=m.sender_agent_id,
        mentions=list(m.mentions or []),
        reply_to=m.reply_to,
        pinned=m.pinned,
        status=MessageStatus(m.status),
        metadata=dict(m.extra or {}),
        created_at=m.created_at,
        user_id=m.user_id,
        pinned_by_user_id=m.pinned_by_user_id,
        pinned_at=m.pinned_at,
    )


class PostgresMessageRepository(MessageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, message: Message) -> None:
        existing = await self._s.get(MessageModel, message.id)
        if existing is None:
            self._s.add(
                MessageModel(
                    id=message.id,
                    session_id=message.session_id,
                    role=str(message.role),
                    content=message.content,
                    content_type=str(message.content_type),
                    sender_agent_id=message.sender_agent_id,
                    mentions=message.mentions,
                    reply_to=message.reply_to,
                    pinned=message.pinned,
                    status=str(message.status),
                    extra=message.metadata,
                    user_id=message.user_id,
                    pinned_by_user_id=message.pinned_by_user_id,
                    pinned_at=message.pinned_at,
                )
            )
        else:
            existing.content = message.content
            existing.status = str(message.status)
            existing.pinned = message.pinned
            existing.extra = message.metadata
            existing.user_id = message.user_id
            existing.pinned_by_user_id = message.pinned_by_user_id
            existing.pinned_at = message.pinned_at
        await self._s.flush()

    async def get_by_id(self, message_id: UUID) -> Message | None:
        m = await self._s.get(MessageModel, message_id)
        return _to_domain(m) if m else None

    async def list_by_session(
        self, session_id: UUID, *, before: UUID | None = None, limit: int = 50
    ) -> list[Message]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.created_at.desc())
            .limit(limit)
        )
        if before is not None:
            anchor = await self._s.get(MessageModel, before)
            if anchor is not None:
                stmt = stmt.where(MessageModel.created_at < anchor.created_at)
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_domain(m) for m in reversed(rows)]

    async def list_after(
        self, session_id: UUID, after_message_id: UUID, *, limit: int = 100
    ) -> list[Message]:
        anchor = await self._s.get(MessageModel, after_message_id)
        if anchor is None:
            return []
        stmt = (
            select(MessageModel)
            .where(
                MessageModel.session_id == session_id,
                MessageModel.created_at > anchor.created_at,
            )
            .order_by(MessageModel.created_at.asc())
            .limit(limit)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_domain(m) for m in rows]

    async def set_pinned(
        self,
        message_id: UUID,
        pinned: bool,
        *,
        pinned_by_user_id: UUID | None = None,
    ) -> None:
        m = await self._s.get(MessageModel, message_id)
        if m is not None:
            m.pinned = pinned
            if pinned:
                m.pinned_by_user_id = pinned_by_user_id
                m.pinned_at = datetime.now(UTC)
            else:
                m.pinned_by_user_id = None
                m.pinned_at = None
            await self._s.flush()

    async def has_assistant_messages(self, session_id: UUID) -> bool:
        stmt = select(exists().where(
            MessageModel.session_id == session_id,
            MessageModel.role == "assistant",
        ))
        result = await self._s.execute(stmt)
        return bool(result.scalar())

    async def delete(self, message_id: UUID) -> None:
        m = await self._s.get(MessageModel, message_id)
        if m is not None:
            await self._s.delete(m)
            await self._s.flush()
