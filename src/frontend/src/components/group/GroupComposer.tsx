import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Reply, Square, X } from 'lucide-react'
import { cn } from '../../lib/cn'
import { useAgentStore } from '../../stores/agentStore'
import { useGroupStore } from '../../stores/groupStore'
import { Button, Icon } from '../ui'
import type { SendGroupOptions } from '../../stores/groupStore'
import type { Group, ReplyRef } from '../../types'

interface Mentionable {
  id: string
  name: string
  hint: string
}

const MENTION_RE = /@\S*$/
// 渲染时匹配：完整 mention（与气泡渲染保持一致），遇标点/空格停
const MENTION_RENDER_RE = /(@[\p{L}\p{N}_]+)/gu

/** 把文本里的 @mention 渲染成带底色的 span（叠在 textarea 之下）。 */
function renderHighlighted(text: string) {
  if (!text) return null
  const parts = text.split(MENTION_RENDER_RE)
  return parts.map((part, i) =>
    part.startsWith('@') ? (
      <span
        key={i}
        className="rounded bg-brand/10 px-1 font-medium text-brand"
      >
        {part}
      </span>
    ) : (
      <Fragment key={i}>{part}</Fragment>
    ),
  )
}

/**
 * 从 textarea 的文本 + selectionStart 检测当前是否在输入一个 @mention。
 * 返回 @ 的起始位置和已输入字符，null 表示不在 @mention 区域内。
 */
function detectMentionAtCursor(
  text: string,
  cursorPos: number,
): { atIdx: number; query: string } | null {
  const before = text.slice(0, cursorPos)
  const match = before.match(MENTION_RE)
  if (!match || match.index === undefined) return null
  return { atIdx: match.index, query: match[0].slice(1) }
}

