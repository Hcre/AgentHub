"""ClaudeAdapter：Anthropic Messages API 流式实现（MVP 功能 4）。

claude_cli 模式（调用本地 claude CLI 子进程）在 M2 补充；
此处先实现 anthropic_api 模式。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from app.domain.llm.protocol import (
    AgentRequest,
    StreamEvent,
    StreamEventType,
    UnifiedAgent,
)


class ClaudeAdapter(UnifiedAgent):
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        seq = 0
        kwargs: dict = {
            "model": self._model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": request.messages,
        }
        if request.system_prompt:
            kwargs["system"] = request.system_prompt

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield StreamEvent(
                    type=StreamEventType.TEXT, seq=seq, content=text
                )
                seq += 1
            final = await stream.get_final_message()

        yield StreamEvent(
            type=StreamEventType.DONE,
            seq=seq,
            metadata={
                "model": self._model,
                "token_usage": final.usage.output_tokens,
            },
        )

    async def chat_structured(self, prompt: str) -> dict:
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text if resp.content else "{}"
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"tasks": [], "rationale": text}
