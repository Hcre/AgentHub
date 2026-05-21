"""PostgresMessageRepository。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
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
                )
            )
        else:
            existing.content = message.content
            existing.status = str(message.status)
            existing.pinned = message.pinned
            existing.extra = message.metadata
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
        return [_to_domain(m) for m in reversed(rows)]  # 返回正序

    async def set_pinned(self, message_id: UUID, pinned: bool) -> None:
        m = await self._s.get(MessageModel, message_id)
        if m is not None:
            m.pinned = pinned
            await self._s.flush()
