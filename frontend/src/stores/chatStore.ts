import { create } from 'zustand'
import {
  conversations as mockConversations,
  messages as mockMessages,
  outputs as mockOutputs,
  stage as mockStage,
} from '../data/mock'
import { nowStamp, uid } from '../lib/id'
import type {
  ChatMessage,
  Conversation,
  OutputFile,
  StageTask,
  StageStatus,
  StreamEvent,
} from '../types'

/** 会话键：agentId:conversationId */
export const convKey = (agentId: string, conversationId: string) => `${agentId}:${conversationId}`

/** 流式增量哨兵消息 id；done 时替换为正式 id。 */
const STREAMING_ID = '__streaming__'

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
  /** convKey → 后端 Session id */
  sessionIds: Record<string, string>
  /** 当前 WS 是否已连接 */
  connected: boolean

  setConnected: (v: boolean) => void
  setSessionId: (key: string, sessionId: string) => void
  /** 本地回显用户气泡（WS 发送时由 hook 调用） */
  addUserMessage: (key: string, text: string) => void
  /** 应用一条服务端流式事件到对应消息桶 */
  applyStreamEvent: (key: string, event: StreamEvent) => void
  /** mock 降级：本地假回复（WS 未连接时用） */
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
  sessionIds: {},
  connected: false,

  setConnected: (v) => set({ connected: v }),

  setSessionId: (key, sessionId) =>
    set((s) => ({ sessionIds: { ...s.sessionIds, [key]: sessionId } })),

  addUserMessage: (key, text) => {
    const userMsg: ChatMessage = { id: uid('u'), from: 'user', time: nowStamp(), text }
    set((s) => ({
      messages: { ...s.messages, [key]: [...(s.messages[key] ?? []), userMsg] },
      typing: { ...s.typing, [key]: true },
    }))
  },

  applyStreamEvent: (key, event) => {
    set((s) => {
      const list = s.messages[key] ?? []
      if (event.type === 'text') {
        const chunk = event.content ?? ''
        const idx = list.findIndex((m) => m.id === STREAMING_ID)
        if (idx >= 0) {
          const cur = list[idx]!
          const next = [...list]
          next[idx] = { ...cur, text: cur.text + chunk }
          return {
            messages: { ...s.messages, [key]: next },
            typing: { ...s.typing, [key]: false },
          }
        }
        const seeded: ChatMessage = {
          id: STREAMING_ID,
          from: 'agent',
          time: nowStamp(),
          text: chunk,
          streaming: true,
        }
        return {
          messages: { ...s.messages, [key]: [...list, seeded] },
          typing: { ...s.typing, [key]: false },
        }
      }
      if (event.type === 'done') {
        const next = list.map((m) =>
          m.id === STREAMING_ID ? { ...m, id: uid('a'), streaming: false } : m,
        )
        return {
          messages: { ...s.messages, [key]: next },
          typing: { ...s.typing, [key]: false },
        }
      }
      if (event.type === 'error') {
        const errMsg: ChatMessage = {
          id: uid('e'),
          from: 'agent',
          time: nowStamp(),
          text: `⚠️ ${event.content ?? '执行出错'}`,
        }
        const next = list.filter((m) => m.id !== STREAMING_ID).concat(errMsg)
        return {
          messages: { ...s.messages, [key]: next },
          typing: { ...s.typing, [key]: false },
        }
      }
      // thinking / tool_* / task_plan / request_approval：MVP 暂不渲染
      return {}
    })
  },

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
