# 四 Provider × 三 CLI 配置矩阵（修订版）

## Provider API 端点汇总

| Provider | OpenAI Base URL | Anthropic Base URL | Key 格式 | 备注 |
|----------|----------------|-------------------|---------|------|
| **DeepSeek** | `https://api.deepseek.com` | `https://api.deepseek.com/anthropic` | `sk-xxx` | 两个端点同一把 key |
| **Xiaomi MiMo** | `https://token-plan-cn.xiaomimimo.com/v1` | `https://token-plan-cn.xiaomimimo.com/anthropic` | `tp-xxx` (Token Plan) | 可选国际端点 `api.xiaomimimo.com` |
| **MiniMax** | `https://api.minimaxi.com/v1` | `https://api.minimaxi.com/anthropic` | 标准 key | ⚠️ OpenAI 和 Anthropic 需要**不同类型的 key** |
| **Anthropic** | — (不适用) | `https://api.anthropic.com` | `sk-ant-xxx` | 原生 Anthropic |

> 注：MiniMax 国际端点为 `api.minimax.io`，国内为 `api.minimaxi.com`

---

## Provider × CLI 完整矩阵

### 1. DeepSeek

| CLI | 协议 | Base URL | Key Env Var | 直连/Proxy | 模型名格式 |
|-----|------|----------|------------|-----------|-----------|
| **Claude CLI** | Anthropic | `https://api.deepseek.com/anthropic` | `ANTHROPIC_API_KEY` | **Proxy** 透传 | `claude-sonnet-4-20250514` |
| **Pi CLI** | OpenAI | CLI 内置 | `DEEPSEEK_API_KEY` | **直连** | `deepseek-chat`, `deepseek-v4-pro` |
| **OpenCode** | OpenAI | `https://api.deepseek.com` | `DEEPSEEK_API_KEY` | **直连** | `deepseek/deepseek-v4-pro` |

Pi CLI 命令：`pi --mode rpc --provider deepseek --model deepseek-v4-pro`

---

### 2. Xiaomi MiMo

| CLI | 协议 | Base URL | Key Env Var | 直连/Proxy | 模型名格式 |
|-----|------|----------|------------|-----------|-----------|
| **Claude CLI** | Anthropic | `https://token-plan-cn.xiaomimimo.com/anthropic` | `ANTHROPIC_AUTH_TOKEN` | **Proxy** 透传 | `mimo-v2.5-pro` |
| **Pi CLI** | OpenAI | CLI 内置 | `XIAOMI_TOKEN_PLAN_CN_API_KEY` | **直连** | `mimo-v2.5-pro`, `mimo-v2-flash` |
| **OpenCode** | OpenAI | `https://token-plan-cn.xiaomimimo.com/v1` | `XIAOMI_TOKEN_PLAN_CN_API_KEY` | **直连** | `xiaomi/mimo-v2.5-pro` |

Pi CLI 命令：`pi --mode rpc --provider xiaomi --model mimo-v2.5-pro`

⚠️ Claude CLI 用 `ANTHROPIC_AUTH_TOKEN`（不是 `ANTHROPIC_API_KEY`），MiMo 要求 auth header 用 Bearer token 格式。

---

### 3. MiniMax

| CLI | 协议 | Base URL | Key Env Var | 直连/Proxy | 模型名格式 |
|-----|------|----------|------------|-----------|-----------|
| **Claude CLI** | Anthropic | `https://api.minimaxi.com/anthropic` | `ANTHROPIC_AUTH_TOKEN` | **Proxy** 透传 | `MiniMax-M2.7` |
| **Pi CLI** | OpenAI | CLI 内置 | `MINIMAX_API_KEY` | **直连** | `MiniMax-M2.7` |
| **OpenCode** | OpenAI | `https://api.minimaxi.com/v1` | `MINIMAX_API_KEY` | **直连** | `minimax/MiniMax-M2.7` |

Pi CLI 命令：`pi --mode rpc --provider minimax --model MiniMax-M2.7`

