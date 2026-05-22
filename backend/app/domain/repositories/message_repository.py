"""MessageRepository 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.message import Message


class MessageRepository(ABC):
    @abstractmethod
    async def save(self, message: Message) -> None: ...

    @abstractmethod
    async def get_by_id(self, message_id: UUID) -> Message | None: ...

    @abstractmethod
    async def list_by_session(
        self, session_id: UUID, *, before: UUID | None = None, limit: int = 50
    ) -> list[Message]:
        """按时间倒序分页拉取会话历史。"""
        ...

    @abstractmethod
    async def set_pinned(self, message_id: UUID, pinned: bool) -> None: ...

    @abstractmethod
    async def delete(self, message_id: UUID) -> None: ...
