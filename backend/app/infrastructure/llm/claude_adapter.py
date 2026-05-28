"""ClaudeAdapter：Anthropic Messages API 流式实现。

支持完整 8 种 StreamEvent 中适配器负责的 5 种：
TEXT / THINKING / TOOL_CALL / ERROR / DONE。

包含：memory 注入 system_prompt、tools 参数传递、指数退避重试。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from anthropic import (
    APIStatusError,
    AsyncAnthropic,
    RateLimitError,
)

from app.domain.llm.protocol import (
    AgentRequest,
    LLMAdapter,
    StreamEvent,
    StreamEventType,
    ToolCall,
)

logger = logging.getLogger(__name__)

# --- 重试常量 ---
_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # 秒
_RETRYABLE = (RateLimitError, APIStatusError)


class ClaudeAdapter(LLMAdapter):
    """Anthropic Messages API 适配器（anthropic_api 模式）。"""

    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncAnthropic(**kwargs)
        self._model = model

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:  # type: ignore[override]
        """流式执行一次 LLM 调用，逐事件 yield。"""
        system_prompt = _build_system_prompt(request)
        messages = request.messages
        tool_defs = _build_tool_definitions(request.available_tools)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": request.max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tool_defs:
            kwargs["tools"] = tool_defs
        # temperature 不能与 thinking 同时设置
        # 当未启用 thinking 时才传 temperature
        kwargs["temperature"] = request.temperature

        seq = 0
        try:
            async for event in self._stream_with_retry(kwargs):
                event_obj = StreamEvent(**{**event, "seq": seq})
                yield event_obj
                seq += 1
        except _RETRYABLE as exc:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=seq,
                content=f"LLM 调用失败（已重试 {_MAX_RETRIES} 次）：{exc}",
            )
            return
        except Exception as exc:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=seq,
                content=f"LLM 调用异常：{exc}",
            )
            return

    async def chat_structured(self, prompt: str) -> dict:
        """非流式结构化调用（协调者任务分解用）。"""
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

    # ------------------------------------------------------------------
    # 内部：带重试的流式调用
    # ------------------------------------------------------------------

    async def _stream_with_retry(self, kwargs: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """带指数退避的流式调用，yield 原始事件 dict。"""
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async for raw in self._do_stream(kwargs):
                    yield raw
                return  # 成功完成
            except _RETRYABLE:
                if attempt == _MAX_RETRIES:
                    raise
                delay = _BASE_DELAY * (2**attempt)
                logger.warning(
                    "Anthropic API 错误，第 %d 次重试，等待 %.1fs",
                    attempt + 1,
                    delay,
                )
                await asyncio.sleep(delay)

    async def _do_stream(self, kwargs: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """单次 Anthropic API 流式调用，解析所有事件类型。"""
        # 收集状态
        current_block_type: str | None = None
        tool_name: str = ""
        tool_call_id: str = ""
        tool_input_chunks: list[str] = []
        usage: dict[str, int] = {}
        stop_reason: str | None = None

        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                event_type = event.type

                # --- content_block_start ---
                if event_type == "content_block_start":
                    block = event.content_block
                    current_block_type = block.type
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_call_id = block.id
                        tool_input_chunks = []
                    continue

                # --- content_block_delta ---
                if event_type == "content_block_delta":
                    delta = event.delta

                    # text delta
                    if delta.type == "text_delta":
                        yield {
                            "type": StreamEventType.TEXT,
                            "content": delta.text,
                        }
                        continue

                    # thinking delta
                    if delta.type == "thinking_delta":
                        yield {
                            "type": StreamEventType.THINKING,
                            "content": delta.thinking,
                        }
                        continue

                    # tool input JSON delta
                    if delta.type == "input_json_delta":
                        tool_input_chunks.append(delta.partial_json)
                        continue

                    continue

                # --- content_block_stop ---
                if event_type == "content_block_stop":
                    if current_block_type == "tool_use":
                        raw_json = "".join(tool_input_chunks)
                        try:
                            arguments = json.loads(raw_json) if raw_json else {}
                        except json.JSONDecodeError:
                            arguments = {"_raw": raw_json}
                        yield {
                            "type": StreamEventType.TOOL_CALL,
                            "tool_call": ToolCall(
                                call_id=tool_call_id,
                                name=tool_name,
                                arguments=arguments,
                            ),
                        }
                    current_block_type = None
                    continue

                # --- message_delta (usage / stop_reason) ---
                if event_type == "message_delta":
                    if hasattr(event, "usage") and event.usage:
                        usage["output_tokens"] = event.usage.output_tokens
                    if hasattr(event, "delta") and hasattr(event.delta, "stop_reason"):
                        stop_reason = event.delta.stop_reason
                    continue

                # --- message_start (input tokens) ---
                if event_type == "message_start":
                    if hasattr(event, "message") and hasattr(event.message, "usage"):
                        usage["input_tokens"] = event.message.usage.input_tokens
                    continue

            # 流结束 → DONE
            yield {
                "type": StreamEventType.DONE,
                "metadata": {
                    "model": self._model,
                    "token_usage": usage,
                    "stop_reason": stop_reason,
                },
            }


# ======================================================================
# 纯函数：prompt 构建
# ======================================================================


def _build_system_prompt(request: AgentRequest) -> str:
    """合并 agent system_prompt + memory context → 单一 system 字符串。"""
    parts: list[str] = []

    if request.system_prompt:
        parts.append(request.system_prompt)

    if request.memory:
        if request.memory.l3_specs:
            parts.append(f"## Project Context\n{request.memory.l3_specs}")
        if request.memory.l2_summary:
            parts.append(f"## Conversation Summary\n{request.memory.l2_summary}")
        if request.memory.l4_rag:
            parts.append(f"## Relevant Knowledge\n{request.memory.l4_rag}")

    return "\n\n".join(parts)


def _build_tool_definitions(available_tools: list[str]) -> list[dict[str, Any]]:
    """将 available_tools 名称列表转换为 Anthropic tools 参数。

    当前阶段：ToolRegistry 尚未实现，返回空列表。
    M3 实现后，此函数从 ToolRegistry 查询完整 JSON Schema。
    """
    # TODO(M3): 从 ToolRegistry 获取 ToolDefinition 并转为 Anthropic schema
    if not available_tools:
        return []
    # 占位：有 tool 名但无 registry 时，不传 tools 参数，避免 API 报错
    logger.debug("available_tools=%s 但 ToolRegistry 未就绪，跳过", available_tools)
    return []
