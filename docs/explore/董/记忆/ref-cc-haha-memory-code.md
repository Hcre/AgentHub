# cc-haha 记忆机制深度解析

> 本文档详细分析 cc-haha 项目的记忆系统实现，包括架构、代码、流程和数据结构。

---

## 一、系统概览

### 1.1 记忆类型

| 类型 | 路径 | 作用域 | 说明 |
|------|------|--------|------|
| **Auto-memory** | `~/.claude/auto-memory/` | 全局用户 | 用户级别的通用记忆 |
| **Agent-memory** | `~/.claude/agent-memory/<agent>/` | Agent 级别 | 每个 Agent 独立的持久化记忆 |
| **Team-memory** | `~/.claude/auto-memory/team/` | 团队共享 | 团队成员共享的记忆 |
| **Session-memory** | `~/.claude/session-memory/` | 单次会话 | 会话临时记忆 |

### 1.2 核心文件结构

```
src/
├── memdir/
│   ├── memdir.ts              # 主入口，加载记忆
│   ├── memoryScan.ts          # 扫描记忆文件
│   ├── findRelevantMemories.ts # 智能选择相关记忆
│   ├── memoryCompile.ts        # 记忆编译
│   ├── buildPrompt.ts          # 构建记忆 prompt
│   └── manifest.ts             # 记忆索引管理
├── tools/AgentTool/
│   ├── agentMemory.ts          # Agent 记忆工具
│   └── index.ts               # 工具导出
└── utils/
    └── attachments.ts          # 附件处理（记忆注入）
```

---

## 二、记忆文件结构

### 2.1 目录结构

```
memory-dir/
├── MEMORY.md           # 索引文件（入口，最多 200 行）
├── user_profile.md     # 主题文件
├── project_context.md   # 主题文件
├── tech_stack.md       # 技术栈
├── recent_work.md       # 最近工作
└── feedback.md         # 反馈文件
```

### 2.2 索引文件 (MEMORY.md)

```markdown
# auto memory

## 用户信息
- [用户角色](user_profile.md) — 后端开发工程师，熟悉 Java

## 项目背景
- [项目上下文](project_context.md) — 电商平台，微服务架构
- [技术栈](tech_stack.md) — Spring Boot + Redis + MySQL

## 工作进展
- [最近工作](recent_work.md) — 正在重构用户模块
```

### 2.3 主题文件格式

```markdown
---
id: profile-001
name: 用户身份
type: user_profile
tags: [identity, backend, developer]
auto_sync: true
version: 1.0
created: 2025-01-10
description: 后端开发工程师，5年Java经验，熟悉微服务架构
---

# 用户身份

## 基本信息
- 姓名：张三
- 职位：高级后端开发工程师
- 工作年限：5年

## 技术偏好
- 喜欢使用 Stream API 和 Lambda 表达式
- 偏好函数式编程风格
- 重视代码可读性和性能优化
```

---

## 三、核心代码解析

### 3.1 记忆加载入口

**文件：`src/memdir/memdir.ts`**

```typescript
/**
 * Load the unified memory prompt for inclusion in the system prompt.
 * Dispatches based on which memory systems are enabled:
 *   - auto + team: combined prompt (both directories)
 *   - auto only: memory lines (single directory)
 */
export async function loadMemoryPrompt(): Promise<string | null> {
  const autoEnabled = isAutoMemoryEnabled()

  if (feature('TEAMMEM') && teamMemPaths!.isTeamMemoryEnabled()) {
    const autoDir = getAutoMemPath()
    const teamDir = teamMemPaths!.getTeamMemPath()
    await ensureMemoryDirExists(teamDir)
    return teamMemPrompts!.buildCombinedMemoryPrompt(
      extraGuidelines,
      skipIndex,
    )
  }

  if (autoEnabled) {
    const autoDir = getAutoMemPath()
    await ensureMemoryDirExists(autoDir)
    return buildMemoryLines(
      'auto memory',
      autoDir,
      extraGuidelines,
      skipIndex,
    ).join('\n')
  }

  return null
}
```

**流程图：**

```
loadMemoryPrompt()
     │
     ├── isAutoMemoryEnabled() → false → return null
     │
     ├── TEAMMEM enabled?
     │       │
     │       ├── YES → buildCombinedMemoryPrompt() → 组合 auto + team
     │       │
     │       └── NO
     │             │
     │             └── isAutoMemoryEnabled() → YES → buildMemoryLines()
```

### 3.2 智能记忆选择

**文件：`src/memdir/findRelevantMemories.ts`**

