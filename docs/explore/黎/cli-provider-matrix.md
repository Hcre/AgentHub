# CLI × Provider 连接矩阵

## 每种 CLI 连接每种 Provider 的方式

### Claude CLI

入口：spawn `claude --output-format stream-json`

| Provider | base_url | 协议 | API Key 位置 | 模型名格式 |
|----------|----------|------|-------------|-----------|
| **DeepSeek** | `https://api.deepseek.com/anthropic` | Anthropic Messages | `x-api-key` header | `claude-sonnet-4-20250514` 等 (Anthropic 模型名) |
| **Anthropic** | `https://api.anthropic.com` | Anthropic Messages | `x-api-key` header | `claude-sonnet-4-20250514` 等 |
| **OpenAI** | ❌ 不支持 | — | — | — |
| **硅基流动** | `https://api.siliconflow.cn/anthropic` | Anthropic Messages | `x-api-key` header | Anthropic 模型名 |
| **其他 Anthropic 兼容** | 自定义 | Anthropic Messages | `x-api-key` header | 自定义模型名 |

Key 注入方式：`ANTHROPIC_BASE_URL={proxy}` + `ANTHROPIC_API_KEY=placeholder` → AgentHub proxy 替换 key 后转发到目标 base_url

文件操作：✅ (CLI 自带 Read/Write/Bash)

---

### Pi CLI

入口：spawn `pi --mode rpc --provider {provider} --model {model}`

| Provider | --provider 参数 | env var | 协议 | base_url |
|----------|----------------|---------|------|----------|
| **DeepSeek** | `deepseek` | `DEEPSEEK_API_KEY` | OpenAI Completions | CLI 内置 |
| **Anthropic** | `anthropic` | `ANTHROPIC_API_KEY` | Anthropic Messages | CLI 内置 |
| **OpenAI** | `openai` | `OPENAI_API_KEY` | OpenAI Completions | CLI 内置 |
| **Google** | `google` | `GEMINI_API_KEY` | Gemini | CLI 内置 |
| **硅基流动** | `openai` (需手动设 base_url) | `OPENAI_API_KEY` | OpenAI Completions | 需设 `OPENAI_BASE_URL` |
| **Groq** | `groq` | `GROQ_API_KEY` | OpenAI Completions | CLI 内置 |

Key 注入方式：环境变量（CLI 内置 provider 自动处理 endpoint），不需要 AgentHub 传 base_url

文件操作：✅ (CLI 自带 Read/Write/Bash/Edit)

模型名：直接传真实模型名，如 `deepseek-chat`, `claude-sonnet-4-20250514`, `gpt-4o`

---

### OpenCode CLI

入口：spawn `opencode run --format json --model {provider/model} --dir {workspace}`

| Provider | 模型前缀 | env var | 配置方式 | base_url |
|----------|---------|---------|---------|----------|
| **DeepSeek** | `deepseek/` | `DEEPSEEK_API_KEY` | opencode.jsonc + `@ai-sdk/openai-compatible` | `https://api.deepseek.com` |
| **Anthropic** | `anthropic/` | `ANTHROPIC_API_KEY` | opencode.jsonc + `@ai-sdk/anthropic` | `https://api.anthropic.com` |
| **OpenAI** | `openai/` | `OPENAI_API_KEY` | opencode.jsonc + `@ai-sdk/openai` | `https://api.openai.com` |
| **OpenCode 免费** | `opencode/` | 不需要 | 内置 | CLI 内置 |

Key 注入方式：环境变量 + 预写 `~/.config/opencode/opencode.jsonc` 配置文件（含 provider 定义和 `{env:XXX}` 引用）

文件操作：✅ (CLI 自带工具系统)

模型名：格式为 `{provider}/{model}`，如 `deepseek/deepseek-v4-pro`

---

### 三种 CLI 汇总

