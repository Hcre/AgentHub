# Agent 记忆系统 — Phase A 实现文档

> 日期：2026-05-30 | 状态：**实现文档**
> 前置阅读：`memory-system-design-v1.md`（设计方案）
> 范围：Phase A（立即可做，无需 Phase 1 长驻）

---

## 一、实现概览

Phase A 的目标：让每个 Agent 拥有**独立的文件系统身份**（CLAUDE.md + context/）和 **CLI 原生记忆能力**（memory/），同时将 System Prompt 构建逻辑从 `ContextBuilder` 中分离为独立的 `SystemPromptBuilder`。

### 1.1 变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **新增** | `src/backend/app/application/services/system_prompt_builder.py` | SP 构建器（~150 行） |
| **新增** | `src/backend/app/application/services/agent_file_manager.py` | Agent CWD 文件管理（~200 行） |
| **新增** | `src/backend/app/domain/value_objects/group_context.py` | 群聊上下文值对象（~40 行） |
| **修改** | `src/backend/app/infrastructure/llm/claude_code_runtime.py` | `_run_cli`/`_spawn_long` 加 `cwd=`，`_acquire_with_sp_guard` 接受外部 spawn |
| **修改** | `src/backend/app/application/services/context_builder.py` | 群聊路径集成 AgentFileManager |
| **修改** | `src/backend/app/core/config.py` | 新增 `agent_cwd_base` 配置项 |
| **修改** | `src/backend/app/api/deps.py` | 注册新服务 |
| **新增** | `tests/unit/test_system_prompt_builder.py` | SP Builder 单测 |
| **新增** | `tests/unit/test_agent_file_manager.py` | 文件管理单测 |
| **新增** | `tests/integration/test_memory_flow.py` | 端到端记忆流集成测试 |

### 1.2 不改动的部分

- `MemoryContext` 四层模型 — 保留，l2/l3/l4 继续预留
- `ProcessPool` — 已有 `spawn_system_prompt` 比较 + drop 机制，直接复用
- `prompt_templates.py` — GROUP_CHAT_CONTRACT 不变
- 私聊路径 — 不影响。继续在 AgentRequest 中设置 `memory=MemoryContext(l1_working=window)`。群聊路径不设 `memory=`（上下文已通过 CLAUDE.md + SP 注入）

---

## 二、新增组件实现

### 2.1 GroupContext 值对象

**文件**：`src/backend/app/domain/value_objects/group_context.py`

```python
"""群聊上下文值对象 — 携带群共享状态的快照。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class GroupContext:
    """群聊上下文快照，由 ContextBuilder 从 PG/Redis 构建。

    包含两层信息：
    - summary（一行摘要）→ 写入 CLAUDE.md 索引，~300 tokens 内
    - detail（完整内容）→ 写入 context/*.md 详情文件，Agent 按需 Read
    """

    # --- 摘要（写入 CLAUDE.md 索引行） ---
    members_summary: str       # e.g. "3人: 后端专家/前端专家/测试专家"
    task_board_summary: str    # e.g. "进行中: 实现登录API (后端专家)"
    decisions_summary: str     # e.g. "最新: JWT过期7天 (2026-05-30)"

    # --- 详情（写入 context/*.md） ---
    members_detail: str        # Markdown 表格
    task_board_detail: str     # Markdown 任务列表
    decisions_detail: str      # Markdown 决策日志

    def context_hash(self) -> str:
        """上下文版本 hash。hash 变化 → SP hash 变化 → 触发重 spawn。

        只用摘要计算：摘要变了说明上下文实质变化，详情可能是格式调整。
        """
        payload = f"{self.members_summary}|{self.task_board_summary}|{self.decisions_summary}"
        return hashlib.sha256(payload.encode()).hexdigest()[:12]
```

### 2.2 SystemPromptBuilder

**文件**：`src/backend/app/application/services/system_prompt_builder.py`

