"""全链路测试：Claude Code 适配器。

用法：
  Terminal 1: 先启动 server
  Terminal 2: cd backend && python scripts/manual_test_claude.py

流程：创建 agent → 创建 session → WS 多轮对话
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import websockets

HOST = "127.0.0.1"
PORT = 8000
BASE = f"http://{HOST}:{PORT}"


async def main():
    # 1. 创建 agent
    print(">>> 创建 agent (agent_system=claude_code) ...")
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{BASE}/api/agents",
            json={
                "name": f"test-cli-{uuid4().hex[:6]}",
                "avatar": "🤖",
                "role": "开发助手",
                "agent_system": "claude_code",
                "provider": "anthropic",
            },
        )
        r.raise_for_status()
        agent = r.json()
        print(f"Agent: {agent['id']}")

        # 2. 创建 session
        print(">>> 创建 session ...")
        r = await c.post(
            f"{BASE}/api/sessions",
            json={
                "type": "private",
                "agent_id": agent["id"],
                "title": "手动测试",
            },
        )
        r.raise_for_status()
        session = r.json()
        print(f"Session: {session['id']}\n")

    # 3. WebSocket 多轮对话
    sid = session["id"]
    rounds = [
        "用一句话介绍你自己",
        "你上一句说了什么？",
        "谢谢，不用回复",
    ]

    async with websockets.connect(f"ws://{HOST}:{PORT}/ws/sessions/{sid}") as ws:
        for msg in rounds:
            await ws.send(json.dumps({"type": "message", "content": msg}))
            print(f"{'─' * 50}\n>>> {msg}\n")
            while True:
                evt = json.loads(await ws.recv())
                t = evt.get("type")
                if t == "text":
                    print(evt.get("content", ""), end="", flush=True)
                elif t == "tool_call":
                    tc = evt.get("tool_call", {})
                    print(
                        f"\n[TOOL] {tc.get('name')}: {json.dumps(tc.get('arguments', {}), ensure_ascii=False)[:200]}"
                    )
                elif t == "done":
                    m = evt.get("metadata", {})
                    print(
                        f"\n[DONE] ${m.get('total_cost_usd', 0):.4f} {m.get('duration_ms', 0)}ms\n"
                    )
                    break
                elif t == "error":
                    print(f"\n[ERROR] {evt.get('content')}\n")
                    break
                elif t == "request_approval":
                    print(f"\n[APPROVAL] {evt.get('content')}")
                    break
                else:
                    print(f"\n[{t}]")

    print("=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
