import type { HTMLAttributes, ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../lib/cn'

export interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
  /**
   * 测试钩子：把 data-testid 透传到外层 wrapper（fixed inset-0 z-50 那层），
   * 让 vitest 能在 portal 出去的节点上直接 `getByTestId('xxx-dialog')`。
   * backdrop 是 dialog 同一父容器内的兄弟 div。
   */
  'data-testid'?: string
}

export function Dialog({ open, onOpenChange, children, ...rest }: DialogProps) {
  if (!open) return null
  return createPortal(
    <div
      data-testid={rest['data-testid']}
      className="animate-[var(--animate-fade-in)] fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />
      <div className="animate-[var(--animate-slide-in)] relative z-10">{children}</div>
    </div>,
    document.body,
  )
}

export function DialogContent({
  className,
  children,
  ...rest
}: {
  className?: string
  children: ReactNode
} & HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...rest}
      className={cn(
        'flex max-h-[85vh] w-[560px] max-w-[calc(100vw-2rem)] flex-col rounded-xl border bg-background shadow-lg',
        className,
      )}
    >
      {children}
    </div>
  )
}
