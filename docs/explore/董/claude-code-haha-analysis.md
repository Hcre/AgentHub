# cc-haha 项目分析：IM 模块与 CLI 子进程对接机制

## 一、项目概述

**项目地址**: https://github.com/NanmiCoder/cc-haha.git

cc-haha 是一个基于 Claude Code 源码的桌面端工作台，主要功能包括：
- 多会话管理
- IM 接入（Telegram / 飞书 / 微信 / 钉钉）
- 分支 / Worktree 支持
- Computer Use（桌面控制）
- H5 远程访问

**技术栈**: TypeScript + Electron + Bun

---

## 二、核心架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     IM 适配器层 (adapters/)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Telegram │ │  飞书    │ │  微信    │ │  钉钉    │        │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘        │
│       └────────────┴────────────┴────────────┘                │
│                           │                                    │
│                    ┌──────▼──────┐                            │
│                    │  WsBridge   │  (WebSocket 桥接)          │
│                    │  统一接口    │                            │
│                    └──────┬──────┘                            │
└───────────────────────────┼───────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│                    Desktop Server (src/server/)                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  WebSocket Handler (src/server/ws/handler.ts)          │  │
│  │  - 管理 WebSocket 连接生命周期                           │  │
│  │  - 消息路由与转换                                       │  │
│  └─────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  ConversationService (src/server/services/)              │  │
│  │  - CLI 子进程管理                                       │  │
│  │  - 会话生命周期                                         │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────┬───────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│                    CLI 子进程 (Claude Code)                     │
│  - Claude Code CLI 运行在独立进程中                             │
│  - 通过 stdin/stdout 与服务器通信                              │
│  - 输入格式: stream-json                                       │
│  - 输出格式: stream-json                                        │
└───────────────────────────────────────────────────────────────┘
```

---

## 三、IM 模块与 CLI 对接的核心机制

### 3.1 整体数据流

```
IM 平台 (飞书/微信等)
       │
       │ HTTP/WebSocket
       ▼
┌────────────────────┐
│   IM Adapter       │  (adapters/common/ws-bridge.ts)
│   - 消息格式化      │
│   - 命令解析        │
│   - 附件处理        │
└────────┬───────────┘
         │ WebSocket
         ▼
┌────────────────────┐
│   Desktop Server   │  (src/server/ws/handler.ts)
│   - 会话路由       │
│   - 消息转换       │
└────────┬───────────┘
         │ stdin/stdout (stream-json)
         ▼
┌────────────────────┐
│   CLI 子进程       │  (Claude Code CLI)
│   - AI 对话        │
│   - 工具执行       │
│   - 会话历史       │
└────────────────────┘
```

### 3.2 WebSocket 桥接层 (WsBridge)

```typescript
// adapters/common/ws-bridge.ts
export class WsBridge {
  private sessions = new Map<string, Session>()
  private handlers = new Map<string, MessageHandler>()

  /** 连接到特定会话 */
  connectSession(chatId: string, sessionId: string): boolean

  /** 发送用户消息 */
  sendUserMessage(chatId: string, content: string, attachments?: AttachmentRef[]): boolean

  /** 发送权限响应 */
  sendPermissionResponse(chatId: string, requestId: string, allowed: boolean, rule?: string): boolean

  /** 停止生成 */
  sendStopGeneration(chatId: string): boolean

  /** 处理服务器消息 */
  onServerMessage(chatId: string, handler: MessageHandler): void
}
```

**核心职责**：
1. **会话映射**: `chatId` (IM) ↔ `sessionId` (CLI)
2. **消息转换**: IM 消息格式 ↔ ServerMessage 格式
3. **自动重连**: 连接断开后自动重试
4. **心跳机制**: 30秒心跳保活

### 3.3 消息类型定义

```typescript
// src/server/ws/events.ts