export function GroupComposer({
  group,
  onSend,
  /**
   * P1-1 reply/quote：父组件持有此 ref，调用 groupComposerRef.current.setReplyTo(ref)
   * 即可让 GroupComposer 进入 reply 模式。setReplyTo(null) 清空。
   */
  groupComposerRef,
}: {
  group: Group
  onSend: (text: string, opts: SendGroupOptions) => void
  groupComposerRef?: React.MutableRefObject<{
    setReplyTo: (ref: ReplyRef | null) => void
  } | null>
}) {
  const [val, setVal] = useState('')
  const [showMentions, setShowMentions] = useState(false)
  const [requiresApproval, setRequiresApproval] = useState(false)
  // P1-1 reply mode：当前正在回复的消息引用；null = 普通模式
  const [replyTo, setReplyTo] = useState<ReplyRef | null>(null)
  const agents = useAgentStore((s) => s.agents)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // 检测是否有 agent 正在回复（消息带 streaming:true）
  const isStreaming = useGroupStore((s) => {
    const msgs = s.messagesByGroup[group.id] ?? []
    return msgs.some((m) => m.streaming === true)
  })
  // 停止：textarea 为空 + 有 streaming → 显示停止按钮
  const showStop = isStreaming && !val.trim()

  // 当前 @mention 片段信息
  const [mentionInfo, setMentionInfo] = useState<{
    atIdx: number
    query: string
  } | null>(null)

  const mentionables: Mentionable[] = useMemo(() => {
    const list: Mentionable[] = []
    if (group.coordinatorId) {
      list.push({
        id: group.coordinatorId,
        name: group.coordinatorName ?? '协调者',
        hint: group.coordinatorRole || '拆分并分发任务',
      })
    }
    for (const id of group.members) {
      const a = agents.find((x) => x.id === id)
      list.push({ id, name: a?.name ?? id, hint: a?.role ?? '' })
    }
    return list
  }, [agents, group.coordinatorId, group.coordinatorName, group.coordinatorRole, group.members])

  const filtered = useMemo(() => {
    if (!mentionInfo) return mentionables
    const q = mentionInfo.query.toLowerCase()
    if (!q) return mentionables
    return mentionables.filter((m) => m.name.toLowerCase().includes(q))
  }, [mentionables, mentionInfo])

  const handleChange = useCallback(
    (text: string) => {
      setVal(text)
      // 读光标位置判定是否在 @mention 内
      requestAnimationFrame(() => {
        const ta = textareaRef.current
        if (!ta) return
        const pos = ta.selectionStart ?? text.length
        const info = detectMentionAtCursor(text, pos)
        setMentionInfo(info)
        setShowMentions(!!info)
      })
    },
    [],
  )

  const send = () => {
    const text = val.trim()
    if (!text) return
    onSend(text, { requiresApproval, replyTo: replyTo ?? undefined })
    setVal('')
    setShowMentions(false)
    setMentionInfo(null)
    setRequiresApproval(false)
    setReplyTo(null)
  }

  const handleStop = () => {
    const ws = useGroupStore.getState().ws
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'cancel' }))
    }
  }

  const cancelReply = () => setReplyTo(null)

  // 把 setReplyTo 暴露给父组件（GroupChatView → GroupMessageItem.onReply 路径）
  // useCallback 保证 ref 调用的 setReplyTo 始终是最新闭包
  const setReplyToStable = useCallback((ref: ReplyRef | null) => {
    setReplyTo(ref)
    if (ref) {
      // 进入 reply mode → focus + 滚动到 textarea
      requestAnimationFrame(() => {
        const ta = textareaRef.current
        if (ta) ta.focus()
      })
    }
  }, [])

  // 把 setReplyTo 透出到外部 ref（用 useEffect 而不是 render 期赋值，避免 react-hooks/refs 红线）
  useEffect(() => {
    if (groupComposerRef) {
      groupComposerRef.current = { setReplyTo: setReplyToStable }
    }
  })

  const insertMention = (name: string) => {
    if (!mentionInfo) return
    const { atIdx } = mentionInfo
    const endIdx = textareaRef.current?.selectionStart ?? val.length
    // 替换 @fragment → @Name
    const before = val.slice(0, atIdx)
    const after = val.slice(endIdx)
    const next = `${before}@${name} ${after}`
    setVal(next)
    setShowMentions(false)
    setMentionInfo(null)
    // 光标定位到 @Name 后
    const cursorTarget = atIdx + name.length + 2 // '@' + name + ' '
    requestAnimationFrame(() => {
      const ta = textareaRef.current
      if (ta) {
        ta.focus()
        ta.setSelectionRange(cursorTarget, cursorTarget)
      }
    })
  }

  return (
    <div className="relative mx-4 mb-4 rounded-xl border bg-background shadow-sm transition-all focus-within:ring-2 focus-within:ring-ring">
      {/* P1-1 群聊 reply 引文条：与 Composer 视觉一致。test 期望 data-testid="group-reply-badge"。 */}
      {replyTo && (
        <div
          data-testid="group-reply-badge"
          data-reply-to-id={replyTo.id}
          className="mx-2 mt-2 flex items-start gap-1.5 rounded-md border-l-2 border-brand/60 bg-muted/40 px-2 py-1 text-[12px] text-muted-foreground"
        >
          <Reply className="mt-0.5 h-3 w-3 flex-shrink-0 text-brand" strokeWidth={2} />
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium text-foreground/80">
              回复 {replyTo.author}
            </div>
            <div className="line-clamp-2 break-words">{replyTo.snippet}</div>
          </div>
          <button
            type="button"
            data-testid="group-reply-cancel"
            aria-label="取消回复"
            title="取消回复"
            onClick={cancelReply}
            className="grid h-5 w-5 flex-shrink-0 place-items-center rounded text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      )}
      {/* @mention 弹出菜单 */}
      {showMentions && filtered.length > 0 && (
        <div className="absolute bottom-full left-3 mb-2 w-64 rounded-lg border bg-popover p-1 shadow-lg z-10">
          {filtered.map((m) => (
            <button
              key={m.id}
              onMouseDown={(e) => {
                e.preventDefault()
                insertMention(m.name)
              }}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[12.5px] hover:bg-accent"
            >
              <span className="font-medium text-brand">@{m.name}</span>
              <span className="truncate text-[11px] text-muted-foreground">{m.hint}</span>
            </button>
          ))}
        </div>
      )}

      {/* textarea + 高亮 overlay：textarea 透明，overlay 同位置呈现带色 @mention */}
      <div className="relative">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words rounded-t-xl px-3 py-3 text-[14px] leading-[1.5] text-foreground"
        >
          {renderHighlighted(val)}
          {/* 末尾零宽空格：让 overlay 在 val 末尾换行时不塌陷 */}
          <span>{'​'}</span>
        </div>
        <textarea
          ref={textareaRef}
          rows={1}
          placeholder={replyTo
            ? `回复 ${replyTo.author}…`
            : `在 #${group.name} 里说点什么，或 @协调者 派活…`}
          value={val}
          onChange={(e) => handleChange(e.target.value)}
          onScroll={(e) => {
            // 同步 overlay 滚动位置（textarea 超过 maxHeight 会自身滚动）
            const ov = (e.currentTarget.previousElementSibling as HTMLElement | null)
            if (ov) ov.scrollTop = e.currentTarget.scrollTop
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send()
            }
          }}
          className="relative w-full resize-none rounded-t-xl border-0 bg-transparent px-3 py-3 text-[14px] leading-[1.5] outline-none placeholder:text-muted-foreground"
          style={{
            maxHeight: 200,
            color: 'transparent',
            caretColor: '#0f172a',
          }}
        />
      </div>

      <div className="flex items-center justify-between px-2 py-2">
        <div className="flex items-center gap-0.5">
          <Button variant="ghost" size="iconSm" className="h-7 w-7 text-muted-foreground">
            <Icon name="paperclip" className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="iconSm"
            onClick={() => setShowMentions((v) => !v)}
            className={cn(
              'h-7 w-7 text-muted-foreground',
              showMentions && 'bg-accent text-foreground',
            )}
          >
            <Icon name="atSign" className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="iconSm" className="h-7 w-7 text-muted-foreground">
            <Icon name="smile" className="h-3.5 w-3.5" />
          </Button>
          <div className="mx-1 h-4 w-px self-center bg-border" />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setRequiresApproval((v) => !v)}
            title={requiresApproval ? '下一条消息将需要批准' : '标记为需批准才可执行'}
            className={cn(
              'h-7 gap-1.5 px-2 text-[11px] font-medium',
              requiresApproval
                ? 'bg-brand-soft text-brand-deep hover:bg-brand-soft/80'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Icon name="shieldCheck" className="h-3.5 w-3.5" />
            {requiresApproval ? '需批准' : '权限认可'}
          </Button>
        </div>
        <div className="flex items-center gap-2">
          {showStop ? (
            <Button
              variant="destructive"
              size="sm"
              onClick={handleStop}
              title="停止生成"
              className="h-7 gap-1.5 px-2 text-[12px]"
            >
              <Square className="h-3 w-3" fill="currentColor" />
              停止
            </Button>
          ) : (
            <>
              <span className="font-mono text-[11px] text-muted-foreground">Enter 发送</span>
              <Button variant="brand" size="iconSm" className="h-7 w-7" onClick={send}>
                <Icon name="send" className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
