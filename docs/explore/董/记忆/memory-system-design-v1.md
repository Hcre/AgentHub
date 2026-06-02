# Agent 记忆系统 — 本地文件方案设计

> 日期：2026-05-30 | 状态：**初版设计，已有实验验证**
> 前置阅读：`ref-cc-haha-memory-arch.md`（cc-haha 架构）、`ref-memory-comparison.md`（5 项目对比）、`../黎/群聊记忆系统高效组织方案.md`（30+ 项目调研）
> 实验验证：`cli-memory-boundary-experiments.md` — 9 个实验确认了 CLI 三层注入结构、spawn 时缓存 `<system-reminder>`、kill + `--resume` 刷新文件

---

## 一、设计结论

1. **Agent 身份/约束/私有记忆 → 本地文件**（Agent CWD 下的 CLAUDE.md + memory/）
2. **群共享状态/关系/实时数据 → PG + Redis**（不变）
3. **CLI 自动管理 Layer 1（CLAUDE.md/MEMORY.md 注入）和 Layer 3（工具能力）**，AgentHub 只需关注 Layer 2（SP 模板）
4. **不需要 pgvector、Neo4j、Chroma**（Letta 实验：grep + markdown 74% vs 专用向量库 68.5%）
5. **SP 含上下文版本 hash，群聊上下文变更时 kill + `--resume` 重 spawn**。文件在 spawn 时读取（实验 6），同进程不重读。上下文变更（成员/任务/决策）→ 版本 hash 变化 → `_acquire_with_sp_guard` kill 旧进程 → `--resume` 起新进程，对话历史恢复（实验 8）。大多数轮次无变更，享受 V1 长驻低延迟。

---

## 二、CLI 三层注入模型

> 来源：`cli-memory-boundary-experiments.md` 实验 1-3

`--system-prompt` 模式下，CLI 的 System Prompt 由三层组成。

**关键行为（实验 6-8）**：`<system-reminder>` 在 spawn 时一次性读取并缓存，同进程后续轮次不重读。文件更新后需要 kill + `--resume` 起新进程才能读取最新内容。

```
CLI 完整 System Prompt =

┌───────────────────────────────────────────────────────────┐
│ Layer 1: <system-reminder> 注入链（不受 --system-prompt 影响） │
│                                                            │
│   spawn 时读取并缓存（同进程不重读，kill + --resume 后刷新）：   │
│     CLAUDE.md 内容（全局 + 项目/Agent CWD）← Agent 身份+领域    │
│     MEMORY.md 内容（auto-memory 索引）                       │
│     rules/*.md（用户配置的规则文件）                          │
│     currentDate / userEmail / gitStatus                    │
│     skills 列表                                             │
│                                                            │
│   群聊上下文（members / task_board / decisions）通过 context/    │
│   详情文件传递 —— Agent 在 CLAUDE.md 索引中看到链接，        │
│   需要时 Read。文件由 AgentHub 在上下文变更时更新，           │
│   配合 SP 版本 hash 触发重 spawn，新进程读到新文件。          │
├───────────────────────────────────────────────────────────┤
│ Layer 2: --system-prompt 内容（含版本 hash，变更触发重 spawn）  │
│                                                            │
│   被替换的：                                                 │
│     "You are Claude Code..." 默认人格                       │
│     # System 工具使用规范                                    │
│     # Memory 指令段 ← 必须补回                               │
│     # Doing tasks 任务执行规范                               │
│                                                            │
│   AgentHub 构建的：                                          │
│     Agent 身份/人格（从 PG 渲染）                             │
│     # Memory 指令段（补回，指向 CLI memory 路径）              │
│     行为约束（Delivery Contract）                            │
│     上下文版本 hash（用于检测变更、触发重 spawn）              │
├───────────────────────────────────────────────────────────┤
│ Layer 3: Harness 动态注入                                    │
│                                                            │
│   session hook 输出 / MCP server 指令 / deferred tools      │
│   运行时动态，每轮不同，AgentHub 不需要干预                    │
└───────────────────────────────────────────────────────────┘
```

**核心收益**：Layer 1 和 Layer 3 由 CLI 免费提供。AgentHub 构建 Layer 2 + 管理 Agent CWD 文件。上下文变更时通过 SP hash 触发重 spawn（~1-2s），大多数轮次无变更享受 V1 长驻低延迟。

---

## 三、存储边界

### 3.1 三层存储模型

