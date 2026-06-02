# open-multi-agent 项目深度分析报告

> 项目地址：https://github.com/open-multi-agent/open-multi-agent.git
> 分析日期：2026-05-25

---

## 一、项目概述

**open-multi-agent** 是一个面向 TypeScript 后端的多智能体编排框架，核心特点是**目标驱动**：
- 工程师只描述目标（如"创建 REST API"）
- 框架自动将目标拆解为任务 DAG
- 并行执行独立任务
- 最终合成结果

**设计哲学**："工程师只描述目标，不画任务图"

---

## 二、模块清单与职责

### 2.1 核心模块列表

| 模块 | 文件路径 | 核心职责 |
|------|----------|----------|
| **Orchestrator** | `src/orchestrator/orchestrator.ts` | 顶层编排引擎，任务分解、DAG 执行、结果聚合 |
| **Team** | `src/team/team.ts` | Agent 团队管理、消息总线、事件发布 |
| **Agent** | `src/agent/agent.ts` | 单 Agent 生命周期管理、对话历史、状态追踪 |
| **AgentRunner** | `src/agent/runner.ts` | Agent 对话循环引擎，工具调用、上下文管理 |
| **TaskQueue** | `src/task/queue.ts` | 依赖感知的任务队列，状态流转、级联失败 |
| **Scheduler** | `src/orchestrator/scheduler.ts` | 任务-Agent 分配策略 |
| **ToolRegistry** | `src/tool/framework.ts` | 工具注册、Schema 生成 |
| **ToolExecutor** | `src/tool/executor.ts` | 工具执行、结果处理 |
| **SharedMemory** | `src/memory/shared.ts` | Agent 间共享记忆、TTL 支持 |
| **MessageBus** | `src/team/messaging.ts` | Agent 间消息传递、发布订阅 |
| **LLMAdapter** | `src/llm/adapter.ts` | LLM 适配器接口 + 10+ 实现 |

### 2.2 辅助模块

| 模块 | 文件路径 | 职责 |
|------|----------|------|
| **AgentPool** | `src/agent/pool.ts` | 并发控制、MapReduce 执行 |
| **LoopDetector** | `src/agent/loop-detector.ts` | 检测 Agent 死循环 |
| **TextToolExtractor** | `src/tool/text-tool-extractor.ts` | 从文本提取工具调用 |
| **MCP** | `src/mcp.ts` | MCP 协议集成 |

---

## 三、模块间交互与协调运作流程

### 3.1 核心数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           用户调用层                                        │
│                                                                              │
│  orchestrator.runTeam(team, "创建 REST API")                                 │
│  └─ runTeam() → 自动创建 Coordinator Agent                                  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Orchestrator (编排引擎)                               │
│                                                                              │
│  1. isSimpleGoal() 判断是否需要协调者                                        │
│  2. 如果复杂 → 创建临时 Coordinator Agent                                   │
│  3. Coordinator.run() → 目标分解 → 返回 Task[]                              │
│  4. TaskQueue.addBatch() → 构建依赖图                                        │
│  5. Scheduler.autoAssign() → 任务分配到 Agent                               │
│  6. AgentPool.runParallel() → 并行执行就绪任务                              │
│  7. 等待任务完成 → 聚合结果 → 返回 TeamRunResult                            │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │ Agent A │ │ Agent B  │ │ Agent C  │
              │ (task1) │ │ (task2)  │ │ (task3)  │
              └────┬─────┘ └────┬─────┘ └────┬─────┘
                   │             │             │
                   ▼             ▼             ▼
              ┌──────────────────────────────────┐
              │         SharedMemory             │
              │  Agent 间共享中间结果              │
              └──────────────────────────────────┘
                                  │
                                  ▼
              ┌──────────────────────────────────┐
              │         MessageBus               │
              │  Agent 间点对点消息/广播          │
              └──────────────────────────────────┘
```

### 3.2 任务生命周期

```
Task 创建
    │
    ▼
┌─────────┐    dependsOn 全部完成    ┌─────────────┐
│ pending │ ──────────────────────▶ │   ready     │
└─────────┘                         └──────┬──────┘
                                          │
                                          ▼
                               ┌─────────────────────┐
                               │ Scheduler 分配      │
                               │ agent → assigne     │
                               └──────────┬──────────┘
                                          │
                                          ▼
                               ┌─────────────────────┐
                               │   in_progress       │
                               │ AgentPool 执行      │
                               └──────────┬──────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
              ┌──────────┐         ┌──────────┐         ┌──────────┐
              │completed │         │  failed │         │ skipped  │
              └─────┬────┘         └─────┬────┘         └─────┬────┘
                    │                    │                    │
                    ▼                    ▼                    ▼
              unblock 依赖          cascadeFailure        cascadeSkip
