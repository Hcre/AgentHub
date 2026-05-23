import { useEffect, useRef, useState } from 'react'
import { user } from '../../data/mock'
import { convKey, useChatStore } from '../../stores/chatStore'
import { useUIStore } from '../../stores/uiStore'
import { Composer } from './Composer'
import { ConversationTabs } from './ConversationTabs'
import { MessageBubble } from './MessageBubble'
import { TypingIndicator } from './TypingIndicator'
import type { Agent } from '../../types'

export function ChatView({ agent }: { agent: Agent }) {
  const activeConversationId = useUIStore((s) => s.activeConversationId)
  const openConversation = useUIStore((s) => s.openConversation)
  const { conversations, messages, typing, send, addConversation } = useChatStore()
  const [historyOpen, setHistoryOpen] = useState(true)
  const bottomRef = useRef<HTMLDivElement>(null)

  const convs = conversations[agent.id] ?? []
  const key = activeConversationId ? convKey(agent.id, activeConversationId) : null
  const list = key ? (messages[key] ?? []) : []
  const isTyping = key ? (typing[key] ?? false) : false

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [list.length, isTyping])

  const onNew = () => {
    const id = addConversation(agent.id)
    openConversation(agent.id, id)
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
        <div className="mx-auto flex max-w-3xl flex-col gap-5">
          {list.map((m) => (
            <MessageBubble key={m.id} msg={m} agent={agent} user={user} />
          ))}
          {isTyping && <TypingIndicator agent={agent} />}
          <div ref={bottomRef} />
        </div>
      </div>

      <Composer
        agent={agent}
        onSend={(text) => activeConversationId && send(agent.id, activeConversationId, text)}
      />
    </div>
  )
}
