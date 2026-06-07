"""CLI PATH 扫描 API 路由（P1-3）。"""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Query

from app.infrastructure.cli_scanner import DEFAULT_BINS, scan_all

router = APIRouter(prefix="/api/cli", tags=["cli"])

_CACHE_TTL_SECONDS = 3600
_scan_cache: dict[str, tuple[float, list[dict]]] = {}


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
    cache_key = ",".join(names)
    now = time.time()
    cached = _scan_cache.get(cache_key)
    if not refresh and cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        items, ts = cached[1], cached[0]
        return {
            "items": items,
            "scanned_at": ts,
            "next_scan_at": ts + _CACHE_TTL_SECONDS,
            "cached": True,
        }
    results = scan_all(names)
    items = [r.to_dict() for r in results]
    _scan_cache[cache_key] = (now, items)
    return {
        "items": items,
        "scanned_at": now,
        "next_scan_at": now + _CACHE_TTL_SECONDS,
        "cached": False,
    }


@router.post("/scan/refresh")
async def refresh_scan(
    bins: Annotated[str | None, Query()] = None,
) -> dict:
    return await scan_cli(bins=bins, refresh=True)
