import { Fragment, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Avatar, Badge, Icon } from '../ui'
import { CoordinatorPlan } from './CoordinatorPlan'
import { lookupActor } from './actors'
import type { Group, GroupMessage } from '../../types'

/**
 * @mention 名字字符集：拉丁字母 / 数字 / 下划线 / 任意 Unicode 字母（含 CJK）。
 * 遇到任何标点（中英文）、空格、emoji 立刻停 —— 避免 @工程师，xxx 把"，xxx"也吞掉。
 */
const MENTION_RE = /(@[\p{L}\p{N}_]+)/gu

/** 把 @mention 渲染成内联高亮标签；递归处理 ReactNode 树。 */
function highlightMentions(children: ReactNode): ReactNode {
  if (typeof children === 'string') {
    const parts = children.split(MENTION_RE)
    if (parts.length === 1) return children
    return parts.map((part, i) =>
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
  if (Array.isArray(children)) {
    return children.map((c, i) => <Fragment key={i}>{highlightMentions(c)}</Fragment>)
  }
  return children
}

export function GroupMessageItem({ msg, group }: { msg: GroupMessage; group?: Group }) {
  const actor = lookupActor(msg.who, group)
  const isUser = msg.from === 'user'
  const isCoordinator = !!group?.coordinatorId && msg.who === group.coordinatorId
  return (
    <div
      className="group/msg -mx-2 flex gap-3 rounded-lg px-2 py-1.5 transition-all duration-150 hover:bg-muted/40 hover:shadow-sm hover:ring-1 hover:ring-border/60 animate-[var(--animate-fade-in)]"
    >
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
          <div className="prose prose-sm max-w-none text-[14px] leading-[1.6] text-foreground [text-wrap:pretty]">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
              components={{
                p: ({ children }: any) => (
                  <p className="mb-2 last:mb-0">{highlightMentions(children)}</p>
                ),
                li: ({ children }: any) => <li>{highlightMentions(children)}</li>,
                pre: ({ children }: any) => (
                  <pre className="my-2 overflow-x-auto rounded-lg border border-slate-700/50 bg-slate-800 p-3 text-[12px] leading-[1.5] text-slate-100">
                    {children}
                  </pre>
                ),
                code: ({ className, children, ...props }: any) => {
                  const text = String(children ?? '')
                  const isBlock =
                    text.includes('\n') ||
                    (typeof className === 'string' && className.includes('language-'))
                  return isBlock ? (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  ) : (
                    <code
                      className="rounded bg-muted/50 px-1 py-0.5 font-mono text-[12px] text-foreground"
                      {...props}
                    >
                      {children}
                    </code>
                  )
                },
                a: ({ href, children }: any) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener"
                    className="text-brand underline"
                  >
                    {children}
                  </a>
                ),
              }}
            >
              {msg.text}
            </ReactMarkdown>
            {msg.streaming && (
              <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-foreground/60 align-text-bottom" />
            )}
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
        {msg.kind === 'plan' && msg.plan && <CoordinatorPlan plan={msg.plan} group={group} />}
      </div>
    </div>
  )
}
