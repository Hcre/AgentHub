"""冒烟测试：验证 ClaudeCodeRuntime 多轮对话（resume 机制）。

用法：
  cd backend
  python scripts/smoke_claude_runtime.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.llm.protocol import AgentRequest, StreamEventType
from app.infrastructure.llm.claude_code_runtime import ClaudeCodeRuntime


async def send(runtime: ClaudeCodeRuntime, session_id, prompt: str) -> None:
    """发送一条消息并打印响应。"""
    print(f"\n{'='*50}")
    print(f">>> USER: {prompt}")
    print(f"{'='*50}")

    request = AgentRequest(
        request_id=str(uuid4()),
        session_id=session_id,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )

    async for event in runtime.stream(request):
        if event.type == StreamEventType.TEXT and event.content:
            print(event.content, end="", flush=True)
        elif event.type == StreamEventType.ERROR:
            print(f"\n[ERROR] {event.content}")
        elif event.type == StreamEventType.DONE:
            cost = event.metadata.get("total_cost_usd", 0)
            ms = event.metadata.get("duration_ms", 0)
            print(f"\n[DONE] cost=${cost:.4f}  time={ms}ms")


async def main() -> None:
    runtime = ClaudeCodeRuntime(timeout=60)
    session_id = uuid4()
    print(f"Session ID: {session_id}")

    # 第1轮：新建（resume 找不到 → fallback session-id）
    await send(runtime, session_id, "我叫小明，请记住")

    # 第2轮：resume 已有 session
    await send(runtime, session_id, "我叫什么名字？")

    print("\n\n>>> 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
