"""任务路由（架构 §4.4）。MVP 骨架：完整 FSM/DAG 调度在 M3 实现。"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
async def list_tasks() -> dict:
    # TODO(M3): 接入 TaskService.list_tasks + TaskFilter
    return {"items": [], "total": 0, "note": "任务管理在 M3 实现"}
