import { useMemo, useState } from 'react'
import { activity } from '../../data/extra'
import { user } from '../../data/mock'
import { Avatar, Badge, Icon } from '../ui'

export function ActivityFeed() {
  const [q, setQ] = useState('')
  const filtered = useMemo(
    () =>
      activity.filter(
        (e) => !q || `${e.text} ${e.tools.join(' ')}`.toLowerCase().includes(q.toLowerCase()),
      ),
    [q],
  )

  return (
    <div className="flex h-full flex-col gap-4 overflow-hidden px-6 py-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex h-8 items-center gap-1.5 rounded-md border bg-background px-2.5 text-muted-foreground">
          <Icon name="search" className="h-3.5 w-3.5" />
          <input
            placeholder="搜索活动…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-56 bg-transparent text-[12.5px] outline-none placeholder:text-muted-foreground"
          />
        </div>
        <span className="font-mono text-[11.5px] text-muted-foreground">
          {filtered.length} / {activity.length} 个回合
        </span>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {filtered.length === 0 && (
          <div className="py-16 text-center font-mono text-[11.5px] text-muted-foreground">
            没有匹配的活动
          </div>
        )}
        {filtered.map((e) => (
          <article
            key={e.id}
            className="overflow-hidden rounded-xl border bg-card transition-colors hover:bg-muted/20"
          >
            <header className="flex items-center gap-2.5 border-b bg-muted/30 px-4 py-2.5">
              <Badge variant="brand">消息</Badge>
              <Avatar initial={user.initial} color="neutral" size={20} />
              <span className="text-[13px] font-medium">{user.handle}</span>
              <div className="flex-1" />
              {e.latest && <Badge variant="brand">最新</Badge>}
              <span className="font-mono text-[11px] text-muted-foreground">{e.when}</span>
              <span className="font-mono text-[11px] text-muted-foreground">{e.count} 个事件</span>
            </header>
            <div className="space-y-3 p-4">
              <div className="inline-flex items-center gap-2 rounded-md border border-dashed bg-background px-2 py-1 text-muted-foreground">
                <Icon name="settings" className="h-3 w-3" />
                <span className="font-mono text-[11.5px]">使用了 {e.tools.length} 个工具</span>
              </div>
              <p className="text-[13.5px] leading-relaxed [text-wrap:pretty]">{e.text}</p>
              {e.running && (
                <div>
                  <Badge variant="brand">运行中</Badge>
                </div>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
