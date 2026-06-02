"""适配器工厂：per-agent 构造（根据 agent_system 字段路由到对应实现）。

CLI 运行时优先（有文件系统访问），CLI 未安装时自动降级 HTTP API。
借鉴 Open Design 的 BYOK proxy fallback 模式。
"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.core.security import decrypt_secret
from app.domain.entities.agent import Agent
from app.domain.enums import AgentSystem
from app.domain.llm.protocol import UnifiedAgent
from app.infrastructure.llm.mock_adapter import MockAdapter

logger = logging.getLogger(__name__)

# CLI 二进制 → 描述，用于日志
_CLI_BINARIES: dict[AgentSystem, str] = {
    AgentSystem.CLAUDE_CODE: "claude",
    AgentSystem.PI_AGENT: "pi",
    AgentSystem.OPENCODE: "opencode",
    AgentSystem.CODEX: "codex",
    AgentSystem.GEMINI: "gemini",
    AgentSystem.CURSOR_AGENT: "cursor-agent",
}


def _cli_installed(system: AgentSystem) -> bool:
    from app.infrastructure.llm.provider_scanner import _resolve_binary

    binary = _CLI_BINARIES.get(system)
    return binary is not None and _resolve_binary(binary) is not None


def _build_api_fallback(agent: Agent) -> UnifiedAgent:
    """CLI 未安装时的 HTTP API 降级适配器。"""
    from app.infrastructure.llm.claude_adapter import ClaudeAdapter

    api_key = decrypt_secret(agent.api_key_encrypted) if agent.api_key_encrypted else ""
    s = agent.settings or {}
    model = agent.model
    base_url = agent.base_url or ""

    if agent.provider.value == "deepseek":
        model = s.get("anthropic_model", model or "claude-sonnet-4-20250514")
        base_url = base_url or "https://api.deepseek.com/anthropic"

    logger.warning(
        "Agent '%s' (system=%s) CLI 未安装，降级 HTTP API",
        agent.name,
        agent.agent_system.value,
    )
    return ClaudeAdapter(api_key=api_key, model=model, base_url=base_url)


def build_adapter_for_agent(agent: Agent) -> UnifiedAgent:
    """根据 Agent 实体的 agent_system 字段构造对应的适配器/运行时。

    CLI 运行时优先（有文件系统操作能力），CLI 未安装自动降级 HTTP API。
    """
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
        logger.warning("OpenAI API 适配器待实现，Agent %s 降级为 mock", agent.name)
        return MockAdapter()

    if system == AgentSystem.CLAUDE_CODE:
        if not _cli_installed(system):
            return _build_api_fallback(agent)

        from app.infrastructure.llm.claude_code_runtime import ClaudeCodeRuntime

        s = agent.settings or {}
        logger.info("Agent '%s' → ClaudeCodeRuntime (CLI 子进程)", agent.name)
        return ClaudeCodeRuntime(
            model=agent.model,
            agent_id=str(agent.id),
            proxy_base=settings.proxy_base_url,
            permission_mode=s.get("permission_mode", "acceptEdits"),
            max_turns=s.get("max_turns", 10),
            timeout=s.get("cli_timeout", settings.claude_cli_timeout),
        )

    if system == AgentSystem.PI_AGENT:
        # pi CLI v0.74 原生支持 anthropic / openai / deepseek provider
        # 不用 proxy，pi CLI 直接根据 --provider 选择正确协议 + 端点
        if not _cli_installed(system):
            return _build_api_fallback(agent)

        from app.infrastructure.llm.pi_agent_runtime import PiAgentRuntime

        api_key = decrypt_secret(agent.api_key_encrypted) if agent.api_key_encrypted else ""
        provider_value = str(agent.provider.value)

        logger.info(
            "Agent '%s' → PiAgentRuntime (CLI 子进程, cwd=workspace, provider=%s)",
            agent.name,
            provider_value,
        )
        return PiAgentRuntime(
            model=agent.model,
            agent_id=str(agent.id),
            agent_name=agent.name,
            provider=provider_value,
            api_key=api_key,
            base_url=agent.base_url or "",
        )

    if system == AgentSystem.OPENCODE:
        if not _cli_installed(system):
            return _build_api_fallback(agent)

        from app.infrastructure.llm.opencode_runtime import OpenCodeRuntime

        # opencode.jsonc 通过 {env:DEEPSEEK_API_KEY} 读取 key
        # AgentHub 注入环境变量，opencode 自己的 provider 系统处理协议+端点
        api_key = decrypt_secret(agent.api_key_encrypted) if agent.api_key_encrypted else ""
        provider_value = str(agent.provider.value)
        # opencode 模型格式: provider/model（如 deepseek/deepseek-v4-flash）
        model = agent.model or ""
        if "/" not in model:
            model = f"{provider_value}/{model}" if model else f"{provider_value}/deepseek-v4-flash"

        logger.info(
            "Agent '%s' → OpenCodeRuntime (CLI, model=%s, provider=%s)",
            agent.name,
            model,
            provider_value,
        )
        return OpenCodeRuntime(
            model=model,
            agent_id=str(agent.id),
            provider=provider_value,
            api_key=api_key,
            timeout=agent.settings.get("cli_timeout", settings.claude_cli_timeout),
        )

    # CODEX / GEMINI / CURSOR_AGENT — CLI 适配器待实现，暂走 HTTP API
    if system in (AgentSystem.CODEX, AgentSystem.GEMINI, AgentSystem.CURSOR_AGENT):
        return _build_api_fallback(agent)

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
