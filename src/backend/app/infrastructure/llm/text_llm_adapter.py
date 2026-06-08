"""TextLLM 适配器 — Planner 的 LLM 文本补全实现（Phase 5 §7.2）。

实现 domain/task_engine/ports.py 的 TextLLM Protocol：complete(prompt) -> str。
只做调用，**容错归 Planner**（planner.py 已有 extract_json + 解析重试 + API 退避）。
适配器不得吞错——瞬时错误原样抛出，交 Planner._complete_with_backoff 处理。

两个实现 + 一个工厂：
- AnthropicTextLLM：Anthropic Messages API
- OpenAITextLLM：OpenAI 兼容 chat.completions（DeepSeek/-V1、Groq、vLLM 等）
- build_text_llm()：按 settings.coordinator_provider 选实现
"""

from __future__ import annotations

import anthropic
from openai import AsyncOpenAI

from app.core.config import settings
from app.domain.task_engine.ports import TextLLM

_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


class AnthropicTextLLM:
    """ports.TextLLM 的 Anthropic 实现。非 tool 调用，返回首个 text 块。"""

    def __init__(self, client: anthropic.AsyncAnthropic, model: str) -> None:
        self._client = client
        self._model = model

    async def complete(self, prompt: str) -> str:
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text


class OpenAITextLLM:
    """ports.TextLLM 的 OpenAI 兼容实现（DeepSeek 走 base_url=.../v1）。"""

    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    async def complete(self, prompt: str) -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""


def build_text_llm() -> TextLLM:
    """按 settings 构造 Planner 的 TextLLM。provider/model/base_url/api_key 全部可配置——
    不锁定任何单一模型或端点（OpenAI 兼容 provider 必须显式指定模型）。"""
    provider = settings.coordinator_provider
    model = settings.coordinator_model

    if provider == "anthropic":
        return AnthropicTextLLM(
            anthropic.AsyncAnthropic(
                api_key=settings.coordinator_api_key or settings.anthropic_api_key
            ),
            model or settings.default_model,
        )

    # OpenAI 兼容（openai / deepseek / groq / vllm …）
    base_url = settings.coordinator_base_url
    if not base_url and provider == "deepseek":
        base_url = _DEEPSEEK_BASE_URL
    key = (
        settings.coordinator_api_key
        or settings.deepseek_api_key
        or settings.openai_api_key
    )
    if not model:
        raise ValueError(
            "coordinator_model 未配置：OpenAI 兼容 provider 必须显式指定模型，禁止硬编码默认"
        )
    client = AsyncOpenAI(api_key=key, base_url=base_url) if base_url else AsyncOpenAI(api_key=key)
    return OpenAITextLLM(client, model)
