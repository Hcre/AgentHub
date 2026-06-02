/** CLI × Provider 自动推导表
 *
 * 选完 CLI + Provider 后，自动填 base_url、协议、模型列表。
 * 新增 Provider 或 CLI 只需加一行。
 */

export interface CliProviderEntry {
  protocol: string           // "Anthropic Messages" | "OpenAI Completions"
  baseUrl: string            // 默认端点
  envVar: string             // AgentHub 注入的环境变量名
  needsProxy: boolean        // 是否需要 AgentHub proxy
  modelPrefix: string        // opencode 需要的 provider/ 前缀
  models: string[]           // 默认模型列表
  note?: string
}

type Matrix = Record<string, Record<string, CliProviderEntry>>

export const CLI_PROVIDER_MATRIX: Matrix = {
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
      envVar: 'ANTHROPIC_AUTH_TOKEN',
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
      note: '需 Coding Plan Key，Standard Key 不可用',
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
      note: '需 Standard Key，Coding Plan Key 不可用',
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
      note: '需 opencode.jsonc 配置 @ai-sdk/openai-compatible',
    },
    minimax: {
      protocol: 'OpenAI Completions',
      baseUrl: 'https://api.minimaxi.com/v1',
      envVar: 'MINIMAX_API_KEY',
      needsProxy: false,
      modelPrefix: 'minimax/',
      models: ['minimax/MiniMax-M2.7'],
      note: '需 opencode.jsonc 配置 @ai-sdk/openai-compatible',
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

/** 根据 CLI 和 Provider 查表，返回推导的配置 */
export function resolveProviderConfig(
  agentSystem: string,
  provider: string,
): CliProviderEntry | null {
  return CLI_PROVIDER_MATRIX[agentSystem]?.[provider] ?? null
}

/** 列出某个 CLI 支持的所有 provider */
export function listProvidersForCli(agentSystem: string): string[] {
  return Object.keys(CLI_PROVIDER_MATRIX[agentSystem] ?? {})
}
