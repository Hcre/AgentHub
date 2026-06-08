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
from collections.abc import AsyncIterator
from contextlib import suppress
from pathlib import Path

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
        model: str = "",
        agent_id: str = "",
        agent_name: str = "",
        provider: str = "anthropic",
        api_key: str = "",
        base_url: str = "",
        proxy_base: str = "",
        thinking_level: str = _DEFAULT_THINKING_LEVEL,
        timeout: int = _DEFAULT_TIMEOUT,
        session_dir: str = "",
        permission_mode: str = _DEFAULT_PERMISSION_MODE,
        max_turns: int = _DEFAULT_MAX_TURNS,
    ) -> None:
        self._model = model
        self._agent_id = agent_id
        self._agent_name = agent_name
        self._provider = provider
        self._api_key = api_key
        self._base_url = base_url
        self._thinking_level = thinking_level
        self._timeout = timeout
        self._permission_mode = permission_mode
        self._max_turns = max_turns

        self._proxy_url = (
            f"{proxy_base.rstrip('/')}/proxy/agents/{agent_id}" if proxy_base and agent_id else ""
        )

        self._session_dir = session_dir or str(Path.home() / ".agenthub" / "pi-sessions")
        Path(self._session_dir).mkdir(parents=True, exist_ok=True)

        self._process: asyncio.subprocess.Process | None = None

    async def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        # 合并群聊 delta 到 system_prompt（对齐 ClaudeCode V0 行为）
        sp = request.system_prompt
        if request.group_delta_text:
            sp = "\n\n".join(filter(None, [sp, request.group_delta_text]))

        logger.info(
            "Pi Agent request_id=%s session=%s provider=%s model=%s",
            request.request_id,
            request.session_id,
            self._provider,
            self._model,
        )

        prompt = self._extract_prompt(request)
        if not prompt:
            yield StreamEvent(type=StreamEventType.ERROR, seq=0, content="Pi Agent: 无用户消息")
            return

        # 群聊：uuid5(session_id:agent_id) 确定性映射，避免跨 agent 会话污染
        session_key = self._compute_session_key(request)
        session_file = str(Path(self._session_dir) / f"{session_key}.jsonl")

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
        assert self._process.stdin is not None
        assert self._process.stdout is not None

        # 发送 prompt command
        prompt_cmd = json.dumps({"type": "prompt", "message": prompt}) + "\n"
        self._process.stdin.write(prompt_cmd.encode())
        await self._process.stdin.drain()

        # 读取并解析 stdout JSONL
        seq = 0
        try:
            async for line in self._read_lines_with_timeout(self._process.stdout):
                events = self._parse_line(line, seq)
                for evt in events:
                    yield evt
                    seq = evt.seq + 1
                if events and events[-1].type in (StreamEventType.DONE, StreamEventType.ERROR):
                    break
        except TimeoutError:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                seq=seq,
                content=f"Pi Agent 超时 ({self._timeout}s)",
            )
            await self.stop()
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
            self._process = None

    # --- 内部方法 ---

    @staticmethod
    def _pi_binary() -> str:
        """查找 pi CLI 路径，优先用全局安装，fallback 到本地构建。"""
        pi = shutil.which("pi")
        if pi:
            return pi
        # fallback: 检查本地 clone
        local = Path(__file__).parent.parent.parent.parent.parent.parent / "pi-agent" / "pi-test.sh"
        if local.exists():
            return str(local)
        return "pi"  # 最后 fallback

    def _build_cmd(self, session_file: str, request: AgentRequest, sp: str | None = None) -> list[str]:
        cmd = [
            self._pi_binary(),
            "--mode",
            "rpc",
            "--session",
            session_file,
        ]

        pi_provider = _PROVIDER_MAP.get(self._provider, "anthropic")
        cmd.extend(["--provider", pi_provider])

        if self._thinking_level != "off":
            cmd.extend(["--thinking", self._thinking_level])

        # 权限模式（可配置）
        cmd.extend(["--permission-mode", self._permission_mode])
        cmd.extend(["--max-turns", str(self._max_turns)])

        if sp:
            if self._agent_name:
                sp = f"你的名字是{self._agent_name}。\n\n{sp}"
            cmd.extend(["--system-prompt", sp])

        # API key：代理模式下不暴露在命令行（由 _build_env 注入环境变量）
        if self._api_key and not self._proxy_url:
            cmd.extend(["--api-key", self._api_key])

        # NB-02: MCP 注入 seam — blocked on upstream pi CLI MCP support（见 ADR-06 §2.3 / RT-MCP §3）
        # 解除条件：确认 pi CLI 的 MCP config 或 extension 通道存在 → 按 ADR-06 统一原则把
        #   request.mcp_servers 经 _entry_to_pi 翻译 + 逐调用通道注入 + 实测（本机当前无 pi 二进制可验证）。

        return cmd

    def _build_env(self) -> dict[str, str]:
        """构造 CLI 子进程环境变量。

        - 任意模式：注入 model（让 CLI 知道用什么模型）
        - 代理模式（proxy_url 非空）：额外注入 API key / base URL
          把请求重定向到 AgentHub 代理（认证/限流）
        - 全局模式：不覆盖 API key / base URL，CLI 沿用自身配置
        """
        env = os.environ.copy()
        # 注入模型：通过 provider 对应的 env var（如 ANTHROPIC_MODEL、DEEPSEEK_API_KEY 等）
        if self._model:
            env["PI_MODEL"] = self._model
        if self._proxy_url:
            # 代理模式：API key 通过环境变量注入（不在命令行暴露）
            env_key = _PROVIDER_ENV_KEY.get(self._provider, "")
            if env_key:
                env[env_key] = "agenthub-proxy"
            # 注入代理 base URL
            env["PI_BASE_URL"] = self._proxy_url
        elif self._api_key:
            # 非代理模式：如果有 API key，注入环境变量
            env_key = _PROVIDER_ENV_KEY.get(self._provider, "")
            if env_key and env_key not in env:
                env[env_key] = self._api_key
        return env

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
        """解析一行 Pi RPC JSONL 输出，映射为 StreamEvent 列表。

        Pi RPC 事件 → StreamEventType:
        - message_update.text_delta    → TEXT
        - message_update.thinking_delta → THINKING
        - message_update.toolcall_end  → TOOL_CALL
        - message_update.done          → DONE (turn 结束)
        - message_update.error         → ERROR
        - tool_execution_end           → TOOL_RESULT
        - agent_end                    → DONE (流结束)
        - extension_ui_request         → REQUEST_APPROVAL
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

        elif event_type == "tool_execution_start":
            pass  # 不产出事件，等待 tool_execution_end

        elif event_type == "tool_execution_end":
            te = data
            is_error = te.get("isError", False)
            raw = te.get("result")
            if isinstance(raw, dict):
                raw = json.dumps(raw, ensure_ascii=False)
            elif not isinstance(raw, str):
                raw = str(raw) if raw is not None else ""
            events = [
                StreamEvent(
                    type=StreamEventType.TOOL_RESULT,
                    seq=seq,
                    tool_result=ToolResult(
                        call_id=te.get("toolCallId", ""),
                        success=not is_error,
                        content=raw if not is_error else None,
                        error=raw if is_error else None,
                    ),
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
