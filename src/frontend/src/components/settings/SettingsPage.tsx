import { useEffect, useState } from 'react'
import { Button, Dialog, DialogContent, Icon } from '../ui'
import { useAgentStore } from '../../stores/agentStore'

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
  const [model, setModel] = useState('deepseek-chat')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [hasSavedKey, setHasSavedKey] = useState(false)
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState<'idle' | 'saved' | 'error'>('idle')
  const [credentialOpen, setCredentialOpen] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; latency_ms?: number; model?: string; error?: string } | null>(null)

  // 监督者表单
  const [supervisorOpen, setSupervisorOpen] = useState(false)
  const [supervisorAgentId, setSupervisorAgentId] = useState('')
  const [savedSupervisorName, setSavedSupervisorName] = useState('')
  const [supervisorSaving, setSupervisorSaving] = useState(false)
  const [supervisorFeedback, setSupervisorFeedback] = useState<'idle' | 'saved' | 'error'>('idle')
  const agents = useAgentStore(s => s.agents)
  const cliAgents = agents.filter(a => a.agentSystem === 'claude_code')

  // 页面加载时读取已保存凭证
  useEffect(() => {
    fetch('/api/agents/coordinator/credential')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.has_key) {
          setProvider(data.provider || 'deepseek')
          setModel(data.model || 'deepseek-chat')
          setBaseUrl(data.base_url || '')
          setHasSavedKey(true)
          // 不设置 apiKey（已加密，只返回前缀），用户需重新输入
        }
        if (data?.supervisor_agent_name) {
          setSavedSupervisorName(data.supervisor_agent_name)
        }
      })
      .catch(() => {})
  }, [])

  const handleSupervisorSave = async () => {
    setSupervisorSaving(true)
    setSupervisorFeedback('idle')
    try {
      const selected = cliAgents.find(a => a.id === supervisorAgentId)
      const name = selected?.name || ''
      const r = await fetch('/api/agents/coordinator/supervisor', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ supervisor_agent_name: name }),
      })
      if (!r.ok) throw new Error(`${r.status}`)
      setSavedSupervisorName(name)
      setSupervisorFeedback('saved')
    } catch {
      setSupervisorFeedback('error')
    } finally {
      setSupervisorSaving(false)
    }
  }

  // CLI 配置面板
  const [showCliConfig, setShowCliConfig] = useState(false)

  const handleSave = async () => {
    if (!apiKey.trim()) return
    setSaving(true)
    setFeedback('idle')
    setTestResult(null)
    try {
      const r = await fetch('/api/agents/coordinator/credential', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: apiKey, model, base_url: baseUrl }),
      })
      if (!r.ok) throw new Error(`${r.status}`)
      setFeedback('saved')
      setHasSavedKey(true)
    } catch {
      setFeedback('error')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    if (!apiKey.trim() || !model.trim()) return
    setTesting(true)
    setTestResult(null)
    setFeedback('idle')
    try {
      const r = await fetch('/api/agents/coordinator/credential/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: apiKey, model, base_url: baseUrl }),
      })
      const data = await r.json()
      setTestResult(data)
    } catch {
      setTestResult({ ok: false, error: '网络请求失败' })
    } finally {
      setTesting(false)
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
          <button
            onClick={() => setCredentialOpen(true)}
            className="flex w-full items-center gap-4 rounded-lg border border-border/60 glass-soft p-4 text-left transition-colors hover:bg-accent/40"
          >
            <div className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-lg bg-brand/10 text-brand">
              <Icon name="brain" className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-medium">
                {hasSavedKey ? `${PROVIDERS.find(p => p.value === provider)?.label ?? provider} · ${model || '—'}` : '未配置'}
              </div>
              <div className="mt-0.5 text-[11px] text-muted-foreground">
                {hasSavedKey
                  ? `密钥已设置 · 点击修改`
                  : '点击配置协调者 API 凭证'}
              </div>
            </div>
            <div className={`grid h-3 w-3 flex-shrink-0 place-items-center rounded-full ${hasSavedKey ? 'bg-emerald-500' : 'bg-muted-foreground/30'}`}>
              {hasSavedKey && <Icon name="check" className="h-2 w-2 text-white" strokeWidth={3} />}
            </div>
          </button>
        </section>

        {/* 凭证弹窗 */}
        <Dialog open={credentialOpen} onOpenChange={setCredentialOpen}>
          <DialogContent className="w-[440px]">
            <header className="flex items-center gap-3 border-b border-border/70 p-4">
              <div className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-lg bg-brand/10 text-brand">
                <Icon name="brain" className="h-4 w-4" strokeWidth={2} />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-[15px] font-semibold">协调者凭证</h2>
                <p className="mt-0.5 text-[12px] text-muted-foreground">
                  配置群组协调者使用的 LLM API
                </p>
              </div>
            </header>

            <div className="space-y-3 p-4">
              {/* Provider */}
              <div>
                <label className="block mb-1 text-[11px] text-muted-foreground">Provider</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="w-full rounded-md border border-border/60 bg-background px-3 py-1.5 text-[13px] text-foreground outline-none focus:border-brand/50"
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
                  className="w-full rounded-md border border-border/60 bg-background px-3 py-1.5 text-[13px] text-foreground outline-none placeholder:text-muted-foreground/40 focus:border-brand/50"
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
                  className="w-full rounded-md border border-border/60 bg-background px-3 py-1.5 text-[13px] text-foreground outline-none placeholder:text-muted-foreground/40 focus:border-brand/50"
                />
              </div>

              {/* Base URL */}
              <div>
                <label className="block mb-1 text-[11px] text-muted-foreground">
                  Base URL <span className="text-muted-foreground/50">（可选）</span>
                </label>
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="留空则自动推导"
                  className="w-full rounded-md border border-border/60 bg-background px-3 py-1.5 text-[13px] text-foreground outline-none placeholder:text-muted-foreground/40 focus:border-brand/50"
                />
              </div>

              {/* Test result */}
              {testResult && (
                <div className={`rounded-md px-3 py-2 text-[12px] ${testResult.ok ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300' : 'bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-300'}`}>
                  {testResult.ok
                    ? `✓ 连通正常 · ${testResult.latency_ms}ms · 模型 ${testResult.model}`
                    : `✗ 连通失败 · ${testResult.error}`}
                </div>
              )}

              {/* Save feedback */}
              {!testResult && feedback === 'saved' && (
                <div className="rounded-md bg-emerald-50 px-3 py-2 text-[12px] text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">
                  ✓ 已保存
                </div>
              )}
              {!testResult && feedback === 'error' && (
                <div className="rounded-md bg-red-50 px-3 py-2 text-[12px] text-red-600 dark:bg-red-950/30 dark:text-red-300">
                  保存失败，请重试
                </div>
              )}
            </div>

            <footer className="flex items-center justify-between gap-2 border-t border-border/70 p-3">
              <Button
                variant="outline"
                size="sm"
                onClick={handleTest}
                disabled={testing || !apiKey.trim() || !model.trim()}
              >
                {testing ? '测试中…' : '测试连通'}
              </Button>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => setCredentialOpen(false)}>
                  取消
                </Button>
                <Button
                  variant="default"
                  size="sm"
                  onClick={handleSave}
                  disabled={saving || !apiKey.trim()}
                >
                  {saving ? '保存中…' : '保存'}
                </Button>
              </div>
            </footer>
          </DialogContent>
        </Dialog>

        {/* ── 监督者 ── */}
        <section>
          <h3 className="mb-3 text-[13px] font-medium text-muted-foreground">监督者</h3>
          <button
            onClick={() => {
              const saved = cliAgents.find(a => a.name === savedSupervisorName)
              setSupervisorAgentId(saved?.id || '')
              setSupervisorFeedback('idle')
              setSupervisorOpen(true)
            }}
            className="flex w-full items-center gap-4 rounded-lg border border-border/60 glass-soft p-4 text-left transition-colors hover:bg-accent/40"
          >
            <div className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-lg bg-brand/10 text-brand">
              <Icon name="shieldCheck" className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-medium">
                {savedSupervisorName || '未配置'}
              </div>
              <div className="mt-0.5 text-[11px] text-muted-foreground">
                {savedSupervisorName
                  ? `监督者: ${savedSupervisorName} · 点击更换`
                  : '点击选择监督者 Agent'}
              </div>
            </div>
            <div className={`grid h-3 w-3 flex-shrink-0 place-items-center rounded-full ${savedSupervisorName ? 'bg-emerald-500' : 'bg-muted-foreground/30'}`}>
              {savedSupervisorName && <Icon name="check" className="h-2 w-2 text-white" strokeWidth={3} />}
            </div>
          </button>
        </section>

        {/* 监督者弹窗 */}
        <Dialog open={supervisorOpen} onOpenChange={setSupervisorOpen}>
          <DialogContent className="w-[440px]">
            <header className="flex items-center gap-3 border-b border-border/70 p-4">
              <div className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-lg bg-brand/10 text-brand">
                <Icon name="shieldCheck" className="h-4 w-4" strokeWidth={2} />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-[15px] font-semibold">监督者</h2>
                <p className="mt-0.5 text-[12px] text-muted-foreground">
                  选择担任任务监督者的 Agent（仅 CLI 本地 Agent）
                </p>
              </div>
            </header>

            <div className="space-y-3 p-4">
              {/* Agent 选择 */}
              <div>
                <label className="block mb-1 text-[11px] text-muted-foreground">监督者 Agent</label>
                {cliAgents.length === 0 ? (
                  <p className="text-[12px] text-muted-foreground">
                    暂无 CLI Agent。请先在 Agent 管理创建 Claude Code 类型的 Agent。
                  </p>
                ) : (
                  <select
                    value={supervisorAgentId}
                    onChange={(e) => setSupervisorAgentId(e.target.value)}
                    className="w-full rounded-md border border-border/60 bg-background px-3 py-1.5 text-[13px] text-foreground outline-none focus:border-brand/50"
                  >
                    <option value="">-- 不启用监督者 --</option>
                    {cliAgents.map((a) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </select>
                )}
              </div>

              {/* 保存反馈 */}
              {supervisorFeedback === 'saved' && (
                <div className="rounded-md bg-emerald-50 px-3 py-2 text-[12px] text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">
                  ✓ 已保存
                </div>
              )}
              {supervisorFeedback === 'error' && (
                <div className="rounded-md bg-red-50 px-3 py-2 text-[12px] text-red-600 dark:bg-red-950/30 dark:text-red-300">
                  保存失败，请重试
                </div>
              )}
            </div>

            <footer className="flex items-center justify-end gap-2 border-t border-border/70 p-3">
              <Button variant="ghost" size="sm" onClick={() => setSupervisorOpen(false)}>
                取消
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleSupervisorSave}
                disabled={supervisorSaving}
              >
                {supervisorSaving ? '保存中…' : '保存'}
              </Button>
            </footer>
          </DialogContent>
        </Dialog>

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