```python
"""构建 --system-prompt 内容（Layer 2）。

Layer 1（CLAUDE.md / MEMORY.md / rules）由 CLI 免费提供。
Layer 3（hooks / MCP / deferred tools）由 Harness 动态注入。
本模块只负责 Layer 2：Agent 身份 + Memory 指令 + 行为约束 + 上下文版本 hash。
"""

from __future__ import annotations

from pathlib import Path

from app.domain.entities.agent import Agent


class SystemPromptBuilder:
    """构建 ``--system-prompt`` 内容。

    SP 包含上下文版本 hash。hash 变化时 ProcessPool 自动
    drop 旧进程 → ``--resume`` 起新进程（实验 8 验证通过）。
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        agent: Agent,
        *,
        ctx_hash: str = "",
        delivery_contract: str = "",
    ) -> str:
        """构建完整 SP。

        Parameters
        ----------
        agent : Agent
            目标 Agent 实体（含 system_prompt / capability_tags）。
        ctx_hash : str
            上下文版本 hash。变化时触发重 spawn。
        delivery_contract : str
            行为约束文本（GROUP_CHAT_CONTRACT 等）。
        """
        parts: list[str] = []

        # 1) Agent 身份（PG agents.system_prompt）
        if agent.system_prompt:
            parts.append(agent.system_prompt)

        # 2) Memory 指令段（~300 tokens）
        cwd = self._agent_cwd(agent)
        parts.append(self._memory_instructions(cwd))

        # 3) 行为约束
        if delivery_contract:
            parts.append(delivery_contract)

        # 4) 上下文版本 hash
        if ctx_hash:
            parts.append(f"# Context\nctx_hash: {ctx_hash}")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _agent_cwd(agent: Agent) -> Path:
        """Agent CWD 路径。与 AgentFileManager 保持一致。"""
        from app.core.config import get_settings

        return Path(get_settings().agent_cwd_base) / str(agent.id)

    @staticmethod
    def _cwd_to_cli_memory_path(cwd: Path) -> str:
        """CWD → CLI 实际的 memory 路径。

        CLI 规则：``~/.claude/projects/-{cwd 中 / 替换为 -}/memory/``
        例：``/data/agenthub/agents/a1`` → ``~/.claude/projects/-data-agenthub-agents-a1/memory/``
        """
        encoded = str(cwd).replace("/", "-")
        return f"~/.claude/projects/{encoded}/memory/"

    def _memory_instructions(self, cwd: Path) -> str:
        """生成 ~300 tokens 的 Memory 指令段。

        精简版：3 种 type（knowledge / feedback / reflection），
        4 条保存规则，替代 CLI 原生的 ~2000 tokens 版本。
        """
        mem_path = self._cwd_to_cli_memory_path(cwd)
        return f"""# Memory
You have a persistent file-based memory at `{mem_path}`.
Write to it directly with the Write tool.
Maintain MEMORY.md as a one-line-per-entry index. Keep entries under 150 chars.

Each memory file uses frontmatter:
---
name: {{{{name}}}}
description: {{{{one-line description}}}}
type: {{{{knowledge | feedback | reflection}}}}
---
{{{{content}}}}

When to save:
- Task conclusions and key decisions
- Learnings from failures
- User preferences and corrections
- Group decisions that affect future work

Do NOT save: ephemeral task details, code patterns in source, git history."""
```

### 2.3 AgentFileManager

**文件**：`src/backend/app/application/services/agent_file_manager.py`

