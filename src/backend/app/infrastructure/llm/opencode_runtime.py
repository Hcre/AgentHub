"""OpenCodeRuntime — OpenCode CLI 子进程适配器 (v1.15+)。

多轮对话通过 opencode 原生 --session 实现：
- 首次调用 spawn opencode run，从 stdout 捕获 sessionID
- 后续调用加 --session <id>，opencode 自动维护上下文

session_key 规则（对齐 ClaudeCodeRuntime）：
- 私聊：session_key = session_id（字符串）
- 群聊：uuid5(session_id:agent_id)（确定性映射，避免跨 agent 会话污染）
"""

from __future__ import annotations

import asyncio
import atexit
import json
import logging
import os
import re
import tempfile
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
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
from app.infrastructure.llm.cli_logger import get_log_path

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 120
_DEFAULT_MAX_TURNS = 10
_DEFAULT_PERMISSION_MODE = "bypassPermissions"

# AgentHub session UUID → opencode session ID
_session_map: dict[str, str] = {}


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
        agent_id: str = "",
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._model = ""
        self._agent_id = agent_id
        self._provider = ""
        self._api_key = ""
        self._timeout = timeout
        self._proxy_url = ""
        self._permission_mode = "bypassPermissions"
        self._process: asyncio.subprocess.Process | None = None
        self._text_seen = False

    async def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        # 合并群聊 delta 到 system_prompt（对齐 ClaudeCode V0 行为）
        sp = request.system_prompt
        if request.group_delta_text:
            sp = "\n\n".join(filter(None, [sp, request.group_delta_text]))

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

        cwd = _resolve_cwd(request.working_directory)
        if request.working_directory and not cwd:
            yield StreamEvent(
                type=StreamEventType.TEXT,
                seq=0,
                content=f"⚠️ 工作目录不可用: {request.working_directory}\n请检查路径是否存在。",
            )

        env = os.environ.copy()
        # opencode Unix 风格，用 $HOME/.config 找配置文件
        if "HOME" not in env:
            env["HOME"] = os.environ.get("USERPROFILE", "")

        # MCP 注入：仅注入 step-tools / memory MCP（不注入 provider/model——CLI 读本地配置）
        mcp_section = _build_opencode_mcp(
            request.mcp_servers, settings.mcp_memory_url, self._agent_id
        )
        if mcp_section:
            cfg_path = _write_opencode_config(mcp_section)
            if cfg_path:
                env["OPENCODE_CONFIG"] = cfg_path

        # 多轮对话：首次创建 session，后续用 --session 继续
        # 群聊：uuid5(session_id:agent_id) 确定性映射，避免跨 agent 会话污染
        session_key = self._compute_session_key(request)
        oc_session = _session_map.get(session_key)

        cmd = [binary, "run", "--format", "json", "--pure"]
        if oc_session:
            cmd.extend(["--session", oc_session])
        # 工作目录通过子进程 cwd 传入（--dir 会触发 opencode coding-agent 流水线卡死，
        # 详见 docs/explore/黎/opencode-issue-log.md；--pure 模式下用 cwd 即可）。

        # system_prompt 拼进完整 prompt，通过 stdin 传入（避免 Windows 命令行长度限制）
        if sp:
            prompt = f"{sp}\n\n---\n\n{prompt}"

        logger.info(
            "OpenCode spawn: %s session_key=%s provider=%s oc_session=%s permission=%s",
            " ".join(cmd),
            session_key,
            self._provider,
            oc_session or "new",
            self._permission_mode,
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
            # prompt 通过 stdin 传入，不放在命令行（避免 Windows 命令行长度限制）
            if self._process.stdin:
                self._process.stdin.write(prompt.encode())
                self._process.stdin.write_eof()
        except FileNotFoundError:
            yield StreamEvent(type=StreamEventType.ERROR, seq=0, content="OpenCode CLI 启动失败")
            return
        except OSError as exc:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=0,
                content=f"OpenCode CLI 启动失败: {exc}",
            )
            return

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
                    "OpenCode 超时 (%ss)，强制终止子进程 pid=%s",
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
                    # 从首个事件中提取 opencode sessionID
                    if not oc_session:
                        sid = _extract_session_id(line)
                        if sid:
                            _session_map[session_key] = sid
                            logger.debug("OpenCode session %s → %s", session_key, sid)

                    events = self._parse_line(line, seq)
                    for evt in events:
                        yield evt
                        seq = evt.seq + 1
                    if events and events[-1].type in (StreamEventType.DONE, StreamEventType.ERROR):
                        break
            finally:
                if watchdog_task and not watchdog_task.done():
                    watchdog_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await watchdog_task

        if timed_out:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=seq,
                content=f"OpenCode 超时 ({self._timeout}s)，已强制终止。请重试。",
            )
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
                with suppress(TimeoutError, ProcessLookupError):
                    await asyncio.wait_for(self._process.wait(), timeout=2)
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
            with suppress(Exception):
                _sub.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=10,
                )
        else:
            with suppress(Exception):
                os.kill(pid, 9)

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

    @staticmethod
    def _compute_session_key(request: AgentRequest) -> str:
        """会话键：群聊使用 uuid5(session_id:agent_id) 避免跨 agent 污染。"""
        if request.is_group_chat and request.agent_id is not None:
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{request.session_id}:{request.agent_id}"))
        return str(request.session_id)

    @staticmethod
    def _is_progress_message(text: str) -> bool:
        """识别 OpenCode CLI 的进度/状态消息（不应显示给用户）。"""
        text_stripped = text.strip()
        # 已知的 OpenCode 进度消息前缀
        progress_prefixes = (
            "Drafting.",
            "Drafting…",
            "Working on",
            "Working…",
            "Processing.",
            "Processing…",
            "Thinking.",
            "Thinking…",
        )
        for prefix in progress_prefixes:
            if text_stripped.startswith(prefix):
                return True
        # 短纯英文状态消息（≤5 词且不含中文）→ 很可能是进度提示
        words = text_stripped.split()
        return bool(len(words) <= 5 and not any("一" <= c <= "\u9fff" for c in text_stripped))

    @staticmethod
    async def _read_lines(stdout: asyncio.StreamReader, session_id: str) -> AsyncIterator[str]:
        """读取 stdout 行，同时写入 cli_logger。不做超时（超时由 watchdog task 杀进程 → EOF 来保证）。"""
        log_path = get_log_path(session_id)
        with open(log_path, "a", encoding="utf-8") as log_f:
            while True:
                line = await stdout.readline()
                if not line:
                    break
                decoded = line.decode(errors="replace").strip()
                if decoded:
                    log_f.write(decoded + "\n")
                    log_f.flush()
                    yield decoded

    def _parse_line(self, line: str, seq: int) -> list[StreamEvent]:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("OpenCode 非 JSON 行: %s", line[:200])
            return []

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
                if self._is_progress_message(text):
                    # OpenCode 进度/状态消息 → 思考面板，不显示给用户
                    events.append(StreamEvent(type=StreamEventType.THINKING, seq=seq, content=text))
                else:
                    self._text_seen = True
                    events.append(StreamEvent(type=StreamEventType.TEXT, seq=seq, content=text))
        elif event_type == "thinking":
            text = _s("text") or _s("content") or _s("thinking")
            if text:
                events.append(StreamEvent(type=StreamEventType.THINKING, seq=seq, content=text))
        elif event_type in ("tool_call", "tool_use"):
            # opencode v1.15 tool_use 格式：part.tool=工具名，part.callID=调用ID
            call_id = str(
                part.get("callID") or part.get("id") or data.get("call_id") or data.get("id", "")
            )
            tool_name = str(part.get("tool") or part.get("name") or data.get("name", ""))
            tool_args = (
                part.get("state", {}).get("input")
                or part.get("arguments")
                or data.get("arguments")
                or data.get("args")
                or {}
            )
            events.append(
                StreamEvent(
                    type=StreamEventType.TOOL_CALL,
                    seq=seq,
                    tool_call=ToolCall(
                        call_id=call_id,
                        name=tool_name,
                        arguments=tool_args,
                    ),
                )
            )
            seq += 1
            # opencode 内部执行工具，tool_use 已包含结果 → 直接发 ToolResult
            state = part.get("state", {})
            if state.get("status") == "completed":
                output = state.get("output", "")
                content_str = None
                if output:
                    if isinstance(output, str):
                        content_str = output
                    else:
                        content_str = json.dumps(output, ensure_ascii=False)
                events.append(
                    StreamEvent(
                        type=StreamEventType.TOOL_RESULT,
                        seq=seq,
                        tool_result=ToolResult(
                            call_id=call_id,
                            success=True,
                            content=content_str,
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
        elif event_type == "step_start":
            # 新 step 开始：重置 text 标记（用于区分中间 step_finish 和终态）
            # 同时发 THINKING 状态，避免前端空白等待
            self._text_seen = False
            draft_text = part.get("drafting") or part.get("status") or ""
            if not draft_text:
                draft_text = "正在处理…"
            events.append(StreamEvent(type=StreamEventType.THINKING, seq=seq, content=draft_text))
        elif event_type in ("done", "result", "complete", "exit"):
            # 从 data 中提取 usage / cost / duration 等元数据
            usage = data.get("usage") or part.get("usage") or {}
            is_error = data.get("is_error") or part.get("is_error", False)
            if is_error:
                err_msg = (
                    data.get("error")
                    or part.get("error")
                    or data.get("message")
                    or part.get("message")
                    or "OpenCode error"
                )
                events.append(
                    StreamEvent(type=StreamEventType.ERROR, seq=seq, content=str(err_msg))
                )
            else:
                metadata: dict = {
                    "model": self._model,
                }
                if usage:
                    metadata["token_usage"] = usage
                cost = data.get("total_cost_usd") or part.get("total_cost_usd")
                if cost is not None:
                    metadata["total_cost_usd"] = cost
                duration = data.get("duration_ms") or part.get("duration_ms")
                if duration is not None:
                    metadata["duration_ms"] = duration
                errors = data.get("errors") or part.get("errors") or []
                if errors:
                    metadata["errors"] = errors
                events.append(StreamEvent(type=StreamEventType.DONE, seq=seq, metadata=metadata))
        elif event_type == "step_finish":
            # 仅当 step 内产出过 text 时才视为终态；
            # 工具调用后的 step_finish（无 text）是中间态，不结束流
            if self._text_seen:
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
        else:
            text = _s("text") or _s("content")
            if text:
                events.append(StreamEvent(type=StreamEventType.TEXT, seq=seq, content=text))
        return events


def _extract_session_id(line: str) -> str | None:
    m = re.search(r'"sessionID"\s*:\s*"([^"]+)"', line)
    return m.group(1) if m else None


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


def _build_provider_dict(provider: str, api_key: str, model: str = "") -> dict[str, Any]:
    """返回 provider 配置 dict，产出 dict 供自包含临时配置。

    模型使用传入的 model 参数（来自构造函数），不再硬编码。
    非 deepseek provider 使用通用 @ai-sdk/openai-compatible 模板。
    """
    if provider == "deepseek":
        # 使用传入的模型名动态构建配置
        model_id = model or "deepseek/deepseek-v4-pro"
        small_model = "deepseek/deepseek-v4-flash"
        model_short = model_id.split("/", 1)[1] if "/" in model_id else model_id
        return {
            "$schema": "https://opencode.ai/config.json",
            "model": model_id,
            "small_model": small_model,
            "provider": {
                "deepseek": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "DeepSeek",
                    "options": {
                        "baseURL": "https://api.deepseek.com/v1",
                        "apiKey": api_key,
                    },
                    "models": {
                        model_short: {
                            "name": model_short,
                            "limit": {"context": 1000000, "output": 393216},
                            "modalities": {"input": ["text"], "output": ["text"]},
                            "variants": {
                                "think-high": {
                                    "reasoning": True,
                                    "reasoningEffort": "high",
                                    "interleaved": {"field": "reasoning_content"},
                                }
                            },
                        }
                    },
                }
            },
        }
    # 非 deepseek provider：使用通用模板，baseURL 从已知映射获取
    base_url_map: dict[str, str] = {
        "anthropic": "https://api.anthropic.com/v1",
        "openai": "https://api.openai.com/v1",
        "xiaomi": "https://api.x.ai/v1",
        "minimax": "https://api.minimax.chat/v1",
        "siliconflow": "https://api.siliconflow.cn/v1",
    }
    base_url = base_url_map.get(provider, "")
    return {
        "$schema": "https://opencode.ai/config.json",
        "model": model or f"{provider}/default",
        "provider": {
            provider: {
                "npm": "@ai-sdk/openai-compatible",
                "options": {"baseURL": base_url, "apiKey": api_key},
            }
        },
    }


def _write_opencode_config(mcp_section: dict[str, Any]) -> str | None:
    """写临时 opencode MCP 配置，返回路径供 OPENCODE_CONFIG。不注入 provider/model——CLI 读本地配置。"""
    config = {"mcp": mcp_section}
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
