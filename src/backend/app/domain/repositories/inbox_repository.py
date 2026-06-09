"""InboxRepository 抽象接口（L2 定义，L1 实现）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.inbox import InboxItem


class InboxRepository(ABC):
    @abstractmethod
    async def save(self, item: InboxItem) -> None: ...

    @abstractmethod
    async def get_by_id(self, item_id: UUID) -> InboxItem | None: ...

    @abstractmethod
    async def list_items(
        self,
        *,
        type_: str | None = None,
        include_resolved: bool = False,
    ) -> list[InboxItem]: ...

    @abstractmethod
    async def unread_count(self) -> int: ...
