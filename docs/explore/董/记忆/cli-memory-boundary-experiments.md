# CLI 记忆边界实验报告

> 日期：2026-05-30 | 状态：**实验完成，结论可用于设计决策**
> 前置阅读：`memory-system-design-v1.md`（v1 设计）、`ref-cc-haha-memory-code.md`（cc-haha 代码分析）
> 目的：确认 Claude CLI 在 AgentHub 使用场景下的记忆边界 — 什么由 CLI 管、什么由 AgentHub 管、两者如何协作

---

## 一、实验背景

AgentHub 采用 CLI 优先架构（见 `worklogs/decisions/0001-cli-first-pivot.md`），通过 `ClaudeCodeRuntime` 以子进程方式调用 Claude CLI。当前代码（`claude_code_runtime.py`）使用 `--system-prompt` 传入 Agent 身份。

核心问题：**CLI 自带的记忆系统在 `--system-prompt` 模式下还能用多少？AgentHub 需要自己管哪些？**

---

## 二、实验环境

- CLI 版本：Claude Code（当前安装版本）
- 运行目录：`/home/huishuohuademao/workspace/AgentHub`
- 项目有 CLAUDE.md + 5 条 auto-memory 记录
- 实验方法：用不同参数启动 CLI，让 CLI 自报 system prompt 结构

---

## 三、实验结果

### 实验 1：默认模式（不传 --system-prompt）

**命令**：`claude --print -p "你的 system prompt 中有没有 auto memory 相关内容？"`

**结果**：

- system prompt 中有完整的 `# Memory` 段
- 包含指令："You have a persistent file-based memory at `/home/huishuohuademao/.claude/projects/-home-huishuohuademao-workspace-AgentHub/memory/`"
- 包含 MEMORY.md 索引内容（5 条记忆）
- 包含 CLAUDE.md 内容
- CLI 人格为 "You are Claude Code, Anthropic's official CLI..."

### 实验 2：`--system-prompt` 模式

**命令**：`claude --print --system-prompt "你是 Agent-005，测试用。" -p "列出 system prompt 中所有 # 标题"`

**结果**：

- CLI 人格 **被替换** 为 "你是 Agent-005，测试用。"（前面有一句 SDK 声明）
- `# Memory` **指令段消失** — "You have a persistent file-based memory..." 不存在
- 但 **`<system-reminder>` 注入链仍然生效**：
  - `# claudeMd` → CLAUDE.md 内容 ✅ 保留
  - MEMORY.md 内容 → 以只读上下文注入 ✅ 保留
  - `# currentDate` ✅ 保留
  - `# userEmail` ✅ 保留
  - `rules/*.md` ✅ 保留

### 实验 3：`--append-system-prompt` 模式

**命令**：`claude --print --append-system-prompt "你是 Agent-002，前端专家。" -p "你同时有 Claude Code 和 Agent-002 吗？"`

**结果**：

- CLI 默认人格 **保留**（"You are Claude Code..."）
- 自定义内容 **追加** 在默认 system prompt 末尾（`# Context management` 段之后）
- `# Memory` 指令段 ✅ 保留
- CLAUDE.md ✅ 保留
- MEMORY.md ✅ 保留

### 实验 4：Memory 目录路径

**命令**：在不同 CWD 下运行 CLI，查看 memory 目录

**结果**：

- memory 路径 **跟 CWD 走**：`~/.claude/projects/-{cwd-path-encoded}/memory/`
- 在 AgentHub 目录下：`~/.claude/projects/-home-huishuohuademao-workspace-AgentHub/memory/`
- 在临时空目录下：**不存在 memory 目录**（无 CLAUDE.md、无历史 → CLI 不创建）

### 实验 5：CLI 工具能力

- `--system-prompt` 模式下 CLI **仍保留 Read/Write/Bash 等工具**
- 可以读写文件，包括 memory 目录下的文件
- 但因为 `# Memory` 指令段消失，**CLI 不会主动写记忆**

---

## 四、核心发现

### 4.1 CLI System Prompt 的三层结构

