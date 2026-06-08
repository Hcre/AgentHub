"""CodexRuntime — OpenAI Codex CLI 子进程适配器 (v0.135+).

通过 `codex exec --json [prompt]` 调用，prompt 经 stdin 传入。
JSONL 输出事件：thread.started / turn.started / item.completed / turn.completed。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
from collections.abc import AsyncIterator

from app.domain.llm.protocol import (
    AgentRequest,
    AgentRuntime,
    StreamEvent,
    StreamEventType,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 300  # 秒
_DEFAULT_MAX_TURNS = 10
_DEFAULT_PERMISSION_MODE = "bypassPermissions"


def _resolve_cwd(workspace: str | None) -> str | None:
    """将 workspace 转为可用 cwd。自动检测 Docker/宿主机。"""
    if not workspace:
        return None
    path = workspace.strip()
    if not path:
        return None
    m = re.match(r"^([A-Za-z]):[/\\](.*)", path)
    if m:
        # 先试原始路径（宿主机）
        if os.path.exists(path):
            return path
        # 再试 Docker mount
        rest = m.group(2).replace("\\", "/")
        container = f"/mnt/host_{m.group(1).lower()}/{rest}"
        if os.path.exists(container):
            return container
        logger.warning("workspace 路径不存在: %s", workspace)
        return None
    return path if os.path.exists(path) else None


class CodexRuntime(AgentRuntime):
    """Codex CLI 运行时 — codex exec --json [prompt] via stdin。"""

    def __init__(
        self,
        *,
        model: str = "",
        agent_id: str = "",
        api_key: str = "",
        timeout: int = _DEFAULT_TIMEOUT,
        workspace: str | None = None,
        permission_mode: str = _DEFAULT_PERMISSION_MODE,
        max_turns: int = _DEFAULT_MAX_TURNS,
        proxy_base: str = "",
    ) -> None:
        self._model = model
        self._agent_id = agent_id
        self._api_key = api_key
        self._timeout = timeout
        self._workspace = workspace
        self._permission_mode = permission_mode
        self._max_turns = max_turns
        self._proxy_url = (
            f"{proxy_base.rstrip('/')}/proxy/agents/{agent_id}" if proxy_base and agent_id else ""
        )
        self._process: asyncio.subprocess.Process | None = None

    async def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        # 构建完整 prompt：system_prompt + group_delta_text + 最后一条用户消息
        sp = request.system_prompt
        if request.group_delta_text:
            sp = "\n\n".join(filter(None, [sp, request.group_delta_text]))
        trigger = self._extract_prompt(request)
        if not trigger:
            yield StreamEvent(type=StreamEventType.ERROR, seq=0, content="Codex: no user message")
            return

        # 注入 system_prompt：Codex CLI 没有 --system-prompt flag，
        # 将 sp 作为 prompt 前缀拼接（SP 在前，用户消息在后）
        prompt = f"{sp}\n\n---\n\n{trigger}" if sp else trigger

        binary = shutil.which("codex") or "codex"

        cmd = [binary, "exec", "--json"]
        if self._model:
            cmd.extend(["-c", f'model="{self._model}"'])
        # 权限模式 + 最大轮次
        cmd.extend(["--approval-mode", self._permission_mode])
        cmd.extend(["--max-turns", str(self._max_turns)])

        # stdin 传 prompt；codex exec 用 `-` 表示从 stdin 读
        cmd.append("-")

        env = os.environ.copy()
        # 确保 HOME 在 Windows 下存在（codex 读 ~/.codex/config.toml）
        if "HOME" not in env:
            env["HOME"] = os.environ.get("USERPROFILE", "")
        # 代理模式：API key + base URL 通过环境变量注入
        if self._proxy_url:
            env["OPENAI_API_KEY"] = "agenthub-proxy"
            env["OPENAI_BASE_URL"] = self._proxy_url
        elif self._api_key:
            env["OPENAI_API_KEY"] = self._api_key

        logger.info("Codex spawn: %s (model=%s)", " ".join(cmd), self._model or "default")

        # 工作目录：从请求动态取（会话 workspace），fallback 构造函数参数
        cwd = _resolve_cwd(request.working_directory)
        if not cwd and self._workspace:
            cwd = _resolve_cwd(self._workspace)
        if (request.working_directory or self._workspace) and not cwd:
            yield StreamEvent(
                type=StreamEventType.TEXT,
                seq=0,
                content=f"⚠️ 工作目录不可用: {request.working_directory or self._workspace}\n请检查路径是否存在。",
            )

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd,
            )
        except FileNotFoundError:
            yield StreamEvent(type=StreamEventType.ERROR, seq=0, content="Codex CLI not found")
            return

        assert self._process.stdin is not None
        self._process.stdin.write(prompt.encode())
        self._process.stdin.write_eof()

        assert self._process.stdout is not None
        seq = 0
        try:
            async for line in self._read_lines_with_timeout(self._process.stdout):
                events = self._parse_line(line, seq)
                for evt in events:
                    yield evt
                    seq = evt.seq + 1
        except TimeoutError:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=seq,
                content=f"Codex CLI timeout ({self._timeout}s)",
            )
            await self.stop()
            return

        await self._process.wait()

        if self._process.returncode and self._process.returncode != 0:
            stderr = ""
            if self._process.stderr:
                stderr = (await self._process.stderr.read()).decode(errors="replace")
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=seq,
                content=f"Codex CLI exit {self._process.returncode}: {stderr[:500]}",
            )

        self._process = None

    async def stop(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.kill()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.terminate()
            self._process = None

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

    @staticmethod
    def _parse_line(line: str, seq: int) -> list[StreamEvent]:
        """解析 codex --json 输出行，转为 StreamEvent。

        codex JSONL 事件类型:
        - thread.started / turn.started → 跳过
        - item.completed → 提取 item.text (TEXT) + item.content[] 中的 tool_use (TOOL_CALL)
        - turn.completed → DONE 事件（含 usage / cost / duration）
        """
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Codex 非 JSON 行: %s", line[:200])
            return []

        event_type = data.get("type", "")
        events: list[StreamEvent] = []

        if event_type == "item.completed":
            item = data.get("item", {})
            # 提取纯文本
            text = item.get("text", "")
            if text:
                events.append(StreamEvent(type=StreamEventType.TEXT, seq=seq, content=text))
                seq += 1
            # 提取 content 数组中的 tool_use / tool_result blocks
            for block in item.get("content", []) or []:
                block_type = block.get("type", "")
                if block_type == "tool_use":
                    events.append(
                        StreamEvent(
                            type=StreamEventType.TOOL_CALL,
                            seq=seq,
                            tool_call=ToolCall(
                                call_id=block.get("id", ""),
                                name=block.get("name", ""),
                                arguments=block.get("input", {}),
                            ),
                        )
                    )
                    seq += 1
                elif block_type == "tool_result":
                    raw_content = block.get("content")
                    if isinstance(raw_content, list):
                        raw_content = "\n".join(
                            c.get("text", "")
                            for c in raw_content
                            if isinstance(c, dict) and c.get("type") == "text"
                        )
                    elif not isinstance(raw_content, str):
                        raw_content = str(raw_content) if raw_content is not None else None
                    is_error = block.get("is_error", False)
                    events.append(
                        StreamEvent(
                            type=StreamEventType.TOOL_RESULT,
                            seq=seq,
                            tool_result=ToolResult(
                                call_id=block.get("tool_use_id", ""),
                                success=not is_error,
                                content=raw_content if not is_error else None,
                                error=raw_content if is_error else None,
                            ),
                        )
                    )
                    seq += 1

        elif event_type == "turn.completed":
            usage = data.get("usage", {})
            metadata: dict = {
                "model": "codex-cli",
                "token_usage": usage,
                "is_error": False,
            }
            # 提取额外元数据（如果 codex 提供）
            cost = data.get("total_cost_usd")
            if cost is not None:
                metadata["total_cost_usd"] = cost
            duration = data.get("duration_ms")
            if duration is not None:
                metadata["duration_ms"] = duration
            is_error = data.get("is_error", False)
            if is_error:
                metadata["is_error"] = True
            errors = data.get("errors", [])
            if errors:
                metadata["errors"] = errors
            events.append(
                StreamEvent(type=StreamEventType.DONE, seq=seq, metadata=metadata)
            )

        return events
