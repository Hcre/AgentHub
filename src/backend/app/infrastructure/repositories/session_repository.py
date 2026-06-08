"""PostgresSessionRepository。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.session import Session
from app.domain.enums import SessionType
from app.domain.repositories import SessionRepository
from app.infrastructure.db.models import SessionModel


def _to_domain(m: SessionModel) -> Session:
    return Session(
        id=m.id,
        type=SessionType(m.type),
        title=m.title,
        group_id=m.group_id,
        agent_id=m.agent_id,
        workspace_path=m.workspace_path or "",
        pinned=m.pinned,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class PostgresSessionRepository(SessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, session: Session) -> None:
        existing = await self._s.get(SessionModel, session.id)
        if existing is None:
            self._s.add(
                SessionModel(
                    id=session.id,
                    type=str(session.type),
                    title=session.title,
                    group_id=session.group_id,
                    agent_id=session.agent_id,
                    workspace_path=session.workspace_path or "",
                    pinned=session.pinned,
                )
            )
        else:
            existing.title = session.title
            existing.workspace_path = session.workspace_path or ""
            existing.pinned = session.pinned
        await self._s.flush()

    async def get_by_id(self, session_id: UUID) -> Session | None:
        m = await self._s.get(SessionModel, session_id)
        return _to_domain(m) if m else None

    async def list(self, *, type: str | None = None, query: str | None = None) -> list[Session]:
        stmt = select(SessionModel).order_by(SessionModel.updated_at.desc())
        if type:
            stmt = stmt.where(SessionModel.type == type)
        if query:
            stmt = stmt.where(
                or_(
                    SessionModel.title.ilike(f"%{query}%"),
                )
            )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_domain(m) for m in rows]

    async def delete(self, session_id: UUID) -> None:
        m = await self._s.get(SessionModel, session_id)
        if m is not None:
            await self._s.delete(m)
            await self._s.flush()