```
CLI 完整 System Prompt =

┌───────────────────────────────────────────────────────────┐
│ 层 1: 核心人格 (可被 --system-prompt 替换)                    │
│                                                            │
│   默认内容:                                                 │
│     "You are Claude Code, Anthropic's official CLI..."     │
│     # System (工具使用规范)                                  │
│     # Doing tasks (任务执行规范)                             │
│     # Memory (记忆系统指令 + 路径)  ← --system-prompt 后消失 │
│     # Context management (上下文管理)                       │
│                                                            │
│   --system-prompt 时: 整个层 1 被替换为用户传入的内容         │
│   --append-system-prompt 时: 用户内容追加在层 1 末尾         │
├───────────────────────────────────────────────────────────┤
│ 层 2: <system-reminder> 注入链 (不受 --system-prompt 影响)   │
│                                                            │
│   始终注入:                                                 │
│     # claudeMd → 全局 CLAUDE.md + 项目 CLAUDE.md            │
│     rules/*.md → 用户配置的规则文件                          │
│     MEMORY.md 内容 → 只读上下文 (auto-memory 索引)          │
│     # userEmail                                             │
│     # currentDate                                           │
│     gitStatus → 当前 git 状态快照                            │
│     skills → 可用 skill 列表                                │
│                                                            │
│   特点: 以 <system-reminder> 标签包裹，独立于层 1            │
├───────────────────────────────────────────────────────────┤
│ 层 3: Harness 动态注入                                      │
│                                                            │
│   session hook 输出                                        │
│   MCP server 指令                                          │
│   deferred tools 列表                                      │
│                                                            │
│   特点: 运行时动态，每轮可能不同                              │
└───────────────────────────────────────────────────────────┘
```

### 4.2 `--system-prompt` vs `--append-system-prompt` 对比

| 特性 | `--system-prompt` | `--append-system-prompt` |
|------|-------------------|-------------------------|
| CLI 默认人格 | ❌ 被替换 | ✅ 保留 |
| `# Memory` 指令段 | ❌ 消失 | ✅ 保留 |
| CLI 主动写记忆 | ❌ 不会 | ✅ 会（有指令驱动） |
| CLAUDE.md 注入 | ✅ 保留 | ✅ 保留 |
| MEMORY.md 只读注入 | ✅ 保留 | ✅ 保留 |
| 自定义 Agent 身份 | ✅ 完全控制 | ⚠️ 追加在末尾，可能被默认人格"压过" |

### 4.3 Memory 目录隔离机制

```
CLI memory 路径 = ~/.claude/projects/-{CWD 路径编码}/memory/

AgentHub CWD:     /home/.../AgentHub
  → memory:       ~/.claude/projects/-home-...-AgentHub/memory/

Agent-001 CWD:    /tmp/agenthub/agents/agent-001/
  → memory:       ~/.claude/projects/-tmp-agenthub-agents-agent-001/memory/

Agent-002 CWD:    /tmp/agenthub/agents/agent-002/
  → memory:       ~/.claude/projects/-tmp-agenthub-agents-agent-002/memory/

结论: 不同 CWD → 不同 memory 目录 → 天然隔离
```

---

## 五、AgentHub 与 CLI 的记忆职责划分

### 5.1 当前状态（`--system-prompt` 模式）

