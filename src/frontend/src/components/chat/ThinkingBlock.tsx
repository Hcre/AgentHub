import { useState, useCallback } from 'react'
import { Brain, ChevronDown, ChevronUp, Copy } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

/** ThinkingBlock：模型推理过程展示。
 *  流式时默认展开并带脉冲动画 + 游标；完成后默认收起。
 *  hover 时显示复制按钮。 */
export function ThinkingBlock({ text, streaming }: { text: string; streaming?: boolean }) {
  const [expanded, setExpanded] = useState(true)
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
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
  }, [text])

  const toggle = () => setExpanded((v) => !v)

  return (
    <div className="mt-2 rounded-lg border border-amber-200/60 bg-amber-50/40 dark:border-amber-800/50 dark:bg-amber-950/20 px-3 py-2">
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-center gap-2 select-none"
        aria-expanded={expanded}
        aria-label="思考过程"
      >
        <Brain
          className={`h-4 w-4 text-amber-600 dark:text-amber-400 ${streaming ? 'animate-pulse' : ''}`}
          strokeWidth={1.75}
        />
        <span className="text-[12px] font-medium text-amber-700 dark:text-amber-300">
          思考过程{streaming ? '…' : ''}
        </span>
        {expanded ? (
          <ChevronUp className="ml-auto h-3.5 w-3.5 text-amber-500" strokeWidth={1.75} />
        ) : (
          <ChevronDown className="ml-auto h-3.5 w-3.5 text-amber-500" strokeWidth={1.75} />
        )}
      </button>

      <div
        className={`transition-all duration-200 ease-out overflow-hidden ${
          expanded ? 'max-h-96 overflow-y-auto mt-1.5' : 'max-h-0'
        }`}
      >
        <div className="pl-6 text-[13px] leading-relaxed text-amber-800/80 dark:text-amber-200/70 font-normal relative group/think">
          <ReactMarkdown
            components={{
              h1: ({ children }) => <p className="font-medium">{children}</p>,
              h2: ({ children }) => <p className="font-medium">{children}</p>,
              h3: ({ children }) => <p className="font-medium">{children}</p>,
              h4: ({ children }) => <p className="font-medium">{children}</p>,
              h5: ({ children }) => <p className="font-medium">{children}</p>,
              h6: ({ children }) => <p className="font-medium">{children}</p>,
              p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
              code: ({ children }) => (
                <code className="rounded bg-amber-200/50 dark:bg-amber-800/30 px-1 py-0.5 text-[12px]">
                  {children}
                </code>
              ),
              pre: ({ children }) => (
                <pre className="overflow-x-auto rounded bg-amber-200/30 dark:bg-amber-800/20 px-2 py-1 my-1 text-[12px]">
                  {children}
                </pre>
              ),
            }}
          >
            {text}
          </ReactMarkdown>
          {streaming && (
            <span className="inline-block w-1.5 h-4 bg-amber-500 animate-pulse ml-0.5 align-text-bottom" />
          )}
          <button
            type="button"
            onClick={handleCopy}
            className="absolute top-0 right-0 opacity-0 group-hover/think:opacity-100 transition-opacity"
            aria-label="复制思考内容"
            title="复制思考内容"
          >
            <Copy className="h-3 w-3 text-muted-foreground hover:text-foreground" strokeWidth={1.75} />
          </button>
          {copied && (
            <span className="absolute top-0 right-6 text-[10px] text-emerald-600">已复制</span>
          )}
        </div>
      </div>
    </div>
  )
}
