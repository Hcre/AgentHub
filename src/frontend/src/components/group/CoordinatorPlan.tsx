import { Avatar, Badge, Icon } from '../ui'
import { lookupActor } from './actors'
import type { CoordinatorPlan as Plan, Group } from '../../types'

/** 协调者的结构化分发方案卡。 */
export function CoordinatorPlan({ plan, group }: { plan: Plan; group?: Group }) {
  return (
    <div className="mt-2 overflow-hidden rounded-xl border bg-card">
      <header className="flex items-center gap-2 border-b border-border/70 bg-brand/5 px-4 py-2.5">
        <Icon name="network" className="h-3.5 w-3.5 text-brand" />
        <span className="font-mono text-[10.5px] uppercase tracking-wider text-brand">
          分发方案 · {plan.steps.length} 步
        </span>
        <div className="flex-1" />
        <Badge variant="brand">协调者</Badge>
      </header>
      {plan.summary && (
        <div className="px-4 py-3">
          <p className="text-[13.5px] leading-relaxed text-foreground/90 [text-wrap:pretty]">
            {plan.summary}
          </p>
        </div>
      )}
      <ol className="divide-y border-t">
        {plan.steps.map((s) => {
          const a = lookupActor(s.who, group)
          return (
            <li
              key={s.id}
              className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-muted/30"
            >
              <span className="w-7 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
                {s.id}
              </span>
              <div className="flex w-[120px] flex-shrink-0 items-center gap-2">
                <Avatar initial={a.initial} color={a.color} size={32} />
                <span className="truncate text-[12.5px] font-medium">{a.name}</span>
              </div>
              <span className="flex-1 truncate text-[13px]">{s.label}</span>
              {s.eta > 0 && (
                <span className="hidden items-center gap-1 font-mono text-[10.5px] text-muted-foreground md:inline-flex">
                  <Icon name="clock" className="h-3 w-3" />~{s.eta} min
                </span>
              )}
              <span className="hidden font-mono text-[10.5px] text-muted-foreground lg:inline">
                {s.depends.length ? `依赖 ${s.depends.join(', ')}` : '可立即开始'}
              </span>
            </li>
          )
        })}
      </ol>
      {plan.watchouts.length > 0 && (
        <div className="border-t bg-amber-50/40 px-4 py-2.5 dark:bg-amber-950/20">
          <div className="flex items-start gap-2">
            <Icon name="info" className="mt-0.5 h-3.5 w-3.5 text-amber-700 dark:text-amber-400" />
            <div className="space-y-0.5">
              {plan.watchouts.map((w, i) => (
                <div key={i} className="text-[12.5px] text-amber-800 dark:text-amber-300">
                  {w}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
      <footer className="flex items-center border-t bg-muted/20 px-4 py-2">
        <span className="font-mono text-[11px] text-muted-foreground">
          每个子任务作为独立任务执行，进度见顶部面板
        </span>
      </footer>
    </div>
  )
}
