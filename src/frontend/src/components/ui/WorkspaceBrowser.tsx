import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Button, Icon } from './index'

interface FsItem { name: string; path: string; type: string }

export function WorkspaceBrowser({ open, onClose, onSelect }: {
  open: boolean; onClose: () => void; onSelect: (path: string) => void
}) {
  const [current, setCurrent] = useState('')
  const [items, setItems] = useState<FsItem[]>([])
  const [parent, setParent] = useState('')
  const [stack, setStack] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  const browse = async (path: string) => {
    setLoading(true)
    try {
      const qs = path ? `?path=${encodeURIComponent(path)}` : ''
      const r = await fetch(`/api/fs/browse${qs}`)
      const data = await r.json()
      if (Array.isArray(data)) {
        setCurrent(''); setParent('')
        setItems(data.map((d: any) => ({ name: d.label ?? d.letter, path: d.path, type: 'drive' })))
        setStack([])
      } else {
        setCurrent(data.path ?? path); setParent(data.parent ?? '')
        setItems(data.items ?? [])
        if (path && !stack.includes(path)) setStack([...stack, path])
      }
    } catch {
      // 后端不可用时静默失败
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { if (open) browse('') }, [open])
  if (!open) return null

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="w-[420px] max-h-[80vh] rounded-lg border bg-background shadow-xl flex flex-col">
        <header className="flex items-center gap-1 border-b px-3 py-2 shrink-0">
          <Button variant="ghost" size="iconSm" disabled={!parent && stack.length === 0}
            onClick={() => { const prev = stack[stack.length - 2] || ''; setStack(s => s.slice(0, -1)); browse(prev) }}>
            <Icon name="chevronLeft" className="h-3.5 w-3.5" />
          </Button>
          <span className="flex-1 truncate text-[12px] font-medium">{current || '此电脑'}</span>
          <Button variant="ghost" size="iconSm" onClick={onClose}><Icon name="x" className="h-3.5 w-3.5" /></Button>
        </header>
        <div className="max-h-64 overflow-y-auto p-1 flex-1">
          {loading ? (
            <div className="py-10 text-center text-[12px] text-muted-foreground">加载中…</div>
          ) : items.length === 0 ? (
            <div className="py-10 text-center text-[12px] text-muted-foreground">此目录为空</div>
          ) : (
            items.map((item) => (
              <button key={item.path}
                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-[13px] hover:bg-accent"
                onClick={() => browse(item.path)}
                onDoubleClick={() => onSelect(item.path)}
              >
                <span>{item.type === 'drive' ? '💿' : '📁'}</span>
                <span className="truncate">{item.name}</span>
              </button>
            ))
          )}
        </div>
        <footer className="flex items-center justify-between border-t px-3 py-2 shrink-0">
          <span className="text-[11px] text-muted-foreground/60">单击进入 · 双击选择</span>
          {current && <Button variant="brand" size="sm" onClick={() => onSelect(current)}>选此目录</Button>}
        </footer>
      </div>
    </div>,
    document.body
  )
}