// Client → Server
type ClientMessage =
  | { type: 'prewarm_session' }
  | { type: 'user_message'; content: string; attachments?: AttachmentRef[] }
  | { type: 'permission_response'; requestId: string; allowed: boolean; rule?: string }
  | { type: 'set_permission_mode'; mode: string }
  | { type: 'set_runtime_config'; providerId: string | null; modelId: string }
  | { type: 'stop_generation' }

// Server → Client
type ServerMessage =
  | { type: 'connected'; sessionId: string }
  | { type: 'content_start'; blockType: 'text' | 'tool_use'; toolName?: string }
  | { type: 'content_delta'; text?: string; toolInput?: string }
  | { type: 'tool_use_complete'; toolName: string; toolUseId: string }
  | { type: 'tool_result'; toolUseId: string; content: unknown; isError: boolean }
  | { type: 'permission_request'; requestId: string; toolName: string; input: unknown }
  | { type: 'message_complete'; usage: TokenUsage }
  | { type: 'thinking'; text: string }
  | { type: 'status'; state: ChatState; verb?: string }
  | { type: 'error'; message: string; code: string }
```

---

## 四、会话历史管理

### 4.1 会话映射机制

```typescript
// adapters/common/session-store.ts
export type SessionEntry = {
  sessionId: string      // CLI 会话 ID
  workDir: string        // 工作目录
  updatedAt: number      // 最后更新时间
}

export class SessionStore {
  // chatId → sessionId/workDir 映射
  get(chatId: string): SessionEntry | null
  set(chatId: string, sessionId: string, workDir: string): void
  delete(chatId: string): void
  deleteBySessionId(sessionId: string): string[]  // 反向查询
  listAll(): Array<{ chatId: string } & SessionEntry>
}
```

**存储位置**: `~/.claude/adapter-sessions.json`

### 4.2 CLI 会话历史

```typescript
// src/history.ts
// CLI 会话历史存储在 ~/.claude/history.jsonl

export async function* getHistory(): AsyncGenerator<HistoryEntry> {
  // 按项目过滤
  // 当前会话优先
  // 最多 100 条
}

export async function* makeHistoryReader(): AsyncGenerator<LogEntry> {
  // 从 history.jsonl 读取
  // 支持 Ctrl+R 搜索
  // 支持粘贴内容解析
}
```

### 4.3 历史消息流转

```
IM 用户请求历史
       │
       ▼
IM Adapter 调用 httpClient 获取会话信息
       │
       │ GET /api/sessions/:sessionId/history
       ▼
Desktop Server 返回消息列表
       │
       ▼
IM Adapter 格式化并展示
```

---

## 五、工具 (Tools) 和 Skill 系统

### 5.1 工具分类

```typescript
// src/tools.ts
// 内置工具
import { BashTool } from './tools/BashTool/BashTool.js'
import { FileEditTool } from './tools/FileEditTool/FileEditTool.js'
import { FileReadTool } from './tools/FileReadTool/FileReadTool.js'
import { FileWriteTool } from './tools/FileWriteTool/FileWriteTool.js'
import { GlobTool } from './tools/GlobTool/GlobTool.js'
import { WebSearchTool } from './tools/WebSearchTool/WebSearchTool.js'
// ...

// 条件编译工具
const REPLTool = process.env.USER_TYPE === 'ant' ? ... : null
const SleepTool = feature('PROACTIVE') ? ... : null
const cronTools = feature('AGENT_TRIGGERS') ? [...] : []
```

### 5.2 SkillTool 执行流程

```typescript
// src/tools/SkillTool/SkillTool.ts

async function executeForkedSkill(
  command: Command & { type: 'prompt' },
  commandName: string,
  args: string | undefined,
  context: ToolUseContext,
): Promise<ToolResult<Output>> {
  // 1. 在 fork 上下文中执行 Skill
  const forkedContext = prepareForkedCommandContext(command, context)

  // 2. 创建子 Agent 执行
  const agentResult = await runAgent(forkedContext)

  // 3. 提取结果
  return extractResultText(agentResult)
}
```

### 5.3 Skill 加载机制

```typescript
// src/docs/skills/loadSkillsDir.ts
export function loadSkillsFromDir(dir: string): Command[] {
  // 从目录加载 .md 文件
  // 解析 frontmatter
  // 提取 name, description, allowed-tools 等
}