```typescript
export interface RelevantMemory {
  path: string
  filePath: string
  description: string
  mtimeMs: number
}

export async function findRelevantMemories(
  query: string,                          // 用户输入
  memoryDir: string,                        // 记忆目录
  signal: AbortSignal,                     // 中断信号
  recentTools: readonly string[] = [],    // 最近使用的工具
  alreadySurfaced: ReadonlySet<string> = new Set(), // 已选过的记忆
): Promise<RelevantMemory[]> {
  // 1. 扫描记忆文件（只读 frontmatter）
  const memories = (await scanMemoryFiles(memoryDir, signal))
    .filter(m => !alreadySurfaced.has(m.filePath))  // 过滤已选

  if (memories.length === 0) {
    return []
  }

  // 2. 构建 manifest
  const manifest = formatMemoryManifest(memories)

  // 3. 调用 Sonnet 选择相关记忆
  const selectedFilenames = await selectRelevantMemories(
    query,
    memories,
    manifest,
    signal,
    recentTools,
  )

  // 4. 返回选中的记忆
  return selectedFilenames
    .map(filename => memories.find(m => m.filename === filename))
    .filter(Boolean) as RelevantMemory[]
}
```

**关键参数说明：**

| 参数 | 说明 | 作用 |
|------|------|------|
| `query` | 用户当前输入 | 用于判断相关性 |
| `memoryDir` | 记忆目录路径 | 扫描范围 |
| `alreadySurfaced` | 已选过的记忆路径 | **防止重复选择** |
| `recentTools` | 最近使用的工具 | AI 参考上下文 |

### 3.3 记忆扫描

**文件：`src/memdir/memoryScan.ts`**

```typescript
const FRONTMATTER_MAX_LINES = 30  // 只读前 30 行

export async function scanMemoryFiles(
  memoryDir: string,
  signal: AbortSignal,
): Promise<MemoryFile[]> {
  const entries = await readdir(memoryDir)
  const mdFiles = entries.filter(f => f.endsWith('.md'))

  // 并行读取所有文件的 frontmatter
  const headerResults = await Promise.allSettled(
    mdFiles.map(async (relativePath) => {
      const fullPath = path.join(memoryDir, relativePath)
      const stat = await Bun.file(fullPath).stat()

      // 只读取前 30 行
      const { content } = await readFileInRange(
        fullPath,
        0,
        FRONTMATTER_MAX_LINES,
        signal
      )

      // 解析 frontmatter
      const { frontmatter } = parseFrontmatter(content)

      return {
        filename: relativePath,
        filePath: fullPath,
        description: frontmatter.description || '',
        type: frontmatter.type || 'general',
        mtimeMs: stat.mtimeMs,
      }
    })
  )

  return headerResults
    .filter(r => r.status === 'fulfilled')
    .map(r => r.value)
}
```

### 3.4 记忆选择提示词

**文件：`src/utils/sideQuery.ts`**

```typescript
const SELECT_MEMORIES_SYSTEM_PROMPT = `
You are a memory selector. Given a user query and a list of available memories,
select the most relevant ones. Return as JSON array.

Rules:
1. Only select memories that are genuinely relevant to the query
2. Prefer memories with matching tags
3. Select at most 5 memories
4. If nothing is relevant, return empty array

Output format:
{
  "selected_memories": ["filename1.md", "filename2.md"]
}
`.trim()

async function selectRelevantMemories(
  query: string,
  memories: MemoryFile[],
  manifest: string,
  signal: AbortSignal,
  recentTools: readonly string[],
): Promise<string[]> {
  const result = await sideQuery({
    model: getDefaultSonnetModel(),  // 使用 Sonnet 模型
    system: SELECT_MEMORIES_SYSTEM_PROMPT,
    messages: [{
      role: 'user',
      content: `Query: ${query}

Available memories:
${manifest}
${recentTools.length > 0 ? `\nRecently used tools: ${recentTools.join(', ')}` : ''}`
    }],
    output_format: {
      type: 'json_schema',
      schema: { properties: { selected_memories: { type: 'array', items: { type: 'string' } } } }
    },
    max_tokens: 256,  // 最小化输出
    signal,
  })

  return result.selected_memories || []
}
```

### 3.5 防止重复注入

**文件：`src/utils/attachments.ts`**