```python
"""管理 Agent CWD 下的 CLAUDE.md（索引）+ context/（详情）。

职责边界：
- 本模块管理 CLAUDE.md + context/ → CLI Layer 1 自动注入
- memory/ 由 CLI 自管，本模块不创建也不读取
- SP（Layer 2）由 SystemPromptBuilder 构建
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import get_settings
from app.domain.entities.agent import Agent
from app.domain.value_objects.group_context import GroupContext

logger = logging.getLogger(__name__)


class AgentFileManager:
    """管理 Agent CWD 文件系统。

    注意：所有文件 I/O 操作是同步的。Phase A 目标路径为本地磁盘
    （/data/agenthub/），不阻塞事件循环。未来若迁移到网络存储（NFS/S3），
    需改用 aiofiles 异步 I/O。
    """

    def __init__(self, base_dir: str | None = None) -> None:
        self._base = Path(base_dir or get_settings().agent_cwd_base)
        self._last_ctx_hash: dict[str, str] = {}  # str(agent.id) → 上次 hash，跳过重复写入

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def agent_cwd(self, agent: Agent) -> Path:
        """返回 Agent CWD 路径。"""
        return self._base / str(agent.id)

    def ensure_agent_cwd(self, agent: Agent) -> Path:
        """创建 Agent CWD + 渲染初始文件。Agent 创建时调用一次。

        创建：
        - {cwd}/CLAUDE.md       — 索引文件
        - {cwd}/context/        — 详情目录
        - {cwd}/context/tech-stack.md
        - {cwd}/context/conventions.md

        不创建：
        - {cwd}/memory/         — CLI 首次写记忆时自动创建
        """
        cwd = self.agent_cwd(agent)
        cwd.mkdir(parents=True, exist_ok=True)
        (cwd / "context").mkdir(exist_ok=True)

        # 渲染静态详情文件
        self._render_static_context(agent, cwd)

        # 渲染初始索引（无群聊上下文）
        self._render_claude_md(agent, cwd, group_ctx=None)

        logger.info("Agent CWD created: %s", cwd)
        return cwd

    def update_group_context(
        self,
        agent: Agent,
        group_ctx: GroupContext,
    ) -> str:
        """上下文变更时调用。更新动态详情文件 + CLAUDE.md 索引。

        Returns
        -------
        str
            当前上下文版本 hash（始终返回，无论是否有变更）。
            调用方将 hash 嵌入 SP，ProcessPool 通过 SP 比较决定是否重 spawn。

        注意：始终返回 hash（而非 None）是关键设计决策。如果无变更时返回 None，
        调用方会用空字符串构建 SP（缺少 ctx_hash 段），导致 SP 与上一轮不同，
        触发不必要的重 spawn。始终返回 hash 确保 SP 在无变更时 bit-for-bit 一致。
        """
        cwd = self.agent_cwd(agent)
        agent_key = str(agent.id)
        new_hash = group_ctx.context_hash()

        # 跳过文件写入：hash 与上次相同 → 内容无实质变化
        if self._last_ctx_hash.get(agent_key) == new_hash:
            return new_hash  # 返回缓存 hash，不写文件

        ctx_dir = cwd / "context"
        ctx_dir.mkdir(parents=True, exist_ok=True)

        # 更新详情文件（全量覆写）
        (ctx_dir / "members.md").write_text(
            group_ctx.members_detail, encoding="utf-8",
        )
        (ctx_dir / "task-board.md").write_text(
            group_ctx.task_board_detail, encoding="utf-8",
        )
        (ctx_dir / "decisions.md").write_text(
            group_ctx.decisions_detail, encoding="utf-8",
        )

        # 更新索引
        self._render_claude_md(agent, cwd, group_ctx)

        self._last_ctx_hash[agent_key] = new_hash
        logger.debug(
            "Agent %s context updated, hash=%s", agent.id, new_hash,
        )
        return new_hash

    def cleanup_agent_cwd(self, agent: Agent) -> None:
        """删除 Agent CWD。Agent 删除时调用。

        注意：不删除 CLI memory 路径（~/.claude/projects/-data-agenthub-agents-{id}/memory/），
        那是用户级目录，由 CLI 管理。但为避免永久孤儿文件，至少 log 路径供运维清理。
        """
        import shutil

        from app.application.services.system_prompt_builder import SystemPromptBuilder

        cwd = self.agent_cwd(agent)
        if cwd.exists():
            shutil.rmtree(cwd)
            logger.info("Agent CWD removed: %s", cwd)

        # 提示清理 CLI memory 路径
        cli_mem = SystemPromptBuilder._cwd_to_cli_memory_path(cwd)
        logger.info(
            "Agent %s 的 CLI memory 路径未被删除（需手动清理）: %s",
            agent.id, cli_mem,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _render_static_context(self, agent: Agent, cwd: Path) -> None:
        """渲染静态详情文件（Agent 创建/角色变更时）。

        内容从 capability_tags + role 推导。Phase A 为模板占位，
        后续可由用户编辑。
        """
        ctx_dir = cwd / "context"

        # 技术栈（从 capability_tags 推导）
        tags = agent.capability_tags or []
        tag_lines = "\n".join(f"- {t}" for t in tags) if tags else "- 通用"
        (ctx_dir / "tech-stack.md").write_text(
            f"# 技术栈\n\n{tag_lines}\n",
            encoding="utf-8",
        )

        # 代码规范（从 Agent 角色推导）
        role = agent.role or "通用开发"
        (ctx_dir / "conventions.md").write_text(
            f"# 代码规范\n\n"
            f"角色：{role}\n\n"
            f"遵循项目 CLAUDE.md 中定义的规范。\n"
            f"具体规范由 Agent 在首次任务中根据角色推导并补充。\n",
            encoding="utf-8",
        )

    def _render_claude_md(
        self,
        agent: Agent,
        cwd: Path,
        group_ctx: GroupContext | None,
    ) -> None:
        """渲染 CLAUDE.md 索引（~300 tokens）。

        索引规则：
        - 每条一行：[文件名](路径) — 一句话摘要（≤100 字符）
        - 总行数 ≤20 行，总 token ≤300
        - 不放身份/角色（在 SP 中），不放 delta_text（在用户消息中）
        """
        tags_summary = ", ".join(agent.capability_tags[:5]) if agent.capability_tags else "通用"

        lines = [
            "# Agent 上下文",
            "",
            "## 领域知识",
            f"- [技术栈](context/tech-stack.md) — {tags_summary}",
            f"- [代码规范](context/conventions.md) — {agent.role or '通用开发'}",
        ]

        if group_ctx:
            lines += [
                "",
                "## 群聊上下文",
                f"- [群成员](context/members.md) — {group_ctx.members_summary}",
                f"- [任务看板](context/task-board.md) — {group_ctx.task_board_summary}",
                f"- [最近决策](context/decisions.md) — {group_ctx.decisions_summary}",
            ]

        lines += ["", "需要详情时用 Read 工具查看对应文件。"]

        (cwd / "CLAUDE.md").write_text("\n".join(lines), encoding="utf-8")
```

