# cc-haha 上下文消息管理机制深度分析

## 1. 概述

cc-haha 项目在 **IM 层与 CLI 层之间构建了完整的消息管理层**。以下是核心发现：

> **关键结论**：cc-haha 采用了 **WebSocket + SDK Protocol** 的方式实现消息注入，而非简单的 stdin 输入。消息通过 SDK WebSocket 协议传递给 CLI，CLI 负责维护对话历史和上下文，IM 层通过 Proxy 代理协议转换。

---

## 2. 消息管理架构总览

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           IM 层 (Desktop Server)                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    ConversationService                              │  │
│  │  ├── sendMessage()        → 构建 SDK UserMessage                   │  │
│  │  ├── sendSdkMessage()     → 通过 WebSocket 发送给 CLI              │  │
│  │  └── WebSocket Server     ← 接收 CLI 的响应                        │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ WebSocket (SDK Protocol)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLI 层 (子进程)                                 │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    Claude CLI (长驻进程)                              │  │
│  │  ├── 维护对话历史 (session-id)                                      │  │
│  │  ├── 维护上下文窗口                                                 │  │
│  │  ├── 执行工具                                                       │  │
│  │  └── 管理 Memory/Auto-memory                                        │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心组件与职责

### 3.1 IM 侧组件

| 组件 | 文件 | 职责 |
|------|------|------|
| **ConversationService** | `conversationService.ts` | CLI 子进程管理、消息发送、WebSocket 控制 |
| **WebSocket Handler** | `ws/handler.ts` | 处理 IM 端的 WebSocket 连接 |
| **Proxy Handler** | `proxy/handler.ts` | 协议转换（Anthropic ↔ OpenAI） |

### 3.2 CLI 侧组件

| 组件 | 文件 | 职责 |
|------|------|------|
| **SessionRunner** | `bridge/sessionRunner.ts` | CLI 子进程 spawn、stdin/stdout 管理 |
| **Bridge Core** | `bridge/replBridge.ts` | WebSocket 连接建立、消息路由 |

---

## 4. 消息注入机制详解

### 4.1 CLI 启动参数

cc-haha 通过以下参数启动 Claude CLI：

```typescript
// conversationService.ts::buildSessionCliArgs()
const args = [
  '--print',                    // 非交互模式
  '--verbose',                  // 详细输出
  '--sdk-url', sdkUrl,         // WebSocket 连接地址
  '--enable-auth-status',
  '--input-format', 'stream-json',   // ← 关键：JSONL 输入格式
  '--output-format', 'stream-json',  // ← 关键：JSONL 输出格式
  '--include-partial-messages',      // 流式输出
  '--resume', sessionId,              // 或 --session-id
  '--replay-user-messages',           // 重放历史消息
  '--permission-mode', 'default',
]
```

### 4.2 WebSocket SDK 协议消息格式

IM 侧通过 WebSocket 发送 SDK 消息给 CLI：

```typescript
// conversationService.ts::sendSdkMessage()
interface SDKMessage {
  type: 'user' | 'control_request' | 'control_response'
  
  // User 消息
  message?: {
    role: 'user'
    content: string | ContentBlock[]
  }
  parent_tool_use_id?: string | null
  
  // Control 消息
  request_id?: string
  request?: {
    subtype: 'set_permission_mode' | 'set_max_thinking_tokens' | 'interrupt'
    mode?: string
    max_thinking_tokens?: number
  }
  response?: {
    subtype: 'success' | 'error'
    behavior: 'allow' | 'deny'
  }
}

// 发送示例
sendSdkMessage(sessionId, {
  type: 'user',
  message: {
    role: 'user',
    content: this.buildUserContent(content, sessionId, attachments)
  },
  parent_tool_use_id: null,
  session_id: ''
})
```

### 4.3 CLI 输入格式 (stream-json)

CLI 支持 JSONL (Newline-delimited JSON) 输入格式：

```jsonl
{"type":"user","message":{"role":"user","content":"帮我写一个排序算法"}}
{"type":"control_request","request_id":"uuid","request":{"subtype":"interrupt"}}
```

### 4.4 CLI 输出格式 (stream-json)

CLI 的流式输出也采用 JSONL 格式：

```jsonl
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"好的"}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"，"}}]}}
{"type":"result","subtype":"success","usage":{"input_tokens":100,"output_tokens":50}}
```

---

## 5. 会话管理机制

### 5.1 会话 ID 与历史维护

```typescript
// conversationService.ts
interface SessionProcess {
  proc: Bun.spawn              // CLI 子进程
  sdkSocket: WebSocket | null  // SDK WebSocket 连接
  pendingOutbound: string[]    // 待发送消息队列
  sdkMessages: any[]           // 最近 SDK 消息 (最多40条)
  initMessage: any | null     // 初始化消息
}
```

