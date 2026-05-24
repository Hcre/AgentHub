import { useEffect, useRef, useState } from 'react'
import { user } from '../../data/mock'
import { convKey, useChatStore } from '../../stores/chatStore'
import { useUIStore } from '../../stores/uiStore'
import { sessionsApi } from '../../api/sessions'
import { useWebSocket } from '../../hooks/useWebSocket'
import { Composer } from './Composer'
import { ConversationTabs } from './ConversationTabs'
import { MessageBubble } from './MessageBubble'
import { TypingIndicator } from './TypingIndicator'
import type { Agent } from '../../types'

export function ChatView({ agent }: { agent: Agent }) {
  const activeConversationId = useUIStore((s) => s.activeConversationId)
  const openConversation = useUIStore((s) => s.openConversation)
  const conversations = useChatStore((s) => s.conversations)
  const messages = useChatStore((s) => s.messages)
  const typing = useChatStore((s) => s.typing)
  const send = useChatStore((s) => s.send)
  const addConversation = useChatStore((s) => s.addConversation)
  const sessionIds = useChatStore((s) => s.sessionIds)
  const setSessionId = useChatStore((s) => s.setSessionId)
  const [historyOpen, setHistoryOpen] = useState(true)
  const bottomRef = useRef<HTMLDivElement>(null)

  const convs = conversations[agent.id] ?? []
  const key = activeConversationId ? convKey(agent.id, activeConversationId) : null
  const list = key ? (messages[key] ?? []) : []
  const isTyping = key ? (typing[key] ?? false) : false
  const sessionId = key ? (sessionIds[key] ?? null) : null

  // 首次进入会话：创建后端 Session。失败（mock agent / 后端不可用）则维持 mock 降级。
  useEffect(() => {
    if (!key || sessionId) return
    let cancelled = false
    sessionsApi
      .createPrivate(agent.id)
      .then((s) => {
        if (!cancelled) setSessionId(key, s.id)
      })
      .catch(() => {
        // mock agent（非 UUID id）或后端不可用 → 保持 mock 假对话
      })
    return () => {
      cancelled = true
    }
  }, [key, sessionId, agent.id, setSessionId])

  const { sendMessage } = useWebSocket(sessionId, key)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [list.length, isTyping])

  const onNew = () => {
    const id = addConversation(agent.id)
    openConversation(agent.id, id)
  }

  const onSend = (text: string) => {
    if (!activeConversationId) return
    // 优先走真实 WS；未连接（mock agent / 后端不可用）则降级假回复
    if (!sendMessage(text)) send(agent.id, activeConversationId, text)
  }

  return (
    <div className="flex h-full flex-col">
      <ConversationTabs
        convs={convs}
        activeId={activeConversationId}
        open={historyOpen}
        onPick={(id) => openConversation(agent.id, id)}
        onToggle={() => setHistoryOpen((v) => !v)}
        onNew={onNew}
      />

      <div className="flex-1 overflow-y-auto px-4 py-5">
        <div className="ah-msgs mx-auto flex max-w-3xl flex-col gap-5">
          {list.map((m) => (
            <MessageBubble key={m.id} msg={m} agent={agent} user={user} />
          ))}
          {isTyping && <TypingIndicator agent={agent} />}
          <div ref={bottomRef} />
        </div>
      </div>

      <Composer agent={agent} onSend={onSend} />
    </div>
  )
}
