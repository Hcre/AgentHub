import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../lib/cn'
import type { IconName } from '../../types'
import { Icon } from './Icon'

export interface ContextMenuItem {
  icon: IconName
  label: string
  /** 红色高亮（删除等危险操作） */
  danger?: boolean
  onClick: () => void
}

export function ContextMenu({
  x,
  y,
  items,
  onClose,
}: {
  x: number
  y: number
  items: ContextMenuItem[]
  onClose: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('keydown', onKey)
    // 延迟绑定 click，避免触发右键的同一次 mouseup 立刻关闭菜单
    const t = setTimeout(() => document.addEventListener('click', onClick), 0)
    return () => {
      document.removeEventListener('keydown', onKey)
      clearTimeout(t)
      document.removeEventListener('click', onClick)
    }
  }, [onClose])

  // 防止溢出视口
  const style: React.CSSProperties = { left: x, top: y }
  if (typeof window !== 'undefined') {
    if (x + 160 > window.innerWidth) style.left = x - 160
    if (y + items.length * 36 + 8 > window.innerHeight) style.top = y - items.length * 36 - 8
  }

  return createPortal(
    <div
      ref={ref}
      style={style}
      className="fixed z-50 min-w-[140px] rounded-lg border bg-background p-1 shadow-lg"
    >
      {items.map((item) => (
        <button
          key={item.label}
          onClick={() => {
            item.onClick()
            onClose()
          }}
          className={cn(
            'flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-[13px] transition-colors',
            item.danger
              ? 'text-destructive hover:bg-destructive/10'
              : 'text-foreground hover:bg-accent',
          )}
        >
          <Icon name={item.icon} className="h-3.5 w-3.5" />
          <span>{item.label}</span>
        </button>
      ))}
    </div>,
    document.body,
  )
}
