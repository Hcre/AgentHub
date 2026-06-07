"""CLI PATH 扫描 API 路由（P1-3）。

数据源 = `app.infrastructure.cli_scheduler.CliScheduler`（lifespan startup 立即扫一次 +
后台每 1h 扫一次），路由只读取调度器缓存，未命中时再同步补一次（兜底）。
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Query

from app.infrastructure.cli_scanner import DEFAULT_BINS
from app.infrastructure.cli_scheduler import get_cli_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cli", tags=["cli"])


def _parse_bins(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_BINS)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts or list(DEFAULT_BINS)


@router.get("/scan")
async def scan_cli(
    bins: Annotated[str | None, Query()] = None,
    refresh: Annotated[bool, Query()] = False,
) -> dict:
    names = _parse_bins(bins)
    sched = get_cli_scheduler()

    if refresh:
        return await sched.force_refresh(names)

    cached = sched.now(names)
    if cached is not None:
        return cached

    # 兜底：scheduler 未启动（如测试场景或 lifespan 异常）→ 同步补一次
    logger.debug("cli /scan cache miss → 同步补扫 bins=%s", names)
    return await sched.force_refresh(names)


@router.post("/scan/refresh")
async def refresh_scan(
    bins: Annotated[str | None, Query()] = None,
) -> dict:
    return await scan_cli(bins=bins, refresh=True)
