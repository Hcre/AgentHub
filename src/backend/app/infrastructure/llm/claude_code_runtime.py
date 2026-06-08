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
import signal
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
        logger.info("Session %s has_history=%s → %s", session_key, resume, "resume" if resume else "new")
        resume_gen = self._run_cli(prompt, request, session_key, resume=resume)
        async for event in resume_gen:
            if resume and (
                "No conversation found" in (event.content or "")
                or (
                    event.type == StreamEventType.DONE
                    and "No conversation found" in str(event.metadata)
                )
            ):
                # 极端情况：CLI 磁盘数据丢失（清缓存/迁移环境），fallback 新建。
                # ① 先 kill 失败的 resume 进程 + 关闭被放弃的生成器：否则该进程泄漏、
                #    且占着 session 文件锁，fallback 进程会撞锁僵死（不出输出、不超时前一直卡）。
                # ② fallback 用全新 session-id，不复用刚损坏的那个（复用会再次撞坏 session）。
                logger.warning("Session %s resume 失败（磁盘数据丢失），fallback 新建", session_key)
                await self.stop()  # kill 泄漏的 resume 进程，释放锁
                await resume_gen.aclose()  # 清理被放弃的生成器
                fallback_key = str(uuid.uuid4())
                logger.info("fallback 新 session-id=%s（不复用 %s）", fallback_key, session_key)
                async for fallback_event in self._run_cli(
                    prompt, request, fallback_key, resume=False
                ):
                    yield fallback_event
                return
            yield event

    async def stop(self) -> None:
        """优雅阶梯终止 CLI 进程：SIGINT（Ctrl+C）→ SIGTERM → SIGKILL，每档给宽限。

        先给进程机会优雅收尾（取消在飞 API 流），收不住才升级强杀。
        （旧实现 kill() 先于 terminate()，顺序反了 = 直接 SIGKILL，已修。）
        """
        proc = self._process
        if proc is None or proc.returncode is not None:
            return
        for send, grace in (
            (lambda: proc.send_signal(signal.SIGINT), 2.0),  # Ctrl+C
            (proc.terminate, 2.0),                            # SIGTERM
            (proc.kill, 2.0),                                 # SIGKILL 兜底
        ):
            try:
                send()
            except ProcessLookupError:
                break  # 已退出
            try:
                await asyncio.wait_for(proc.wait(), timeout=grace)
                break  # 收住了
            except TimeoutError:
                continue  # 升级下一档
        else:
            # 三档全失败（Windows 常见），taskkill /F 兜底
            if proc.returncode is None:
                await self._force_kill_subprocess(proc)
        self._process = None

    @staticmethod
    async def _force_kill_subprocess(proc: asyncio.subprocess.Process) -> None:
        """跨平台强制杀子进程。Windows 上 asyncio terminate/kill 可能无效时兜底。"""
        pid = proc.pid
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
            # 隔离用户个人 MCP 配置，避免 CLI 启动等外部 MCP 初始化挂死（见 _build_cmd）
            "--strict-mcp-config",
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
        watchdog_task: asyncio.Task[None] | None = None
        timed_out = False

        async def _watchdog() -> None:
            nonlocal timed_out
            try:
                await asyncio.sleep(self._timeout)
                timed_out = True
                logger.warning(
                    "Claude CLI 超时 (%ss)，强制终止子进程 pid=%s",
                    self._timeout,
                    self._process.pid if self._process else "?",
                )
                await self.stop()
            except asyncio.CancelledError:
                pass

        if self._process and self._process.stdout:
            watchdog_task = asyncio.create_task(_watchdog())
            try:
                async for line in self._read_lines(self._process.stdout):
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
                content=f"Claude CLI 超时 ({self._timeout}s)，已强制终止。请重试。",
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
            # 服务端 headless spawn：隔离用户个人 MCP 配置（~/.claude.json / 项目
            # .mcp.json）。否则 CLI 启动时会拉起用户的 context7/fast-context 等 MCP
            # server 并等其初始化完成才处理 prompt——npx 式按需下载会挂起，整个 CLI
            # 卡在发 API 之前（do_epoll_wait）。strict 模式仅用 --mcp-config 指定的。
            "--strict-mcp-config",
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
        # MCP 工具注入：memory + step-tools（协调者）+ P2 绑定的 MCP servers
        # ⚠️ --mcp-config flag 需在实际 CLI 版本中验证（claude --help | grep mcp）
        mcp_path = _write_mcp_config(
            agent_id=str(request.agent_id) if request.agent_id else "",
            memory_url=settings.mcp_memory_url,
            step_tools_url=settings.mcp_step_tools_url,
            session_id=str(request.session_id) if request.session_id else "",
            group_id=str(request.group_id) if request.group_id else "",
            bound_servers=request.mcp_servers,
        )
        if mcp_path:
            cmd.extend(["--mcp-config", mcp_path])
        return cmd

    def _build_env(self) -> dict[str, str]:
        """构造 CLI 子进程环境变量。

        - 任意模式：若构造时指定了 model，注入 ANTHROPIC_MODEL（让 CLI 知道用什么模型）
        - 代理模式（proxy_url 非空）：额外注入 ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL
          把请求重定向到 AgentHub 自己的代理（代理里能查 agent_id 做认证 / 限流）
        - 全局模式：不覆盖 ANTHROPIC_API_KEY / BASE_URL，CLI 沿用 shell 环境（指向真服务）
        """
        env = os.environ.copy()
        if self._model:
            env["ANTHROPIC_MODEL"] = self._model
        if self._proxy_url:
            env["ANTHROPIC_API_KEY"] = "agenthub-proxy"
            env["ANTHROPIC_BASE_URL"] = self._proxy_url
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

    @staticmethod
    async def _read_lines(stdout: asyncio.StreamReader) -> AsyncIterator[str]:
        """读取 stdout 行，不做超时（超时由 watchdog task 杀进程 → EOF 来保证）。"""
        while True:
            line = await stdout.readline()
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
                elif block_type == "thinking":
                    # 扩展思考的内部推理块：不投递给用户（答案在随后的 text block）。
                    # 预期行为，debug 级即可，不该用 warning 制造"数据丢失"错觉。
                    logger.debug("跳过 thinking block (has_signature=%s)", bool(block.get("signature")))
                else:
                    # 真正未知的 block 类型才告警——可能是新协议字段，需排查。
                    preview = block.get("text") or block
                    logger.warning(
                        "丢弃未知 assistant block type=%s keys=%s 预览=%s",
                        block_type,
                        list(block.keys()),
                        str(preview)[:300],
                    )

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
                    raw_content = block.get("content")
                    # content 可能是 string 或 list[{type,text}] → 统一转 string
                    if isinstance(raw_content, list):
                        raw_content = "\n".join(
                            c.get("text", "") for c in raw_content if isinstance(c, dict) and c.get("type") == "text"
                        )
                    elif not isinstance(raw_content, str):
                        raw_content = str(raw_content) if raw_content is not None else None
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
    agent_id: str,
    memory_url: str = "",
    step_tools_url: str = "",
    session_id: str = "",
    group_id: str = "",
    bound_servers: list[dict] | None = None,
) -> str | None:
    """写临时 MCP 配置文件，返回路径。atexit 注册删除，崩溃时也清理。

    合并三种 MCP server 来源：
    - memory_url     — agenthub-memory server（save_memory tool）
    - step_tools_url — agenthub-step-tools server（task_complete/ask tools，coordinator）
    - bound_servers  — P2 绑定的 MCP servers（请求携带 request.mcp_servers）
    session_id/group_id — 注入 step-tools URL query param，供 ASGI wrapper 映射上下文
    """
    servers: dict[str, dict] = {}
    if memory_url and agent_id:
        servers["agenthub-memory"] = {"type": "sse", "url": f"{memory_url}?agent_id={agent_id}"}
    if step_tools_url and agent_id:
        url = f"{step_tools_url}?agent_id={agent_id}"
        if session_id:
            url += f"&session_id={session_id}"
        if group_id:
            url += f"&group_id={group_id}"
        servers["agenthub-step-tools"] = {
            "type": "sse",
            "url": url,
        }
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
