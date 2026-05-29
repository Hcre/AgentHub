"""ClaudeCodeRuntime：Claude Code CLI 运行时适配器。

支持两种 IO 模式（由 settings.claude_code_long_running 切换）：

V0（默认，短驻 + --resume）：
- 每次请求 spawn 新进程：stdin.write(prompt) + write_eof() → 读到 result → 退出
- 历史复用：先 --resume <session_key> 恢复；CLI 报 "No conversation found" → fallback --session-id 新建

V1（长驻 + stream-json，见 ADR-02 Phase 1）：
- 进程池缓存按 session_key 复用长驻进程，stdin 不关
- 每次请求通过 stdin 写一行 user JSONL；CLI 累积对话历史
- system_prompt 变化时 drop + 重 spawn（CLI 的 --system-prompt 仅 spawn 时生效）

session_key 规则（V0/V1 一致）：
- 私聊：session_key = session_id（UUID）
- 群聊：session_key = uuid5(session_id:agent_id)（确定性映射，CLI 只接受合法 UUID）
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from collections.abc import AsyncIterator
from functools import partial

from app.core.config import settings
from app.domain.llm.protocol import (
    AgentRequest,
    AgentRuntime,
    StreamEvent,
    StreamEventType,
    ToolCall,
    ToolResult,
)
from app.infrastructure.llm.claude_code_process_pool import (
    ProcessHandle,
    get_pool,
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
        model: str = "",
        agent_id: str = "",
        proxy_base: str = "",
        permission_mode: str = _DEFAULT_PERMISSION_MODE,
        max_turns: int = _DEFAULT_MAX_TURNS,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._model = model
        self._proxy_url = (
            f"{proxy_base.rstrip('/')}/proxy/agents/{agent_id}" if proxy_base and agent_id else ""
        )
        self._permission_mode = permission_mode
        self._max_turns = max_turns
        self._timeout = timeout
        self._process: asyncio.subprocess.Process | None = None

    async def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        """按 settings.claude_code_long_running 分流到 V0 / V1。"""
        logger.info(
            "Claude CLI request_id=%s session=%s mode=%s",
            request.request_id,
            request.session_id,
            "long" if settings.claude_code_long_running else "short",
        )
        if settings.claude_code_long_running:
            async for evt in self._stream_long_running(request):
                yield evt
            return

        # V0 短驻：先 resume，找不到 session fallback 新建
        prompt = self._extract_prompt(request)
        session_key = self._compute_session_key(request)
        async for event in self._run_cli(prompt, request, session_key, resume=True):
            if "No conversation found" in (event.content or "") or (
                event.type == StreamEventType.DONE
                and "No conversation found" in str(event.metadata)
            ):
                logger.info("Session %s 不存在，新建 CLI 会话", session_key)
                async for fallback_event in self._run_cli(
                    prompt, request, session_key, resume=False
                ):
                    yield fallback_event
                return
            yield event

    async def stop(self) -> None:
        """终止运行中的 CLI 进程（仅 V0 短驻进程；V1 长驻进程由进程池管理）。"""
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.kill()
            self._process = None

    # --- V1 长驻路径 ---

    async def _stream_long_running(
        self, request: AgentRequest
    ) -> AsyncIterator[StreamEvent]:
        """长驻模式：复用进程池，stdin 写 JSONL，stdout 流式读取。

        system_prompt 守卫：handle 缓存了 spawn 时的 sp 快照，本次请求 sp 不同时
        drop 旧进程重 spawn。私聊场景 sp 稳定 → 复用收益最大；群聊场景 ContextBuilder
        把 delta 拼进 sp，每轮都变 → 退化为每次 spawn（功能正确无收益，待后续工单
        把 delta 从 sp 中拆出来）。
        """
        session_key = self._compute_session_key(request)
        sp = request.system_prompt or ""
        prompt = self._extract_prompt(request)
        pool = get_pool()

        spawn = partial(self._spawn_long, sp, session_key)
        handle = await pool.acquire(session_key, spawn)

        if handle.spawn_system_prompt and handle.spawn_system_prompt != sp:
            logger.info(
                "Claude CLI key=%s system_prompt 变化，drop 重 spawn", session_key
            )
            await pool.drop(session_key)
            handle = await pool.acquire(session_key, spawn)
        handle.spawn_system_prompt = sp

        seq = 0
        try:
            async with handle.stdin_lock:
                await self._send_user_jsonl(handle, prompt)
                async for evt in self._read_until_done(handle, seq):
                    yield evt
                    seq = evt.seq + 1
        except TimeoutError:
            # 卡死的进程不应留池里 —— 下次请求会重 spawn
            await pool.drop(session_key)
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=seq,
                content=f"Claude CLI 长驻超时 ({self._timeout}s)",
            )
        except RuntimeError as exc:
            # stdout EOF / 子进程意外退出
            await pool.drop(session_key)
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=seq,
                content=f"Claude CLI 长驻进程异常: {exc}",
            )

    async def _spawn_long(
        self, system_prompt: str, session_key: str
    ) -> asyncio.subprocess.Process:
        """长驻 spawn：--input-format stream-json + --session-id，stdin 保留。"""
        cmd = [
            "claude",
            "--print",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            self._permission_mode,
            "--max-turns",
            str(self._max_turns),
            "--session-id",
            session_key,
        ]
        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])
        env = self._build_env()
        logger.info("Claude CLI 长驻 spawn key=%s", session_key)
        return await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

    @staticmethod
    async def _send_user_jsonl(handle: ProcessHandle, content: str) -> None:
        """往长驻进程 stdin 推一行 user message JSONL。"""
        assert handle.proc.stdin is not None
        payload = {"type": "user", "message": {"role": "user", "content": content}}
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        handle.proc.stdin.write(line.encode())
        await handle.proc.stdin.drain()

    async def _read_until_done(
        self, handle: ProcessHandle, start_seq: int
    ) -> AsyncIterator[StreamEvent]:
        """读 stdout 直到 type=result（DONE）；遇 EOF 抛 RuntimeError，超时抛 TimeoutError。"""
        assert handle.proc.stdout is not None
        seq = start_seq
        deadline = asyncio.get_event_loop().time() + self._timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError
            raw = await asyncio.wait_for(handle.proc.stdout.readline(), timeout=remaining)
            if not raw:
                raise RuntimeError(
                    f"stdout 关闭 (returncode={handle.proc.returncode})"
                )
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            events = self._parse_line(line, seq)
            for evt in events:
                yield evt
                seq = evt.seq + 1
                if evt.type == StreamEventType.DONE:
                    return

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
        except TimeoutError:
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

    def _build_cmd(self, request: AgentRequest, session_key: str, *, resume: bool) -> list[str]:
        cmd = [
            "claude",
            "--output-format",
            "stream-json",
            "--verbose",
            "--print",
            "--permission-mode",
            self._permission_mode,
            "--max-turns",
            str(self._max_turns),
        ]
        if resume:
            cmd.extend(["--resume", session_key])
        else:
            cmd.extend(["--session-id", session_key])
        if request.system_prompt:
            cmd.extend(["--system-prompt", request.system_prompt])
        return cmd

    def _build_env(self) -> dict[str, str]:
        """构造 CLI 子进程环境变量。

        代理模式（proxy_url 非空）：ANTHROPIC_BASE_URL 指向本地代理，API Key 为占位。
        全局模式（proxy_url 为空）：继承当前 shell 环境（用户自己的 Claude Code 配置）。
        """
        env = os.environ.copy()
        if self._proxy_url:
            env["ANTHROPIC_BASE_URL"] = self._proxy_url
            env["ANTHROPIC_API_KEY"] = "agenthub-proxy"
        if self._model:
            env["ANTHROPIC_MODEL"] = self._model
        return env

    @staticmethod
    def _extract_prompt(request: AgentRequest) -> str:
        """从 messages 提取最后一条 user 消息作为 prompt。"""
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    @staticmethod
    def _compute_session_key(request: AgentRequest) -> str:
        """CLI session key 计算。

        私聊：session_id（单 Agent 占用整个 session）
        群聊：uuid5(session_id:agent_id)，确定性映射为合法 UUID
              （CLI --session-id / --resume 均要求合法 UUID，见 §4.1）
        """
        if request.is_group_chat and request.agent_id is not None:
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{request.session_id}:{request.agent_id}"))
        return str(request.session_id)

    async def _read_lines_with_timeout(self, stdout: asyncio.StreamReader) -> AsyncIterator[str]:
        """逐行读取 stdout，带总超时。"""
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
                    events.append(
                        StreamEvent(
                            type=StreamEventType.TEXT,
                            seq=seq,
                            content=block.get("text", ""),
                        )
                    )
                    seq += 1
                elif block_type == "tool_use":
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

            usage = message.get("usage", {})
            if usage:
                events.append(
                    StreamEvent(
                        type=StreamEventType.TEXT,
                        seq=seq,
                        content="",
                        metadata={"token_usage": usage},
                    )
                )
                seq += 1

        elif event_type == "user":
            # CLI 内部工具执行结果
            for block in data.get("message", {}).get("content", []):
                if block.get("type") == "tool_result":
                    is_error = block.get("is_error", False)
                    events.append(
                        StreamEvent(
                            type=StreamEventType.TOOL_RESULT,
                            seq=seq,
                            tool_result=ToolResult(
                                call_id=block.get("tool_use_id", ""),
                                success=not is_error,
                                content=block.get("content") if not is_error else None,
                                error=block.get("content") if is_error else None,
                            ),
                        )
                    )
                    seq += 1

        elif event_type == "result":
            metadata: dict = {
                "model": data.get("model", "claude-code-cli"),
                "total_cost_usd": data.get("total_cost_usd", 0),
                "duration_ms": data.get("duration_ms", 0),
                "subtype": data.get("subtype", ""),
                "is_error": data.get("is_error", False),
            }
            # 权限阻断信息
            denials = data.get("permission_denials", [])
            if denials:
                metadata["permission_denials"] = denials
            # 错误列表（如 "No conversation found"）
            errors = data.get("errors", [])
            if errors:
                metadata["errors"] = errors
            events.append(
                StreamEvent(
                    type=StreamEventType.DONE,
                    seq=seq,
                    metadata=metadata,
                )
            )

        return events
