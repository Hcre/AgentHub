import { useCallback, useEffect, useState } from 'react'
import { Button, Dialog, DialogContent, Icon, Input, Textarea } from '../ui'
import { cn } from '../../lib/cn'
import { useTemplateStore, type TemplateData, type SyncResult } from '../../stores/templateStore'
import { getTierColor, getTierLabel } from '../../data/cliProviderMatrix'

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

function SyncStatusDot({ lastSynced }: { lastSynced: string | null }) {
  const [hoursAgo, setHoursAgo] = useState<number | null>(null)

  useEffect(() => {
    queueMicrotask(() => {
      if (lastSynced) {
        const syncedAt = new Date(lastSynced).getTime()
        setHoursAgo((Date.now() - syncedAt) / (1000 * 60 * 60))
      } else {
        setHoursAgo(null)
      }
    })
  }, [lastSynced])

  if (hoursAgo === null) {
    return <span className="h-2.5 w-2.5 rounded-full bg-gray-400 flex-shrink-0" title="从未同步" />
  }
  if (hoursAgo > 24) {
    return <span className="h-2.5 w-2.5 rounded-full bg-yellow-500 flex-shrink-0" title="超过24小时未同步" />
  }
  return <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 flex-shrink-0" title="已同步" />
}

function formatSyncTime(lastSynced: string | null): string {
  if (!lastSynced) return '从未同步'
  const d = new Date(lastSynced)
  return d.toLocaleString('zh-CN')
}

/** Build GitHub URL from template source_path.
 *  Expected format: plugins/{plugin}/agents/{agent}.md */
function buildGitHubUrl(t: TemplateData): string {
  const path = t.source_path || ''
  if (path) {
    return `https://github.com/wshobson/agents/blob/main/${path}`
  }
  // Fallback: construct from name
  return `https://github.com/wshobson/agents`
}

// ── Favorite dialog ──

interface FavoriteDialogProps {
  open: boolean
  template: TemplateData | null
  onClose: () => void
  onSaved: () => void
}

function FavoriteDialog({ open, template, onClose, onSaved }: FavoriteDialogProps) {
  const [name, setName] = useState(template?.display_name_zh || template?.name || '')
  const [description, setDescription] = useState(template?.description_zh || template?.description || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSave = async () => {
    if (!template || !name.trim()) return
    setSaving(true)
    setError('')
    try {
      const r = await fetch(`/api/templates/${template.id}/favorite`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          is_favorite: true,
          favorite_name: name.trim(),
          favorite_description: description.trim(),
        }),
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        throw new Error(d.detail || `添加失败 (${r.status})`)
      }
      onSaved()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : '添加失败')
    } finally {
      setSaving(false)
    }
  }

  if (!open || !template) return null

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="w-[420px]">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="text-[15px] font-medium">添加到常用</h3>
          <Button variant="ghost" size="iconSm" onClick={onClose}>
            <Icon name="x" className="h-3.5 w-3.5" />
          </Button>
        </header>

        <div className="flex flex-col gap-3 p-4">
          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-600">
              {error}
            </div>
          )}

          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">模板显示名</span>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="模板显示名"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">模板简介</span>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="模板简介"
              className="min-h-[60px]"
            />
          </label>
        </div>

        <footer className="flex justify-end gap-2 border-t px-4 py-3">
          <Button variant="outline" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button variant="brand" size="sm" onClick={handleSave} disabled={saving || !name.trim()}>
            {saving ? (
              <>
                <Spinner />
                保存中…
              </>
            ) : (
              <>
                <Icon name="check" className="h-3.5 w-3.5" />
                保存
              </>
            )}
          </Button>
        </footer>
      </DialogContent>
    </Dialog>
  )
}

// ── Main tab ──

export interface TemplateManagementTabProps {
  /** Called when user clicks "使用该模板". Parent should open CreateAgentModal
   *  with preSelectedTemplate derived from this template's detail. */
  onUseTemplate?: (template: TemplateData) => void
}

