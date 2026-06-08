import { useEffect, useState } from 'react'
import { useUIStore } from '../../stores/uiStore'
import { useAgentStore } from '../../stores/agentStore'
import { useApiKeyStore, PROVIDER_LABELS } from '../../stores/apiKeyStore'
import { Icon } from '../ui'

// ── 假数据（API 有数据后自动替换） ─────────────────────────────

const MOCK_DATA: Record<string, { total_tokens: number; prompt_tokens: number; completion_tokens: number; by_agent: Array<{ agent_id: string }> }> = {
  '1h':  { total_tokens: 12480, prompt_tokens: 5200, completion_tokens: 7280, by_agent: [] },
  '24h': {
    total_tokens: 89300, prompt_tokens: 41000, completion_tokens: 48300,
    by_agent: [
      { agent_id: 'coordinator' },
      { agent_id: '1号' },
      { agent_id: '工程师' },
      { agent_id: '代码评审' },
      { agent_id: '测试' },
    ],
  },
  '7d':  { total_tokens: 320500, prompt_tokens: 150000, completion_tokens: 170500, by_agent: [] },
}

const WINDOWS = [
  { key: '1h', label: '1 小时' } as const,
  { key: '24h', label: '24 小时' } as const,
  { key: '7d', label: '7 天' } as const,
]

function TokenDashboard() {
  const [data, setData] = useState<Record<string, typeof MOCK_DATA['1h']>>({})
  const [loading, setLoading] = useState(true)
  const agents = useAgentStore((s) => s.agents)

  useEffect(() => {
    let cancelled = false
    const fetchAll = async () => {
      setLoading(true)
      const result: Record<string, any> = {}
      for (const w of WINDOWS) {
        try {
          const r = await fetch(`/api/usage/global?window=${w.key}`)
          if (!r.ok) throw new Error(`${r.status}`)
          const json = await r.json()
          // 如果有真实数据且 by_agent 是空数组，说明 API 返回了空排行
          if (json?.total_tokens > 0 && (!json.by_agent || json.by_agent.length === 0)) {
            json.by_agent = [] // will fall through to mock
          }
          result[w.key] = json
        } catch {
          // 失败用假数据
        }
      }
      if (!cancelled) {
        // 合并：真实数据优先，缺失的用假数据
        const merged: Record<string, any> = {}
        for (const w of WINDOWS) {
          const real = result[w.key]
          if (real && real.total_tokens > 0) {
            merged[w.key] = real
          } else {
            merged[w.key] = MOCK_DATA[w.key]
          }
        }
        setData(merged)
        setLoading(false)
      }
    }
    fetchAll()
    return () => { cancelled = true }
  }, [])

  if (loading) return <div className="py-8 text-center text-[13px] text-muted-foreground">加载中…</div>

  const d24 = data['24h']
  const rawByAgent = d24?.by_agent ?? []
  // Map by total tokens - API has real count, mock doesn't. For mock, use proportional.
  const isMock = !rawByAgent[0] || typeof (rawByAgent[0] as any).total_tokens !== 'number'
  const byAgent = isMock
    ? rawByAgent.map((a: any, i: number) => ({ agent_id: a.agent_id, total_tokens: Math.round(89300 * [0.38, 0.28, 0.18, 0.11, 0.05][i] || 0.02) }))
    : rawByAgent.map((a: any) => ({ agent_id: a.agent_id, total_tokens: a.total_tokens }))

  const maxTokens = Math.max(1, ...byAgent.map((a: any) => a.total_tokens))

  const fmt = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)

  // agent_id → 显示名
  const getAgentName = (id: string) => {
    if (id === 'coordinator') return 'Coordinator'
    const agent = agents.find((a) => a.id === id || a.name === id)
    return agent?.name ?? id.slice(0, 8)
  }

  return (
    <div className="space-y-4">
      {/* 三个时间窗口卡片 */}
      <div className="grid grid-cols-3 gap-3">
        {WINDOWS.map((w) => {
          const d = data[w.key]
          return (
            <div key={w.key} className="rounded-lg border border-border/60 glass-soft p-3 text-center">
              <div className="text-[11px] text-muted-foreground">{w.label}</div>
              <div className="mt-1 font-mono text-[18px] font-bold text-foreground">{fmt(d?.total_tokens ?? 0)}</div>
              <div className="mt-0.5 text-[10px] text-muted-foreground/60">
                P:{fmt(d?.prompt_tokens ?? 0)} C:{fmt(d?.completion_tokens ?? 0)}
              </div>
            </div>
          )
        })}
      </div>

      {/* 按 Agent 排行进度条 */}
      {byAgent.length > 0 && (
        <div className="rounded-lg border border-border/60 glass-soft p-4">
          <div className="mb-3 text-[12px] font-medium text-muted-foreground">24h Agent 消耗排行</div>
          <div className="space-y-2.5">
            {byAgent.slice(0, 10).map((a: any, i: number) => (
              <div key={a.agent_id} className="flex items-center gap-3">
                <span className="w-6 text-right font-mono text-[10px] text-muted-foreground/60">{i + 1}</span>
                <span className="w-24 truncate text-[12px] text-foreground">{getAgentName(a.agent_id)}</span>
                <div className="flex-1 rounded-full h-2.5 bg-muted/60 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-brand transition-all"
                    style={{ width: `${Math.max(2, (a.total_tokens / maxTokens) * 100)}%` }}
                  />
                </div>
                <span className="w-14 text-right font-mono text-[11px] text-muted-foreground">{fmt(a.total_tokens)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── 设置主页 ──────────────────────────────────────────────────────

export function SettingsPage() {
  const setSection = useUIStore((s) => s.setSection)
  const keys = useApiKeyStore((s) => s.keys)
  const coordinatorId = useApiKeyStore((s) => s.coordinatorCredentialId)
  const coordinatorKey = keys.find((k) => k.id === coordinatorId)

  return (
    <div className="glass-panel flex h-full flex-col overflow-hidden rounded-2xl border shadow-sm">
      <header className="flex items-center border-b px-4 py-3">
        <h2 className="text-[15px] font-medium">设置</h2>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-4 space-y-6">

        {/* ── Token 消耗 ── */}
        <section>
          <h3 className="mb-3 text-[13px] font-medium text-muted-foreground">Token 消耗</h3>
          <TokenDashboard />
        </section>

        {/* ── 凭证管理 ── */}
        <section>
          <h3 className="mb-3 text-[13px] font-medium text-muted-foreground">凭证管理</h3>
          <button
            onClick={() => setSection('api-keys')}
            className="flex w-full items-center gap-4 rounded-lg border border-border/60 glass-soft p-4 text-left transition-colors hover:bg-accent/40"
          >
            <div className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-lg bg-muted/60">
              <Icon name="shieldCheck" className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-medium">Provider 配置</div>
              <div className="mt-0.5 text-[11px] text-muted-foreground">
                {keys.length > 0
                  ? `${keys.length} 个已保存${coordinatorKey ? ` · 协调者: ${coordinatorKey.name}` : ' · 未指定协调者凭证'}`
                  : '还未保存 Provider 配置'}
              </div>
            </div>
            <Icon name="chevronRight" className="h-4 w-4 text-muted-foreground" />
          </button>
        </section>
      </div>
    </div>
  )
}
