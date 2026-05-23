import { Fragment } from 'react'
import { Avatar, Badge, Icon } from '../ui'
import { CoordinatorPlan } from './CoordinatorPlan'
import { lookupActor } from './actors'
import type { GroupMessage } from '../../types'

/** 把 @mention 渲染成内联高亮标签。 */
function renderRichText(text: string) {
  return text.split(/(@\S+)/g).map((part, i) =>
    part.startsWith('@') ? (
      <span
        key={i}
        className="inline-flex items-center rounded bg-brand/10 px-1.5 py-0.5 font-medium text-brand"
      >
        {part}
      </span>
    ) : (
      <Fragment key={i}>{part}</Fragment>
    ),
  )
}

export function GroupMessageItem({ msg }: { msg: GroupMessage }) {
  const actor = lookupActor(msg.who)
  const isUser = msg.from === 'user'
  const isCoordinator = msg.who === 'coordinator'
  return (
    <div className="animate-[var(--animate-fade-in)] flex gap-3">
      <div className="pt-0.5">
        <Avatar initial={actor.initial} color={actor.color} size={32} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-[13px] font-semibold">{actor.name}</span>
          {!isUser &&
            (isCoordinator ? (
              <Badge variant="brand">协调者</Badge>
            ) : (
              <Badge variant="brand">AI</Badge>
            ))}
          {msg.requiresApproval && (
            <Badge variant="warning" className="gap-1">
              <Icon name="shieldCheck" className="h-2.5 w-2.5" />
              待批准
            </Badge>
          )}
          <span className="font-mono text-[11px] text-muted-foreground">{msg.time}</span>
        </div>
        {msg.text && (
          <div className="text-[14px] leading-[1.6] text-foreground [text-wrap:pretty]">
            {msg.text.split('\n\n').map((p, i) => (
              <p key={i} className={i > 0 ? 'mt-2' : undefined}>
                {renderRichText(p)}
              </p>
            ))}
          </div>
        )}
        {msg.requiresApproval && (
          <div className="mt-2 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2 dark:border-amber-800 dark:bg-amber-950/30">
            <Icon name="shieldCheck" className="h-3.5 w-3.5 text-amber-700 dark:text-amber-400" />
            <span className="text-[12px] text-amber-900 dark:text-amber-200">
              已进入「收件箱 · 审批」。助手收到批准后才会执行。
            </span>
          </div>
        )}
        {msg.kind === 'plan' && msg.plan && <CoordinatorPlan plan={msg.plan} />}
      </div>
    </div>
  )
}
