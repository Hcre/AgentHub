import { create } from 'zustand'
import { groupsApi, type CreateGroupInput } from '../api/groups'
import { sessionsApi, type MessageOut } from '../api/sessions'
import { nowStamp, uid } from '../lib/id'
import type { ApiGroup, ApprovalRequestData, Group, GroupMessage, ReplyRef, StreamEvent, TaskPlanData, ToolCallEntry, ToolResultEntry } from '../types'

export interface SendGroupOptions {
  requiresApproval?: boolean
  /** P1-1 群聊 reply/quote：被引用消息的最小快照（透传给后端 + 写回消息流）。 */
  replyTo?: ReplyRef
}

/** 流式哨兵 id 前缀；按 sender 区分多人独立聚合。 */
const streamingKey = (groupId: string, senderId: string) =>
  `__streaming__${groupId}:${senderId}`

/** 解析 @mention，返回被点名的名字列表（去掉 @）。 */
function parseMentions(text: string): string[] {
  return (text.match(/@(\S+)/g) ?? []).map((m) => m.slice(1))
}

/** 后端 ApiGroup → UI Group。 */
function toUiGroup(g: ApiGroup): Group {
  return {
    id: g.id,
    name: g.name,
    description: g.description,
    members: g.members.map((m) => m.id),
    coordinatorId: g.coordinator.id,
    coordinatorName: g.coordinator.name,
    coordinatorRole: g.coordinator.role,
  }
}

