import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { cn } from '../../lib/cn'
import { Avatar, Button, ConfirmDialog, Icon } from '../ui'

interface MarketSkill {
  id: string
  name: string
  author: string
  description: string
  github_url: string
  skill_url: string
  stars: number
  downloads: number
  installs: number
  category: string
  version: string
  updated_at: string
}

interface InstalledSkill {
  name: string
  path: string
  rel_path?: string
  source: string
  description: string
  author: string
  version: string
  installed_at: number
}

type SortBy = 'default' | 'stars' | 'downloads'
type Tab = 'market' | 'installed'

/** 排序选项展示（label/icon/value 三元组） */
const SORT_OPTIONS: ReadonlyArray<{ value: SortBy; label: string; icon: string }> = [
  { value: 'downloads', label: '最多下载', icon: '↓' },
  { value: 'stars', label: '最多 Star', icon: '★' },
  { value: 'default', label: '默认（热度）', icon: '⊕' },
]

const PAGE_SIZE = 18

async function safeJson(r: Response) {
  const text = await r.text()
  try {
    return JSON.parse(text)
  } catch {
    const preview = text.trim().slice(0, 80)
    throw new Error(preview || `HTTP ${r.status}`)
  }
}

/** 与群组 / AI 队友卡同款玻璃图标按钮。 */
function GlassIconBtn({
  icon,
  title,
  onClick,
  disabled,
  variant = 'default',
}: {
  icon: 'plus' | 'check' | 'moreVertical' | 'globe' | 'files' | 'trash2'
  title: string
  onClick: (e: ReactMouseEvent<HTMLButtonElement>) => void
  disabled?: boolean
  variant?: 'default' | 'brand'
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      disabled={disabled}
      className={cn(
        'grid h-7 w-7 place-items-center rounded-lg border border-border/60 glass-soft transition-colors',
        'text-muted-foreground',
        'hover:bg-accent hover:text-foreground',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background',
        'disabled:cursor-not-allowed disabled:opacity-50',
        variant === 'brand' && 'text-brand border-brand/40 bg-brand/5 hover:bg-brand/10 hover:text-brand',
      )}
    >
      <Icon name={icon} className="h-3.5 w-3.5" />
    </button>
  )
}

