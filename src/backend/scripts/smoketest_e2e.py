# ruff: noqa: T201
"""E2E Smoketest — 全链路验证脚本。

用法:
    cd src/backend
    python scripts/smoketest_e2e.py

验证步骤:
    1. Health check
    2. 创建 Agent
    3. 创建 Session
    4. WebSocket 发送消息
    5. 收到 AI 回复（text/done/error）
    6. 清理

退出码: 0=全部通过, 1=至少一项失败
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from uuid import uuid4

import httpx
import websockets

BASE = os.getenv("AGENTHUB_BASE", "http://127.0.0.1:8000")
WS_BASE = BASE.replace("http://", "ws://")

PASS = 0
FAIL = 0


def check(step: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  OK {step}")
    else:
        FAIL += 1
        print(f"  FAIL {step}  {detail}")


async def main() -> int:
    global PASS, FAIL
    print(f"Smoketest → {BASE}\n")

    # ── 1. Health ──────────────────────────────────────────
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE}/health")
        check("Health", r.status_code == 200 and r.json()["status"] == "ok")

    # ── 2. 创建 Agent ──────────────────────────────────────
    agent_id: str | None = None
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{BASE}/api/agents",
            json={
                "name": f"smoketest-{uuid4().hex[:6]}",
                "avatar": "🧪",
                "role": "测试",
                "agent_system": "claude_code",
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
            },
        )
        check("Agent 创建", r.status_code == 201, r.text[:100])
        if r.status_code == 201:
            agent_id = r.json()["id"]
            print(f"    agent_id={agent_id}")

    if not agent_id:
        print("\n  ⚠ Agent 创建失败，终止")
        return 1

    # ── 3. 创建 Session ────────────────────────────────────
    session_id: str | None = None
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{BASE}/api/sessions",
            json={"type": "private", "agent_id": agent_id, "title": "smoketest"},
        )
        check("Session 创建", r.status_code < 500, r.text[:100])
        if r.status_code < 500:
            session_id = r.json()["id"]
            print(f"    session_id={session_id}")

    if not session_id:
        print("\n  ⚠ Session 创建失败，终止")
        return 1

    # ── 4. WebSocket E2E ──────────────────────────────────
    ws_url = f"{WS_BASE}/ws/sessions/{session_id}"
    received_text = False
    received_done = False
    received_error = False
    error_content = ""

    try:
        async with websockets.connect(ws_url, max_size=10 * 1024 * 1024) as ws:
            # 发消息
            await ws.send(json.dumps({"type": "message", "content": "用一句话介绍你自己"}))
            print("    → 已发送消息，等待回复...")

            # 等回复（最多 60s）
            deadline = asyncio.get_event_loop().time() + 60
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                except TimeoutError:
                    print("    ⚠ 10s 无响应，继续等待...")
                    continue

                try:
                    evt = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                t = evt.get("type", "")
                if t == "text":
                    received_text = True
                    content = evt.get("content", "")[:80]
                    print(f"    ← text: {content}")
                elif t == "done":
                    received_done = True
                    print("    ← done")
                    break
                elif t == "error":
                    received_error = True
                    error_content = evt.get("content", "")[:200]
                    print(f"    ← error: {error_content}")
                    break

    except (OSError, TimeoutError, websockets.WebSocketException) as e:
        check("WS 连接", False, str(e)[:100])
        return 1

    check("收到 text", received_text)
    check("收到 done", received_done, "未完成" if not received_done else "")
    check("无 error", not received_error, error_content)

    # ── 5. 清理 ───────────────────────────────────────────
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.delete(f"{BASE}/api/agents/{agent_id}")
        check("清理 Agent", r.status_code < 500)

    # ── 结果 ──────────────────────────────────────────────
    total = PASS + FAIL
    print(f"\n{'=' * 40}")
    print(f"结果: {PASS}/{total} 通过")
    if FAIL > 0:
        print(f"      {FAIL}/{total} 失败")
    print(f"{'=' * 40}")

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
