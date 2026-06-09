import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { nowStamp, uid } from '../lib/id'
import type {
  ApprovalRequestData,
  Attachment,
  ChatMessage,
  Conversation,
  OutputFile,
  ReplyRef,
  StageTask,
  StageStatus,
  StreamEvent,
  TaskPlanData,
  ToolCallEntry,
  ToolResultEntry,
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
  addUserMessage: (key: string, text: string, attachment?: Attachment, replyTo?: ReplyRef) => void
  /** 应用一条服务端流式事件到对应消息桶 */
  applyStreamEvent: (key: string, event: StreamEvent) => void
  /** mock 降级：本地假回复（WS 未连接时用） */
  send: (
    agentId: string,
    conversationId: string,
    text: string,
    attachment?: Attachment,
    replyTo?: ReplyRef,
  ) => void
  addConversation: (agentId: string, opts?: { name?: string; workdir?: string }) => string
  toggleStage: (agentId: string, conversationId: string, taskId: string) => void
  /** 清掉某会话的未读数（用户切到该会话/回到消息流底部时调用） */
  clearUnread: (key: string) => void
  /** 整组合计未读（给 NavRail 红点用） */
  totalUnread: () => number
  /** 删除一个会话 */
  removeConversation: (agentId: string, conversationId: string) => void
  /** 批量删除会话 */
  removeConversations: (agentId: string, conversationIds: string[]) => void
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

      addUserMessage: (key, text, attachment, replyTo) => {
        const userMsg: ChatMessage = {
          id: uid('u'),
          from: 'user',
          time: nowStamp(),
          text,
          ...(attachment ? { attachment } : {}),
          ...(replyTo ? { replyTo } : {}),
        }
        set((s) => {
          const prev = s.messages[key] ?? []
          // 关闭还在流式的旧哨兵（防止新回复追加到旧消息上）
          const list = prev.map((m) => (m.streaming ? { ...m, id: uid('a'), streaming: false } : m))
          return {
            messages: { ...s.messages, [key]: [...list, userMsg] },
            typing: { ...s.typing, [key]: true },
          }
        })
      },

  removeConversation: (agentId, conversationId) => {
    const key = convKey(agentId, conversationId)
    // 关闭该会话的持久 WS 连接
    import("../hooks/wsPool").then(({ closePoolWs }) => {
      const sid = get().sessionIds[key]
      if (sid) closePoolWs(`${sid}:${key}`)
    })
    set((s) => {
      const existing = s.conversations[agentId] ?? []
      const filtered = existing.filter((c) => c.id !== conversationId)
      const nextConv = { ...s.conversations }
      if (filtered.length > 0) { nextConv[agentId] = filtered } else { delete nextConv[agentId] }
      const nextMsgs = { ...s.messages }; delete nextMsgs[key]
      const nextSessions = { ...s.sessionIds }; delete nextSessions[key]
      const nextTyping = { ...s.typing }; delete nextTyping[key]
      const nextUnread = { ...s.unreadByConv }; delete nextUnread[key]
      return { conversations: nextConv, messages: nextMsgs, sessionIds: nextSessions, typing: nextTyping, unreadByConv: nextUnread }
    })
  },

  removeConversations: (agentId, conversationIds) => {
    set((s) => {
      const existing = s.conversations[agentId] ?? []
      const filtered = existing.filter((c) => !new Set(conversationIds).has(c.id))
      const nextConv = { ...s.conversations }
      if (filtered.length > 0) { nextConv[agentId] = filtered } else { delete nextConv[agentId] }
      const nextMsgs = { ...s.messages }
      const nextSessions = { ...s.sessionIds }
      const nextTyping = { ...s.typing }
      const nextUnread = { ...s.unreadByConv }
      for (const cid of conversationIds) {
        const k = convKey(agentId, cid)
        delete nextMsgs[k]; delete nextSessions[k]; delete nextTyping[k]; delete nextUnread[k]
      }
      return { conversations: nextConv, messages: nextMsgs, sessionIds: nextSessions, typing: nextTyping, unreadByConv: nextUnread }
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
            if (!chunk) return {}
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
          // ── thinking：累积模型推理过程（ThinkingBlock 渲染）──
          if (event.type === 'thinking') {
            const chunk = event.content ?? ''
            const idx = list.findIndex((m) => m.id === streamingId(key))
            if (idx >= 0) {
              const cur = list[idx]!
              const next = [...list]
              next[idx] = { ...cur, thinking: (cur.thinking ?? '') + chunk }
              return {
                messages: { ...s.messages, [key]: next },
                typing: { ...s.typing, [key]: false },
              }
            }
            const seeded: ChatMessage = {
              id: streamingId(key),
              from: 'agent',
              time: nowStamp(),
              text: '',
              thinking: chunk,
              streaming: true,
            }
            return {
              messages: { ...s.messages, [key]: [...list, seeded] },
              typing: { ...s.typing, [key]: false },
              ...bumpUnread(),
            }
          }

          // ── tool_call：记录工具调用（ToolCallBlock 渲染）──
          if (event.type === 'tool_call') {
            const tc = event.tool_call
            if (!tc) return {}
            const entry: ToolCallEntry = {
              id: uid('tc'),
              callId: tc.call_id,
              name: tc.name,
              args: tc.arguments ?? {},
              status: 'pending',
            }
            // 文件修改类工具 → 通知 FilePreview 刷新
            if (/^(Write|Edit|Bash|write|edit|bash|write_to_file|replace_in_file)$/i.test(tc.name)) {
              queueMicrotask(() => window.dispatchEvent(new CustomEvent('file-changed')))
            }
            const idx = list.findIndex((m) => m.id === streamingId(key))
            if (idx >= 0) {
              const cur = list[idx]!
              const next = [...list]
              next[idx] = { ...cur, toolCalls: [...(cur.toolCalls ?? []), entry] }
              return {
                messages: { ...s.messages, [key]: next },
                typing: { ...s.typing, [key]: false },
              }
            }
            const seeded: ChatMessage = {
              id: streamingId(key),
              from: 'agent',
              time: nowStamp(),
              text: '',
              toolCalls: [entry],
              streaming: true,
            }
            return {
              messages: { ...s.messages, [key]: [...list, seeded] },
              typing: { ...s.typing, [key]: false },
              ...bumpUnread(),
            }
          }
          // ── tool_result：记录工具执行结果（ToolResultBlock 渲染）──
          if (event.type === 'tool_result') {
            const tr = event.tool_result
            if (!tr) return {}
            const resultEntry: ToolResultEntry = {
              id: uid('tr'),
              callId: tr.call_id,
              content: tr.content ?? tr.error ?? '',
              isError: !tr.success,
            }
            const idx = list.findIndex((m) => m.id === streamingId(key))
            if (idx >= 0) {
              const cur = list[idx]!
              // 更新匹配的 ToolCallEntry 状态
              const updatedCalls = (cur.toolCalls ?? []).map((c) =>
                c.callId === tr.call_id
                  ? { ...c, status: (tr.success ? 'success' : 'error') as 'success' | 'error' }
                  : c,
              )
              const next = [...list]
              next[idx] = {
                ...cur,
                toolCalls: updatedCalls,
                toolResults: [...(cur.toolResults ?? []), resultEntry],
              }
              return {
                messages: { ...s.messages, [key]: next },
                typing: { ...s.typing, [key]: false },
              }
            }
            const seeded: ChatMessage = {
              id: streamingId(key),
              from: 'agent',
              time: nowStamp(),
              text: '',
              toolResults: [resultEntry],
              streaming: true,
            }
            return {
              messages: { ...s.messages, [key]: [...list, seeded] },
              typing: { ...s.typing, [key]: false },
              ...bumpUnread(),
            }
          }

          // ── request_approval：审批请求卡（ApprovalRequestBlock 渲染）──
          if (event.type === 'request_approval') {
            const deniedOps = event.metadata?.denied_ops as unknown[]
            const desc =
              (event.content ?? '以下操作需要你的确认') +
              (deniedOps?.length ? `\n\n${JSON.stringify(deniedOps, null, 2)}` : '')
            const arData: ApprovalRequestData = {
              id: uid('ar'),
              action: 'approve_operations',
              description: desc,
              metadata: event.metadata ?? {},
              status: 'pending',
            }
            const idx = list.findIndex((m) => m.id === streamingId(key))
            if (idx >= 0) {
              const cur = list[idx]!
              const next = [...list]
              next[idx] = { ...cur, approvalRequest: arData }
              return {
                messages: { ...s.messages, [key]: next },
                typing: { ...s.typing, [key]: false },
              }
            }
            const seeded: ChatMessage = {
              id: streamingId(key),
              from: 'agent',
              time: nowStamp(),
              text: '',
              approvalRequest: arData,
              streaming: true,
            }
            return {
              messages: { ...s.messages, [key]: [...list, seeded] },
              typing: { ...s.typing, [key]: false },
              ...bumpUnread(),
            }
          }

          // ── task_plan：任务计划（TaskPlanBlock 渲染）──
          if (event.type === 'task_plan') {
            const tpData: TaskPlanData =
              event.task_plan ??
              (() => {
                try {
                  return event.content
                    ? JSON.parse(event.content)
                    : { summary: event.content ?? '', steps: [] }
                } catch {
                  return { summary: event.content ?? '', steps: [] }
                }
              })()
            const idx = list.findIndex((m) => m.id === streamingId(key))
            if (idx >= 0) {
              const cur = list[idx]!
              const next = [...list]
              next[idx] = { ...cur, taskPlan: tpData }
              return {
                messages: { ...s.messages, [key]: next },
                typing: { ...s.typing, [key]: false },
              }
            }
            const seeded: ChatMessage = {
              id: streamingId(key),
              from: 'agent',
              time: nowStamp(),
              text: '',
              taskPlan: tpData,
              streaming: true,
            }
            return {
              messages: { ...s.messages, [key]: [...list, seeded] },
              typing: { ...s.typing, [key]: false },
              ...bumpUnread(),
            }
          }

          // ── task_update：协调者任务进度更新（orchestrator 推送）──
          if (event.type === 'task_update') {
            const updateText = event.content ?? '任务进度更新'
            const idx = list.findIndex((m) => m.id === streamingId(key))
            if (idx >= 0) {
              const cur = list[idx]!
              const next = [...list]
              // 追加到 thinking 字段，让进度信息在 ThinkingBlock 中可见
              next[idx] = {
                ...cur,
                thinking: (cur.thinking ?? '') + '\n🔄 ' + updateText,
              }
              return {
                messages: { ...s.messages, [key]: next },
                typing: { ...s.typing, [key]: false },
              }
            }
            const seeded: ChatMessage = {
              id: streamingId(key),
              from: 'agent',
              time: nowStamp(),
              text: '',
              thinking: '🔄 ' + updateText,
              streaming: true,
            }
            return {
              messages: { ...s.messages, [key]: [...list, seeded] },
              typing: { ...s.typing, [key]: false },
              ...bumpUnread(),
            }
          }

          // 未知事件类型：静默忽略（forward-compat）
          return {}
        })
      },

      send: (agentId, conversationId, text, attachment, replyTo) => {
        const key = convKey(agentId, conversationId)
        const userMsg: ChatMessage = {
          id: uid('u'),
          from: 'user',
          time: nowStamp(),
          text,
          ...(attachment ? { attachment } : {}),
          ...(replyTo ? { replyTo } : {}),
        }
        set((s) => ({
          messages: { ...s.messages, [key]: [...(s.messages[key] ?? []), userMsg] },
          typing: { ...s.typing, [key]: true },
        }))

        window.setTimeout(() => {
          const reply = REPLIES[Math.floor(Math.random() * REPLIES.length)] ?? REPLIES[0]!
          const agentMsg: ChatMessage = {
            id: uid('a'),
            from: 'agent',
            time: nowStamp(),
            text: reply,
          }
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

      removeConversation: (agentId, conversationId) => {
        set((s) => {
          const existing = s.conversations[agentId] ?? []
          const filtered = existing.filter((c) => c.id !== conversationId)
          const next = { ...s.conversations }
          if (filtered.length > 0) {
            next[agentId] = filtered
          } else {
            delete next[agentId]
          }
          return { conversations: next }
        })
      },

      removeConversations: (agentId, conversationIds) => {
        const ids = new Set(conversationIds)
        set((s) => {
          const existing = s.conversations[agentId] ?? []
          const filtered = existing.filter((c) => !ids.has(c.id))
          const next = { ...s.conversations }
          if (filtered.length > 0) {
            next[agentId] = filtered
          } else {
            delete next[agentId]
          }
          return { conversations: next }
        })
      },

      setConversationPinned: (agentId, conversationId, pinned) => {
        set((s) => {
          const existing = s.conversations[agentId] ?? []
          const next = existing.map((c) => (c.id === conversationId ? { ...c, pinned } : c))
          return { conversations: { ...s.conversations, [agentId]: next } }
        })
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
