# cc-haha CLI 多模型支持机制深度分析

## 一、核心问题

**Claude Code CLI 原生只支持 Anthropic 官方 API，如何让它使用 DeepSeek、GPT、Qwen 等其他模型？**

cc-haha 的答案是：**环境变量注入 + 协议转换代理**。

---

## 二、关键类和数据结构

### 2.1 会话启动选项

```typescript
// src/server/services/conversationService.ts:76
type SessionStartOptions = {
  permissionMode?: string
  model?: string                    // 模型 ID
  effort?: string
  thinking?: 'enabled' | 'adaptive' | 'disabled'
  providerId?: string | null         // Provider ID - 每个会话可独立指定
}
```

**关键点**：`providerId` 字段允许每个会话使用不同的 Provider（即不同的模型）。

### 2.2 Provider 配置结构

```typescript
// src/server/types/provider.ts
interface SavedProvider {
  id: string              // UUID，唯一标识
  presetId: string        // 预设类型：deepseek, kimi, custom 等
  name: string            // 显示名称
  apiKey: string          // API Key
  baseUrl: string         // API 地址
  apiFormat: 'anthropic' | 'openai_chat' | 'openai_responses'
  runtimeKind: 'anthropic_compatible' | 'openai_oauth'
  models: {
    main: string    // 主模型
    haiku: string   // 快速模型槽位
    sonnet: string  // 中等模型槽位
    opus: string    // 高级模型槽位
  }
}
```

### 2.3 模型槽位映射

Claude Code CLI 定义了 4 个模型槽位，cc-haha 实现了完整的模型映射：

| 槽位 | 用途 | 环境变量 |
|------|------|----------|
| `main` | 默认模型 | `ANTHROPIC_MODEL` |
| `haiku` | 快速任务 | `ANTHROPIC_DEFAULT_HAIKU_MODEL` |
| `sonnet` | 普通任务 | `ANTHROPIC_DEFAULT_SONNET_MODEL` |
| `opus` | 复杂任务 | `ANTHROPIC_DEFAULT_OPUS_MODEL` |

CLI 会根据任务复杂度自动选择合适的槽位。

---

## 三、支持的 Provider 列表

```typescript
// src/server/config/providerPresets.json
const PROVIDER_PRESETS = [
  { id: "official",     name: "Claude Official",   apiFormat: "anthropic" },
  { id: "deepseek",     name: "DeepSeek",         apiFormat: "anthropic" },
  { id: "zhipuglm",     name: "智谱 GLM",         apiFormat: "anthropic" },
  { id: "kimi",         name: "Kimi",              apiFormat: "anthropic" },
  { id: "minimax",      name: "MiniMax",           apiFormat: "anthropic" },
  { id: "jiekouai",     name: "接口AI",            apiFormat: "anthropic" },
  { id: "shengsuanyun", name: "胜算云",             apiFormat: "anthropic" },
  { id: "lmstudio",     name: "LM Studio",         apiFormat: "anthropic" },  // 本地模型
  { id: "ollama",       name: "Ollama",             apiFormat: "anthropic" },  // 本地模型
  { id: "custom",       name: "Custom",             apiFormat: "anthropic" }, // 自定义配置
]
```

### Provider 详细配置示例

```json
// DeepSeek Provider
{
  "id": "deepseek",
  "name": "DeepSeek",
  "baseUrl": "https://api.deepseek.com/anthropic",
  "apiFormat": "anthropic",
  "defaultModels": {
    "main": "deepseek-v4-pro",
    "haiku": "deepseek-v4-flash",
    "sonnet": "deepseek-v4-pro",
    "opus": "deepseek-v4-pro"
  },
  "needsApiKey": true,
  "authStrategy": "auth_token",
  "modelContextWindows": {
    "deepseek-v4-pro": 1000000,
    "deepseek-v4-flash": 1000000
  }
}
```

---

## 四、数据流转

