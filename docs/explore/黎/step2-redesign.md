# Step 2 重新设计方案

## 新流程

```
Step 1（选模板）→ Step 2（配置+连通预检）→ Step 3（创建）

Step 2 内部:
  ┌─────────────────────────────────────────────┐
  │          创建队友 · 2/3                      │
  ├─────────────────────────────────────────────┤
  │                                             │
  │  ① 选 CLI（自动扫描 PATH）         [重新扫描] │
  │  ┌─────────────────────────────────────┐    │
  │  │ Pi Agent · v0.74.2            [▼]   │    │
  │  └─────────────────────────────────────┘    │
  │  扫描完成，3 个可用                           │
  │                                             │
  │  ② 选择已保存的 Provider 配置     [管理配置]  │
  │  ┌─────────────────────────────────────┐    │
  │  │ DeepSeek · sk-d361****        [▼]   │    │
  │  └─────────────────────────────────────┘    │
  │                                             │
  │  ┌─ 自动加载 ──────────────────────────┐    │
  │  │  提供商标识:  deepseek              │    │
  │  │  协议格式:    OpenAI Completions    │    │
  │  │  Base URL:    https://api.deepseek. │    │
  │  │              com                   │    │
  │  │  模型:        deepseek-chat   [▼]  │    │
  │  │  环境变量:    DEEPSEEK_API_KEY      │    │
  │  │                                    │    │
  │  │  (根据所选 CLI 自动推导，可手动修改)  │    │
  │  └────────────────────────────────────┘    │
  │                                             │
  │  ┌─────────────────────────────────────┐    │
  │  │     [🔄 连通性测试]                  │    │
  │  │                                     │    │
  │  │  空闲态: 按钮可用，点击发起测试       │    │
  │  │  测试中: 显示"连通性测试中…"         │    │
  │  │  成功:   ✅ 连通成功 · 23ms          │    │
  │  │  失败:   ❌ 401 认证失败             │    │
  │  │          → 检查 API Key 是否正确     │    │
  │  │          → 修改后点重试              │    │
  │  └─────────────────────────────────────┘    │
  │                                             │
  │                [上一步]    [✨ 创建队友]     │
  └─────────────────────────────────────────────┘
```

## 和旧方案的区别

| | 旧方案 | 新方案 |
|---|---|---|
| **连通测试时机** | 创建之后（Step 3） | 创建之前（Step 2 底部） |
| **测试失败后果** | 回滚：删 Agent + 关对话 | 原地修改配置，重试即可 |
| **base_url 填写** | 用户手动填 | CLI + Provider 自动推导 |
| **协议格式** | 不展示 | 自动展示（OpenAI/Anthropic） |
| **步骤进度** | 无 | 显示 "2/3" |

## CLI × Provider 自动推导表

前端查这张表，选完 CLI 和保存配置后自动填：

```typescript
const CLI_PROVIDER_MATRIX: Record<string, Record<string, {
  protocol: string
  baseUrl: string
  envVar: string
  modelPrefix: string
  models: string[]
}>> = {
  claude_code: {
    deepseek: {
      protocol: "Anthropic Messages",
      baseUrl: "https://api.deepseek.com/anthropic",
      envVar: "ANTHROPIC_API_KEY",
      modelPrefix: "",
      models: ["claude-sonnet-4-20250514", "claude-haiku-4-5"],
    },
    anthropic: {
      protocol: "Anthropic Messages",
      baseUrl: "https://api.anthropic.com",
      envVar: "ANTHROPIC_API_KEY",
      modelPrefix: "",
      models: ["claude-sonnet-4-20250514", "claude-opus-4-7", "claude-haiku-4-5"],
    },
  },
  pi_agent: {
    deepseek: {
      protocol: "OpenAI Completions",
      baseUrl: "https://api.deepseek.com",
      envVar: "DEEPSEEK_API_KEY",
      modelPrefix: "",
      models: ["deepseek-chat", "deepseek-v4-pro", "deepseek-v4-flash"],
    },
    anthropic: {
      protocol: "Anthropic Messages",
      baseUrl: "https://api.anthropic.com",
      envVar: "ANTHROPIC_API_KEY",
      modelPrefix: "",
      models: ["claude-sonnet-4-20250514", "claude-opus-4-7"],
    },
    openai: {
      protocol: "OpenAI Completions",
      baseUrl: "https://api.openai.com",
      envVar: "OPENAI_API_KEY",
      modelPrefix: "",
      models: ["gpt-4o", "gpt-4o-mini"],
    },
  },
  opencode: {
    deepseek: {
      protocol: "OpenAI Completions",
      baseUrl: "https://api.deepseek.com",
      envVar: "DEEPSEEK_API_KEY",
      modelPrefix: "deepseek/",
      models: ["deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash"],
    },
    anthropic: {
      protocol: "Anthropic Messages",
      baseUrl: "https://api.anthropic.com",
      envVar: "ANTHROPIC_API_KEY",
      modelPrefix: "anthropic/",
      models: ["anthropic/claude-sonnet-4-20250514"],
    },
  },
}
```

## 连通性测试（预检模式）

```
点 [🔄 连通性测试]
  │
  ├─ 1. POST /api/providers/ping
  │     body: { agent_system, provider, model, api_key, base_url }
  │
  ├─ 2. 后端 spawn CLI 子进程发 "ping"
  │     → 收到回复 → 返回 { ok: true, latency_ms: 230 }
  │     → 超时/报错  → 返回 { ok: false, error: "401 Unauthorized" }
  │
  ├─ 3. 成功 → 按钮变绿 ✅ 连通成功 · 230ms
  │    失败 → 按钮变红 ❌ + 错误详情（Key 错误？端点不通？）
  │           → 用户修改配置 → 点 [重试]
  │
  └─ 4. 创建 Agent 时不再做连通测试（已在 Step 2 验证过）
```

## 新增后端端点

```
POST /api/providers/ping
  body: {
    agent_system: "pi_agent",
    provider: "deepseek",
    model: "deepseek-chat",
    api_key: "sk-d361...",
    base_url: "https://api.deepseek.com"
  }
  → spawn CLI, send "ping", wait for response
  → 200 { ok: true, latency_ms: 230 }
  → 或 { ok: false, error: "401: invalid api key" }
```

## 实施步骤

1. **前端**：`CreateAgentModal.tsx` Step 2 重构
   - 加步骤进度 "2/3"
   - 加自动推导展示区
   - 加连通测试按钮 + 状态区
   - 从 `doCreate` 移除连通测试逻辑

2. **前端**：新增 `CLI_PROVIDER_MATRIX` 配置表
   - 文件：`frontend/src/data/cliProviderMatrix.ts`

3. **后端**：新增 `POST /api/providers/ping`
   - 文件：`backend/app/api/routers/providers.py`