**会话历史由 CLI 维护**：
- CLI 使用 `--session-id` 或 `--resume` 标识会话
- CLI 在 `~/.claude/history.jsonl` 中存储历史
- CLI 内部管理上下文窗口（自动 compact）

### 5.2 IM 侧的历史同步

IM 侧通过 WebSocket 接收 CLI 的消息：

```typescript
// replBridge.ts
interface ReplBridgeParams {
  initialMessages?: Message[]  // 初始消息（resume 时）
  onInboundMessage?: (msg: SDKMessage) => void  // 消息回调
}

// WebSocket 接收消息流程
ws.on('message', (data) => {
  const msg = JSON.parse(data.toString())
  onInboundMessage?.(msg)  // 转发给 IM 层
})
```

### 5.3 历史消息重放 (replay-user-messages)

cc-haha 支持在 resume 时重放历史消息：

```typescript
// sessionRunner.ts::extractUserMessageText()
function extractUserMessageText(msg: Record<string, unknown>): string | undefined {
  // 跳过工具结果消息和合成消息
  if (msg.parent_tool_use_id != null || msg.isSynthetic || msg.isReplay)
    return undefined
  
  // 提取用户消息文本
  const message = msg.message as Record<string, unknown>
  const content = message?.content
  // ...
}
```

---

## 6. CLI 启动时的上下文注入

### 6.1 环境变量注入

```typescript
// conversationService.ts::buildChildEnv()
async buildChildEnv(workDir, sdkUrl, options): Record<string, string> {
  const explicitProviderEnv = await this.providerService.getProviderRuntimeEnv(
    options.providerId
  )
  
  return {
    // 基础环境
    PWD: workDir,
    CALLER_DIR: workDir,
    
    // 模型配置
    ...explicitProviderEnv,  // ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN 等
    
    // 功能开关
    CLAUDE_CODE_ENABLE_TASKS: '1',
    CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING: '1',
    
    // 记忆路径
    CLAUDE_COWORK_MEMORY_PATH_OVERRIDE: this.resolveDesktopAutoMemoryPath(workDir),
    
    // Server URL
    CC_HAHA_DESKTOP_SERVER_URL: desktopServerUrl,
  }
}
```

### 6.2 注入的环境变量列表

| 环境变量 | 作用 | 来源 |
|---------|------|------|
| `ANTHROPIC_API_KEY` | API 密钥 | Provider 配置 |
| `ANTHROPIC_BASE_URL` | API 端点 | Provider 配置 (指向 Proxy) |
| `ANTHROPIC_AUTH_TOKEN` | 认证 Token | Provider 配置 |
| `ANTHROPIC_MODEL` | 模型名称 | 会话配置 |
| `CLAUDE_CODE_OAUTH_TOKEN` | OAuth Token | 官方模式 |
| `CLAUDE_COWORK_MEMORY_PATH_OVERRIDE` | 记忆目录 | Desktop 配置 |
| `CC_HAHA_DESKTOP_SERVER_URL` | Desktop Server | Desktop 配置 |

### 6.3 CLI 参数注入

```typescript
// conversationService.ts::getRuntimeArgs()
private getRuntimeArgs(options): string[] {
  const args: string[] = []
  
  if (options?.model) {
    args.push('--model', options.model)      // 模型选择
  }
  
  if (options?.effort) {
    args.push('--effort', options.effort)    // 努力程度
  }
  
  if (options?.thinking) {
    args.push('--thinking', options.thinking) // 思考模式
  }
  
  return args
}
```

---

## 7. 消息流转完整流程

### 7.1 用户发送消息流程

```
1. IM 用户输入消息
         │
         ▼
2. WebSocket Handler 接收消息
   ws/handler.ts::handleUserMessage()
         │
         ▼
3. ConversationService.sendMessage()
   - 构建 SDK UserMessage
   - 序列化 JSON + '\n'
         │
         ▼
4. WebSocket.send() → CLI 子进程
   ws.send(JSON.stringify(msg) + '\n')
         │
         ▼
5. CLI 接收消息，添加到对话历史
   - CLI 内部维护 context window
   - 如需 compact，自动压缩历史
         │
         ▼
6. CLI 处理请求，输出流式响应
   JSONL 格式输出到 stdout
         │
         ▼
7. SessionRunner 解析 stdout
   - extractActivities() 提取活动
   - 通过 WebSocket 转发给 IM 层
         │
         ▼
8. IM 层展示响应
   - 流式卡片显示
   - 工具调用展示
```

### 7.2 工具调用流程

