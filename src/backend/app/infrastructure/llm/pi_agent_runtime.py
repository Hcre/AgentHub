"""PiAgentRuntime: Pi Agent CLI 运行时适配器。

通过 `pi --mode rpc` 启动子进程，JSONL 双向协议。
- stdin:  发送 JSON commands (prompt/abort)
- stdout: 解析 JSONL events → StreamEvent

会话策略: --session <path>（AgentHub session UUID 映射为文件路径）
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from app.domain.llm.protocol import (
    AgentRequest,
    AgentRuntime,
    StreamEvent,
    StreamEventType,
    ToolCall,
    ToolResult,
)
from app.infrastructure.llm.cli_logger import get_log_path

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 300
_DEFAULT_THINKING_LEVEL = "off"
_DEFAULT_MAX_TURNS = 10
_DEFAULT_PERMISSION_MODE = "bypassPermissions"

# Provider → Pi --provider 参数
# Provider → Pi CLI --provider 参数值
_PROVIDER_MAP: dict[str, str] = {
    "anthropic": "anthropic",
    "openai": "openai",
    "deepseek": "deepseek",  # pi CLI 原生支持 deepseek provider（OpenAI 协议）
    "siliconflow": "openai",  # 硅基流动走 OpenAI 兼容协议
}

# Provider → API Key 环境变量
_PROVIDER_ENV_KEY: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "siliconflow": "OPENAI_API_KEY",
}

# Provider → 默认 Base URL（第三方端点需要显式设置）
_PROVIDER_BASE_URL: dict[str, str] = {
    "siliconflow": "https://api.siliconflow.cn/v1",
}


def _resolve_cwd(workspace: str | None) -> str | None:
    """将 workspace 转为可用 cwd。自动检测宿主机/Docker。"""
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
        return None
    return path if os.path.exists(path) else None


class PiAgentRuntime(AgentRuntime):
    """Pi Agent CLI 运行时（pi_agent 模式）。"""

    def __init__(
        self,
        *,
        agent_id: str = "",
        agent_name: str = "",
        thinking_level: str = _DEFAULT_THINKING_LEVEL,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._model = ""
        self._agent_id = agent_id
        self._agent_name = agent_name
        self._provider = ""
        self._api_key = ""
        self._base_url = ""
        self._thinking_level = thinking_level
        self._timeout = timeout
        self._proxy_url = ""
        self._permission_mode = "bypassPermissions"
        self._max_turns = 10

        self._session_dir = tempfile.mkdtemp(prefix="pi_agent_")

        self._process: asyncio.subprocess.Process | None = None

    async def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        # 合并群聊 delta 到 system_prompt（对齐 ClaudeCode V0 行为）
        sp = request.system_prompt
        if request.group_delta_text:
            sp = "\n\n".join(filter(None, [sp, request.group_delta_text]))

        prompt = self._extract_prompt(request)
        if not prompt:
            yield StreamEvent(type=StreamEventType.ERROR, seq=0, content="Pi Agent: 无用户消息")
            return

        # 群聊：agent_id 后缀确定性映射，避免跨 agent 会话污染
        session_key = self._compute_session_key(request)
        session_file = str(Path(self._session_dir) / f"{session_key}.jsonl")

        logger.info(
            "Pi Agent request_id=%s session_key=%s provider=%s model=%s",
            request.request_id,
            session_key,
            self._provider,
            self._model,
        )

        cmd = self._build_cmd(session_file, request, sp)
        env = self._build_env()
        logger.debug("Pi CLI cmd: %s", " ".join(cmd))

        cwd = _resolve_cwd(request.working_directory)
        if request.working_directory and not cwd:
            yield StreamEvent(
                type=StreamEventType.TEXT,
                seq=0,
                content=f"⚠️ 工作目录不可用: {request.working_directory}\n请检查路径是否存在。",
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
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=0,
                content=f"⚠️ pi CLI 未安装或路径不存在: {cwd or '当前目录'}",
            )
            return
        except OSError as exc:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=0,
                content=f"⚠️ pi CLI 启动失败: {exc}",
            )
            return

        prompt_cmd = json.dumps({"type": "prompt", "message": prompt}) + "\n"
        assert self._process.stdin is not None
        assert self._process.stdout is not None

        # 发送 prompt command
        self._process.stdin.write(prompt_cmd.encode())
        await self._process.stdin.drain()

        # 读取并解析 stdout JSONL
        # Windows 上 asyncio.wait_for 无法取消子进程管道 readline（底层 I/O 不支持 cancellation），
        # 所以用并行 watchdog task：超时后 force-kill 子进程 → stdout 关闭 → readline 返回 EOF。
        seq = 0
        watchdog_task: asyncio.Task[None] | None = None
        timed_out = False

        async def _watchdog() -> None:
            nonlocal timed_out
            try:
                await asyncio.sleep(self._timeout)
                timed_out = True
                logger.warning(
                    "Pi Agent 超时 (%ss)，强制终止子进程 pid=%s",
                    self._timeout,
                    self._process.pid if self._process else "?",
                )
                await self.stop()
            except asyncio.CancelledError:
                pass  # 正常完成，取消 watchdog

        if self._process and self._process.stdout:
            watchdog_task = asyncio.create_task(_watchdog())
            try:
                async for line in self._read_lines(self._process.stdout, str(request.session_id)):
                    events = self._parse_line(line, seq)
                    for evt in events:
                        yield evt
                        seq = evt.seq + 1
                    if events and events[-1].type in (StreamEventType.DONE, StreamEventType.ERROR):
                        break
            finally:
                # 确保 watchdog 被取消（正常完成或异常退出）
                if watchdog_task and not watchdog_task.done():
                    watchdog_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await watchdog_task

        if timed_out:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=seq,
                content=f"Pi Agent 超时 ({self._timeout}s)，已强制终止。请重试或简化任务。",
            )
            return

        # 关闭 stdin 并等待退出
        if self._process.stdin and not self._process.stdin.is_closing():
            with suppress(Exception):
                self._process.stdin.close()
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
                    content=f"Pi Agent 退出码 {self._process.returncode}: {stderr[:500]}",
                )

        self._process = None

    async def stop(self) -> None:
        if self._process and self._process.returncode is None:
            # 先尝试优雅 abort
            if self._process.stdin and not self._process.stdin.is_closing():
                with suppress(Exception):
                    self._process.stdin.write(b'{"type":"abort"}\n')
                    await self._process.stdin.drain()
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.kill()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=3)
                except TimeoutError:
                    await self._force_kill_subprocess()
            self._process = None

    async def _force_kill_subprocess(self) -> None:
        """跨平台强制杀子进程 — Windows taskkill / Unix kill -9。
        在 asyncio wait_for 无法取消 Windows 子进程管道 I/O 时兜底。"""
        if self._process is None:
            return
        pid = self._process.pid
        if pid is None:
            return
        import platform
        import subprocess as _sub

        if platform.system() == "Windows":
            with suppress(Exception):
                _sub.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=10,
                )
        else:
            with suppress(Exception):
                os.kill(pid, 9)

    # --- 内部方法 ---

    @staticmethod
    def _pi_binary() -> str:
        """查找 pi CLI 路径，优先用全局安装，fallback 到本地构建。"""
        pi = shutil.which("pi")
        if pi:
            return pi
        # fallback: 检查本地 clone（跨平台脚本）
        import platform

        local_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "pi-agent"
        if platform.system() == "Windows":
            for ext in (".cmd", ".bat", ".ps1", ".sh"):
                local = local_dir / f"pi-test{ext}"
                if local.exists():
                    return str(local)
        else:
            local = local_dir / "pi-test.sh"
            if local.exists():
                return str(local)
        return "pi"  # 最后 fallback

    def _build_cmd(
        self, session_file: str, request: AgentRequest, sp: str | None = None
    ) -> list[str]:
        cmd = [
            self._pi_binary(),
            "--mode",
            "rpc",
            "--session",
            session_file,
        ]

        if self._thinking_level != "off":
            cmd.extend(["--thinking", self._thinking_level])

        # 无界面服务器模式：禁用上下文文件 + 用户扩展，确保确定性行为
        cmd.extend(["--no-context-files", "--no-extensions"])

        if sp:
            if self._agent_name:
                sp = f"你的名字是{self._agent_name}。\n\n{sp}"
            # Windows 命令行长度限制 8191 字符：长 system_prompt 有风险，记录警告
            if len(sp) > 7000:
                logger.warning(
                    "Pi Agent system_prompt 长度 %s 接近 Windows 命令行限制 8191，可能被截断",
                    len(sp),
                )
            cmd.extend(["--system-prompt", sp])

        # 工具允许列表映射（如果上游支持 --tools flag）
        if request.available_tools:
            cmd.extend(["--tools", ",".join(request.available_tools)])

        # NB-02: MCP 注入 seam — blocked on upstream pi CLI MCP support（见 ADR-06 §2.3 / RT-MCP §3）
        # 解除条件：确认 pi CLI 的 MCP config 或 extension 通道存在 → 按 ADR-06 统一原则把
        #   request.mcp_servers 经 _entry_to_pi 翻译 + 逐调用通道注入 + 实测（本机当前无 pi 二进制可验证）。

        return cmd

    def _build_env(self) -> dict[str, str]:
        """构造 CLI 子进程环境变量。不注入 provider/model/api_key——CLI 读本地配置。"""
        return os.environ.copy()

    @staticmethod
    def _extract_prompt(request: AgentRequest) -> str:
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    @staticmethod
    def _compute_session_key(request: AgentRequest) -> str:
        """会话键：群聊使用 session_id（单 agent 视角），私聊直接使用 session_id。

        Pi CLI 使用文件路径存储会话，不需要 UUID 合法性检查，但仍需隔离。
        """
        if request.is_group_chat and request.agent_id is not None:
            return f"{request.session_id}_{request.agent_id}"
        return str(request.session_id)

    @staticmethod
    async def _read_lines(stdout: asyncio.StreamReader, session_id: str = "") -> AsyncIterator[str]:
        """读取 stdout 行，不做超时（超时由 watchdog task 杀进程 → EOF 来保证）。
        同时将输出写入 cli_logger 日志文件。"""
        log_fh = None
        if session_id:
            log_path = get_log_path(session_id)
            log_fh = open(log_path, "a", encoding="utf-8", errors="replace")
            log_fh.write(f"\n=== Pi Agent {datetime.now(UTC).isoformat()} ===\n")
            log_fh.flush()
        try:
            while True:
                line = await stdout.readline()
                if not line:
                    break
                decoded = line.decode(errors="replace").strip()
                if decoded:
                    if log_fh:
                        log_fh.write(decoded + "\n")
                        log_fh.flush()
                    yield decoded
        finally:
            if log_fh:
                log_fh.close()

    def _parse_line(self, line: str, seq: int) -> list[StreamEvent]:
        """解析一行 Pi RPC JSONL 输出，映射为 StreamEvent 列表。

        Pi RPC 事件 → StreamEventType:
        - message_update.text_delta    → TEXT
        - message_update.thinking_delta → THINKING
        - message_update.toolcall_delta → (累积，最终由 toolcall_end 产出 TOOL_CALL)
        - message_update.toolcall_end  → TOOL_CALL
        - message_update.done          → DONE (turn 结束)
        - message_update.error         → ERROR
        - tool_execution_start         → (无事件产出)
        - tool_execution_update        → TEXT（流式工具输出增量）
        - tool_execution_end           → TOOL_RESULT
        - agent_start                  → THINKING（前端显示忙碌指示器）
        - agent_end                    → DONE (流结束)
        - extension_ui_request         → REQUEST_APPROVAL
        - extension_error              → ERROR
        - compaction_start/end         → THINKING（进度指示）
        - auto_retry_start             → THINKING（进度指示）
        - auto_retry_end               → ERROR（最终失败时）
        """
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Pi 非 JSON 行: %s", line[:200])
            return []

        event_type = data.get("type")
        events: list[StreamEvent] = []

        if event_type == "message_update":
            events = self._parse_message_update(data, seq)

        elif event_type == "message_start":
            # 非流式模式：message_start 包含完整 content 数组
            msg = data.get("message", {})
            if msg.get("role") == "assistant":
                events = self._extract_message_content(msg, seq)

        elif event_type == "message_end":
            # 非流式模式：message_end 是最终版本，含 stopReason/errorMessage
            msg = data.get("message", {})
            if msg.get("role") == "assistant":
                if msg.get("stopReason") == "error":
                    err = msg.get("errorMessage", "Pi agent error")
                    events = [StreamEvent(type=StreamEventType.ERROR, seq=seq, content=err)]
                else:
                    events = self._extract_message_content(msg, seq)

        elif event_type == "agent_start":
            # Agent 启动 → THINKING 事件，让前端显示忙碌指示器
            events = [
                StreamEvent(
                    type=StreamEventType.THINKING,
                    seq=seq,
                    content="Pi Agent 正在启动…",
                )
            ]

        elif event_type == "tool_execution_start":
            pass  # 不产出事件，等待 tool_execution_update / tool_execution_end

        elif event_type == "tool_execution_update":
            # 流式工具输出增量 → 作为 TEXT 事件递送（实时显示工具输出）
            delta = data.get("delta", data.get("output", ""))
            if delta:
                call_id = data.get("toolCallId", "")
                events = [
                    StreamEvent(
                        type=StreamEventType.TEXT,
                        seq=seq,
                        content=f"[工具输出] {delta}" if call_id else delta,
                    )
                ]

        elif event_type == "tool_execution_end":
            te = data
            is_error = te.get("isError", False)
            raw = te.get("result")
            # RPC 规范：result 是对象 { content: [{type, text}...], details: {truncation, fullOutputPath} }
            content_str = ""
            if isinstance(raw, dict):
                content_arr = raw.get("content", [])
                if isinstance(content_arr, list):
                    parts = []
                    for c in content_arr:
                        if isinstance(c, dict) and c.get("type") == "text":
                            parts.append(c.get("text", ""))
                    content_str = "\n".join(parts)
                # 截断提示：如果输出被截断，附加提示
                details = raw.get("details", {})
                if isinstance(details, dict) and details.get("truncation"):
                    full_path = details.get("fullOutputPath", "")
                    content_str += (
                        f"\n\n[输出已截断，完整内容: {full_path}]"
                        if full_path
                        else "\n\n[输出已截断]"
                    )
                if not content_str:
                    content_str = json.dumps(raw, ensure_ascii=False)
            elif isinstance(raw, str):
                content_str = raw
            elif raw is not None:
                content_str = str(raw)
            events = [
                StreamEvent(
                    type=StreamEventType.TOOL_RESULT,
                    seq=seq,
                    tool_result=ToolResult(
                        call_id=te.get("toolCallId", ""),
                        success=not is_error,
                        content=content_str if not is_error else None,
                        error=content_str if is_error else None,
                    ),
                )
            ]

        elif event_type == "compaction_start":
            # 上下文压缩开始 → THINKING（进度指示）
            logger.info("Pi Agent 压缩中 (session=%s)", data.get("sessionId", "?"))
            events = [
                StreamEvent(
                    type=StreamEventType.THINKING,
                    seq=seq,
                    content="正在压缩上下文…",
                )
            ]

        elif event_type == "compaction_end":
            # 压缩完成：检查是否有错误
            if not data.get("success", True):
                err = data.get("error", "压缩失败")
                logger.warning("Pi Agent 压缩失败: %s", err)
                events = [
                    StreamEvent(
                        type=StreamEventType.ERROR,
                        seq=seq,
                        content=f"上下文压缩失败: {err}",
                    )
                ]
            else:
                logger.debug("Pi Agent 压缩完成")

        elif event_type == "auto_retry_start":
            attempt = data.get("attempt", 1)
            max_attempts = data.get("maxAttempts", "?")
            events = [
                StreamEvent(
                    type=StreamEventType.THINKING,
                    seq=seq,
                    content=f"正在重试 ({attempt}/{max_attempts})…",
                )
            ]

        elif event_type == "auto_retry_end":
            if not data.get("success", True):
                err = data.get("error", "重试耗尽")
                logger.warning("Pi Agent 自动重试失败: %s", err)
                events = [
                    StreamEvent(
                        type=StreamEventType.ERROR,
                        seq=seq,
                        content=f"自动重试失败: {err}",
                    )
                ]
            else:
                logger.debug("Pi Agent 自动重试成功")

        elif event_type == "extension_error":
            ext_name = data.get("extensionName", data.get("name", "unknown"))
            err_msg = data.get("error", data.get("message", "扩展错误"))
            logger.warning("Pi 扩展错误 [%s]: %s", ext_name, err_msg)
            events = [
                StreamEvent(
                    type=StreamEventType.ERROR,
                    seq=seq,
                    content=f"扩展 [{ext_name}] 错误: {err_msg}",
                )
            ]

        elif event_type == "agent_end":
            messages = data.get("messages", [])
            metadata: dict = {"model": self._model or "pi-agent"}
            for msg in reversed(messages):
                if msg.get("role") == "assistant" and msg.get("usage"):
                    metadata["usage"] = msg["usage"]
                    metadata["model"] = msg.get("model", metadata["model"])
                    break
            events = [StreamEvent(type=StreamEventType.DONE, seq=seq, metadata=metadata)]

        elif event_type == "extension_ui_request":
            ui = data
            events = [
                StreamEvent(
                    type=StreamEventType.REQUEST_APPROVAL,
                    seq=seq,
                    content=json.dumps(
                        {
                            "method": ui.get("method", ""),
                            "message": ui.get("message", ""),
                            "options": ui.get("options", []),
                            "timeout": ui.get("timeout"),
                        }
                    ),
                    metadata={
                        "pi_ui_id": ui.get("id", ""),
                        "pi_ui_method": ui.get("method", ""),
                    },
                )
            ]

        elif event_type == "response":
            # RPC command response（如 prompt 失败返回错误）
            if not data.get("success", True):
                logger.info("Pi RPC response error: %s", data.get("error", "")[:100])
                events = [
                    StreamEvent(
                        type=StreamEventType.ERROR,
                        seq=seq,
                        content=data.get("error", "Pi RPC command failed"),
                    )
                ]
            else:
                logger.debug("Pi RPC response success for command=%s", data.get("command"))

        return events

    @staticmethod
    def _extract_message_content(msg: dict, seq: int) -> list[StreamEvent]:
        """从 Pi message 对象提取文本/思考/工具调用，映射为 StreamEvent 列表。"""
        events: list[StreamEvent] = []
        for block in msg.get("content", []) or []:
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
            elif block_type == "thinking":
                events.append(
                    StreamEvent(
                        type=StreamEventType.THINKING,
                        seq=seq,
                        content=block.get("thinking", ""),
                    )
                )
                seq += 1
            elif block_type == "tool_call":
                events.append(
                    StreamEvent(
                        type=StreamEventType.TOOL_CALL,
                        seq=seq,
                        tool_call=ToolCall(
                            call_id=block.get("id", ""),
                            name=block.get("name", ""),
                            arguments=block.get("args", {}),
                        ),
                    )
                )
                seq += 1
        return events

    @staticmethod
    def _parse_message_update(data: dict, seq: int) -> list[StreamEvent]:
        """解析 message_update 事件内的 assistantMessageEvent delta。"""
        delta = data.get("assistantMessageEvent", {})
        delta_type = delta.get("type", "")
        events: list[StreamEvent] = []

        if delta_type == "text_delta":
            events.append(
                StreamEvent(
                    type=StreamEventType.TEXT,
                    seq=seq,
                    content=delta.get("delta", ""),
                )
            )

        elif delta_type == "thinking_delta":
            events.append(
                StreamEvent(
                    type=StreamEventType.THINKING,
                    seq=seq,
                    content=delta.get("delta", ""),
                )
            )

        elif delta_type == "toolcall_delta":
            # 工具调用参数增量 — 暂不单独产出事件，最终由 toolcall_end 产出完整 TOOL_CALL
            logger.debug(
                "Pi toolcall_delta: call_id=%s delta_len=%s",
                delta.get("id", "?"),
                len(delta.get("delta", "")),
            )

        elif delta_type == "toolcall_end":
            tc = delta.get("toolCall", {})
            events.append(
                StreamEvent(
                    type=StreamEventType.TOOL_CALL,
                    seq=seq,
                    tool_call=ToolCall(
                        call_id=tc.get("id", ""),
                        name=tc.get("name", ""),
                        arguments=tc.get("args", {}),
                    ),
                )
            )

        elif delta_type == "done":
            pass  # turn 结束，不产出事件（等待 agent_end 才发 DONE）

        elif delta_type == "error":
            events.append(
                StreamEvent(
                    type=StreamEventType.ERROR,
                    seq=seq,
                    content=delta.get("error", "Pi Agent error"),
                )
            )

        return events