```

### 3.3 工具调用流程

```
AgentRunner.run()
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  while (turns < maxTurns):                                  │
│    1. 构建 LLM 请求 (systemPrompt + messages + tools)       │
│    2. LLMAdapter.chat() → 获取响应                          │
│    3. 解析响应中的 ToolUseBlock                              │
│    4. ToolExecutor.execute() 并行执行工具                    │
│    5. ToolResultBlock → 加入 messages                        │
│    6. 循环直到 stop_reason === 'end_turn'                   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
返回 RunResult { messages, output, toolCalls, tokenUsage }
```

---

## 四、场景推理：写一份市场分析报告

### 4.1 用户输入

```
目标: "对新能源汽车市场做一份分析报告，包含行业趋势、竞品分析、用户画像"
```

### 4.2 执行流程

```
阶段 1: 目标评估
────────────────────────────────────────────────────────────
Orchestrator.isSimpleGoal("对新能源汽车市场做一份分析报告...")
  └─ 长度 32 > 200? 否
  └─ 匹配复杂模式? 否
  └─ 结果: 需要协调者 → 创建临时 Coordinator Agent
```

```
阶段 2: 任务分解
────────────────────────────────────────────────────────────
Coordinator Agent 执行:
  systemPrompt: 你是专业分析师，将任务分解为可执行的子任务...
  input: 对新能源汽车市场做一份分析报告...
  
  LLM 思考后输出任务分解 JSON:
  {
    "tasks": [
      { "title": "行业趋势研究", "description": "研究2024-2026年..." },
      { "title": "竞品分析", "dependsOn": ["行业趋势研究"] },
      { "title": "用户画像分析", "dependsOn": ["行业趋势研究"] },
      { "title": "报告撰写", "dependsOn": ["竞品分析", "用户画像分析"] }
    ]
  }
  
  解析为 Task[]:
  Task 1: industry-research (pending)
  Task 2: competitor-analysis (dependsOn: [Task 1])
  Task 3: user-persona (dependsOn: [Task 1])
  Task 4: report-writing (dependsOn: [Task 2, Task 3])
```

```
阶段 3: 任务队列构建
────────────────────────────────────────────────────────────
TaskQueue.addBatch([Task1, Task2, Task3, Task4])

DAG 拓扑排序 (Kahn 算法):
  Task 1 (无依赖) → 立即 ready
  Task 2, Task 3 (依赖 Task 1) → pending (blocked)
  Task 4 (依赖 Task 2, Task 3) → pending (blocked)
```

```
阶段 4: 任务调度
────────────────────────────────────────────────────────────
Scheduler (dependency-first 策略):

首次调度:
  Task 1 → assignee: "researcher"
  
  TaskQueue.emit('task:ready', Task 1)

Task 1 完成:
  TaskQueue.complete("Task 1", result)
  └─ Task 2, Task 3 → unblock → emit('task:ready')
  
  Task 2 → assignee: "analyst-competitor"
  Task 3 → assignee: "analyst-user"
  
  Task 2, Task 3 并行执行 (AgentPool.runParallel)

Task 2, Task 3 完成:
  TaskQueue.complete("Task 2")
  TaskQueue.complete("Task 3")
  └─ Task 4 → unblock → emit('task:ready')
  
  Task 4 → assignee: "writer"
  └─ Coordinator Agent 执行最终聚合
```

```
阶段 5: 结果聚合
────────────────────────────────────────────────────────────
Coordinator Agent 执行最终报告撰写:
  context:
    - Task 1 结果: 行业趋势分析内容
    - Task 2 结果: 竞品分析内容
    - Task 3 结果: 用户画像内容
  
  LLM: 综合以上分析，撰写完整市场分析报告...
  
返回 TeamRunResult:
  {
    success: true,
    agentResults: {
      coordinator: { output: "完整报告内容", ... },
      researcher: { output: "行业趋势...", ... },
      ...
    },
    taskResults: { ... },
    totalTokenUsage: { ... }
  }
