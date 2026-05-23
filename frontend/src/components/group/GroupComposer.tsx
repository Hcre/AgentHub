import { useState } from 'react'
import { cn } from '../../lib/cn'
import { agents } from '../../data/mock'
import { coordinator } from '../../data/groups'
import { Button, Icon } from '../ui'
import type { SendGroupOptions } from '../../stores/groupStore'
import type { Group } from '../../types'

interface Mentionable {
  id: string
  name: string
  hint: string
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

  const mentionables: Mentionable[] = [
    { id: coordinator.id, name: coordinator.name, hint: '拆分并分发任务' },
    ...group.members.map((id) => {
      const a = agents.find((x) => x.id === id)
      return { id, name: a?.name ?? id, hint: a?.role ?? '' }
    }),
  ]

  const send = () => {
    const text = val.trim()
    if (!text) return
    onSend(text, { requiresApproval })
    setVal('')
    setShowMentions(false)
    setRequiresApproval(false)
  }

  const insertMention = (name: string) => {
    setVal((v) => `${v}${v && !v.endsWith(' ') ? ' ' : ''}@${name} `)
    setShowMentions(false)
  }

  return (
    <div className="relative mx-4 mb-4 rounded-xl border bg-background shadow-sm transition-all focus-within:ring-2 focus-within:ring-ring">
      {showMentions && (
        <div className="absolute bottom-full left-3 mb-2 w-64 rounded-lg border bg-popover p-1 shadow-lg">
          {mentionables.map((m) => (
            <button
              key={m.id}
              onClick={() => insertMention(m.name)}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[12.5px] hover:bg-accent"
            >
              <span className="font-medium text-brand">@{m.name}</span>
              <span className="truncate text-[11px] text-muted-foreground">{m.hint}</span>
            </button>
          ))}
        </div>
      )}
      <textarea
        rows={1}
        placeholder={`在 #${group.name} 里说点什么，或 @协调者 派活…`}
        value={val}
        onChange={(e) => setVal(e.target.value)}
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
          <span className="font-mono text-[11px] text-muted-foreground">↵ 发送</span>
          <Button variant="brand" size="iconSm" className="h-7 w-7" onClick={send}>
            <Icon name="send" className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}