```
┌─────────────────────────────────────────────────────────────┐
│  CLI 自动管理（AgentHub 不需要干预）                           │
│                                                              │
│  ├── CLAUDE.md 注入（通过 <system-reminder>）                │
│  ├── MEMORY.md 内容注入（只读上下文，通过 <system-reminder>） │
│  ├── Session history（对话历史，跨轮保持）                    │
│  ├── Auto-compact（上下文压缩）                              │
│  ├── --resume 会话恢复                                       │
│  └── 工具执行（Read/Write/Bash/Grep/Glob/...）              │
├─────────────────────────────────────────────────────────────┤
│  CLI 丢失（被 --system-prompt 替换掉）                       │
│                                                              │
│  ├── "You are Claude Code..." 默认人格                      │
│  ├── # Memory 指令段（路径 + 写入规则 + 格式要求）           │
│  ├── # System 工具使用规范                                   │
│  ├── # Doing tasks 任务执行规范                              │
│  └── CLI 主动写记忆的行为                                    │
├─────────────────────────────────────────────────────────────┤
│  AgentHub 需要在 --system-prompt 中提供                      │
│                                                              │
│  ├── Agent 身份/人格（从 PG agents 表渲染）                  │
│  ├── 记忆系统指令（补回 # Memory 段，指向 Agent 专属路径）    │
│  ├── MemoryContext 注入（l2_summary / l3_specs / l4_rag）    │
│  ├── 群聊上下文（members / task_board / delta）              │
│  └── 行为约束（Agent 的 Delivery Contract）                  │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 当前代码的缺失

`claude_code_runtime.py` 第 351-352 行：

```python
if request.system_prompt:
    cmd.extend(["--system-prompt", request.system_prompt])
```

问题：
1. `request.memory`（MemoryContext）**没有注入** — 只在 ClaudeAdapter 路径处理了
2. 没有补回 `# Memory` 指令段 — Agent 不会主动写记忆
3. 没有指定 Agent 专属的 memory 路径 — 所有 Agent 共用 AgentHub 的 memory

---

## 六、设计决策：两个方案

### 方案 A：继续用 `--system-prompt`，AgentHub 补全缺失部分

```
AgentHub 构建 system_prompt:
  ├── Agent 身份（PG 渲染）
  ├── # Memory 指令段（补回，指向 Agent CWD 下的 memory/）
  ├── MemoryContext（l2/l3/l4）
  ├── 群聊上下文
  └── 行为约束

CLI 自动注入（不受影响）:
  ├── CLAUDE.md（Agent CWD 下放定制化 CLAUDE.md）
  ├── MEMORY.md 内容
  └── session history

Agent CWD 隔离:
  每个 Agent 用独立 CWD（/tmp/agenthub/agents/{agent_id}/）
  → CLI 自动为该 CWD 创建隔离的 memory 目录
  → AgentHub 在该 CWD 下放 CLAUDE.md 作为 Agent 项目上下文
```

**优点**：完全控制 Agent 人格，不受 CLI 默认人格干扰
**缺点**：需要自己补回 # Memory 指令段、# System 工具规范等

### 方案 B：改用 `--append-system-prompt`，利用 CLI 内置能力

```
CLI 保留默认 system prompt:
  ├── "You are Claude Code..." 人格
  ├── # Memory 指令段（完整保留）
  ├── # System 工具规范
  └── # Doing tasks

AgentHub 追加:
  ├── ## Agent 身份覆盖（"虽然你是 Claude Code，但在本次会话中你扮演..."）
  ├── MemoryContext（l2/l3/l4）
  ├── 群聊上下文
  └── 行为约束
```

**优点**：CLI 的记忆系统完整保留，Agent 自动具备记忆读写能力
**缺点**：Agent 身份是"追加"在 Claude Code 人格后面，可能被默认人格"压过"；Agent 可能表现得更像 Claude Code 而不是自定义角色

### 方案评估

| 维度 | 方案 A（--system-prompt） | 方案 B（--append-system-prompt） |
|------|--------------------------|--------------------------------|
| Agent 身份控制 | ✅ 完全控制 | ⚠️ 可能被 Claude Code 人格稀释 |
| 记忆系统完整性 | ⚠️ 需要补回 | ✅ 开箱即用 |
| 工具使用规范 | ⚠️ 需要补回 | ✅ 开箱即用 |
| 实现成本 | 中（需要构建完整 SP） | 低（只追加差异部分） |
| Agent 人格一致性 | ✅ 强（100% 自定义） | ❌ 弱（与 Claude Code 人格混合） |
| 群聊多角色区分 | ✅ 每个 Agent 完全不同 | ❌ 所有 Agent 都像 Claude Code |

**建议：方案 A**。AgentHub 是多 Agent 协作平台，Agent 的人格差异是核心体验。方案 B 会让所有 Agent 都表现得像 Claude Code 加了个角色标签，失去人格特色。补回 `# Memory` 指令段的成本很低（几行模板文本）。

