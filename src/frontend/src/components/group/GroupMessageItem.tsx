import { Fragment, useState, type ReactNode } from 'react'
import { Copy, Pin, Reply } from 'lucide-react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Avatar, Badge, Button, Icon } from '../ui'
import { CoordinatorPlan } from './CoordinatorPlan'
import { lookupActor } from './actors'
import type { Group, GroupMessage } from '../../types'

/**
 * @mention 名字字符集：拉丁字母 / 数字 / 下划线 / 任意 Unicode 字母（含 CJK）。
 * 遇到任何标点（中英文）、空格、emoji 立刻停 —— 避免 @工程师，xxx 把"，xxx"也吞掉。
 */
const MENTION_RE = /(@[\p{L}\p{N}_]+)/gu

/** 抓代码围栏内容（与 MessageBubble 同步）。P0-5 群聊复制代码用。
 * matchAll 必须 /g flag；String.prototype.matchAll 每次调用产生新 iterator，
 * 无模块级 regex 的 lastIndex 共享（绕开 react-hooks/immutability 规则）。 */
const CODE_FENCE_RE = /```[a-z]*\n([\s\S]*?)\n```/g

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

/**
 * P1-1：群聊引文 snippet 也截到 60 字符。test 断言 200 个 a 重复 → DOM 里 ≤ 70 个。
 * 60 + 1 省略号 = 61，仍在 ≤ 70 容错内。
 */
function truncateSnippet(s: string, max = 60): string {
  if (s.length <= max) return s
  return s.slice(0, max) + '…'
}