### 2.4 GroupContext 构建器

在 `ContextBuilder` 中新增方法，从 PG/Redis 数据构建 `GroupContext`。

```python
# context_builder.py 新增方法

async def _build_group_context(
    self,
    group: Group,
    members: list[Agent],
    current_agent: Agent,
) -> GroupContext:
    """从 PG 数据构建群聊上下文值对象。

    members 来自 _load_members()（不含 coordinator）。
    """
    from app.domain.value_objects.group_context import GroupContext

    # --- 成员信息 ---
    members_summary = f"{len(members)}人: " + "/".join(a.name for a in members)

    members_rows = []
    for a in members:
        tag = "（你）" if a.id == current_agent.id else ""
        members_rows.append(
            f"| {a.name}{tag} | {a.role} | {', '.join(a.capability_tags[:3])} |"
        )
    members_detail = (
        "# 群成员\n\n"
        "| Agent | 角色 | 技术栈 |\n"
        "|-------|------|--------|\n"
        + "\n".join(members_rows)
    )

    # --- 任务看板（当前简化：从最近消息推导，Phase B 接 TaskFSM） ---
    task_board_summary = "暂无进行中任务"
    task_board_detail = "# 任务看板\n\n暂无进行中任务。\n"

    # --- 决策日志（当前简化：空，Phase B 接 on_group_decision Hook） ---
    decisions_summary = "暂无决策记录"
    decisions_detail = "# 群决策日志\n\n暂无决策记录。\n"

    return GroupContext(
        members_summary=members_summary,
        task_board_summary=task_board_summary,
        decisions_summary=decisions_summary,
        members_detail=members_detail,
        task_board_detail=task_board_detail,
        decisions_detail=decisions_detail,
    )
```

---

## 三、现有代码修改

### 3.1 配置项新增

**文件**：`src/backend/app/core/config.py`

```python
# 在 Settings 类中新增：
agent_cwd_base: str = "/data/agenthub/agents"  # Agent CWD 根目录（持久化卷）
```

> 注意：使用 `/data/` 而非 `/tmp/`，解决设计文档 Q4（容器重启后 `/tmp` 清空）。
> Docker 部署时挂载 persistent volume 到 `/data/agenthub/`。

### 3.2 ContextBuilder 集成

**文件**：`src/backend/app/application/services/context_builder.py`

改动点：在 `_build_group` 方法中，**替换**原有 SP 拼接逻辑（persona + GROUP_CHAT_CONTRACT + members_block），改用 `SystemPromptBuilder` + `AgentFileManager`。

```python
# context_builder.py

class ContextBuilder:
    def __init__(
        self,
        message_repo: MessageRepository,
        agent_repo: AgentRepository,
        l1_memory: L1MemoryStore,
        watermarks: WatermarkStore,
        agent_file_mgr: AgentFileManager | None = None,   # 新增
        sp_builder: SystemPromptBuilder | None = None,     # 新增
    ) -> None:
        self._messages = message_repo
        self._agents = agent_repo       # 注意：复数，与现有代码一致
        self._l1 = l1_memory
        self._wm = watermarks
        self._file_mgr = agent_file_mgr or AgentFileManager()
        self._sp_builder = sp_builder or SystemPromptBuilder()

    async def _build_group(
        self,
        session: Session,
        group: Group,
        target_agent: Agent,
        trigger: Message,
    ) -> AgentRequest:
        # 1. delta 计算（不变）
        delta = await self._compute_delta(...)

        # 2. 渲染群聊上下文 + 更新 Agent CWD 文件
        # 复用现有 _load_members（逐个 get_by_id），不引入新 repo 方法
        members = await self._load_members(group)
        group_ctx = await self._build_group_context(
            group, members, target_agent,
        )
        ctx_hash = self._file_mgr.update_group_context(target_agent, group_ctx)
        # ctx_hash 始终返回当前 hash（有变更返回新值，无变更返回缓存值）
        # 确保 SP 在无变更时 bit-for-bit 一致，不触发不必要的重 spawn

        # 3. 构建 SP（替代原有 persona + GROUP_CHAT_CONTRACT + members_block 拼接）
        # === 删除的旧逻辑 ===
        # persona = target_agent.system_prompt or (...)
        # system_prompt = "\n\n".join(filter(None, [persona, GROUP_CHAT_CONTRACT, members_block]))
        # === 新逻辑 ===
        system_prompt = self._sp_builder.build(
            target_agent,
            ctx_hash=ctx_hash,
            delivery_contract=self._build_contract(members, target_agent),
        )

        # 4. 渲染 delta（不变）
        delta_text = ...

        # 5. 装配 AgentRequest（群聊路径不设 memory=）
        return AgentRequest(
            request_id=str(uuid4()),
            session_id=session.id,
            messages=[{"role": "user", "content": trigger.content}],
            system_prompt=system_prompt,
            agent_id=target_agent.id,
            group_id=group.id,
            is_group_chat=True,
            group_delta_text=delta_text,
            # 群聊路径不设 memory= — Layer 1 已通过 CLAUDE.md 注入
        )

    def _build_contract(
        self,
        agents: list[Agent],
        current_agent: Agent,
    ) -> str:
        """构建行为约束文本（成员列表 + GROUP_CHAT_CONTRACT）。"""
        from app.application.services.prompt_templates import (
            GROUP_CHAT_CONTRACT,
            format_members,
        )

        members_block = format_members(agents, current_agent)
        return f"{GROUP_CHAT_CONTRACT}\n\n{members_block}"
```