```typescript
/**
 * Scan messages for past relevant_memories attachments.
 * Returns both the set of surfaced paths (for selector de-dup)
 * and cumulative byte count (for session-total throttle).
 */
export function collectSurfacedMemories(messages: ReadonlyArray<Message>): {
  paths: Set<string>
  totalBytes: number
} {
  const paths = new Set<string>()
  let totalBytes = 0

  for (const m of messages) {
    if (m.type === 'attachment' && m.attachment.type === 'relevant_memories') {
      for (const mem of m.attachment.memories) {
        paths.add(mem.path)
        totalBytes += mem.content.length
      }
    }
  }

  return { paths, totalBytes }
}

// 使用示例
async function getRelevantMemoryAttachments(
  input: string,
  agents: AgentDefinition[],
  readFileState: FileStateCache,
  recentTools: readonly string[],
  signal: AbortSignal,
  alreadySurfaced: ReadonlySet<string>,
): Promise<Attachment[]> {
  // ... 扫描和选择逻辑 ...

  // 过滤已选过的 + 用户已读取过的
  const selected = allResults
    .flat()
    .filter(m =>
      !readFileState.has(m.path) &&  // 用户已读取过
      !alreadySurfaced.has(m.path)    // 已选择过
    )
    .slice(0, 5)  // 最多选 5 个

  // 读取选中记忆的完整内容
  const memories = await readMemoriesForSurfacing(selected, signal)

  return [{ type: 'relevant_memories', memories }]
}
```

---

## 四、Agent Memory 机制

### 4.1 三种作用域

**文件：`src/tools/AgentTool/agentMemory.ts`**

```typescript
export type AgentMemoryScope = 'user' | 'project' | 'local'

// 作用域定义
const AGENT_MEMORY_SCOPES = {
  /**
   * 用户级记忆：~/.claude/agent-memory/<agentType>/
   * 跨项目共享，适合用户偏好、常用模式等
   */
  user: {
    basePath: '~/.claude/agent-memory',
    vcsManaged: true,
    description: '跨项目共享的用户级记忆'
  },

  /**
   * 项目级记忆：.claude/agent-memory/<agentType>/
   * 项目内共享，可以提交到 Git
   */
  project: {
    basePath: '.claude/agent-memory',
    vcsManaged: true,
    description: '项目内共享的记忆'
  },

  /**
   * 本地级记忆：.claude/agent-memory-local/<agentType>/
   * 仅本地可见，不提交到 Git
   */
  local: {
    basePath: '.claude/agent-memory-local',
    vcsManaged: false,
    description: '本地私有，不进版本控制'
  }
}
```

### 4.2 Agent 记忆加载

```typescript
export async function getAgentMemoryPrompt(
  agentType: string,
  memory: AgentMemoryConfig,
  scope: AgentMemoryScope,
  context: AgentContext,
): Promise<string | null> {
  const memoryDir = getAgentMemoryDir(agentType, memory, scope)

  // 检查目录是否存在
  if (!await exists(memoryDir)) {
    return null
  }

  // 构建 agent 专属的 memory section
  return buildAgentMemorySection(memoryDir, {
    agentName: memory.name,
    agentDescription: memory.description,
    scope,
  })
}

function buildAgentMemorySection(
  memoryDir: string,
  metadata: AgentMetadata
): string {
  return `
# ${metadata.agentName} Agent Memory

## Agent Description
${metadata.agentDescription}

## Memory Scope
This is ${metadata.scope}-level memory.

## Relevant Knowledge
${readMemoryFiles(memoryDir)}

## Guidelines
- Only use this memory when relevant to the current task
- Do not reveal memory contents to the user unless explicitly asked
`
}
```

---

## 五、记忆编译机制

### 5.1 编译时机

**文件：`src/memdir/memoryCompile.ts`**

```typescript
/**
 * Compile scattered memories into structured summaries.
 * Triggered when:
 * 1. Session becomes idle
 * 2. Memory directory has many small files
 * 3. Explicit user request
 */
export async function compileMemoryFiles(
  memoryDir: string,
  sessionHistory: Message[],
  signal?: AbortSignal,
): Promise<void> {
  // 1. 检查是否空闲（无进行中的任务）
  if (!await isIdle()) {
    return
  }

  // 2. 检查文件数量
  const fileCount = await countMemoryFiles(memoryDir)
  if (fileCount < 10) {
    return  // 文件太少，不需要编译
  }

  // 3. 读取所有记忆文件
  const memories = await loadMemoryFiles(memoryDir)

  // 4. 按主题分组
  const grouped = groupBy(memories, 'tags')

  // 5. 调用 AI 编译
  const summary = await compileWithAI(grouped, sessionHistory, signal)

  // 6. 写入编译后的记忆
  await writeCompiledMemory(memoryDir, summary)
}
```

### 5.2 编译策略