⚠️ **关键限制**：MiniMax 的 OpenAI 端点和 Anthropic 端点需要**不同类型的 API key**（Coding Plan key 用于 Anthropic，Standard key 用于 OpenAI）。同一把 key 不能同时在两个端点使用。

---

### 4. Anthropic (Claude)

| CLI | 协议 | Base URL | Key Env Var | 直连/Proxy | 模型名格式 |
|-----|------|----------|------------|-----------|-----------|
| **Claude CLI** | Anthropic | `https://api.anthropic.com` | `ANTHROPIC_API_KEY` | **直连** | `claude-sonnet-4-20250514` |
| **Pi CLI** | Anthropic | CLI 内置 | `ANTHROPIC_API_KEY` | **直连** | `claude-sonnet-4-20250514` |
| **OpenCode** | Anthropic | `https://api.anthropic.com` | `ANTHROPIC_API_KEY` | **直连** | `anthropic/claude-sonnet-4-20250514` |

Pi CLI 命令：`pi --mode rpc --provider anthropic --model claude-sonnet-4-20250514`

---

## 前端推导表（TypeScript）

```typescript
interface CliProviderEntry {
  protocol: 'Anthropic Messages' | 'OpenAI Completions'
  baseUrl: string
  envVar: string           // AgentHub 注入的环境变量名
  needsProxy: boolean      // 是否需要 AgentHub proxy
  modelPrefix: string      // opencode 需要 provider/ 前缀
  models: string[]
  note?: string            // 提示信息
}

const CLI_PROVIDER_MATRIX: Record<string, Record<string, CliProviderEntry>> = {
  // ── Claude CLI ──
  claude_code: {
    deepseek: {
      protocol: 'Anthropic Messages',
      baseUrl: 'https://api.deepseek.com/anthropic',
      envVar: 'ANTHROPIC_API_KEY',
      needsProxy: true,
      modelPrefix: '',
      models: ['claude-sonnet-4-20250514', 'claude-haiku-4-5'],
    },
    xiaomi: {
      protocol: 'Anthropic Messages',
      baseUrl: 'https://token-plan-cn.xiaomimimo.com/anthropic',
      envVar: 'ANTHROPIC_AUTH_TOKEN',     // ← MiMo 用 AUTH_TOKEN
      needsProxy: true,
      modelPrefix: '',
      models: ['mimo-v2.5-pro', 'mimo-v2-flash'],
    },
    minimax: {
      protocol: 'Anthropic Messages',
      baseUrl: 'https://api.minimaxi.com/anthropic',
      envVar: 'ANTHROPIC_AUTH_TOKEN',
      needsProxy: true,
      modelPrefix: '',
      models: ['MiniMax-M2.7'],
      note: '需 Coding Plan 类型 Key，Standard Key 不可用',
    },
    anthropic: {
      protocol: 'Anthropic Messages',
      baseUrl: 'https://api.anthropic.com',
      envVar: 'ANTHROPIC_API_KEY',
      needsProxy: false,                   // ← 原生直连
      modelPrefix: '',
      models: ['claude-sonnet-4-20250514', 'claude-opus-4-7', 'claude-haiku-4-5'],
    },
  },

  // ── Pi CLI ──
  pi_agent: {
    deepseek: {
      protocol: 'OpenAI Completions',
      baseUrl: 'https://api.deepseek.com',
      envVar: 'DEEPSEEK_API_KEY',
      needsProxy: false,
      modelPrefix: '',
      models: ['deepseek-v4-pro', 'deepseek-v4-flash', 'deepseek-chat'],
    },
    xiaomi: {
      protocol: 'OpenAI Completions',
      baseUrl: 'https://token-plan-cn.xiaomimimo.com/v1',
      envVar: 'XIAOMI_TOKEN_PLAN_CN_API_KEY',
      needsProxy: false,
      modelPrefix: '',
      models: ['mimo-v2.5-pro', 'mimo-v2-flash'],
    },
    minimax: {
      protocol: 'OpenAI Completions',
      baseUrl: 'https://api.minimaxi.com/v1',
      envVar: 'MINIMAX_API_KEY',
      needsProxy: false,
      modelPrefix: '',
      models: ['MiniMax-M2.7'],
      note: '需 Standard 类型 Key，Coding Plan Key 不可用',
    },
    anthropic: {
      protocol: 'Anthropic Messages',
      baseUrl: 'https://api.anthropic.com',
      envVar: 'ANTHROPIC_API_KEY',
      needsProxy: false,
      modelPrefix: '',
      models: ['claude-sonnet-4-20250514', 'claude-opus-4-7', 'claude-haiku-4-5'],
    },
  },

  // ── OpenCode CLI ──
  opencode: {
    deepseek: {
      protocol: 'OpenAI Completions',
      baseUrl: 'https://api.deepseek.com',
      envVar: 'DEEPSEEK_API_KEY',
      needsProxy: false,
      modelPrefix: 'deepseek/',
      models: ['deepseek/deepseek-v4-pro', 'deepseek/deepseek-v4-flash'],
    },
    xiaomi: {
      protocol: 'OpenAI Completions',
      baseUrl: 'https://token-plan-cn.xiaomimimo.com/v1',
      envVar: 'XIAOMI_TOKEN_PLAN_CN_API_KEY',
      needsProxy: false,
      modelPrefix: 'xiaomi/',
      models: ['xiaomi/mimo-v2.5-pro', 'xiaomi/mimo-v2-flash'],
      note: '需在 opencode.jsonc 配置 @ai-sdk/openai-compatible',
    },
    minimax: {
      protocol: 'OpenAI Completions',
      baseUrl: 'https://api.minimaxi.com/v1',
      envVar: 'MINIMAX_API_KEY',
      needsProxy: false,
      modelPrefix: 'minimax/',
      models: ['minimax/MiniMax-M2.7'],
      note: '需在 opencode.jsonc 配置 @ai-sdk/openai-compatible',
    },
    anthropic: {
      protocol: 'Anthropic Messages',
      baseUrl: 'https://api.anthropic.com',
      envVar: 'ANTHROPIC_API_KEY',
      needsProxy: false,
      modelPrefix: 'anthropic/',
      models: ['anthropic/claude-sonnet-4-20250514'],
    },
  },
}
```

