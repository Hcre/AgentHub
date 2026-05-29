"""Redis 异步客户端单例。开发环境自动 fallback 到 fakeredis。"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import settings

_client: aioredis.Redis | None = None
_use_fake: bool | None = None


def _check_real_redis() -> bool:
    """检测真实 Redis 是否可用（一次）。"""
    import socket

    try:
        url = settings.redis_url.replace("redis://", "").split(":")[0].split("/")[0]
        parts = url.rsplit(":", 1) if ":" in url else (url, "6379")
        host, port = parts[0], int(parts[1]) if len(parts) > 1 else 6379
    except Exception:
        host, port = "localhost", 6379
    try:
        s = socket.create_connection((host, port), timeout=1)
        s.close()
        return True
    except OSError:
        return False


def get_redis() -> aioredis.Redis:
    """返回 Redis 客户端（开发环境无 Redis 时自动使用 fakeredis）。"""
    global _client, _use_fake
    if _client is not None:
        return _client

    if _use_fake is None:
        _use_fake = not _check_real_redis()

    if _use_fake:
        import fakeredis.aioredis

        _client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    else:
        _client = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
