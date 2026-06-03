"""MemorySelector：LLM 检索，从候选集选 ≤5 条相关记忆注入 SP。

使用 DeepSeek V4 Flash（OpenAI 兼容接口）做选择，与 Selector 共用同一配置路径。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from openai import AsyncOpenAI

from app.core.config import settings
from app.domain.entities.memory import Memory
from app.domain.repositories.memory_repository import MemoryRepository

logger = logging.getLogger(__name__)

_DEEPSEEK_MODEL = "deepseek-chat"   # DeepSeek V4 Flash
_MAX_CONTEXT_CHARS = 3000
_MSG_MAX_CHARS = 300

_SELECTOR_PROMPT = """\
You are a memory relevance judge. Given a conversation context and a list of \
candidate memories, select up to 5 memories that are DIRECTLY relevant to the \
current conversation.

Current conversation:
{dialogue_context}

Candidate memories:
{candidate_list}

Instructions:
- Only select memories that are clearly relevant to the current conversation.
- If uncertain, skip. Better to miss a relevant memory than to inject noise.
- Pinned memories should be selected UNLESS they are clearly irrelevant.
- Return ONLY the IDs of selected memories, one per line. No other text."""


class MemorySelector:
    def __init__(self, repo: MemoryRepository) -> None:
        self._repo = repo

    async def select_for_agent(
        self,
        *,
        agent_id: UUID,
        group_id: UUID | None,
        dialogue_context: str,
    ) -> list[Memory]:
        """返回 pinned（全选）+ LLM 选中的非 pinned 记忆，并更新 hits。"""
        candidates = await self._repo.list_candidates(agent_id=agent_id, group_id=group_id)
        if not candidates:
            return []

        pinned = [m for m in candidates if m.pinned]
        non_pinned = [m for m in candidates if not m.pinned]

        selected_ids = await self._llm_select(non_pinned, dialogue_context)
        selected_non_pinned = [m for m in non_pinned if m.id in selected_ids]

        result = pinned + selected_non_pinned
        if result:
            await self._repo.increment_hits([m.id for m in result])
        return result

    async def _llm_select(self, candidates: list[Memory], ctx: str) -> set[UUID]:
        if not candidates:
            return set()

        candidate_list = "\n".join(
            f"[{m.id}] {m.name} — {m.description} ({m.scope}, {_age_label(m.created_at)})"
            for m in candidates
        )
        prompt_text = _SELECTOR_PROMPT.format(
            dialogue_context=ctx[:_MAX_CONTEXT_CHARS],
            candidate_list=candidate_list,
        )
        try:
            client = AsyncOpenAI(
                base_url="https://api.deepseek.com/v1",
                api_key=settings.deepseek_api_key,
            )
            resp = await client.chat.completions.create(
                model=_DEEPSEEK_MODEL,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt_text}],
            )
            text = resp.choices[0].message.content or ""
            result: set[UUID] = set()
            for line in text.strip().splitlines():
                line = line.strip()
                try:
                    result.add(UUID(line))
                except ValueError:
                    pass
            return result
        except Exception as exc:
            logger.warning("MemorySelector LLM 调用失败，降级返回空集: %s", exc)
            return set()

    @staticmethod
    def build_dialogue_context(messages: list[dict]) -> str:
        """取最近 10 条，每条截断到 300 字符，总计 ≤3000 字符。"""
        recent = messages[-10:]
        parts = []
        for m in recent:
            role = m.get("role", "")
            content = (m.get("content") or "")[:_MSG_MAX_CHARS]
            parts.append(f"{role}: {content}")
        return "\n".join(parts)[:_MAX_CONTEXT_CHARS]


def _age_label(dt: datetime) -> str:
    delta = _days_ago(dt)
    if delta == 0:
        return "今天"
    if delta == 1:
        return "昨天"
    return f"{delta} 天前"


def _days_ago(dt: datetime) -> int:
    now = datetime.now(UTC)
    aware = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
    return (now - aware).days
