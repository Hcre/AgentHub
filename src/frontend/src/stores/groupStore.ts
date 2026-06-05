import { create } from 'zustand'
import { groupsApi, type CreateGroupInput } from '../api/groups'
import { sessionsApi, type MessageOut } from '../api/sessions'
import { nowStamp, uid } from '../lib/id'
import type { ApiGroup, Group, GroupMessage, StreamEvent } from '../types'

export interface SendGroupOptions {
  requiresApproval?: boolean
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

      // thinking / tool_* / request_approval / task_plan：MVP 不渲染
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
