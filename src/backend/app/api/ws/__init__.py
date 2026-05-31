"""WebSocket 端点。"""

from fastapi import APIRouter

from app.api.ws.chat import router as chat_router
from app.api.ws.runner import router as runner_router

router = APIRouter()
router.include_router(chat_router)
router.include_router(runner_router)

__all__ = ["router"]
