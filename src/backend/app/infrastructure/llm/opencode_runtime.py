"""OpenCodeRuntime — OpenCode CLI 子进程适配器 (v1.15+)。

多轮对话通过 opencode 原生 --session 实现：
- 首次调用 spawn opencode run，从 stdout 捕获 sessionID
- 后续调用加 --session <id>，opencode 自动维护上下文
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncIterator
from contextlib import suppress
from pathlib import Path
from typing import ClassVar

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
        env_key = self._PROVIDER_ENV.get(self._provider)
        if env_key and self._api_key:
            env[env_key] = self._api_key
            # 动态写入 opencode.jsonc，注入 AgentHub 解密后的 key
            _write_provider_config(self._provider, self._api_key)

        # 多轮对话：首次创建 session，后续用 --session 继续
        ah_session = str(request.session_id)
        oc_session = _session_map.get(ah_session)

        cmd = [binary, "run", "--format", "json", "--pure"]
        if oc_session:
            cmd.extend(["--session", oc_session])
        cmd.extend(["--model", self._model, "--dangerously-skip-permissions", prompt])

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
                stderr=asyncio.subprocess.PIPE,
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

        def _s(key: str, default: str = "") -> str:
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
                        call_id=str(data.get("id", data.get("call_id", ""))),
                        name=str(data.get("name", "")),
                        arguments=data.get("arguments", data.get("args", {})),
                    ),
                )
            )
        elif event_type == "tool_result":
            tr = data
            tr_content = tr.get("content", tr.get("result", ""))
            if not isinstance(tr_content, str):
                tr_content = json.dumps(tr_content, ensure_ascii=False)
            events.append(
                StreamEvent(
                    type=StreamEventType.TOOL_RESULT,
                    seq=seq,
                    tool_result=ToolResult(
                        call_id=str(tr.get("id", tr.get("call_id", ""))),
                        success=not tr.get("is_error", False),
                        content=tr_content,
                    ),
                )
            )
        elif event_type in ("done", "result", "complete", "exit"):
            events.append(
                StreamEvent(type=StreamEventType.DONE, seq=seq, metadata={"model": self._model})
            )
        elif event_type == "error":
            events.append(
                StreamEvent(
                    type=StreamEventType.ERROR,
                    seq=seq,
                    content=_s("message") or _s("error") or "OpenCode error",
                )
            )
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