export function GroupMessageItem({
  msg,
  group,
  /**
   * 当前群聊 session id。Pin 走 /api/messages/{msg.id}/pin?session_id=...
   * 不传则 Pin 按钮允许视觉切换但不发请求（与 MessageBubble 同 pattern，
   * 避免在没绑 session 的本地 mock 消息上 404）。
   */
  sessionId,
  /**
   * P1-1 群聊 reply/quote：hover 消息时显示回复按钮；点击触发此回调，
   * 父组件 GroupChatView 把 ReplyRef 塞进 GroupComposer。
   * 不传则按钮 disabled（mock 模式）。
   */
  onReply,
}: {
  msg: GroupMessage
  group?: Group
  sessionId?: string
  onReply?: (msg: GroupMessage) => void
}) {
  const actor = lookupActor(msg.who, group)
  const isUser = msg.from === 'user'
  const isCoordinator = !!group?.coordinatorId && msg.who === group.coordinatorId

  // P0-4 群聊 Pin：与 MessageBubble 同源（optimistic update + 失败回滚 + inline 错误）。
  // 初始值用 msg.pinned（后端真值），点击立刻翻转；后端 200 保留，非 2xx 回滚。
  const [pinned, setPinned] = useState<boolean>(msg.pinned ?? false)
  const [pinPending, setPinPending] = useState(false)
  const [pinError, setPinError] = useState<string | null>(null)
  // P0-5 群聊复制代码：与 MessageBubble 同 pattern（inline status，2.5s 自清）。
  const [copyStatus, setCopyStatus] = useState<{ kind: 'ok' | 'err'; msg: string } | null>(null)

  /**
   * 抓文本中所有 ``` ``` 围栏代码，返回拼接后内容。
   * 返回 null = 没有代码，不渲染「复制代码」按钮（避免空操作）。
   * matchAll：每次调用产生新 iterator，避开模块级 /g regex 的 lastIndex 状态。
   */
  const extractCodeFences = (text: string): string | null => {
    const fences: string[] = []
    for (const m of text.matchAll(CODE_FENCE_RE)) {
      fences.push(m[1] ?? '')
    }
    if (fences.length === 0) return null
    return fences.join('\n\n')
  }
  const codePayload = msg.text ? extractCodeFences(msg.text) : null

  const handleCopyCode = async () => {
    if (!codePayload) return
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(codePayload)
      } else {
        // 退化：document.execCommand 是 jsdom / 老浏览器唯一 fallback
        const ta = document.createElement('textarea')
        ta.value = codePayload
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        const ok = document.execCommand('copy')
        document.body.removeChild(ta)
        if (!ok) throw new Error('execCommand copy failed')
      }
      // 段数提示：与 MessageBubble 一致
      const fenceCount = (msg.text ?? '').split('```').length >> 1
      setCopyStatus({ kind: 'ok', msg: `已复制 ${fenceCount} 段代码` })
    } catch (e) {
      const detail = e instanceof Error ? e.message : 'unknown'
      console.error('[GroupMessageItem] copy code failed:', detail)
      setCopyStatus({ kind: 'err', msg: '复制失败' })
    } finally {
      setTimeout(() => setCopyStatus(null), 2500)
    }
  }

  /**
   * P0-4 Pin 切换：URL 对齐后端 sessions.py:91-99 ——
   *   POST   /api/messages/{message_id}/pin?session_id=...
   *   DELETE /api/messages/{message_id}/pin?session_id=...
   * session_id 在 query，不在 path（前端早期 drift 过，MessageBubble 已有 schema 钉死测试，
   * 群聊复用同 URL，保持单一来源）。
   */
  const togglePin = async () => {
    if (pinPending) return
    if (!sessionId) {
      // 没绑 session：允许视觉翻转（demo 模式），不发请求。
      setPinned((v) => !v)
      return
    }
    const willPin = !pinned
    const prev = pinned
    setPinned(willPin)
    setPinError(null)
    setPinPending(true)
    const url = `/api/messages/${msg.id}/pin?session_id=${encodeURIComponent(sessionId)}`
    try {
      const resp = await fetch(url, { method: willPin ? 'POST' : 'DELETE' })
      if (!resp.ok && resp.status !== 204) {
        throw new Error(`API ${resp.status}`)
      }
    } catch (e) {
      setPinned(prev)
      const txt = e instanceof Error ? e.message : 'Pin 操作失败'
      setPinError(txt)
      console.error('[GroupMessageItem] pin toggle failed:', txt)
    } finally {
      setPinPending(false)
    }
  }

  const handleReply = () => {
    onReply?.(msg)
  }

  return (
    <div
      className="group/msg -mx-2 flex gap-3 rounded-lg px-2 py-1.5 transition-all duration-150 hover:bg-muted/40 hover:shadow-sm hover:ring-1 hover:ring-border/60 animate-[var(--animate-fade-in)]"
    >
      <div className="pt-0.5">
        <Avatar initial={actor.initial} color={actor.color} size={32} />
      </div>
      <div className="min-w-0 flex-1">
        {/* P1-1 群聊引文小气泡：与 MessageBubble 视觉一致。
            放在 author 行上方。test 期望 data-testid="group-reply-quote"。 */}
        {msg.replyTo && (
          <div
            data-testid="group-reply-quote"
            data-reply-to-id={msg.replyTo.id}
            className="mb-1 flex max-w-md items-start gap-1.5 rounded-md border-l-2 border-brand/60 bg-muted/40 px-2 py-1 text-[12px] text-muted-foreground"
            title={`回复 ${msg.replyTo.author} 的消息`}
          >
            <Reply className="mt-0.5 h-3 w-3 flex-shrink-0 text-brand" strokeWidth={2} />
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium text-foreground/80">
                {msg.replyTo.author}
              </div>
              <div className="line-clamp-2 break-words">
                {truncateSnippet(msg.replyTo.snippet)}
              </div>
            </div>
          </div>
        )}
        <div className="mb-1 flex items-center gap-2">
          <span className="text-[13px] font-semibold">{actor.name}</span>
          {!isUser && isCoordinator && <Badge variant="brand">协调者</Badge>}
          {msg.requiresApproval && (
            <Badge variant="warning" className="gap-1">
              <Icon name="shieldCheck" className="h-2.5 w-2.5" />
              待批准
            </Badge>
          )}
          <span className="font-mono text-[11px] text-muted-foreground">{msg.time}</span>
          {/* P0-4 群聊 Pin 按钮：与 MessageBubble 同视觉/同 URL。
              hover 才出现（在 group/msg 父层 hover:bg-muted/40 触发）。 */}
          <button
            type="button"
            data-testid="group-pin-btn"
            data-pinned={pinned ? 'true' : 'false'}
            aria-pressed={pinned}
            aria-label={pinned ? '取消置顶' : '置顶消息'}
            title={pinned ? '取消置顶' : '置顶消息'}
            disabled={pinPending}
            onClick={togglePin}
            className={
              'inline-flex h-5 w-5 items-center justify-center rounded transition-opacity ' +
              'opacity-0 group-hover/msg:opacity-100 focus-visible:opacity-100 ' +
              (pinned
                ? 'text-brand hover:bg-accent disabled:opacity-50'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50')
            }
          >
            <Pin
              className="h-3.5 w-3.5"
              fill={pinned ? 'currentColor' : 'none'}
              strokeWidth={1.75}
            />
          </button>
          {/* P1-1 群聊回复按钮：hover 消息时出现。test 期望 data-testid="group-reply-btn"。 */}
          <button
            type="button"
            data-testid="group-reply-btn"
            aria-label="回复消息"
            title="回复消息"
            disabled={!onReply}
            onClick={handleReply}
            className={
              'inline-flex h-5 w-5 items-center justify-center rounded text-muted-foreground transition-all ' +
              'opacity-0 group-hover/msg:opacity-100 focus-visible:opacity-100 ' +
              'hover:bg-accent hover:text-foreground disabled:opacity-0'
            }
          >
            <Reply className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
          {pinError && (
            <span
              data-testid="group-pin-error"
              role="alert"
              className="font-mono text-[10.5px] text-destructive"
              title={pinError}
            >
              Pin 失败
            </span>
          )}
        </div>
        {msg.text && (
          <div className="prose prose-sm max-w-none text-[14px] leading-[1.6] text-foreground [text-wrap:pretty]">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
              components={{
                p: ({ children }) => (
                  <p className="mb-2 last:mb-0">{highlightMentions(children)}</p>
                ),
                li: ({ children }) => <li>{highlightMentions(children)}</li>,
                pre: ({ children }) => (
                  <pre className="my-2 overflow-x-auto rounded-lg border border-slate-700/50 bg-slate-800 p-3 text-[12px] leading-[1.5] text-slate-100">
                    {children}
                  </pre>
                ),
                code: ({ className, children, ...props }) => {
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
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener"
                    className="text-brand underline"
                  >
                    {children}
                  </a>
                ),
              } satisfies Components}
            >
              {msg.text}
            </ReactMarkdown>
            {msg.streaming && (
              <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-foreground/60 align-text-bottom" />
            )}
          </div>
        )}
        {/* P0-5 群聊复制代码：仅在文本含代码围栏时显示。视觉与 MessageBubble 同步。 */}
        {codePayload && (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopyCode}
              data-testid="group-copy-code-btn"
            >
              <Copy className="mr-1.5 h-3.5 w-3.5" strokeWidth={1.75} />
              复制代码
            </Button>
            {copyStatus && (
              <span
                data-testid="group-copy-status"
                role="status"
                className={
                  copyStatus.kind === 'ok'
                    ? 'font-mono text-[10.5px] text-emerald-600'
                    : 'font-mono text-[10.5px] text-destructive'
                }
              >
                {copyStatus.msg}
              </span>
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
