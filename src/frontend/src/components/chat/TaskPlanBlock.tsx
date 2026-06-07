import { useState, useCallback } from 'react'
import { ChevronDown, ChevronUp, Copy, ListTodo } from 'lucide-react'
import type { TaskPlanData } from '../../types'

/** TaskPlanBlock：结构化任务计划。首次到达展开，之后可折叠。
 * Phase 1 仅供展示；Phase 2 预飞计划模式接入审批交互。 */
export function TaskPlanBlock({ plan }: { plan: TaskPlanData }) {
  const [expanded, setExpanded] = useState(true)
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    const lines = [`任务计划: ${plan.summary}`]
    plan.steps.forEach((s, i) => {
      const deps = s.depends?.length ? ` (依赖: ${s.depends.join(', ')})` : ''
      const eta = s.eta ? ` [~${s.eta}min]` : ''
      lines.push(`  ${i + 1}. ${s.label}${deps}${eta}`)
    })
    if (plan.totalEta) lines.push(`预计总耗时: ~${plan.totalEta}min`)
    const text = lines.join('\n')
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
  }, [plan])

  const toggle = () => setExpanded((v) => !v)

  return (
    <div className="mt-2 rounded-lg border border-indigo-200/70 dark:border-indigo-700/50 bg-indigo-50/30 dark:bg-indigo-950/20 px-4 py-3">
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-center gap-2 mb-2 select-none"
        aria-expanded={expanded}
        aria-label="任务计划"
      >
        <ListTodo className="h-4 w-4 text-indigo-600 dark:text-indigo-400 flex-shrink-0" strokeWidth={1.75} />
        <span className="text-[13px] font-semibold text-indigo-800 dark:text-indigo-200">
          任务计划
        </span>
        <span className="font-mono text-[11px] text-indigo-500 dark:text-indigo-400 bg-indigo-100 dark:bg-indigo-900/40 px-1.5 py-0.5 rounded-full">
          {plan.steps.length} 步
        </span>
        {expanded ? (
          <ChevronUp className="ml-auto h-3.5 w-3.5 text-indigo-400" strokeWidth={1.75} />
        ) : (
          <ChevronDown className="ml-auto h-3.5 w-3.5 text-indigo-400" strokeWidth={1.75} />
        )}
      </button>

      <div
        className={`transition-all duration-200 overflow-hidden ${
          expanded ? 'max-h-96 overflow-y-auto' : 'max-h-0'
        }`}
      >
        <div className="mt-2 space-y-1.5 relative group/tp">
          {plan.steps.map((step, i) => (
            <div key={step.id} className="flex items-start gap-2 py-1 px-2 rounded hover:bg-indigo-100/40 dark:hover:bg-indigo-900/20 transition-colors">
              <div className="grid place-items-center h-5 w-5 rounded-full bg-indigo-200 dark:bg-indigo-800 text-[10px] font-bold text-indigo-700 dark:text-indigo-300 flex-shrink-0 mt-0.5">
                {i + 1}
              </div>
              <div className="min-w-0 flex-1">
                <span className="text-[13px] text-indigo-900/80 dark:text-indigo-100/80 leading-snug">
                  {step.label}
                </span>
                {step.depends?.length ? (
                  <span className="text-[10px] text-indigo-400 dark:text-indigo-500 italic ml-1">
                    依赖: 步骤 {step.depends.join(', ')}
                  </span>
                ) : null}
              </div>
              {step.eta ? (
                <span className="font-mono text-[10px] text-indigo-400 dark:text-indigo-500 ml-auto flex-shrink-0">
                  ~{step.eta}min
                </span>
              ) : null}
            </div>
          ))}
          {plan.totalEta ? (
            <div className="mt-3 pt-2 border-t border-indigo-200/40 dark:border-indigo-700/40 flex items-center gap-2 text-[11px] text-indigo-500 dark:text-indigo-400">
              <span className="font-mono">预计总耗时: ~{plan.totalEta}min</span>
            </div>
          ) : null}
          <button
            type="button"
            onClick={handleCopy}
            className="absolute top-0 right-0 opacity-0 group-hover/tp:opacity-100 transition-opacity"
            aria-label="复制计划"
            title="复制计划"
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
