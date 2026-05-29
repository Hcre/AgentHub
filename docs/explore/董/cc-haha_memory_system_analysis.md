# cc-haha 记忆机制深度分析

## 1. 概述

cc-haha 项目构建了一套**完整的文件型持久化记忆系统**，并非全权委托给 CLI。以下是核心发现：

> **关键结论**：cc-haha 实现了多层级、智能检索、文件持久化的记忆系统，通过 `loadMemoryPrompt()` 将记忆注入到发送给 CLI 的 prompt 中，实现了 IM 层对记忆的自主管理。

---

## 2. 记忆类型与层级

### 2.1 记忆类型总览

| 记忆类型 | 存储位置 | 作用域 | 说明 |
|---------|---------|--------|------|
| **Auto-memory** | `~/.claude/auto-memory/` | 全局 | 用户级别的通用持久化记忆 |
| **Agent-memory** | `~/.claude/agent-memory/<agent>/` | Agent 级别 | 每个 Agent 独立的持久化记忆 |
| **Team-memory** | `~/.claude/auto-memory/team/` | 团队共享 | 团队成员共享的记忆 |
| **Session-memory** | `~/.claude/session-memory/` | 单次会话 | 会话临时记忆 |

### 2.2 Agent Memory Scope 选项

```typescript
// src/tools/AgentTool/agentMemory.ts
export type AgentMemoryScope = 'user' | 'project' | 'local'

// 三种作用域：
// - 'user':     ~/.claude/agent-memory/<agentType>/     (跨项目共享)
// - 'project':  .claude/agent-memory/<agentType>/        (项目私有，可 VCS)
// - 'local':    .claude/agent-memory-local/<agentType>/  (本地私有，不进 VCS)
```

---

## 3. 核心数据结构

### 3.1 记忆目录结构

```
memory-dir/
├── MEMORY.md           # 索引文件（入口，最多 200 行，25KB）
├── user_profile.md     # 主题文件
├── project_context.md   # 主题文件
├── feedback.md         # 反馈记忆
└── reference.md       # 参考文档
```

### 3.2 记忆文件格式（Frontmatter）

```yaml
---
name: 用户角色信息
description: 用户是后端开发工程师，熟悉 Python/Go
type: user          # user | feedback | project | reference
tags: [开发者, 后端]
last_accessed: 2024-01-15
---

# 用户角色信息

用户是某科技公司的后端开发工程师，技术栈包括：
- Python (Django, FastAPI)
- Go (Gin, gRPC)
- 熟悉微服务架构
```

### 3.3 关键类型定义

```typescript
// src/memdir/memoryTypes.ts

// 记忆文件头信息
interface MemoryHeader {
  filename: string
  name: string
  description: string
  type: 'user' | 'feedback' | 'project' | 'reference'
  tags: string[]
  last_accessed: string
  mtimeMs: number
  filePath: string
}

// 检索结果
interface RelevantMemory {
  path: string
  mtimeMs: number
}

// 入口截断结果
interface EntrypointTruncation {
  content: string
  lineCount: number
  byteCount: number
  wasLineTruncated: boolean
  wasByteTruncated: boolean
}
```

---

## 4. 核心模块与职责

### 4.1 模块清单

| 模块路径 | 职责 |
|---------|------|
| `src/memdir/memdir.ts` | 记忆目录管理、Prompt 构建、入口文件读取 |
| `src/memdir/findRelevantMemories.ts` | 智能记忆检索（使用 Sonnet 模型） |
| `src/memdir/memoryScan.ts` | 记忆文件扫描与解析 |
| `src/memdir/memoryTypes.ts` | 记忆类型定义与提示词模板 |
| `src/memdir/paths.ts` | 记忆路径配置 |
| `src/memdir/teamMemPaths.ts` | 团队记忆路径管理 |
| `src/tools/AgentTool/agentMemory.ts` | Agent 记忆的 Scope 管理 |

### 4.2 模块关系图

```
┌─────────────────────────────────────────────────────────────────┐
│                        System Prompt                             │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  loadMemoryPrompt() → Memory Section                      │  │
│  │  ├── MEMORY.md 索引内容                                    │  │
│  │  ├── 行为指导（如何保存/检索记忆）                         │  │
│  │  └── 历史上下文检索指导                                     │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────┴─────────────────────────────┐
│                    memdir.ts                                 │
│  ┌────────────────┐  ┌────────────────┐                    │
│  │ buildMemoryPrompt() │  │ loadMemoryPrompt() │            │
│  └────────┬───────┘  └────────┬───────┘                    │
│           │                     │                            │
│  ┌────────▼─────────────────────▼───────┐                    │
│  │         记忆目录管理                      │                 │
│  │  - ensureMemoryDirExists()             │                 │
│  │  - truncateEntrypointContent()         │                 │
│  │  - buildMemoryLines()                  │                 │
│  └───────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────┴─────────────────────────────┐
│              AgentTool / CLI 子进程                          │
│  Claude CLI 读取记忆 → 执行任务 → 可能更新记忆               │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 数据流转与处理流程

### 5.1 记忆加载流程（会话启动时）

```
1. IM 用户发起会话
         │
         ▼
