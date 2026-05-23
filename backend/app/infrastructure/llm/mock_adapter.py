"""MockAdapter：无 API Key 时跑通全链路（PRD §九 降级策略）。

逐字符流式返回预设响应，便于联调 WS → StreamingText。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.domain.llm.protocol import (
    AgentRequest,
    StreamEvent,
    StreamEventType,
    LLMAdapter,
)


class MockAdapter(LLMAdapter):
    def __init__(self, delay: float = 0.02) -> None:
        self._delay = delay

    async def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        last_user = next(
            (m["content"] for m in reversed(request.messages) if m["role"] == "user"),
            "",
        )
        reply = f"[mock] 已收到：{last_user}。这是一段模拟的流式回复。"
        seq = 0
        for ch in reply:
            yield StreamEvent(type=StreamEventType.TEXT, seq=seq, content=ch)
            seq += 1
            await asyncio.sleep(self._delay)
        yield StreamEvent(
            type=StreamEventType.DONE,
            seq=seq,
            metadata={"model": "mock", "token_usage": len(reply)},
        )

    async def chat_structured(self, prompt: str) -> dict:
        return {
            "tasks": [
                {
                    "title": "示例子任务",
                    "description": "mock 协调者产出",
                    "suggested_worker": "",
                    "depends_on": [],
                }
            ],
            "rationale": "mock decomposition",
        }