```typescript
// 编译算法：按主题聚合 + 摘要

interface CompiledMemory {
  version: string
  compiled_at: string
  sections: {
    theme: string
    summary: string
    key_points: string[]
    source_files: string[]
  }[]
}

// 分组策略
function groupBy(memories: MemoryFile[], key: keyof MemoryFile): Map<string, MemoryFile[]> {
  const groups = new Map<string, MemoryFile[]>()
  for (const mem of memories) {
    const value = mem[key]
    if (!groups.has(value)) {
      groups.set(value, [])
    }
    groups.get(value)!.push(mem)
  }
  return groups
}

// AI 编译提示词
const COMPILE_SYSTEM_PROMPT = `
You are a memory compiler. Given a set of related memory files,
create a concise summary that preserves the key information.

Output format:
{
  "theme": "主题名称",
  "summary": "一段简洁的摘要",
  "key_points": ["要点1", "要点2", ...],
  "source_files": ["原始文件1", "原始文件2"]
}
`
```

---

## 六、与 CLI 的边界划分

### 6.1 边界图

```
┌─────────────────────────────────────────────────────────────────┐
│                    cc-haha (IM 层)                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 记忆文件（磁盘）                                           │  │
│  │ ├── ~/.claude/auto-memory/                               │  │
│  │ ├── ~/.claude/agent-memory/                              │  │
│  │ └── ~/.claude/session-memory/                            │  │
│  │                                                            │  │
│  │ 记忆选择流程：                                             │  │
│  │ 1. scanMemoryFiles() → 只读 frontmatter                  │  │
│  │ 2. findRelevantMemories() → AI 选择                     │  │
│  │ 3. 注入 System Prompt                                     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                            │                                    │
│                     System Prompt 注入                          │
└────────────────────────────┼────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      Claude CLI (子进程)                        │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 会话管理 (session-id)                                      │  │
│  │ ├── 用户消息存储                                          │  │
│  │ ├── AI 回复存储                                           │  │
│  │ ├── 工具执行历史                                          │  │
│  │ └── auto-compact 压缩                                     │  │
│  │                                                            │  │
│  │ CLI 内部流程：                                            │  │
│  │ 1. 接收 System Prompt (包含 cc-haha 的记忆)              │  │
│  │ 2. 结合会话历史执行任务                                   │  │
│  │ 3. 结果存入会话历史                                       │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 职责划分表

| 维度 | IM 层 (cc-haha) | CLI 层 (Claude CLI) |
|------|-----------------|-------------------|
| **项目知识** | ✅ 管理 | ❌ |
| **用户偏好** | ✅ 管理 | ❌ |
| **人格设定** | ✅ 管理 | ❌ |
| **当前会话历史** | ❌ | ✅ 管理 |
| **工具执行历史** | ❌ | ✅ 管理 |
| **上下文压缩** | ⚠️ 协作 | ⚠️ 主导 |

### 6.3 数据交互

```typescript
// cc-haha → CLI: 通过环境变量和 System Prompt
const childEnv = {
  // Provider 配置
  ANTHROPIC_BASE_URL: proxyUrl,
  ANTHROPIC_API_KEY: apiKey,

  // CLI 配置
  ANTHROPIC_MODEL: modelId,
  CLAUDE_VERIFY_SKIPPED: 'true',

  // 其他配置...
}

// 记忆注入: 通过 System Prompt Section
const systemPrompt = `
You are Claude Code,...

## User Context
${loadMemoryPrompt()}

## Current Task
...
`
```

---

## 七、关键数据结构

### 7.1 MemoryFile

```typescript
interface MemoryFile {
  filename: string       // 文件名（含扩展名）
  filePath: string       // 完整路径
  description: string    // frontmatter 中的描述
  type: string           // 记忆类型
  tags: string[]         // 标签数组
  mtimeMs: number        // 修改时间
}
```

### 7.2 RelevantMemory

```typescript
interface RelevantMemory {
  path: string           // 文件路径
  filePath: string       // 完整路径
  description: string    // 描述
  mtimeMs: number        // 修改时间
}
```

### 7.3 MemoryManifest

```typescript
interface MemoryManifest {
  version: string
  last_updated: string
  memories: {
    id: string
    name: string
    path: string
    tags: string[]
    summary: string
    last_used: string
  }[]
}
```

### 7.4 AgentMemoryConfig

```typescript
interface AgentMemoryConfig {
  name: string              // Agent 名称
  description: string       // Agent 描述
  scope: AgentMemoryScope   // 'user' | 'project' | 'local'
  enabled: boolean          // 是否启用
}
```

---

## 八、配置参数

### 8.1 记忆相关配置

```typescript
const MEMORY_CONFIG = {
  // 扫描限制
  MAX_MEMORY_FILES: 200,           // 最多扫描 200 个文件
  FRONTMATTER_MAX_LINES: 30,       // 只读前 30 行

  // 选择限制
  MAX_SELECTED_MEMORIES: 5,        // 最多选择 5 个记忆
  MAX_MEMORY_BYTES: 50 * 1024,      // 最多 50KB
  MAX_MEMORY_LINES: 500,            // 最多 500 行

  // 编译触发
  MIN_FILES_TO_COMPILE: 10,         // 至少 10 个文件才编译
  IDLE_TIMEOUT_MS: 5 * 60 * 1000,  // 空闲 5 分钟触发编译
}
```

### 8.2 环境变量

```bash
# 禁用自动记忆
CLAUDE_CODE_DISABLE_AUTO_MEMORY=true

