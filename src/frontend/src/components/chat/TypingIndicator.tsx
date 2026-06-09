import { useEffect, useState } from 'react'
import { Avatar } from '../ui'
import type { Agent } from '../../types'

/** 随时间变化的提示文案 */
const STAGES: [number, string][] = [
  [0, '正在处理…'],
  [15, '工具执行中，请稍候…'],
  [60, '仍在等待 API 响应…'],
  [120, '复杂任务处理中，已等待 2 分钟…'],
]

export function TypingIndicator({ agent }: { agent: Agent }) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setElapsed((n) => n + 1), 1000)
    return () => clearInterval(timer)
  }, [])

  const msg = [...STAGES].reverse().find(([t]) => elapsed >= t)?.[1] ?? STAGES[0][1]

  return (
    <div className="animate-[var(--animate-fade-in)] flex gap-3">
      <Avatar initial={agent.name[0] ?? '?'} color={agent.color} size={32} />
      <div className="flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-[13px] font-semibold">{agent.name}</span>
          <span className="font-mono text-[11px] text-muted-foreground">{msg}</span>
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