```

---

## 五、架构分层图

### 5.1 四层架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Layer 4: 用户入口层                                  │
│                                                                              │
│  OpenMultiAgent.runTeam()    OpenMultiAgent.runAgent()                      │
│  OpenMultiAgent.runTasks()   OpenMultiAgent.createTeam()                    │
│                                                                              │
│  职责: 面向用户的顶级 API， orchestrate 全流程                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Layer 3: 编排层                                     │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │  Orchestrator    │  │  Scheduler       │  │  AgentPool       │         │
│  │                  │  │  - round-robin   │  │  - Semaphore     │         │
│  │  - 任务分解       │  │  - least-busy    │  │  - runParallel   │         │
│  │  - DAG 执行      │  │  - capability    │  │                  │         │
│  │  - 结果聚合      │  │  - dependency    │  │                  │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
│                                                                              │
│  职责: 任务调度、并发控制、流程编排                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Layer 2: Agent 执行层                               │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │  Team            │  │  Agent           │  │  AgentRunner     │         │
│  │                  │  │                  │  │                  │         │
│  │  - AgentConfig[] │  │  - run()         │  │  - 对话循环      │         │
│  │  - MessageBus    │  │  - prompt()      │  │  - 工具调用      │         │
│  │  - SharedMemory  │  │  - stream()      │  │  - 循环检测      │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
│                                                                              │
│  职责: 单个 Agent 的生命周期管理和对话执行                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Layer 1: 基础设施层                                  │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │  LLMAdapter      │  │  ToolRegistry    │  │  SharedMemory    │         │
│  │                  │  │                  │  │                  │         │
│  │  - Anthropic     │  │  - defineTool()  │  │  - MemoryStore   │         │
│  │  - OpenAI        │  │  - 内置工具      │  │  - TTL 支持      │         │
│  │  - Gemini        │  │  - MCP 集成      │  │  - 命名空间      │         │
│  │  - DeepSeek      │  │  - Schema 生成  │  │                  │         │
│  │  - Ollama        │  │                  │  │                  │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                              │
│  │  TaskQueue       │  │  MessageBus      │                              │
│  │                  │  │                  │                              │
│  │  - 依赖图管理     │  │  - Pub/Sub       │                              │
│  │  - 状态流转      │  │  - 消息持久化     │                              │
│  │  - 级联失败      │  │  - 广播          │                              │
│  └──────────────────┘  └──────────────────┘                              │
│                                                                              │
│  职责: 底层工具、LLM 调用、存储、消息传递                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 分层职责总结

| 层级 | 职责 | 关键操作 | 依赖方向 |
|------|------|----------|----------|
| **Layer 4** | 用户入口 | `runTeam()`, `runAgent()`, `createTeam()` | 调用 Layer 3 |
| **Layer 3** | 编排调度 | 任务分解、DAG 执行、并发控制 | 调用 Layer 2 |
| **Layer 2** | Agent 执行 | 对话循环、工具调用、状态管理 | 调用 Layer 1 |
| **Layer 1** | 基础设施 | LLM 调用、工具执行、存储、消息 | 纯实现 |

---

## 六、关键数据结构和类

### 6.1 AgentConfig

```typescript
// src/types.ts
interface AgentConfig {
  name: string                           // Agent 唯一标识
  provider?: SupportedProvider            // LLM 提供商 (默认 anthropic)
  model?: string                         // 模型 ID
  systemPrompt?: string                  // 系统提示词
  apiKey?: string                        // API Key
  baseURL?: string                       // 自定义 API 地址
  tools?: readonly string[]              // 允许的工具列表
  disallowedTools?: readonly string[]    // 禁止的工具列表
  toolPreset?: 'readonly' | 'readwrite' | 'full'
  maxTurns?: number                      // 最大对话轮次
  maxTokens?: number                     // 最大输出 tokens
  temperature?: number                    // 采样温度
  thinking?: ThinkingConfig              // 思考配置
  contextStrategy?: ContextStrategy       // 上下文策略
  loopDetection?: LoopDetectionConfig    // 循环检测配置
  maxTokenBudget?: number                // Token 预算上限
}
```

### 6.2 Task

```typescript
// src/types.ts
interface Task {
  id: string                             // UUID
  title: string                          // 任务标题
  description: string                    // 任务描述
  status: TaskStatus                     // pending | blocked | in_progress | completed | failed | skipped
  assignee?: string                      // 分配的 Agent 名称
  dependsOn?: string[]                   // 依赖的任务 ID
  memoryScope?: 'dependencies' | 'all'   // 共享记忆范围
  result?: string                        // 执行结果
  createdAt: Date
  updatedAt: Date
  maxRetries?: number                    // 最大重试次数
  retryDelayMs?: number                  // 重试延迟
  retryBackoff?: number                  // 指数退避倍率
}

