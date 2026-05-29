"""L1 滑动窗口记忆单测（PRD MVP 功能 6）。"""

from uuid import uuid4

import pytest

from app.infrastructure.cache.memory_l1 import InMemoryL1Store


@pytest.mark.asyncio
async def test_window_keeps_last_n() -> None:
    store = InMemoryL1Store(window=3)
    sid = uuid4()
    for i in range(5):
        await store.append(sid, {"role": "user", "content": str(i)})
    window = await store.get_window(sid)
    assert len(window) == 3
    assert [m["content"] for m in window] == ["2", "3", "4"]


@pytest.mark.asyncio
async def test_clear() -> None:
    store = InMemoryL1Store(window=10)
    sid = uuid4()
    await store.append(sid, {"role": "user", "content": "hi"})
    await store.clear(sid)
    assert await store.get_window(sid) == []
