"""ClaudeCodeRuntime：Claude Code CLI 运行时适配器。

通过 `claude --output-format stream-json --verbose` 启动子进程，
解析事件类型（system/assistant/user/result）映射为 StreamEvent。

会话持久化策略（利用 CLI 自带 session 机制，不自己拼历史）：
- 先尝试 --resume <session_id> 恢复对话
- CLI 返回 "No conversation found" 时 fallback --session-id 新建
- session_id 直接复用 AgentHub 的 session UUID
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
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
_DEFAULT_PERMISSION_MODE = "acceptEdits"


class ClaudeCodeRuntime(AgentRuntime):
    """Claude Code CLI 运行时（claude_code 模式）。"""

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str = "",
        base_url: str | None = None,
        permission_mode: str = _DEFAULT_PERMISSION_MODE,
        max_turns: int = _DEFAULT_MAX_TURNS,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._permission_mode = permission_mode
        self._max_turns = max_turns
        self._timeout = timeout
        self._process: asyncio.subprocess.Process | None = None

    async def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        """先 resume，找不到 session 时 fallback 新建。"""
        logger.info("Claude CLI request_id=%s session=%s", request.request_id, request.session_id)
        prompt = self._extract_prompt(request)
        session_key = str(request.session_id)

        async for event in self._run_cli(prompt, request, session_key, resume=True):
            if (
                event.type == StreamEventType.ERROR
                and "No conversation found" in (event.content or "")
            ):
                logger.info("Session %s 不存在，新建 CLI 会话", session_key)
                async for fallback_event in self._run_cli(
                    prompt, request, session_key, resume=False
                ):
                    yield fallback_event
                return
            yield event

    async def stop(self) -> None:
        """终止运行中的 CLI 进程。"""
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None

    # --- 内部方法 ---

    async def _run_cli(
        self,
        prompt: str,
        request: AgentRequest,
        session_key: str,
        *,
        resume: bool,
    ) -> AsyncIterator[StreamEvent]:
        """启动一次 CLI 进程并流式产出事件。"""
        cmd = self._build_cmd(request, session_key, resume=resume)
        env = self._build_env()

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

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
        except asyncio.TimeoutError:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=seq,
                content=f"Claude CLI 超时 ({self._timeout}s)",
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
                content=f"Claude CLI 退出码 {self._process.returncode}: {stderr[:500]}",
            )

        self._process = None

    def _build_cmd(
        self, request: AgentRequest, session_key: str, *, resume: bool
    ) -> list[str]:
        cmd = [
            "claude",
            "--output-format", "stream-json",
            "--verbose",
            "--print",
            "--permission-mode", self._permission_mode,
            "--max-turns", str(self._max_turns),
        ]
        if resume:
            cmd.extend(["--resume", session_key])
        else:
            cmd.extend(["--session-id", session_key])
        if request.system_prompt:
            cmd.extend(["--system-prompt", request.system_prompt])
        return cmd

    def _build_env(self) -> dict[str, str]:
        """构造 CLI 子进程环境变量，继承当前环境并覆盖 agent 配置。"""
        env = os.environ.copy()
        if self._api_key:
            env["ANTHROPIC_API_KEY"] = self._api_key
        if self._model:
            env["ANTHROPIC_MODEL"] = self._model
        if self._base_url:
            env["ANTHROPIC_BASE_URL"] = self._base_url
        return env

    @staticmethod
    def _extract_prompt(request: AgentRequest) -> str:
        """从 messages 提取最后一条 user 消息作为 prompt。"""
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    async def _read_lines_with_timeout(
        self, stdout: asyncio.StreamReader
    ) -> AsyncIterator[str]:
        """逐行读取 stdout，带总超时。"""
        deadline = asyncio.get_event_loop().time() + self._timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise asyncio.TimeoutError
            try:
                line = await asyncio.wait_for(stdout.readline(), timeout=remaining)
            except asyncio.TimeoutError:
                raise
            if not line:
                break
            decoded = line.decode(errors="replace").strip()
            if decoded:
                yield decoded

    @staticmethod
    def _parse_line(line: str, seq: int) -> list[StreamEvent]:
        """解析一行 stream-json 输出，返回 0~N 个 StreamEvent。

        支持的事件类型:
        - system: 跳过（可提取 init 元信息）
        - assistant: TEXT / TOOL_CALL / usage
        - user: TOOL_RESULT（CLI 内部工具执行结果）
        - result: DONE（含 permission_denials 等）
        """
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Claude CLI 非 JSON 行: %s", line[:200])
            return []

        event_type = data.get("type")
        events: list[StreamEvent] = []

        if event_type == "system":
            pass

        elif event_type == "assistant":
            message = data.get("message", {})
            for block in message.get("content", []):
                block_type = block.get("type")
                if block_type == "text":
                    events.append(StreamEvent(
                        type=StreamEventType.TEXT,
                        seq=seq,
                        content=block.get("text", ""),
                    ))
                    seq += 1
                elif block_type == "tool_use":
                    events.append(StreamEvent(
                        type=StreamEventType.TOOL_CALL,
                        seq=seq,
                        tool_call=ToolCall(
                            call_id=block.get("id", ""),
                            name=block.get("name", ""),
                            arguments=block.get("input", {}),
                        ),
                    ))
                    seq += 1

            usage = message.get("usage", {})
            if usage:
                events.append(StreamEvent(
                    type=StreamEventType.TEXT,
                    seq=seq,
                    content="",
                    metadata={"token_usage": usage},
                ))
                seq += 1

        elif event_type == "user":
            # CLI 内部工具执行结果
            for block in data.get("message", {}).get("content", []):
                if block.get("type") == "tool_result":
                    is_error = block.get("is_error", False)
                    events.append(StreamEvent(
                        type=StreamEventType.TOOL_RESULT,
                        seq=seq,
                        tool_result=ToolResult(
                            call_id=block.get("tool_use_id", ""),
                            success=not is_error,
                            content=block.get("content") if not is_error else None,
                            error=block.get("content") if is_error else None,
                        ),
                    ))
                    seq += 1

        elif event_type == "result":
            metadata: dict = {
                "model": data.get("model", "claude-code-cli"),
                "total_cost_usd": data.get("total_cost_usd", 0),
                "duration_ms": data.get("duration_ms", 0),
                "subtype": data.get("subtype", ""),
            }
            # 权限阻断信息
            denials = data.get("permission_denials", [])
            if denials:
                metadata["permission_denials"] = denials
                metadata["is_error"] = data.get("is_error", False)
            events.append(StreamEvent(
                type=StreamEventType.DONE,
                seq=seq,
                metadata=metadata,
            ))

        return events
