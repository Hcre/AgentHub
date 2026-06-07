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

// ── Model Tier Mapping ────────────────────────────────────────────
// 每个 agentSystem × provider 组合的 tier → model 映射。
// 约定：opus=最强推理, sonnet=平衡, haiku=快速轻量, inherit=沿用 Agent 自身 model

type ModelTier = 'opus' | 'sonnet' | 'haiku' | 'inherit'

const TIER_ORDER: Record<string, number> = { opus: 0, sonnet: 1, haiku: 2 }

interface TierModels {
  opus: string | null
  sonnet: string | null
  haiku: string | null
}

/**
 * 从矩阵 models 数组里按名字关键词推断 tier → model。
 * 对于仅 1-2 个模型的 provider（DeepSeek/MiniMax/Xiaomi），高层 tier 回退到最佳模型。
 */
function inferTierModels(models: string[]): TierModels {
  const byName = (keyword: string) =>
    models.find((m) => m.toLowerCase().includes(keyword)) ?? null

  const opus = byName('opus') ?? byName('pro') ?? models[0] ?? null
  const sonnet = byName('sonnet') ?? byName('pro') ?? models[0] ?? models[1] ?? opus
  const haiku = byName('haiku') ?? byName('flash') ?? models[models.length - 1] ?? sonnet

  return { opus, sonnet, haiku }
}

/** 所有 agentSystem × provider 的 tier → model 推导结果（惰性初始化）。 */
let _tierCache: Record<string, Record<string, TierModels>> | null = null

function getTierCache(): Record<string, Record<string, TierModels>> {
  if (_tierCache) return _tierCache
  _tierCache = {}
  for (const [agentSystem, providers] of Object.entries(CLI_PROVIDER_MATRIX)) {
    _tierCache[agentSystem] = {}
    for (const [provider, entry] of Object.entries(providers)) {
      _tierCache[agentSystem][provider] = inferTierModels(entry.models)
    }
  }
  return _tierCache
}

/**
 * 根据 Agent 系统 + provider + tier 解析出具体模型名。
 * - tier='inherit' → 返回 null（表示沿用 Agent 自身 model，不做覆盖）
 * - 无此组合 → null
 */
export function resolveModelFromTier(
  agentSystem: string,
  provider: string,
  tier: ModelTier,
): string | null {
  if (tier === 'inherit') return null
  const cache = getTierCache()
  const tierModels = cache[agentSystem]?.[provider]
  if (!tierModels) return null
  return tierModels[tier] ?? null
}

/** tier 的中文标签 */
export function getTierLabel(tier: string): string {
  const labels: Record<string, string> = {
    opus: '旗舰（Opus）',
    sonnet: '平衡（Sonnet）',
    haiku: '轻量（Haiku）',
    inherit: '继承默认',
  }
  return labels[tier] ?? tier
}

/** tier 的主题色（Tailwind 语义） */
export function getTierColor(tier: string): string {
  const colors: Record<string, string> = {
    opus: 'text-purple-600 bg-purple-50 border-purple-200',
    sonnet: 'text-blue-600 bg-blue-50 border-blue-200',
    haiku: 'text-emerald-600 bg-emerald-50 border-emerald-200',
    inherit: 'text-muted-foreground bg-muted border-border',
  }
  return colors[tier] ?? 'text-muted-foreground bg-muted border-border'
}
