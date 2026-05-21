"""群组路由（架构 §4.2）。MVP 骨架：群聊 + 协调者在 M3 实现。"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("")
async def list_groups() -> dict:
    # TODO(M3): 创建群组自动生成协调者 + 成员管理
    return {"items": [], "note": "群组与协调者在 M3 实现"}