export function TemplateManagementTab({ onUseTemplate }: TemplateManagementTabProps) {
  const templates = useTemplateStore((s) => s.templates)
  const loading = useTemplateStore((s) => s.loading)
  const error = useTemplateStore((s) => s.error)
  const sourceStatus = useTemplateStore((s) => s.sourceStatus)
  const sourceLoading = useTemplateStore((s) => s.sourceLoading)
  const syncing = useTemplateStore((s) => s.syncing)
  const loadTemplates = useTemplateStore((s) => s.loadTemplates)
  const getSourceStatus = useTemplateStore((s) => s.getSourceStatus)
  const syncSource = useTemplateStore((s) => s.syncSource)

  const [toast, setToast] = useState<string | null>(null)
  const [favOpen, setFavOpen] = useState(false)
  const [favTemplate, setFavTemplate] = useState<TemplateData | null>(null)

  // Load data on mount
  useEffect(() => {
    loadTemplates()
    getSourceStatus()
  }, [loadTemplates, getSourceStatus])

  const handleSync = useCallback(async () => {
    try {
      const result: SyncResult = await syncSource()
      setToast('同步完成: 新增 ' + result.added + ', 更新 ' + result.updated)
    } catch {
      setToast('同步失败，请重试')
    } finally {
      setTimeout(() => setToast(null), 3000)
    }
  }, [syncSource])

  // Only show templates from wshobson/agents (synced from GitHub)
  const ghTemplates = templates.filter((t) => t.source !== 'local')

  const handleOpenWeb = (t: TemplateData) => {
    window.open(buildGitHubUrl(t), '_blank', 'noopener,noreferrer')
  }

  const handleUseTemplate = (t: TemplateData) => {
    onUseTemplate?.(t)
  }

  const handleAddFavorite = (t: TemplateData) => {
    setFavTemplate(t)
    setFavOpen(true)
  }

  const handleFavSaved = () => {
    loadTemplates()
  }

  return (
    <div className="flex h-full flex-col min-h-0 overflow-hidden">
      {/* Top bar */}
      <div className="flex items-center justify-between gap-3 border-b border-border/70 px-5 py-3.5">
        <div className="flex items-center gap-2">
          <h2 className="text-[15px] font-semibold">模板管理</h2>
          <span className="rounded bg-muted/60 px-1.5 py-0.5 text-[11px] text-muted-foreground tabular-nums">
            {ghTemplates.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleSync}
            disabled={syncing}
          >
            {syncing ? (
              <>
                <Spinner />
                同步中
              </>
            ) : (
              <>
                <Icon name="zap" className="h-3.5 w-3.5" />
                同步模板
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Source status card */}
      <div className="border-b border-border/70 px-5 py-3">
        {sourceLoading ? (
          <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
            <Spinner />
            加载来源状态…
          </div>
        ) : sourceStatus ? (
          <div className="flex items-center gap-3 rounded-lg border border-border/60 glass-soft px-3 py-2.5">
            <SyncStatusDot lastSynced={sourceStatus.last_synced} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[13px] font-medium">{sourceStatus.url || 'wshobson/agents'}</span>
                <span className="text-[11px] text-muted-foreground">{sourceStatus.branch}</span>
              </div>
              <div className="flex items-center gap-3 mt-0.5 text-[11px] text-muted-foreground">
                <span>模板数: {sourceStatus.template_count}</span>
                <span>上次同步: {formatSyncTime(sourceStatus.last_synced)}</span>
              </div>
            </div>
            {sourceStatus.description_zh && (
              <span className="hidden sm:inline text-[11px] text-muted-foreground/70 max-w-[200px] truncate">
                {sourceStatus.description_zh}
              </span>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2 rounded-lg border border-dashed border-border/60 px-3 py-2.5 text-[12px] text-muted-foreground">
            <Icon name="info" className="h-3.5 w-3.5" />
            尚未配置模板来源，点击「同步模板」初始化
          </div>
        )}
      </div>

      {/* Error display */}
      {error && (
        <div className="mx-5 mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-600">
          {error}
        </div>
      )}

      {/* Template cards grid */}
      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <span className="text-[13px] text-muted-foreground">加载中…</span>
          </div>
        ) : ghTemplates.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <Icon name="files" className="mb-2 h-8 w-8 text-muted-foreground/30" />
            <p className="text-[13px] text-muted-foreground">暂无模板</p>
            <p className="mt-1 text-[12px] text-muted-foreground">
              点击「同步模板」从 wshobson/agents 拉取
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
            {ghTemplates.map((t) => {
              const displayName = t.display_name_zh || t.name
              const displayDesc = t.description_zh || t.description || '暂无描述'
              const tierColor = getTierColor(t.model_tier)
              const tierLabel = getTierLabel(t.model_tier)

              return (
                <article
                  key={t.id}
                  className={cn(
                    'group relative flex flex-col gap-2 rounded-xl glass-soft p-3',
                    'border border-border/60 transition-colors hover:border-border',
                  )}
                >
                  {/* Header: name + tier badge + source badge */}
                  <div className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <h3 className="truncate text-[13.5px] font-semibold leading-tight">
                        {displayName}
                      </h3>
                      <div className="mt-1 flex items-center gap-1.5">
                        {t.model_tier !== 'inherit' && (
                          <span
                            className={cn(
                              'inline-flex items-center rounded-md border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider',
                              tierColor,
                            )}
                          >
                            {tierLabel}
                          </span>
                        )}
                        <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                          GitHub
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Description */}
                  <p className="line-clamp-3 min-h-[3em] flex-1 text-[12px] leading-relaxed text-foreground/75">
                    {displayDesc}
                  </p>

                  {/* Footer: 3 action buttons */}
                  <div className="mt-auto flex items-center gap-1 pt-2 border-t border-border/40">
                    <button
                      type="button"
                      onClick={() => handleOpenWeb(t)}
                      title="打开网页"
                      className={cn(
                        'inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] transition-colors',
                        'text-muted-foreground hover:bg-accent hover:text-foreground',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      )}
                    >
                      <Icon name="globe" className="h-3 w-3" />
                      打开网页
                    </button>
                    <button
                      type="button"
                      onClick={() => handleUseTemplate(t)}
                      title="使用该模板"
                      className={cn(
                        'inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] transition-colors',
                        'text-brand hover:bg-brand/10',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      )}
                    >
                      <Icon name="rocket" className="h-3 w-3" />
                      使用该模板
                    </button>
                    <button
                      type="button"
                      onClick={() => handleAddFavorite(t)}
                      title="添加到常用"
                      className={cn(
                        'inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] transition-colors',
                        'text-muted-foreground hover:bg-accent hover:text-foreground',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      )}
                    >
                      <Icon name="pin" className="h-3 w-3" />
                      添加到常用
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </div>

      {/* Favorite dialog */}
      <FavoriteDialog
        key={favTemplate?.id ?? 'none'}
        open={favOpen}
        template={favTemplate}
        onClose={() => setFavOpen(false)}
        onSaved={handleFavSaved}
      />

      {/* Toast notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 animate-[var(--animate-slide-in)] rounded-lg border border-border/60 bg-background px-4 py-2.5 text-[13px] shadow-lg glass-soft">
          {toast}
        </div>
      )}
    </div>
  )
}