### 3.3 ClaudeCodeRuntime 改动

**文件**：`src/backend/app/infrastructure/llm/claude_code_runtime.py`

改动点：`_build_cmd()` **不修改 cmd 列表**。CWD 通过 `create_subprocess_exec(cwd=...)` 在进程启动时设置。

> **注意**：Claude CLI 没有 `--cwd` 参数。CWD 是 OS 级进程属性，必须通过 `create_subprocess_exec(cwd=agent_cwd)` 设置。见 §3.3b。

**`_run_cli()` 签名加 `cwd`，`create_subprocess_exec` 传 `cwd=`**：

```python
async def _run_cli(self, prompt, request, session_key, *, resume, cwd=None):
    cmd = self._build_cmd(request, session_key, resume=resume)
    env = self._build_env()
    self._process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=cwd,  # ← Agent CWD（None 时继承父进程 CWD）
    )
    # ... 后续 stdin.write + stdout 读取不变 ...
```

**V0 调用方（`stream()` 方法）也要传 cwd**：

```python
async def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
    # ... V1 分流不变 ...

    # V0 短驻路径
    request = self._merge_delta_into_system_prompt_v0(request)
    prompt = self._extract_prompt(request)
    session_key = self._compute_session_key(request)
    cwd = self._resolve_agent_cwd(request)  # ← 新增

    async for event in self._run_cli(prompt, request, session_key, resume=True, cwd=cwd):
        if "No conversation found" in (event.content or "") or (...):
            # fallback 也传 cwd
            async for fallback_event in self._run_cli(
                prompt, request, session_key, resume=False, cwd=cwd,
            ):
                yield fallback_event
            return
        yield event
```

`_spawn_long()` 同样加 `cwd` 参数，见 §3.3b。

### 3.3b `_spawn_long()` 改动

**文件**：`src/backend/app/infrastructure/llm/claude_code_runtime.py`

`_spawn_long()` 签名加 `cwd`，`create_subprocess_exec` 传 `cwd=`：

```python
async def _spawn_long(
    self, system_prompt: str, session_key: str, cwd: str | None = None,
) -> asyncio.subprocess.Process:
    # ... 现有 cmd 构建不变 ...
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=cwd,  # ← Agent CWD（None 时继承父进程 CWD）
    )
    _SEEN_SESSION_KEYS.add(session_key)
    return proc
```

`_acquire_with_sp_guard` 签名变更：接受外部传入的 `spawn` 闭包（不再内部创建），因为 spawn 现在需要捕获 `cwd`：

```python
async def _acquire_with_sp_guard(
    self, pool, session_key: str, sp: str, spawn: SpawnFn,
) -> ProcessHandle:
    """从池子取 handle，spawn-time sp 不匹配时 drop+重 spawn。

    变更：spawn 参数由调用方传入（原先内部 partial 创建），
    因为 _spawn_long 现在需要 cwd 参数，调用方包一层 partial 传入。
    """
    handle = await pool.acquire(session_key, spawn)
    if handle.spawn_system_prompt and handle.spawn_system_prompt != sp:
        logger.info(
            "Claude CLI key=%s system_prompt 变化，drop 重 spawn", session_key
        )
        await pool.drop(session_key)
        handle = await pool.acquire(session_key, spawn)
    handle.spawn_system_prompt = sp
    return handle
```

`_stream_long_running` 改动：构建含 cwd 的 spawn 闭包，传给 `_acquire_with_sp_guard`。崩溃恢复路径同样使用同一个 spawn 闭包：