2. Desktop Server 构建 CLI 启动参数
         │
         ▼
3. loadMemoryPrompt() 被调用
         │
         ▼
4. 读取 ~/.claude/auto-memory/MEMORY.md
         │
         ▼
5. 截断处理（最多 200 行，25KB）
         │
         ▼
6. 拼接为 Memory Section
         │
         ▼
7. 注入 System Prompt
         │
         ▼
8. 启动 CLI 子进程
```

### 5.2 记忆检索流程（运行时）

```
1. Agent 处理用户查询
         │
         ▼
2. findRelevantMemories(query, memoryDir)
         │
         ▼
3. scanMemoryFiles() 扫描所有 .md 文件
         │
         ▼
4. 解析 frontmatter，提取 metadata
         │
         ▼
5. sideQuery() 调用 Sonnet 模型选择相关记忆
         │
         ▼
6. 返回 RelevantMemory[] (最多 5 个)
         │
         ▼
7. 加载选中的记忆文件内容
         │
         ▼
8. 注入到当前对话上下文
```

### 5.3 记忆保存流程（运行时）

```
1. Agent 判断需要保存记忆
         │
         ▼
2. 按 frontmatter 格式写入新文件
         │
         ▼
3. 更新 MEMORY.md 索引
         │
         ▼
4. 记忆持久化到文件系统
```

---

## 6. 智能检索机制（findRelevantMemories）

### 6.1 检索算法

```typescript
// src/memdir/findRelevantMemories.ts

const SELECT_MEMORIES_SYSTEM_PROMPT = `You are selecting memories that will be useful
to Claude Code as it processes a user's query. Return a list of filenames for the
memories that will clearly be useful (up to 5).`

async function findRelevantMemories(
  query: string,
  memoryDir: string,
  signal: AbortSignal,
  recentTools: readonly string[] = [],
  alreadySurfaced: ReadonlySet<string> = new Set(),
): Promise<RelevantMemory[]> {
  // 1. 扫描所有记忆文件
  const memories = await scanMemoryFiles(memoryDir, signal)

  // 2. 过滤已展示的记忆
  const filtered = memories.filter(m => !alreadySurfaced.has(m.filePath))

  // 3. 使用 Sonnet 模型选择相关记忆
  const selectedFilenames = await selectRelevantMemories(
    query,
    filtered,
    signal,
    recentTools
  )

  // 4. 返回路径和修改时间
  return selected.map(m => ({ path: m.filePath, mtimeMs: m.mtimeMs }))
}
```

### 6.2 检索特点

| 特性 | 说明 |
|------|------|
| **AI 驱动** | 使用 Sonnet 模型而非简单关键词匹配 |
| **智能去重** | 过滤已展示的记忆，避免重复 |
| **工具感知** | 考虑最近使用的工具，避免重复加载工具文档 |
| **限制数量** | 最多返回 5 个相关记忆，控制上下文长度 |

---

## 7. 与 CLI 的协作模式

### 7.1 记忆注入方式

cc-haha 通过 **System Prompt 注入**的方式将记忆传递给 CLI：

```typescript
// CLI 启动时的 System Prompt 结构
System Prompt = [
  "# Claude Code",
  "You are a helpful coding assistant...",
  "[memory_section]",  // ← 这里注入记忆
  "[tools_section]",
  "[context_section]"
]
```

### 7.2 IM 侧 vs CLI 侧记忆职责

| 维度 | IM 侧 (cc-haha Desktop) | CLI 侧 (Claude Code) |
|------|-------------------------|---------------------|
| **记忆存储** | 管理 `~/.claude/auto-memory/` 目录 | 仅读取和写入 |
| **记忆格式** | 定义 frontmatter 结构 | 遵循格式写入 |
| **会话历史** | 通过 API 获取 CLI 历史 | 存储在 `~/.claude/history.jsonl` |
| **智能检索** | findRelevantMemories() 实现 | 调用检索结果 |

### 7.3 协作流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                      cc-haha Desktop (IM 层)                     │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐  │
│  │  会话管理       │    │  记忆管理       │    │  历史管理       │  │
│  │  - chatId      │    │  - auto-memory │    │  - history     │  │
│  │  - sessionId   │    │  - agent-memory│    │  - JSONL       │  │
│  └───────┬────────┘    └───────┬────────┘    └───────┬────────┘  │
│          │                      │                      │          │
│          └──────────────────────┼──────────────────────┘          │
│                                 │                                   │
│                    ┌─────────────▼─────────────┐                    │
│                    │    loadMemoryPrompt()      │                    │
│                    │    buildSystemPrompt()     │                    │
│                    └─────────────┬─────────────┘                    │
└──────────────────────────────────┼──────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Claude CLI (子进程)                           │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐   │
│  │  执行任务       │    │  读取记忆      │    │  更新记忆      │   │
│  │  - tools       │    │  - MEMORY.md  │    │  - write file │   │
│  │  - reasoning   │    │  - context    │    │  - index      │   │
│  └────────────────┘    └────────────────┘    └────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 8. 入口文件截断机制

### 8.1 截断规则

```typescript
// src/memdir/memdir.ts

