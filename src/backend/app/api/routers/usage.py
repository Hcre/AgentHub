"""Token 消耗监控 API 路由（P1-2）。"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_usage_service
from app.application.services import UsageService

router = APIRouter(prefix="/api/usage", tags=["usage"])

ServiceDep = Annotated[UsageService, Depends(get_usage_service)]


@router.get("")
async def get_usage(
    agent_id: UUID | None = Query(default=None),
    session_id: UUID | None = Query(default=None),
    window: str = Query(default="24h", pattern="^(1h|24h|7d)$"),
    svc: ServiceDep = ...,  # type: ignore[assignment]
) -> dict:
    if agent_id is not None and session_id is not None:
        raise HTTPException(
            status_code=422,
            detail="E_USAGE_PARAMS_CONFLICT: agent_id and session_id cannot both be set",
        )
    if agent_id is not None:
        return await svc.aggregate_by_agent(agent_id, window_name=window)
    if session_id is not None:
        return await svc.aggregate_by_session(session_id, window_name=window)
    raise HTTPException(
        status_code=422,
        detail="E_USAGE_PARAMS_MISSING: must pass either agent_id or session_id",
    )


@router.get("/agents/{agent_id}")
async def get_agent_usage(
    agent_id: UUID,
    window: str = Query(default="24h", pattern="^(1h|24h|7d)$"),
    svc: ServiceDep = ...,  # type: ignore[assignment]
) -> dict:
    return await svc.aggregate_by_agent(agent_id, window_name=window)


@router.get("/sessions/{session_id}")
async def get_session_usage(
    session_id: UUID,
    window: str = Query(default="24h", pattern="^(1h|24h|7d)$"),
    svc: ServiceDep = ...,  # type: ignore[assignment]
) -> dict:
    return await svc.aggregate_by_session(session_id, window_name=window)


@router.get("/global")
async def get_global_usage(
    window: str = Query(default="24h", pattern="^(1h|24h|7d)$"),
    top_n: int = Query(default=10, ge=1, le=100),
    svc: ServiceDep = ...,  # type: ignore[assignment]
) -> dict:
    """全平台 Token 聚合（t6 Token 监控 UI 用，1h/24h/7d window + top N agent）。"""
    return await svc.aggregate_global(window_name=window, top_n=top_n)
