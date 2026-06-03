"""PostgresMemoryRepository：MemoryRepository 的 SQLAlchemy 实现。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.memory import Memory
from app.domain.repositories.memory_repository import MemoryRepository
from app.infrastructure.db.models import MemoryModel


def _to_domain(m: MemoryModel) -> Memory:
    return Memory(
        id=m.id,
        agent_id=m.agent_id,
        user_id=m.user_id,
        scope=m.scope,
        name=m.name,
        description=m.description,
        memory_type=m.memory_type,
        content=m.content,
        source=m.source,
        pinned=m.pinned,
        hits=m.hits,
        metadata=dict(m.metadata_ or {}),
        group_id=m.group_id,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _to_model(m: Memory) -> MemoryModel:
    return MemoryModel(
        id=m.id,
        agent_id=m.agent_id,
        user_id=m.user_id,
        scope=m.scope,
        name=m.name,
        description=m.description,
        memory_type=m.memory_type,
        content=m.content,
        source=m.source,
        pinned=m.pinned,
        hits=m.hits,
        metadata_=m.metadata,
        group_id=m.group_id,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class PostgresMemoryRepository(MemoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, memory: Memory) -> None:
        existing = await self._s.get(MemoryModel, memory.id)
        if existing is None:
            self._s.add(_to_model(memory))
        else:
            existing.name = memory.name
            existing.description = memory.description
            existing.memory_type = memory.memory_type
            existing.content = memory.content
            existing.pinned = memory.pinned
            existing.metadata_ = memory.metadata
            existing.updated_at = memory.updated_at
        await self._s.flush()

    async def get_by_id(self, memory_id: UUID) -> Memory | None:
        m = await self._s.get(MemoryModel, memory_id)
        return _to_domain(m) if m else None

    async def list_candidates(
        self,
        *,
        agent_id: UUID,
        group_id: UUID | None,
        limit: int = 50,
    ) -> list[Memory]:
        if group_id is not None:
            stmt = (
                select(MemoryModel)
                .where(
                    or_(
                        and_(MemoryModel.scope == "group", MemoryModel.group_id == group_id),
                        and_(MemoryModel.scope == "agent", MemoryModel.agent_id == agent_id),
                    )
                )
                .order_by(MemoryModel.pinned.desc(), MemoryModel.updated_at.desc())
                .limit(limit)
            )
        else:
            stmt = (
                select(MemoryModel)
                .where(
                    MemoryModel.agent_id == agent_id,
                    MemoryModel.scope == "agent",
                )
                .order_by(MemoryModel.pinned.desc(), MemoryModel.updated_at.desc())
                .limit(limit)
            )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def list_by_agent(
        self,
        agent_id: UUID,
        *,
        memory_type: str | None = None,
    ) -> list[Memory]:
        stmt = (
            select(MemoryModel)
            .where(MemoryModel.agent_id == agent_id)
            .order_by(MemoryModel.pinned.desc(), MemoryModel.updated_at.desc())
        )
        if memory_type:
            stmt = stmt.where(MemoryModel.memory_type == memory_type)
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def stats_by_agent(self, agent_id: UUID) -> dict:
        stmt = select(
            func.count(MemoryModel.id).label("total"),
            MemoryModel.memory_type,
            func.min(MemoryModel.created_at).label("oldest"),
            func.max(MemoryModel.created_at).label("newest"),
        ).where(MemoryModel.agent_id == agent_id).group_by(MemoryModel.memory_type)

        rows = (await self._s.execute(stmt)).all()
        by_type: dict[str, int] = {}
        total = 0
        oldest = None
        newest = None
        for row in rows:
            by_type[row.memory_type] = row.total
            total += row.total
            if oldest is None or (row.oldest and row.oldest < oldest):
                oldest = row.oldest
            if newest is None or (row.newest and row.newest > newest):
                newest = row.newest
        return {"total": total, "by_type": by_type, "oldest": oldest, "newest": newest}

    async def increment_hits(self, memory_ids: list[UUID]) -> None:
        if not memory_ids:
            return
        stmt = (
            update(MemoryModel)
            .where(MemoryModel.id.in_(memory_ids))
            .values(hits=MemoryModel.hits + 1)
        )
        await self._s.execute(stmt)

    async def delete(self, memory_id: UUID) -> None:
        m = await self._s.get(MemoryModel, memory_id)
        if m:
            await self._s.delete(m)
            await self._s.flush()