```
┌──────────────────────────────────────────────────────────────┐
│                    PostgreSQL（关系 + 权威）                     │
│  agents / groups / sessions / messages / tasks                │
│  谁写：AgentHub 后端                                          │
│  谁读：AgentHub 后端（裁剪后注入 Agent）                         │
├──────────────────────────────────────────────────────────────┤
│                    Redis（热缓存 + 实时）                        │
│  L1 滑动窗口 / session 状态 / Pub/Sub                          │
│  谁写：AgentHub 后端                                          │
│  谁读：AgentHub 后端                                          │
├──────────────────────────────────────────────────────────────┤
│                 本地文件系统（Agent 自治域）                      │
│  Agent CWD 下的 CLAUDE.md + memory/                           │
│  谁写：AgentHub（CLAUDE.md）+ CLI（memory/）                    │
│  谁读：CLI 通过 <system-reminder> 自动注入                      │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 决策树

```
需要决定数据放哪？问：
├─ 需要 JOIN/WHERE/聚合查询？                    → PG
├─ 毫秒级读写 + 自动过期？                       → Redis
├─ CLI 需要跨会话记住？                          → Agent CWD 下的 memory/ 文件
├─ CLI 需要启动时就知道（身份/领域知识）？          → Agent CWD 下的 CLAUDE.md
├─ 多 Agent 并发写入同一份数据？                   → PG（事务保护）
└─ 纯 Agent 临时状态（对话上下文/工具历史）？       → CLI 进程内部，不持久化
```

### 3.3 边界速查表

| 数据 | 存储 | 理由 |
|------|------|------|
| Agent 身份/人格 | **PG（权威）+ CLAUDE.md（注入）** | PG 用于管理；CLAUDE.md 由 CLI 自动注入 |
| Agent 能力标签/角色 | **PG agents 表** | Coordinator 匹配 Agent |
| 群聊消息历史 | **PG**（持久）+ **Redis**（热窗口） | 需要按 session/时间查询 |
| 任务状态（TaskFSM） | **PG** | 状态机需要事务 |
| Agent 学习/经验 | **memory/ 文件**（CLI 自管） | Agent 私有，CLI 原生支持 |
| 群组决策记录 | **PG sessions.decisions** + SP 注入 | 需要跨 session 查询 |
| 任务产物（代码文件） | **Agent CWD workspace/** | CLI 工具直接操作 |
| 用户偏好 | **PG sessions.settings** | 需要跨 session 查询 |
| MEMORY.md 索引 | **memory/ 文件**（CLI 自管） | CLI 通过 `<system-reminder>` 自动注入 |

---

## 四、文件系统布局

### 4.1 Agent CWD

```
/tmp/agenthub/agents/{agent_id}/
├── CLAUDE.md              # 索引文件（~300 tokens），CLI spawn 时注入
│                          # 指向 context/ 下的详情文件，Agent 按需 Read
├── context/               # 详情文件（AgentHub 管理，Agent 按需读取）
│   ├── tech-stack.md      # 静态：技术栈
│   ├── conventions.md     # 静态：代码规范
│   ├── members.md         # 动态：群成员快照
│   ├── task-board.md      # 动态：任务看板
│   └── decisions.md       # 动态：决策日志
├── memory/                # CLI 运行时自动创建和管理
│   ├── MEMORY.md          # 索引（CLI 原生格式，200 行 / 25KB）
│   └── *.md               # 记忆文件（CLI 原生 frontmatter 格式）
└── workspace/             # 任务产物（可选）
    └── artifacts/         # 代码文件、diff
```

**设计原则 — 索引优先（渐进式披露）**：
- **CLAUDE.md 是索引，不是指南**：每条一行摘要 + 文件链接，~300 tokens 固定大小
- **context/ 是详情**：Agent 需要时用 Read 工具查看，不自动注入，不浪费 token
- **CLI 管 memory/**：目录和 MEMORY.md 由 CLI 首次写记忆时自动创建
- **AgentHub 管 CLAUDE.md + context/**：从 PG 渲染。上下文变更时更新动态文件，配合 SP 版本 hash 触发重 spawn（实验 8）让新进程读到新文件
- **不需要 `.brain/` 或 `.claude/`**

### 4.2 群共享域

```
/tmp/agenthub/groups/{group_id}/
├── members.md             # 成员能力快照（从 PG agents 表渲染）
├── decisions.md           # 群组决策日志
└── task_board.md          # 当前任务看板
```

这些文件是**群级权威源**，供前端展示任务/进度。每个 Agent 的 `context/` 下有对应的副本（由 AgentHub 从群文件裁剪后写入），Agent 通过 Read 工具按需查看。

### 4.3 Memory 目录隔离

CLI 的 memory 路径跟 CWD 走（实验 4 验证）：

```
Agent CWD:     /tmp/agenthub/agents/agent-001/
  → memory:    ~/.claude/projects/-tmp-agenthub-agents-agent-001/memory/

