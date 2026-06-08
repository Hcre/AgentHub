"""适配器工厂：per-agent 构造（根据 agent_system 字段路由到对应实现）。

CLI 运行时优先（有文件系统访问），CLI 未安装时自动降级 HTTP API。
借鉴 Open Design 的 BYOK proxy fallback 模式。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

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

# Provider → API Key env var / settings fallback
_PROVIDER_KEY_FALLBACK: dict[str, str] = {
    "deepseek": "DEEPSEEK_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def _resolve_api_key(agent: Agent) -> str:
    """Resolve API key: encrypted field first, then env var, then settings globals."""
    api_key = decrypt_secret(agent.api_key_encrypted) if agent.api_key_encrypted else ""
    if api_key:
        return api_key
    provider = str(agent.provider.value)
    env_var = _PROVIDER_KEY_FALLBACK.get(provider)
    if env_var:
        api_key = os.environ.get(env_var, "")
        if api_key:
            logger.info("Agent '%s': API key resolved from env %s", agent.name, env_var)
            return api_key
    # Secondary: read from Claude Code settings.json (stores ANTHROPIC_AUTH_TOKEN in env section)
    try:
        claude_cfg_path = Path.home() / ".claude" / "settings.json"
        if claude_cfg_path.exists():
            claude_cfg = json.loads(claude_cfg_path.read_text())
            auth_token = claude_cfg.get("env", {}).get("ANTHROPIC_AUTH_TOKEN", "")
            if auth_token:
                logger.info("Agent '%s': API key resolved from ~/.claude/settings.json", agent.name)
                return auth_token
    except Exception:
        pass
    # Last resort: settings-level keys
    if provider == "deepseek" and settings.deepseek_api_key:
        return settings.deepseek_api_key
    if provider == "anthropic" and settings.anthropic_api_key:
        return settings.anthropic_api_key
    return ""


def _cli_installed(system: AgentSystem) -> bool:
    from app.infrastructure.llm.provider_scanner import _resolve_binary

    binary = _CLI_BINARIES.get(system)
    return binary is not None and _resolve_binary(binary) is not None


def _build_api_fallback(agent: Agent) -> UnifiedAgent:
    """CLI 未安装时的 HTTP API 降级适配器。"""
    from app.infrastructure.llm.claude_adapter import ClaudeAdapter

    api_key = _resolve_api_key(agent)
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
        # Claude Code CLI 自带认证（claude login OAuth），不需要 AgentHub 传 API Key。
        # 只有当 CLI 未安装时，才降级 HTTP API（此时需要 Agent 配置中有 api_key）。
        if not _cli_installed(system):
            return _build_api_fallback(agent)

        from app.infrastructure.llm.claude_code_runtime import ClaudeCodeRuntime

        s = agent.settings or {}
        # 有 base_url：BYOK，走本地 proxy 注入真实 key（CLI 只会 Anthropic 协议）。
        # 无 base_url：用宿主机全局 claude 认证（global 模式），不设 ANTHROPIC_BASE_URL。
        #   否则会被指向 proxy，而 proxy 见空 base_url 直接 400 —— agent 永远跑不通。
        use_proxy = bool(agent.base_url)
        logger.info(
            "Agent '%s' → ClaudeCodeRuntime (CLI 子进程, %s)",
            agent.name,
            "proxy" if use_proxy else "global",
        )
        return ClaudeCodeRuntime(
            model=agent.model,
            agent_id=str(agent.id),
            proxy_base=settings.proxy_base_url if use_proxy else "",
            permission_mode=s.get("permission_mode", "bypassPermissions"),
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
        s_pi = agent.settings or {}
        return PiAgentRuntime(
            model=agent.model,
            agent_id=str(agent.id),
            agent_name=agent.name,
            provider=provider_value,
            api_key=api_key,
            base_url=agent.base_url or "",
            proxy_base=settings.proxy_base_url,
            timeout=s_pi.get("cli_timeout", settings.claude_cli_timeout),
            thinking_level=s_pi.get("thinking_level", "off"),
            permission_mode=s_pi.get("permission_mode", "bypassPermissions"),
            max_turns=s_pi.get("max_turns", 10),
        )

    if system == AgentSystem.OPENCODE:
        if not _cli_installed(system):
            return _build_api_fallback(agent)

        from app.infrastructure.llm.opencode_runtime import OpenCodeRuntime

        # AgentHub 通过 OPENCODE_CONFIG 自包含临时配置文件注入 apiKey，
        # opencode 从该文件读取 provider 配置 + 密钥（通过字符串替换 {api_key}）。
        # 密钥来源：加密字段 > 环境变量 > settings 全局 key。
        api_key = _resolve_api_key(agent)
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
        s_oc = agent.settings or {}
        return OpenCodeRuntime(
            model=model,
            agent_id=str(agent.id),
            provider=provider_value,
            api_key=api_key,
            timeout=s_oc.get("cli_timeout", settings.claude_cli_timeout),
            permission_mode=s_oc.get("permission_mode", "bypassPermissions"),
            max_turns=s_oc.get("max_turns", 10),
            proxy_base=settings.proxy_base_url,
        )

    if system == AgentSystem.CODEX:
        if not _cli_installed(system):
            return _build_api_fallback(agent)

        from app.infrastructure.llm.codex_runtime import CodexRuntime

        api_key = _resolve_api_key(agent)
        s_cx = agent.settings or {}
        logger.info(
            "Agent '%s' → CodexRuntime (CLI, model=%s)", agent.name, agent.model or "default"
        )
        return CodexRuntime(
            model=agent.model or "",
            agent_id=str(agent.id),
            api_key=api_key,
            workspace=s_cx.get("workspace_path"),
            timeout=s_cx.get("cli_timeout", settings.claude_cli_timeout),
            permission_mode=s_cx.get("permission_mode", "bypassPermissions"),
            max_turns=s_cx.get("max_turns", 10),
            proxy_base=settings.proxy_base_url,
        )

    # GEMINI / CURSOR_AGENT — CLI 适配器待实现，暂走 HTTP API
    if system in (AgentSystem.GEMINI, AgentSystem.CURSOR_AGENT):
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