## 关键差异点

### 1. Claude CLI 为什么几乎全走 Proxy？

Claude CLI 只支持 Anthropic 协议。非 Anthropic 的 provider（DeepSeek、MiMo、MiniMax）都有 Anthropic 兼容端点，但 Claude CLI 自己不管 key 注入 — 它只认 `ANTHROPIC_API_KEY` 和 `ANTHROPIC_BASE_URL`。

**Proxy 的作用不是转协议，是换 key + 换 endpoint。** Proxy 收到 Claude CLI 的请求 → 取 agent 的真实 key → 发给 provider 的 Anthropic 端点。

### 2. MiMo 和 MiniMax 用 `ANTHROPIC_AUTH_TOKEN` 而非 `ANTHROPIC_API_KEY`

这是 Anthropic 兼容端点的两种认证方式：
- `x-api-key: sk-xxx` — Anthropic 原生格式，DeepSeek 兼容
- `Authorization: Bearer xxx` — Bearer token 格式，MiMo/MiniMax 使用

`ANTHROPIC_AUTH_TOKEN` 环境变量会被 Claude CLI 放入 `Authorization: Bearer` header。

### 3. MiniMax 的 Key 类型陷阱

MiniMax 有两类 key，不通用：
- **Standard Key** → 仅 OpenAI 端点 (`/v1/chat/completions`)
- **Coding Plan Key** → 仅 Anthropic 端点 (`/anthropic/v1/messages`)

所以同一个 MiniMax 账号，Claude CLI（走 Anthropic）和 Pi CLI（走 OpenAI）需要**两把不同的 key**。这在配置矩阵的 `note` 字段里标注了。

### 4. Pi CLI 对四个 Provider 全部原生直连

pi CLI v0.74.2 原生支持 `deepseek`、`xiaomi`、`minimax`、`anthropic` 四个 provider，不需要手动设 base_url。只要设对 env var，CLI 自己处理协议和端点。
