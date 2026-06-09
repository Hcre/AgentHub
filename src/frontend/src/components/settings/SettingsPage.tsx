import { useEffect, useState } from 'react'
import { Icon } from '../ui'

const WINDOWS = [
  { key: '1h', label: '1 小时' } as const,
  { key: '24h', label: '24 小时' } as const,
  { key: '7d', label: '7 天' } as const,
]

interface UsageData {
  total_tokens: number
  prompt_tokens: number
  completion_tokens: number
  by_agent: Array<{ agent_id: string; agent_name: string; total_tokens: number }>
}

function TokenDashboard() {
  const [data, setData] = useState<Record<string, UsageData | null>>({})
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const fetchAll = async () => {
      setLoading(true)
      try {
        const results = await Promise.all(
          WINDOWS.map(async (w) => {
            const r = await fetch(`/api/usage/global?window=${w.key}`)
            if (!r.ok) throw new Error(`${w.key}: ${r.status}`)
            return [w.key, (await r.json()) as UsageData] as const
          })
        )
        if (!cancelled) {
          setData(Object.fromEntries(results))
          setErr(null)
        }
      } catch (e) {
        if (!cancelled) setErr(String(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchAll()
    return () => { cancelled = true }
  }, [])

  if (loading) return <div className="py-8 text-center text-[13px] text-muted-foreground">加载中…</div>
  if (err) return <div className="py-8 text-center text-[13px] text-destructive">{err}</div>

  const d24 = data['24h']
  const byAgent = d24?.by_agent ?? []

  const maxTokens = Math.max(1, ...byAgent.map((a) => a.total_tokens))

  const fmt = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)

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
                <span className="w-24 truncate text-[12px] text-foreground">{a.agent_name}</span>
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

// ── Provider 选项 ────────────────────────────────────────────────

const PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'openai', label: 'OpenAI' },
]

// ── CLI 配置路径 ─────────────────────────────────────────────────

const CLI_CONFIG_PATHS = [
  { label: 'Claude Code', path: '~/.claude/settings.json' },
  { label: 'OpenCode', path: '~/.config/opencode/config.yaml' },
  { label: 'Codex CLI', path: '~/.codex/config.yaml' },
  { label: 'Pi Agent', path: '~/.pi-agent/config.yaml' },
]

// ── 设置主页 ──────────────────────────────────────────────────────

export function SettingsPage() {
  // 协调者凭证表单
  const [provider, setProvider] = useState('deepseek')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState<'idle' | 'saved' | 'error'>('idle')

  // CLI 配置面板
  const [showCliConfig, setShowCliConfig] = useState(false)

  const handleSave = async () => {
    if (!apiKey.trim()) return
    setSaving(true)
    setFeedback('idle')
    try {
      const r = await fetch('/api/agents/coordinator/credential', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: apiKey, model }),
      })
      if (!r.ok) throw new Error(`${r.status}`)
      setFeedback('saved')
    } catch {
      setFeedback('error')
    } finally {
      setSaving(false)
    }
  }

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

        {/* ── 协调者凭证 ── */}
        <section>
          <h3 className="mb-3 text-[13px] font-medium text-muted-foreground">协调者凭证</h3>
          <div className="rounded-lg border border-border/60 glass-soft p-4 space-y-3">
            {/* Provider */}
            <div>
              <label className="block mb-1 text-[11px] text-muted-foreground">Provider</label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="w-full rounded-md border border-border/60 bg-background px-3 py-1.5 text-[13px] text-foreground outline-none focus:border-brand/50 focus:ring-1 focus:ring-brand/20"
              >
                {PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>

            {/* Model */}
            <div>
              <label className="block mb-1 text-[11px] text-muted-foreground">Model</label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="如 deepseek-chat"
                className="w-full rounded-md border border-border/60 bg-background px-3 py-1.5 text-[13px] text-foreground outline-none placeholder:text-muted-foreground/40 focus:border-brand/50 focus:ring-1 focus:ring-brand/20"
              />
            </div>

            {/* API Key */}
            <div>
              <label className="block mb-1 text-[11px] text-muted-foreground">API Key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
                className="w-full rounded-md border border-border/60 bg-background px-3 py-1.5 text-[13px] text-foreground outline-none placeholder:text-muted-foreground/40 focus:border-brand/50 focus:ring-1 focus:ring-brand/20"
              />
            </div>

            {/* Save button + feedback */}
            <div className="flex items-center gap-3 pt-1">
              <button
                onClick={handleSave}
                disabled={saving || !apiKey.trim()}
                className="inline-flex items-center gap-1.5 rounded-md bg-brand px-4 py-1.5 text-[13px] font-medium text-brand-foreground shadow-sm transition-colors hover:bg-brand/90 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Icon name="check" className="h-3.5 w-3.5" />
                {saving ? '保存中…' : '保存'}
              </button>
              {feedback === 'saved' && (
                <span className="text-[12px] text-green-600 dark:text-green-400">已保存</span>
              )}
              {feedback === 'error' && (
                <span className="text-[12px] text-destructive">保存失败，请重试</span>
              )}
            </div>
          </div>
        </section>

        {/* ── CLI 配置 ── */}
        <section>
          <h3 className="mb-3 text-[13px] font-medium text-muted-foreground">CLI 配置</h3>
          <button
            onClick={() => setShowCliConfig(!showCliConfig)}
            className="flex w-full items-center gap-4 rounded-lg border border-border/60 glass-soft p-4 text-left transition-colors hover:bg-accent/40"
          >
            <div className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-lg bg-muted/60">
              <Icon name="folderOpen" className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-medium">CLI 配置文件路径</div>
              <div className="mt-0.5 text-[11px] text-muted-foreground">
                Claude Code · OpenCode · Codex CLI · Pi Agent
              </div>
            </div>
            <Icon name={showCliConfig ? 'chevronUp' : 'chevronDown'} className="h-4 w-4 text-muted-foreground" />
          </button>

          {showCliConfig && (
            <div className="mt-2 rounded-lg border border-border/60 glass-soft p-4 space-y-2">
              {CLI_CONFIG_PATHS.map((c) => (
                <div key={c.label} className="flex items-center justify-between text-[12px]">
                  <span className="text-muted-foreground">{c.label}</span>
                  <code className="font-mono text-[11px] text-foreground/70">{c.path}</code>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
