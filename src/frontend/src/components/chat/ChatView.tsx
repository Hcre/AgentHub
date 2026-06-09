import { useEffect, useRef, useState } from 'react'
import { user } from '../../data/mock'
import { convKey, useChatStore } from '../../stores/chatStore'
import { useUIStore } from '../../stores/uiStore'
import { sessionsApi } from '../../api/sessions'
import { useWebSocket } from '../../hooks/useWebSocket'
import { getPoolWs } from '../../hooks/wsPool'
import { Composer, type ComposerHandle } from './Composer'
import { MessageBubble } from './MessageBubble'
import { TypingIndicator } from './TypingIndicator'
import { Icon } from '../ui'
import type { Agent, ChatMessage, ReplyRef } from '../../types'

export function ChatView({ agent }: { agent: Agent }) {
  const activeConversationId = useUIStore((s) => s.activeConversationId)
  const messages = useChatStore((s) => s.messages)
  const typing = useChatStore((s) => s.typing)
  const send = useChatStore((s) => s.send)
  const sessionIds = useChatStore((s) => s.sessionIds)
  const setSessionId = useChatStore((s) => s.setSessionId)
  const clearUnread = useChatStore((s) => s.clearUnread)
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const composerRef = useRef<ComposerHandle>(null)
  const [workspacePath, setWorkspacePath] = useState('')
  // 滚动到底部按钮：滚动时检测是否在底部（≤24px 容差）
  const [isAtBottom, setIsAtBottom] = useState(true)
  // 用户主动滚走后，新消息到来的计数（点 ↓ 时清零）
  const [pendingCount, setPendingCount] = useState(0)
  const key = activeConversationId ? convKey(agent.id, activeConversationId) : null
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
    // 从 conversation store 读取 workdir（由 StartChatModal 写入），不回退 agent settings
    const convs = useChatStore.getState().conversations[agent.id] ?? []
    const activeConv = convs.find(c => c.id === activeConversationId)
    const wsPath = activeConv?.workdir || ''
    sessionsApi.createPrivate(agent.id, '', wsPath)
      .then((s) => {
        if (cancelled) return
        setSessionId(key, s.id)
        if (s.workspace_path) setWorkspacePath(s.workspace_path)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [key, sessionId, agent.id, setSessionId, activeConversationId])

  const { sendMessage } = useWebSocket(sessionId, key)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [list.length, isTyping])

  // 进入会话时清零未读；新消息如果在底部则自动滚到底 + 清零 pending
  useEffect(() => {
    if (!key) return
    clearUnread(key)
  }, [key, clearUnread])

  useEffect(() => {
    // 滚到底时清零未读计数（pattern 与 line 44 同源：依赖 store 状态自动 reset）
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (isAtBottom) setPendingCount(0)
  }, [list.length, isAtBottom])

  // 滚动监听：是否在底部
  const onScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    setIsAtBottom(distFromBottom < 24)
  }

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    setPendingCount(0)
  }

  const onSend = (payload: { text: string; attachment?: { name: string; size: string; url?: string }; replyTo?: ReplyRef }) => {
    if (!activeConversationId) return
    const { text, attachment, replyTo } = payload
    // 优先走真实 WS；未连接（mock agent / 后端不可用）则降级假回复
    if (!sendMessage(text, attachment, replyTo)) send(agent.id, activeConversationId, text, attachment, replyTo)
  }

  const handleCreateSkill = () => {
    if (!activeConversationId) return
    const text = '请帮我创建一个新的 Skill'
    if (!sendMessage(text)) send(agent.id, activeConversationId, text)
  }

  // P1-1 reply/quote：MessageBubble 点的回复按钮 → 调 composerRef.setReplyTo
  const handleReply = (target: ChatMessage) => {
    const author =
      target.from === 'user'
        ? user.handle
        : agent.name
    const snippet = (target.text ?? '').slice(0, 60)
    const ref: ReplyRef = { id: target.id, author, snippet }
    composerRef.current?.setReplyTo(ref)
  }

  // 3 个 prompt 建议卡（top-level const — 用作 single source of truth，测试也用同一份）
  const prompts = PROMPTS_DEFAULT

  return (
    <div className="flex h-full flex-col">
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="relative flex-1 overflow-y-auto overflow-x-hidden px-4 py-5"
      >
        <div className="ah-msgs mx-auto flex max-w-3xl flex-col gap-5">
          {list.length === 0 ? (
            <EmptyChatState
              agentName={agent.name}
              prompts={prompts}
              onPick={(text) => onSend({ text })}
            />
          ) : (
            list.map((m) => (
              <MessageBubble
                key={m.id}
                msg={m}
                agent={agent}
                user={user}
                sessionId={sessionId ?? undefined}
                onReply={handleReply}
              />
            ))
          )}
          {isTyping && <TypingIndicator agent={agent} />}
          <div ref={bottomRef} />
        </div>

        {/* 浮动 ↓ 按钮：移出滚动容器，放到 workspace 区域，top-0 -translate-y-full 永远紧贴 chat 底部 */}
      </div>

      {/* 工作空间 — 文本输入 + 后端浏览器辅助（后端拿得到完整路径） */}
      <div className="relative border-t border-border/70 px-4 py-1.5">
        {/* 浮动 ↓ 按钮：移出滚动容器，绝对定位到 workspace 区上沿，
            永远紧贴 chat 底部（workdir chip 之上），isAtBottom 时整段不渲染 */}
        {!isAtBottom && (
          <button
            type="button"
            onClick={scrollToBottom}
            title="滚动到底部"
            className="absolute left-1/2 -top-5 z-10 flex h-9 -translate-x-1/2 items-center gap-1.5 rounded-full border bg-card/90 px-3 text-[12px] font-medium text-foreground shadow-sm backdrop-blur transition-all hover:bg-card hover:-translate-y-0.5"
          >
            <Icon name="chevronDown" className="h-3.5 w-3.5" />
            {pendingCount > 0 && (
              <span className="grid h-4 min-w-4 place-items-center rounded-full bg-brand px-1 font-mono text-[10px] font-bold text-brand-foreground">
                {pendingCount > 99 ? '99+' : pendingCount}
              </span>
            )}
            <span>回到最新</span>
          </button>
        )}
        {/* 工作空间 */}
        <div className="flex items-center gap-1.5 py-0.5">
          <Icon name="sparkle" className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
          {workspacePath ? (
            <span className="truncate text-[11px] text-muted-foreground">📁 {workspacePath}</span>
          ) : (
            <span className="text-[11px] text-muted-foreground/60">未设置工作目录</span>
          )}
        </div>
      </div>

      <Composer
        ref={composerRef}
        agent={agent}
        onSend={onSend}
        onCreateSkill={handleCreateSkill}
        isTyping={isTyping}
        onAbort={() => {
          const poolKey = sessionId && key ? `${sessionId}:${key}` : null
          if (poolKey) {
            const ws = getPoolWs(poolKey)
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'abort' }))
            }
          }
        }}
      />
    </div>
  )
}

