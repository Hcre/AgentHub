import { useEffect, useRef, useState } from 'react'
import { user } from '../../data/mock'
import { useChatStore } from '../../stores/chatStore'
import { useUIStore } from '../../stores/uiStore'
import { sessionsApi } from '../../api/sessions'
import { useWebSocket } from '../../hooks/useWebSocket'
import { Composer } from './Composer'
import { MessageBubble } from './MessageBubble'
import { TypingIndicator } from './TypingIndicator'
import { Button, Icon, Dialog, DialogContent } from '../ui'
import type { Agent } from '../../types'

interface FsItem { name: string; path: string; type: string }

/** 后端文件浏览弹窗 — 用了就能拿到完整路径 */
function WorkspaceBrowser({ open, onClose, onSelect }: {
  open: boolean; onClose: () => void; onSelect: (p: string) => void
}) {
  const [current, setCurrent] = useState('')
  const [items, setItems] = useState<FsItem[]>([])
  const [parent, setParent] = useState('')
  const [stack, setStack] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  const browse = async (path: string) => {
    setLoading(true)
    const qs = path ? `?path=${encodeURIComponent(path)}` : ''
    const r = await fetch(`/api/fs/browse${qs}`)
    const data = await r.json()
    if (Array.isArray(data)) {
      setCurrent('')
      setParent('')
      setItems(data.map((d: any) => ({ name: d.label ?? d.letter, path: d.path, type: 'drive' })))
      setStack([])
    } else {
      setCurrent(data.path ?? path)
      setParent(data.parent ?? '')
      setItems(data.items ?? [])
      if (path && !stack.includes(path)) setStack([...stack, path])
    }
    setLoading(false)
  }

  useEffect(() => { if (open) browse('') }, [open])

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <header className="flex items-center gap-1 border-b px-3 py-2">
          <Button variant="ghost" size="iconSm" disabled={!parent && stack.length === 0}
            onClick={() => { const prev = stack[stack.length - 2] || ''; setStack(s => s.slice(0, -1)); browse(prev) }}>
            <Icon name="chevronLeft" className="h-3.5 w-3.5" />
          </Button>
          <span className="flex-1 truncate text-[12px] font-medium">{current || '此电脑'}</span>
          <Button variant="ghost" size="iconSm" onClick={onClose}><Icon name="x" className="h-3.5 w-3.5" /></Button>
        </header>
        <div className="max-h-64 overflow-y-auto p-1">
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
        <footer className="flex items-center justify-between border-t px-3 py-2">
          <span className="text-[11px] text-muted-foreground/60">单击进入 · 双击选择</span>
          {current && <Button variant="brand" size="sm" onClick={() => onSelect(current)}>选此目录</Button>}
        </footer>
      </DialogContent>
    </Dialog>
  )
}

export function ChatView({ agent }: { agent: Agent }) {
  const activeConversationId = useUIStore((s) => s.activeConversationId)
  const messages = useChatStore((s) => s.messages)
  const typing = useChatStore((s) => s.typing)
  const send = useChatStore((s) => s.send)
  const sessionIds = useChatStore((s) => s.sessionIds)
  const setSessionId = useChatStore((s) => s.setSessionId)
  const bottomRef = useRef<HTMLDivElement>(null)
  const [workspacePath, setWorkspacePath] = useState('')
  const [editWs, setEditWs] = useState(false)
  const [wsInput, setWsInput] = useState('')
  const [browserOpen, setBrowserOpen] = useState(false)

  const key = activeConversationId ? `${agent.id}|${activeConversationId}` : null
  const list = key ? (messages[key] ?? []) : []
  const isTyping = key ? (typing[key] ?? false) : false
  const sessionId = key ? (sessionIds[key] ?? null) : null

  // 首次进入会话：创建后端 Session 并恢复 workspace。
  useEffect(() => {
    if (!key) return
    if (sessionId) {
      // 已有 session — 加载其 workspace_path
      fetch(`/api/sessions/${sessionId}`)
        .then((r) => r.json())
        .then((s) => { if (s.workspace_path) setWorkspacePath(s.workspace_path) })
        .catch(() => {})
      return
    }
    let cancelled = false
    // 从后端获取 agent 的 workspace_path 设置
    fetch(`/api/agents/${agent.id}`)
      .then(r => r.json())
      .then(ag => ag.settings?.workspace_path || '')
      .catch(() => '')
      .then(wsPath => {
        if (cancelled) return
        sessionsApi.createPrivate(agent.id, '', wsPath)
          .then((s) => {
            if (cancelled) return
            setSessionId(key, s.id)
            if (s.workspace_path) setWorkspacePath(s.workspace_path)
          })
          .catch(() => {})
      })
    return () => {
      cancelled = true
    }
  }, [key, sessionId, agent.id, setSessionId])

  const { sendMessage } = useWebSocket(sessionId, key)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [list.length, isTyping])

  const onSend = (text: string) => {
    if (!activeConversationId) return
    // 优先走真实 WS；未连接（mock agent / 后端不可用）则降级假回复
    if (!sendMessage(text)) send(agent.id, activeConversationId, text)
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-5">
        <div className="ah-msgs mx-auto flex max-w-3xl flex-col gap-5">
          {list.map((m) => (
            <MessageBubble key={m.id} msg={m} agent={agent} user={user} />
          ))}
          {isTyping && <TypingIndicator agent={agent} />}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* 工作空间 — 文本输入 + 后端浏览器辅助（后端拿得到完整路径） */}
      <div className="border-t border-border/70 px-4 py-1.5">
        {editWs ? (
          <form className="flex items-center gap-1.5" onSubmit={(e) => {
            e.preventDefault()
            const p = wsInput.trim()
            if (p) {
              setWorkspacePath(p)
              if (sessionId && key) fetch(`/api/sessions/${sessionId}`, {
                method: 'PATCH', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ workspace_path: p }),
              }).catch(() => {})
            }
            setEditWs(false)
          }}>
            <Icon name="sparkle" className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
            <input value={wsInput} onChange={(e) => setWsInput(e.target.value)}
              placeholder="D:\projects\blog"
              className="h-7 flex-1 rounded-md border border-input bg-transparent px-2 text-[11px] outline-none"
              autoFocus onBlur={() => setEditWs(false)}
            />
            <Button variant="ghost" size="iconSm" type="submit"><Icon name="check" className="h-3 w-3" /></Button>
          </form>
        ) : (
          <div className="flex items-center gap-1">
            <button type="button" onClick={() => { setEditWs(true); setWsInput(workspacePath) }}
              className="flex flex-1 items-center gap-1.5 py-0.5 text-[11px] text-muted-foreground hover:text-foreground"
            >
              <Icon name="sparkle" className="h-3 w-3 flex-shrink-0" />
              {workspacePath ? <span className="truncate">📁 {workspacePath}</span>
               : <span>设置工作目录…</span>}
            </button>
            <button type="button" onClick={() => setBrowserOpen(true)}
              className="flex-shrink-0 text-[11px] text-brand hover:underline"
            >浏览</button>
          </div>
        )}
      </div>

      {browserOpen && (
        <WorkspaceBrowser open={browserOpen} onClose={() => setBrowserOpen(false)}
          onSelect={(path) => {
            setWorkspacePath(path)
            if (sessionId && key) fetch(`/api/sessions/${sessionId}`, {
              method: 'PATCH', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ workspace_path: path }),
            }).catch(() => {})
            setBrowserOpen(false)
          }} />
      )}

      <Composer agent={agent} onSend={onSend} />
    </div>
  )
}
