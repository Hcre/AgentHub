import { useEffect, useState } from 'react'
import { useUIStore } from '../../stores/uiStore'
import { useApiKeyStore, PROVIDER_LABELS } from '../../stores/apiKeyStore'
import { Button, Icon } from '../ui'

// ── Token 消耗仪表盘 ─────────────────────────────────────────────

interface AggData {
  total_tokens: number
  prompt_tokens: number
  completion_tokens: number
  by_agent: Array<{ agent_id: string; total_tokens: number }>
}

const WINDOWS = [
  { key: '1h', label: '1 小时' },
  { key: '24h', label: '24 小时' },
  { key: '7d', label: '7 天' },
]

function TokenDashboard() {
  const [data, setData] = useState<Record<string, AggData>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const fetchAll = async () => {
      setLoading(true); setError(null)
      const result: Record<string, AggData> = {}
      for (const w of WINDOWS) {
        try {
          const r = await fetch(`/api/usage/global?window=${w.key}`)
          if (!r.ok) throw new Error(`${r.status}`)
          result[w.key] = await r.json()
        } catch { result[w.key] = { total_tokens: 0, prompt_tokens: 0, completion_tokens: 0, by_agent: [] } }
      }
      if (!cancelled) { setData(result); setLoading(false) }
    }
    fetchAll()
    return () => { cancelled = true }
  }, [])

  if (loading) return <div className="py-8 text-center text-[13px] text-muted-foreground">加载中…</div>
  if (error) return <div className="py-8 text-center text-[13px] text-red-500">{error}</div>

  const d24 = data['24h']
  const maxTokens = Math.max(1, ...(d24?.by_agent?.map((a) => a.total_tokens) ?? [0]))

  const fmt = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)

  return (
    <div className="space-y-4">
      {/* 三个时间窗口卡片 */}
      <div className="grid grid-cols-3 gap-3">
        {WINDOWS.map((w) => {
          const d = data[w.key]
          return (
            <div key={w.key} className="rounded-lg border bg-card p-3 text-center shadow-sm">
              <div className="text-[11px] text-muted-foreground">{w.label}</div>
              <div className="mt-1 font-mono text-[18px] font-bold">{fmt(d?.total_tokens ?? 0)}</div>
              <div className="mt-0.5 text-[10px] text-muted-foreground/60">
                P:{fmt(d?.prompt_tokens ?? 0)} C:{fmt(d?.completion_tokens ?? 0)}
              </div>
            </div>
          )
        })}
      </div>

      {/* 按 Agent 排行进度条 */}
      {d24?.by_agent?.length > 0 && (
        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="mb-2 text-[12px] font-medium text-muted-foreground">24h Agent 消耗排行</div>
          <div className="space-y-2">
            {d24.by_agent.slice(0, 10).map((a) => (
              <div key={a.agent_id} className="flex items-center gap-2">
                <span className="w-24 truncate font-mono text-[11px] text-muted-foreground">{a.agent_id.slice(0, 8)}</span>
                <div className="flex-1 rounded-full bg-muted/40 h-2.5 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-brand transition-all"
                    style={{ width: `${Math.max(2, (a.total_tokens / maxTokens) * 100)}%` }}
                  />
                </div>
                <span className="w-12 text-right font-mono text-[11px] text-muted-foreground">{fmt(a.total_tokens)}</span>
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
    <div className="flex h-full flex-col bg-background">
      <header className="flex items-center gap-3 border-b px-4 py-3">
        <Button variant="ghost" size="iconSm" onClick={() => setSection('chat')}>
          <Icon name="chevronLeft" className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h2 className="text-[15px] font-medium">设置</h2>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-4 space-y-4">

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
            className="flex w-full items-center gap-4 rounded-lg border bg-card p-4 text-left shadow-sm transition-colors hover:bg-accent/40"
          >
            <div className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-lg bg-muted">
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