type TaskStatus = 'pending' | 'blocked' | 'in_progress' | 'completed' | 'failed' | 'skipped'
```

### 6.3 Team

```typescript
// src/team/team.ts
class Team {
  readonly name: string
  readonly config: TeamConfig
  
  private readonly agentMap: ReadonlyMap<string, AgentConfig>
  private readonly bus: MessageBus       // 消息总线
  private readonly queue: TaskQueue       // 任务队列
  private readonly memory: SharedMemory | undefined  // 共享记忆
  private readonly events: EventBus       // 事件总线
  
  // 核心方法
  getAgents(): AgentConfig[]
  getAgent(name: string): AgentConfig | undefined
  sendMessage(from: string, to: string, content: string): void  // 点对点消息
  broadcast(from: string, content: string): void               // 广播
  getMessages(agentName: string): Message[]                    // 获取消息
  addTask(input: TaskInput): Task
  on(event: string, handler: Function): () => void             // 事件监听
}
```

### 6.4 Scheduler

```typescript
// src/orchestrator/scheduler.ts
type SchedulingStrategy = 'round-robin' | 'least-busy' | 'capability-match' | 'dependency-first'

class Scheduler {
  constructor(strategy: SchedulingStrategy = 'dependency-first')
  
  // 核心方法
  schedule(tasks: Task[], agents: AgentConfig[]): Map<taskId, agentName>
  autoAssign(queue: TaskQueue, agents: AgentConfig[]): void
  
  // 策略实现
  private scheduleRoundRobin()
  private scheduleLeastBusy()
  private scheduleCapabilityMatch()
  private scheduleDependencyFirst()  // 优先调度关键路径任务
}
```

### 6.5 TaskQueue

```typescript
// src/task/queue.ts
class TaskQueue {
  // 核心方法
  add(task: Task): void                              // 添加任务
  addBatch(tasks: Task[]): void                      // 批量添加
  complete(taskId: string, result?: string): Task    // 标记完成
  fail(taskId: string, error: string): Task          // 标记失败
  skip(taskId: string, reason: string): Task        // 标记跳过
  update(taskId: string, update: Partial<Task>): Task
  list(): Task[]
  get(taskId: string): Task | undefined
  
  // 事件
  on(event: TaskQueueEvent, handler: Function): void
}

type TaskQueueEvent = 'task:ready' | 'task:complete' | 'task:failed' | 'task:skipped' | 'all:complete'
```

### 6.6 SharedMemory

```typescript
// src/memory/shared.ts
class SharedMemory {
  constructor(store?: MemoryStore)
  
  // 核心方法
  write(agentName: string, key: string, value: string, metadata?: object): Promise<void>
  writeExpiring(agentName: string, key: string, value: string, ttlTurns: number): Promise<void>
  read(key: string): Promise<MemoryEntry | null>
  listByAgent(agentName: string): Promise<MemoryEntry[]>
  getSummary(): Promise<string>  // 生成可读摘要
  advanceTurn(): void            // 推进轮次，使过期条目失效
}
```

### 6.7 MessageBus

```typescript
// src/team/messaging.ts
interface Message {
  readonly id: string
  readonly from: string           // 发送者
  readonly to: string             // 接收者 ('*' = 广播)
  readonly content: string
  readonly timestamp: Date
}

class MessageBus {
  send(from: string, to: string, content: string): Message    // 点对点
  broadcast(from: string, content: string): Message            // 广播
  getUnread(agentName: string): Message[]
  getAll(agentName: string): Message[]
  markRead(agentName: string, messageIds: string[]): void
  subscribe(agentName: string, callback: (msg: Message) => void): () => void
}
```

### 6.8 ToolRegistry

```typescript
// src/tool/framework.ts
interface ToolDefinition<TInput = unknown> {
  name: string
  description: string
  inputSchema: ZodSchema<TInput>
  execute: (input: TInput, context: ToolUseContext) => Promise<ToolResult>
}