---

## 七、方案 A 的具体实施要点

### 7.1 Agent CWD 结构

```
/tmp/agenthub/agents/{agent_id}/
├── CLAUDE.md              # AgentHub 渲染：Agent 的项目上下文
├── memory/                # CLI 自动创建（首次写记忆时）
│   ├── MEMORY.md          # 索引
│   └── *.md               # 记忆文件
└── workspace/             # 任务产物（可选）
```

### 7.2 System Prompt 构建模板

```
# Agent 身份
{从 PG agents.system_prompt 渲染}

# 行为约束
{从 PG agents.capability_tags 生成行为契约}

# Memory
You have a persistent file-based memory at `{agent_cwd}/memory/`.
Write to it directly with the Write tool. Each memory file uses frontmatter:
---
name: {{memory name}}
description: {{one-line description}}
type: {{knowledge | feedback | reflection}}
---
{{content}}

Update MEMORY.md as an index. Keep entries under 150 characters.
Save learnings that will be useful in future tasks. Do not save ephemeral details.

# Group Context (群聊时注入)
{members.md + task_board.md + decisions.md}

# Conversation Summary (如有)
{MemoryContext.l2_summary}

# Project Context (如有)
{MemoryContext.l3_specs}
```

### 7.3 需要改动的代码

| 文件 | 改动 |
|------|------|
| `claude_code_runtime.py` | `_build_cmd()` 中用 `_build_agent_system_prompt()` 构建完整 SP |
| `claude_code_runtime.py` | `_spawn_long()` 中同上 |
| 新增 `AgentFileManager` | 创建 Agent CWD + 渲染 CLAUDE.md |
| `protocol.py` | MemoryContext 不变（已有 l1-l4） |

---

## 八、实验 6：V1 长驻模式 CLAUDE.md 热重载

### 8.1 实验目的

验证 `--input-format stream-json` 长驻模式下，CLI 是否每轮重新读取 CWD 下的 CLAUDE.md。

**背景**：`memory-system-design-v1.md` 提出的"SP 永不变"设计，依赖 CLAUDE.md 作为动态上下文热更新通道。但实验 1-5 只验证了 V0（`--print -p` 一次性模式）。V1 长驻进程是否每轮重读 CLAUDE.md 是未验证的假设。

### 8.2 实验环境

- 模式：`--print --input-format stream-json --output-format stream-json --session-id <uuid>`
- Agent CWD：`/tmp/agenthub/agents/exp6-test/`
- 初始 CLAUDE.md 标记：`V1-INITIAL`

### 8.3 实验步骤

1. 创建 Agent CWD + CLAUDE.md（`V1-INITIAL`）
2. 启动 V1 CLI 进程（`cwd=CWD`）
3. Turn 1：stdin JSONL 询问 CLAUDE.md 版本标记 → Agent 回答 `V1-INITIAL` ✅
4. 修改 CLAUDE.md：`V2-UPDATED-AFTER-TURN1` + 新增「群聊上下文」段（含群成员和任务看板）
5. Turn 2：stdin JSONL 询问版本标记和群聊上下文

### 8.4 实验结果

| 轮次 | Agent 回答 |
|------|-----------|
| Turn 1 | `V1-INITIAL` |
| Turn 2 | `1) V1-INITIAL  2) 没有群聊上下文段。` |

Turn 2 仍然看到旧版本，且明确表示没有新增的「群聊上下文」段。

### 8.5 结论

**CLI 在 V1 长驻模式下，spawn 时读取一次 CLAUDE.md 并缓存到 `<system-reminder>` 中。后续轮次不重新读取文件。CLAUDE.md 不能作为动态上下文的热更新通道。**

### 8.6 方法论检查：--print 对照实验

实验 6 使用了 `--print` 标志（V0 输出模式）。为排除 `--print` 对行为的潜在影响，补做对照实验：去掉 `--print`，使用纯 stream-json 命令（对齐 `_spawn_long()` 的实际命令）。

