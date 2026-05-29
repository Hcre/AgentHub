import { cn } from '../../lib/cn'
import type { AgentColor } from '../../types'

const PALETTES: Record<AgentColor, string> = {
  brand: 'bg-brand text-brand-foreground',
  neutral: 'bg-zinc-200 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-200',
  sage: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
  clay: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
  rose: 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300',
  blue: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
}

export interface AvatarProps {
  initial: string
  color?: AgentColor
  size?: number
  online?: boolean
  className?: string
}

export function Avatar({ initial, color = 'neutral', size = 24, online, className }: AvatarProps) {
  const dot = Math.max(7, size * 0.28)
  return (
    <div
      className={cn(
        'relative inline-flex flex-shrink-0 items-center justify-center rounded-full font-medium',
        PALETTES[color],
        className,
      )}
      style={{ width: size, height: size, fontSize: Math.max(10, size * 0.42) }}
    >
      <span className="leading-none">{initial}</span>
      {online !== undefined && (
        <span
          className={cn(
            'absolute -bottom-0.5 -right-0.5 rounded-full border-2 border-background',
            online ? 'bg-emerald-500' : 'bg-zinc-400',
          )}
          style={{ width: dot, height: dot }}
        />
      )}
    </div>
  )
}
