import { createContext, useContext, type ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface TabsContextValue {
  value: string
  onValueChange: (value: string) => void
}

const TabsCtx = createContext<TabsContextValue | null>(null)

function useTabs(): TabsContextValue {
  const ctx = useContext(TabsCtx)
  if (!ctx) throw new Error('Tabs.* 必须在 <Tabs> 内使用')
  return ctx
}

export interface TabsProps {
  value: string
  onValueChange: (value: string) => void
  className?: string
  children: ReactNode
}

export function Tabs({ value, onValueChange, className, children }: TabsProps) {
  return (
    <TabsCtx.Provider value={{ value, onValueChange }}>
      <div className={className}>{children}</div>
    </TabsCtx.Provider>
  )
}

export function TabsList({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={cn(
        'inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground',
        className,
      )}
    >
      {children}
    </div>
  )
}

export interface TabsTriggerProps {
  value: string
  className?: string
  children: ReactNode
}

export function TabsTrigger({ value, className, children }: TabsTriggerProps) {
  const ctx = useTabs()
  const active = ctx.value === value
  return (
    <button
      type="button"
      onClick={() => ctx.onValueChange(value)}
      data-state={active ? 'active' : 'inactive'}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        active ? 'bg-background text-foreground shadow' : 'hover:text-foreground',
        className,
      )}
    >
      {children}
    </button>
  )
}
