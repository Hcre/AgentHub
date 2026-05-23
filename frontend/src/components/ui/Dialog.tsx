import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
}

export function Dialog({ open, onOpenChange, children }: DialogProps) {
  if (!open) return null
  return (
    <div className="animate-[var(--animate-fade-in)] fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />
      <div className="animate-[var(--animate-slide-in)] relative z-10">{children}</div>
    </div>
  )
}

export function DialogContent({
  className,
  children,
}: {
  className?: string
  children: ReactNode
}) {
  return (
    <div
      className={cn(
        'flex max-h-[85vh] w-[560px] max-w-[calc(100vw-2rem)] flex-col rounded-xl border bg-background shadow-lg',
        className,
      )}
    >
      {children}
    </div>
  )
}
