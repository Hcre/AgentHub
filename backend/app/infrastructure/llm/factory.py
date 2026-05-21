"""适配器工厂：按配置选择 LLM 实现（mock / anthropic_api / claude_cli）。"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.domain.llm.protocol import UnifiedAgent
from app.infrastructure.llm.mock_adapter import MockAdapter

logger = logging.getLogger(__name__)


def build_adapter() -> UnifiedAgent:
    mode = settings.llm_adapter_mode

    if mode == "anthropic_api":
        if not settings.anthropic_api_key:
            logger.warning("未配置 ANTHROPIC_API_KEY，降级为 mock 适配器")
            return MockAdapter()
        from app.infrastructure.llm.claude_adapter import ClaudeAdapter

        return ClaudeAdapter(
            api_key=settings.anthropic_api_key, model=settings.default_model
        )

    if mode == "claude_cli":
        logger.warning("claude_cli 适配器待 M2 实现，暂用 mock")
        return MockAdapter()

    return MockAdapter()
