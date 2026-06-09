import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Button, Icon } from './index'

interface FsItem {
  name: string
  path: string
  type: string
}

/** 文件夹浏览器：可浏览 + 双击/按钮选中。带「新建文件夹」入口（POST /api/fs/mkdir）。 */
export function WorkspaceBrowser({ open, onClose, onSelect }: {
  open: boolean
  onClose: () => void
  onSelect: (path: string) => void
}) {
  const [current, setCurrent] = useState('')
  const [items, setItems] = useState<FsItem[]>([])
  const [parent, setParent] = useState('')
  const [stack, setStack] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  /** 内嵌「新建文件夹」表单状态：null=收起，string=正在输入的名字 */
  const [newName, setNewName] = useState<string | null>(null)
  const [createErr, setCreateErr] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

  const browse = async (path: string): Promise<void> => {
    setLoading(true)
    try {
      const qs = path ? `?path=${encodeURIComponent(path)}` : ''
      const r = await fetch(`${API_BASE}/api/fs/browse${qs}`)
      const data = await r.json()
      if (Array.isArray(data)) {
        setCurrent('')
        setParent('')
        setItems(
          data.map((d: { label?: string; letter?: string; path: string }) => ({
            name: d.label ?? d.letter ?? '',
            path: d.path,
            type: 'drive',
          })),
        )
        setStack([])
      } else {
        setCurrent(data.path ?? path)
        setParent(data.parent ?? '')
        setItems(data.items ?? [])
        if (path && !stack.includes(path)) setStack([...stack, path])
      }
    } catch {
      // 后端不可用时静默失败
    } finally {
      setLoading(false)
    }
  }

  // 父组件用 `key={open ? 'open' : 'closed'}` 触发重挂载，state 天然归零；这里只需首次拉根目录
  // browse 是 fetch 包装（外部系统同步），不在 lint 反模式范畴
  /* eslint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */
  useEffect(() => {
    void browse('')
  }, [])
  /* eslint-enable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */

  const handleCreate = async () => {
    if (!newName || !current) return
    setCreating(true)
    setCreateErr(null)
    try {
      const r = await fetch(`${API_BASE}/api/fs/mkdir`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parent: current, name: newName.trim() }),
      })
      const data = await r.json()
      if (!r.ok) {
        const detail = data?.detail
        const msg =
          typeof detail === 'string'
            ? detail
            : Array.isArray(detail)
              ? detail.map((d: { msg?: string }) => d.msg ?? '').filter(Boolean).join('; ')
              : `创建失败（${r.status}）`
        setCreateErr(msg || `创建失败（${r.status}）`)
        return
      }
      // 创建成功：刷新列表 + 立刻选中新文件夹
      const newPath: string = data.path
      setNewName(null)
      setCreateErr(null)
      await browse(newPath)
      onSelect(newPath)
    } catch (e) {
      setCreateErr(e instanceof Error ? e.message : '网络错误')
    } finally {
      setCreating(false)
    }
  }

  if (!open) return null

  const canCreateFolder = !!current && !!newName?.trim() && !creating

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="flex max-h-[80vh] w-[480px] flex-col rounded-lg border bg-background shadow-xl">
        <header className="flex shrink-0 items-center gap-1 border-b px-3 py-2">
          <Button
            variant="ghost"
            size="iconSm"
            disabled={!parent && stack.length === 0}
            onClick={() => {
              const prev = stack[stack.length - 2] || ''
              setStack((s) => s.slice(0, -1))
              browse(prev)
            }}
          >
            <Icon name="chevronLeft" className="h-3.5 w-3.5" />
          </Button>
          <span className="flex-1 truncate text-[12px] font-medium">{current || '此电脑'}</span>
          {/* 新建文件夹按钮（仅在已选目录时显示） */}
          {current && (
            <Button
              variant="ghost"
              size="iconSm"
              onClick={() => {
                setNewName('')
                setCreateErr(null)
              }}
              title="新建文件夹"
            >
              <Icon name="plus" className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button variant="ghost" size="iconSm" onClick={onClose}>
            <Icon name="x" className="h-3.5 w-3.5" />
          </Button>
        </header>

        {/* 内嵌「新建文件夹」表单 */}
        {newName !== null && current && (
          <div className="flex shrink-0 items-center gap-2 border-b bg-muted/40 px-3 py-2">
            <span className="text-[12px] text-muted-foreground">新建文件夹</span>
            <input
              autoFocus
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && canCreateFolder) void handleCreate()
                if (e.key === 'Escape') setNewName(null)
              }}
              placeholder="文件夹名"
              className="h-7 flex-1 rounded border border-input bg-background px-2 text-[12px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <Button size="sm" variant="brand" onClick={handleCreate} disabled={!canCreateFolder}>
              {creating ? '创建中…' : '创建'}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setNewName(null)}>
              取消
            </Button>
          </div>
        )}
        {createErr && (
          <div className="shrink-0 border-b bg-destructive/10 px-3 py-1.5 text-[11.5px] text-destructive">
            {createErr}
          </div>
        )}

        <div className="max-h-64 flex-1 overflow-y-auto p-1">
          {loading ? (
            <div className="py-10 text-center text-[12px] text-muted-foreground">加载中…</div>
          ) : items.length === 0 ? (
            <div className="py-10 text-center text-[12px] text-muted-foreground">此目录为空</div>
          ) : (
            items.map((item) => (
              <button
                key={item.path}
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
        <footer className="flex shrink-0 items-center justify-between border-t px-3 py-2">
          <span className="text-[11px] text-muted-foreground/60">
            单击进入 · 双击选择 · 点 + 新建文件夹
          </span>
          {current && (
            <Button variant="brand" size="sm" onClick={() => onSelect(current)}>
              选此目录
            </Button>
          )}
        </footer>
      </div>
    </div>,
    document.body,
  )
}
