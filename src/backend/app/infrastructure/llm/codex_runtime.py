"""CodexRuntime — OpenAI Codex CLI 子进程适配器 (v0.135+).

通过 `codex exec --json [prompt]` 调用，prompt 经 stdin 传入。
JSONL 输出事件：thread.started / turn.started / item.completed / turn.completed。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from collections.abc import AsyncIterator

from app.domain.llm.protocol import (
    AgentRequest,
    AgentRuntime,
    StreamEvent,
    StreamEventType,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 300  # 秒


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
    ) -> None:
        self._model = model
        self._agent_id = agent_id
        self._api_key = api_key
        self._timeout = timeout
        self._workspace = workspace
        self._process: asyncio.subprocess.Process | None = None

    async def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        prompt = self._extract_prompt(request)
        if not prompt:
            yield StreamEvent(type=StreamEventType.ERROR, seq=0, content="Codex: no user message")
            return

        binary = shutil.which("codex") or "codex"

        cmd = [binary, "exec", "--json"]
        if self._model:
            cmd.extend(["-c", f'model="{self._model}"'])

        # stdin 传 prompt；codex exec 用 `-` 表示从 stdin 读
        cmd.append("-")

        env = os.environ.copy()
        # 确保 HOME 在 Windows 下存在（codex 读 ~/.codex/config.toml）
        if "HOME" not in env:
            env["HOME"] = os.environ.get("USERPROFILE", "")
        # 注入 API key（如果 agent 有存储或环境变量有）
        if self._api_key:
            env["OPENAI_API_KEY"] = self._api_key

        logger.info("Codex spawn: %s (model=%s)", " ".join(cmd), self._model or "default")

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=self._workspace,
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
        - item.completed → 提取 item.text 作为 TEXT 事件
        - turn.completed → DONE 事件（含 usage）
        """
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return []

        event_type = data.get("type", "")
        events: list[StreamEvent] = []

        if event_type == "item.completed":
            item = data.get("item", {})
            text = item.get("text", "")
            if text:
                events.append(StreamEvent(type=StreamEventType.TEXT, seq=seq, content=text))
                seq += 1

        elif event_type == "turn.completed":
            usage = data.get("usage", {})
            events.append(
                StreamEvent(
                    type=StreamEventType.DONE,
                    seq=seq,
                    metadata={
                        "model": "codex-cli",
                        "token_usage": usage,
                        "is_error": False,
                    },
                )
            )

        return events
