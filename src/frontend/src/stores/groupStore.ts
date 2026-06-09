import { create } from 'zustand'
import { groupsApi, type CreateGroupInput } from '../api/groups'
import { sessionsApi, type MessageOut } from '../api/sessions'
import { nowStamp, uid } from '../lib/id'
import type { ApiGroup, ApprovalRequestData, CoordinatorPlan, DAGLivePlan, Group, GroupMessage, LivePlanStep, ReplyRef, StepStatus, StreamEvent, TaskPlanData, ToolCallEntry, ToolResultEntry } from '../types'

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
  /** task_plan + task_update 驱动的 live DAG 投影；null = 纯聊天。 */
  activePlanByGroup: Record<string, DAGLivePlan | null>

  // CRUD
  fetchGroups: () => Promise<void>
  createGroup: (input: CreateGroupInput) => Promise<string>
  renameGroup: (id: string, name: string) => Promise<void>
  deleteGroup: (id: string) => Promise<void>

  // Session / 流式
  setGroupSession: (groupId: string, sessionId: string) => void
  loadGroupHistory: (groupId: string) => Promise<void>
  applyGroupStreamEvent: (groupId: string, event: StreamEvent) => void
  /** 手动关闭某群的 live 任务卡（× 按钮）。 */
  dismissActivePlan: (groupId: string) => void
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
  activePlanByGroup: {},

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
        // 后台完整发言（worker 报到/交卷、协调者里程碑）：直接 append 独立完成消息，不走流式哨兵
        if (event.metadata?.final) {
          const finalMsg: GroupMessage = {
            id: uid('gm'), from: 'agent', who: senderId, time: nowStamp(), text: chunk,
          }
          return { messagesByGroup: { ...s.messagesByGroup, [groupId]: [...list, finalMsg] } }
        }
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
        if (/^(Write|Edit|Bash|write|edit|bash|write_to_file|replace_in_file)$/i.test(tc.name)) {
          queueMicrotask(() => window.dispatchEvent(new CustomEvent('file-changed')))
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

      // ── task_plan：任务计划 → message + activePlan ──
      if (event.type === 'task_plan') {
        const tpData: TaskPlanData = event.task_plan ?? (() => {
          try {
            return event.content ? JSON.parse(event.content) : { summary: event.content ?? '', steps: [] }
          } catch {
            return { summary: event.content ?? '', steps: [] }
          }
        })()
        // 从 metadata.plan 取 live steps（含 status）；fallback 到 task_plan.steps
        const rawSteps: LivePlanStep[] =
          (event.metadata?.plan as { steps?: LivePlanStep[] } | undefined)?.steps?.map(
            (s: LivePlanStep) => ({ ...s, status: s.status || 'pending' }),
          ) ??
          tpData.steps.map((s) => ({ ...s, who: s.id, status: 'pending' as StepStatus })) ??
          []
        const dagPlan: DAGLivePlan = { steps: rawSteps, coordinatorId: senderId }
        // 聊天内嵌用橙色「分发方案」卡（CoordinatorPlan），不用靛蓝 TaskPlanBlock
        const msgPlan: CoordinatorPlan = {
          summary: tpData.summary,
          steps: rawSteps.map((s) => ({
            id: s.id, who: s.who, label: s.label, eta: s.eta ?? 0, depends: s.depends,
          })),
          watchouts: [],
        }
        const idx = list.findIndex((m) => m.id === sentinelId)
        const seed = (m: Partial<GroupMessage>): GroupMessage => ({
          id: sentinelId, from: 'agent', who: senderId, time: nowStamp(),
          kind: 'plan', plan: msgPlan, streaming: true, ...m,
        })
        const msgs = idx >= 0
          ? (() => { const n = [...list]; n[idx] = { ...list[idx]!, kind: 'plan', plan: msgPlan }; return n })()
          : [...list, seed({})]
        return {
          messagesByGroup: { ...s.messagesByGroup, [groupId]: msgs },
          activePlanByGroup: { ...s.activePlanByGroup, [groupId]: dagPlan },
        }
      }

      // ── task_update：就地更新 step 状态 ──
      // 后端 _emit_update 发 running/done/failed，需映射到前端 StepStatus。
      if (event.type === 'task_update') {
        const taskId = event.metadata?.taskId as string | undefined
        const raw = event.metadata?.status as string | undefined
        const reason = event.metadata?.reason as string | undefined
        if (!taskId || !raw) return {}
        const STATUS_MAP: Record<string, StepStatus> = {
          pending: 'pending',
          queued: 'pending',
          running: 'running',
          done: 'completed',
          completed: 'completed',
          failed: 'failed',
          blocked: 'blocked',
        }
        const status = STATUS_MAP[raw]
        if (!status) return {}
        const cur = s.activePlanByGroup[groupId]
        if (!cur) return {}
        const nextSteps = cur.steps.map(
          (st): LivePlanStep => (st.id === taskId ? { ...st, status, reason: reason ?? st.reason } : st),
        )
        // 不自动清空：保留卡片让用户看到最终结果，新任务的 task_plan 会覆盖。
        return {
          activePlanByGroup: { ...s.activePlanByGroup, [groupId]: { ...cur, steps: nextSteps } },
        }
      }

      // ── task_activity：worker 实时活动 → 归到步骤 feed ──
      if (event.type === 'task_activity') {
        const taskId = event.metadata?.taskId as string | undefined
        const kind = event.metadata?.kind as string | undefined
        if (!taskId || !kind) return {}
        const cur = s.activePlanByGroup[groupId]
        if (!cur) return {}
        const nextSteps = cur.steps.map((st): LivePlanStep => {
          if (st.id !== taskId) return st
          const feed = [...(st.activity ?? [])]
          if (kind === 'text') {
            const text = (event.metadata?.text as string) ?? ''
            const last = feed[feed.length - 1]
            if (last && last.kind === 'text') {
              feed[feed.length - 1] = { ...last, text: (last.text ?? '') + text }
            } else {
              feed.push({ kind: 'text', text })
            }
          } else if (kind === 'tool_call') {
            feed.push({
              kind: 'tool',
              callId: event.metadata?.callId as string | undefined,
              name: event.metadata?.name as string | undefined,
            })
          } else if (kind === 'tool_result') {
            const callId = event.metadata?.callId as string | undefined
            const ok = event.metadata?.ok as boolean | undefined
            const idx = feed.findIndex((a) => a.kind === 'tool' && a.callId === callId)
            if (idx >= 0) feed[idx] = { ...feed[idx]!, ok }
          }
          return { ...st, activity: feed }
        })
        return {
          activePlanByGroup: { ...s.activePlanByGroup, [groupId]: { ...cur, steps: nextSteps } },
        }
      }

      // ── task_update：协调者任务进度更新（orchestrator 推送）──
      if (event.type === 'task_update') {
        const updateText = event.content ?? '任务进度更新'
        const idx = list.findIndex((m) => m.id === sentinelId)
        if (idx >= 0) {
          const cur = list[idx]!
          const next = [...list]
          next[idx] = {
            ...cur,
            thinking: (cur.thinking ?? '') + '\n🔄 ' + updateText,
          }
          return { messagesByGroup: { ...s.messagesByGroup, [groupId]: next } }
        }
        const seeded: GroupMessage = {
          id: sentinelId,
          from: 'agent',
          who: senderId,
          time: nowStamp(),
          thinking: '🔄 ' + updateText,
          streaming: true,
        }
        return { messagesByGroup: { ...s.messagesByGroup, [groupId]: [...list, seeded] } }
      }

      // 未知事件类型：静默忽略（forward-compat）
      return {}
    })
  },

  dismissActivePlan: (groupId) =>
    set((s) => ({ activePlanByGroup: { ...s.activePlanByGroup, [groupId]: null } })),

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