```python
async def _stream_long_running(self, request):
    session_key = self._compute_session_key(request)
    sp = request.system_prompt or ""
    prompt = self._build_v1_user_prompt(request)
    pool = get_pool()
    agent_cwd = self._resolve_agent_cwd(request)

    # spawn 闭包捕获 cwd — _acquire_with_sp_guard 不再内部创建
    spawn = partial(self._spawn_long, sp, session_key, agent_cwd)
    handle = await self._acquire_with_sp_guard(pool, session_key, sp, spawn)

    seq = 0
    try:
        async for evt in self._send_and_read(handle, prompt, seq):
            yield evt
            seq = evt.seq + 1
    except TimeoutError:
        await pool.drop(session_key)
        yield StreamEvent(type=StreamEventType.ERROR, seq=seq, ...)
    except RuntimeError as exc:
        # 崩溃恢复：drop → 用同一个 spawn 闭包（含 cwd）重 spawn
        logger.warning("Claude CLI key=%s 流中崩溃 (%s)，尝试恢复", session_key, exc)
        await pool.drop(session_key)
        try:
            new_handle = await self._acquire_with_sp_guard(pool, session_key, sp, spawn)
            async for evt in self._send_and_read(new_handle, prompt, seq):
                yield evt
                seq = evt.seq + 1
        except (TimeoutError, RuntimeError) as exc2:
            await pool.drop(session_key)
            yield StreamEvent(type=StreamEventType.ERROR, seq=seq, ...)
```

`_resolve_agent_cwd` 辅助方法：

```python
def _resolve_agent_cwd(self, request: AgentRequest) -> str | None:
    """从 AgentRequest 解析 Agent CWD 路径。

    返回 str（路径存在时）或 None（私聊/无 Agent/路径不存在时）。
    None 传给 create_subprocess_exec(cwd=None) 表示继承父进程 CWD。
    注意：不能返回空字符串 ""，否则 subprocess 会抛 OSError。
    """
    if request.agent_id:
        from app.core.config import get_settings
        cwd = Path(get_settings().agent_cwd_base) / str(request.agent_id)
        if cwd.exists():
            return str(cwd)
    return None
```

### 3.4 依赖注入

**文件**：`src/backend/app/api/deps.py`

```python
from app.application.services.agent_file_manager import AgentFileManager
from app.application.services.system_prompt_builder import SystemPromptBuilder

# Process-level singletons
@lru_cache
def get_agent_file_manager() -> AgentFileManager:
    return AgentFileManager()

@lru_cache
def get_sp_builder() -> SystemPromptBuilder:
    return SystemPromptBuilder()

# 修改 ContextBuilder 注入
def get_context_builder(...) -> ContextBuilder:
    return ContextBuilder(
        msg_repo=msg_repo,
        agent_repo=agent_repo,
        l1=l1,
        watermark=wm,
        agent_file_mgr=get_agent_file_manager(),   # 新增
        sp_builder=get_sp_builder(),                 # 新增
    )
```

### 3.5 Agent 创建流程集成

**文件**：`src/backend/app/application/services/agent_service.py`

在 Agent 创建/删除时调用 `AgentFileManager`：

```python
class AgentService:
    def __init__(self, ..., file_mgr: AgentFileManager) -> None:
        self._file_mgr = file_mgr

    async def create_agent(self, cmd: CreateAgentCommand) -> Agent:
        agent = await self._repo.create(...)

        # 创建 Agent CWD（只在 CLAUDE_CODE 类型时）
        if agent.agent_system == AgentSystem.CLAUDE_CODE:
            self._file_mgr.ensure_agent_cwd(agent)

        return agent

    async def delete_agent(self, agent_id: UUID) -> None:
        agent = await self._repo.get(agent_id)

        # 清理 Agent CWD
        if agent.agent_system == AgentSystem.CLAUDE_CODE:
            self._file_mgr.cleanup_agent_cwd(agent)

        await self._repo.delete(agent_id)
```

---

## 四、数据流验证

### 4.1 Agent 创建时

```
POST /agents {name, role, system_prompt, capability_tags, agent_system: CLAUDE_CODE}
  │
  ▼
AgentService.create_agent()
  ├─ PG: INSERT INTO agents
  └─ AgentFileManager.ensure_agent_cwd(agent):
       ├─ mkdir /data/agenthub/agents/{agent_id}/
       ├─ mkdir /data/agenthub/agents/{agent_id}/context/
       ├─ write context/tech-stack.md
       ├─ write context/conventions.md
       └─ write CLAUDE.md（索引，无群聊段）
```

### 4.2 群聊消息发送时

