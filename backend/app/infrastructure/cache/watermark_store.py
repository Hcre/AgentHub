"""群聊 Watermark：跟踪每 Agent 在群里上次接触到第几条消息（增量注入用）。

设计见 docs/design/group-chat_群聊功能设计方案.md §3.4。

Key: wm:{group_id}:{agent_id} → message_id (UUID string)
TTL: settings.watermark_ttl_seconds (默认 7 天)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

import redis.asyncio as aioredis

from app.core.config import settings


class WatermarkStore(ABC):
    """每 Agent 在群里的进度指针。"""

    @abstractmethod
    async def get(self, group_id: UUID, agent_id: UUID) -> UUID | None: ...

    @abstractmethod
    async def set(self, group_id: UUID, agent_id: UUID, message_id: UUID) -> None: ...

    @abstractmethod
    async def delete(self, group_id: UUID, agent_id: UUID) -> None: ...

    @abstractmethod
    async def delete_by_group(self, group_id: UUID) -> None: ...

    @abstractmethod
    async def delete_by_agent(self, agent_id: UUID) -> None: ...


class RedisWatermarkStore(WatermarkStore):
    """Redis 实现：原子 SET + TTL。

    Note:
        delete_by_group / delete_by_agent 用 SCAN 模式匹配，按需迭代删除。
        生产规模下群×Agent 数 << 万级，SCAN 成本可接受。
    """

    def __init__(self, redis: aioredis.Redis, ttl: int | None = None) -> None:
        self._r = redis
        self._ttl = ttl if ttl is not None else settings.watermark_ttl_seconds

    @staticmethod
    def _key(group_id: UUID, agent_id: UUID) -> str:
        return f"wm:{group_id}:{agent_id}"

    async def get(self, group_id: UUID, agent_id: UUID) -> UUID | None:
        raw = await self._r.get(self._key(group_id, agent_id))
        return UUID(raw) if raw else None

    async def set(self, group_id: UUID, agent_id: UUID, message_id: UUID) -> None:
        await self._r.set(self._key(group_id, agent_id), str(message_id), ex=self._ttl)

    async def delete(self, group_id: UUID, agent_id: UUID) -> None:
        await self._r.delete(self._key(group_id, agent_id))

    async def delete_by_group(self, group_id: UUID) -> None:
        pattern = f"wm:{group_id}:*"
        async for key in self._r.scan_iter(match=pattern, count=100):
            await self._r.delete(key)

    async def delete_by_agent(self, agent_id: UUID) -> None:
        pattern = f"wm:*:{agent_id}"
        async for key in self._r.scan_iter(match=pattern, count=100):
            await self._r.delete(key)


class InMemoryWatermarkStore(WatermarkStore):
    """进程内实现（测试用）。"""

    def __init__(self) -> None:
        self._data: dict[tuple[UUID, UUID], UUID] = {}

    async def get(self, group_id: UUID, agent_id: UUID) -> UUID | None:
        return self._data.get((group_id, agent_id))

    async def set(self, group_id: UUID, agent_id: UUID, message_id: UUID) -> None:
        self._data[(group_id, agent_id)] = message_id

    async def delete(self, group_id: UUID, agent_id: UUID) -> None:
        self._data.pop((group_id, agent_id), None)

    async def delete_by_group(self, group_id: UUID) -> None:
        keys_to_drop = [k for k in self._data if k[0] == group_id]
        for k in keys_to_drop:
            self._data.pop(k, None)

    async def delete_by_agent(self, agent_id: UUID) -> None:
        keys_to_drop = [k for k in self._data if k[1] == agent_id]
        for k in keys_to_drop:
            self._data.pop(k, None)
