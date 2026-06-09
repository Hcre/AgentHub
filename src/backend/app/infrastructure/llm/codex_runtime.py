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
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime

from app.domain.llm.protocol import (
    AgentRequest,
    AgentRuntime,
    StreamEvent,
    StreamEventType,
    ToolCall,
    ToolResult,
)
from app.infrastructure.llm.cli_logger import get_log_path, spawn_visible_terminal
from app.infrastructure.llm.process_registry import save_spawn_info

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
        agent_id: str = "",
        timeout: int = _DEFAULT_TIMEOUT,
        workspace: str | None = None,
    ) -> None:
        self._model = ""
        self._agent_id = agent_id
        self._api_key = ""
        self._timeout = timeout
        self._workspace = workspace
        self._proxy_url = ""
        self._permission_mode = "bypassPermissions"
        self._max_turns = 10
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
            cmd.extend(["-m", self._model])
        # 全部权限绕过（与 Claude Code bypassPermissions 对齐）
        cmd.append("--dangerously-bypass-approvals-and-sandbox")
        # 工作目录：从请求动态取（会话 workspace），通过 -C flag 传给 Codex
        cwd = _resolve_cwd(request.working_directory)
        if not cwd and self._workspace:
            cwd = _resolve_cwd(self._workspace)
        if cwd:
            cmd.extend(["-C", cwd])
        elif request.working_directory or self._workspace:
            yield StreamEvent(
                type=StreamEventType.TEXT,
                seq=0,
                content=f"⚠️ 工作目录不可用: {request.working_directory or self._workspace}\n请检查路径是否存在。",
            )

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

        session_key = self._compute_session_key(request)
        logger.info(
            "Codex spawn: %s session_key=%s model=%s",
            " ".join(cmd), session_key, self._model or "default",
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
        except (FileNotFoundError, OSError):
            yield StreamEvent(type=StreamEventType.ERROR, seq=0, content="Codex CLI not found")
            return

        save_spawn_info(session_key, cmd=cmd, env=env, cwd=cwd, prompt_text=prompt)

        # 尝试打开可见终端用于调试；失败静默回退 headless 模式
        ok = spawn_visible_terminal(cmd, env, cwd, session_key, prompt)
        if not ok:
            logger.debug("Visible terminal unavailable for session=%s, continuing headless", session_key)

        assert self._process.stdin is not None
        self._process.stdin.write(prompt.encode())
        self._process.stdin.write_eof()

        assert self._process.stdout is not None
        seq = 0
        watchdog_task: asyncio.Task[None] | None = None
        timed_out = False

        async def _watchdog() -> None:
            nonlocal timed_out
            try:
                await asyncio.sleep(self._timeout)
                timed_out = True
                logger.warning(
                    "Codex CLI 超时 (%ss)，强制终止子进程 pid=%s",
                    self._timeout,
                    self._process.pid if self._process else "?",
                )
                await self.stop()
            except asyncio.CancelledError:
                pass

        if self._process and self._process.stdout:
            watchdog_task = asyncio.create_task(_watchdog())
            try:
                async for line in self._read_lines(self._process.stdout, str(request.session_id)):
                    events = self._parse_line(line, seq)
                    for evt in events:
                        yield evt
                        seq = evt.seq + 1
            finally:
                if watchdog_task and not watchdog_task.done():
                    watchdog_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await watchdog_task

        if timed_out:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=seq,
                content=f"Codex CLI 超时 ({self._timeout}s)，已强制终止。请重试。",
            )
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
        """3-tier graceful stop: SIGINT → SIGTERM → SIGKILL（对齐 ClaudeCodeRuntime）。"""
        if self._process and self._process.returncode is None:
            import signal

            try:
                self._process.send_signal(signal.SIGINT)
                await asyncio.wait_for(self._process.wait(), timeout=2)
            except (TimeoutError, ProcessLookupError):
                pass
            if self._process.returncode is None:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=2)
                except (TimeoutError, ProcessLookupError):
                    pass
            if self._process.returncode is None:
                self._process.kill()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=2)
                except TimeoutError:
                    await self._force_kill_subprocess()
            self._process = None

    async def _force_kill_subprocess(self) -> None:
        """跨平台强制杀子进程。asyncio wait_for 无法取消 Windows 管道 I/O 时兜底。"""
        if self._process is None:
            return
        pid = self._process.pid
        if pid is None:
            return
        import platform
        import subprocess as _sub

        if platform.system() == "Windows":
            try:
                _sub.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=10,
                )
            except Exception:
                pass
        else:
            with suppress(Exception):
                os.kill(pid, 9)

    @staticmethod
    def _compute_session_key(request: AgentRequest) -> str:
        """会话键：群聊使用 uuid5(session_id:agent_id) 避免跨 agent 污染（对齐 ClaudeCode）。"""
        if request.is_group_chat and request.agent_id is not None:
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{request.session_id}:{request.agent_id}"))
        return str(request.session_id)

    @staticmethod
    def _extract_prompt(request: AgentRequest) -> str:
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    @staticmethod
    async def _read_lines(stdout: asyncio.StreamReader, session_id: str) -> AsyncIterator[str]:
        """读取 stdout 行，不做超时（超时由 watchdog task 杀进程 → EOF 来保证）。

        每行实时写入 CLI 日志文件（~/.agenthub/cli-logs/{session_id}.log），
        前端可通过 API 获取路径进行 tail 查看。
        """

        log_path = get_log_path(session_id)
        with open(log_path, "a", encoding="utf-8", errors="replace") as log_fh:
            while True:
                line = await stdout.readline()
                if not line:
                    break
                decoded = line.decode(errors="replace").strip()
                if decoded:
                    ts = datetime.now(UTC).isoformat()
                    log_fh.write(f"[{ts}] {decoded}\n")
                    log_fh.flush()
                    yield decoded

    @staticmethod
    def _parse_line(line: str, seq: int) -> list[StreamEvent]:
        """解析 codex --json 输出行，转为 StreamEvent。

        codex JSONL 事件类型:
        - thread.started / turn.started → 跳过
        - item.completed → 提取 item.text (TEXT) + item.content[] 中的
          tool_use (TOOL_CALL) / thinking (THINKING) / tool_result (TOOL_RESULT)
          + 每 item 的 usage 元数据
        - turn.completed → DONE 事件（含 usage / cost / duration / permission_denials）
        - 未知类型 → 记录 warning，若含 text/content 则回退为 TEXT
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
            # 提取 content 数组中的 tool_use / thinking / tool_result blocks
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
                elif block_type == "thinking":
                    # Codex 推理块 → THINKING 事件（前端 ThinkingBlock 渲染）
                    thinking_text = block.get("thinking", "")
                    if thinking_text:
                        events.append(
                            StreamEvent(
                                type=StreamEventType.THINKING,
                                seq=seq,
                                content=thinking_text,
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
            # 提取 per-item usage 元数据（附加到最后产生的事件上）
            item_usage = item.get("usage", {})
            if item_usage and events:
                last = events[-1]
                meta = dict(last.metadata or {})
                meta["token_usage"] = item_usage
                events[-1] = last.model_copy(update={"metadata": meta})

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
            # 提取 permission_denials（如 codex 提供）
            permission_denials = data.get("permission_denials", [])
            if permission_denials:
                metadata["permission_denials"] = permission_denials
            events.append(
                StreamEvent(type=StreamEventType.DONE, seq=seq, metadata=metadata)
            )

        elif event_type in ("thread.started", "turn.started"):
            pass  # 跳过元事件

        else:
            # 未知事件类型：记录 warning，若含 text/content 则回退为 TEXT
            logger.debug("Codex 未知事件类型: %s keys=%s", event_type, list(data.keys())[:5])
            fallback_text = data.get("text") or data.get("content")
            if fallback_text and isinstance(fallback_text, str):
                events.append(
                    StreamEvent(type=StreamEventType.TEXT, seq=seq, content=fallback_text)
                )

        return events
