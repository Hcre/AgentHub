"""MemoryService：记忆 CRUD + stats（L3）。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.application.commands import CreateMemoryCommand, UpdateMemoryCommand
from app.core.exceptions import NotFoundError
from app.domain.entities.memory import Memory
from app.domain.repositories.memory_repository import MemoryRepository


def _now() -> datetime:
    return datetime.now(UTC)


class MemoryService:
    def __init__(self, repo: MemoryRepository) -> None:
        self._repo = repo

    async def create(
        self,
        *,
        agent_id: UUID,
        user_id: UUID,
        cmd: CreateMemoryCommand,
    ) -> Memory:
        scope = "group" if cmd.group_id else "agent"
        now = _now()
        memory = Memory(
            id=uuid4(),
            agent_id=agent_id,
            user_id=user_id,
            scope=scope,
            name=cmd.name,
            description=cmd.description,
            memory_type=cmd.memory_type,
            content=cmd.content,
            source=cmd.source,
            pinned=False,
            hits=0,
            metadata=cmd.metadata,
            group_id=cmd.group_id,
            created_at=now,
            updated_at=now,
        )
        await self._repo.save(memory)
        return memory

    async def get(self, memory_id: UUID) -> Memory:
        m = await self._repo.get_by_id(memory_id)
        if m is None:
            raise NotFoundError(f"memory {memory_id}")
        return m

    async def update(self, memory_id: UUID, *, patch: UpdateMemoryCommand) -> Memory:
        m = await self._repo.get_by_id(memory_id)
        if m is None:
            raise NotFoundError(f"memory {memory_id}")
        updated = replace(
            m,
            content=patch.content if patch.content is not None else m.content,
            memory_type=patch.memory_type if patch.memory_type is not None else m.memory_type,
            pinned=patch.pinned if patch.pinned is not None else m.pinned,
            metadata=patch.metadata if patch.metadata is not None else m.metadata,
            updated_at=_now(),
        )
        await self._repo.save(updated)
        return updated

    async def delete(self, memory_id: UUID) -> None:
        await self._repo.delete(memory_id)

    async def list_by_agent(
        self, agent_id: UUID, memory_type: str | None = None
    ) -> list[Memory]:
        return await self._repo.list_by_agent(agent_id, memory_type=memory_type)

    async def stats(self, agent_id: UUID) -> dict:
        return await self._repo.stats_by_agent(agent_id)
