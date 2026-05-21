"""WebSocket 连接管理器：按 session_id 分组，支持广播。

MVP：单进程内存管理。多副本部署时改为 Redis Pub/Sub 桥接（架构 L1 WS Bridge）。
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, session_id: UUID, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._rooms[session_id].add(ws)

    async def disconnect(self, session_id: UUID, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms[session_id].discard(ws)
            if not self._rooms[session_id]:
                self._rooms.pop(session_id, None)

    async def send(self, ws: WebSocket, payload: dict) -> None:
        await ws.send_json(payload)

    async def broadcast(self, session_id: UUID, payload: dict) -> None:
        """向会话内所有连接广播；失效连接静默丢弃。"""
        dead: list[WebSocket] = []
        for ws in list(self._rooms.get(session_id, set())):
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001 - 连接异常即清理
                dead.append(ws)
        for ws in dead:
            await self.disconnect(session_id, ws)


ws_manager = ConnectionManager()