```
User → WS → ChatService.send_and_stream()
  │
  ▼
ContextBuilder.build_for_agent(target_agent=AgentA)
  │
  ├─ _build_group_context() → GroupContext 值对象
  │
  ├─ AgentFileManager.update_group_context(AgentA, group_ctx)
  │     ├─ write context/members.md
  │     ├─ write context/task-board.md
  │     ├─ write context/decisions.md
  │     ├─ write CLAUDE.md（含群聊段摘要）
  │     └─ return ctx_hash = "a1b2c3d4e5f6"
  │
  ├─ SystemPromptBuilder.build(AgentA, ctx_hash="a1b2c3d4e5f6")
  │     → "# Agent 身份\n...\n# Memory\n...\n# Context\nctx_hash: a1b2c3d4e5f6"
  │
  └─ AgentRequest(system_prompt=..., group_delta_text=...)
       │
       ▼
  ClaudeCodeRuntime._build_cmd() or _spawn_long()
    ├─ --system-prompt <sp>
    ├─ cwd=/data/agenthub/agents/{agent_id}     ← CLI 从该目录读取 CLAUDE.md
    └─ CLI 启动:
         Layer 1: CLAUDE.md（索引） + MEMORY.md（记忆）← CLI 自动注入
         Layer 2: --system-prompt（身份+Memory指令+约束+hash）
         Layer 3: Harness 动态注入
```

### 4.3 上下文变更触发重 spawn（V1 长驻模式）

```
群成员变更 / 任务状态更新 / 新决策
  │
  ▼
ContextBuilder._build_group()
  → AgentFileManager.update_group_context() → ctx_hash 变化（新 hash）
  → SystemPromptBuilder.build(ctx_hash="new_hash")
  → AgentRequest.system_prompt 变化
       │
       ▼
ClaudeCodeRuntime._stream_long_running()
  → spawn = partial(_spawn_long, sp, session_key, agent_cwd)
  → _acquire_with_sp_guard(pool, session_key, sp, spawn)
       └─ handle.spawn_system_prompt != sp（SP 含新 ctx_hash）
            → pool.drop(session_key)     # kill 旧进程
            → pool.acquire(spawn)        # --resume 起新进程（cwd 在 spawn 闭包中）
            → CLI 重新读取:
                 CLAUDE.md（新摘要）
                 MEMORY.md（含新记忆）
                 对话历史恢复
            → 代价 ~1-2s，仅上下文变化时触发

无变更时：update_group_context 返回缓存 hash → SP bit-for-bit 一致 → 不触发重 spawn
```

### 4.4 Agent 写记忆（CLI 自驱动，AgentHub 不参与）

```
Agent 推理 → "这个决策值得记住"
  │
  ▼
Agent 调用 Write 工具:
  → ~/.claude/projects/-data-agenthub-agents-{agent_id}/memory/jwt_decision.md
  → 更新 MEMORY.md 索引
  │
  ▼
同 session 内: Agent 可通过 Read 读取文件
下次 spawn/resume: CLI 自动注入 MEMORY.md 到 <system-reminder>
```

---

## 五、SP 变更检测机制（已有，无需改动 ProcessPool）

SP 变更检测由 `ClaudeCodeRuntime._acquire_with_sp_guard()` 负责（runtime L175-188），**不在 ProcessPool 中**。机制如下：

1. `_acquire_with_sp_guard` 从 pool 取 handle
2. 比较 `handle.spawn_system_prompt`（上次 spawn 时的 SP 快照）与本次 SP
3. 不一致 → `pool.drop()` 终止旧进程 → `pool.acquire()` 用 spawn 闭包创建新进程
4. 更新 `handle.spawn_system_prompt = sp`

`ProcessPool.acquire()` 本身只检查 handle 存活性和做 LRU 淘汰，不涉及 SP 比较（见 `claude_code_process_pool.py` L70-129）。

**Phase A 改动对此机制的影响**：
- ctx_hash 嵌入 SP → 上下文变化 → SP 字符串变化 → `_acquire_with_sp_guard` 检测到 → drop + re-spawn
- `_acquire_with_sp_guard` 签名变更（§3.3b）：接受外部 spawn 闭包（含 cwd），替代内部创建
- **ProcessPool 代码不需要任何修改**

---

## 六、Docker 部署配置

### 6.1 持久化卷

```yaml
# src/docker/docker-compose.yml 新增

services:
  backend:
    volumes:
      - agent_data:/data/agenthub    # Agent CWD 持久化

volumes:
  agent_data:
    driver: local
```

### 6.2 环境变量

```bash
# .env
AGENT_CWD_BASE=/data/agenthub/agents
```

---

## 七、测试计划

### 7.1 单元测试

**`tests/unit/test_system_prompt_builder.py`**：

| 用例 | 验证点 |
|------|--------|
| `test_build_with_all_fields` | SP 包含身份 + Memory + 约束 + hash |
| `test_build_minimal` | 无 system_prompt 的 Agent → 只有 Memory 段 |
| `test_memory_path_encoding` | `/data/agenthub/agents/a1` → `~/.claude/projects/-data-agenthub-agents-a1/memory/` |
| `test_ctx_hash_in_sp` | ctx_hash 出现在 SP 末尾 |
| `test_no_ctx_hash_when_empty` | 空 hash 时 SP 无 `# Context` 段 |

