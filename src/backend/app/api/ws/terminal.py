"""Terminal WebSocket — 实时推送 CLI log 文件内容到前端终端。

协议（服务端 → 客户端）：
    {"type": "waiting", "seq": N}          # 等待文件出现，每 500ms 一个点
    {"type": "init",    "content": "..."}  # 现有全部内容（一次性发送）
    {"type": "delta",   "content": "..."}  # 增量新内容（逐行推送）
    {"type": "error",   "content": "..."}  # 错误信息
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.infrastructure.llm.cli_logger import get_log_path

logger = logging.getLogger(__name__)
router = APIRouter()

WAIT_TIMEOUT = 10.0   # 等待日志文件出现的最大秒数
DOT_INTERVAL = 0.5    # 等待期间发送占位点的间隔秒数
POLL_INTERVAL = 0.1   # 增量轮询间隔秒数


@router.websocket("/ws/sessions/{session_id}/terminal")
async def terminal_ws(websocket: WebSocket, session_id: str) -> None:
    """实时推送 session 的 CLI 日志内容。

    三阶段：
    1. 等待日志文件出现（最多 WAIT_TIMEOUT 秒，期间发 waiting 点）
    2. 发送文件现有全部内容（init）
    3. 轮询增量并逐行推送（delta）
    """
    await websocket.accept()
    log_path = get_log_path(session_id)
    logger.info("Terminal WS connected session=%s path=%s", session_id, log_path)

    # ---- 阶段 1: 等待文件出现 -----------------------------------------------
    t0 = asyncio.get_event_loop().time()
    dot_seq = 0
    last_dot = t0

    while not log_path.exists():
        elapsed = asyncio.get_event_loop().time() - t0
        if elapsed > WAIT_TIMEOUT:
            await _safe_send(
                websocket,
                {"type": "error", "content": f"日志文件未创建（等待 {WAIT_TIMEOUT}s）"},
            )
            logger.warning(
                "Terminal WS timeout waiting for log file session=%s path=%s",
                session_id, log_path,
            )
            return

        now = asyncio.get_event_loop().time()
        if now - last_dot >= DOT_INTERVAL:
            dot_seq += 1
            if not await _safe_send(websocket, {"type": "waiting", "seq": dot_seq}):
                return  # 客户端已断开
            last_dot = now

        await asyncio.sleep(0.1)

    # ---- 阶段 2-3: 发送现有内容 + 轮询增量 --------------------------------
    file_handle = None
    try:
        file_handle = open(log_path, encoding="utf-8", errors="replace")

        # 发送现有全部内容
        existing = file_handle.read()
        if existing:
            if not await _safe_send(websocket, {"type": "init", "content": existing}):
                return

        # 轮询增量（逐行推送）
        while True:
            line = file_handle.readline()
            if line:
                if not await _safe_send(websocket, {"type": "delta", "content": line}):
                    return
            else:
                await asyncio.sleep(POLL_INTERVAL)

    except WebSocketDisconnect:
        logger.info("Terminal WS disconnected session=%s", session_id)
    except RuntimeError:
        # WebSocket 已关闭时 send_json 抛出
        pass
    except OSError as exc:
        logger.error(
            "Terminal WS I/O error session=%s path=%s: %s",
            session_id, log_path, exc,
        )
        await _safe_send(
            websocket,
            {"type": "error", "content": f"读取日志文件出错: {exc}"},
        )
    except Exception:
        logger.exception("Terminal WS error session=%s", session_id)
    finally:
        if file_handle is not None:
            try:
                file_handle.close()
            except OSError:
                pass


async def _safe_send(websocket: WebSocket, payload: dict) -> bool:
    """尽力发送一条 JSON 消息；客户端已断开时返回 False。"""
    try:
        await websocket.send_json(payload)
        return True
    except (WebSocketDisconnect, RuntimeError):
        return False
