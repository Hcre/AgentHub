"""适配器工厂：per-agent 构造（根据 agent_system 字段路由到对应实现）。

CLI 运行时优先（有文件系统访问），CLI 未安装时直接报错。
每个运行时只收最小必要参数，不传递 model/provider/api_key/base_url/proxy_base。
认证和模型选择由各 CLI 自身的配置/环境变量管理。
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


def build_adapter_for_agent(agent: Agent) -> UnifiedAgent:
    """根据 Agent 实体的 agent_system 字段构造对应的适配器/运行时。

    CLI 运行时优先（有文件系统操作能力），CLI 未安装直接报错。
    每个运行时只收最小必要参数 — 认证和模型选择由各 CLI 自身的配置/环境变量管理。
    """
    system = agent.agent_system

    if system == AgentSystem.ANTHROPIC_API:
        api_key = decrypt_secret(agent.settings.get("api_key_encrypted", ""))
        if not api_key:
            logger.warning("Agent %s 无 API key，降级为 mock", agent.name)
            return MockAdapter()
        from app.infrastructure.llm.claude_adapter import ClaudeAdapter

        return ClaudeAdapter(api_key=api_key, model=agent.settings.get("model", "") or settings.default_model)

    if system == AgentSystem.OPENAI_API:
        api_key = decrypt_secret(agent.settings.get("api_key_encrypted", ""))
        if not api_key:
            logger.warning("Agent %s 无 API key，降级为 mock", agent.name)
            return MockAdapter()
        logger.warning("OpenAI API 适配器待实现，Agent %s 降级为 mock", agent.name)
        return MockAdapter()

    if system == AgentSystem.CLAUDE_CODE:
        if not _cli_installed(system):
            raise RuntimeError("Claude Code CLI not installed")

        from app.infrastructure.llm.claude_code_runtime import ClaudeCodeRuntime

        s = agent.settings or {}
        logger.info("Agent '%s' → ClaudeCodeRuntime (CLI, global mode)", agent.name)
        return ClaudeCodeRuntime(
            agent_id=str(agent.id),
            permission_mode=s.get("permission_mode", "bypassPermissions"),
            max_turns=s.get("max_turns", 10),
            timeout=s.get("cli_timeout", settings.claude_cli_timeout),
        )

    if system == AgentSystem.PI_AGENT:
        if not _cli_installed(system):
            raise RuntimeError("Pi Agent CLI not installed")

        from app.infrastructure.llm.pi_agent_runtime import PiAgentRuntime

        s = agent.settings or {}
        api_key = decrypt_secret(agent.settings.get("api_key_encrypted", "")) if agent.settings.get("api_key_encrypted", "") else ""
        logger.info("Agent '%s' → PiAgentRuntime (CLI, provider=%s, model=%s)", agent.name, agent.settings.get("provider", "deepseek"), agent.settings.get("model", ""))
        return PiAgentRuntime(
            agent_id=str(agent.id),
            agent_name=agent.name,
            model=agent.settings.get("model", "") or "",
            provider=agent.settings.get("provider", "deepseek") or "anthropic",
            api_key=api_key,
            proxy_base=settings.proxy_base_url or "",
            timeout=s.get("cli_timeout", settings.claude_cli_timeout),
            thinking_level=s.get("thinking_level", "off"),
            permission_mode=s.get("permission_mode", "bypassPermissions"),
            max_turns=s.get("max_turns", 10),
        )

    if system == AgentSystem.OPENCODE:
        if not _cli_installed(system):
            raise RuntimeError("OpenCode CLI not installed")

        from app.infrastructure.llm.opencode_runtime import OpenCodeRuntime

        s = agent.settings or {}
        api_key = decrypt_secret(agent.settings.get("api_key_encrypted", "")) if agent.settings.get("api_key_encrypted", "") else ""
        logger.info("Agent '%s' → OpenCodeRuntime (CLI, provider=%s, model=%s)", agent.name, agent.settings.get("provider", "deepseek"), agent.settings.get("model", ""))
        return OpenCodeRuntime(
            agent_id=str(agent.id),
            model=agent.settings.get("model", "") or "",
            provider=agent.settings.get("provider", "deepseek") or "deepseek",
            api_key=api_key,
            proxy_base=settings.proxy_base_url or "",
            timeout=s.get("cli_timeout", settings.claude_cli_timeout),
            permission_mode=s.get("permission_mode", "bypassPermissions"),
            max_turns=s.get("max_turns", 10),
        )

    if system == AgentSystem.CODEX:
        if not _cli_installed(system):
            raise RuntimeError("Codex CLI not installed")

        from app.infrastructure.llm.codex_runtime import CodexRuntime

        s = agent.settings or {}
        api_key = decrypt_secret(agent.settings.get("api_key_encrypted", "")) if agent.settings.get("api_key_encrypted", "") else ""
        logger.info("Agent '%s' → CodexRuntime (CLI, model=%s)", agent.name, agent.settings.get("model", ""))
        return CodexRuntime(
            agent_id=str(agent.id),
            model=agent.settings.get("model", "") or "",
            api_key=api_key,
            proxy_base=settings.proxy_base_url or "",
            workspace=s.get("workspace_path"),
            timeout=s.get("cli_timeout", settings.claude_cli_timeout),
            permission_mode=s.get("permission_mode", "bypassPermissions"),
            max_turns=s.get("max_turns", 10),
        )

    if system in (AgentSystem.GEMINI, AgentSystem.CURSOR_AGENT):
        raise RuntimeError(f"{system.value} CLI not installed")

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
