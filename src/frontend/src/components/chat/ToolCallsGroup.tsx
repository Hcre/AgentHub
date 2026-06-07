import { useState, useMemo } from 'react'
import { ChevronDown, ChevronUp, Wrench, Loader2 } from 'lucide-react'
import type { ToolCallEntry, ToolResultEntry } from '../../types'
import { ToolCallBlock } from './ToolCallBlock'
import { ToolResultBlock } from './ToolResultBlock'

interface Props {
  toolCalls?: ToolCallEntry[]
  toolResults?: ToolResultEntry[]
}

export function ToolCallsGroup({ toolCalls, toolResults }: Props) {
  const hasPending = useMemo(
    () => toolCalls?.some((c) => c.status === 'pending') ?? false,
    [toolCalls],
  )
  const [expanded, setExpanded] = useState(hasPending)

  const callCount = (toolCalls?.length ?? 0) + (toolResults?.length ?? 0)
  if (callCount === 0) return null

  const pendingCount = toolCalls?.filter((c) => c.status === 'pending').length ?? 0
  const errorCount = toolCalls?.filter((c) => c.status === 'error').length ?? 0
  const successCount = callCount - pendingCount - errorCount

  return (
    <div className="mt-2 rounded-lg border border-zinc-300/60 dark:border-zinc-700/60 overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left select-none hover:bg-zinc-100/60 dark:hover:bg-zinc-900/40 transition-colors"
      >
        <Wrench className="h-3.5 w-3.5 text-zinc-400 flex-shrink-0" strokeWidth={1.75} />
        <span className="text-[12px] font-medium text-zinc-600 dark:text-zinc-400">
          工具调用 ({callCount})
        </span>
        {hasPending && (
          <>
            <Loader2 className="h-3 w-3 text-zinc-400 animate-spin" strokeWidth={2} />
            <span className="text-[11px] text-zinc-400">{pendingCount} 个执行中</span>
          </>
        )}
        {!hasPending && (
          <span className="text-[11px] text-zinc-400">
            {successCount > 0 && `${successCount} 完成`}
            {errorCount > 0 && ` ${errorCount} 失败`}
          </span>
        )}
        <span className="ml-auto">
          {expanded ? (
            <ChevronUp className="h-3.5 w-3.5 text-zinc-400" strokeWidth={1.75} />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 text-zinc-400" strokeWidth={1.75} />
          )}
        </span>
      </button>
      <div
        className={`transition-all duration-150 overflow-hidden ${
          expanded ? 'max-h-[600px] overflow-y-auto' : 'max-h-0'
        }`}
      >
        {toolCalls && toolCalls.length > 0 && (
          <ToolCallBlock calls={toolCalls} />
        )}
        {toolResults && toolResults.length > 0 && (
          <ToolResultBlock results={toolResults} />
        )}
      </div>
    </div>
  )
}