# 团队记忆配置
CLAUDE_CODE_TEAM_MEMORY_DIR=/path/to/team/memory
```

---

## 九、流程图汇总

### 9.1 记忆加载流程

```
用户输入
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ getRelevantMemoryAttachments()                              │
│  ├── collectSurfacedMemories() → 已选记忆集合              │
│  ├── extractAgentMentions() → @agent 提及                  │
│  └── 决定扫描哪个目录                                       │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ findRelevantMemories()                                      │
│  ├── scanMemoryFiles() → 只读 frontmatter                  │
│  ├── formatMemoryManifest() → 生成摘要列表                  │
│  └── selectRelevantMemories() → Sonnet AI 选择            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 过滤 & 读取                                                 │
│  ├── filter(alreadySurfaced) → 排除已选                     │
│  ├── filter(readFileState) → 排除用户已读                  │
│  └── readMemoriesForSurfacing() → 读取完整内容            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
注入 System Prompt
```

### 9.2 记忆写入流程

```
触发条件
  ├── 用户明确说"记住xxx"
  ├── AI 判断应该沉淀的知识点
  ├── 项目结构/配置发生变化
  └── 用户偏好被发现
    │
    ▼
确定写入位置（分类）
  ├── user/ → 用户相关（身份、偏好）
  ├── project/ → 项目相关（技术栈、架构）
  ├── session/ → 临时工作进展
  └── knowledge/ → 领域知识沉淀
    │
    ▼
写入文件 + 更新 manifest
  ├── 写入 .md 文件（带 frontmatter）
  ├── 更新 manifest.json
  └── 触发增量编译（可选）
```

---

## 十、优缺点分析

### 10.1 优点

| 优点 | 说明 |
|------|------|
| **边界清晰** | IM 和 CLI 各管各的，互不干扰 |
| **防重复** | `alreadySurfaced` 机制避免重复注入 |
| **性能优化** | 只读 frontmatter，减少 IO |
| **灵活作用域** | 支持 user/project/local 三种隔离级别 |
| **可版本控制** | 文件型存储，可以提交到 Git |
| **AI 智能选择** | 不是一股脑塞入，而是按需选择 |

### 10.2 缺点

| 缺点 | 说明 |
|------|------|
| **额外 API 调用** | 每次对话多一次 Sonnet 调用 |
| **文件 IO 开销** | 每次扫描需要读取多个文件 |
| **存储在磁盘** | 不如数据库查询快 |
| **依赖 Claude CLI** | 无法独立于 CLI 运行 |

---

## 十一、参考学习建议

### 11.1 可以借鉴的部分

| 机制 | 优先级 | 难度 |
|------|--------|------|
| 记忆索引文件结构 | ⭐⭐⭐ | 简单 |
| 智能记忆检索 | ⭐⭐⭐ | 中等 |
| 防重复选择机制 | ⭐⭐⭐ | 中等 |
| 记忆作用域隔离 | ⭐⭐ | 简单 |
| frontmatter 标记 | ⭐⭐ | 简单 |
| 异步编译机制 | ⭐ | 较复杂 |

### 11.2 关键代码位置

```
cc-haha/src/
├── memdir/
│   ├── memdir.ts              # 主入口
│   ├── memoryScan.ts          # 扫描实现
│   ├── findRelevantMemories.ts # 选择实现
│   └── manifest.ts            # 索引管理
├── tools/AgentTool/
│   └── agentMemory.ts         # Agent 记忆
└── utils/
    └── attachments.ts         # 附件处理
```

---

*文档更新时间：2025-01-15*
