import { cn } from '../../lib/cn'
import { Badge } from '../ui/Badge'
import { Icon } from '../ui'
import type { TemplateData } from '../../stores/templateStore'
import { getTierColor, getTierLabel } from '../../data/cliProviderMatrix'

export interface TemplateCardProps {
  template: TemplateData
  selected: boolean
  onClick: () => void
  /** Show action buttons (use/favorite/open web) — management mode */
  showActions?: boolean
  onUse?: () => void
  onFavorite?: () => void
  onOpenWeb?: (url: string) => void
}

const SOURCE_LABEL: Record<string, string> = {
  'wshobson-agents': 'GitHub',
  wshobson: 'GitHub',
  local: '本地',
}

export function TemplateCard({ template, selected, onClick, showActions, onUse, onFavorite, onOpenWeb }: TemplateCardProps) {
  const displayName = template.display_name_zh || template.name
  const displayDesc = template.description_zh || template.description
  const tierColor = getTierColor(template.model_tier)
  const tierLabel = getTierLabel(template.model_tier)

  const cardBody = (
    <>
      {/* Top row: tier badge + source */}
      <div className="flex items-center gap-2">
        <span
          className={cn(
            'inline-flex items-center rounded-md border px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wider',
            tierColor,
          )}
        >
          {tierLabel}
        </span>
        <Badge variant={template.source === 'local' ? 'default' : 'outline'}>
          {SOURCE_LABEL[template.source] ?? template.source}
        </Badge>
      </div>

      {/* Name */}
      <h3 className="text-[14px] font-semibold leading-snug text-foreground group-hover:text-brand transition-colors">
        {displayName}
      </h3>

      {/* Description */}
      <p className="line-clamp-2 text-[13px] leading-relaxed text-muted-foreground">
        {displayDesc || '暂无描述'}
      </p>

      {/* Footer: tools count + color dot (non-management) */}
      {!showActions && (
        <div className="mt-auto flex items-center gap-2 pt-1">
          {template.tools.length > 0 && (
            <span className="font-mono text-[10px] text-muted-foreground">
              {template.tools.length} 个工具
            </span>
          )}
          {template.color && (
            <span
              className="ml-auto h-2.5 w-2.5 rounded-full border"
              style={{ backgroundColor: template.color }}
            />
          )}
        </div>
      )}

      {/* Action buttons (management mode) */}
      {showActions && (
        <div className="mt-auto flex items-center gap-1 pt-2 border-t border-border/40">
          {onOpenWeb && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onOpenWeb(template.source_path ? `https://github.com/wshobson/agents/blob/main/${template.source_path}` : 'https://github.com/wshobson/agents') }}
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
          )}
          {onUse && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onUse() }}
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
          )}
          {onFavorite && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onFavorite() }}
              title="添加到常用"
              className={cn(
                'inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] transition-colors',
                'text-muted-foreground hover:bg-accent hover:text-foreground',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              )}
            >
              <Icon name="zap" className="h-3 w-3" />
              添加到常用
            </button>
          )}
        </div>
      )}
    </>
  )

  if (showActions) {
    return (
      <article
        className={cn(
          'group flex flex-col gap-2 rounded-xl border bg-card p-4 text-left transition-all',
          'hover:-translate-y-px hover:shadow-md',
          selected && 'border-brand ring-2 ring-brand/20',
        )}
      >
        {cardBody}
      </article>
    )
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'group flex flex-col gap-2 rounded-xl border bg-card p-4 text-left transition-all',
        'hover:-translate-y-px hover:shadow-md',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        selected && 'border-brand ring-2 ring-brand/20',
      )}
    >
      {cardBody}
    </button>
  )
}
