"""会话 WebSocket：双向通信 + 流式输出（PRD MVP 功能 2/5，架构 S12）。

协议（客户端 → 服务端）：
    {"type": "message", "content": "...", "mentions": [], "reply_to": null}
协议（服务端 → 客户端）：逐 StreamEvent 推送：
    {"type": "text", "seq": 0, "content": "片段"} ... {"type": "done", ...}
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.application.commands import SendMessageCommand
from app.application.services import ChatService
from app.core.events import get_event_bus
from app.core.exceptions import AgentHubError
from app.domain.enums import DispatchMode
from app.infrastructure.cache.memory_l1 import RedisL1Store
from app.infrastructure.cache.redis_client import get_redis
from app.infrastructure.db.base import session_factory
from app.infrastructure.llm.factory import build_adapter
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresMessageRepository,
    PostgresSessionRepository,
)
from app.infrastructure.ws.connection_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()

_adapter = build_adapter()  # 进程级单例


@router.websocket("/ws/sessions/{session_id}")
async def session_ws(websocket: WebSocket, session_id: UUID) -> None:
    await ws_manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") != "message":
                continue
            await _handle_message(websocket, session_id, data)
    except WebSocketDisconnect:
        await ws_manager.disconnect(session_id, websocket)
    except Exception:  # noqa: BLE001 - 顶层兜底，避免连接悬挂
        logger.exception("WS 处理异常")
        await ws_manager.disconnect(session_id, websocket)


async def _handle_message(ws: WebSocket, session_id: UUID, data: dict) -> None:
    """每条消息开启独立 DB 事务，贯穿流式始终。"""
    cmd = SendMessageCommand(
        session_id=session_id,
        content=data.get("content", ""),
        mentions=data.get("mentions", []),
        reply_to=data.get("reply_to"),
        dispatch_mode=DispatchMode(data.get("dispatch_mode", "auto")),
    )
    async with session_factory() as db:
        chat = ChatService(
            PostgresSessionRepository(db),
            PostgresMessageRepository(db),
            PostgresAgentRepository(db),
            RedisL1Store(get_redis()),
            _adapter,
            get_event_bus(),
        )
        try:
            async for event in chat.send_and_stream(cmd):
                await ws.send_json(event.model_dump(mode="json"))
            await db.commit()
        except AgentHubError as exc:
            await db.rollback()
            await ws.send_json({"type": "error", "seq": -1, "content": str(exc)})
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            logger.exception("流式执行失败")
            await ws.send_json({"type": "error", "seq": -1, "content": str(exc)})
