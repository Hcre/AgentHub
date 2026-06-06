import { useState } from 'react'
import { Pin } from 'lucide-react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Avatar, Button, Icon } from '../ui'
import type { Agent, ChatMessage, UserInfo } from '../../types'
import { DiffView } from './DiffView'
import { WebPreviewCard } from './WebPreviewCard'
import { collectUrls } from './webPreviewUrl'
import { extractDiffFences } from './diffParse'

/**
 * 把 ReactMarkdown 的自定义 components 抽出来 —— 跟 DiffView 拆围栏后产生的
 * 「围栏前/围栏后」两段 markdown 共用同一套渲染规则（pre/code/a/table/blockquote）。
 * 抽出来后：
 *   1. 避免 2 段 markdown + 1 段 diff 拼接时重复写 60 行 components 对象
 *   2. 风格保持完全一致（包括表格、表头、引用块、code 块灰底）
 */
const MARKDOWN_COMPONENTS = {
  pre: ({ children }) => (
    <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border bg-muted/50 p-3 text-[13px] font-mono text-foreground/80">
      {children}
    </pre>
  ),
  code: ({ className, children, ...props }) => {
    const isInline = !className
    return isInline ? (
      <code className="text-[13px] font-mono text-foreground" {...props}>
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
    <a href={href} target="_blank" rel="noopener" className="text-brand underline">
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="min-w-full border-separate border-spacing-0 rounded-lg border text-[13px]">
        {children}
      </table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border-b bg-muted/50 px-3 py-1.5 text-left font-medium text-muted-foreground">
      {children}
    </th>
  ),
  td: ({ children }) => <td className="border-b px-3 py-1.5">{children}</td>,
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-brand/40 pl-3 italic text-muted-foreground">
      {children}
    </blockquote>
  ),
} satisfies Components

function MarkdownBody({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight]}
      components={MARKDOWN_COMPONENTS}
    >
      {text}
    </ReactMarkdown>
  )
}