**对照命令**：`claude --input-format stream-json --output-format stream-json --verbose --permission-mode acceptEdits --max-turns 5 --session-id <uuid>`

| 轮次 | 对照实验回答 |
|------|-------------|
| Turn 1 | `V1-INITIAL-NO-PRINT` |
| Turn 2 | `1) V1-INITIAL-NO-PRINT 2)没有` |

**结论一致**：`--print` 不影响 CLAUDE.md 缓存行为。V1 长驻模式下 spawn 时缓存，后续轮次不重读。

### 8.7 设计与退路

"SP 永不变 + CLAUDE.md 热更新"方案不成立。两条退路：
- **退路 A**：SP 版本号触发重 spawn。kill 旧进程 + `--resume` 起新进程，新进程读取新的 CLAUDE.md。需要实验 8 验证。
- **退路 B**：只用 V0 模式。每条消息 spawn 新进程，天然读取最新文件，但丢失跨轮上下文窗口。

---

## 九、实验 7：V1 长驻模式下 Agent 运行时写入 memory 的可见性

### 9.1 实验目的

验证两个问题：
1. Agent 按绝对路径（`~/.claude/projects/.../memory/`）能否成功写入 memory 文件
2. 写入后，同一 session 的下轮对话中，CLI 是否通过 `<system-reminder>` 注入新写入的记忆

### 9.2 实验环境

- Agent CWD：`/tmp/agenthub/agents/exp7-test/`
- CLI memory 路径：`~/.claude/projects/-tmp-agenthub-agents-exp7-test/memory/`
- SP 中包含 `# Memory` 指令段，路径为上述绝对路径
- 模式：`--input-format stream-json --session-id <uuid>`

### 9.3 实验步骤

1. 创建 Agent CWD + CLAUDE.md
2. 启动 V1 CLI 进程，SP 包含 Memory 指令
3. Turn 1：要求 Agent 写一条记忆到 `{cli_memory_path}test-exp7.md` + 更新 MEMORY.md
4. 检查文件系统（不依赖 Agent 回答）
5. Turn 2：询问 Agent 是否在 `<system-reminder>` 中看到该记忆

### 9.4 实验结果

**文件系统验证**（Turn 1 完成后）：

| 文件 | 状态 | 内容 |
|------|:---:|------|
| `test-exp7.md` | ✅ 已创建 | frontmatter + 正文 |
| `MEMORY.md` | ✅ 已创建 | 正确的索引行 |

Agent 能够按绝对路径写入 memory 文件，格式正确。

**Turn 2 Agent 回答**：`没有。`

### 9.5 结论

1. **Agent 按绝对路径写 memory**：✅ 可行
2. **写入后同 session 可见**：❌ 不可见。CLI spawn 时缓存 MEMORY.md 到 `<system-reminder>`，运行时写入的新记忆在当前 session 不可见。下次 spawn 才可见。

---

## 十、实验 8（关键）：kill + --resume 后 CLAUDE.md 是否重读

### 10.1 实验目的

验证退路 A 的核心假设：杀掉 V1 进程后用 `--resume` 恢复，新进程是否读取最新的 CLAUDE.md 和 MEMORY.md，以及对话历史是否完整恢复。

### 10.2 实验环境

- Agent CWD：`/tmp/agenthub/agents/exp8-test/`
- 初始 CLAUDE.md 标记：`V1-BEFORE-KILL`
- 模式：`--input-format stream-json --session-id <uuid>`（Phase 1）→ kill → `--resume <uuid>`（Phase 3）
- 对话历史验证：在 Phase 1 中写入秘密暗号 `BLUE-FALCON-42`

### 10.3 实验步骤

1. 创建 Agent CWD + CLAUDE.md（`V1-BEFORE-KILL`）
2. Phase 1：启动 V1 CLI（`--session-id`），Turn 1 告知秘密暗号 `BLUE-FALCON-42`
3. Phase 2：kill 进程。修改 CLAUDE.md 为 `V2-AFTER-KILL`，新增群聊上下文（群成员 X/Y/Z + 任务「重构支付模块」）
4. Phase 3：`--resume` 起新进程
5. Turn 2：询问 CLAUDE.md 版本标记
6. Turn 3：询问秘密暗号（验证对话历史恢复）
7. Turn 4：询问群聊上下文（验证新增内容被注入）

