"""长驻 Claude CLI 进程池（Phase 1，见 ADR-02）。

设计要点：
- 按 session_key 维护一个 dict
- 同 session_key 并发 spawn 用 per-key 锁防 race；不同 key 并发 spawn 不互相阻塞
- handle 自带 stdin 写入锁，调用方串行使用（CLI stream-json input 是 FIFO）
- 软上限超过仅 warning（提醒配置问题）
- 硬上限触发 LRU 淘汰，防 OOM（Step 3）
- 后台 sweeper 周期扫描 idle handle，超 TTL 淘汰（Step 3）
- shutdown_pool() 由 FastAPI lifespan 调用，干净退出不留孤儿（Step 3）
- 崩溃恢复在 runtime 层处理（Step 2 用 --resume 重 spawn）
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProcessHandle:
    """长驻 CLI 进程句柄。

    一个 handle 对应一个 session_key（私聊 = session_id，群聊 = uuid5(session_id, agent_id)）。
    """

    proc: asyncio.subprocess.Process
    session_key: str
    # 同 handle 上写 stdin 必须串行 —— CLI 的 stream-json input 是 FIFO，
    # 多请求并发会把 JSONL 行交错破坏。
    stdin_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_used: float = field(default_factory=time.monotonic)
    # spawn 时使用的 system_prompt 快照；runtime 用它检测 sp 变化决定是否重 spawn
    # （CLI 的 --system-prompt 只在 spawn 时生效，长驻期间无法热更新）
    spawn_system_prompt: str = ""

    def alive(self) -> bool:
        return self.proc.returncode is None


SpawnFn = Callable[[], Awaitable[asyncio.subprocess.Process]]


class ProcessPool:
    """按 session_key 索引的长驻进程池。"""

    def __init__(
        self,
        soft_max: int = 32,
        hard_max: int = 64,
        idle_ttl_seconds: int = 300,
        idle_sweep_interval: int = 60,
    ) -> None:
        self._handles: dict[str, ProcessHandle] = {}
        # per-key 锁仅在 acquire 创建/重建 handle 时持有，避免同 key 并发 spawn。
        # 不同 key 之间不互锁。
        self._spawn_locks: dict[str, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()
        self._soft_max = soft_max
        self._hard_max = hard_max
        self._idle_ttl = idle_ttl_seconds
        self._idle_sweep_interval = idle_sweep_interval
        self._sweeper_task: asyncio.Task | None = None

    async def acquire(self, session_key: str, spawn: SpawnFn) -> ProcessHandle:
        """返回 session_key 对应的 handle，必要时通过 spawn() 创建。

        调用方负责对 handle.stdin_lock 加锁后再写 stdin。
        """
        # 快路径：handle 存在且 alive 就直接返回，不抢 spawn 锁
        existing = self._handles.get(session_key)
        if existing is not None and existing.alive():
            existing.last_used = time.monotonic()
            return existing

        # 慢路径：进 spawn 锁双检
        spawn_lock = await self._get_spawn_lock(session_key)
        async with spawn_lock:
            handle = self._handles.get(session_key)
            if handle is not None and handle.alive():
                handle.last_used = time.monotonic()
                return handle

            if handle is not None:
                logger.info(
                    "ProcessPool: handle key=%s 已死 (returncode=%s)，重新 spawn",
                    session_key,
                    handle.proc.returncode,
                )
                self._handles.pop(session_key, None)

            if len(self._handles) >= self._soft_max:
                logger.warning(
                    "ProcessPool: 持有 %d 个进程已达软上限 %d (key=%s)",
                    len(self._handles),
                    self._soft_max,
                    session_key,
                )

            # LRU 淘汰：到达硬上限时挤掉最久未用的（Step 2 已保证 --resume 可恢复）
            while len(self._handles) >= self._hard_max:
                victim_key = self._pick_lru_victim()
                if victim_key is None or victim_key == session_key:
                    break  # 没法淘汰自己，放过这一次
                logger.info(
                    "ProcessPool: 硬上限 %d，LRU 淘汰 victim=%s 为 key=%s 让位",
                    self._hard_max,
                    victim_key,
                    session_key,
                )
                victim = self._handles.pop(victim_key, None)
                if victim is not None:
                    await self._terminate(victim)

            proc = await spawn()
            new_handle = ProcessHandle(proc=proc, session_key=session_key)
            self._handles[session_key] = new_handle
            logger.info(
                "ProcessPool: spawn key=%s pid=%s (pool_size=%d)",
                session_key,
                proc.pid,
                len(self._handles),
            )
            return new_handle

    async def drop(self, session_key: str) -> None:
        """显式淘汰并终止一个 handle（崩溃恢复 / 测试 / shutdown 用）。"""
        spawn_lock = await self._get_spawn_lock(session_key)
        async with spawn_lock:
            handle = self._handles.pop(session_key, None)
        if handle is None:
            return
        await self._terminate(handle)
        logger.info("ProcessPool: dropped key=%s", session_key)

    async def shutdown(self) -> None:
        """关闭所有进程（FastAPI lifespan 退出时调用）。"""
        await self.stop_sweeper()
        async with self._registry_lock:
            keys = list(self._handles.keys())
        for key in keys:
            await self.drop(key)

    @property
    def size(self) -> int:
        return len(self._handles)

    # --- Step 3：生命周期 ---

    def start_sweeper(self) -> None:
        """启动 idle TTL 后台扫描任务（FastAPI lifespan startup 调用）。"""
        if self._sweeper_task is not None and not self._sweeper_task.done():
            return
        self._sweeper_task = asyncio.create_task(
            self._idle_sweep_loop(), name="claude_code_pool_sweeper"
        )
        logger.info(
            "ProcessPool: sweeper 启动 ttl=%ds interval=%ds",
            self._idle_ttl,
            self._idle_sweep_interval,
        )

    async def stop_sweeper(self) -> None:
        """停止 sweeper（shutdown 或测试）。"""
        if self._sweeper_task is None:
            return
        self._sweeper_task.cancel()
        try:
            await self._sweeper_task
        except (asyncio.CancelledError, Exception):
            pass
        self._sweeper_task = None

    async def _idle_sweep_loop(self) -> None:
        """周期扫描 _handles，淘汰超过 idle_ttl 的 handle。"""
        try:
            while True:
                await asyncio.sleep(self._idle_sweep_interval)
                await self._sweep_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("ProcessPool: sweeper 异常退出")
            raise

    async def _sweep_once(self) -> int:
        """单轮扫描：返回淘汰数量。"""
        now = time.monotonic()
        stale: list[str] = []
        for key, handle in list(self._handles.items()):
            if not handle.alive():
                stale.append(key)
                continue
            if now - handle.last_used > self._idle_ttl:
                stale.append(key)
        for key in stale:
            handle = self._handles.get(key)
            idle = now - handle.last_used if handle else 0
            logger.info(
                "ProcessPool: idle 淘汰 key=%s idle=%.0fs alive=%s",
                key,
                idle,
                handle.alive() if handle else False,
            )
            await self.drop(key)
        return len(stale)

    def _pick_lru_victim(self) -> str | None:
        """挑 last_used 最早的 key（不区分 alive，dead 也优先淘汰）。"""
        if not self._handles:
            return None
        # dead 优先淘汰
        for key, handle in self._handles.items():
            if not handle.alive():
                return key
        return min(self._handles.items(), key=lambda kv: kv[1].last_used)[0]

    # --- 内部 ---

    async def _get_spawn_lock(self, session_key: str) -> asyncio.Lock:
        async with self._registry_lock:
            lock = self._spawn_locks.get(session_key)
            if lock is None:
                lock = asyncio.Lock()
                self._spawn_locks[session_key] = lock
            return lock

    @staticmethod
    async def _terminate(handle: ProcessHandle) -> None:
        if not handle.alive():
            return
        try:
            if handle.proc.stdin is not None:
                handle.proc.stdin.close()
        except Exception:
            pass
        try:
            handle.proc.terminate()
            await asyncio.wait_for(handle.proc.wait(), timeout=3)
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                handle.proc.kill()
            except ProcessLookupError:
                pass


# --- 全局单例 ---

_GLOBAL_POOL: ProcessPool | None = None


def get_pool() -> ProcessPool:
    """全局 ProcessPool 单例。"""
    global _GLOBAL_POOL
    if _GLOBAL_POOL is None:
        from app.core.config import settings

        _GLOBAL_POOL = ProcessPool(
            soft_max=settings.claude_code_pool_soft_max,
            hard_max=settings.claude_code_pool_hard_max,
            idle_ttl_seconds=settings.claude_code_idle_ttl_seconds,
            idle_sweep_interval=settings.claude_code_idle_sweep_interval,
        )
    return _GLOBAL_POOL


def start_pool_sweeper() -> None:
    """FastAPI lifespan startup 调用，启动 idle 扫描任务。"""
    get_pool().start_sweeper()


async def shutdown_pool() -> None:
    """FastAPI lifespan shutdown 调用，停 sweeper + 清理所有子进程。"""
    global _GLOBAL_POOL
    if _GLOBAL_POOL is not None:
        await _GLOBAL_POOL.shutdown()
        _GLOBAL_POOL = None