/** 后端 MessageOut → UI GroupMessage。 */
function toUiMessage(m: MessageOut): GroupMessage {
  const isUser = m.role === 'user'
  return {
    id: m.id,
    from: isUser ? 'user' : 'agent',
    who: isUser ? 'user' : (m.sender_agent_id ?? 'unknown'),
    time: m.created_at ? formatTime(m.created_at) : nowStamp(),
    text: m.content,
    mentions: m.mentions,
  }
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    return `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return nowStamp()
  }
}

interface GroupState {
  groups: Group[]
  messagesByGroup: Record<string, GroupMessage[]>
  /** groupId → 后端 Session id。 */
  sessionIdsByGroup: Record<string, string>
  /** 当前活跃群聊 WS 实例（sendGroup 取用；切群时整体替换）。 */
  ws: WebSocket | null
  /** WS 是否已建立连接。 */
  connected: boolean
  /** WS 未 OPEN 时入队的 JSON payload，按 groupId 隔离；onopen 后 flushPending 回放。 */
  pendingByGroup: Record<string, string[]>

  // CRUD
  fetchGroups: () => Promise<void>
  createGroup: (input: CreateGroupInput) => Promise<string>
  renameGroup: (id: string, name: string) => Promise<void>
  deleteGroup: (id: string) => Promise<void>

  // Session / 流式
  setGroupSession: (groupId: string, sessionId: string) => void
  loadGroupHistory: (groupId: string) => Promise<void>
  applyGroupStreamEvent: (groupId: string, event: StreamEvent) => void
  setWs: (ws: WebSocket | null) => void
  setConnected: (v: boolean) => void
  /** WS 刚 OPEN 时调用，把某个 group 的待发队列冲到当前 ws。 */
  flushPending: (groupId: string) => void

  // 发送
  sendGroup: (groupId: string, text: string, opts?: SendGroupOptions) => void
}

export const useGroupStore = create<GroupState>((set, get) => ({
  groups: [],
  messagesByGroup: {},
  sessionIdsByGroup: {},
  ws: null,
  connected: false,
  pendingByGroup: {},

  fetchGroups: async () => {
    try {
      const list = await groupsApi.list()
      set((s) => {
        const existing = new Set(s.groups.map((g) => g.id))
        const incoming = list.filter((g) => !existing.has(g.id)).map(toUiGroup)
        return { groups: [...s.groups, ...incoming] }
      })
    } catch {
      // 后端不可用 → 空列表（UI 由组件层兜底引导创建群组）
    }
  },

  createGroup: async (input) => {
    try {
      const created = await groupsApi.create(input)
      const group: Group = {
        ...toUiGroup(created),
        workdir: input.workdir,
      }
      set((s) => ({ groups: [...s.groups, group] }))
      return group.id
    } catch {
      const id = uid('grp')
      const group: Group = {
        id,
        name: input.name,
        description: input.description ?? '',
        members: input.member_ids ?? [],
        workdir: input.workdir,
      }
      set((s) => ({ groups: [...s.groups, group] }))
      return id
    }
  },

  renameGroup: async (id, name) => {
    const prev = get().groups
    set((s) => ({
      groups: s.groups.map((g) => (g.id === id ? { ...g, name } : g)),
    }))
    try {
      await groupsApi.rename(id, name)
    } catch {
      set({ groups: prev })
    }
  },

  deleteGroup: async (id) => {
    const prev = get().groups
    set((s) => ({
      groups: s.groups.filter((g) => g.id !== id),
      messagesByGroup: { ...s.messagesByGroup, [id]: [] },
    }))
    try {
      await groupsApi.remove(id)
    } catch {
      try {
        const list = await groupsApi.list()
        set({ groups: list.map(toUiGroup) })
      } catch {
        set({ groups: prev })
      }
    }
  },

  setGroupSession: (groupId, sessionId) =>
    set((s) => ({
      sessionIdsByGroup: { ...s.sessionIdsByGroup, [groupId]: sessionId },
    })),

  loadGroupHistory: async (groupId) => {
    const sid = get().sessionIdsByGroup[groupId]
    if (!sid) return
    try {
      const raw = await sessionsApi.messages(sid)
      const msgs = raw.map(toUiMessage)
      set((s) => ({
        messagesByGroup: { ...s.messagesByGroup, [groupId]: msgs },
      }))
    } catch {
      // 拉取失败 → 保留现有缓存
    }
  },

  applyGroupStreamEvent: (groupId, event) => {
    set((s) => {
      const list = s.messagesByGroup[groupId] ?? []
      const senderId = event.sender_agent_id ?? 'unknown'
      const sentinelId = streamingKey(groupId, senderId)

      if (event.type === 'text') {
        const chunk = event.content ?? ''
        if (!chunk) return {}
        const idx = list.findIndex((m) => m.id === sentinelId)
        if (idx >= 0) {
          const cur = list[idx]!
          const next = [...list]
          next[idx] = { ...cur, text: (cur.text ?? '') + chunk }
          return { messagesByGroup: { ...s.messagesByGroup, [groupId]: next } }
        }
        const seeded: GroupMessage = {
          id: sentinelId,
          from: 'agent',
          who: senderId,
          time: nowStamp(),
          text: chunk,
          streaming: true,
        }
        return {
          messagesByGroup: { ...s.messagesByGroup, [groupId]: [...list, seeded] },
        }
      }

      if (event.type === 'done') {
        const next = list.map((m) =>
          m.id === sentinelId ? { ...m, id: uid('gm'), streaming: false } : m,
        )
        return { messagesByGroup: { ...s.messagesByGroup, [groupId]: next } }
      }

      if (event.type === 'error') {
        const errMsg: GroupMessage = {
          id: uid('ge'),
          from: 'agent',
          who: senderId,
          time: nowStamp(),
          text: `⚠️ ${event.content ?? '执行出错'}`,
        }
        const next = list.filter((m) => m.id !== sentinelId).concat(errMsg)
        return { messagesByGroup: { ...s.messagesByGroup, [groupId]: next } }
      }

      // ── thinking：累积模型推理过程 ──
      if (event.type === 'thinking') {
        const chunk = event.content ?? ''
        const idx = list.findIndex((m) => m.id === sentinelId)
        if (idx >= 0) {
          const cur = list[idx]!
          const next = [...list]
          next[idx] = { ...cur, thinking: (cur.thinking ?? '') + chunk }
          return { messagesByGroup: { ...s.messagesByGroup, [groupId]: next } }
        }
        const seeded: GroupMessage = {
          id: sentinelId,
          from: 'agent',
          who: senderId,
          time: nowStamp(),
          thinking: chunk,
          streaming: true,
        }
        return { messagesByGroup: { ...s.messagesByGroup, [groupId]: [...list, seeded] } }
      }

      // ── tool_call：记录工具调用 ──
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
        const idx = list.findIndex((m) => m.id === sentinelId)
        if (idx >= 0) {
          const cur = list[idx]!
          const next = [...list]
          next[idx] = { ...cur, toolCalls: [...(cur.toolCalls ?? []), entry] }
          return { messagesByGroup: { ...s.messagesByGroup, [groupId]: next } }
        }
        const seeded: GroupMessage = {
          id: sentinelId,
          from: 'agent',
          who: senderId,
          time: nowStamp(),
          toolCalls: [entry],
          streaming: true,
        }
        return { messagesByGroup: { ...s.messagesByGroup, [groupId]: [...list, seeded] } }
      }

      // ── tool_result：记录工具执行结果 ──
      if (event.type === 'tool_result') {
        const tr = event.tool_result
        if (!tr) return {}
        const resultEntry: ToolResultEntry = {
          id: uid('tr'),
          callId: tr.call_id,
          content: tr.content ?? (tr.error ?? ''),
          isError: !tr.success,
        }
        const idx = list.findIndex((m) => m.id === sentinelId)
        if (idx >= 0) {
          const cur = list[idx]!
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
          return { messagesByGroup: { ...s.messagesByGroup, [groupId]: next } }
        }
        const seeded: GroupMessage = {
          id: sentinelId,
          from: 'agent',
          who: senderId,
          time: nowStamp(),
          toolResults: [resultEntry],
          streaming: true,
        }
        return { messagesByGroup: { ...s.messagesByGroup, [groupId]: [...list, seeded] } }
      }

      // ── request_approval：审批请求卡 ──
      if (event.type === 'request_approval') {
        const deniedOps = event.metadata?.denied_ops as unknown[]
        const desc = (event.content ?? '以下操作需要你的确认')
          + (deniedOps?.length ? `\n\n${JSON.stringify(deniedOps, null, 2)}` : '')
        const arData: ApprovalRequestData = {
          id: uid('ar'),
          action: 'approve_operations',
          description: desc,
          metadata: event.metadata ?? {},
          status: 'pending',
        }
        const idx = list.findIndex((m) => m.id === sentinelId)
        if (idx >= 0) {
          const cur = list[idx]!
          const next = [...list]
          next[idx] = { ...cur, approvalRequest: arData }
          return { messagesByGroup: { ...s.messagesByGroup, [groupId]: next } }
        }
        const seeded: GroupMessage = {
          id: sentinelId,
          from: 'agent',
          who: senderId,
          time: nowStamp(),
          approvalRequest: arData,
          streaming: true,
        }
        return { messagesByGroup: { ...s.messagesByGroup, [groupId]: [...list, seeded] } }
      }

      // ── task_plan：任务计划 ──
      if (event.type === 'task_plan') {
        const tpData: TaskPlanData = event.task_plan ?? (() => {
          try {
            return event.content ? JSON.parse(event.content) : { summary: event.content ?? '', steps: [] }
          } catch {
            return { summary: event.content ?? '', steps: [] }
          }
        })()
        const idx = list.findIndex((m) => m.id === sentinelId)
        if (idx >= 0) {
          const cur = list[idx]!
          const next = [...list]
          next[idx] = { ...cur, taskPlan: tpData }
          return { messagesByGroup: { ...s.messagesByGroup, [groupId]: next } }
        }
        const seeded: GroupMessage = {
          id: sentinelId,
          from: 'agent',
          who: senderId,
          time: nowStamp(),
          taskPlan: tpData,
          streaming: true,
        }
        return { messagesByGroup: { ...s.messagesByGroup, [groupId]: [...list, seeded] } }
      }

      // 未知事件类型：静默忽略（forward-compat）
      return {}
    })
  },

  setWs: (ws) => set({ ws }),
  setConnected: (v) => set({ connected: v }),

  flushPending: (groupId) => {
    const ws = get().ws
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    const queue = get().pendingByGroup[groupId] ?? []
    if (queue.length === 0) return
    for (const payload of queue) {
      try {
        ws.send(payload)
      } catch {
        // 单条发送失败：忽略，避免阻塞后续；用户可手动重发
      }
    }
    set((s) => ({
      pendingByGroup: { ...s.pendingByGroup, [groupId]: [] },
    }))
  },

  sendGroup: (groupId, text, opts) => {
    const mentions = parseMentions(text)
    const userMsg: GroupMessage = {
      id: uid('gu'),
      from: 'user',
      who: 'user',
      time: nowStamp(),
      text,
      mentions,
      requiresApproval: opts?.requiresApproval,
      ...(opts?.replyTo ? { replyTo: opts.replyTo } : {}),
    }
    set((s) => ({
      messagesByGroup: {
        ...s.messagesByGroup,
        [groupId]: [...(s.messagesByGroup[groupId] ?? []), userMsg],
      },
    }))

    const payload = JSON.stringify({
      type: 'message',
      content: text,
      mentions,
      dispatch_mode: 'auto',
      ...(opts?.replyTo ? { reply_to_id: opts.replyTo.id } : {}),
    })
    const ws = get().ws
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload)
      return
    }
    // WS 还在 CONNECTING / 切群瞬间 ws=null → 入队，等待 onopen flushPending
    set((s) => ({
      pendingByGroup: {
        ...s.pendingByGroup,
        [groupId]: [...(s.pendingByGroup[groupId] ?? []), payload],
      },
    }))
  },
}))
