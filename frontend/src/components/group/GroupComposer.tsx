import { useCallback, useMemo, useRef, useState } from 'react'
import { cn } from '../../lib/cn'
import { useAgentStore } from '../../stores/agentStore'
import { Button, Icon } from '../ui'
import type { SendGroupOptions } from '../../stores/groupStore'
import type { Group } from '../../types'

interface Mentionable {
  id: string
  name: string
  hint: string
}

const MENTION_RE = /@\S*$/

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
}: {
  group: Group
  onSend: (text: string, opts: SendGroupOptions) => void
}) {
  const [val, setVal] = useState('')
  const [showMentions, setShowMentions] = useState(false)
  const [requiresApproval, setRequiresApproval] = useState(false)
  const agents = useAgentStore((s) => s.agents)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

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
    onSend(text, { requiresApproval })
    setVal('')
    setShowMentions(false)
    setMentionInfo(null)
    setRequiresApproval(false)
  }

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

      <textarea
        ref={textareaRef}
        rows={1}
        placeholder={`在 #${group.name} 里说点什么，或 @协调者 派活…`}
        value={val}
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            send()
          }
        }}
        className="w-full resize-none rounded-t-xl border-0 bg-transparent px-3 py-3 text-[14px] outline-none placeholder:text-muted-foreground"
        style={{ maxHeight: 200 }}
      />

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
          <span className="font-mono text-[11px] text-muted-foreground">Enter 发送</span>
          <Button variant="brand" size="iconSm" className="h-7 w-7" onClick={send}>
            <Icon name="send" className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}
