import { useEffect, useMemo, useState } from 'react'
import { cn } from '../../lib/cn'
import { useInboxStore } from '../../stores/inboxStore'
import { Badge, Button, Icon, Tabs, TabsList, TabsTrigger } from '../ui'
import type { DiffLine, InboxItem, InboxType } from '../../types'

const TABS: { id: InboxType | 'all'; label: string }[] = [
  { id: 'all', label: '全部' },
  { id: 'approval', label: '审批' },
  { id: 'task', label: '任务' },
  { id: 'system', label: '系统' },
]

const diffCls = (kind: DiffLine['kind']) =>
  kind === 'add'
    ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
    : kind === 'del'
      ? 'bg-destructive/10 text-destructive'
      : 'text-muted-foreground'

const diffPrefix = (kind: DiffLine['kind']) => (kind === 'add' ? '+' : kind === 'del' ? '-' : ' ')

function InboxCard({ item }: { item: InboxItem }) {
  const { markRead, resolve } = useInboxStore()
  return (
    <article
      onMouseEnter={() => item.unread && markRead(item.id)}
      className="overflow-hidden rounded-xl border bg-card"
    >
      <header className="flex items-center gap-2.5 border-b bg-muted/30 px-4 py-2.5">
        <Badge
          variant={
            item.type === 'approval' ? 'warning' : item.type === 'task' ? 'brand' : 'outline'
          }
        >
          {item.type === 'approval' ? '审批' : item.type === 'task' ? '任务' : '系统'}
        </Badge>
        <span className="truncate text-[13px] font-medium">{item.title}</span>
        <div className="flex-1" />
        {item.unread && <span className="h-1.5 w-1.5 rounded-full bg-brand" />}
        <span className="font-mono text-[11px] text-muted-foreground">{item.when}</span>
      </header>
      <div className="space-y-3 p-4">
        <p className="text-[13px] leading-relaxed text-foreground/90 [text-wrap:pretty]">
          {item.summary}
        </p>
        {item.diff && (
          <div className="overflow-hidden rounded-md border font-mono text-[11.5px]">
            {item.diff.map((d, i) => (
              <div key={i} className={cn('flex gap-2 px-2.5 py-1', diffCls(d.kind))}>
                <span className="select-none opacity-60">{diffPrefix(d.kind)}</span>
                <span className="truncate">{d.text}</span>
              </div>
            ))}
          </div>
        )}
        {item.impact && (
          <div className="font-mono text-[11px] text-muted-foreground">{item.impact}</div>
        )}
        {item.type === 'approval' && (
          <div className="flex gap-2">
            <Button variant="brand" size="sm" onClick={() => resolve(item.id, 'approve')}>
              <Icon name="check" className="h-3.5 w-3.5" />
              批准
            </Button>
            <Button variant="outline" size="sm" onClick={() => resolve(item.id, 'reject')}>
              <Icon name="x" className="h-3.5 w-3.5" />
              驳回
            </Button>
          </div>
        )}
      </div>
    </article>
  )
}

export function InboxView() {
  const items = useInboxStore((s) => s.items)
  const load = useInboxStore((s) => s.load)
  const [tab, setTab] = useState<InboxType | 'all'>('all')

  useEffect(() => {
    void load()
  }, [load])
  const filtered = useMemo(() => items.filter((i) => tab === 'all' || i.type === tab), [items, tab])

  return (
    <div className="flex h-full flex-col gap-4 px-6 py-5">
      <div className="flex items-center justify-between">
        <h2 className="text-[17px] font-medium">收件箱</h2>
        <Tabs value={tab} onValueChange={(v) => setTab(v as InboxType | 'all')}>
          <TabsList className="h-8">
            {TABS.map((t) => (
              <TabsTrigger key={t.id} value={t.id} className="h-6 px-3 text-[12px]">
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {filtered.length === 0 ? (
          <div className="py-16 text-center font-mono text-[11.5px] text-muted-foreground">
            收件箱已清空
          </div>
        ) : (
          filtered.map((i) => <InboxCard key={i.id} item={i} />)
        )}
      </div>
    </div>
  )
}
