"""InMemoryWatermarkStore 单元测试（Redis 实现行为相同，由集成测试覆盖）。"""

from __future__ import annotations

import uuid

import pytest

from app.infrastructure.cache.watermark_store import InMemoryWatermarkStore


@pytest.mark.asyncio
async def test_get_miss_returns_none() -> None:
    s = InMemoryWatermarkStore()
    assert await s.get(uuid.uuid4(), uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_set_then_get_roundtrip() -> None:
    s = InMemoryWatermarkStore()
    g, a, m = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await s.set(g, a, m)
    assert await s.get(g, a) == m


@pytest.mark.asyncio
async def test_set_overwrites_previous() -> None:
    s = InMemoryWatermarkStore()
    g, a = uuid.uuid4(), uuid.uuid4()
    m1, m2 = uuid.uuid4(), uuid.uuid4()
    await s.set(g, a, m1)
    await s.set(g, a, m2)
    assert await s.get(g, a) == m2


@pytest.mark.asyncio
async def test_delete_single() -> None:
    s = InMemoryWatermarkStore()
    g, a, m = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await s.set(g, a, m)
    await s.delete(g, a)
    assert await s.get(g, a) is None


@pytest.mark.asyncio
async def test_delete_by_group_cascade() -> None:
    s = InMemoryWatermarkStore()
    g1, g2 = uuid.uuid4(), uuid.uuid4()
    a1, a2 = uuid.uuid4(), uuid.uuid4()
    await s.set(g1, a1, uuid.uuid4())
    await s.set(g1, a2, uuid.uuid4())
    await s.set(g2, a1, uuid.uuid4())

    await s.delete_by_group(g1)
    assert await s.get(g1, a1) is None
    assert await s.get(g1, a2) is None
    # 不影响其他 group
    assert await s.get(g2, a1) is not None


@pytest.mark.asyncio
async def test_delete_by_agent_cascade() -> None:
    s = InMemoryWatermarkStore()
    g1, g2 = uuid.uuid4(), uuid.uuid4()
    target, other = uuid.uuid4(), uuid.uuid4()
    await s.set(g1, target, uuid.uuid4())
    await s.set(g2, target, uuid.uuid4())
    await s.set(g1, other, uuid.uuid4())

    await s.delete_by_agent(target)
    assert await s.get(g1, target) is None
    assert await s.get(g2, target) is None
    # 同群其他 Agent 不受影响
    assert await s.get(g1, other) is not None
