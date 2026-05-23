import { cn } from '../../lib/cn'
import { Button, Icon } from '../ui'
import type { Conversation } from '../../types'

export function ConversationTabs({
  convs,
  activeId,
  open,
  onPick,
  onToggle,
  onNew,
}: {
  convs: Conversation[]
  activeId: string | null
  open: boolean
  onPick: (id: string) => void
  onToggle: () => void
  onNew: () => void
}) {
  const active = convs.find((c) => c.id === activeId)
  return (
    <div className="relative flex items-center gap-2 border-b border-border/70 px-3 py-2.5">
      <div
        className={cn(
          'min-w-0 flex-1 overflow-hidden transition-all duration-300',
          open ? 'max-h-12 opacity-100' : 'pointer-events-none max-h-0 opacity-0',
        )}
      >
        <div className="flex gap-1.5 overflow-x-auto [scrollbar-width:none]">
          {convs.map((c) => (
            <button
              key={c.id}
              onClick={() => onPick(c.id)}
              data-active={activeId === c.id ? 'true' : undefined}
              className={cn(
                'flex min-w-[140px] flex-col items-start gap-0.5 rounded-md border px-3 py-1.5 text-left transition-colors hover:bg-accent',
                'data-[active=true]:border-brand/30 data-[active=true]:bg-brand/10',
              )}
            >
              <span className="text-[12px] font-semibold">{c.name}</span>
              <span className="max-w-[160px] truncate font-mono text-[10.5px] text-muted-foreground">
                {c.subtitle}
              </span>
            </button>
          ))}
          <button
            onClick={onNew}
            title="新建会话"
            className="flex w-9 items-center justify-center rounded-md border border-dashed text-muted-foreground hover:bg-accent hover:text-brand"
          >
            <Icon name="plus" className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      {!open && (
        <div className="flex flex-1 items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
          <span>历史会话</span>
          {active && (
            <span className="text-[12.5px] font-medium normal-case tracking-normal text-foreground">
              · {active.name}
            </span>
          )}
        </div>
      )}
      <Button variant="ghost" size="iconSm" onClick={onToggle} title={open ? '收起' : '展开'}>
        <Icon
          name="chevronUp"
          className={cn('h-3.5 w-3.5 transition-transform', !open && 'rotate-180')}
        />
      </Button>
    </div>
  )
}