### 4.1 完整数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           用户操作层                                        │
│  用户在 IM 界面选择 Provider (DeepSeek) + 模型 (deepseek-v4-pro)             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ WebSocket 消息: set_runtime_config
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      WebSocket Handler (handler.ts)                          │
│  1. 解析消息: { providerId, modelId }                                        │
│  2. 存储到 runtimeOverrides Map<sessionId, Override>                        │
│  3. 调用 restartSessionWithRuntimeConfig()                                   │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  ConversationService (conversationService.ts)               │
│                                                                              │
│  startSession(sessionId, workDir, sdkUrl, options)                          │
│  {                                                                          │
│    providerId: "deepseek-uuid",                                             │
│    model: "deepseek-v4-pro"                                                 │
│  }                                                                          │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       buildChildEnv() - 核心环境注入                          │
│                                                                              │
│  // 获取 Provider 运行时环境                                                  │
│  const explicitProviderEnv = providerService.getProviderRuntimeEnv(         │
│    options.providerId  // "deepseek-uuid"                                   │
│  )                                                                          │
│                                                                              │
│  // 返回的环境变量                                                           │
│  return {                                                                   │
│    ANTHROPIC_BASE_URL: "http://127.0.0.1:3456/proxy/providers/deepseek-uuid",
│    ANTHROPIC_AUTH_TOKEN: "sk-xxxxx",                                        │
│    ANTHROPIC_MODEL: "deepseek-v4-pro",                                      │
│    ANTHROPIC_DEFAULT_HAIKU_MODEL: "deepseek-v4-flash",                      │
│    ANTHROPIC_DEFAULT_SONNET_MODEL: "deepseek-v4-pro",                       │
│    ANTHROPIC_DEFAULT_OPUS_MODEL: "deepseek-v4-pro",                         │
│    // ... 其他配置                                                           │
│  }                                                                           │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Bun.spawn() 启动 CLI 子进程                              │
│                                                                              │
│  const proc = Bun.spawn(args, {                                            │
│    cwd: workDir,                                                            │
│    env: childEnv,  // 注入的环境变量                                          │
│    stdin: 'pipe',                                                           │
│    stdout: 'pipe',                                                          │
│    stderr: 'pipe',                                                          │
│  })                                                                         │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Claude CLI 子进程                                     │
│                                                                              │
│  CLI 读取环境变量:                                                           │
│    ANTHROPIC_BASE_URL → "http://127.0.0.1:3456/proxy/providers/..."        │
│    ANTHROPIC_MODEL → "deepseek-v4-pro"                                      │
│                                                                              │
│  CLI 向 ANTHROPIC_BASE_URL 发送 Anthropic Messages API 请求                  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  │ HTTP POST (Anthropic 格式)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Proxy Handler (handler.ts)                              │
│                                                                              │
│  // 路径: /proxy/providers/{providerId}/v1/messages                          │
│                                                                              │
│  1. 获取 Provider 配置 (baseUrl, apiKey, apiFormat)                         │
│  2. Anthropic → OpenAI 格式转换 (如果需要)                                  │
│  3. 转发到第三方 API                                                        │
│  4. OpenAI → Anthropic 格式转换 (如果需要)                                  │
│  5. 返回响应给 CLI                                                          │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  │ HTTP POST (OpenAI Chat 格式)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     第三方 API (DeepSeek API)                               │
│                                                                              │
│  POST https://api.deepseek.com/v1/chat/completions                          │
│  {                                                                          │
│    model: "deepseek-v4-pro",                                                │
│    messages: [...],                                                         │
│  }                                                                           │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  │ HTTP Response
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Proxy Handler (响应处理)                                │
│                                                                              │
│  1. 接收 OpenAI 响应                                                        │
│  2. OpenAI → Anthropic 格式转换                                             │
│  3. 返回 Anthropic SSE 格式给 CLI                                           │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  │ SSE Stream
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CLI 子进程 & IM 界面                                   │
│                                                                              │
│  CLI 处理响应，通过 SDK WebSocket 发送给 Desktop Server                       │
│  Desktop Server 转发给 IM 界面                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 五、逻辑分层

