import { create } from 'zustand'
import { persist } from 'zustand/middleware'
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

/** 按会话键生成流式哨兵 id，防止多轮并发时哨兵碰撞（群聊已采用同名空间隔离模式） */
const streamingId = (key: string) => `__streaming__:${key}`

const REPLIES = [
  'Got it. Reading through now — I’ll come back with a structured pass.',
  'On it. Will queue a new task in 阶段 so you can watch progress.',
  'Understood. Want me to flag open questions inline, or save them as a separate task?',
  'Drafting. Be back in ~30s.',
]

const NEXT_STAGE: Record<StageStatus, StageStatus> = { todo: 'doing', doing: 'done', done: 'todo' }

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
  /** convKey → 该会话未读消息数（用户切到该会话/回到底部时清零） */
  unreadByConv: Record<string, number>

  setConnected: (v: boolean) => void
  setSessionId: (key: string, sessionId: string) => void
  /** 本地回显用户气泡（WS 发送时由 hook 调用） */
  addUserMessage: (key: string, text: string) => void
  /** 应用一条服务端流式事件到对应消息桶 */
  applyStreamEvent: (key: string, event: StreamEvent) => void
  /** mock 降级：本地假回复（WS 未连接时用） */
  send: (agentId: string, conversationId: string, text: string) => void
  addConversation: (
    agentId: string,
    opts?: { name?: string; workdir?: string },
  ) => string
  toggleStage: (agentId: string, conversationId: string, taskId: string) => void
  /** 清掉某会话的未读数（用户切到该会话/回到消息流底部时调用） */
  clearUnread: (key: string) => void
  /** 整组合计未读（给 NavRail 红点用） */
  totalUnread: () => number
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
  messages: {},
  conversations: {},
  typing: {},
  stages: {},
  outputs: {},
  sessionIds: {},
  connected: false,
  unreadByConv: {},

  setConnected: (v) => set({ connected: v }),

  setSessionId: (key, sessionId) =>
    set((s) => ({ sessionIds: { ...s.sessionIds, [key]: sessionId } })),

  addUserMessage: (key, text) => {
    const userMsg: ChatMessage = { id: uid('u'), from: 'user', time: nowStamp(), text }
    set((s) => {
      const prev = s.messages[key] ?? []
      // 关闭还在流式的旧哨兵（防止新回复追加到旧消息上）
      const list = prev.map((m) =>
        m.streaming ? { ...m, id: uid('a'), streaming: false } : m,
      )
      return {
        messages: { ...s.messages, [key]: [...list, userMsg] },
        typing: { ...s.typing, [key]: true },
      }
    })
  },

  applyStreamEvent: (key, event) => {
    set((s) => {
      const list = s.messages[key] ?? []
      // 新流式 agent 消息到来 → 未读 +1（ChatView 切到该 conv 会 clearUnread）
      const bumpUnread = () => ({
        unreadByConv: { ...s.unreadByConv, [key]: (s.unreadByConv[key] ?? 0) + 1 },
      })
      if (event.type === 'text') {
        const chunk = event.content ?? ''
        const idx = list.findIndex((m) => m.id === streamingId(key))
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
          id: streamingId(key),
          from: 'agent',
          time: nowStamp(),
          text: chunk,
          streaming: true,
        }
        return {
          messages: { ...s.messages, [key]: [...list, seeded] },
          typing: { ...s.typing, [key]: false },
          ...bumpUnread(),
        }
      }
      if (event.type === 'done') {
        const next = list.map((m) =>
          m.id === streamingId(key) ? { ...m, id: uid('a'), streaming: false } : m,
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
        const next = list.filter((m) => m.id !== streamingId(key)).concat(errMsg)
        return {
          messages: { ...s.messages, [key]: next },
          typing: { ...s.typing, [key]: false },
          ...bumpUnread(),
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
        // mock 假回复也算未读
        unreadByConv: { ...s.unreadByConv, [key]: (s.unreadByConv[key] ?? 0) + 1 },
      }))
    }, 1100)
  },

  addConversation: (agentId, opts) => {
    const id = uid('c')
    const existing = get().conversations[agentId] ?? []
    const trimmedName = opts?.name?.trim()
    const trimmedWorkdir = opts?.workdir?.trim()
    const conv: Conversation = {
      id,
      name: trimmedName || `对话 ${existing.length + 1}`,
      subtitle: '刚刚开始',
      workdir: trimmedWorkdir || undefined,
    }
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

  clearUnread: (key) =>
    set((s) => {
      if (!s.unreadByConv[key]) return s
      const next = { ...s.unreadByConv }
      delete next[key]
      return { unreadByConv: next }
    }),

  totalUnread: () => {
    const m = get().unreadByConv
    return Object.values(m).reduce((a, b) => a + b, 0)
  },
}),
    {
      name: 'agenthub-chat',
      partialize: (state) => ({
        messages: state.messages,
        conversations: state.conversations,
        sessionIds: state.sessionIds,
      }),
    },
  ),
)