| | Claude CLI | Pi CLI | OpenCode |
|---|---|---|---|
| **协议支持** | 仅 Anthropic | Anthropic + OpenAI + 多 provider | 需按 provider 装对应 SDK 包 |
| **base_url 管理** | AgentHub proxy 统一路由 | CLI 内置，不需传 | 需预写 jsonc 配置文件 |
| **Key 注入** | env var → proxy 替换 | env var → CLI 直读 | env var + jsonc `{env:XXX}` |
| **模型名格式** | 原始模型名 | 原始模型名 | `provider/model` |
| **文件操作** | ✅ | ✅ | ✅ |
| **扩展新 provider** | proxy 配置 | pi CLI 可能已支持 | 改 jsonc + 装对应 npm 包 |
| **无 CLI 降级** | HTTP API (proxy) | HTTP API (ClaudeAdapter) | HTTP API (ClaudeAdapter) |

---

## 通用前端方案

### 核心思路

**用户只填提供商标识 + Key，其他由 CLI 自适应。**

### Step 2 改版

```
┌─────────────────────────────────────────────────┐
│ 第二步：配置 Provider 和运行时                    │
├─────────────────────────────────────────────────┤
│                                                 │
│  选择 Provider                                  │
│  ┌─────────────────────────────────────────┐    │
│  │ DeepSeek                           [▼]  │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  API Key                                        │
│  ┌─────────────────────────────────────────┐    │
│  │ sk-d361e6e293...                  [👁]   │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  或从已保存配置选择:                              │
│  ┌─────────────────────────────────────────┐    │
│  │ 我的 DeepSeek · sk-d361****         [▼] │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  ───────────────────────────────────────        │
│                                                 │
│  运行依赖 (自动扫描 PATH)            [重新扫描]   │
│  ┌─────────────────────────────────────────┐    │
│  │ Claude Code · v2.1.153            [▼]   │    │
│  └─────────────────────────────────────────┘    │
│  扫描完成，3 个可用                               │
│                                                 │
│  ┌─ 当前 CLI 连接信息 ──────────────────────┐    │
│  │                                         │    │
│  │  协议:   OpenAI Completions             │    │
│  │  端点:   https://api.deepseek.com       │    │
│  │  模型:   deepseek-chat             [▼]  │    │
│  │          deepseek-v4-pro               │    │
│  │          deepseek-v4-flash             │    │
│  │         (由 CLI 自动提供)                │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│                             [上一步] [创建队友]  │
└─────────────────────────────────────────────────┘
```

### 核心逻辑：Provider × CLI → 自动填配置

```typescript
// cliProviderConfig.ts — 前端唯一配置表

interface CliProviderConfig {
  protocol: string           // "Anthropic Messages" | "OpenAI Completions"
  baseUrl: string            // 默认端点
  envVar: string             // 需要的环境变量名
  modelPrefix: string        // 模型名前缀（opencode 需要 "deepseek/"）
  defaultModels: string[]    // 默认模型列表
  needsProxy: boolean        // 是否需要走 AgentHub proxy
}

// provider=deepseek 时，不同 CLI 的配置：
const DEEPSEEK_CONFIG: Record<string, CliProviderConfig> = {
  claude_code: {
    protocol:   "Anthropic Messages",
    baseUrl:    "https://api.deepseek.com/anthropic",
    envVar:     "ANTHROPIC_API_KEY",
    modelPrefix: "",
    defaultModels: ["claude-sonnet-4-20250514", "deepseek-chat"],
    needsProxy: true,
  },
  pi_agent: {
    protocol:   "OpenAI Completions",
    baseUrl:    "https://api.deepseek.com",      // CLI 内置，仅展示
    envVar:     "DEEPSEEK_API_KEY",
    modelPrefix: "",
    defaultModels: ["deepseek-chat", "deepseek-v4-pro"],
    needsProxy: false,
  },
  opencode: {
    protocol:   "OpenAI Completions",
    baseUrl:    "https://api.deepseek.com",
    envVar:     "DEEPSEEK_API_KEY",
    modelPrefix: "deepseek/",
    defaultModels: ["deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash"],
    needsProxy: false,
  },
}
```

### 后端参数传递

创建 Agent 时只需传：

```json
{
  "name": "编辑",
  "system_prompt": "...",
  "skills": ["..."],

  "provider": "deepseek",
  "api_key": "sk-d361...",
  "model": "deepseek-v4-pro",

  "agent_system": "pi_agent"   // 用户选的 CLI
}
```

后端的 `factory.py` 根据 `agent_system` + `provider` 查表构建正确的 Runtime，自动处理 base_url、协议、key 注入方式。