### 5.1 四层架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Layer 4: 展示层 (IM Interface)                        │
│                                                                              │
│  - Web UI: 用户选择 Provider 和 Model                                        │
│  - WebSocket 通信: 发送 set_runtime_config 消息                              │
│                                                                              │
│  关键文件:                                                                   │
│    - src/adapters/feishu/index.ts (飞书适配器)                               │
│    - src/adapters/common/ws-bridge.ts (WebSocket 桥接)                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                        Layer 3: 业务层 (Server)                              │
│                                                                              │
│  - Session 管理: 会话创建、销毁、运行时配置                                   │
│  - Provider 管理: CRUD、激活、切换                                           │
│  - 设置管理: 用户设置、Provider 设置                                         │
│                                                                              │
│  关键文件:                                                                   │
│    - src/server/services/conversationService.ts (会话管理)                  │
│    - src/server/services/providerService.ts (Provider 管理)                  │
│    - src/server/services/sessionService.ts (会话元数据)                      │
│    - src/server/ws/handler.ts (WebSocket 消息处理)                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                       Layer 2: 环境注入层                                    │
│                                                                              │
│  - 构建子进程环境变量                                                        │
│  - Provider 配置到环境变量转换                                               │
│  - 协议格式判断与路由                                                        │
│                                                                              │
│  关键文件:                                                                   │
│    - src/server/services/conversationService.ts::buildChildEnv()             │
│    - src/server/services/providerRuntimeEnv.ts (环境变量构建)                 │
│    - src/server/services/providerService.ts::getProviderRuntimeEnv()         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                       Layer 1: 协议转换层 (Proxy)                             │
│                                                                              │
│  - Anthropic → OpenAI 请求转换                                               │
│  - OpenAI → Anthropic 响应转换                                               │
│  - 流式响应转换 (SSE)                                                        │
│                                                                              │
│  关键文件:                                                                   │
│    - src/server/proxy/handler.ts (代理入口)                                   │
│    - src/server/proxy/transform/anthropicToOpenaiChat.ts                     │
│    - src/server/proxy/transform/openaiChatToAnthropic.ts                     │
│    - src/server/proxy/streaming/openaiChatStreamToAnthropic.ts               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 各层职责

| 层级 | 职责 | 核心操作 |
|------|------|----------|
| Layer 4 | 用户交互 | 选择 Provider/Model |
| Layer 3 | 业务编排 | 会话管理、Provider 管理 |
| Layer 2 | 环境准备 | 构建 CLI 子进程环境变量 |
| Layer 1 | 协议转换 | Anthropic ↔ OpenAI 格式转换 |

---

## 六、结构层级

### 6.1 项目目录结构

```
cc-haha/
├── src/
│   ├── adapters/                    # IM 适配器层
│   │   ├── common/
│   │   │   ├── ws-bridge.ts         # WebSocket 桥接
│   │   │   ├── message-buffer.ts   # 消息缓冲
│   │   │   └── format.ts            # 消息格式化
│   │   └── feishu/
│   │       └── index.ts             # 飞书适配器
│   │
│   ├── server/                     # 核心服务层
│   │   ├── ws/
│   │   │   ├── handler.ts           # WebSocket 处理
│   │   │   └── events.ts            # 事件类型
│   │   │
│   │   ├── services/               # 业务服务
│   │   │   ├── conversationService.ts   # 会话管理 + CLI 启动
│   │   │   ├── providerService.ts       # Provider CRUD
│   │   │   ├── sessionService.ts        # 会话元数据
│   │   │   ├── providerRuntimeEnv.ts    # 环境变量构建
│   │   │   └── settingsService.ts       # 设置管理
│   │   │
│   │   ├── proxy/                   # 协议转换代理
│   │   │   ├── handler.ts           # 代理入口
│   │   │   ├── transform/           # 格式转换
│   │   │   │   ├── anthropicToOpenaiChat.ts
│   │   │   │   ├── openaiChatToAnthropic.ts
│   │   │   │   └── types.ts
│   │   │   └── streaming/           # 流式转换
│   │   │       └── openaiChatStreamToAnthropic.ts
│   │   │
│   │   ├── config/
│   │   │   ├── providerPresets.ts       # Provider 预设
│   │   │   └── providerPresets.json     # 预设 JSON
│   │   │
│   │   └── types/
│   │       └── provider.ts          # Provider 类型定义
│   │
│   ├── tools/                       # 内置工具
│   │   ├── SkillTool/
│   │   └── ...
│   │
│   └── history.ts                   # 历史记录管理
│
└── ...
```

