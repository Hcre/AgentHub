import { useCallback, useEffect, useState } from 'react'
import {
  CheckCircle2,
  ExternalLink,
  Loader2,
  Rocket,
  TriangleAlert,
  Clock,
  Trash2,
  RefreshCw,
} from 'lucide-react'
import { deployApi, type Deployment, type DeployStatus } from '../../api/deploy'
import { cn } from '../../lib/cn'

/**
 * DeployPanel — 部署 tab 内容
 * - 列出会话历史部署（按 session_id 过滤）
 * - 4 状态色卡（复用 DeployCard 的视觉语言）
 * - 点击行展开 build_logs + preview/download 链接
 * - 删除按钮（确认弹窗）+ 刷新按钮
 */

const STATUS_STYLES: Record<
  DeployStatus,
  { wrap: string; icon: string; label: string; tone: string }
> = {
  queued: {
    wrap: 'border-zinc-300 bg-zinc-100/60 dark:bg-zinc-900/40 dark:border-zinc-700',
    icon: 'text-zinc-500',
    label: '排队中',
    tone: 'text-zinc-600 dark:text-zinc-400',
  },
  building: {
    wrap: 'border-blue-300 bg-blue-50/60 dark:bg-blue-950/30 dark:border-blue-800',
    icon: 'text-blue-500',
    label: '构建中',
    tone: 'text-blue-600 dark:text-blue-400',
  },
  ready: {
    wrap: 'border-emerald-300 bg-emerald-50/60 dark:bg-emerald-950/30 dark:border-emerald-800',
    icon: 'text-emerald-600 dark:text-emerald-400',
    label: '已就绪',
    tone: 'text-emerald-600 dark:text-emerald-400',
  },
  failed: {
    wrap: 'border-rose-300 bg-rose-50/60 dark:bg-rose-950/30 dark:border-rose-800',
    icon: 'text-rose-500',
    label: '失败',
    tone: 'text-rose-600 dark:text-rose-400',
  },
}

function StatusIcon({ status }: { status: DeployStatus }) {
  if (status === 'queued')
    return <Clock className={cn('h-3.5 w-3.5', STATUS_STYLES[status].icon)} />
  if (status === 'building')
    return <Loader2 className={cn('h-3.5 w-3.5 animate-spin', STATUS_STYLES[status].icon)} />
  if (status === 'ready')
    return <CheckCircle2 className={cn('h-3.5 w-3.5', STATUS_STYLES[status].icon)} />
  return <TriangleAlert className={cn('h-3.5 w-3.5', STATUS_STYLES[status].icon)} />
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', {
      hour12: false,
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function isUuid(s: string | null | undefined): boolean {
  return !!s && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s)
}