```
1. CLI 调用工具 (如 Bash/Read/Edit)
         │
         ▼
2. CLI 输出 tool_use 消息
   {"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash"}]}}
         │
         ▼
3. 如果需要权限，发送 control_request
   {"type":"control_request","request":{"subtype":"can_use_tool"}}
         │
         ▼
4. IM 层处理权限请求
   ConversationService.pendingPermissionRequests
         │
         ▼
5. 用户批准/拒绝
   sendSdkMessage({type:"control_response",response:{behavior:"allow"}})
         │
         ▼
6. CLI 继续执行，返回工具结果
```

---

## 8. 上下文窗口管理

### 8.1 谁在管理上下文？

| 职责 | 管理方 | 说明 |
|------|--------|------|
| **对话历史** | CLI | CLI 内部维护，自动 compact |
| **工具调用结果** | CLI | CLI 决定何时显示/隐藏 |
| **系统提示** | CLI | CLI 内置的 prompts.ts |
| **记忆 (Memory)** | **IM + CLI** | IM 注入 Memory section 到 System Prompt |
| **会话 ID** | IM + CLI | IM 提供 sessionId，CLI 关联 |
| **模型配置** | IM | IM 通过环境变量和参数注入 |

### 8.2 IM 侧注入的上下文

IM 侧在启动 CLI 时会注入以下上下文：

1. **Provider 配置**：API 密钥、端点、模型
2. **Memory 路径**：`CLAUDE_COWORK_MEMORY_PATH_OVERRIDE`
3. **Desktop Server URL**：用于权限请求等

但 **对话内容本身由 CLI 管理和决定**。

---

## 9. 与会话历史的交互

### 9.1 cc-haha 如何获取历史

```typescript
// adapters/common/session-store.ts
// chatId (IM) ↔ sessionId (CLI) 映射
// IM 通过 HTTP API 获取 CLI 的历史
await fetch(`/conversations/${sessionId}/history`)
```

### 9.2 历史消息的获取时机

| 时机 | 方式 |
|------|------|
| Resume 会话 | CLI 内部处理，IM 侧通过 `--resume` 触发 |
| 新建会话 | 无历史，通过 `initialMessages` 注入 |
| 展示历史 | IM 侧通过 WebSocket 接收并展示 |

---

## 10. 关键代码路径

### 10.1 消息发送路径

```
IM Input
  ↓
ws/handler.ts: handleUserMessage()
  ↓
conversationService.sendMessage(content, attachments)
  ↓
conversationService.sendSdkMessage(sessionId, sdkMessage)
  ↓
session.sdkSocket.send(JSON.stringify(payload) + '\n')
  ↓
CLI stdin
```

### 10.2 消息接收路径

```
CLI stdout (JSONL)
  ↓
sessionRunner.ts: rl.on('line')
  ↓
extractActivities() / 解析消息
  ↓
bridge/replBridge.ts: onInboundMessage()
  ↓
ws/handler.ts: handleBridgeMessage()
  ↓
IM UI 更新
```

---

## 11. 总结

### 11.1 cc-haha 的上下文管理策略

| 维度 | 管理方 | 机制 |
|------|--------|------|
| **消息注入** | IM → CLI | WebSocket SDK Protocol |
| **对话历史** | CLI 维护 | session-id + 自动 compact |
| **系统提示** | CLI 内置 | prompts.ts 模块化构建 |
| **记忆系统** | **IM + CLI** | IM 注入 Memory section |
| **工具权限** | IM 审批 | Control Request/Response |
| **上下文压缩** | CLI 自动 | CLAUDE_CODE_AUTO_COMPACT_WINDOW |

### 11.2 IM 层对 CLI 的控制手段

1. **环境变量**：模型、端点、API 密钥
2. **启动参数**：模型、思考模式、努力程度
3. **WebSocket 消息**：用户消息、权限响应、中断请求
4. **记忆注入**：Memory section 到 System Prompt

### 11.3 CLI 自主管理的部分

1. **对话历史**：自动 compact，维持上下文窗口
2. **工具执行**：实际执行工具调用
3. **响应生成**：模型调用和文本生成
4. **记忆更新**：写入 auto-memory 目录

### 11.4 与 AgentPipe 的对比

| 维度 | cc-haha | AgentPipe |
|------|---------|-----------|
| **通信方式** | WebSocket + SDK Protocol | stdin/stdout |
| **会话维持** | 长驻进程 + session-id | 每次新建进程 |
| **历史管理** | CLI 内部维护 | 每次作为 Prompt 传递 |
| **上下文注入** | 环境变量 + WebSocket | 一次性 Prompt |
| **工具权限** | WebSocket 审批 | 无 |
