"""P1-3 CLI PATH 扫描调度器测试（spec 04-commands §6.7 B-5.4-P1-3）。

4 路径：
1. test_cli_scan_first_run — 首次调用 → 调底层 scanner + 写缓存
2. test_cli_scan_cache_hit — 1h 内第二次调用 → 走缓存不重扫
3. test_cli_scan_cache_expired — mock time advance 61min → 重扫
4. test_cli_scan_missing_graceful — 假装某个 CLI bin 不在 → 不抛异常，记录 warning
"""

from __future__ import annotations

import asyncio
import base64
import os
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LLM_ADAPTER_MODE", "mock")
os.environ.setdefault("ENV", "test")

import pytest

from app.infrastructure.cli_scanner import CliScanResult
from app.infrastructure.cli_scheduler import CliScheduler, reset_cli_scheduler


def _fake_result(name: str, available: bool = True) -> CliScanResult:
    return CliScanResult(
        name=name,
        path=f"/usr/bin/{name}" if available else None,
        version=f"{name} 1.0" if available else None,
        available=available,
        error=None if available else f"{name!r} not in PATH",
        last_scan_at=1.0,
    )


def _build_scheduler() -> CliScheduler:
    """新建一个 1s TTL 的 scheduler（测试用，加速 TTL 检查）。"""
    return CliScheduler(interval_seconds=3600, cache_ttl_seconds=1)


# ---------------------------------------------------------------------------
# 路径 1：首次调用 → 调底层 scanner + 写缓存
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cli_scan_first_run() -> None:
    """首次调用 force_refresh 应调底层 scan_all 并把结果写入缓存。"""
    sched = _build_scheduler()
    fake_results = [_fake_result("claude"), _fake_result("codex")]

    with patch("app.infrastructure.cli_scheduler.scan_all", return_value=fake_results) as mock:
        payload = await sched.force_refresh(["claude", "codex"])

    # 1. 底层 scan 被调一次
    mock.assert_called_once()
    # 2. 缓存里命中且内容一致
    assert payload["cached"] is False
    assert len(payload["items"]) == 2
    assert payload["items"][0]["name"] == "claude"
    assert payload["items"][0]["available"] is True
    # 3. now() 同步读缓存 → cached=True
    cached = sched.now(["claude", "codex"])
    assert cached is not None
    assert cached["cached"] is True
    assert len(cached["items"]) == 2
    assert cached["items"][0]["name"] == "claude"


# ---------------------------------------------------------------------------
# 路径 2：1h 内第二次调用 → 走缓存不重扫
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cli_scan_cache_hit() -> None:
    """1h 内第二次 now() 应走缓存，不调底层 scan_all。"""
    sched = CliScheduler(interval_seconds=3600, cache_ttl_seconds=3600)
    fake_results = [_fake_result("claude")]

    with patch("app.infrastructure.cli_scheduler.scan_all", return_value=fake_results) as mock:
        # 首次：force_refresh
        await sched.force_refresh(["claude"])
        assert mock.call_count == 1

        # TTL 内连续 5 次同步读 → 都不应再调 scan
        for _ in range(5):
            cached = sched.now(["claude"])
            assert cached is not None
            assert cached["cached"] is True
        assert mock.call_count == 1  # 仍只 1 次


# ---------------------------------------------------------------------------
# 路径 3：mock time advance 61min → 缓存过期 → 重扫
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cli_scan_cache_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    """缓存过期后 now() 返回 None，force_refresh 重新扫描。"""
    sched = _build_scheduler()  # TTL=1s
    fake_v1 = [_fake_result("claude")]
    fake_v2 = [_fake_result("claude", available=False)]  # 模拟 PATH 变化：丢失

    with patch("app.infrastructure.cli_scheduler.scan_all") as mock:
        mock.side_effect = [fake_v1, fake_v2]

        await sched.force_refresh(["claude"])
        first_cached = sched.now(["claude"])
        assert first_cached is not None
        assert first_cached["items"][0]["available"] is True

        # 推进 monotonic 时间 5s（> TTL=1s）
        base_mono = sched._cache[",".join(["claude"])][0]  # type: ignore[attr-defined]
        monkeypatch.setattr(
            "app.infrastructure.cli_scheduler.time.monotonic",
            lambda: base_mono + 5.0,
        )

        # now() 应感知到过期
        expired = sched.now(["claude"])
        assert expired is None  # 已过期

        # 重新 force_refresh 应再扫一次
        payload = await sched.force_refresh(["claude"])
        assert payload["items"][0]["available"] is False
        assert mock.call_count == 2


# ---------------------------------------------------------------------------
# 路径 4：CLI 缺失 → 不抛异常，记录 warning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cli_scan_missing_graceful(caplog: pytest.LogCaptureFixture) -> None:
    """某个 bin 不在 PATH → scan 完成 + warning log + available=False，不抛异常。"""
    sched = _build_scheduler()
    fake_results = [
        _fake_result("claude", available=True),
        _fake_result("definitely-missing-cli-xyz", available=False),
        _fake_result("codex", available=False),
    ]

    with (
        caplog.at_level("WARNING", logger="app.infrastructure.cli_scheduler"),
        patch("app.infrastructure.cli_scheduler.scan_all", return_value=fake_results),
    ):
        payload = await sched.force_refresh(
            ["claude", "definitely-missing-cli-xyz", "codex"]
        )

    # 1. 不抛异常，payload 正常返回
    assert payload["cached"] is False
    assert len(payload["items"]) == 3
    # 2. 缺失 bin 标记 available=False
    assert payload["items"][1]["available"] is False
    assert "not in PATH" in (payload["items"][1]["error"] or "")
    # 3. warning 至少打了 2 条
    warning_msgs = [r.message for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning_msgs) >= 2
    assert any("definitely-missing-cli-xyz" in m for m in warning_msgs)
    # 4. now() 也能读到这条（即使有缺失也照样缓存，不阻塞）
    cached = sched.now(["claude", "definitely-missing-cli-xyz", "codex"])
    assert cached is not None
    assert cached["items"][1]["available"] is False


# ---------------------------------------------------------------------------
# 附加：lifespan 集成 — start/stop 周期循环
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_scheduler_loop() -> None:
    """start() 启动后台任务，stop() 干净退出（不抛 CancelledError 给调用方）。"""
    sched = CliScheduler(interval_seconds=3600, cache_ttl_seconds=3600)
    fake_results = [_fake_result("claude")]

    with patch("app.infrastructure.cli_scheduler.scan_all", return_value=fake_results):
        sched.start()
        # 让循环至少能跑起来
        await asyncio.sleep(0)
        # 任务存在
        assert sched._task is not None  # type: ignore[attr-defined]
        assert not sched._task.done()  # type: ignore[attr-defined]
        # 停
        await sched.stop()
        assert sched._task is None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 附加：reset_cli_scheduler 单例重置
# ---------------------------------------------------------------------------


def test_reset_cli_scheduler() -> None:
    """reset_cli_scheduler 应清空全局单例，get_cli_scheduler 重新构造。"""
    from app.infrastructure.cli_scheduler import get_cli_scheduler

    s1 = get_cli_scheduler()
    reset_cli_scheduler()
    s2 = get_cli_scheduler()
    assert s1 is not s2
