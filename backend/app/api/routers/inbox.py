"""收件箱路由（架构 §4.6）。MVP 骨架：审批流 + 通知在 M4 实现。"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


@router.get("")
async def list_inbox() -> dict:
    # TODO(M4): 审批/任务/日历分类 + 未读计数
    return {"items": [], "unread_count": 0, "note": "收件箱在 M4 实现"}


@router.get("/unread-count")
async def unread_count() -> dict:
    return {"unread_count": 0}
