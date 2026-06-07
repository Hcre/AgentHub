"""OpenCodeRuntime — OpenCode CLI 子进程适配器 (v1.15+)。

多轮对话通过 opencode 原生 --session 实现：
- 首次调用 spawn opencode run，从 stdout 捕获 sessionID
- 后续调用加 --session <id>，opencode 自动维护上下文
"""

from __future__ import annotations

import asyncio
import atexit
import json
import logging
import os
import re
import tempfile
from collections.abc import AsyncIterator
from contextlib import suppress
from pathlib import Path
from typing import Any, ClassVar

from app.core.config import settings
from app.domain.llm.protocol import (
    AgentRequest,
    AgentRuntime,
    StreamEvent,
    StreamEventType,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 300

# AgentHub session UUID → opencode session ID
_session_map: dict[str, str] = {}


class OpenCodeRuntime(AgentRuntime):
    """OpenCode CLI 运行时 — opencode run --format json --session <id>。"""

    _PROVIDER_ENV: ClassVar[dict[str, str]] = {
        "deepseek": "DEEPSEEK_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "xiaomi": "XIAOMI_TOKEN_PLAN_CN_API_KEY",
        "minimax": "MINIMAX_API_KEY",
    }

    def __init__(
        self,
        *,
        model: str = "",
        agent_id: str = "",
        provider: str = "deepseek",
        api_key: str = "",
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._model = model or "deepseek/deepseek-v4-flash"
        self._agent_id = agent_id
        self._provider = provider
        self._api_key = api_key
        self._timeout = timeout
        self._process: asyncio.subprocess.Process | None = None

    async def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        prompt = self._extract_prompt(request)
        if not prompt:
            yield StreamEvent(type=StreamEventType.ERROR, seq=0, content="OpenCode: 无用户消息")
            return

        binary = self._find_binary()
        if not binary:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=0,
                content="OpenCode CLI 未安装: npm i -g opencode-ai",
            )
            return

        cwd = request.working_directory or os.getcwd()
        env = os.environ.copy()
        # opencode Unix 风格，用 $HOME/.config 找配置文件
        if "HOME" not in env:
            env["HOME"] = os.environ.get("USERPROFILE", "")

        # AgentHub 通过 OPENCODE_CONFIG 自包含临时配置文件注入 provider + apiKey，
        # 不再依赖 ~/.config/opencode/opencode.json（用户本地可能不存在）。
        # opencode 从配置文件读取密钥，不依赖环境变量传递。

        # MCP 注入（ADR-06 统一原则）：opencode 无 --mcp-config flag，改用逐进程隔离通道
        # OPENCODE_CONFIG=<tmp>（本机实测可注入，非全局，零串号）。临时配置自包含
        # provider+mcp 块。mcp 块随每次 spawn 重写。
        #
        # 解析有效 API key：AgentHub 存储优先 → 回退环境变量。
        api_key = self._api_key
        if not api_key:
            env_var = self._PROVIDER_ENV.get(self._provider)
            if env_var:
                api_key = os.environ.get(env_var, "")
        mcp_section = _build_opencode_mcp(
            request.mcp_servers, settings.mcp_memory_url, self._agent_id
        )
        # 有 apiKey 时必须注入配置（否则 opencode 无凭证，挂起直至超时）；MCP 可空。
        # 两者都无时跳过：不写空配置覆盖用户本地的 ~/.config/opencode/opencode.json。
        if api_key or mcp_section:
            cfg_path = _write_opencode_config(self._provider, api_key, mcp_section)
            if cfg_path:
                env["OPENCODE_CONFIG"] = cfg_path
        else:
            logger.warning(
                "OpenCode: 无 apiKey 且无 MCP server，跳过 OPENCODE_CONFIG 注入。"
                "opencode 将尝试 ~/.config/opencode/opencode.json；若不存在则无凭证，可能挂起。"
            )

        # 多轮对话：首次创建 session，后续用 --session 继续
        ah_session = str(request.session_id)
        oc_session = _session_map.get(ah_session)

        cmd = [binary, "run", "--format", "json", "--pure"]
        if oc_session:
            cmd.extend(["--session", oc_session])
        # 不再传 --model：CLI 启动时从 opencode.json 读 default model
        cmd.extend(["--dangerously-skip-permissions", prompt])

        logger.info(
            "OpenCode spawn: %s (provider=%s, oc_session=%s)",
            " ".join(cmd),
            self._provider,
            oc_session or "new",
        )

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
                cwd=cwd,
            )
        except FileNotFoundError:
            yield StreamEvent(type=StreamEventType.ERROR, seq=0, content="OpenCode CLI 启动失败")
            return

        assert self._process.stdout is not None

        seq = 0
        try:
            async for line in self._read_lines_with_timeout(self._process.stdout):
                # 从首个事件中提取 opencode sessionID
                if not oc_session:
                    sid = _extract_session_id(line)
                    if sid:
                        _session_map[ah_session] = sid
                        logger.debug("OpenCode session %s → %s", ah_session, sid)

                events = self._parse_line(line, seq)
                for evt in events:
                    yield evt
                    seq = evt.seq + 1
                if events and events[-1].type in (StreamEventType.DONE, StreamEventType.ERROR):
                    break
        except TimeoutError:
            yield StreamEvent(
                type=StreamEventType.ERROR, seq=seq, content=f"OpenCode 超时 ({self._timeout}s)"
            )
            await self.stop()
            return

        try:
            await asyncio.wait_for(self._process.wait(), timeout=10)
        except TimeoutError:
            self._process.kill()

        if self._process.returncode and self._process.returncode != 0:
            stderr = ""
            if self._process.stderr:
                with suppress(Exception):
                    stderr = (await self._process.stderr.read()).decode(errors="replace")
            if stderr:
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    seq=seq,
                    content=f"OpenCode 退出码 {self._process.returncode}: {stderr[:500]}",
                )
        self._process = None

    async def stop(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.kill()
            self._process = None

    @staticmethod
    def _find_binary() -> str | None:
        from app.infrastructure.llm.provider_scanner import _resolve_binary

        return _resolve_binary("opencode")

    @staticmethod
    def _extract_prompt(request: AgentRequest) -> str:
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    async def _read_lines_with_timeout(self, stdout: asyncio.StreamReader) -> AsyncIterator[str]:
        deadline = asyncio.get_event_loop().time() + self._timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError
            try:
                line = await asyncio.wait_for(stdout.readline(), timeout=remaining)
            except TimeoutError:
                raise
            if not line:
                break
            decoded = line.decode(errors="replace").strip()
            if decoded:
                yield decoded

    def _parse_line(self, line: str, seq: int) -> list[StreamEvent]:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return [StreamEvent(type=StreamEventType.TEXT, seq=seq, content=line)]

        # opencode v1.15+ JSON schema: 大部分字段嵌套在 data.part 内
        part = data.get("part", {})

        def _s(key: str, default: str = "") -> str:
            # 优先取 part 内字段（opencode v1.15+ 标准），fallback 到顶层（兼容旧版）
            v = part.get(key) if part else None
            if v is None:
                v = data.get(key, default)
            if isinstance(v, str):
                return v
            if v:
                return json.dumps(v, ensure_ascii=False)
            return default

        event_type = data.get("type", "")
        events: list[StreamEvent] = []

        if event_type in ("text", "content", "message"):
            text = _s("text") or _s("content") or _s("message")
            if text:
                events.append(StreamEvent(type=StreamEventType.TEXT, seq=seq, content=text))
        elif event_type == "thinking":
            text = _s("text") or _s("content") or _s("thinking")
            if text:
                events.append(StreamEvent(type=StreamEventType.THINKING, seq=seq, content=text))
        elif event_type in ("tool_call", "tool_use"):
            events.append(
                StreamEvent(
                    type=StreamEventType.TOOL_CALL,
                    seq=seq,
                    tool_call=ToolCall(
                        call_id=str(data.get("id", data.get("call_id", part.get("id", "")))),
                        name=str(part.get("name", data.get("name", ""))),
                        arguments=part.get(
                            "arguments", data.get("arguments", data.get("args", {}))
                        ),
                    ),
                )
            )
        elif event_type == "tool_result":
            tr_content = part.get("content", data.get("content", data.get("result", "")))
            if not isinstance(tr_content, str):
                tr_content = json.dumps(tr_content, ensure_ascii=False)
            events.append(
                StreamEvent(
                    type=StreamEventType.TOOL_RESULT,
                    seq=seq,
                    tool_result=ToolResult(
                        call_id=str(part.get("id", data.get("id", data.get("call_id", "")))),
                        success=not part.get("is_error", data.get("is_error", False)),
                        content=tr_content,
                    ),
                )
            )
        elif event_type in ("done", "result", "complete", "exit"):
            events.append(
                StreamEvent(type=StreamEventType.DONE, seq=seq, metadata={"model": self._model})
            )
        elif event_type == "step_finish":
            # 单步完成（无 tool_use 时 step_finish 即为终态）；产生 DONE 并终止循环
            events.append(
                StreamEvent(
                    type=StreamEventType.DONE,
                    seq=seq,
                    metadata={"model": self._model, "status": "step_finish"},
                )
            )
        elif event_type == "error":
            events.append(
                StreamEvent(
                    type=StreamEventType.ERROR,
                    seq=seq,
                    content=_s("message") or _s("error") or "OpenCode error",
                )
            )
        elif event_type == "step_start":
            # 仅提取 sessionID，不产生用户可见事件
            pass
        else:
            text = _s("text") or _s("content")
            if text:
                events.append(StreamEvent(type=StreamEventType.TEXT, seq=seq, content=text))
        return events


def _extract_session_id(line: str) -> str | None:
    m = re.search(r'"sessionID"\s*:\s*"([^"]+)"', line)
    return m.group(1) if m else None


# opencode.jsonc 模板 — 除了 apiKey 其他字段固定
_OPENCODE_CONFIG_TEMPLATE = """{
  "$schema": "https://opencode.ai/config.json",
  "model": "deepseek/deepseek-v4-pro",
  "small_model": "deepseek/deepseek-v4-flash",
  "provider": {
    "deepseek": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "DeepSeek",
      "options": {
        "baseURL": "https://api.deepseek.com/v1",
        "apiKey": "{api_key}"
      },
      "models": {
        "deepseek-v4-flash": {
          "name": "deepseek-v4-flash",
          "limit": { "context": 1000000, "output": 393216 },
          "modalities": { "input": ["text"], "output": ["text"] },
          "variants": {
            "think-high": {
              "reasoning": true,
              "reasoningEffort": "high",
              "interleaved": { "field": "reasoning_content" }
            }
          }
        },
        "deepseek-v4-pro": {
          "name": "deepseek-v4-pro",
          "limit": { "context": 1000000, "output": 393216 },
          "modalities": { "input": ["text"], "output": ["text"] },
          "variants": {
            "think-high": {
              "reasoning": true,
              "reasoningEffort": "high",
              "interleaved": { "field": "reasoning_content" }
            }
          }
        }
      }
    }
  }
}"""


def _write_provider_config(provider: str, api_key: str) -> None:
    """动态写入 opencode.jsonc，注入 AgentHub 解密后的 API key。"""
    config_dir = Path.home() / ".config" / "opencode"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "opencode.jsonc"

    # 只写 deepseek provider，其他 provider 可扩展
    if provider == "deepseek":
        content = _OPENCODE_CONFIG_TEMPLATE.replace("{api_key}", api_key)
    else:
        # 通用模板
        content = f"""{{
  "$schema": "https://opencode.ai/config.json",
  "provider": {{
    "{provider}": {{
      "npm": "@ai-sdk/openai-compatible",
      "options": {{
        "baseURL": "",
        "apiKey": "{api_key}"
      }}
    }}
  }}
}}"""

    config_path.write_text(content, encoding="utf-8")
    logger.info("OpenCode config written: %s (provider=%s)", config_path, provider)


def _entry_to_opencode(entry: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """canonical MCP 条目（build_mcp_config_entry）→ opencode mcp.<name> 值。

    差异（RT-MCP §2.2）：command 合并为数组 / env→environment / 必带 enabled / 远程统一 remote。
    返回 (name, opencode_value)。
    """
    name = entry.get("name", "")
    if entry.get("type") == "stdio":
        command = [entry.get("command", "")]
        if entry.get("args"):
            command.extend(entry["args"])
        value: dict[str, Any] = {"type": "local", "command": command, "enabled": True}
        if entry.get("env"):
            value["environment"] = entry["env"]
        return name, value
    # sse / http → opencode remote
    value = {"type": "remote", "url": entry.get("url", ""), "enabled": True}
    if entry.get("headers"):
        value["headers"] = entry["headers"]
    return name, value


def _build_opencode_mcp(
    bound_servers: list[dict] | None, memory_url: str, agent_id: str
) -> dict[str, Any]:
    """构建 opencode `mcp` 块：记忆工具（agenthub-memory）+ P2 绑定的 MCP servers。

    无任何 server 时返回 {}（调用方据此跳过 OPENCODE_CONFIG，退化为现状）。
    """
    mcp: dict[str, Any] = {}
    if memory_url and agent_id:
        mcp["agenthub-memory"] = {
            "type": "remote",
            "url": f"{memory_url}?agent_id={agent_id}",
            "enabled": True,
        }
    for entry in bound_servers or []:
        name, value = _entry_to_opencode(entry)
        if name:
            mcp[name] = value
    return mcp


def _build_provider_dict(provider: str, api_key: str) -> dict[str, Any]:
    """返回 provider 配置 dict，产出 dict 供自包含临时配置。"""
    if provider == "deepseek":
        parsed: dict[str, Any] = json.loads(_OPENCODE_CONFIG_TEMPLATE.replace("{api_key}", api_key))
        return parsed
    return {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            provider: {
                "npm": "@ai-sdk/openai-compatible",
                "options": {"baseURL": "", "apiKey": api_key},
            }
        },
    }


def _write_opencode_config(provider: str, api_key: str, mcp_section: dict[str, Any]) -> str | None:
    """写自包含临时 opencode 配置（provider+mcp），返回路径供 OPENCODE_CONFIG。

    delete=False 持久化供 CLI 读取，atexit 清理（对齐 claude_code _write_mcp_config）。
    """
    config = _build_provider_dict(provider, api_key)
    config["mcp"] = mcp_section
    try:
        f = tempfile.NamedTemporaryFile(  # noqa: SIM115 — 故意 delete=False，atexit 清理
            mode="w",
            suffix=".json",
            prefix="agenthub_oc_",
            delete=False,
            dir=tempfile.gettempdir(),
        )
        json.dump(config, f, ensure_ascii=False)
        f.close()
        atexit.register(lambda p: os.unlink(p) if os.path.exists(p) else None, f.name)
        return f.name
    except Exception as exc:
        logger.warning("写 OpenCode MCP 配置失败，跳过 MCP 注入: %s", exc)
        return None