// ── 空态：3 个 prompt 建议卡 + 提示语 ─────────────────────────────

export interface PromptCard {
  icon: string
  title: string
  desc: string
  onPick: string
}

/**
 * S1 私聊空态默认 3 张建议卡（与 docs/specs/04-commands §6.4.7 BDD 场景对齐）。
 *
 * 提为 top-level const（替代之前的 useMemo 包裹）— 数据完全静态，useMemo 空依赖等同 const，
 * 且 top-level 形式方便测试 (vitest) 直接 import 同一份数据，避免在测试里复制粘贴。
 *
 * 修改后务必同步：
 *   - 04-commands §6.4.7 (BDD spec)
 *   - __tests__/ChatView.suggestion.test.tsx (4 个 it 锁数据)
 */
// eslint-disable-next-line react-refresh/only-export-components
export const PROMPTS_DEFAULT: PromptCard[] = [
  { icon: '🔍', title: '帮我看看代码', desc: '打开项目后说"看看 src/"', onPick: '帮我看看当前项目的代码结构' },
  { icon: '🐛', title: '改个 bug', desc: '贴错误日志让它定位', onPick: '我遇到一个 bug，需要你帮我定位和修复' },
  { icon: '✨', title: '起一个新项目', desc: '从一句话需求到目录', onPick: '帮我从零开始一个新项目，先聊聊需求' },
]

/**
 * S1 私聊空态展示组件。
 *
 * onPick 接收每个 PromptCard 的 onPick 文本字段。
 * **注意**：调用方应直接走 send 链路（如 ChatView 的 onSend），不要只把文字塞进
 * composer input — 否则用户体感「点了没反应」（Day 2 gap #6）。
 *
 * 导出供 vitest 单测使用。
 */
export function EmptyChatState({
  agentName,
  prompts,
  onPick,
}: {
  agentName: string
  prompts: PromptCard[]
  onPick: (text: string) => void
}) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 py-12 text-center">
      <div>
        <div className="mb-2 inline-flex h-12 w-12 items-center justify-center rounded-2xl border bg-card text-2xl shadow-sm">
          ✨
        </div>
        <h3 className="text-[16px] font-medium text-foreground">和 {agentName} 开始对话</h3>
        <p className="mt-1 text-[12.5px] text-muted-foreground">挑一个起点，或者直接发你想聊的</p>
      </div>
      <div className="grid w-full max-w-2xl grid-cols-1 gap-2 sm:grid-cols-3">
        {prompts.map((p) => (
          <button
            key={p.title}
            type="button"
            data-testid={`prompt-card-${p.title}`}
            onClick={() => onPick(p.onPick)}
            className="group flex flex-col items-start gap-1.5 rounded-xl border bg-card/70 p-3.5 text-left transition-all hover:-translate-y-0.5 hover:border-brand/40 hover:bg-card hover:shadow-sm"
          >
            <span className="text-xl leading-none">{p.icon}</span>
            <span className="text-[13px] font-medium text-foreground">{p.title}</span>
            <span className="text-[11px] leading-snug text-muted-foreground">{p.desc}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
