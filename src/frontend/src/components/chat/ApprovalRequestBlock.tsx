import { useState, useCallback } from 'react'
import { ShieldAlert, Check, X, Loader2 } from 'lucide-react'
import { Button } from '../ui'
import type { ApprovalRequestData } from '../../types'

/**
 * ApprovalRequestBlock：阻断性审批请求卡。
 * 不可折叠，要求用户交互。Phase 1 仅本地翻转状态；
 * Phase 2 接入 POST /api/approvals/{id}/resolve 真正持久化。
 *
 * onResolve: 父组件收到决议后可更新 store 内的 approvalRequest.status。
 * 不传时按钮仅本地乐观更新。
 */
export function ApprovalRequestBlock({
  data,
  onResolve,
}: {
  data: ApprovalRequestData
  onResolve?: (action: 'approve' | 'deny') => void
}) {
  const [status, setStatus] = useState<'pending' | 'approved' | 'denied'>(data.status)
  const [submitting, setSubmitting] = useState(false)

  const handleApprove = useCallback(() => {
    if (status !== 'pending' || submitting) return
    setSubmitting(true)
    setStatus('approved')
    onResolve?.('approve')
    setSubmitting(false)
  }, [status, submitting, onResolve])

  const handleDeny = useCallback(() => {
    if (status !== 'pending' || submitting) return
    setSubmitting(true)
    setStatus('denied')
    onResolve?.('deny')
    setSubmitting(false)
  }, [status, submitting, onResolve])

  const isResolved = status !== 'pending'

  return (
    <div
      className={`mt-2 rounded-lg border-2 px-4 py-3 shadow-sm transition-opacity ${
        isResolved
          ? 'border-amber-300/50 dark:border-amber-600/30 bg-amber-50/30 dark:bg-amber-950/15 opacity-80'
          : 'border-amber-400/70 dark:border-amber-500/50 bg-amber-50/60 dark:bg-amber-950/30'
      }`}
    >
      <div className="flex items-center gap-2 mb-2">
        <ShieldAlert className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0" strokeWidth={1.75} />
        <span className="text-[13px] font-semibold text-amber-800 dark:text-amber-200">
          需要你的确认
        </span>
        <span
          className={`font-mono text-[10px] px-2 py-0.5 rounded-full ml-auto flex-shrink-0 ${
            status === 'pending'
              ? 'bg-amber-200 dark:bg-amber-800/50 text-amber-800 dark:text-amber-200'
              : status === 'approved'
                ? 'bg-emerald-200 dark:bg-emerald-800/40 text-emerald-800 dark:text-emerald-200'
                : 'bg-red-200 dark:bg-red-800/40 text-red-800 dark:text-red-200'
          }`}
        >
          {status === 'pending' ? '待确认' : status === 'approved' ? '已批准' : '已拒绝'}
        </span>
      </div>

      <div className="text-[13px] leading-relaxed text-amber-900/80 dark:text-amber-100/80 mb-3 whitespace-pre-wrap">
        {data.description}
      </div>

      {!isResolved && (
        <div className="flex items-center gap-2">
          <Button
            variant="default"
            size="sm"
            onClick={handleApprove}
            disabled={submitting}
          >
            {submitting ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" strokeWidth={2} />
            ) : (
              <Check className="mr-1.5 h-3.5 w-3.5" strokeWidth={1.75} />
            )}
            批准
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleDeny}
            disabled={submitting}
          >
            {submitting ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" strokeWidth={2} />
            ) : (
              <X className="mr-1.5 h-3.5 w-3.5" strokeWidth={1.75} />
            )}
            拒绝
          </Button>
        </div>
      )}

      {isResolved && data.resolvedBy && (
        <div className="mt-2 text-right text-[11px] text-muted-foreground">
          已由 {data.resolvedBy} 处理
        </div>
      )}
    </div>
  )
}
