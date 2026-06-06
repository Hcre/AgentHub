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
import atexit
import json
import logging
import os
import re
import tempfile
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


def _resolve_cwd(workspace: str | None) -> str | None:
    """将 workspace 转为可用 cwd。自动检测 Docker/宿主机。"""
    if not workspace:
        return None
    path = workspace.strip()
    if not path:
        return None
    m = re.match(r"^([A-Za-z]):[/\\](.*)", path)
    if m:
        rest = m.group(2).replace("\\", "/")
        # 先试原始路径（宿主机）
        if os.path.exists(path):
            return path
        # 再试 Docker mount 路径
        container = f"/mnt/host_{m.group(1).lower()}/{rest}"
        if os.path.exists(container):
            return container
        logger.warning("workspace 路径不存在: %s", workspace)
        return None
    if os.path.exists(path):
        return path
    return None


# 进程级状态：哪些 session_key 已经至少 spawn 过一次。
# 用于 V1 路径的崩溃恢复 — 重 spawn 时若 key 在此集合中，使用 --resume
# 而不是 --session-id，让 CLI 从磁盘恢复对话历史。
# （V5 已验证 --resume + --input-format stream-json 兼容。）
_SEEN_SESSION_KEYS: set[str] = set()


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

        # V0 短驻：根据 DB 查询结果决定 --resume 还是 --session-id
        # has_history=True → DB 有 assistant 消息 → CLI 磁盘必有记录 → --resume
        # has_history=False → 首次对话 → --session-id 直接新建，省掉空跑
        request = self._merge_delta_into_system_prompt_v0(request)
        prompt = self._extract_prompt(request)
        session_key = self._compute_session_key(request)
        resume = request.has_history
        logger.info(
            "Session %s has_history=%s → %s", session_key, resume, "resume" if resume else "new"
        )
        async for event in self._run_cli(prompt, request, session_key, resume=resume):
            if resume and (
                "No conversation found" in (event.content or "")
                or (
                    event.type == StreamEventType.DONE
                    and "No conversation found" in str(event.metadata)
                )
            ):
                # 极端情况：CLI 磁盘数据丢失（清缓存/迁移环境），fallback 新建
                logger.warning("Session %s resume 失败（磁盘数据丢失），fallback 新建", session_key)
                async for fallback_event in self._run_cli(
                    prompt, request, session_key, resume=False
                ):
                    yield fallback_event
                return
            yield event

    async def stop(self) -> None:
        """终止运行中的 CLI 进程（仅 V0 短驻进程；V1 长驻进程由进程池管理）。"""
        if self._process and self._process.returncode is None:
            self._process.kill()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.terminate()
            self._process = None

    # --- V1 长驻路径 ---

    async def _stream_long_running(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        """长驻模式：复用进程池，stdin 写 JSONL，stdout 流式读取。

        system_prompt 守卫：handle 缓存 spawn 时的 sp 快照，本次请求 sp 不同时
        drop 旧进程重 spawn。ContextBuilder 已把动态 delta 从 sp 中拆出（见
        AgentRequest.group_delta_text），sp 现在跨轮稳定 → 长驻收益完整生效。

        崩溃恢复（Step 2）：mid-stream RuntimeError 时 drop + 用 --resume 重 spawn
        + 重试一次。仅重试一次防止死循环。
        """
        session_key = self._compute_session_key(request)
        sp = request.system_prompt or ""
        # V1：稳定 sp 留 spawn 时用；动态 delta 嵌进 user message 逐轮注入
        prompt = self._build_v1_user_prompt(request)
        pool = get_pool()

        handle = await self._acquire_with_sp_guard(pool, session_key, sp)

        seq = 0
        try:
            async for evt in self._send_and_read(handle, prompt, seq):
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
            # stdout EOF / 子进程意外退出：drop → --resume 重 spawn → 重试一次
            logger.warning(
                "Claude CLI key=%s 流中崩溃 (%s)，尝试 --resume 恢复重试",
                session_key,
                exc,
            )
            await pool.drop(session_key)
            try:
                new_handle = await self._acquire_with_sp_guard(pool, session_key, sp)
                async for evt in self._send_and_read(new_handle, prompt, seq):
                    yield evt
                    seq = evt.seq + 1
            except (TimeoutError, RuntimeError) as exc2:
                await pool.drop(session_key)
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    seq=seq,
                    content=f"Claude CLI 长驻进程崩溃恢复失败: {exc2}",
                )

    async def _acquire_with_sp_guard(self, pool, session_key: str, sp: str) -> ProcessHandle:
        """从池子取 handle，spawn-time sp 不匹配时 drop+重 spawn。"""
        spawn = partial(self._spawn_long, sp, session_key)
        handle = await pool.acquire(session_key, spawn)
        if handle.spawn_system_prompt and handle.spawn_system_prompt != sp:
            logger.info("Claude CLI key=%s system_prompt 变化，drop 重 spawn", session_key)
            await pool.drop(session_key)
            handle = await pool.acquire(session_key, spawn)
        handle.spawn_system_prompt = sp
        return handle

    async def _send_and_read(
        self, handle: ProcessHandle, prompt: str, start_seq: int
    ) -> AsyncIterator[StreamEvent]:
        """串行写 stdin + 读 stdout 到 DONE 的标准段，独立出来便于重试复用。"""
        async with handle.stdin_lock:
            await self._send_user_jsonl(handle, prompt)
            async for evt in self._read_until_done(handle, start_seq):
                yield evt

    async def _spawn_long(self, system_prompt: str, session_key: str) -> asyncio.subprocess.Process:
        """长驻 spawn：--input-format stream-json，stdin 保留。

        首次见 session_key 用 --session-id 新建；后续（崩溃恢复）用 --resume
        让 CLI 从磁盘恢复历史。
        """
        is_resume = session_key in _SEEN_SESSION_KEYS
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
        ]
        if is_resume:
            cmd.extend(["--resume", session_key])
        else:
            cmd.extend(["--session-id", session_key])
        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])
        env = self._build_env()
        logger.info(
            "Claude CLI 长驻 spawn key=%s mode=%s",
            session_key,
            "resume" if is_resume else "new",
        )
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        _SEEN_SESSION_KEYS.add(session_key)
        return proc

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
                raise RuntimeError(f"stdout 关闭 (returncode={handle.proc.returncode})")
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
                content=f"⚠️ 路径不存在或 claude 未安装: {cwd or '当前目录'}",
            )
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
        import shutil

        binary = shutil.which("claude") or "claude"
        cmd = [
            binary,
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
        # MCP 注入：记忆工具（settings.mcp_memory_url）+ P2 绑定的 MCP servers（请求携带）
        # ⚠️ --mcp-config flag 需在实际 CLI 版本中验证（claude --help | grep mcp）
        mcp_path = _write_mcp_config(
            str(request.agent_id) if request.agent_id else "",
            settings.mcp_memory_url,
            request.mcp_servers,
        )
        if mcp_path:
            cmd.extend(["--mcp-config", mcp_path])
        return cmd

    def _build_env(self) -> dict[str, str]:
        """构造 CLI 子进程环境变量。

        不再注入 ANTHROPIC_* 配置：CLI 启动时自己从 ~/.claude/ 读 model/api_key/base_url。
        AgentHub 这边只控制 cwd / system_prompt / skills / MCP 注入（与"配置"无关的部分）。
        """
        env = os.environ.copy()
        return env

    @staticmethod
    def _extract_prompt(request: AgentRequest) -> str:
        """从 messages 提取最后一条 user 消息作为 prompt。"""
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    @staticmethod
    def _merge_delta_into_system_prompt_v0(request: AgentRequest) -> AgentRequest:
        """V0 兼容：把 group_delta_text 拼回 system_prompt（历史行为）。

        ContextBuilder 拆分后，sp 只剩稳定部分。V0 路径需把 delta 拼回避免行为变化。
        """
        if not request.group_delta_text:
            return request
        merged_sp = "\n\n".join(filter(None, [request.system_prompt, request.group_delta_text]))
        return request.model_copy(update={"system_prompt": merged_sp, "group_delta_text": None})

    @staticmethod
    def _build_v1_user_prompt(request: AgentRequest) -> str:
        """V1：把 group_delta_text 嵌进 user message 头部，触发文本附后。

        长驻 CLI 模式下 sp 一次性 spawn 注入；每轮通过 user message 把新群聊 delta
        告知 CLI。私聊（无 delta）退化为原始 trigger 文本。
        """
        trigger = ClaudeCodeRuntime._extract_prompt(request)
        delta = request.group_delta_text
        if not delta:
            return trigger
        return f"{delta}\n\n---\n[本轮触发]\n{trigger}"

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


def _entry_to_claude(entry: dict) -> dict:
    """build_mcp_config_entry 的条目 → Claude mcpServers 值（去掉 name 键）。"""
    return {k: v for k, v in entry.items() if k != "name"}


def _write_mcp_config(
    agent_id: str, mcp_url: str, bound_servers: list[dict] | None = None
) -> str | None:
    """写临时 MCP 配置文件，返回路径。atexit 注册删除，崩溃时也清理。

    合并：记忆工具（agenthub-memory，settings.mcp_memory_url）+ P2 绑定的 MCP servers
    （请求携带 request.mcp_servers）。无任何 server 时返回 None（不传 --mcp-config）。
    """
    # agent_id 通过 query param 传给服务端 ASGI wrapper；
    # env 字段对 SSE 类型的 MCP 服务端无效（仅对 subprocess 类型有效）。
    servers: dict[str, dict] = {}
    if mcp_url and agent_id:
        servers["agenthub-memory"] = {"type": "sse", "url": f"{mcp_url}?agent_id={agent_id}"}
    for entry in bound_servers or []:
        name = entry.get("name")
        if name:
            servers[name] = _entry_to_claude(entry)
    if not servers:
        return None
    config = {"mcpServers": servers}
    try:
        f = tempfile.NamedTemporaryFile(  # noqa: SIM115 — 故意 delete=False 持久化供 CLI 读取，atexit 清理
            mode="w",
            suffix=".json",
            prefix="agenthub_mcp_",
            delete=False,
            dir=tempfile.gettempdir(),
        )
        json.dump(config, f)
        f.close()
        atexit.register(lambda p: os.unlink(p) if os.path.exists(p) else None, f.name)
        return f.name
    except Exception as exc:
        logger.warning("写 MCP 配置失败，跳过 MCP 注入: %s", exc)
        return None