export function SkillMarketplacePage() {
  // ── 市场 tab 状态 ──
  const [q, setQ] = useState('')
  const [sortBy, setSortBy] = useState<SortBy>('downloads')
  const [skills, setSkills] = useState<MarketSkill[]>([])
  const [loading, setLoading] = useState(false)
  const [openingSet, setOpeningSet] = useState<Set<string>>(new Set())
  const [error, setError] = useState('')

  // 筛选 dropdown
  const [filterOpen, setFilterOpen] = useState(false)
  const filterRef = useRef<HTMLDivElement>(null)

  // ── 已安装 tab 状态 ──
  const [installed, setInstalled] = useState<InstalledSkill[]>([])
  const [installedLoading, setInstalledLoading] = useState(false)
  const [installedBatchMode, setInstalledBatchMode] = useState(false)
  const [installedSelected, setInstalledSelected] = useState<Set<string>>(new Set())
  const [installedDeleting, setInstalledDeleting] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [batchDeleteConfirm, setBatchDeleteConfirm] = useState<string[] | null>(null)

  // ── tab 状态 ──
  const [tab, setTab] = useState<Tab>('market')

  // 加载已安装列表
  const loadInstalled = useCallback(() => {
    setInstalledLoading(true)
    fetch('/api/skills/library?_=' + Date.now())
      .then(safeJson)
      .then((list: InstalledSkill[]) => setInstalled(list ?? []))
      .catch(() => {})
      .finally(() => setInstalledLoading(false))
  }, [])

  // 挂载时就加载（市场卡要预知哪些已装）
  // loadInstalled 内部 setState 推迟到 microtask 避开 react-hooks/set-state-in-effect
  useEffect(() => {
    queueMicrotask(() => loadInstalled())
  }, [loadInstalled])

  // tab 切到 installed 时**重新**加载（保险）
  useEffect(() => {
    if (tab === 'installed') queueMicrotask(() => loadInstalled())
  }, [tab, loadInstalled])

  // 监听来自 MessageBubble 中 SKILL.md 保存成功的事件，刷新已安装列表
  useEffect(() => {
    const handler = () => {
      queueMicrotask(() => loadInstalled())
    }
    window.addEventListener('skill-library-updated', handler)
    return () => window.removeEventListener('skill-library-updated', handler)
  }, [loadInstalled])

  // 加载市场（统一走 /search，sort_by 后端客户端 sort）
  const search = useCallback(() => {
    setLoading(true)
    setError('')
    fetch('/api/skills/marketplace/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q, page: 1, limit: PAGE_SIZE, sort_by: sortBy }),
    })
      .then(safeJson)
      .then((data) => {
        if (data.detail) throw new Error(data.detail)
        setSkills(data.skills ?? [])
      })
      .catch((e) => setError(e instanceof Error ? e.message : '搜索失败'))
      .finally(() => setLoading(false))
  }, [q, sortBy])

  // 市场 tab 默认加载；sortBy 切换 / q 变化都重新加载
  // search 内部 setState 推迟到 microtask 避开 react-hooks/set-state-in-effect
  useEffect(() => {
    if (tab === 'market') queueMicrotask(() => search())
  }, [tab, search])

  // 安装：POST /api/skills/marketplace/install（真下载 + 解压），成功后本地 installed 加名
  const installSkill = async (skill: MarketSkill) => {
    setOpeningSet((prev) => new Set(prev).add(skill.id))
    setError('')
    try {
      const r = await fetch('/api/skills/marketplace/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_id: skill.id, name: skill.name }),
      })
      const data = await safeJson(r)
      if (!r.ok) throw new Error(data.detail || '安装失败')
      // 安装成功 → 已安装列表加上 + 「市场」卡变「已安装」
      setInstalled((prev) => [
        ...prev,
        {
          name: skill.name,
          path: data.path,
          source: data.source ?? 'skillhub',
          description: skill.description,
          author: skill.author,
          version: skill.version,
          installed_at: Date.now(),
        },
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : '安装失败')
    } finally {
      setOpeningSet((prev) => {
        const next = new Set(prev)
        next.delete(skill.id)
        return next
      })
    }
  }

  // 纯外链：开新 tab 看 skillhub 详情
  const openOnSkillhub = (skill: MarketSkill) => {
    window.open(skill.skill_url, '_blank', 'noopener,noreferrer')
  }

  // 已装名字集合（用于「市场」卡判断按钮态）
  const installedNames = useMemo(
    () => new Set(installed.map((s) => s.name)),
    [installed],
  )

  // 当前 sort 的展示信息（加运行时兜底，防 TS 非空断言被打脸）
  const currentSort = SORT_OPTIONS.find((o) => o.value === sortBy) ?? SORT_OPTIONS[0]

  // 筛选 dropdown：点外面关
  useEffect(() => {
    if (!filterOpen) return
    const onClickOutside = (e: MouseEvent) => {
      if (filterRef.current && !filterRef.current.contains(e.target as Node)) {
        setFilterOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [filterOpen])

  const formatDate = (ts: string) => {
    const d = new Date(Number(ts) * 1000)
    return d.toLocaleDateString('zh-CN')
  }

  const fmtNum = (n: number) => {
    if (n >= 10000) return `${(n / 1000).toFixed(1)}k`
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
    return String(n)
  }

  return (
    <div className="glass-panel flex h-full flex-col overflow-hidden rounded-2xl border shadow-sm">
      {/* 头部：tab 放大占原返回/标题位置，返回/标题都去掉 */}
      <header className="flex items-center justify-between gap-3 border-b border-border/70 px-5 py-3.5">
        {/* tab toggle：市场 / 已安装（放大） */}
        <div className="flex items-center rounded-lg border border-border/60 glass-soft p-0.5 text-[13px]">
          <button
            type="button"
            onClick={() => setTab('market')}
            className={cn(
              'rounded-md px-4 py-1.5 transition-colors',
              tab === 'market'
                ? 'bg-brand/15 text-brand font-medium'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            市场
          </button>
          <button
            type="button"
            onClick={() => setTab('installed')}
            className={cn(
              'rounded-md px-4 py-1.5 transition-colors',
              tab === 'installed'
                ? 'bg-brand/15 text-brand font-medium'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            已安装
            {installed.length > 0 && (
              <span className="ml-1 rounded bg-muted/60 px-1 text-[10px] tabular-nums">
                {installed.length}
              </span>
            )}
          </button>
        </div>

        {/* 右侧：「批量管理」（仅 installed tab）+「+ 创建 skill」（所有 tab） */}
        <div className="flex items-center gap-2">
          {tab === 'installed' && !installedBatchMode && installed.length > 0 && (
            <Button variant="outline" size="sm" onClick={() => setInstalledBatchMode(true)}>
              <Icon name="listCheck" className="h-3.5 w-3.5" />
              批量管理
            </Button>
          )}
        </div>
      </header>

      {/* ── 市场 tab ── */}
      {tab === 'market' && (
        <>
          <div className="border-b border-border/70 px-5 py-3">
            {/* 搜索框 + 旁边筛选按钮（sliders + dropdown） */}
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Icon
                  name="search"
                  className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                />
                <input
                  className="h-9 w-full rounded-lg border border-border/60 bg-background/40 pl-9 pr-3 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  placeholder="搜索技能，如 react、python、小红书..."
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && search()}
                />
              </div>

              {/* 筛选按钮 + dropdown：3 选项（最多下载 / 最多 Star / 默认热度） */}
              <div ref={filterRef} className="relative flex-shrink-0">
                <button
                  type="button"
                  onClick={() => setFilterOpen((v) => !v)}
                  className={cn(
                    'flex h-9 items-center gap-1.5 rounded-lg border border-border/60 glass-soft px-3 text-[12px] transition-colors',
                    'hover:bg-accent',
                    filterOpen && 'border-brand/40 bg-brand/5 text-brand',
                  )}
                  title="筛选"
                >
                  <Icon name="sliders" className="h-3.5 w-3.5" />
                  <span className="font-medium">
                    <span className="mr-0.5 opacity-70">{currentSort!.icon}</span>
                    {currentSort!.label}
                  </span>
                  <Icon
                    name="chevronDown"
                    className={cn(
                      'h-3 w-3 opacity-50 transition-transform',
                      filterOpen && 'rotate-180',
                    )}
                  />
                </button>
                {filterOpen && (
                  <div className="absolute right-0 top-full z-50 mt-1.5 w-48 overflow-hidden rounded-lg border border-border/60 glass-soft shadow-lg">
                    {SORT_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => {
                          setSortBy(opt.value)
                          setFilterOpen(false)
                        }}
                        className={cn(
                          'flex w-full items-center gap-2 px-3 py-2 text-left text-[12.5px] transition-colors',
                          'hover:bg-accent',
                          sortBy === opt.value
                            ? 'bg-brand/10 text-brand font-medium'
                            : 'text-foreground',
                        )}
                      >
                        <span className="w-4 text-center text-[14px] opacity-80">
                          {opt.icon}
                        </span>
                        <span className="flex-1">{opt.label}</span>
                        {sortBy === opt.value && (
                          <Icon name="check" className="h-3.5 w-3.5" />
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {error && (
            <div className="mx-5 mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-600">
              {error}
            </div>
          )}

          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {loading ? (
              <div className="flex items-center justify-center py-20">
                <span className="text-[13px] text-muted-foreground">加载中…</span>
              </div>
            ) : skills.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <Icon name="search" className="mb-2 h-8 w-8 text-muted-foreground/30" />
                <p className="text-[13px] text-muted-foreground">
                  {q.trim() ? `未找到「${q}」相关技能` : '市场暂无数据'}
                </p>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                  {skills.map((s) => {
                    const isInstalled = installedNames.has(s.name)
                    const installing = openingSet.has(s.id)
                    return (
                      <article
                        key={s.id}
                        className={cn(
                          'group relative flex flex-col gap-2 rounded-xl glass-soft p-3',
                          'border border-border/60 transition-colors hover:border-border',
                        )}
                      >
                        {/* 头部：技能首字头像 + 名称 + Star 角标 */}
                        <div className="flex items-start gap-2.5">
                          <Avatar
                            initial={s.name[0]?.toUpperCase() ?? '?'}
                            color="brand"
                            size={32}
                            className="flex-shrink-0"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5">
                              <h3 className="min-w-0 flex-1 truncate text-[13.5px] font-semibold leading-tight">
                                {s.name}
                              </h3>
                              <span
                                className="flex flex-shrink-0 items-center gap-0.5 rounded-md bg-amber-100 px-1.5 py-0.5 text-[10.5px] font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300"
                                title={`${s.stars} stars`}
                              >
                                ★ {fmtNum(s.stars)}
                              </span>
                            </div>
                            <div className="mt-0.5 truncate text-[11px] text-muted-foreground">
                              @{s.author}
                            </div>
                          </div>
                        </div>

                        {/* 描述（已含 description_zh 优先）—— flex-1 占满剩余空间，把底部行顶到底 */}
                        <p className="line-clamp-3 min-h-[3em] flex-1 text-[12px] leading-relaxed text-foreground/75">
                          {s.description || '暂无描述'}
                        </p>

                        {/* 底部：日期 + 2 个玻璃图标按钮 —— mt-auto 贴底 */}
                        <div className="mt-auto flex items-center justify-between gap-2 pt-2">
                          <span className="font-mono text-[10.5px] text-muted-foreground/70">
                            {formatDate(s.updated_at)}
                          </span>
                          <div className="flex items-center gap-1">
                            {/* 在 skillhub 查看：纯外链 */}
                            <GlassIconBtn
                              icon="globe"
                              title="在 skillhub 查看"
                              onClick={() => openOnSkillhub(s)}
                            />
                            {/* 安装 / 已安装：状态化 */}
                            <GlassIconBtn
                              icon={isInstalled ? 'check' : 'plus'}
                              title={
                                installing
                                  ? '安装中…'
                                  : isInstalled
                                    ? '已安装'
                                    : '安装'
                              }
                              onClick={() => !isInstalled && !installing && installSkill(s)}
                              disabled={isInstalled || installing}
                              variant={isInstalled ? 'default' : 'brand'}
                            />
                          </div>
                        </div>
                      </article>
                    )
                  })}
                </div>

                <p className="mt-5 text-center text-[11px] text-muted-foreground/50">
                  仅展示前 {PAGE_SIZE} 个结果，更多 skill 请访问{' '}
                  <a
                    href="https://www.skillhub.cn"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline hover:text-muted-foreground"
                  >
                    skillhub.cn
                  </a>{' '}
                  探索
                </p>
              </>
            )}
          </div>
        </>
      )}

      {/* ── 已安装 tab ── */}
      {tab === 'installed' && (
        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {installedLoading ? (
            <div className="flex items-center justify-center py-20">
              <span className="text-[13px] text-muted-foreground">加载中…</span>
            </div>
          ) : installed.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <Icon name="files" className="mb-2 h-8 w-8 text-muted-foreground/30" />
              <p className="text-[13px] font-medium">还没有安装 skill</p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                skillhub 上的 skill 目前需要在浏览器打开详情页手动集成
                <br />
                （暂未提供本地一键安装）
              </p>
              <Button variant="brand" size="sm" className="mt-4" onClick={() => setTab('market')}>
                <Icon name="search" className="h-3.5 w-3.5" />
                去市场看看
              </Button>
            </div>
          ) : (
            <>
              {/* 批量模式工具条 */}
              {installedBatchMode && (
                <div className="mb-3 flex items-center justify-between gap-2 rounded-lg border border-brand/30 bg-brand/5 px-3 py-2">
                  <div className="flex items-center gap-2 text-[12.5px]">
                    <Icon name="listCheck" className="h-3.5 w-3.5 text-brand" />
                    <span>
                      已选 <b className="text-brand">{installedSelected.size}</b> / {installed.length}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        if (installedSelected.size === installed.length) {
                          setInstalledSelected(new Set())
                        } else {
                          setInstalledSelected(new Set(installed.map((s) => s.name)))
                        }
                      }}
                    >
                      {installedSelected.size === installed.length ? '取消全选' : '全选'}
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={installedSelected.size === 0 || installedDeleting}
                      onClick={() => {
                        setBatchDeleteConfirm(Array.from(installedSelected))
                      }}
                    >
                      <Icon name="trash2" className="h-3.5 w-3.5" />
                      删除选中{installedSelected.size > 0 ? ` (${installedSelected.size})` : ''}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setInstalledBatchMode(false)
                        setInstalledSelected(new Set())
                      }}
                    >
                      退出批量
                    </Button>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                {installed.map((s) => {
                  const isSelected = installedSelected.has(s.name)
                  return (
                    <article
                      key={s.name}
                      onClick={installedBatchMode ? () => {
                        setInstalledSelected((prev) => {
                          const next = new Set(prev)
                          if (next.has(s.name)) next.delete(s.name)
                          else next.add(s.name)
                          return next
                        })
                      } : undefined}
                      className={cn(
                        'relative flex flex-col gap-2 rounded-xl glass-soft p-3 border transition-colors',
                        'border-border/60 hover:border-border',
                        installedBatchMode && 'cursor-pointer',
                        isSelected && 'border-brand bg-brand/10 ring-1 ring-brand/40',
                      )}
                    >
                      {/* 批量模式复选框（卡片右上角） */}
                      {installedBatchMode && (
                        <span
                          className={cn(
                            'absolute top-2 right-2 z-10 grid h-5 w-5 place-items-center rounded border-2',
                            isSelected
                              ? 'border-brand bg-brand text-white'
                              : 'border-muted-foreground/40 bg-background/80',
                          )}
                        >
                          {isSelected && <Icon name="check" className="h-3 w-3" strokeWidth={3} />}
                        </span>
                      )}

                      {/* 头部：头像 | 名+作者（竖排）| 按钮（贴右） */}
                      <div className="flex items-start gap-2.5">
                        <Avatar
                          initial={s.name[0]?.toUpperCase() ?? '?'}
                          color="sage"
                          size={32}
                          className="flex-shrink-0"
                        />
                        <div className="min-w-0 flex-1">
                          <h3 className="truncate text-[13.5px] font-semibold leading-tight">
                            {s.name}
                          </h3>
                          <div
                            className="mt-0.5 truncate text-[11px] text-muted-foreground/80"
                            title={s.author}
                          >
                            <span className="text-muted-foreground/50">@</span>
                            {s.author}
                          </div>
                        </div>

                        {/* 2 个玻璃图标按钮（贴右，跟头像同列）— 批量模式时隐藏 */}
                        {!installedBatchMode && (
                          <div
                            className="flex flex-shrink-0 items-center gap-1"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <GlassIconBtn
                              icon="files"
                              title="在文件资源管理器打开"
                              onClick={async () => {
                                try {
                                  const r = await fetch('/api/fs/reveal', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ path: s.path }),
                                  })
                                  if (!r.ok) {
                                    const data = await r.json().catch(() => ({}))
                                    setError(data.detail ?? `打开失败 (${r.status})`)
                                  }
                                } catch (e) {
                                  setError(e instanceof Error ? e.message : '打开失败')
                                }
                              }}
                            />
                            <GlassIconBtn
                              icon="trash2"
                              title="删除"
                              onClick={() => setDeleteConfirm(s.name)}
                            />
                          </div>
                        )}
                      </div>

                      {/* 描述：flex-1 占满剩余空间（没底部行了） */}
                      <p className="line-clamp-3 min-h-[3em] flex-1 text-[12px] leading-relaxed text-foreground/75">
                        {s.description || '暂无描述'}
                      </p>
                    </article>
                  )
                })}
              </div>
            </>
          )}
        </div>
      )}

      {/* 单个删除确认 */}
      <ConfirmDialog
        open={deleteConfirm !== null}
        title="删除 Skill"
        message={`确定删除「${deleteConfirm}」？此操作不可恢复。`}
        confirmLabel="删除"
        danger
        loading={installedDeleting}
        onConfirm={async () => {
          if (!deleteConfirm) return
          setInstalledDeleting(true)
          try {
            const r = await fetch(`/api/skills/library/${encodeURIComponent(deleteConfirm)}`, { method: 'DELETE' })
            if (!r.ok) { const d = await r.json().catch(() => ({})); setError(d.detail ?? `删除失败 (${r.status})`); return }
            setInstalled((prev) => prev.filter((x) => x.name !== deleteConfirm))
          } catch (e) {
            setError(e instanceof Error ? e.message : '删除失败')
          } finally {
            setInstalledDeleting(false)
            setDeleteConfirm(null)
          }
        }}
        onCancel={() => setDeleteConfirm(null)}
      />

      {/* 批量删除确认 */}
      <ConfirmDialog
        open={batchDeleteConfirm !== null}
        title="批量删除 Skill"
        message={`确定删除选中的 ${batchDeleteConfirm?.length ?? 0} 个 skill？此操作不可恢复。`}
        confirmLabel="删除"
        danger
        loading={installedDeleting}
        onConfirm={async () => {
          if (!batchDeleteConfirm) return
          setInstalledDeleting(true)
          try {
            const r = await fetch('/api/skills/library/batch-delete', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ names: batchDeleteConfirm }),
            })
            if (!r.ok) { const d = await r.json().catch(() => ({})); setError(d.detail ?? `删除失败 (${r.status})`); return }
            setInstalled((prev) => prev.filter((s) => !batchDeleteConfirm.includes(s.name)))
            setInstalledSelected(new Set())
            setInstalledBatchMode(false)
          } catch (e) {
            setError(e instanceof Error ? e.message : '删除失败')
          } finally {
            setInstalledDeleting(false)
            setBatchDeleteConfirm(null)
          }
        }}
        onCancel={() => setBatchDeleteConfirm(null)}
      />
    </div>
  )
}
