"""SessionRepository 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.session import Session


class SessionRepository(ABC):
    @abstractmethod
    async def save(self, session: Session) -> None: ...

    @abstractmethod
    async def get_by_id(self, session_id: UUID) -> Session | None: ...

    @abstractmethod
    async def list(self, *, type: str | None = None) -> list[Session]: ...
