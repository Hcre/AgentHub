import { useState, useCallback } from 'react'
import { ChevronDown, ChevronUp, Copy, Loader2, CheckCircle, XCircle, Wrench } from 'lucide-react'
import type { ToolCallEntry } from '../../types'

/** ToolCallBlock：工具调用展示。默认折叠。pending 时显示 spinner，
 *  success/error 时按 tool_result 更新状态指示器。 */
export function ToolCallBlock({ calls }: { calls: ToolCallEntry[] }) {
  return (
    <div className="mt-1.5 rounded-lg border border-zinc-300/60 dark:border-zinc-700/60 bg-zinc-100/60 dark:bg-zinc-900/40 overflow-hidden">
      {calls.map((call, i) => (
        <ToolCallItem key={call.id} call={call} isLast={i === calls.length - 1} />
      ))}
    </div>
  )
}

function ToolCallItem({ call, isLast }: { call: ToolCallEntry; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    const text = JSON.stringify(call.args, null, 2)
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        const ta = document.createElement('textarea')
        ta.value = text
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
      }
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // 静默失败
    }
  }, [call.args])

  const toggle = () => setExpanded((v) => !v)

  const argsPreview = JSON.stringify(call.args).slice(0, 60)

  const StatusIcon =
    call.status === 'pending' ? (
      <Loader2 className="h-3 w-3 text-zinc-400 animate-spin" strokeWidth={2} />
    ) : call.status === 'success' ? (
      <CheckCircle className="h-3 w-3 text-emerald-500" strokeWidth={1.75} />
    ) : (
      <XCircle className="h-3 w-3 text-red-500" strokeWidth={1.75} />
    )

  return (
    <div className={!isLast ? 'border-b border-zinc-200/40 dark:border-zinc-700/40' : ''}>
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-center gap-2 px-3 py-2 select-none hover:bg-zinc-200/40 dark:hover:bg-zinc-800/40 transition-colors"
        aria-expanded={expanded}
        aria-label={`工具调用: ${call.name}`}
      >
        <Wrench className="h-3.5 w-3.5 text-zinc-500 dark:text-zinc-400 flex-shrink-0" strokeWidth={1.75} />
        <span className="font-mono text-[12px] font-semibold text-zinc-700 dark:text-zinc-300">
          {call.name}
        </span>
        {StatusIcon}
        <span className="font-mono text-[11px] text-zinc-500 dark:text-zinc-400 truncate max-w-[300px] ml-auto">
          {argsPreview}{argsPreview.length >= 60 ? '…' : ''}
        </span>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 text-zinc-400 flex-shrink-0" strokeWidth={1.75} />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-zinc-400 flex-shrink-0" strokeWidth={1.75} />
        )}
      </button>
      <div
        className={`transition-all duration-150 overflow-hidden ${
          expanded ? 'max-h-64 overflow-y-auto' : 'max-h-0'
        }`}
      >
        <div className="px-3 pb-2 pt-0 border-t border-zinc-200/60 dark:border-zinc-700/60 relative group/tc">
          <div className="text-[10px] uppercase tracking-wider text-zinc-400 dark:text-zinc-500 font-medium mb-1 mt-2">
            参数
          </div>
          <pre className="font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-all text-zinc-600 dark:text-zinc-400 bg-zinc-200/40 dark:bg-zinc-800/60 rounded px-2 py-1.5">
            {JSON.stringify(call.args, null, 2)}
          </pre>
          <button
            type="button"
            onClick={handleCopy}
            className="absolute top-2 right-2 opacity-0 group-hover/tc:opacity-100 transition-opacity"
            aria-label="复制参数"
            title="复制参数"
          >
            <Copy className="h-3 w-3 text-muted-foreground hover:text-foreground" strokeWidth={1.75} />
          </button>
          {copied && (
            <span className="absolute top-2 right-8 text-[10px] text-emerald-600">已复制</span>
          )}
        </div>
      </div>
    </div>
  )
}
