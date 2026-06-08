"""Provider 路由 — 自动检测 Agent CLI。"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import suppress

from fastapi import APIRouter

from app.infrastructure.llm.cli_config_reader import read_default_config
from app.infrastructure.llm.provider_scanner import scan_providers
from app.schemas.provider import (
    DefaultConfigOut,
    PingRequest,
    PingResponse,
    ProviderOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/providers", tags=["providers"])


# ── 不再有 _DEFAULT_CONFIG 硬编码表 ──
# default-config 端点从用户机器 ~/.claude/ ~/.codex/ 等真实配置文件读，
# 读不到返 None + note。详见 app.infrastructure.llm.cli_config_reader


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


@router.get("/{agent_system}/default-config", response_model=DefaultConfigOut)
async def default_config(agent_system: str) -> DefaultConfigOut:
    """从 CLI 本地配置文件读取默认连接配置（model / base_url / api_key / provider）。

    实现见 app.infrastructure.llm.cli_config_reader.read_default_config。
    读不到时所有字段返 None，note 标注原因。
    """
    source, fields = read_default_config(agent_system)
    if source is None:
        if any(v is not None for v in fields.values()):
            note = "已读到部分字段，其余缺失"
        elif agent_system in {"mock", "gemini", "cursor_agent"}:
            note = f"该 CLI 暂未实现配置文件读取（或不需要），请手动填写"
        else:
            note = f"未在 {os.environ.get('USERPROFILE') or os.environ.get('HOME') or '~'} 找到 {agent_system} 的配置文件"
    else:
        note = f"已从 {source} 读取"
    return DefaultConfigOut(
        agent_system=agent_system,
        model=fields.get("model"),
        base_url=fields.get("base_url"),
        api_key=fields.get("api_key"),
        provider=fields.get("provider"),
        source=source,
        note=note,
    )


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
        "codex": "codex",
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
        if env_key and req.api_key:
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
        if req.api_key:
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
        if env_key and req.api_key:
            env[env_key] = req.api_key
        cmd = [
            binary,
            "run",
            "--format",
            "json",
            "--pure",
        ]
        if req.model:
            cmd.extend(["--model", req.model])
        # opencode 无 --dangerously-skip-permissions flag，权限由 opencode.json 配置控制
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

    elif system == "codex":
        # Codex 走 chatgpt OAuth（auth_mode="chatgpt"），不需 env 注入 API key。
        # --version 输出纯文本（"codex-cli 0.43.0"）不是 JSONL，所以走"进程退出码 0 = 通"
        # 这个分支：等 proc 退出，exit 0 返 True；其余返 False。
        cmd = [binary, "--version"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )
        try:
            returncode = await asyncio.wait_for(proc.wait(), timeout=10)
            return returncode == 0
        except TimeoutError:
            with suppress(Exception):
                proc.kill()
            return False
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
