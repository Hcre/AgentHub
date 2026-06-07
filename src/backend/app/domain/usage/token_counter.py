"""Token 计数器（P1-2）。"""

from __future__ import annotations

from uuid import UUID

from app.domain.usage.usage_record import (
    USAGE_KIND_COMPLETION,
    USAGE_KIND_PROMPT,
    UsageRecord,
)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    other = len(text) - cjk
    return max(1, round(cjk / 1.5 + other / 4))


def extract_completion_tokens(metadata: dict | None) -> int:
    if not metadata:
        return 0
    usage = metadata.get("usage")
    if isinstance(usage, dict):
        for key in ("output_tokens", "completion_tokens"):
            v = usage.get(key)
            if isinstance(v, int) and v >= 0:
                return v
    tu = metadata.get("token_usage")
    if isinstance(tu, int) and tu >= 0:
        return tu
    return 0


class TokenCounter:
    def count_user_message(
        self, *, session_id: UUID, message_id: UUID, content: str
    ) -> list[UsageRecord]:
        tokens = estimate_tokens(content)
        if tokens == 0:
            return []
        return [
            UsageRecord(
                session_id=session_id,
                agent_id=None,
                message_id=message_id,
                kind=USAGE_KIND_PROMPT,
                tokens=tokens,
                model=None,
            )
        ]

    def count_completion(
        self,
        *,
        session_id: UUID,
        message_id: UUID,
        agent_id: UUID,
        content: str,
        metadata: dict | None,
        model: str | None,
    ) -> list[UsageRecord]:
        tokens = extract_completion_tokens(metadata) or estimate_tokens(content)
        if tokens == 0:
            return []
        return [
            UsageRecord(
                session_id=session_id,
                agent_id=agent_id,
                message_id=message_id,
                kind=USAGE_KIND_COMPLETION,
                tokens=tokens,
                model=model,
            )
        ]