---

## 七、场景推理

### 场景 1: 用户首次启动，选择 DeepSeek Provider

```
用户操作:
  1. 打开 cc-haha Desktop
  2. 进入设置 → Provider → 添加 Provider
  3. 选择 "DeepSeek" 预设
  4. 输入 API Key: sk-xxxxx
  5. 点击 "激活"

系统处理:
  providerService.addProvider()      // 保存 Provider 配置
  providerService.activateProvider() // 激活 Provider
  ├─ 保存到 ~/.claude/cc-haha/providers.json
  └─ 写入 ~/.claude/cc-haha/settings.json
     {
       "env": {
         "ANTHROPIC_BASE_URL": "http://127.0.0.1:3456/proxy/providers/{uuid}",
         "ANTHROPIC_AUTH_TOKEN": "sk-xxxxx",
         "ANTHROPIC_MODEL": "deepseek-v4-pro",
         "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash",
         "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-pro",
         "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-pro"
       }
     }

结果:
  Provider 配置持久化到磁盘
  后续 CLI 启动时读取此配置
```

### 场景 2: 创建新会话，CLI 使用 DeepSeek

```
用户操作:
  1. 创建新会话
  2. IM 界面发起 WebSocket 连接
  3. 发送 connect 消息

系统处理:
  ws/handler.ts::handleConnect()
  └─ conversationService.startSession()
     └─ buildChildEnv()
        ├─ 读取 ~/.claude/cc-haha/providers.json
        ├─ 获取当前激活的 Provider (DeepSeek)
        ├─ providerService.getProviderRuntimeEnv("deepseek-uuid")
        │  └─ 返回环境变量:
        │     ANTHROPIC_BASE_URL: "http://127.0.0.1:3456/proxy/providers/deepseek-uuid"
        │     ANTHROPIC_AUTH_TOKEN: "sk-xxxxx"
        │     ANTHROPIC_MODEL: "deepseek-v4-pro"
        ├─ Bun.spawn(claude, { env: childEnv })
        └─ CLI 子进程启动

CLI 行为:
  1. 读取环境变量
  2. 发现 ANTHROPIC_BASE_URL 指向本地代理
  3. 发送 API 请求到本地代理
  4. 本地代理转发到 DeepSeek API
```

### 场景 3: 会话进行中，切换模型

```
用户操作:
  1. 在会话中输入 "/model deepseek-v4-flash"
  2. IM 界面解析命令
  3. 发送 WebSocket 消息: { type: "set_runtime_config", modelId: "deepseek-v4-flash" }

系统处理:
  ws/handler.ts::handleSetRuntimeConfig()
  ├─ 更新 runtimeOverrides.set(sessionId, { modelId: "deepseek-v4-flash" })
  ├─ conversationService.stopSession()        // 停止当前 CLI
  ├─ getRuntimeSettings()                    // 获取新的运行时设置
  │  └─ 返回: { providerId: "deepseek-uuid", model: "deepseek-v4-flash" }
  └─ conversationService.startSession()       // 使用新模型重启
     └─ buildChildEnv()
        └─ explicitProviderEnv.ANTHROPIC_MODEL = "deepseek-v4-flash"

CLI 重启:
  1. 新 CLI 子进程使用 deepseek-v4-flash 模型
  2. 旧会话的上下文通过 --resume 恢复
```

### 场景 4: 不同会话使用不同模型

