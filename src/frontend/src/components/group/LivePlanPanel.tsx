import { useState } from 'react'
import { CheckCircle2, Circle, Loader2, XCircle, Ban, ChevronRight, ChevronDown, CornerDownRight, Wrench, Check, X } from 'lucide-react'
import { useGroupStore } from '../../stores/groupStore'
import { lookupActor } from './actors'
import { Avatar } from '../ui'
import { cn } from '../../lib/cn'
import type { Group, LivePlanStep, StepActivity, StepStatus } from '../../types'

/** 单条工具名美化：mcp__server__tool → tool；Read/Write/Bash 原样。 */
function prettyToolName(name?: string): string {
  if (!name) return '工具'
  const parts = name.split('__')
  return parts[parts.length - 1] || name
}

/** Claude Code 风格的实时活动 feed：旁白 + 工具调用。 */
function ActivityFeed({ activity }: { activity: StepActivity[] }) {
  return (
    <div className="mt-1.5 space-y-1 border-l-2 border-brand/20 pl-2.5">
      {activity.map((a, i) =>
        a.kind === 'text' ? (
          <p key={i} className="text-[12px] leading-snug text-foreground/75 [text-wrap:pretty]">
            {a.text}
          </p>
        ) : (
          <div key={i} className="flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground">
            {a.ok === undefined ? (
              <Wrench className="h-3 w-3 flex-shrink-0 text-brand" strokeWidth={2} />
            ) : a.ok ? (
              <Check className="h-3 w-3 flex-shrink-0 text-emerald-500" strokeWidth={2.5} />
            ) : (
              <X className="h-3 w-3 flex-shrink-0 text-red-500" strokeWidth={2.5} />
            )}
            <span className="text-foreground/70">{prettyToolName(a.name)}</span>
          </div>
        ),
      )}
    </div>
  )
}

const STATUS_TEXT: Record<StepStatus, string> = {
  pending: '等待',
  running: '进行中',
  completed: '完成',
  failed: '失败',
  blocked: '阻塞',
}

/** 状态图标（颜色编码）。running 转圈，其余静态。 */
function StatusIcon({ status }: { status: StepStatus }) {
  const cls = 'h-4 w-4 flex-shrink-0'
  switch (status) {
    case 'completed':
      return <CheckCircle2 className={cn(cls, 'text-emerald-500')} strokeWidth={2} />
    case 'running':
      return <Loader2 className={cn(cls, 'animate-spin text-brand')} strokeWidth={2} />
    case 'failed':
      return <XCircle className={cn(cls, 'text-red-500')} strokeWidth={2} />
    case 'blocked':
      return <Ban className={cn(cls, 'text-muted-foreground')} strokeWidth={2} />
    default:
      return <Circle className={cn(cls, 'text-muted-foreground/40')} strokeWidth={2} />
  }
}

interface StepRowProps {
  step: LivePlanStep
  group: Group
  labelById: Map<string, string>
  expanded: boolean
  onToggle: () => void
  onLocate?: (who: string) => void
}

function StepRow({ step, group, labelById, expanded, onToggle, onLocate }: StepRowProps) {
  const actor = lookupActor(step.who, group)
  const deps = step.depends.map((d) => labelById.get(d) ?? d)
  return (
    <li className="border-t border-border/50 first:border-t-0">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors hover:bg-muted/40"
      >
        <StatusIcon status={step.status} />
        <span
          className={cn(
            'flex-1 truncate text-[13px]',
            step.status === 'blocked' && 'text-muted-foreground line-through',
            step.status === 'pending' && 'text-muted-foreground',
          )}
        >
          {step.label}
        </span>
        <Avatar initial={actor.initial} color={actor.color} size={18} />
        <span className="hidden w-16 truncate text-right text-[11px] text-muted-foreground sm:inline">
          {actor.name}
        </span>
        <span
          className={cn(
            'w-12 text-right font-mono text-[10.5px]',
            step.status === 'running' && 'text-brand',
            step.status === 'completed' && 'text-emerald-600 dark:text-emerald-400',
            step.status === 'failed' && 'text-red-600 dark:text-red-400',
            (step.status === 'pending' || step.status === 'blocked') && 'text-muted-foreground',
          )}
        >
          {STATUS_TEXT[step.status]}
        </span>
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
        )}
      </button>
      {expanded && (
        <div className="space-y-1.5 bg-muted/20 px-3 pb-2.5 pl-9 pt-0.5 text-[12px] text-muted-foreground">
          <div>
            执行人：<span className="text-foreground/80">{actor.name}</span>
          </div>
          <div>
            前置依赖：
            <span className="text-foreground/80">{deps.length ? deps.join('、') : '无，可立即开始'}</span>
          </div>
          {step.reason && <div className="text-red-600 dark:text-red-400">原因：{step.reason}</div>}
          {step.activity && step.activity.length > 0 ? (
            <div>
              <div className="text-[11px] font-medium text-foreground/60">实时进度</div>
              <ActivityFeed activity={step.activity} />
            </div>
          ) : (
            <div className="text-muted-foreground/60">
              {step.status === 'pending' ? '尚未开始' : '暂无活动记录'}
            </div>
          )}
          {onLocate && (
            <button
              type="button"
              onClick={() => onLocate(step.who)}
              className="inline-flex items-center gap-1 text-brand hover:underline"
            >
              <CornerDownRight className="h-3 w-3" />
              查看 TA 的发言
            </button>
          )}
        </div>
      )}
    </li>
  )
}

