import { Avatar } from '../ui'
import type { Agent } from '../../types'

export function TypingIndicator({ agent }: { agent: Agent }) {
  return (
    <div className="animate-[var(--animate-fade-in)] flex gap-3">
      <Avatar initial={agent.name[0] ?? '?'} color={agent.color} size={32} />
      <div className="flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-[13px] font-semibold">{agent.name}</span>
          <span className="font-mono text-[11px] text-muted-foreground">正在输入…</span>
        </div>
        <div className="inline-flex items-center gap-1 rounded-full border bg-muted/40 px-3 py-1.5">
          <span className="typing-dot h-1 w-1 rounded-full bg-brand" />
          <span className="typing-dot h-1 w-1 rounded-full bg-brand" />
          <span className="typing-dot h-1 w-1 rounded-full bg-brand" />
        </div>
      </div>
    </div>
  )
}
