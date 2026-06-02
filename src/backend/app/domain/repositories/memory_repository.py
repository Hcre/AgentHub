"""MemoryRepository 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.memory import Memory


class MemoryRepository(ABC):
    @abstractmethod
    async def save(self, memory: Memory) -> None: ...

    @abstractmethod
    async def get_by_id(self, memory_id: UUID) -> Memory | None: ...

    @abstractmethod
    async def list_candidates(
        self,
        *,
        agent_id: UUID,
        group_id: UUID | None,
        limit: int = 50,
    ) -> list[Memory]:
        """候选集查询（pinned 优先 + 最近更新）。

        群聊：scope='group' AND group_id=$2 OR scope='agent' AND agent_id=$1
        私聊：group_id=None → 只取 scope='agent' AND agent_id=$1
        """
        ...

    @abstractmethod
    async def list_by_agent(
        self,
        agent_id: UUID,
        *,
        memory_type: str | None = None,
    ) -> list[Memory]: ...

    @abstractmethod
    async def stats_by_agent(self, agent_id: UUID) -> dict:
        """返回 {total, by_type, oldest, newest}。"""
        ...

    @abstractmethod
    async def increment_hits(self, memory_ids: list[UUID]) -> None:
        """批量原子 UPDATE hits = hits + 1。"""
        ...

    @abstractmethod
    async def delete(self, memory_id: UUID) -> None: ...