// Skill frontmatter 示例:
/*
---
name: my-skill
description: A useful skill for...
allowed-tools: [Read, Edit, Bash]
model: claude-sonnet-4-20250514
effort: medium
---

# Skill Content
...
*/
```

### 5.4 工具调用流程

```
CLI 执行工具
       │
       ▼
┌────────────────────┐
│ ToolUseComplete    │  tool_use_complete 事件
│ 事件发送到客户端    │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ IM Adapter 处理    │
│ - 流式卡片更新     │
│ - 格式化结果      │
└────────┬───────────┘
         │
         ▼
用户收到工具执行结果
```

---

## 六、权限管理

### 6.1 权限请求流程

```typescript
// adapters/common/permission.ts
type PermissionDecision = 'allow' | 'deny' | 'always' | 'never'

// IM 命令格式:
// /allow <requestId>
// /deny <requestId>
// /always <requestId>  (记住决策)
```

### 6.2 权限消息转发

```typescript
// IM Adapter 处理权限请求
async function handlePermissionRequest(msg: ServerMessage) {
  if (msg.type === 'permission_request') {
    const card = formatPermissionRequest(msg)
    await sendCard(chatId, card)
    // 保存 requestId 以便后续响应
    pendingPermissions.get(chatId).add(msg.requestId)
  }
}

// 用户响应权限
async function handlePermissionCommand(chatId: string, cmd: string) {
  const { requestId, decision } = parsePermissionCommand(cmd)
  bridge.sendPermissionResponse(chatId, requestId, decision === 'allow')
}
```

---

## 七、飞书适配器示例

```typescript
// adapters/feishu/index.ts

// 1. 初始化
const bridge = new WsBridge(config.serverUrl, 'feishu')
const sessionStore = new SessionStore()

// 2. 接收消息
larkClient.im.message RECEIVE => {
  const payload = extractInboundPayload(event)
  const { chatId, text, attachments } = payload

  // 3. 确保会话存在
  const stored = sessionStore.get(chatId)
  if (!stored) {
    // 新会话：选择项目
    return handleProjectSelection(chatId, text)
  }

  // 4. 发送消息到 CLI
  bridge.sendUserMessage(chatId, text, attachments)
}

// 5. 处理 CLI 响应
bridge.onServerMessage(chatId, handleServerMessage)

// 6. 流式更新
async function handleServerMessage(chatId: string, msg: ServerMessage) {
  switch (msg.type) {
    case 'content_start':
      getOrCreateStreamingCard(chatId).start()
      break
    case 'content_delta':
      streamingCard.append(msg.text || '')
      break
    case 'tool_use_complete':
      card.updateToolStatus(msg.toolName, 'done')
      break
    case 'message_complete':
      await card.finalize()
      break
  }
}
```

---

## 八、关键设计模式

### 8.1 消息缓冲模式

```typescript
// adapters/common/message-buffer.ts
export class MessageBuffer {
  // 按时间窗口或字符数批量 flush
  // 用于流式卡片更新

  append(text: string): void {
    this.buffer += text
    if (this.buffer.length >= this.charThreshold) {
      this.scheduleFlush()
    }
  }

  async complete(): Promise<void> {
    // 最终刷新
    await this.flush(true)
  }
}
```

### 8.2 会话清理机制

```typescript
// WebSocket 断开后延迟清理
const cleanupTimer = setTimeout(() => {
  if (!activeSessions.has(sessionId)) {
    conversationService.stopSession(sessionId)  // 停止 CLI 子进程
  }
}, 30_000)