export function MessageBubble({
  msg,
  agent,
  user,
  sessionId,
}: {
  msg: ChatMessage
  agent: Agent
  user: UserInfo
  /**
   * 当前会话的后端 Session id。Pin 操作调 POST/DELETE
   * /api/sessions/{sessionId}/messages/{msg.id}/pin 时需要。
   * 不传则按钮 disabled（避免在没绑会话的 mock 消息上乱发请求）。
   */
  sessionId?: string
}) {
  const isAgent = msg.from === 'agent'
  // 乐观更新本地 Pin 状态；初始值用 msg.pinned（后端真值），点击后立刻翻转，再
  // 调后端 200 则保持；非 2xx 回滚 + console.error 提示。
  const [pinned, setPinned] = useState<boolean>(msg.pinned ?? false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const togglePin = async () => {
    if (pending) return
    if (!sessionId) {
      // 没绑 session 的消息（典型：mock 假回复）— 允许视觉切换但不发请求，
      // 避免在没绑会话的 mock 消息上乱发 404
      setPinned((v) => !v)
      return
    }
    const willPin = !pinned
    const prev = pinned
    // 乐观更新：先翻状态，失败再回滚
    setPinned(willPin)
    setError(null)
    setPending(true)
    const url = `/api/sessions/${sessionId}/messages/${msg.id}/pin`
    try {
      const resp = await fetch(url, { method: willPin ? 'POST' : 'DELETE' })
      if (!resp.ok && resp.status !== 204) {
        throw new Error(`API ${resp.status}`)
      }
    } catch (e) {
      // 回滚 + 错误提示
      setPinned(prev)
      const msgText = e instanceof Error ? e.message : 'Pin 操作失败'
      setError(msgText)
      console.error('[MessageBubble] pin toggle failed:', msgText)
    } finally {
      setPending(false)
    }
  }
  // 优先用 Agent 显式声明的 urls 字段；退化路径从 text 抓 http(s)://
  const previewUrls = isAgent ? collectUrls(msg.text, msg.urls) : []

  // Agent 消息：识别 ```diff``` 围栏，把围栏内容交给 DiffView 渲染彩色 diff，
  // 围栏前/后的纯 markdown 段落走标准 ReactMarkdown。
  // - 非 Agent 消息：保持原行为（按段渲染纯文本），不解析 diff 围栏。
  // - 没有 diff 围栏：保持原行为（一整段 ReactMarkdown）。
  const fence = isAgent ? extractDiffFences(msg.text) : null
  const showDiffInline = isAgent && fence?.hasDiffFence

  return (
    <div className="animate-[var(--animate-fade-in)] flex gap-3">
      <div className="pt-0.5">
        {isAgent ? (
          <Avatar initial={agent.name[0] ?? '?'} color={agent.color} size={32} />
        ) : (
          <Avatar initial={user.initial} color="neutral" size={32} />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-[13px] font-semibold">{isAgent ? agent.name : user.handle}</span>
          <span className="font-mono text-[11px] text-muted-foreground">{msg.time}</span>
          {/* P0-4 Pin 按钮：放在时间戳旁。已 pinned → 填充态 + 主色（lucide fill 用 fill="currentColor"）；
              未 pinned → outline（stroke only）。optimistic update + 失败回滚。 */}
          <button
            type="button"
            data-testid="pin-btn"
            data-pinned={pinned ? 'true' : 'false'}
            aria-pressed={pinned}
            aria-label={pinned ? '取消置顶' : '置顶消息'}
            title={pinned ? '取消置顶' : '置顶消息'}
            disabled={pending}
            onClick={togglePin}
            className={
              pinned
                ? 'inline-flex h-5 w-5 items-center justify-center rounded text-brand transition-colors hover:bg-accent disabled:opacity-50'
                : 'inline-flex h-5 w-5 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-50'
            }
          >
            <Pin
              className="h-3.5 w-3.5"
              fill={pinned ? 'currentColor' : 'none'}
              strokeWidth={1.75}
            />
          </button>
          {error && (
            <span
              data-testid="pin-error"
              role="alert"
              className="font-mono text-[10.5px] text-destructive"
              title={error}
            >
              Pin 失败
            </span>
          )}
        </div>
        <div className="prose min-w-0 max-w-full break-words text-[14px] leading-[1.6] text-foreground">
          {showDiffInline && fence ? (
            <>
              {fence.before.trim() && <MarkdownBody text={fence.before} />}
              <DiffView unifiedDiff={fence.diffBody} />
              {fence.after.trim() && <MarkdownBody text={fence.after} />}
            </>
          ) : isAgent ? (
            <MarkdownBody text={msg.text} />
          ) : (
            msg.text.split('\n\n').map((p, i) => (
              <p key={i} className={i > 0 ? 'mt-2' : undefined}>
                {p}
              </p>
            ))
          )}
        </div>
        {previewUrls.map((u) => (
          <WebPreviewCard key={u} url={u} />
        ))}
        {msg.attachment && (
          <a
            href={msg.attachment.url ?? '#'}
            download={msg.attachment.url ? undefined : undefined}
            target="_blank"
            rel="noopener"
            className="mt-2 inline-flex items-center gap-2.5 rounded-md border bg-muted/40 px-3 py-2 transition-colors hover:bg-muted/60"
          >
            <div className="grid h-7 w-7 place-items-center rounded border bg-background text-muted-foreground">
              <Icon name="doc" className="h-3.5 w-3.5" />
            </div>
            <div className="text-left">
              <div className="font-mono text-[12px] underline-offset-2 group-hover:underline">
                {msg.attachment.name}
              </div>
              <div className="font-mono text-[10.5px] text-muted-foreground">
                {msg.attachment.size}
              </div>
            </div>
          </a>
        )}
        {msg.actions && (
          <div className="mt-2 flex gap-2">
            {msg.actions.map((a) => (
              <Button key={a} variant="outline" size="sm">
                {a}
              </Button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
