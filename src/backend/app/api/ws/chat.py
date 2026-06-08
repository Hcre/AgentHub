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
from app.application.services import ChatService, UsageService
from app.application.services.context_builder import ContextBuilder
from app.application.services.memory_selector import MemorySelector
from app.core.events import get_event_bus
from app.core.exceptions import AgentHubError
from app.domain.enums import DispatchMode
from app.infrastructure.cache.memory_l1 import RedisL1Store
from app.infrastructure.cache.redis_client import get_redis
from app.infrastructure.cache.watermark_store import RedisWatermarkStore
from app.infrastructure.db.base import session_factory
from app.infrastructure.llm.factory import build_adapter
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresGroupRepository,
    PostgresMemoryRepository,
    PostgresMessageRepository,
    PostgresSessionRepository,
    PostgresUsageRepository,
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
    except (WebSocketDisconnect, RuntimeError):
        # RuntimeError: receive_json 在已关闭 WS 上调用（客户端先关）
        await ws_manager.disconnect(session_id, websocket)
    except Exception:
        logger.exception("WS 处理异常")
        await ws_manager.disconnect(session_id, websocket)


async def _handle_message(ws: WebSocket, session_id: UUID, data: dict) -> None:
    """每条消息开启独立 DB 事务，贯穿流式始终。"""
    cmd = SendMessageCommand(
        session_id=session_id,
        content=data.get("content", ""),
        mentions=data.get("mentions", []),
        reply_to=data.get("reply_to_id") or data.get("reply_to"),
        dispatch_mode=DispatchMode(data.get("dispatch_mode", "auto")),
    )
    async with session_factory() as db:
        msg_repo = PostgresMessageRepository(db)
        agent_repo = PostgresAgentRepository(db)
        group_repo = PostgresGroupRepository(db)
        redis = get_redis()
        l1 = RedisL1Store(redis)
        wm = RedisWatermarkStore(redis)
        mem_repo = PostgresMemoryRepository(db)
        mem_selector = MemorySelector(mem_repo)
        ctx = ContextBuilder(msg_repo, agent_repo, l1, wm, memory_selector=mem_selector)
        bus = get_event_bus()
        usage_svc = UsageService(PostgresUsageRepository(db))
        chat = ChatService(
            PostgresSessionRepository(db),
            msg_repo,
            agent_repo,
            group_repo,
            l1,
            wm,
            ctx,
            _adapter,
            bus,
            usage_service=usage_svc,
        )
        try:
            async for event in chat.send_and_stream(cmd):
                await ws.send_json(event.model_dump(mode="json"))
            await db.commit()
        except WebSocketDisconnect:
            # 客户端 mid-stream 关闭：刷新/切走/网络抖动 —— 不算服务端错误，回滚后让外层 while 退出
            await db.rollback()
            logger.info("WS 客户端中途断开，停止 stream session=%s", session_id)
            raise
        except AgentHubError as exc:
            await db.rollback()
            await _safe_send_error(ws, str(exc))
        except Exception as exc:
            await db.rollback()
            logger.exception("流式执行失败")
            await _safe_send_error(ws, str(exc))


async def _safe_send_error(ws: WebSocket, message: str) -> None:
    """尽力把错误送回 WS；客户端已关时静默吞掉。"""
    try:
        await ws.send_json({"type": "error", "seq": -1, "content": message})
    except (WebSocketDisconnect, RuntimeError):
        # RuntimeError: "Cannot call send once a close message has been sent"
        # WebSocketDisconnect: 客户端已关
        pass