export function DeployPanel({ sessionId }: { sessionId?: string | null }) {
  const [items, setItems] = useState<Deployment[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const validSession = isUuid(sessionId ?? null) ? (sessionId as string) : null

  const load = useCallback(async () => {
    if (!validSession) {
      setItems([])
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await deployApi.list({ session_id: validSession })
      setItems(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载部署历史失败')
    } finally {
      setLoading(false)
    }
  }, [validSession])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load()
  }, [load])

  // 自动刷新：building/queued 状态下每 3s 重拉
  useEffect(() => {
    if (items.length === 0) return
    const hasInFlight = items.some((d) => d.status === 'queued' || d.status === 'building')
    if (!hasInFlight) return
    const t = setInterval(() => void load(), 3000)
    return () => clearInterval(t)
  }, [items, load])

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleDelete = async (id: string) => {
    try {
      await deployApi.remove(id)
      setItems((prev) => prev.filter((d) => d.id !== id))
      setConfirmDelete(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败')
    }
  }

  if (!validSession) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-center text-sm text-muted-foreground">
        <div>
          <Rocket className="mx-auto mb-3 h-6 w-6 opacity-50" />
          <p>请先选择一个聊天会话</p>
          <p className="mt-1 text-[11.5px]">部署历史按 session 过滤</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border/70 px-3 py-2">
        <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
          <Rocket className="h-3.5 w-3.5" />
          <span>部署历史</span>
          <span className="font-mono text-[11px]">· {items.length} 条</span>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          aria-label="刷新"
          title="刷新"
          className="grid h-6 w-6 place-items-center rounded text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50"
        >
          <RefreshCw className={cn('h-3 w-3', loading && 'animate-spin')} />
        </button>
      </div>
      {error && (
        <div className="mx-3 mt-2 rounded border border-rose-300 bg-rose-50/60 px-2 py-1 text-[11.5px] text-rose-700 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-300">
          {error}
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        {loading && items.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[12px] text-muted-foreground">
            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
            加载中…
          </div>
        ) : items.length === 0 ? (
          <div className="flex h-full items-center justify-center text-center text-[12px] text-muted-foreground">
            <div>
              <Rocket className="mx-auto mb-2 h-5 w-5 opacity-40" />
              <p>暂无部署记录</p>
              <p className="mt-1 text-[11px]">在聊天中发送「部署」指令即可创建</p>
            </div>
          </div>
        ) : (
          <ul className="space-y-2">
            {items.map((d) => {
              const isOpen = expanded.has(d.id)
              const style = STATUS_STYLES[d.status]
              return (
                <li
                  key={d.id}
                  data-testid="deploy-row"
                  data-status={d.status}
                  className={cn('rounded-lg border p-2.5 text-[12px]', style.wrap)}
                >
                  <div className="flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => toggleExpand(d.id)}
                      className="flex min-w-0 flex-1 items-center gap-2 text-left"
                    >
                      <StatusIcon status={d.status} />
                      <span className={cn('font-medium', style.tone)}>{style.label}</span>
                      <span className="font-mono text-[11px] text-muted-foreground">
                        {d.id.slice(0, 8)}
                      </span>
                      <span className="text-muted-foreground">·</span>
                      <span className="truncate text-muted-foreground">
                        {d.framework || d.target}
                      </span>
                    </button>
                    <div className="flex items-center gap-1">
                      {d.status === 'ready' && d.preview_url && (
                        <a
                          href={d.preview_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="grid h-6 w-6 place-items-center rounded text-muted-foreground hover:bg-emerald-100 hover:text-emerald-700 dark:hover:bg-emerald-900/40"
                          title="打开预览"
                          aria-label="打开预览"
                        >
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          setConfirmDelete(d.id)
                        }}
                        className="grid h-6 w-6 place-items-center rounded text-muted-foreground hover:bg-rose-100 hover:text-rose-700 dark:hover:bg-rose-900/40"
                        title="删除"
                        aria-label="删除部署"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[11px] text-muted-foreground">
                    <span>{formatTime(d.created_at)}</span>
                    {d.status === 'building' && (
                      <span className="font-mono">
                        {Math.round(d.progress * 100)}% · {d.stage ?? '构建中'}
                      </span>
                    )}
                    {d.status === 'failed' && d.error_code && (
                      <span className="font-mono text-rose-600 dark:text-rose-400">
                        {d.error_code}
                      </span>
                    )}
                  </div>
                  {d.status === 'building' && (
                    <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-blue-100 dark:bg-blue-950/40">
                      <div
                        className="h-full bg-blue-500 transition-all"
                        style={{ width: `${Math.round(d.progress * 100)}%` }}
                      />
                    </div>
                  )}
                  {isOpen && (
                    <div className="mt-2 space-y-1.5 border-t border-current/10 pt-2 text-[11.5px]">
                      {d.preview_url && (
                        <div className="flex items-center gap-1.5">
                          <span className="text-muted-foreground">预览：</span>
                          <a
                            href={d.preview_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="truncate font-mono text-emerald-600 hover:underline dark:text-emerald-400"
                            title={d.preview_url}
                          >
                            {d.preview_url.length > 60
                              ? d.preview_url.slice(0, 60) + '…'
                              : d.preview_url}
                          </a>
                        </div>
                      )}
                      {d.download_url && (
                        <div className="flex items-center gap-1.5">
                          <span className="text-muted-foreground">下载：</span>
                          <a
                            href={d.download_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="truncate font-mono text-emerald-600 hover:underline dark:text-emerald-400"
                            title={d.download_url}
                          >
                            {d.download_url}
                          </a>
                        </div>
                      )}
                      {d.error_message && (
                        <div className="rounded border border-rose-300/60 bg-rose-50/60 px-2 py-1 text-rose-700 dark:border-rose-800/60 dark:bg-rose-950/20 dark:text-rose-300">
                          {d.error_message}
                        </div>
                      )}
                      {d.build_logs.length > 0 && (
                        <details className="rounded border border-border/60 bg-background/40 px-2 py-1">
                          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                            构建日志 ({d.build_logs.length} 行)
                          </summary>
                          <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap font-mono text-[10.5px] text-muted-foreground">
                            {d.build_logs.join('\n')}
                          </pre>
                        </details>
                      )}
                      <div className="flex items-center gap-1.5 text-muted-foreground">
                        <span>TTL：</span>
                        <span className="font-mono">{d.ttl}s</span>
                        {d.entry_file && (
                          <>
                            <span>·</span>
                            <span>入口：</span>
                            <span className="font-mono">{d.entry_file}</span>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>
      {confirmDelete && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 grid place-items-center bg-black/40"
          onClick={() => setConfirmDelete(null)}
        >
          <div
            className="w-80 max-w-[90vw] rounded-lg border bg-card p-4 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-sm font-semibold">确认删除部署？</h3>
            <p className="mt-1 text-[12px] text-muted-foreground">
              将软删（status=deleted），不可恢复。
            </p>
            <div className="mt-3 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmDelete(null)}
                className="rounded border border-border/70 bg-card px-3 py-1.5 text-[12px] hover:bg-muted"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void handleDelete(confirmDelete)}
                className="rounded bg-rose-600 px-3 py-1.5 text-[12px] text-white hover:bg-rose-700"
              >
                删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