```
会话 A:
  sessionId: "session-aaa"
  providerId: "deepseek-uuid"     → DeepSeek Provider
  model: "deepseek-v4-pro"

会话 B:
  sessionId: "session-bbb"
  providerId: "kimi-uuid"         → Kimi Provider
  model: "kimi-k2.6"

会话 C:
  sessionId: "session-ccc"
  providerId: "ollama-uuid"       → Ollama (本地模型)
  model: "qwen3.6:27b"

实现机制:
  runtimeOverrides: Map<sessionId, { providerId, modelId }>
  
  每个会话独立存储运行时配置：
    session-aaa → { providerId: "deepseek-uuid", modelId: "deepseek-v4-pro" }
    session-bbb → { providerId: "kimi-uuid", modelId: "kimi-k2.6" }
    session-ccc → { providerId: "ollama-uuid", modelId: "qwen3.6:27b" }

  CLI 子进程环境变量独立：
    Session A ENV: ANTHROPIC_BASE_URL → /proxy/providers/deepseek-uuid
    Session B ENV: ANTHROPIC_BASE_URL → /proxy/providers/kimi-uuid
    Session C ENV: ANTHROPIC_BASE_URL → /proxy/providers/ollama-uuid
```

### 场景 5: API Format 转换 (DeepSeek 不需要转换)

```
Provider: DeepSeek
  baseUrl: "https://api.deepseek.com/anthropic"
  apiFormat: "anthropic"  ← 直接使用 Anthropic 协议

流程:
  CLI 发送 (Anthropic 格式):
    POST /anthropic/v1/messages
    {
      "model": "deepseek-v4-pro",
      "messages": [...]
    }

  Proxy Handler 判断:
    config.apiFormat === "anthropic" → 直接转发，不转换

  请求转发:
    → POST https://api.deepseek.com/anthropic/v1/messages
    (保持 Anthropic 格式)
```

### 场景 6: API Format 转换 (OpenAI Chat 格式需要转换)

```
Provider: 自定义 Provider (OpenAI 兼容)
  baseUrl: "https://api.openai.com/v1"
  apiFormat: "openai_chat"

流程:
  CLI 发送 (Anthropic 格式):
    POST /anthropic/v1/messages
    { "model": "gpt-4o", "messages": [...], "tools": [...] }

  Proxy Handler 转换 (anthropicToOpenaiChat):
    {
      "model": "gpt-4o",
      "messages": [
        { "role": "system", "content": "..." },
        { "role": "user", "content": "..." }
      ],
      "tools": [
        { "type": "function", "function": { "name": "...", ... } }
      ]
    }

  请求转发:
    → POST https://api.openai.com/v1/chat/completions
    (OpenAI Chat 格式)

  响应转换 (openaiChatToAnthropic):
    OpenAI Response:
      { "choices": [{ "message": { "content": "..." } }] }
    
    → Anthropic Response:
      { "content": [{ "type": "text", "text": "..." }] }
```

### 场景 7: 使用本地模型 (Ollama/LM Studio)

```
Provider: Ollama
  baseUrl: "http://localhost:11434"
  apiFormat: "anthropic"
  authStrategy: "auth_token_empty_api_key"
  
配置:
  ANTHROPIC_AUTH_TOKEN: "ollama"  (占位符，不需要真实 Token)

流程:
  CLI → Proxy Handler → Ollama API
  注意: 本地模型可能不支持 Claude Code 的所有工具和 Skill
```

---

## 八、关键代码路径

### 8.1 Provider 运行时环境构建