class ToolRegistry {
  register(tool: ToolDefinition): void
  unregister(name: string): void
  get(name: string): ToolDefinition | undefined
  list(): ToolDefinition[]
  has(name: string): boolean
  toToolDefs(): LLMToolDef[]  // 转换为 LLM 格式
}

function defineTool<TInput>(config: {
  name: string
  description: string
  inputSchema: ZodSchema<TInput>
  execute: (input: TInput, context: ToolUseContext) => Promise<ToolResult>
}): ToolDefinition<TInput>
```

---

## 七、优缺点简评

### 7.1 优点

| 优点 | 说明 |
|------|------|
| **目标驱动** | 用户只需描述目标，框架自动拆解任务，降低使用门槛 |
| **自动并行** | 依赖分析 + 并发执行，最大化吞吐量 |
| **多 Provider** | 原生支持 10+ LLM 提供商，同一团队可混用 |
| **级联失败处理** | 任务失败时自动标记依赖方，避免无限等待 |
| **共享记忆** | Agent 间可读写命名空间共享数据 |
| **丰富的策略** | 4 种调度策略 + 多种上下文压缩策略 |
| **可观测性** | 内置 `onProgress`/`onTrace` 回调，支持 HTML Dashboard |
| **轻量依赖** | 仅 3 个运行时依赖，可嵌入任意 Node.js 项目 |

### 7.2 缺点/局限

| 缺点 | 说明 |
|------|------|
| **TypeScript Only** | 不支持 Python/Java 等其他语言 |
| **无持久化** | 任务状态、记忆默认存储在内存，需自行实现 `MemoryStore` |
| **CLI 能力弱** | 无 cc-haha 那样的 CLI 子进程管理和协议转换 |
| **无多租户** | 设计为单进程，不适合高并发多租户场景 |
| **审批流缺失** | 无内置 Human-in-the-loop 审批机制 |
| **Web UI 缺失** | 无配套的 Web 界面，需自行开发 |
| **协作模式单一** | 主要基于任务委派，缺少真正的群聊交互 |

---

## 八、对比总结

### open-multi-agent vs cc-haha vs AgentPipe

| 维度 | open-multi-agent | cc-haha | AgentPipe |
|------|------------------|---------|-----------|
| **语言** | TypeScript | TypeScript | Go |
| **核心定位** | 目标驱动多 Agent 编排 | CLI 管理 + IM 界面 | CLI 编排 + TUI |
| **多模型支持** | ✅ 10+ Provider | ✅ 协议转换 | ✅ OpenRouter |
| **会话管理** | ❌ 无 | ✅ 完整 | ❌ 无 |
| **群聊** | ❌ 无 | ✅ 完整 | ❌ 无 |
| **CLI 集成** | ❌ 无 | ✅ Claude CLI | ❌ 无 |
| **任务 DAG** | ✅ 核心特性 | ❌ 无 | ❌ 无 |
| **共享记忆** | ✅ SharedMemory | ✅ Claude History | ❌ 无 |
| **工具能力** | 内置 + MCP | CLI 原生工具 | 适配器封装 |
| **适用场景** | 后端任务编排 | 开发者 CLI 工具 | CLI 批处理 |

---

## 九、关键文件索引

```
src/
├── orchestrator/
│   ├── orchestrator.ts      # 核心编排引擎 (1000+ 行)
│   └── scheduler.ts         # 4 种调度策略
├── agent/
│   ├── agent.ts            # Agent 生命周期
│   ├── runner.ts           # 对话循环引擎
│   └── pool.ts             # 并发池
├── team/
│   ├── team.ts             # Team 管理
│   └── messaging.ts        # MessageBus
├── task/
│   ├── task.ts            # Task 工具函数
│   └── queue.ts           # 任务队列
├── memory/
│   ├── shared.ts          # 共享记忆
│   └── store.ts           # 内存存储
├── tool/
│   ├── framework.ts        # ToolRegistry + defineTool
│   ├── executor.ts         # 工具执行器
│   ├── built-in/           # 内置工具集
│   └── mcp.ts             # MCP 集成
└── llm/
    ├── adapter.ts          # 适配器基类
    ├── anthropic.ts       # Anthropic
    ├── openai.ts          # OpenAI
    ├── deepseek.ts        # DeepSeek
    ├── gemini.ts          # Gemini
    └── ...                # 其他 Provider
```