### 10.4 实验结果

| 测试项 | Turn | 回答 | 结果 |
|--------|------|------|:---:|
| CLAUDE.md 版本 | Turn 2 | `V2-AFTER-KILL` | ✅ 读到最新 |
| 对话历史恢复 | Turn 3 | `BLUE-FALCON-42` | ✅ 完整恢复 |
| 新增群聊上下文 | Turn 4 | `有，任务：重构支付模块` | ✅ 正确注入 |

### 10.5 结论

**退路 A 的完整假设链全部成立：**

```
上下文变更 → 更新 CLAUDE.md → SP hash 变化
→ _acquire_with_sp_guard 检测到变化
→ kill 旧进程 → --resume 起新进程
→ 新进程读取最新 CLAUDE.md ✅
→ 对话历史恢复 ✅
→ 新写入的 memory 文件被注入 ✅
```

**成本**：重 spawn ~1-2 秒，只有在上下文确实变化时才触发。大多数轮次（上下文不变）享受 V1 长驻进程的低延迟。

---

## 十一、实验汇总与设计影响

### 11.1 全部实验结论

| # | 实验 | 结论 | 日期 |
|----|------|------|------|
| 1 | 默认模式 memory 注入 | CLI 有完整 `# Memory` 段 + MEMORY.md 注入 | 05-30 |
| 2 | `--system-prompt` 模式 | 人格被替换，`# Memory` 指令消失，`<system-reminder>` 保留 | 05-30 |
| 3 | `--append-system-prompt` | 人格保留，记忆系统完整，但身份被稀释 | 05-30 |
| 4 | Memory 目录路径 | 跟 CWD 走，不同 CWD 天然隔离 | 05-30 |
| 5 | CLI 工具能力 | `--system-prompt` 下工具仍可用，但不会主动写记忆 | 05-30 |
| 6 | V1 CLAUDE.md 热重载 | ❌ spawn 时缓存，同进程不重读 | 05-30 |
| 6b | 同上（无 `--print` 对照） | ❌ 去掉 `--print` 结论一致 | 05-30 |
| 7 | V1 运行时写 memory 可见性 | ✅ 可写入，❌ 同 session 不可见 | 05-30 |
| 8 | kill + `--resume` 重读 | ✅ CLAUDE.md 重读 + 对话历史恢复 | 05-30 |

### 11.2 对设计的关键修正

| 设计假设 | 实验结论 | 修正方向 |
|---------|---------|---------|
| CLAUDE.md 每轮热更新 | ❌ spawn 时缓存 | SP 版本号触发重 spawn（退路 A） |
| runtime 写 memory 即时可见 | ❌ 下次 spawn 可见 | 可接受：下次 spawn 是几秒到几分钟的事 |
| SP 永不变 | ❌ 需要变（版本号） | SP 包含上下文版本 hash，变化时触发重 spawn |

### 11.3 更新后的开放问题

| # | 问题 | 状态 |
|---|------|:---:|
| Q1 | Agent CWD 生命周期？ | 开放 |
| Q2 | Memory 指令段格式？ | 开放 |
| Q3 | CLAUDE.md 能否作为热更新通道？ | **已关闭** ❌ |
| Q4 | `/tmp/agenthub/` 多实例部署？ | 开放 |
| Q5 | runtime 写 memory 同 session 可见？ | **已关闭** ❌ |
| Q6 | `--resume` 后是否重读 CLAUDE.md？ | **已关闭** ✅ |

---

> **下一步**：
> 1. 基于实验 8 结论更新 `memory-system-design-v1.md`：SP 版本号重 spawn 方案替代 CLAUDE.md 热更新
> 2. Phase A 基础设施（AgentFileManager + CWD + Memory 指令 + SP 版本号机制）可推进
> 3. 实验 9（`--resume` 后对话历史 compaction 前后完整度，可选）延后
