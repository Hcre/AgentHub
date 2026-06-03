"""WS Event Gateway 测试 fixture (M-A02).

[文件路径] src/agenthub/access/ws_gateway/tests/conftest.py
[文件职责] 共享 pytest fixture：fakeredis stream / socketio test_client / JWT factory
[所属模块] M-A02
[关联设计规范] MD-M-A02 §测试策略
[功能描述]
  功能1: event_loop - asyncio 事件循环
  功能2: fakeredis_stream - 离线队列测试用 fakeredis
  功能3: ws_test_client - socketio AsyncClient（test mode）
  功能4: jwt_factory - 预生成 5 类 JWT token
[来源标注] [DD-M推断:为单元/集成测试提供共享 fixture]
[创建日期] 2026-06-02
[作者] DD-M-A02
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Callable

import fakeredis.aioredis  # type: ignore[import-untyped]
import pytest
import pytest_asyncio
import socketio  # type: ignore[import-untyped]

from agenthub.access.ws_gateway.server import WSServer
from agenthub.core.config import Settings


@pytest.fixture
def event_loop() -> AsyncIterator[asyncio.AbstractEventLoop]:
    """[fixture] event_loop
    [职责] 提供 asyncio 事件循环
    [来源标注] [DD-M推断:标准 fixture]
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def fakeredis_stream() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    """[fixture] fakeredis_stream
    [职责] OfflineQueue 单元测试用 fakeredis
    [来源标注] [DD-001:MD-M-A02 测试 Mock: fakeredis Stream]
    """
    redis = fakeredis.aioredis.FakeRedis()
    yield redis
    await redis.aclose()


@pytest.fixture
def ws_test_client() -> Callable:
    """[fixture] ws_test_client
    [职责] 返回 socketio.AsyncClient 工厂
    [来源标注] [DD-001:MD-M-A02 测试 Mock: socketio test_client]
    """
    def _factory() -> socketio.AsyncClient:
        return socketio.AsyncClient(logger=False, engineio_logger=False)
    return _factory


@pytest.fixture
def jwt_factory() -> Callable[..., str]:
    """[fixture] jwt_factory
    [职责] 生成 5 类 JWT（valid/expired/tampered/wrong-alg/no-sub）
    [来源标注] [DD-001:MD-M-A02 测试数据 5 类 JWT]
    """
    def _make(variant: str = "valid") -> str:
        # 框架占位；具体 payload 由实现者填写
        ...
    return _make
