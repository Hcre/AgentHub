"""ProcessPool 单元测试（Phase 1 Step 1-3）。"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.llm.claude_code_process_pool import (
    ProcessHandle,
    ProcessPool,
)


def _fake_proc(pid: int, alive: bool = True) -> MagicMock:
    p = MagicMock()
    p.returncode = None if alive else 0
    p.pid = pid
    p.stdin = MagicMock()
    p.terminate = MagicMock()
    p.kill = MagicMock()
    p.wait = AsyncMock(return_value=0)
    return p


def _spawn_factory(proc: MagicMock):
    async def _spawn():
        return proc
    return _spawn


class TestAcquireBasics:
    @pytest.mark.asyncio
    async def test_acquire_creates_handle(self) -> None:
        pool = ProcessPool()
        proc = _fake_proc(100)
        h = await pool.acquire("k1", _spawn_factory(proc))
        assert h.proc is proc
        assert h.session_key == "k1"
        assert pool.size == 1

    @pytest.mark.asyncio
    async def test_acquire_returns_cached_alive(self) -> None:
        pool = ProcessPool()
        proc = _fake_proc(100)
        h1 = await pool.acquire("k1", _spawn_factory(proc))

        # 第二次 acquire 不应再 spawn
        called = []
        async def _other_spawn():
            called.append(1)
            return _fake_proc(200)
        h2 = await pool.acquire("k1", _other_spawn)
        assert h2 is h1
        assert called == []  # 没调 spawn

    @pytest.mark.asyncio
    async def test_dead_handle_triggers_respawn(self) -> None:
        pool = ProcessPool()
        dead = _fake_proc(100, alive=False)
        # 手动塞个 dead handle
        pool._handles["k1"] = ProcessHandle(proc=dead, session_key="k1")

        fresh = _fake_proc(200)
        h = await pool.acquire("k1", _spawn_factory(fresh))
        assert h.proc is fresh

    @pytest.mark.asyncio
    async def test_concurrent_acquire_same_key_spawns_once(self) -> None:
        """同 key 并发 acquire 只 spawn 一次（per-key 锁）。"""
        pool = ProcessPool()
        spawn_count = 0

        async def _slow_spawn():
            nonlocal spawn_count
            spawn_count += 1
            await asyncio.sleep(0.05)
            return _fake_proc(100 + spawn_count)

        handles = await asyncio.gather(
            pool.acquire("k1", _slow_spawn),
            pool.acquire("k1", _slow_spawn),
            pool.acquire("k1", _slow_spawn),
        )
        assert spawn_count == 1
        # 三个 handle 应该是同一个对象
        assert handles[0] is handles[1] is handles[2]


class TestLruEviction:
    @pytest.mark.asyncio
    async def test_hard_max_evicts_lru(self) -> None:
        pool = ProcessPool(soft_max=2, hard_max=2)
        for i in range(3):
            await pool.acquire(f"k{i}", _spawn_factory(_fake_proc(100 + i)))
        # k0 是最早创建的，应被淘汰
        assert "k0" not in pool._handles
        assert pool.size == 2

    @pytest.mark.asyncio
    async def test_lru_prefers_dead_handle(self) -> None:
        pool = ProcessPool()
        pool._handles["alive"] = ProcessHandle(
            proc=_fake_proc(100), session_key="alive"
        )
        pool._handles["dead"] = ProcessHandle(
            proc=_fake_proc(200, alive=False), session_key="dead"
        )
        # alive 创建得晚但 dead 应优先
        assert pool._pick_lru_victim() == "dead"


class TestIdleSweep:
    @pytest.mark.asyncio
    async def test_sweep_evicts_stale(self) -> None:
        pool = ProcessPool(idle_ttl_seconds=1, idle_sweep_interval=999)
        await pool.acquire("fresh", _spawn_factory(_fake_proc(100)))
        await pool.acquire("stale", _spawn_factory(_fake_proc(200)))
        pool._handles["stale"].last_used = time.monotonic() - 10

        swept = await pool._sweep_once()
        assert swept == 1
        assert "fresh" in pool._handles
        assert "stale" not in pool._handles

    @pytest.mark.asyncio
    async def test_sweep_evicts_dead_even_if_recent(self) -> None:
        pool = ProcessPool(idle_ttl_seconds=999)
        dead = _fake_proc(100, alive=False)
        pool._handles["d"] = ProcessHandle(proc=dead, session_key="d")
        pool._handles["d"].last_used = time.monotonic()  # 不老

        swept = await pool._sweep_once()
        assert swept == 1
        assert "d" not in pool._handles

    @pytest.mark.asyncio
    async def test_start_stop_sweeper(self) -> None:
        pool = ProcessPool(idle_sweep_interval=10)
        pool.start_sweeper()
        assert pool._sweeper_task is not None
        assert not pool._sweeper_task.done()
        await pool.stop_sweeper()
        assert pool._sweeper_task is None


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_clears_pool(self) -> None:
        pool = ProcessPool()
        for i in range(3):
            await pool.acquire(f"k{i}", _spawn_factory(_fake_proc(100 + i)))
        assert pool.size == 3

        await pool.shutdown()
        assert pool.size == 0

    @pytest.mark.asyncio
    async def test_shutdown_stops_sweeper(self) -> None:
        pool = ProcessPool(idle_sweep_interval=10)
        pool.start_sweeper()
        await pool.shutdown()
        assert pool._sweeper_task is None
