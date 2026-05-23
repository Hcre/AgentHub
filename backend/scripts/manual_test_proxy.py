"""代理模式手动测试：验证 CLI → Proxy → 第三方 API 全链路。

前提：后端已启动（8000 端口），Agent 有 api_key + base_url 配置。

用法：
  cd backend
  python scripts/manual_test_proxy.py
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
    # 先确认 server 在线
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/health")
        r.raise_for_status()
        print("✓ server 在线\n")

    # 1. 创建 claude_code Agent（带 api_key + base_url，代理模式用）
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/api/agents", json={
            "name": f"proxy-test-{uuid4().hex[:6]}",
            "avatar": "🤖",
            "role": "开发助手",
            "agent_system": "claude_code",
            "provider": "anthropic",
            "model": "deepseek-v4-pro",
            "base_url": "https://api.deepseek.com/anthropic",
            "api_key": "sk-your-deepseek-key-here",  # 替换为真实 key
        })
        if r.status_code != 201:
            print(f"创建 Agent 失败: {r.status_code} {r.text}")
            return
        agent = r.json()
        print(f"✓ Agent: {agent['id']}")

        # 2. 创建 session
        r = await c.post(f"{BASE}/api/sessions", json={
            "type": "private", "agent_id": agent["id"], "title": "代理模式测试",
        })
        r.raise_for_status()
        session = r.json()
        print(f"✓ Session: {session['id']}\n")

    # 3. WebSocket 对话
    sid = session["id"]
    async with websockets.connect(f"ws://{HOST}:{PORT}/ws/sessions/{sid}") as ws:
        print(">>> 发送: 用一句话介绍你自己\n")
        await ws.send(json.dumps({"type": "message", "content": "用一句话介绍你自己"}))
        while True:
            evt = json.loads(await ws.recv())
            t = evt.get("type")
            if t == "text":
                print(evt.get("content", ""), end="", flush=True)
            elif t == "tool_call":
                tc = evt.get("tool_call", {})
                print(f"\n[TOOL] {tc.get('name')}")
            elif t == "done":
                m = evt.get("metadata", {})
                print(f"\n\n✓ DONE ${m.get('total_cost_usd', 0):.4f} {m.get('duration_ms', 0)}ms")
                break
            elif t == "error":
                print(f"\n✗ ERROR: {evt.get('content')}")
                break
            elif t == "request_approval":
                print(f"\n⚠ APPROVAL: {evt.get('content')}")
                break

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
