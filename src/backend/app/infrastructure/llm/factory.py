"""适配器工厂：per-agent 构造（根据 agent_system 字段路由到对应实现）。"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.core.security import decrypt_secret
from app.domain.entities.agent import Agent
from app.domain.enums import AgentSystem
from app.domain.llm.protocol import UnifiedAgent
from app.infrastructure.llm.mock_adapter import MockAdapter

logger = logging.getLogger(__name__)


def build_adapter_for_agent(agent: Agent) -> UnifiedAgent:
    """根据 Agent 实体的 agent_system 字段构造对应的适配器/运行时。"""
    system = agent.agent_system

    if system == AgentSystem.ANTHROPIC_API:
        api_key = decrypt_secret(agent.api_key_encrypted)
        if not api_key:
            logger.warning("Agent %s 无 API key，降级为 mock", agent.name)
            return MockAdapter()
        from app.infrastructure.llm.claude_adapter import ClaudeAdapter

        return ClaudeAdapter(api_key=api_key, model=agent.model or settings.default_model)

    if system == AgentSystem.OPENAI_API:
        api_key = decrypt_secret(agent.api_key_encrypted)
        if not api_key:
            logger.warning("Agent %s 无 API key，降级为 mock", agent.name)
            return MockAdapter()
        # TODO: 实现 OpenAIAdapter，暂降级 mock
        logger.warning("OpenAI API 适配器待实现，Agent %s 降级为 mock", agent.name)
        return MockAdapter()

    if system == AgentSystem.CLAUDE_CODE:
        from app.infrastructure.llm.claude_code_runtime import ClaudeCodeRuntime

        s = agent.settings or {}

        return ClaudeCodeRuntime(
            model=agent.model,
            agent_id=str(agent.id),
            proxy_base=settings.proxy_base_url,
            permission_mode=s.get("permission_mode", "acceptEdits"),
            max_turns=s.get("max_turns", 10),
            timeout=s.get("cli_timeout", settings.claude_cli_timeout),
        )

    if system == AgentSystem.PI_AGENT:
        from app.infrastructure.llm.claude_adapter import ClaudeAdapter

        s = agent.settings or {}
        api_key = decrypt_secret(agent.api_key_encrypted) if agent.api_key_encrypted else ""

        # 第三方 provider 的 Anthropic 兼容端点需要 Anthropic 模型名
        model = agent.model
        if agent.provider.value == "deepseek":
            model = s.get("anthropic_model", "claude-sonnet-4-20250514")

        # 用 ClaudeAdapter 通过 proxy 调 API（Pi CLI 在 Windows 下有网络问题）
        base_url = f"{settings.proxy_base_url}/proxy/agents/{agent.id}"
        return ClaudeAdapter(
            api_key="agenthub-proxy",  # proxy 会替换为真实 key
            model=model,
            base_url=base_url,
        )

    # AgentSystem.MOCK 或未知
    return MockAdapter()


def build_adapter() -> UnifiedAgent:
    """全局默认适配器（兼容旧调用，按全局配置构造）。"""
    mode = settings.llm_adapter_mode

    if mode == "anthropic_api":
        if not settings.anthropic_api_key:
            logger.warning("未配置 ANTHROPIC_API_KEY，降级为 mock 适配器")
            return MockAdapter()
        from app.infrastructure.llm.claude_adapter import ClaudeAdapter

        return ClaudeAdapter(api_key=settings.anthropic_api_key, model=settings.default_model)

    if mode == "claude_cli":
        from app.infrastructure.llm.claude_code_runtime import ClaudeCodeRuntime

        return ClaudeCodeRuntime(
            model=settings.default_model,
            timeout=settings.claude_cli_timeout,
        )

    return MockAdapter()
