import { useState, useCallback } from 'react'
import { ChevronDown, ChevronUp, Copy, FileOutput } from 'lucide-react'
import type { ToolResultEntry } from '../../types'

/** 截断长文本，超过 max 字符显示前 max 字符 + 摘要。 */
function truncateText(text: string, max = 2000): { display: string; truncated: boolean } {
  if (text.length <= max) return { display: text, truncated: false }
  return { display: text.slice(0, max), truncated: true }
}

/** ToolResultBlock：工具执行结果展示。默认折叠（结果嘈杂）。 */
export function ToolResultBlock({ results }: { results: ToolResultEntry[] }) {
  return (
    <>
      {results.map((r) => (
        <ToolResultItem key={r.id} result={r} />
      ))}
    </>
  )
}

function ToolResultItem({ result }: { result: ToolResultEntry }) {
  const [expanded, setExpanded] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [copied, setCopied] = useState(false)

  const { display, truncated } = truncateText(result.content)
  const visibleContent = showAll ? result.content : display

  const handleCopy = useCallback(async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(result.content)
      } else {
        const ta = document.createElement('textarea')
        ta.value = result.content
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
  }, [result.content])

  const toggle = () => setExpanded((v) => !v)

  const preview = result.content.slice(0, 80)

  return (
    <div className="border-t border-zinc-200/40 dark:border-zinc-700/40 px-3 py-2 bg-zinc-50/40 dark:bg-zinc-950/30">
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-center gap-2 select-none"
        aria-expanded={expanded}
        aria-label={result.isError ? '执行出错' : '返回结果'}
      >
        <FileOutput
          className={`h-3.5 w-3.5 flex-shrink-0 ${result.isError ? 'text-red-500' : 'text-emerald-500'}`}
          strokeWidth={1.75}
        />
        <span className="font-mono text-[11px] font-medium text-zinc-500 dark:text-zinc-400">
          {result.isError ? '执行出错' : '返回结果'}
        </span>
        <span className="font-mono text-[11px] text-zinc-400 dark:text-zinc-500 truncate max-w-[280px] ml-auto">
          {preview}{preview.length >= 80 ? '…' : ''}
        </span>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 text-zinc-400 flex-shrink-0" strokeWidth={1.75} />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-zinc-400 flex-shrink-0" strokeWidth={1.75} />
        )}
      </button>
      <div
        className={`transition-all duration-150 overflow-hidden ${
          expanded ? 'max-h-48 overflow-y-auto mt-1.5' : 'max-h-0'
        }`}
      >
        <div className="relative group/tr">
          <pre className="font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-all text-zinc-600 dark:text-zinc-400 bg-zinc-200/40 dark:bg-zinc-800/60 rounded px-2 py-1.5">
            {visibleContent}
          </pre>
          {truncated && !showAll && (
            <button
              type="button"
              onClick={() => setShowAll(true)}
              className="text-[11px] text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 underline mt-1"
            >
              显示全部（共 {result.content.length} 字符）
            </button>
          )}
          <button
            type="button"
            onClick={handleCopy}
            className="absolute top-1 right-1 opacity-0 group-hover/tr:opacity-100 transition-opacity"
            aria-label="复制结果"
            title="复制结果"
          >
            <Copy className="h-3 w-3 text-muted-foreground hover:text-foreground" strokeWidth={1.75} />
          </button>
          {copied && (
            <span className="absolute top-1 right-7 text-[10px] text-emerald-600">已复制</span>
          )}
        </div>
      </div>
    </div>
  )
}
