import { useEffect, useState, useCallback } from 'react'
import { useUIStore } from '../../stores/uiStore'
import { Button, Icon } from '../ui'

interface MarketSkill {
  id: string
  name: string
  author: string
  description: string
  github_url: string
  skill_url: string
  stars: number
  updated_at: string
}

interface InstalledSkill {
  name: string
  path: string
  source: string
}

const PAGE_SIZE = 20

async function safeJson(r: Response) {
  const text = await r.text()
  try { return JSON.parse(text) }
  catch {
    // 后端返回非 JSON（如 nginx 错误页），截取前 80 字展示
    const preview = text.trim().slice(0, 80)
    throw new Error(preview || `HTTP ${r.status}`)
  }
}

export function SkillMarketplacePage() {
  const setSection = useUIStore((s) => s.setSection)

  const [q, setQ] = useState('')
  const [skills, setSkills] = useState<MarketSkill[]>([])
  const [loading, setLoading] = useState(false)
  const [installed, setInstalled] = useState<Set<string>>(new Set())
  const [installing, setInstalling] = useState<Set<string>>(new Set())
  const [error, setError] = useState('')

  const loadInstalled = useCallback(() => {
    fetch('/api/skills/library?_=' + Date.now())
      .then(safeJson)
      .then((list: InstalledSkill[]) => setInstalled(new Set(list.map((s) => s.name))))
      .catch(() => {})
  }, [])

  useEffect(() => { loadInstalled() }, [loadInstalled])

  const search = useCallback(() => {
    setLoading(true)
    setError('')
    fetch('/api/skills/marketplace/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q, page: 1, limit: PAGE_SIZE, sort_by: 'stars' }),
    })
      .then(safeJson)
      .then((data) => {
        if (data.detail) throw new Error(data.detail)
        setSkills(data.skills ?? [])
      })
      .catch((e) => setError(e.message || '搜索失败'))
      .finally(() => setLoading(false))
  }, [q])

  useEffect(() => { search() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const install = async (skill: MarketSkill) => {
    setInstalling((prev) => new Set(prev).add(skill.id))
    setError('')
    try {
      const r = await fetch('/api/skills/marketplace/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skill_id: skill.id,
          github_url: skill.github_url,
          name: skill.name,
        }),
      })
      const data = await safeJson(r)
      if (!r.ok) throw new Error(data.detail || '安装失败')
      setInstalled((prev) => new Set(prev).add(skill.name))
    } catch (e: any) {
      setError(e.message || '安装失败')
    } finally {
      setInstalling((prev) => {
        const next = new Set(prev)
        next.delete(skill.id)
        return next
      })
    }
  }

  const formatDate = (ts: string) => {
    const d = new Date(Number(ts) * 1000)
    return d.toLocaleDateString('zh-CN')
  }

  const fmtStars = (n: number) => {
    if (n >= 10000) return `${(n / 1000).toFixed(0)}k`
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
    return String(n)
  }

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Header */}
      <header className="flex items-center gap-3 border-b px-4 py-3">
        <Button variant="ghost" size="iconSm" onClick={() => setSection('chat')}>
          <Icon name="chevronLeft" className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h2 className="text-[15px] font-medium">技能市场</h2>
          <p className="text-[11px] text-muted-foreground">搜索并安装社区共享的 AI 技能</p>
        </div>
        <span className="text-[11px] text-muted-foreground/60">数据来源 skillsmp.com</span>
      </header>

      {/* Search bar */}
      <div className="flex gap-2 border-b px-4 py-2.5">
        <div className="relative flex-1">
          <Icon
            name="search"
            className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
          />
          <input
            className="h-8 w-full rounded-md border bg-transparent pl-7 pr-3 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
            placeholder="搜索技能，如 react、python、docker..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && search()}
          />
        </div>
        <Button variant="outline" size="sm" onClick={() => search()} disabled={loading}>
          <Icon name="search" className="h-3 w-3" />
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="mx-4 mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-600">
          {error}
        </div>
      )}

      {/* Results */}
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <span className="text-[13px] text-muted-foreground">搜索中…</span>
          </div>
        ) : skills.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <Icon name="search" className="mb-2 h-8 w-8 text-muted-foreground/30" />
            <p className="text-[13px] text-muted-foreground">
              {q ? `未找到「${q}」相关技能` : '输入关键词搜索技能'}
            </p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {skills.map((s) => {
                const isInstalled = installed.has(s.name)
                const isInstalling = installing.has(s.id)
                return (
                  <div
                    key={s.id}
                    className="flex flex-col gap-2 rounded-lg border-2 border-border bg-card p-3.5 shadow-sm transition-all hover:border-brand/40 hover:shadow-md"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <h4 className="truncate text-[13px] font-semibold">{s.name}</h4>
                        <p className="text-[11px] text-muted-foreground">@{s.author}</p>
                      </div>
                      <Button
                        variant={isInstalled ? 'ghost' : 'outline'}
                        size="sm"
                        className="h-6 flex-shrink-0 text-[11px]"
                        disabled={isInstalled || isInstalling}
                        onClick={() => install(s)}
                      >
                        {isInstalling ? '下载中…' : isInstalled ? '已安装' : '安装'}
                      </Button>
                    </div>
                    <p className="line-clamp-2 text-[12px] leading-relaxed text-muted-foreground">
                      {s.description || '暂无描述'}
                    </p>
                    <div className="flex items-center gap-3 text-[11px] text-muted-foreground/70">
                      <span className="inline-flex items-center gap-0.5 font-medium text-amber-600">
                        ★ {fmtStars(s.stars)}
                      </span>
                      <span>{formatDate(s.updated_at)}</span>
                    </div>
                  </div>
                )
              })}
            </div>

            <p className="mt-5 text-center text-[11px] text-muted-foreground/50">
              仅展示前 {PAGE_SIZE} 个结果，更多 skill 请访问{' '}
              <a
                href="https://skillsmp.com"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-muted-foreground"
              >
                skillsmp.com
              </a>{' '}
              探索
            </p>
          </>
        )}
      </div>
    </div>
  )
}
