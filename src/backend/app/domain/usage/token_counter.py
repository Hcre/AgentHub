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
    """从 metadata 提取真实 token 消耗。

    各 runtime 上报格式：
      - Claude Adapter / Codex / OpenCode: token_usage={"input_tokens":N,"output_tokens":M}
      - Claude Code CLI:            token_usage={"input_tokens":N,"output_tokens":M}
      - Pi Agent:                   usage={"input_tokens":N,"output_tokens":M}
      - Mock:                       token_usage=int
      - Anthropic SDK:              usage={"input_tokens":N,"output_tokens":N}
    """
    if not metadata:
        return 0

    def _from_dict(d: dict) -> int:
        """从 usage dict 取 output_tokens 或 completion_tokens。"""
        for key in ("output_tokens", "completion_tokens", "input_tokens"):
            v = d.get(key)
            if isinstance(v, int) and v >= 0:
                return v
        return 0

    # 路径 1: "usage" 键（Pi Agent, Anthropic SDK）
    usage = metadata.get("usage")
    if isinstance(usage, dict):
        tokens = _from_dict(usage)
        if tokens > 0:
            return tokens
    if isinstance(usage, int) and usage >= 0:
        return usage

    # 路径 2: "token_usage" 键（Claude Code, Claude Adapter, Codex, OpenCode, Mock）
    tu = metadata.get("token_usage")
    if isinstance(tu, dict):
        tokens = _from_dict(tu)
        if tokens > 0:
            return tokens
    if isinstance(tu, int) and tu >= 0:
        return tu

    # 路径 3: 直接从顶层取 output_tokens / completion_tokens（兼容旧格式）
    for key in ("output_tokens", "completion_tokens"):
        v = metadata.get(key)
        if isinstance(v, int) and v >= 0:
            return v

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