```typescript
// providerRuntimeEnv.ts::buildProviderManagedEnv()
export function buildProviderManagedEnv(
  provider: SavedProvider,
  options?: { proxyPath?: string; serverPort?: number },
): Record<string, string> {
  
  // 1. 判断是否需要代理
  const needsProxy = provider.apiFormat !== 'anthropic'
  
  // 2. 构建 baseUrl
  const baseUrl = needsProxy
    ? `http://127.0.0.1:${serverPort}${proxyPath}`  // 指向本地代理
    : provider.baseUrl                              // 直接指向 Provider API
  
  // 3. 构建认证环境变量
  const authEnv = buildProviderAuthEnv(provider, presetDefaultEnv, needsProxy)
  
  // 4. 返回完整环境变量
  return {
    ANTHROPIC_BASE_URL: baseUrl,
    ...authEnv,
    ANTHROPIC_MODEL: models.main,
    ANTHROPIC_DEFAULT_HAIKU_MODEL: models.haiku,
    ANTHROPIC_DEFAULT_SONNET_MODEL: models.sonnet,
    ANTHROPIC_DEFAULT_OPUS_MODEL: models.opus,
  }
}
```

### 8.2 CLI 子进程环境注入

```typescript
// conversationService.ts::buildChildEnv()
private async buildChildEnv(
  workDir: string,
  sdkUrl?: string,
  options?: SessionStartOptions,
): Promise<Record<string, string>> {
  
  // 1. 获取 Provider 运行时环境
  const explicitProviderEnv =
    typeof options?.providerId === 'string'
      ? await this.providerService.getProviderRuntimeEnv(options.providerId)
      : null
  
  // 2. 如果显式指定了模型，覆盖 Provider 配置
  if (explicitProviderEnv && options?.model?.trim()) {
    explicitProviderEnv.ANTHROPIC_MODEL = options.model.trim()
  }
  
  // 3. 构建完整环境变量
  return {
    ...cleanEnv,
    CLAUDE_CODE_ENABLE_TASKS: '1',
    CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING: '1',
    CALLER_DIR: workDir,
    PWD: workDir,
    ...(explicitProviderEnv ?? {}),  // 注入 Provider 环境变量
    ...networkEnv,
    ...attributionHeaderEnv,
  }
}
```

### 8.3 Proxy 请求路由

```typescript
// proxy/handler.ts::handleProxyRequest()
export async function handleProxyRequest(req: Request, url: URL): Promise<Response> {
  
  // 1. 解析 Provider ID
  const providerMatch = url.pathname.match(/^\/proxy\/providers\/([^/]+)\/v1\/messages$/)
  const providerId = providerMatch ? decodeURIComponent(providerMatch[1]) : undefined
  
  // 2. 获取 Provider 配置
  const config = await providerService.getProviderForProxy(providerId)
  
  // 3. 根据 API Format 选择处理函数
  if (config.apiFormat === 'openai_chat') {
    return handleOpenaiChat(body, baseUrl, config.apiKey, isStream, ...)
  } else if (config.apiFormat === 'openai_responses') {
    return handleOpenaiResponses(body, baseUrl, config.apiKey, isStream, ...)
  } else {
    // Anthropic 格式，直接转发
    return forwardToAnthropic(body, baseUrl, config.apiKey, isStream, ...)
  }
}
```

---

## 九、总结

### cc-haha 多模型支持的核心机制

1. **环境变量注入**：通过 `ANTHROPIC_BASE_URL` 让 CLI 以为在调用 Anthropic API，实际调用本地代理
2. **Provider 配置管理**：每个 Provider 独立配置 API 地址、API Key、模型映射
3. **会话级隔离**：通过 `runtimeOverrides` Map，每个会话独立存储 Provider 和 Model 选择
4. **协议转换代理**：支持 Anthropic、OpenAI Chat、OpenAI Responses 三种 API 格式
5. **模型槽位映射**：支持 main/haiku/sonnet/opus 四个槽位，CLI 自动选择

### 每个会话不同模型的实现

```typescript
// 会话配置独立存储
runtimeOverrides: Map<sessionId, { providerId, modelId }>

// CLI 子进程环境独立注入
Session A: { ANTHROPIC_BASE_URL: "/proxy/providers/deepseek-uuid", ... }
Session B: { ANTHROPIC_BASE_URL: "/proxy/providers/kimi-uuid", ... }
Session C: { ANTHROPIC_BASE_URL: "/proxy/providers/ollama-uuid", ... }
```

### 与 AgentPipe 的对比

| 维度 | cc-haha | AgentPipe |
|------|---------|-----------|
| 多模型支持 | ✅ 无限 (任何 Provider) | ✅ 有限 (OpenRouter) |
| 模型粒度 | ✅ 会话级独立 | ❌ 全部会话统一 |
| CLI 原生能力 | ✅ 完整保留 | ❌ 无 CLI |
| 工具/Skill | ✅ 完整保留 | ❌ 无 |
| 架构复杂度 | 高 | 低 |
