import { create } from 'zustand'
import {
  conversations as mockConversations,
  messages as mockMessages,
  outputs as mockOutputs,
  stage as mockStage,
} from '../data/mock'
import { nowStamp, uid } from '../lib/id'
import type { ChatMessage, Conversation, OutputFile, StageTask, StageStatus } from '../types'

/** 会话键：agentId:conversationId */
export const convKey = (agentId: string, conversationId: string) => `${agentId}:${conversationId}`

const REPLIES = [
  'Got it. Reading through now — I’ll come back with a structured pass.',
  'On it. Will queue a new task in 阶段 so you can watch progress.',
  'Understood. Want me to flag open questions inline, or save them as a separate task?',
  'Drafting. Be back in ~30s.',
]

const NEXT_STAGE: Record<StageStatus, StageStatus> = { todo: 'doing', doing: 'done', done: 'todo' }

function seedMessages(): Record<string, ChatMessage[]> {
  const out: Record<string, ChatMessage[]> = {}
  for (const [agentId, byConv] of Object.entries(mockMessages)) {
    for (const [convId, list] of Object.entries(byConv)) {
      out[convKey(agentId, convId)] = list
    }
  }
  return out
}

interface ChatState {
  messages: Record<string, ChatMessage[]>
  conversations: Record<string, Conversation[]>
  typing: Record<string, boolean>
  stages: Record<string, StageTask[]>
  outputs: Record<string, OutputFile[]>

  send: (agentId: string, conversationId: string, text: string) => void
  addConversation: (agentId: string) => string
  toggleStage: (agentId: string, conversationId: string, taskId: string) => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: seedMessages(),
  conversations: { ...mockConversations },
  typing: {},
  stages: { [convKey('editor', 'c2')]: mockStage },
  outputs: { [convKey('editor', 'c2')]: mockOutputs },

  send: (agentId, conversationId, text) => {
    const key = convKey(agentId, conversationId)
    const userMsg: ChatMessage = { id: uid('u'), from: 'user', time: nowStamp(), text }
    set((s) => ({
      messages: { ...s.messages, [key]: [...(s.messages[key] ?? []), userMsg] },
      typing: { ...s.typing, [key]: true },
    }))

    window.setTimeout(() => {
      const reply = REPLIES[Math.floor(Math.random() * REPLIES.length)] ?? REPLIES[0]!
      const agentMsg: ChatMessage = { id: uid('a'), from: 'agent', time: nowStamp(), text: reply }
      set((s) => ({
        messages: { ...s.messages, [key]: [...(s.messages[key] ?? []), agentMsg] },
        typing: { ...s.typing, [key]: false },
      }))
    }, 1100)
  },

  addConversation: (agentId) => {
    const id = uid('c')
    const existing = get().conversations[agentId] ?? []
    const conv: Conversation = { id, name: `对话 ${existing.length + 1}`, subtitle: '刚刚开始' }
    set((s) => ({
      conversations: { ...s.conversations, [agentId]: [...existing, conv] },
    }))
    return id
  },

  toggleStage: (agentId, conversationId, taskId) => {
    const key = convKey(agentId, conversationId)
    set((s) => ({
      stages: {
        ...s.stages,
        [key]: (s.stages[key] ?? []).map((t) =>
          t.id === taskId ? { ...t, state: NEXT_STAGE[t.state] } : t,
        ),
      },
    }))
  },
}))
