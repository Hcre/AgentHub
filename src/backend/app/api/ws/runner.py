"""Runner WebSocket — 宿主机 CLI Runner 连接点。

Backend 通过此 WS 将执行指令发给 Runner，Runner 流式返回 claude 输出。
"""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class RunnerConnectionManager:
    """管理所有连接的 CLI Runner。"""

    def __init__(self) -> None:
        self._runner_ws: WebSocket | None = None
        self._lock = asyncio.Lock()

    @property
    def has_runner(self) -> bool:
        return self._runner_ws is not None

    async def exec(
        self,
        *,
        binary: str,
        args: list[str],
        cwd: str,
        prompt: str,
        env: dict[str, str],
        timeout: float = 300,  # noqa: ASYNC109
    ):
        """通过 Runner 异步执行命令，逐条 yield 响应 dict。"""
        async with self._lock:
            if not self._runner_ws:
                yield {
                    "type": "error",
                    "error": "无可用 Runner，请在宿主机运行 python cli_runner/main.py",
                }
                return

            ws = self._runner_ws
            rid = str(uuid4())
            await ws.send_json(
                {
                    "type": "exec",
                    "request_id": rid,
                    "binary": binary,
                    "args": args,
                    "cwd": cwd,
                    "prompt": prompt,
                    "env": env,
                }
            )

            try:
                while True:
                    raw = await asyncio.wait_for(ws.receive_text(), timeout=timeout)
                    msg = json.loads(raw)
                    if msg.get("request_id") != rid:
                        continue
                    yield msg
                    if msg.get("type") in ("done", "error"):
                        break
            except TimeoutError:
                yield {"type": "error", "error": f"Runner 超时 ({timeout}s)"}
            except (WebSocketDisconnect, RuntimeError):
                self._runner_ws = None
                yield {"type": "error", "error": "Runner 已断开"}


# 全局单例
runner_mgr = RunnerConnectionManager()


@router.websocket("/ws/runner")
async def runner_ws(ws: WebSocket) -> None:
    """CLI Runner 连接端点。"""
    await ws.accept()
    runner_mgr._runner_ws = ws
    logger.info("runner 已连接")

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except (WebSocketDisconnect, RuntimeError):
        runner_mgr._runner_ws = None
        logger.info("runner 已断开")
