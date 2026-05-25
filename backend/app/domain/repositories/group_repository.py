"""GroupRepository 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.group import Group


class GroupRepository(ABC):
    @abstractmethod
    async def save(self, group: Group) -> None: ...

    @abstractmethod
    async def get_by_id(self, group_id: UUID) -> Group | None: ...

    @abstractmethod
    async def exists_by_name(self, name: str, exclude_id: UUID | None = None) -> bool: ...

    @abstractmethod
    async def list(self) -> list[Group]: ...

    @abstractmethod
    async def update_name(self, group_id: UUID, name: str) -> Group | None: ...

    @abstractmethod
    async def delete(self, group_id: UUID) -> None: ...
