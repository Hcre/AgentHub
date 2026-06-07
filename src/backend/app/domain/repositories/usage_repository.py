"""UsageRepository 抽象接口（P1-2）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.usage import UsageRecord, UsageWindow


class UsageRepository(ABC):
    @abstractmethod
    async def save(self, record: UsageRecord) -> None: ...

    @abstractmethod
    async def sum_by_agent(self, agent_id: UUID, window: UsageWindow) -> dict[str, int]: ...

    @abstractmethod
    async def sum_by_session(self, session_id: UUID, window: UsageWindow) -> dict[str, int]: ...

    @abstractmethod
    async def group_by_session(self, agent_id: UUID, window: UsageWindow) -> list[dict]: ...

    @abstractmethod
    async def group_by_agent(self, session_id: UUID, window: UsageWindow) -> list[dict]: ...