// 重新连接则取消清理
function handleWebSocketOpen(ws) {
  const pendingTimer = sessionCleanupTimers.get(sessionId)
  if (pendingTimer) {
    clearTimeout(pendingTimer)
    sessionCleanupTimers.delete(sessionId)
  }
}
```

### 8.3 附件处理

```typescript
// adapters/common/attachment/
interface AttachmentStore {
  store(data: Buffer, mime: string): string  // 返回 attachmentId
  retrieve(id: string): Buffer | null
  delete(id: string): void
}

// 支持类型:
// - 文件: path → 上传到 IM 平台
// - 图片: base64 → 上传为 image_key
// - 目录: 打包上传
```

---

## 九、IM 模块如何获取 CLI 状态

### 9.1 状态同步

```typescript
// IM Adapter 维护本地状态
type ChatRuntimeState = {
  state: 'idle' | 'thinking' | 'streaming' | 'tool_executing' | 'permission_pending'
  verb?: string
  model?: string
  pendingPermissionCount: number
}

// 从 ServerMessage 同步
function handleServerMessage(chatId: string, msg: ServerMessage) {
  switch (msg.type) {
    case 'status':
      const state = getRuntimeState(chatId)
      state.state = msg.state
      state.verb = msg.verb
      break
  }
}
```

### 9.2 /status 命令

```typescript
// adapters/common/format.ts
async function buildStatusText(chatId: string): Promise<string> {
  const stored = await ensureExistingSession(chatId)
  const runtime = getRuntimeState(chatId)

  // 获取 Git 信息
  const gitInfo = await httpClient.getGitInfo(stored.sessionId)

  // 获取任务统计
  const tasks = await httpClient.getTasksForSession(stored.sessionId)

  return formatImStatus({
    sessionId: stored.sessionId,
    projectName: gitInfo.repoName,
    branch: gitInfo.branch,
    model: runtime.model,
    state: runtime.state,
    taskCounts: summarizeTasks(tasks)
  })
}
```

---

## 十、总结

### 10.1 IM 与 CLI 对接的关键设计

| 组件 | 职责 | 位置 |
|------|------|------|
| WsBridge | IM 会话 ↔ CLI 会话映射 | adapters/common/ws-bridge.ts |
| SessionStore | chatId/sessionId 持久化 | adapters/common/session-store.ts |
| MessageBuffer | 流式消息缓冲 | adapters/common/message-buffer.ts |
| ConversationService | CLI 子进程管理 | src/server/services/conversationService.ts |
| WebSocketHandler | 消息路由 | src/server/ws/handler.ts |

### 10.2 数据流

```
IM 消息 → WsBridge → WebSocket → Server
                                     ↓
                               ClientMessage
                                     ↓
                          stdin (stream-json)
                                     ↓
                          ┌──────────┴──────────┐
                          │   CLI 子进程        │
                          │   - AI 处理        │
                          │   - 工具执行       │
                          │   - 会话历史       │
                          └──────────┬──────────┘
                                     ↓
                          stdout (stream-json)
                                     ↓
                               ServerMessage
                                     ↓
                          WebSocket → WsBridge
                                     ↓
                          IM 消息 (格式化后)
```

### 10.3 与 AgentPipe 的对比

| 方面 | AgentPipe | cc-haha |
|------|-----------|---------|
| 架构 | CLI 为主，TUI 为辅 | Desktop 为主，IM 为辅 |
| 会话管理 | 多 Agent 编排 | 单 CLI 会话 + 多适配器 |
| 工具系统 | Agent Adapter | 内置 Tool + Skill |
| IM 对接 | Bridge 事件输出 | IM Adapter 直连 |
| 会话历史 | 存储在 CLI | 存储在 CLI，但通过 API 暴露 |

cc-haha 的 IM 对接设计更加**垂直**，直接将 IM 消息桥接到 Claude Code 的 WebSocket 会话；而 AgentPipe 则更偏**水平**编排，通过事件系统支持多 Agent 协作。
