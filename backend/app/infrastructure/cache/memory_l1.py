"""L1 短期记忆：Redis 滑动窗口（PRD MVP 功能 6，最近 20 条消息）。

数据结构：Redis List `l1:{session_id}`，append 后 LTRIM 保留最近 N 条。
提供 InMemory 实现用于测试 / 无 Redis 环境。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from uuid import UUID

import redis.asyncio as aioredis

from app.core.config import settings


class L1MemoryStore(ABC):
    """会话级短期记忆滑动窗口。"""

    @abstractmethod
    async def append(self, session_id: UUID, message: dict) -> None: ...

    @abstractmethod
    async def get_window(self, session_id: UUID) -> list[dict]: ...

    @abstractmethod
    async def clear(self, session_id: UUID) -> None: ...


class RedisL1Store(L1MemoryStore):
    def __init__(self, redis: aioredis.Redis, window: int | None = None) -> None:
        self._r = redis
        self._window = window or settings.l1_window_size

    def _key(self, session_id: UUID) -> str:
        return f"l1:{session_id}"

    async def append(self, session_id: UUID, message: dict) -> None:
        key = self._key(session_id)
        await self._r.rpush(key, json.dumps(message, ensure_ascii=False))
        await self._r.ltrim(key, -self._window, -1)

    async def get_window(self, session_id: UUID) -> list[dict]:
        raw = await self._r.lrange(self._key(session_id), 0, -1)
        return [json.loads(item) for item in raw]

    async def clear(self, session_id: UUID) -> None:
        await self._r.delete(self._key(session_id))


class InMemoryL1Store(L1MemoryStore):
    """进程内实现（测试用）。"""

    def __init__(self, window: int | None = None) -> None:
        self._window = window or settings.l1_window_size
        self._data: dict[UUID, deque[dict]] = defaultdict(
            lambda: deque(maxlen=self._window)
        )

    async def append(self, session_id: UUID, message: dict) -> None:
        self._data[session_id].append(message)

    async def get_window(self, session_id: UUID) -> list[dict]:
        return list(self._data[session_id])

    async def clear(self, session_id: UUID) -> None:
        self._data.pop(session_id, None)
