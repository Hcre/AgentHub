import { useEffect, useState } from 'react'
import type { TemplateData } from '../../stores/templateStore'
import { cn } from '../../lib/cn'
import { Avatar, Button, Icon } from '../ui'

export interface TemplateGridProps {
  templates: TemplateData[]
  loading: boolean
  error: string
  onTemplateClick: (template: TemplateData) => void
  selectedId?: string | null
  /** Search query (controlled from parent) */
  onSearch?: (q: string) => void
  /** Current model tier filter value */
  modelTier?: string
  /** Called when model tier filter changes */
  onModelTierChange?: (tier: string) => void
  /** Called when retry button is clicked (error state) */
  onRetry?: () => void
}

const MODEL_TIER_OPTIONS = [
  { value: '', label: '全部层级' },
  { value: 'inherit', label: 'inherit' },
  { value: 'fast', label: 'fast' },
  { value: 'smart', label: 'smart' },
  { value: 'max', label: 'max' },
]

function label(t: TemplateData): string {
  return t.display_name_zh || t.name
}

function desc(t: TemplateData): string {
  return t.description_zh || t.description || '暂无描述'
}

function sourceLabel(source: string): string {
  if (source === 'wshobson-agents') return 'GitHub'
  return source === 'local' ? '本地' : source
}

export function TemplateGrid({
  templates,
  loading,
  error,
  onTemplateClick,
  selectedId,
  onSearch,
  modelTier,
  onModelTierChange,
  onRetry,
}: TemplateGridProps) {
  const [searchInput, setSearchInput] = useState('')

  // Debounced search: flush to parent 300ms after user stops typing
  useEffect(() => {
    if (!onSearch) return
    const timer = setTimeout(() => {
      onSearch(searchInput)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchInput, onSearch])

  return (
    <div className="flex flex-col gap-3">
      {/* Search + filter bar (only when features enabled) */}
      {(onSearch || onModelTierChange) && (
        <div className="flex items-center gap-2">
          {onSearch && (
            <div className="relative flex-1">
              <Icon
                name="search"
                className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
              />
              <input
                className="h-9 w-full rounded-lg border border-border/60 bg-background/40 pl-9 pr-3 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="搜索模板名称或描述…"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </div>
          )}
          {onModelTierChange && (
            <select
              value={modelTier ?? ''}
              onChange={(e) => onModelTierChange(e.target.value)}
              className="h-9 rounded-lg border border-border/60 bg-background/40 px-3 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {MODEL_TIER_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          )}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <span className="text-[13px] text-muted-foreground">加载中…</span>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="flex items-center justify-between rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-600">
          <span className="truncate mr-2">{error}</span>
          {onRetry && (
            <Button variant="outline" size="sm" onClick={onRetry} className="shrink-0">
              重试
            </Button>
          )}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && templates.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Icon name="files" className="mb-2 h-8 w-8 text-muted-foreground/30" />
          <p className="text-[13px] text-muted-foreground">暂无模板</p>
          <p className="mt-1 text-[12px] text-muted-foreground">
            点击「同步模板」从 wshobson/agents 拉取，或点击「新建模板」手动创建
          </p>
        </div>
      )}

      {/* Grid */}
      {!loading && !error && templates.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
          {templates.map((t) => {
            const isSelected = selectedId === t.id
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => onTemplateClick(t)}
                className={cn(
                  'flex flex-col gap-2 rounded-xl glass-soft p-3 border text-left transition-colors',
                  'border-border/60 hover:border-border',
                  isSelected && 'border-brand bg-brand/5 ring-1 ring-brand/40',
                )}
              >
                {/* 头部：头像 + 名称 + 来源角标 */}
                <div className="flex items-start gap-2.5">
                  <Avatar
                    initial={(t.display_name_zh || t.name)[0]?.toUpperCase() ?? '?'}
                    color={t.color === 'sage' ? 'sage' : 'brand'}
                    size={32}
                    className="flex-shrink-0"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <h3 className="min-w-0 flex-1 truncate text-[13.5px] font-semibold leading-tight">
                        {label(t)}
                      </h3>
                      <span
                        className={cn(
                          'flex-shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium',
                          t.source === 'local'
                            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                            : 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
                        )}
                      >
                        {sourceLabel(t.source)}
                      </span>
                    </div>
                    <div className="mt-0.5 truncate text-[11px] text-muted-foreground">
                      {t.model_tier !== 'inherit' && (
                        <span className="mr-1.5 rounded bg-muted/60 px-1 py-px text-[10px]">
                          {t.model_tier}
                        </span>
                      )}
                      <span className="font-mono text-[10px] text-muted-foreground/60">
                        {t.name}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 描述 */}
                <p className="line-clamp-3 min-h-[3em] flex-1 text-[12px] leading-relaxed text-foreground/75">
                  {desc(t)}
                </p>

                {/* 底部：来源路径 + 推荐技能数 */}
                <div className="mt-auto flex items-center justify-between gap-2 pt-2">
                  <span className="font-mono truncate text-[10px] text-muted-foreground/50 max-w-[60%]">
                    {t.source_path || t.id.slice(0, 8)}
                  </span>
                  {t.recommended_skills.length > 0 && (
                    <span className="flex-shrink-0 rounded bg-muted/40 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                      {t.recommended_skills.length} skills
                    </span>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
