import { useMemo, useState } from 'react'
import { Copy, Pin, RefreshCw, Reply, Trash2 } from 'lucide-react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Avatar, Button, Icon } from '../ui'
import type { Agent, ChatMessage, UserInfo } from '../../types'
import { ThinkingBlock } from './ThinkingBlock'
import { ToolCallsGroup } from './ToolCallsGroup'
import { ApprovalRequestBlock } from './ApprovalRequestBlock'
import { TaskPlanBlock } from './TaskPlanBlock'
import { DiffView } from './DiffView'
import { WebPreviewCard } from './WebPreviewCard'
import { collectUrls } from './webPreviewUrl'
import { extractDiffFences } from './diffParse'
import { DeployCardView } from '../deploy/DeployCard'
import { detectSkillMd, SkillMdPreview } from '../skills/SkillMdPreview'

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

/**
 * P1-1：把引文 snippet 截到 60 字符（含省略号）。
 * test: 「a」 重复 200 次 → DOM 里 ≤ 70 个 a（防漂移）。
 */
function truncateSnippet(s: string, max = 60): string {
  if (s.length <= max) return s
  return s.slice(0, max) + '…'
}

export function MessageBubble({
  msg,
  agent,
  user,
  sessionId,
  /**
   * P1-1 reply/quote：hover message 出回复按钮 → 点击触发此回调，
   * 父组件 ChatView 把对应消息的 ReplyRef 塞进 Composer.setReplyTo。
   * 不传则按钮 disabled（避免 mock 场景乱发）。
   */
  onReply,
  /**
   * 删除消息：hover 出删除按钮 → 确认后触发此回调，父组件 ChatView 调
   * sessionsApi.deleteMessage + chatStore.removeMessage。不传则按钮不渲染
   * （避免在没绑后端的 mock 消息上发 404）。
   */
  onDelete,
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
  onReply?: (msg: ChatMessage) => void
  onDelete?: (msg: ChatMessage) => void
}) {
  const isAgent = msg.from === 'agent'
  // 乐观更新本地 Pin 状态；初始值用 msg.pinned（后端真值），点击后立刻翻转，再
  // 调后端 200 则保持；非 2xx 回滚 + console.error 提示。
  const [pinned, setPinned] = useState<boolean>(msg.pinned ?? false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // P0-5: 复制代码 / 重新生成 状态。copyStatus = null = idle, { kind: 'ok' | 'err', msg: string } = 显示中。
  // 不引第三方 toast 库，直接在 actions 行旁 inline 显示（与 pin 错误同 pattern），简单可靠。
  const [copyStatus, setCopyStatus] = useState<{ kind: 'ok' | 'err'; msg: string } | null>(null)

  /**
   * P0-5 复制代码按钮处理器：
   *   - 用正则 /```[a-z]*\n([\s\S]*?)\n```/g 抓所有围栏内容
   *   - 拼接后调 navigator.clipboard.writeText
   *   - 成功：「已复制 N 段代码」（N=0 时仍显示「已复制 0 段代码」让用户知道按了有反应）
   *   - 失败：「复制失败」（clipboard API 不可用 / 浏览器拒绝权限）
   *   - 2.5s 后自动清空（避免占位）
   */
  const handleCopyCode = async () => {
    const fences: string[] = []
    const re = /```[a-z]*\n([\s\S]*?)\n```/g
    let m: RegExpExecArray | null
    while ((m = re.exec(msg.text)) !== null) {
      fences.push(m[1] ?? '')
    }
    const payload = fences.join('\n\n')
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(payload)
      } else {
        // 退化：document.execCommand 已弃用但仍是 jsdom 唯一 fallback
        const ta = document.createElement('textarea')
        ta.value = payload
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        const ok = document.execCommand('copy')
        document.body.removeChild(ta)
        if (!ok) throw new Error('execCommand copy failed')
      }
      setCopyStatus({ kind: 'ok', msg: `已复制 ${fences.length} 段代码` })
    } catch (e) {
      const detail = e instanceof Error ? e.message : 'unknown'
      console.error('[MessageBubble] copy code failed:', detail)
      setCopyStatus({ kind: 'err', msg: '复制失败' })
    } finally {
      // 2.5s 后清空 inline 状态
      setTimeout(() => setCopyStatus(null), 2500)
    }
  }

  /**
   * P0-5 重新生成按钮：当前后端无 regenerate 端点（grep sessions.py 无命中），
   * 所以按钮 disabled + tooltip「即将支持」。后续后端落地后去掉 disabled
   * 并接 fetch('/api/messages/{id}/regenerate?session_id=...')。
   */
  const handleRegenerate = () => {
    // noop for now — 后端实现后再加 fetch
  }

  const handleReply = () => {
    onReply?.(msg)
  }

  const handleDelete = () => {
    if (!onDelete) return
    if (window.confirm('确定删除这条消息？该操作不可恢复。')) {
      onDelete(msg)
    }
  }

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
    // 对齐后端实际路由：src/backend/app/api/routers/sessions.py:91-99
    //   @router.post("/messages/{message_id}/pin", ...)
    //   @router.delete("/messages/{message_id}/pin", ...)
    // session_id 是 query 参数（不是 path）。前端 URL 必须跟后端一致，否则 404。
    const url = `/api/messages/${msg.id}/pin?session_id=${encodeURIComponent(sessionId)}`
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

  // SKILL.md 检测：使用 useMemo 避免每次 render 重新解析（只在 msg.text 变化时触发）
  const skillMdDetection = useMemo(() => {
    if (!isAgent) return { found: false as const }
    return detectSkillMd(msg.text)
  }, [msg.text, isAgent])

  return (
    <div className="group/msg animate-[var(--animate-fade-in)] flex gap-3">
      <div className="pt-0.5">
        {isAgent ? (
          <Avatar initial={agent.name[0] ?? '?'} color={agent.color} size={32} />
        ) : (
          <Avatar initial={user.initial} color="neutral" size={32} />
        )}
      </div>
      <div className="min-w-0 flex-1">
        {/* P1-1 引文小气泡（顶角）：msg.replyTo 存在时渲染，紧贴 author 行下方。
            pointer-events-none：纯展示，不参与交互（不阻断下方的回复按钮）。 */}
        {msg.replyTo && (
          <div
            data-testid="reply-quote"
            data-reply-to-id={msg.replyTo.id}
            className="mb-1.5 flex max-w-md items-start gap-1.5 rounded-md border-l-2 border-brand/60 bg-muted/40 px-2 py-1 text-[12px] text-muted-foreground"
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
          {/* P1-1 回复按钮：hover message 才出现（CSS 控制可见性，但 always in DOM，
              以便测试与「键盘聚焦时也可见」）。onReply 未传时 disabled。 */}
          <button
            type="button"
            data-testid="reply-btn"
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
          {/* 删除按钮：hover message 才出现；onDelete 未传（mock 消息）则不渲染 */}
          {onDelete && (
            <button
              type="button"
              data-testid="delete-btn"
              aria-label="删除消息"
              title="删除消息"
              onClick={handleDelete}
              className={
                'inline-flex h-5 w-5 items-center justify-center rounded text-muted-foreground transition-all ' +
                'opacity-0 group-hover/msg:opacity-100 focus-visible:opacity-100 ' +
                'hover:bg-destructive/10 hover:text-destructive'
              }
            >
              <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
            </button>
          )}
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
        {/* ── CLI 流式块：思考过程（主文本之上）── */}
        {msg.thinking && <ThinkingBlock text={msg.thinking} streaming={msg.streaming} />}

        {/* ── CLI 流式块：任务计划（主文本之上，思考之下）── */}
        {msg.taskPlan && <TaskPlanBlock plan={msg.taskPlan} />}

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

        {/* ── CLI 流式块：工具调用 + 工具结果（默认折叠，主文本之下）── */}
        {(msg.toolCalls?.length || msg.toolResults?.length) && (
          <ToolCallsGroup toolCalls={msg.toolCalls} toolResults={msg.toolResults} />
        )}

        {/* ── CLI 流式块：审批请求（阻断性 CTA，置于底部醒目位置）── */}
        {msg.approvalRequest && (
          <ApprovalRequestBlock data={msg.approvalRequest} />
        )}

        {previewUrls.map((u) => (
          <WebPreviewCard key={u} url={u} />
        ))}
        {msg.deploy && <DeployCardView card={msg.deploy} />}
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
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {msg.actions.map((a) => {
              // P0-5: 「复制代码」绑 handleCopyCode + 左侧 Copy 图标
              if (a === '复制代码') {
                return (
                  <Button
                    key={a}
                    variant="outline"
                    size="sm"
                    onClick={handleCopyCode}
                    data-testid="copy-code-btn"
                  >
                    <Copy className="mr-1.5 h-3.5 w-3.5" strokeWidth={1.75} />
                    {a}
                  </Button>
                )
              }
              // P0-5: 「重新生成」— 后端无端点，disabled + tooltip「即将支持」
              if (a === '重新生成') {
                return (
                  <Button
                    key={a}
                    variant="outline"
                    size="sm"
                    onClick={handleRegenerate}
                    disabled
                    title="即将支持"
                    data-testid="regenerate-btn"
                    aria-label="重新生成（即将支持）"
                  >
                    <RefreshCw className="mr-1.5 h-3.5 w-3.5" strokeWidth={1.75} />
                    {a}
                  </Button>
                )
              }
              // 其他 action label 保持原行为（纯展示按钮）
              return (
                <Button key={a} variant="outline" size="sm">
                  {a}
                </Button>
              )
            })}
            {copyStatus && (
              <span
                data-testid="copy-status"
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

        {/* SKILL.md 检测：Agent 消息中包含 YAML frontmatter 围栏草稿时，在气泡下方渲染预览面板 */}
        {skillMdDetection.found && (
          <SkillMdPreview
            data={skillMdDetection.data}
            onSaveSuccess={() => {
              // 保存成功后触发自定义事件，让 SkillMarketplacePage 知道需要刷新列表
              window.dispatchEvent(new CustomEvent('skill-library-updated'))
            }}
          />
        )}
      </div>
    </div>
  )
}
