"""CLI PATH 扫描调度器（P1-3 / spec 04-commands §6.7 B-5.4-P1-3）。

设计要点：
- 应用启动时调一次 `scan_all`，把结果缓存到内存；后续 HTTP 端点 /api/cli/scan 直接
  读缓存，秒级响应。
- 后台 asyncio 任务每 1h 触发一次 scan，保持缓存新鲜（TTL 1h，与原路由常量一致）。
- 缓存按 bins 名列表分桶（key = ",".join(names)），与路由协议保持一致。
- 优雅降级：单个 bin 缺失或探测失败 → warning log，不抛出；整个 scan 永不阻塞应用启动。
- 引用 `claude_code_process_pool.sweeper` 模式：模块级单例 + `asyncio.create_task`。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

from app.infrastructure.cli_scanner import DEFAULT_BINS, scan_all

logger = logging.getLogger(__name__)

# 缓存 TTL 1h（与 api/routers/cli.py 保持一致）
CACHE_TTL_SECONDS = 3600
# 周期扫描间隔 1h（每 60min 刷新一次，避免 PATH 变化滞后）
SCAN_INTERVAL_SECONDS = 3600


class CliScheduler:
    """CLI PATH 扫描调度器：startup 立即扫一次 + 后台每 1h 扫一次。"""

    def __init__(
        self,
        interval_seconds: int = SCAN_INTERVAL_SECONDS,
        cache_ttl_seconds: int = CACHE_TTL_SECONDS,
        bins: tuple[str, ...] = DEFAULT_BINS,
    ) -> None:
        self._interval = interval_seconds
        self._ttl = cache_ttl_seconds
        self._bins = bins
        # cache_key → (scanned_at_monotonic, scanned_at_wallclock, items)
        self._cache: dict[str, tuple[float, float, list[dict[str, Any]]]] = {}
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        # 启动时是否已做过一次 scan（用于 now() 决定是否同步补扫）
        self._initialized = False

    def _cache_key(self, names: tuple[str, ...] | list[str]) -> str:
        return ",".join(names)

    async def _scan_once(self, names: tuple[str, ...] | list[str]) -> list[dict[str, Any]]:
        """执行一次扫描；永不抛异常。"""
        results = await asyncio.to_thread(scan_all, tuple(names), timeout=3.0)
        items = [r.to_dict() for r in results]
        for item in items:
            if not item.get("available"):
                logger.warning(
                    "CliScheduler: bin %r 缺失 (error=%s)",
                    item.get("name"),
                    item.get("error"),
                )
        return items

    async def _refresh_cache(self, names: tuple[str, ...] | list[str]) -> None:
        """扫描并写入缓存（线程安全）。"""
        key = self._cache_key(names)
        try:
            items = await self._scan_once(names)
        except Exception:  # 永远不阻塞 scheduler 循环
            logger.exception("CliScheduler: scan_once 异常，保留旧缓存")
            return
        async with self._lock:
            self._cache[key] = (time.monotonic(), time.time(), items)
        logger.info(
            "CliScheduler: 缓存刷新 bins=%s available=%d/%d",
            key,
            sum(1 for it in items if it.get("available")),
            len(items),
        )

    async def startup_scan(self) -> None:
        """启动时同步触发一次 scan（lifespan startup 调用），阻塞直到首次完成。

        失败不抛（外层 try 包裹），保证 app 启动不被阻塞。
        """
        await self._refresh_cache(self._bins)
        self._initialized = True

    def start(self) -> None:
        """启动后台周期扫描任务（lifespan startup 调用）。"""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop(), name="cli_scheduler")
        logger.info(
            "CliScheduler: 后台循环启动 interval=%ds bins=%s",
            self._interval,
            ",".join(self._bins),
        )

    async def stop(self) -> None:
        """停止后台循环（lifespan shutdown 调用）。"""
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await self._task
        self._task = None
        logger.info("CliScheduler: 后台循环停止")

    async def _loop(self) -> None:
        """周期循环：sleep interval → refresh → 重复。"""
        try:
            while True:
                await asyncio.sleep(self._interval)
                await self._refresh_cache(self._bins)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("CliScheduler: 后台循环异常退出")
            raise

    def now(
        self,
        names: tuple[str, ...] | list[str] | None = None,
        *,
        refresh: bool = False,
    ) -> dict[str, Any] | None:
        """读取当前缓存（同步，安全从任何上下文调用）。

        - `refresh=True`：返回 None，让调用方走 HTTP 手动刷新路径。
        - 缓存未命中：返回 None（首启动 race 时调用方应自己兜底）。
        """
        if refresh:
            return None
        target = tuple(names) if names is not None else self._bins
        key = self._cache_key(target)
        entry = self._cache.get(key)
        if entry is None:
            return None
        mono_ts, wall_ts, items = entry
        # 用 monotonic 差值计算 TTL，避免系统时钟回拨
        if (time.monotonic() - mono_ts) >= self._ttl:
            return None
        return {
            "items": items,
            "scanned_at": wall_ts,
            "next_scan_at": wall_ts + (self._ttl - (time.monotonic() - mono_ts)),
            "cached": True,
        }

    async def force_refresh(
        self, names: tuple[str, ...] | list[str] | None = None
    ) -> dict[str, Any]:
        """强制刷新缓存并返回结果。"""
        target = tuple(names) if names is not None else self._bins
        await self._refresh_cache(target)
        entry = self._cache.get(self._cache_key(target))
        assert entry is not None
        _, wall_ts, items = entry
        return {
            "items": items,
            "scanned_at": wall_ts,
            "next_scan_at": wall_ts + self._ttl,
            "cached": False,
        }

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def interval_seconds(self) -> int:
        return self._interval

    @property
    def cache_ttl_seconds(self) -> int:
        return self._ttl

    def clear_cache(self) -> None:
        """测试辅助：清空缓存。"""
        self._cache.clear()
        self._initialized = False


# --- 全局单例（与 claude_code_process_pool 模式一致） ---


_GLOBAL: CliScheduler | None = None


def get_cli_scheduler() -> CliScheduler:
    """全局 CliScheduler 单例。"""
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = CliScheduler()
    return _GLOBAL


def reset_cli_scheduler() -> None:
    """测试辅助：清空全局单例。"""
    global _GLOBAL
    _GLOBAL = None


async def startup_cli_scheduler() -> None:
    """lifespan startup 调用：先立即扫一次（best-effort），再启后台循环。"""
    sched = get_cli_scheduler()
    try:
        await sched.startup_scan()
    except Exception:  # 启动期绝不阻塞
        logger.exception("CliScheduler: startup_scan 失败，app 继续启动")
    sched.start()


async def shutdown_cli_scheduler() -> None:
    """lifespan shutdown 调用：停后台循环。"""
    sched = get_cli_scheduler()
    await sched.stop()