**`tests/unit/test_agent_file_manager.py`**：

| 用例 | 验证点 |
|------|--------|
| `test_ensure_agent_cwd` | 目录结构正确 + CLAUDE.md + context/*.md 存在 |
| `test_update_group_context` | 详情文件内容更新 + CLAUDE.md 索引摘要更新 |
| `test_claude_md_token_budget` | CLAUDE.md ≤300 tokens（用 tiktoken 验证） |
| `test_cleanup_agent_cwd` | 目录完全删除 |
| `test_idempotent_ensure` | 重复调用不报错，文件内容最新 |

**`tests/unit/test_group_context.py`**：

| 用例 | 验证点 |
|------|--------|
| `test_context_hash_deterministic` | 相同输入 → 相同 hash |
| `test_context_hash_changes` | 成员变更 → hash 变化 |
| `test_frozen_dataclass` | 不可变 |

### 7.2 集成测试

**`tests/integration/test_memory_flow.py`**：

| 用例 | 验证点 |
|------|--------|
| `test_agent_creation_creates_cwd` | Agent 创建 → CWD 存在 + 文件正确 |
| `test_group_message_updates_context` | 群聊消息 → context/*.md 更新 |
| `test_sp_contains_ctx_hash` | AgentRequest.system_prompt 含 ctx_hash |
| `test_context_change_triggers_different_hash` | 成员变更 → hash 变化 → SP 变化 |
| `test_agent_deletion_cleans_cwd` | Agent 删除 → CWD 不存在 |

---

## 八、实施步骤

按依赖顺序，每步可独立验证：

### Step 1：值对象 + 配置（无外部依赖）

1. 创建 `domain/value_objects/group_context.py`
2. `config.py` 新增 `agent_cwd_base`
3. 写单测 `test_group_context.py`
4. **验证**：`pytest tests/unit/test_group_context.py`

### Step 2：SystemPromptBuilder（依赖 Step 1）

1. 创建 `application/services/system_prompt_builder.py`
2. 写单测 `test_system_prompt_builder.py`
3. **验证**：`pytest tests/unit/test_system_prompt_builder.py`

### Step 3：AgentFileManager（依赖 Step 1）

1. 创建 `application/services/agent_file_manager.py`
2. 写单测 `test_agent_file_manager.py`
3. **验证**：`pytest tests/unit/test_agent_file_manager.py`

### Step 4：集成到 ContextBuilder（依赖 Step 2+3）

1. 修改 `context_builder.py`：新增 `_build_group_context()` + **替换**旧 SP 拼接逻辑为 SystemPromptBuilder
2. 修改 `deps.py`：注入 AgentFileManager + SystemPromptBuilder
3. 写集成测试
4. **验证**：`pytest tests/integration/test_memory_flow.py`

### Step 5：集成到 Runtime + Agent Service（不依赖 Step 4，可并行）

1. 修改 `claude_code_runtime.py`：`_run_cli()` 加 `cwd=`，`_spawn_long()` 签名加 `cwd`
2. 修改 `agent_service.py`：创建/删除时调用 AgentFileManager
3. Docker volume 配置
4. **验证**：端到端手动测试（创建 Agent → 发群聊消息 → 检查 CWD 文件）

---

## 九、开放问题处理

| # | 问题 | Phase A 决策 |
|---|------|-------------|
| Q1 | CLAUDE.md 由谁初始撰写？ | **AgentFileManager 模板生成**。从 `capability_tags` + `role` 推导内容 |
| Q3 | Agent CWD 生命周期？ | **持久保留**。Agent 删除时由 `cleanup_agent_cwd()` 清理 |
| Q4 | 多实例部署时路径 | **`/data/agenthub/agents/`**，Docker 挂载 persistent volume |
| Q5 | Agent 删除时清理 | **立即删除 CWD**。CLI memory 路径（`~/.claude/projects/...`）不删 |

---

## 十、Phase B/C 接口预留

Phase A 代码已为后续阶段预留扩展点：

| 扩展点 | 位置 | Phase B/C 用途 |
|--------|------|---------------|
| `GroupContext.task_board_*` | 当前返回空值 | Phase B 接 TaskFSM 实时状态 |
| `GroupContext.decisions_*` | 当前返回空值 | Phase B 接 `on_group_decision` Hook |
| `MemoryContext.l2_summary` | 保留不动 | Phase B `on_session_end` 生成摘要 |
| `MemoryContext.l4_rag` | 保留不动 | Phase C LLM 语义检索 |
| `AgentFileManager` 无 memory/ 操作 | 设计约束 | Phase B MemoryToolHandler 可读取 |

---

> **下一步**：确认本文档后，按 Step 1-5 顺序实施。预估 3-4 小时完成 Phase A 全部代码 + 测试。
