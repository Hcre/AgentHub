"""Provider 路由 — 自动检测 Agent CLI。"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import suppress

from fastapi import APIRouter

from app.infrastructure.llm.provider_scanner import scan_providers
from app.schemas.provider import PingRequest, PingResponse, ProviderOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("", response_model=list[ProviderOut])
async def list_providers() -> list[ProviderOut]:
    """列出当前系统中所有自动检测到的 Agent CLI。"""
    detected = await scan_providers()
    return [ProviderOut(**p.__dict__) for p in detected]


@router.post("/scan", response_model=list[ProviderOut])
async def scan() -> list[ProviderOut]:
    """手动触发重新扫描 PATH，发现新增或移除的 CLI。"""
    detected = await scan_providers()
    return [ProviderOut(**p.__dict__) for p in detected]


@router.post("/ping", response_model=PingResponse)
async def ping(req: PingRequest) -> PingResponse:
    """连通性预检：spawn CLI 发 ping 消息，验证配置是否可用。

    不创建 Agent，不写数据库，纯只读验证。
    超时 25s（opencode 完整 agent 流水线需要时间）。
    """
    t0 = time.monotonic()
    binary_map = {
        "claude_code": "claude",
        "pi_agent": "pi",
        "opencode": "opencode",
    }
    binary = binary_map.get(req.agent_system)
    if not binary:
        return PingResponse(ok=False, error=f"Unknown agent_system: {req.agent_system}")

    from app.infrastructure.llm.provider_scanner import _resolve_binary

    full_path = _resolve_binary(binary)
    if not full_path:
        return PingResponse(ok=False, error=f"CLI not found: {binary}")

    try:
        result = await _ping_cli(req.agent_system, full_path, req)
        latency = int((time.monotonic() - t0) * 1000)
        return (
            PingResponse(ok=True, latency_ms=latency)
            if result
            else PingResponse(ok=False, error="No response")
        )
    except TimeoutError:
        return PingResponse(ok=False, error="Timeout (25s)")
    except Exception as e:
        return PingResponse(ok=False, error=str(e)[:500])


async def _ping_cli(system: str, binary: str, req: PingRequest) -> bool:
    """Spawn CLI with 'ping' prompt, wait for text response."""
    env = os.environ.copy()

    if system == "pi_agent":
        env_key = _pi_env_for(req.provider)
        if env_key:
            env[env_key] = req.api_key
        if req.base_url:
            env["OPENAI_BASE_URL"] = req.base_url
        cmd = [binary, "--mode", "rpc", "--provider", _pi_provider_for(req.provider)]
        if req.model:
            cmd.extend(["--model", req.model])
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        assert proc.stdin and proc.stdout
        proc.stdin.write(b'{"type":"prompt","message":"reply OK"}\n')
        await proc.stdin.drain()
        # 不关 stdin — pi CLI 需要 stdin 保持打开才能运行

    elif system == "claude_code":
        env["ANTHROPIC_API_KEY"] = req.api_key
        if req.base_url:
            env["ANTHROPIC_BASE_URL"] = req.base_url
        cmd = [
            binary,
            "-p",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
            "--max-turns",
            "1",
        ]
        if req.model:
            cmd.extend(["--model", req.model])
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        assert proc.stdin and proc.stdout
        # stream-json 格式: JSONL user message
        import json as _json

        user_msg = (
            _json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": "reply OK"}]},
                }
            )
            + "\n"
        )
        proc.stdin.write(user_msg.encode())
        await proc.stdin.drain()

    elif system == "opencode":
        env_key = _opencode_env_for(req.provider)
        if env_key:
            env[env_key] = req.api_key
        model = req.model or f"{req.provider}/default"
        cmd = [
            binary,
            "run",
            "--format",
            "json",
            "--model",
            model,
            "--dangerously-skip-permissions",
            "reply OK",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
    else:
        return False

    assert proc.stdout
    import json

    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        try:
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=min(remaining, 5))
        except TimeoutError:
            continue
        if not line:
            break
        try:
            data = json.loads(line.decode(errors="replace").strip())
        except json.JSONDecodeError:
            continue
        t = data.get("type", "")
        # pi CLI 嵌套事件: message_update.assistantMessageEvent.type = "text_delta"
        if t == "message_update":
            inner = data.get("assistantMessageEvent", {})
            it = inner.get("type", "")
            if it in ("text_delta", "text_start", "text_end"):
                return True
            continue
        # claude_code stream-json: "assistant" with text content
        if t == "assistant":
            msg = data.get("message", {})
            for block in msg.get("content", []):
                if block.get("type") == "text" and block.get("text", "").strip():
                    return True
            continue
        # opencode 事件: type = "text"
        if t in ("text", "content"):
            return True
        if t in ("error",):
            err = data.get("error", data.get("message", ""))
            if isinstance(err, dict):
                err = err.get("message", str(err))
            logger.warning("Ping CLI error: %s", str(err)[:200])
            return False
        if t in ("done", "result", "complete", "exit", "agent_end", "turn_end"):
            return True

    with suppress(Exception):
        proc.kill()
    return False


def _pi_provider_for(provider: str) -> str:
    return {
        "deepseek": "deepseek",
        "anthropic": "anthropic",
        "openai": "openai",
        "xiaomi": "xiaomi",
        "minimax": "minimax",
    }.get(provider, provider)


def _pi_env_for(provider: str) -> str:
    return {
        "deepseek": "DEEPSEEK_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "xiaomi": "XIAOMI_TOKEN_PLAN_CN_API_KEY",
        "minimax": "MINIMAX_API_KEY",
    }.get(provider, f"{provider.upper()}_API_KEY")


def _opencode_env_for(provider: str) -> str:
    return {
        "deepseek": "DEEPSEEK_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "xiaomi": "XIAOMI_TOKEN_PLAN_CN_API_KEY",
        "minimax": "MINIMAX_API_KEY",
    }.get(provider, f"{provider.upper()}_API_KEY")
