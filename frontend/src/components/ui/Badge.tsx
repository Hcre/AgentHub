import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export type BadgeVariant =
  | 'default'
  | 'secondary'
  | 'outline'
  | 'brand'
  | 'success'
  | 'warning'
  | 'destructive'

const VARIANTS: Record<BadgeVariant, string> = {
  default: 'border-transparent bg-primary text-primary-foreground',
  secondary: 'border-transparent bg-secondary text-secondary-foreground',
  outline: 'text-foreground',
  brand: 'border-transparent bg-brand/10 text-brand dark:bg-brand/20',
  success:
    'border-transparent bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
  warning: 'border-transparent bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
  destructive: 'border-transparent bg-destructive/10 text-destructive',
}

export interface BadgeProps {
  variant?: BadgeVariant
  className?: string
  children: ReactNode
}

export function Badge({ variant = 'default', className, children }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wider',
        VARIANTS[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}