Agent CWD:     /tmp/agenthub/agents/agent-002/
  → memory:    ~/.claude/projects/-tmp-agenthub-agents-agent-002/memory/

结论: 不同 CWD → 不同 memory 目录 → 天然隔离，AgentHub 不需要做额外权限控制
```

### 4.4 与现有架构的对应

| 文件系统路径 | 注入方式 | 管理者 |
|-------------|---------|--------|
| Agent CWD/CLAUDE.md | CLI Layer 1（`<system-reminder>`，spawn 时注入） | AgentHub 渲染索引 |
| Agent CWD/context/*.md | Agent 按需 Read（不自动注入） | AgentHub 渲染详情 |
| Agent CWD/memory/MEMORY.md | CLI Layer 1（`<system-reminder>`） | CLI 自管 |
| `groups/{id}/*.md` | 不注入（前端消费 + 作为 Agent context/ 的渲染源） | AgentHub 渲染 |

---

## 五、文件格式

### 5.1 CLAUDE.md 格式（索引模式）

CLAUDE.md 是**索引**，不是指南。遵循渐进式披露原则：索引永远注入（~300 tokens），详情按需 Read。

**三通道分工**：
- `--system-prompt`：Agent 身份 + Memory 指令 + 行为约束 + 上下文版本 hash
- `CLAUDE.md`：上下文索引（CLI spawn 时注入，AgentHub 在上下文变更时更新 + SP hash 触发重 spawn）
- 用户消息：delta_text（最动态，每轮新消息）

```markdown
# Agent 上下文

## 领域知识
- [技术栈](context/tech-stack.md) — Python, FastAPI, SQLAlchemy, PostgreSQL, Redis
- [代码规范](context/conventions.md) — 5层洋葱架构，异步优先，Pydantic v2

## 群聊上下文
- [群成员](context/members.md) — 3人: 后端专家/前端专家/测试专家
- [任务看板](context/task-board.md) — 进行中: 实现登录API (后端专家)
- [最近决策](context/decisions.md) — 最新: JWT过期7天, refresh 30天 (2026-05-30)

需要详情时用 Read 工具查看对应文件。
```

**索引规则**：
- 每条一行：`[文件名](路径) — 一句话摘要`（≤100 字符）
- 总行数 ≤20 行，总 token ≤300
- 动态条目（群聊上下文段）由 AgentHub 在上下文变更时更新摘要文本
- 静态条目（领域知识段）仅在 Agent 创建/更新时渲染
- **不放身份/角色**（在 SP 中）、**不放 delta_text**（在用户消息中）

### 5.1b context/ 详情文件格式

Agent CWD 下的 `context/` 目录存放详情文件，Agent 通过 Read 工具按需查看：

```markdown
<!-- context/members.md -->
# 群成员

| Agent | 角色 | 技术栈 | 当前任务 |
|-------|------|--------|---------|
| 后端专家 | 后端开发 | Python, FastAPI, PostgreSQL | 实现登录 API |
| 前端专家 | 前端开发 | React, TypeScript | 设计登录页面 |
| 测试专家 | QA | Pytest, Playwright | 待分配 |
```

```markdown
<!-- context/decisions.md -->
# 群决策日志

## 2026-05-30
- **JWT 过期策略**: 过期时间 7 天，refresh token 30 天
  - 参与: 后端专家, 前端专家
  - 理由: 平衡安全性和用户体验

## 2026-05-29
- **ORM 选型**: SQLAlchemy 2.0 async
  - 参与: 后端专家
  - 理由: 团队熟悉度 + FastAPI 官方推荐
```

**静态 vs 动态文件**：

| 文件 | 类型 | 更新时机 |
|------|------|---------|
| `context/tech-stack.md` | 静态 | Agent 创建/角色变更时 |
| `context/conventions.md` | 静态 | Agent 创建/角色变更时 |
| `context/members.md` | 动态 | 成员加入/退出时 |
| `context/task-board.md` | 动态 | 任务状态变更时 |
| `context/decisions.md` | 动态 | 新决策产生时 |

### 5.2 memory/ 文件格式（CLI 原生）

由 CLI 维护，AgentHub 不需要干预格式。CLI 原生 frontmatter 格式：

```yaml
---
name: 任务结论-JWT过期策略
description: 确定了 JWT 过期时间为 7 天，refresh token 30 天
type: knowledge
tags: [auth, jwt, decision]
last_accessed: 2026-05-30
---

# JWT 过期策略决策

（正文内容）
```

---

## 六、System Prompt 构建

### 6.1 完整模板

AgentHub 通过 `--system-prompt` 向 CLI 传入以下内容。SP 含上下文版本 hash，hash 变化时 `_acquire_with_sp_guard` 自动 kill 旧进程 + `--resume` 起新进程（实验 8 验证）。

```
# Agent 身份
{从 PG agents.system_prompt 渲染}

# Memory
You have a persistent file-based memory at `{cli_memory_path}`.
Write to it directly with the Write tool.
Maintain MEMORY.md as a one-line-per-entry index. Keep entries under 150 chars.

# cli_memory_path = ~/.claude/projects/-{cwd-path-encoded}/memory/
# 例：CWD=/tmp/agenthub/agents/agent-001
#   → ~/.claude/projects/-tmp-agenthub-agents-agent-001/memory/
# 注意：这是 CLI 自动注入 <system-reminder> 时读取的路径，
#       不是 Agent CWD 下的 memory/（那个路径 CLI 不读）

Each memory file uses frontmatter:
---
name: {{name}}
description: {{one-line description}}
type: {{knowledge | feedback | reflection}}
---
{{content}}

When to save:
- Task conclusions and key decisions
- Learnings from failures
- User preferences and corrections
- Group decisions that affect future work

Do NOT save: ephemeral task details, code patterns in source, git history.

# 行为约束
{从 PG agents.capability_tags 生成 Delivery Contract}

# Context
ctx_hash: {上下文版本 hash}
```

**不在 SP 中的内容（改走其他通道）**：

| 内容 | 通道 | 说明 |
|------|------|------|
| 群成员快照 | context/ 详情文件 + CLAUDE.md 索引 | 变更时更新 + SP hash 触发重 spawn（~1-2s） |
| 任务看板 | context/ 详情文件 + CLAUDE.md 索引 | 同上 |
| 最近决策 | context/ 详情文件 + CLAUDE.md 索引 | 同上 |
| delta_text（新消息） | 用户消息 | 最高频变化，走消息通道，不触发任何文件更新 |

### 6.2 `# Memory` 指令段的设计

| | CLI 原生 `# Memory` 段 | AgentHub 精简版 |
|---|----------------------|----------------|
| Token 数 | ~2000 tokens | ~300 tokens |
| Type 种类 | 6 种（user/feedback/project/reference/…） | 3 种（knowledge/feedback/reflection） |
| 保存规则 | 复杂的排除规则体系 | 4 条简明规则 |
| 场景 | 个人用户 | 群聊 Agent |

精简理由：Agent 本身就是项目的一部分，不需要区分"user memory"和"project memory"。3 种 type 足够覆盖群聊场景。

### 6.3 构建代码

```python
class SystemPromptBuilder:
    """构建 --system-prompt 内容。

    SP 包含 Agent 身份 + Memory 指令 + 行为约束 + 上下文版本 hash。
    上下文变更 → hash 变化 → _acquire_with_sp_guard kill 旧进程 →
    --resume 起新进程（实验 8 验证通过）。
    """

    def build_agent_sp(self, agent: AgentDefinition, ctx_hash: str = "") -> str:
        """构建 SP。ctx_hash 变化触发重 spawn。"""
        parts = [
            agent.system_prompt,                     # Agent 身份
            self._memory_instructions(agent.cwd),     # # Memory 指令段
            agent.delivery_contract,                  # 行为约束
        ]
        if ctx_hash:
            parts.append(f"# Context\nctx_hash: {ctx_hash}")
        return "\n\n".join(p for p in parts if p)

    @staticmethod
    def _cwd_to_cli_memory_path(cwd: Path) -> str:
        """CWD → CLI 实际的 memory 路径。

        CLI 的 memory 路径规则：~/.claude/projects/-{cwd 中 / 替换为 -}/memory/
        例：/tmp/agenthub/agents/a1 → ~/.claude/projects/-tmp-agenthub-agents-a1/memory/
        """
        encoded = str(cwd).replace("/", "-")
        return f"~/.claude/projects/{encoded}/memory/"

    def _memory_instructions(self, cwd: Path) -> str:
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

class AgentFileManager:
    """管理 Agent CWD 下的 CLAUDE.md（索引）+ context/（详情）。"""

    def ensure_agent_cwd(self, agent: AgentDefinition) -> Path:
        """Agent 创建时调用一次。"""
        cwd = agent.cwd
        cwd.mkdir(parents=True, exist_ok=True)
        (cwd / "context").mkdir(exist_ok=True)
        # 渲染静态详情文件
        self._render_static_context(agent)
        # 渲染初始索引
        self._render_claude_md(agent, group_ctx=None)
        return cwd

    def update_group_context(
        self,
        agent: AgentDefinition,
        group_ctx: GroupContext,
    ) -> str | None:
        """上下文变更时调用。更新动态详情文件 + CLAUDE.md 索引。

        返回新的上下文版本 hash（有变更时）或 None（无变更时）。
        调用方用 hash 判断是否触发重 spawn。
        """
        ctx_dir = agent.cwd / "context"
        # 更新详情文件（全量覆写）
        (ctx_dir / "members.md").write_text(group_ctx.members_detail)
        (ctx_dir / "task-board.md").write_text(group_ctx.task_board_detail)
        (ctx_dir / "decisions.md").write_text(group_ctx.decisions_detail)
        # 更新索引（摘要行变化才重写）
        self._render_claude_md(agent, group_ctx)

    def _render_claude_md(
        self,
        agent: AgentDefinition,
        group_ctx: GroupContext | None,
    ) -> None:
        """渲染 CLAUDE.md 索引（~300 tokens）。"""
        lines = [
            "# Agent 上下文",
            "",
            "## 领域知识",
            f"- [技术栈](context/tech-stack.md) — {agent.tech_stack_summary}",
            f"- [代码规范](context/conventions.md) — {agent.conventions_summary}",
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
        (agent.cwd / "CLAUDE.md").write_text("\n".join(lines))
```

> **delta_text**（新消息）不写入任何文件，作为用户消息传给 CLI stdin。

---

## 七、数据流

### 7.1 Agent 创建/更新时：PG → CLAUDE.md 渲染

```
用户/管理员 创建 Agent
         │
         ▼
AgentHub 后端写入 PG agents 表（权威源）
         │
         ▼
AgentFileManager.ensure_agent_cwd(agent):
  ├─ 创建 Agent CWD: /tmp/agenthub/agents/{agent_id}/
  ├─ 创建 context/ 目录
  ├─ 渲染静态详情文件:
  │     ├─ context/tech-stack.md（从 capability_tags）
  │     └─ context/conventions.md（从 Agent 角色推导）
  └─ 渲染 CLAUDE.md 索引（~300 tokens，指向 context/ 文件）
  memory/ 目录不创建 — 由 CLI 首次写记忆时自动创建
  身份/角色 → 走 --system-prompt 注入，不写入 CLAUDE.md
```

### 7.2 Agent 启动/重 spawn 时：SP 构建 → CLI 注入

```
Agent CLI 进程启动（首次或重 spawn）
         │
         ▼
ClaudeCodeRuntime._build_cmd():
  ├─ SystemPromptBuilder.build_agent_sp(agent, ctx_hash)
  │     ├─ Agent 身份（PG 渲染）
  │     ├─ # Memory 指令段（~300 tokens）
  │     ├─ 行为约束
  │     └─ 上下文版本 hash
  ├─ cmd.extend(["--system-prompt", sp])
  └─ cmd.extend(["--print", "-p", user_message])
         │
         ▼
CLI 启动 → System Prompt 三层拼接:
  Layer 1: <system-reminder> → CLAUDE.md + MEMORY.md + rules（spawn 时读取）
  Layer 2: --system-prompt → Agent 身份 + Memory + 约束 + hash
  Layer 3: Harness 动态注入
```

### 7.2b 上下文变更时：文件更新 + 重 spawn

```
群聊上下文变更（成员/任务/决策）
         │
         ▼
AgentFileManager.update_group_context(agent, group_ctx):
  ├─ 更新详情文件：
  │     ├─ context/members.md（成员变更时）
  │     ├─ context/task-board.md（任务状态变更时）
  │     └─ context/decisions.md（新决策时追加）
  ├─ 更新 CLAUDE.md 索引摘要行
  └─ 返回新的上下文版本 hash
         │
         ▼
SP hash 变化 → _acquire_with_sp_guard 检测到变化（已有机制）
  ├─ kill 旧进程（terminate → kill）
  ├─ --resume 起新进程
  │     → <system-reminder> 重新读取 CLAUDE.md（含新摘要）
  │     → 重新读取 MEMORY.md（含新写入的记忆）
  │     → 对话历史完整恢复（实验 8 验证）
  └─ 代价：~1-2s，仅在上下文实际变化时触发

delta_text（新消息）作为用户消息传入 CLI stdin，不走文件，不触发重 spawn
```

### 7.3 Agent 运行时：记忆读写

```
Agent 写记忆（CLI 驱动）:
  1. Agent 在推理中判断"这个信息值得记住"
  2. Agent 调用 Write 工具 → 写入 {cli_memory_path}/{name}.md
     （绝对路径 ~/.claude/projects/-{encoded-cwd}/memory/，见 SP 中 # Memory 指令）
  3. Agent 更新 {cli_memory_path}/MEMORY.md 索引
  4. 同 session 内不可见（实验 7），下次 spawn/resume 时 CLI 自动注入
  AgentHub 不参与此流程

Agent 读记忆（CLI 驱动）:
  1. Agent 调用 Read/Grep 工具 → 读取 {cli_memory_path} 下的文件
  2. 注意：当前 session 新写入的记忆可以通过 Read 直接读（文件已存在），
     但不会出现在 <system-reminder> 中（需要重 spawn）
  AgentHub 不参与此流程

Agent 查群记忆（AgentHub 驱动）:
  1. Agent 调用 get_group_memory Tool（Phase B）
  2. AgentHub MemoryToolHandler → 从 PG/群文件检索
  3. 返回结果给 Agent
```

---

## 八、群聊记忆 vs CLI 记忆边界

### 8.1 核心区分

```
┌──────────────────────────────────────────────────────────┐
│              群聊共享记忆（AgentHub 管理）                    │
│                                                          │
│  存储：PG + Redis + groups/{id}/ 文件                       │
│  注入：AgentHub → Agent CWD context/ 文件 → CLAUDE.md 索引  │
│       上下文变更 → SP hash 变化 → kill + resume 重 spawn    │
│  生命周期：群存在期间 + 审计保留                             │
│                                                          │
│  内容：                                                   │
│  · members.md / task_board.md  ──→ context/ + CLAUDE.md 索引│
│  · decisions.md                ──→ context/ + CLAUDE.md 索引│
│  · PG messages 表              ──→ group_delta_text（用户消息）│
│  · Redis L1 滑动窗口           ──→ group_delta_text（用户消息）│
└──────────────────────────┬───────────────────────────────┘
                           │ 文件更新 + SP hash 触发重 spawn
┌──────────────────────────▼───────────────────────────────┐
│              Agent 私有记忆（CLI 管理）                      │
│                                                          │
│  存储：Agent CWD 下的 CLAUDE.md + memory/                   │
│  注入：CLI 通过 Layer 1 <system-reminder> 自动注入          │
│  生命周期：Agent CWD 生命周期                               │
│                                                          │
│  内容：                                                   │
│  · CLAUDE.md                   ──→ Layer 1 自动           │
│  · memory/MEMORY.md            ──→ Layer 1 自动           │
│  · memory/*.md                 ──→ Agent 主动 Read/Grep   │
│  · 对话上下文窗口                ──→ CLI 进程内部           │
│  · 工具调用历史                  ──→ CLI 进程内部           │
└──────────────────────────────────────────────────────────┘
```

### 8.2 注入边界

```
Agent A 的完整上下文 =

  ┌─ Layer 1: CLI 自动注入（spawn 时读取，重 spawn 刷新）────┐
  │ CLAUDE.md 索引    → ~300 tokens，指向 context/ 详情    │
  │ MEMORY.md         → 该 Agent 的历史记忆索引            │
  │ rules/*.md        → 用户配置的规则                    │
  └──────────────────────────────────────────────────────┘
  +
  ┌─ Agent 按需 Read（不自动注入）──────────────────────────┐
  │ context/*.md      → 技术栈/规范/成员/任务/决策详情     │
  │ memory/*.md       → 记忆文件全文                      │
  └──────────────────────────────────────────────────────┘
  +
  ┌─ Layer 2: --system-prompt（含版本 hash，变更触发重 spawn）─┐
  │ Agent 身份     → "你是群聊中的后端专家..."              │
  │ # Memory 指令  → "记忆路径是 {cli_memory_path}..."     │
  │ 行为约束       → "回复前检查新鲜度..."                  │
  │ 上下文版本 hash → "ctx:v1.2.3"                        │
  └──────────────────────────────────────────────────────┘
  +
  ┌─ 用户消息通道（每轮不同）───────────────────────────────┐
  │ delta_text     → 自上次发言后的新消息                   │
  └──────────────────────────────────────────────────────┘

Agent A 看不到：
  · Agent B 的 CLAUDE.md（不同 CWD）
  · Agent B 的 memory/ 目录（CLI 路径隔离）
  · Agent B 的 CLI 内部对话历史
  · Agent B 的工具调用记录
```

### 8.3 边界法则

| 问题 | 答案 |
|------|------|
| Agent A 能看到群聊消息吗？ | 能。群上下文通过 CLAUDE.md 索引 + context/ 详情看到；新消息通过 delta_text 用户消息看到 |
| Agent A 能读 Agent B 的私有记忆吗？ | **不能**。不同 CWD → 不同 memory 路径 → CLI 天然隔离 |
| Agent A 写的记忆能被 Agent B 看到吗？ | 默认不能。除非显式写入群共享域（通过 Phase B 的 Tool API） |
| CLI 进程崩溃后记忆还在吗？ | 在。memory/ 文件不受进程生命周期影响 |
| Coordinator 能看到所有 Agent 的私有记忆吗？ | 技术上能（后端有文件系统权限），但设计约束禁止 |

---

## 九、需要新增/改动的组件

### 9.1 新增组件

| 组件 | 职责 | 优先级 |
|------|------|:---:|
| `SystemPromptBuilder` | 构建 `--system-prompt` 内容（Agent 身份 + Memory 指令 + 行为约束 + 上下文版本 hash） | P0 |
| `AgentFileManager` | 创建 Agent CWD + 渲染 CLAUDE.md | P0 |

### 9.2 需改动的现有代码

| 文件 | 改动 |
|------|------|
| `claude_code_runtime.py::_build_cmd()` | 用 `SystemPromptBuilder` 构建完整 SP，替代当前仅透传 `request.system_prompt` |
| `claude_code_runtime.py::_spawn_long()` | 同上 |
| `context_builder.py` | 扩展或替换为 `SystemPromptBuilder` |

### 9.3 现有 MemoryContext 的映射

```python
class MemoryContext(BaseModel):
    l1_working: list[dict] = []        # 在用：Redis 滑动窗口
    l2_summary: str | None = None      # 预留，Phase A 不实现
    l3_specs: str | None = None        # 预留，Phase A 不实现
    l4_rag: str | None = None          # 预留，Phase A 不实现
```

> **注意**：l2/l3/l4 当前是死字段。`claude_code_runtime.py` 不访问 `request.memory`。
> 等 Phase B 钩子系统（`on_session_end` 生成摘要 → l2_summary）和 Phase C LLM 检索（→ l4_rag）落地后再激活。
> 当前 ContextBuilder 填充 L1 仅用于私聊路径的消息窗口传递，群聊路径已改用 group_delta_text + CLAUDE.md 通道。

### 9.4 不引入的新组件

- ❌ pgvector — grep + markdown 更优
- ❌ Neo4j/Cognee — tags + wikilink 替代
- ❌ Chroma/LanceDB — 不需要
- ❌ 新 PG 表 — `sessions.preferences`/`sessions.decisions` JSONB 字段足够

---

## 十、开放问题

| # | 问题 | 状态 | 答案/方向 |
|---|------|:---:|------|
| Q1 | CLAUDE.md 由谁初始撰写？ | 开放 | 用户手写 / 模板生成（按 Agent 角色） / LLM 辅助生成 |
| Q2 | memory/ 文件质量如何控制？ | 开放 | CLI 原生有防重复机制（alreadySurfaced），AgentHub 不需要额外控制 |
| Q3 | Agent CWD 生命周期？ | 开放 | 意向持久保留（memory/ 是长期记忆），但与 Q4 的 `/tmp` 路径矛盾 → 必须先解决 Q4 才能定 Q3 |
| Q4 | 多实例部署时 `/tmp/agenthub/` 是否可用？ | 开放 | 容器重启后 `/tmp` 清空 → 需持久化卷或改路径为 `/data/agenthub/`。**Q3 依赖此决策** |
| Q5 | Agent 删除时文件清理策略？ | 开放 | 保留 N 天？归档？立即删除？ |
| Q6 | 群共享文件并发写入策略？ | 已明确 | Coordinator 独占写。Agent 不直接写群文件，通过 Phase B Tool API |

---

## 十一、渐进实施路线

```
Phase A（立即可做，无需 Phase 1 长驻）:
  ✅ AgentFileManager        → 创建 Agent CWD + 渲染 CLAUDE.md
  ✅ SystemPromptBuilder     → 构建完整 SP（身份 + Memory 指令 + 群聊上下文）
  ✅ claude_code_runtime 改动 → _build_cmd() 使用 SystemPromptBuilder
  ✅ Agent 筛选              → Coordinator 裁剪群记忆（filter by agent tags）
  ✅ 防重复注入              → TTL Set，同一 session 不重复注入
  注: memory/ 目录不需要创建 — CLI 首次写记忆时自动创建

Phase B（依赖 Phase 1 长驻 CLI + Tool API）:
  🟡 MemoryToolHandler       → get_group_memory / save_to_group Tool
  🟡 钩子系统（4 个）         → on_task_completed / on_task_failed /
                               on_group_decision / on_session_end
  🟡 分级检索 Step 2         → keywords ×0.5 + recency ×0.3 + pinned ×0.2

Phase C（有真实需求驱动）:
  🔵 LLM 语义选择            → 对标 cc-haha findRelevantMemories
  🔵 记忆编译                → 文件数 >20 后自动聚合
  🔵 群决策自动归档           → on_group_decision Hook 自动写 decisions.md
```

---

## 附录 A：cc-haha 记忆系统参考要点

> 来源：已合并的 `memory-system-future.md`，原始日期 2026-05-29

### A.1 核心设计

| 类型 | 路径 | 作用域 |
|------|------|--------|
| Auto-memory | `~/.claude/auto-memory/` | 用户级，全局 |
| Agent-memory | `~/.claude/agent-memory/<agent>/` | 单个 Agent，user/project/local scope |
| Team-memory | `~/.claude/auto-memory/team/` | 团队共享，可 VCS |
| Session-memory | `~/.claude/session-memory/` | 单次会话临时 |

| 机制 | 说明 |
|------|------|
| 入口索引 | `MEMORY.md`，每条 ≤150 字符，200 行 / 25KB 截断 |
| 智能检索 | Sonnet 模型选择 ≤5 条相关记忆，去重 + 工具感知 |
| 注入方式 | `loadMemoryPrompt()` 注入 System Prompt |
| 扫描优化 | 只读 frontmatter 前 30 行，不读全量 |

### A.2 对 AgentHub 的复用与差异

| 直接复用 | 需要重新设计 |
|---------|------------|
| frontmatter 格式 | 1v1 → N Agent 群聊（独立 CWD + 群共享层） |
| MEMORY.md 索引入口 | Agent 自主写入 → 钩子辅助 + 审计 |
| AI 驱动相关性检索（Phase C） | Sonnet 每次调 → 分级 fast keyword + slow LLM |
| 多层 scope | scope 简化为 agent-private / group-shared 两级 |

### A.3 与长驻 CLI 协作

选定的**方案 A**（`--system-prompt` + 补回 Memory 指令）：

| 选项 | 做法 | 选择理由 |
|------|------|---------|
| A: `--system-prompt` | 完全控制 Agent 人格，补回 Memory 指令（~300 tokens） | **✅ 选定** — Agent 人格差异是群聊核心体验 |
| B: `--append-system-prompt` | 保留 CLI 默认人格，追加 Agent 角色 | ❌ 所有 Agent 都像 Claude Code |
| C: Tool API | `get_memory`/`save_memory` 工具 | 与 A 互补，Phase B 实现 |

### A.4 现有基础

`protocol.py` 中 `MemoryContext` 四层已定义，仅 L1 在用：

```python
class MemoryContext(BaseModel):
    l1_working: list[dict] = []     # Redis 滑动窗口 ← 在用
    l2_summary: str | None = None   # 超长历史摘要 ← 预留
    l3_specs: str | None = None     # 群共享上下文 ← 预留
    l4_rag: str | None = None       # LLM 检索结果 ← 预留
```

---

## 附录 B：与 v1 原始设想的修正清单

CLI 边界实验修正了 v1 原始设想中的 6 个假设：

| # | 原始假设 | 实验结论 | 设计修正 |
|---|---------|---------|---------|
| 1 | `.brain/soul.md + base.md + act.md` 需要手动注入 SP | CLI 自动注入 CLAUDE.md，AgentHub 不需要手动读文件 | 用 Agent CWD 下的 CLAUDE.md 替代 `.brain/` |
| 2 | MEMORY.md 需要 AgentHub 代码读取并注入 | CLI 通过 `<system-reminder>` 自动注入 MEMORY.md | 删除相关代码逻辑 |
| 3 | `.claude/` 目录需要 AgentHub 创建和管理 | `--system-prompt` 模式下 CLI 不读 `.claude/` | 删除 `.claude/` 目录设计 |
| 4 | `ContextBuilder` 需要读取文件拼入 SP | Layer 1 由 CLI 免费提供 | 重命名为 `SystemPromptBuilder`，只构建 Layer 2 |
| 5 | `# Memory` 指令段由 CLI 自带 | `--system-prompt` 替换了该指令段 | Phase A 必做：补回 ~300 tokens 的精简版 |
| 6 | 群聊上下文放 SP，SP 变更时杀进程重建 | CLI spawn 时读取 `<system-reminder>`，同进程不重读（实验 6），但 kill + `--resume` 新进程会重新读取（实验 8） | 群聊上下文放 context/ 详情文件 + CLAUDE.md 索引摘要。SP 含版本 hash，上下文变更时 hash 变化 → `_acquire_with_sp_guard` kill 旧进程 → `--resume` 起新进程读取新文件。代价 1-2s，仅上下文变化时触发 |

---

> **下一步**：与团队讨论 Q1/Q4/Q5 后定稿，纳入 `docs/specs/` 作为正式规格。
> **关联文档**：`cli-memory-boundary-experiments.md`、`memory-feature-evaluation.md`、`ref-cc-haha-memory-arch.md`、`ref-cc-haha-memory-code.md`、`ref-memory-comparison.md`、`../黎/群聊记忆系统高效组织方案.md`
