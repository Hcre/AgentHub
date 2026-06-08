"""Process registry: tracks live subprocesses for graceful shutdown + visible terminal re-spawn.

Module-level singleton dicts:
- _registry: agent_id → list of running subprocesses
- _session_spawn: session_id → last spawn info (cmd, env, cwd, prompt_text)
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import subprocess as sp
import sys

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_registry: dict[str, list[asyncio.subprocess.Process]] = {}
_session_spawn: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def register(agent_id: str, proc: asyncio.subprocess.Process) -> None:
    """Register *proc* under *agent_id* so it gets killed on shutdown."""
    _registry.setdefault(agent_id, []).append(proc)


def unregister(agent_id: str, proc: asyncio.subprocess.Process) -> None:
    """Remove *proc* from *agent_id*; clean up the key if the list is empty."""
    procs = _registry.get(agent_id)
    if procs is None:
        return
    try:
        procs.remove(proc)
    except ValueError:
        return
    if not procs:
        del _registry[agent_id]


def save_spawn_info(
    session_id: str, *, cmd: list[str], env: dict[str, str], cwd: str | None, prompt_text: str
) -> None:
    """记住最后 spawn 的参数，供 visible terminal re-spawn 使用。"""
    _session_spawn[session_id] = dict(
        cmd=list(cmd), env=dict(env), cwd=cwd, prompt_text=prompt_text,
    )


def get_spawn_info(session_id: str) -> dict | None:
    """返回 session 最后一次 spawn 的参数，没有则 None。"""
    return _session_spawn.get(session_id)


async def kill_session(session_id: str) -> bool:
    """找到该 session 关联的所有进程并强制终止。返回是否杀到了进程。"""
    killed_any = False
    for agent_id, procs in list(_registry.items()):
        for proc in list(procs):
            # 通过 spawn info 判断归属
            if session_id in _session_spawn:
                try:
                    if proc.returncode is None:
                        _logger.info("Killing PID %d for session %s", proc.pid, session_id)
                        proc.terminate()
                        try:
                            await asyncio.wait_for(proc.wait(), timeout=2.0)
                        except asyncio.TimeoutError:
                            proc.kill()
                        killed_any = True
                except ProcessLookupError:
                    pass
                except Exception:
                    _logger.debug("kill failed pid=%s", proc.pid, exc_info=True)
    return killed_any


async def kill_all() -> None:
    """Kill every registered subprocess.

    1. ``proc.terminate()`` (SIGTERM / TerminateProcess).
    2. Wait up to 2 s.
    3. Force-kill stragglers: ``taskkill /F /T`` on Windows, ``proc.kill()``
       on Unix.
    4. Log every killed PID.
    5. Clear the registry.
    """
    if not _registry:
        return

    # Snapshot so we can clear the live dict even if something races.
    snapshot: list[tuple[str, asyncio.subprocess.Process]] = []
    for agent_id, procs in _registry.items():
        for proc in procs:
            snapshot.append((agent_id, proc))

    _logger.info("Shutting down %d agent subprocess(es)...", len(snapshot))

    # -- Phase 1: graceful --------------------------------------------------
    for _agent_id, proc in snapshot:
        try:
            proc.terminate()
        except ProcessLookupError:
            continue  # already dead
        except Exception:
            _logger.debug("terminate() failed for pid %s", proc.pid, exc_info=True)

    try:
        await asyncio.wait_for(_wait_all_dead(snapshot), timeout=2.0)
    except asyncio.TimeoutError:
        _logger.debug("Grace period expired; force-killing stragglers")

    # -- Phase 2: force -----------------------------------------------------
    killed: list[int] = []
    is_windows = sys.platform == "win32"

    for _agent_id, proc in snapshot:
        pid = proc.pid
        if pid is None:
            continue
        try:
            if proc.returncode is not None:
                continue  # already exited
        except Exception:
            pass

        if is_windows:
            try:
                sp.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                _logger.debug("taskkill failed for pid %d", pid, exc_info=True)
        else:
            try:
                proc.kill()
            except ProcessLookupError:
                continue
            except Exception:
                _logger.debug("kill() failed for pid %d", pid, exc_info=True)

        killed.append(pid)
        _logger.info("Force-killed PID %d (agent=%s)", pid, _agent_id)

    # -- Phase 3: cleanup ---------------------------------------------------
    _registry.clear()
    _logger.info(
        "Process shutdown complete: %d total / %d force-killed",
        len(snapshot),
        len(killed),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _wait_all_dead(
    procs: list[tuple[str, asyncio.subprocess.Process]],
) -> None:
    """Await ``proc.wait()`` for every process that is still running."""
    for _, proc in procs:
        try:
            if proc.returncode is None:
                await proc.wait()
        except Exception:
            pass  # best-effort


# ---------------------------------------------------------------------------
# atexit best-effort fallback (synchronous bridge)
# ---------------------------------------------------------------------------


def _atexit_handler() -> None:
    """Run ``kill_all()`` synchronously at interpreter exit.

    Best-effort: if the event loop is already closed or running we cannot
    execute the coroutine, so we silently skip.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return  # no event loop in this thread
    if loop.is_closed() or loop.is_running():
        return
    try:
        loop.run_until_complete(kill_all())
    except Exception:
        _logger.debug("atexit kill_all failed", exc_info=True)


atexit.register(_atexit_handler)