export const MAX_ENTRYPOINT_LINES = 200    // 最多 200 行
export const MAX_ENTRYPOINT_BYTES = 25_000 // 最多 25KB

export function truncateEntrypointContent(raw: string): EntrypointTruncation {
  // 1. 行数截断（如果超过 200 行）
  // 2. 字节截断（如果超过 25KB）

  // 追加警告信息
  return {
    content: truncated + "\n\n> WARNING: MEMORY.md is X lines...",
    wasLineTruncated: boolean,
    wasByteTruncated: boolean
  }
}
```

### 8.2 截断原因与解决

- **问题**：LLM 可能写入过多索引导致上下文溢出
- **解决**：
  1. 限制入口文件大小
  2. 提示 LLM 保持索引简洁（每条 < 150 字符）
  3. 详细内容移到主题文件

---

## 9. 团队记忆功能（TEAMMEM）

### 9.1 特性

当 `feature('TEAMMEM')` 启用时，支持团队共享记忆：

```typescript
// src/memdir/teamMemPaths.ts
export function getTeamMemPath(): string {
  return join(getAutoMemPath(), 'team')
}

// 团队记忆可被 VCS 追踪（project scope）
// 团队成员共享同一记忆目录
```

### 9.2 与自动记忆的关系

```
~/.claude/auto-memory/
├── MEMORY.md              # 个人索引
├── user_profile.md        # 个人主题
├── project_context.md     # 个人主题
└── team/                 # 团队共享目录
    ├── MEMORY.md          # 团队索引
    └── coding-standards.md # 团队规范
```

---

## 10. 与会话历史的区别

| 维度 | 记忆 (Memory) | 会话历史 (History) |
|------|--------------|-------------------|
| **存储位置** | `~/.claude/auto-memory/` | `~/.claude/history.jsonl` |
| **内容** | 结构化的知识片段 | 原始对话记录 |
| **生命周期** | 跨会话持久化 | 长期保留但无结构化 |
| **用途** | 长期知识积累 | 上下文延续 |
| **IM 侧可见性** | 通过 API 获取展示 | 通过 API 获取展示 |
| **更新频率** | 按需更新 | 每轮对话追加 |

---

## 11. 总结

### 11.1 cc-haha 记忆系统的优势

1. **文件持久化**：记忆存储在文件系统，重启不丢失
2. **多层级管理**：支持用户、Agent、项目、团队多级记忆
3. **智能检索**：使用 AI 模型选择相关记忆
4. **结构化存储**：frontmatter 格式便于解析和检索
5. **IM 层自主管理**：cc-haha Desktop 不依赖 CLI 实现记忆功能

### 11.2 与"全权委托 CLI"的对比

| 维度 | cc-haha 实际做法 | 完全委托给 CLI |
|------|-----------------|---------------|
| **记忆来源** | cc-haha 管理的 `auto-memory/` + Agent Memory | 仅 CLI 内部处理 |
| **记忆持久化** | 文件系统持久化，可跨会话 | 依赖 CLI 实现 |
| **多 Agent 记忆** | 支持每个 Agent 独立记忆 + 团队共享记忆 | 通常是全局的 |
| **智能检索** | 使用 Sonnet 模型选择相关记忆 | 无或简单关键词匹配 |
| **IM 侧历史** | Desktop 侧通过 API 获取并展示 | 不涉及 |

### 11.3 关键文件索引

| 文件 | 行数 | 核心功能 |
|------|------|---------|
| `src/memdir/memdir.ts` | 500+ | 记忆目录管理、Prompt 构建 |
| `src/memdir/findRelevantMemories.ts` | 142 | 智能记忆检索 |
| `src/memdir/memoryScan.ts` | - | 记忆文件扫描 |
| `src/memdir/memoryTypes.ts` | - | 类型定义与模板 |
| `src/tools/AgentTool/agentMemory.ts` | 177 | Agent 记忆 Scope 管理 |
| `adapters/common/session-store.ts` | - | 会话 ID 映射管理 |