/** Live DAG 进度卡：钉在成员条与消息区之间。activePlan 非 null 自动出现。 */
export function LivePlanPanel({
  group,
  onLocateWorker,
}: {
  group: Group
  onLocateWorker?: (who: string) => void
}) {
  const plan = useGroupStore((s) => s.activePlanByGroup[group.id] ?? null)
  const dismiss = useGroupStore((s) => s.dismissActivePlan)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  // null = 跟随自动（执行中展开、完成收起）；true/false = 用户手动覆盖。
  const [manualCollapsed, setManualCollapsed] = useState<boolean | null>(null)

  const steps = plan?.steps ?? []
  const allTerminal =
    steps.length > 0 &&
    steps.every((s) => s.status === 'completed' || s.status === 'failed' || s.status === 'blocked')
  const anyFailed = steps.some((s) => s.status === 'failed' || s.status === 'blocked')
  const collapsed = manualCollapsed ?? allTerminal // 完成后默认收起，无 effect

  if (!plan || steps.length === 0) return null

  const done = steps.filter((s) => s.status === 'completed').length
  const total = steps.length
  const pct = Math.round((done / total) * 100)
  const labelById = new Map(steps.map((s) => [s.id, s.label]))

  return (
    <div className="mx-4 my-2 overflow-hidden rounded-xl border border-brand/30 bg-card shadow-sm">
      <div className="flex items-center gap-2.5 border-b border-border/60 bg-brand/5 px-3 py-2">
        <button
          type="button"
          onClick={() => setManualCollapsed(!collapsed)}
          className="flex flex-1 items-center gap-2.5 text-left"
          aria-expanded={!collapsed}
          title={collapsed ? '展开任务进度' : '收起任务进度'}
        >
          {allTerminal ? (
            anyFailed ? (
              <XCircle className="h-4 w-4 text-red-500" strokeWidth={2} />
            ) : (
              <CheckCircle2 className="h-4 w-4 text-emerald-500" strokeWidth={2} />
            )
          ) : (
            <Loader2 className="h-4 w-4 animate-spin text-brand" strokeWidth={2} />
          )}
          <span className="text-[13px] font-semibold text-foreground">
            {allTerminal ? (anyFailed ? '任务结束' : '任务完成') : '任务执行中'}
          </span>
          <span className="font-mono text-[11px] text-muted-foreground">
            {done}/{total} 完成
          </span>
          <div className="ml-auto h-1.5 w-20 overflow-hidden rounded-full bg-muted">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-500',
                anyFailed ? 'bg-red-400' : 'bg-brand',
              )}
              style={{ width: `${pct}%` }}
            />
          </div>
          {collapsed ? (
            <ChevronRight className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
          )}
        </button>
        <button
          type="button"
          onClick={() => dismiss(group.id)}
          className="grid h-5 w-5 flex-shrink-0 place-items-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="关闭任务卡"
          title="关闭任务卡"
        >
          <X className="h-3.5 w-3.5" strokeWidth={2} />
        </button>
      </div>
      {!collapsed && (
        <ol className="max-h-80 overflow-y-auto">
          {steps.map((step) => (
            <StepRow
              key={step.id}
              step={step}
              group={group}
              labelById={labelById}
              expanded={expandedId === step.id}
              onToggle={() => setExpandedId((cur) => (cur === step.id ? null : step.id))}
              onLocate={onLocateWorker}
            />
          ))}
        </ol>
      )}
    </div>
  )
}
