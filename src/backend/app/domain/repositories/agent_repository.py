"""AgentRepository 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.agent import Agent


class AgentRepository(ABC):
    @abstractmethod
    async def save(self, agent: Agent) -> None: ...

    @abstractmethod
    async def get_by_id(self, agent_id: UUID) -> Agent | None: ...

    @abstractmethod
    async def exists_by_name(self, name: str) -> bool: ...

    @abstractmethod
    async def get_by_name(self, name: str) -> Agent | None:
        """按 name 精确查 Agent（@mention 解析用，软删 Agent 不返回）。"""
        ...

    @abstractmethod
    async def list(
        self, *, status: str | None = None, capability: str | None = None
    ) -> list[Agent]: ...

    @abstractmethod
    async def soft_delete(self, agent_id: UUID) -> None: ...
