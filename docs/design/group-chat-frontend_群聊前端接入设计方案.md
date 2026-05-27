# 群聊前端接入设计方案

> 状态：设计阶段 | 日期：2026-05-26
>
> 依赖：
> - `docs/design/group-chat-implementation-plan_群聊实施计划.md` — Phase 8 前端部分
> - 前端审查 worklog `2026-05-26_frontend-review-group-chat.md` — 逐项验证结论

## 一、现状总结

群聊前端 UI 骨架完整（气泡、@mention、方案卡、成员条），**但数据通道全部走 mock**。

| 链路 | 问题 |
|------|------|
| 发送 | `sendGroup` → `setTimeout` → `simulateGroupReply`，不调后端 API/WS |
| 接收 | 无群聊 WS hook，`useWebSocket.ts` 写死路由到 `chatStore`（私聊） |
| 历史 | `messagesByGroup` 初始值 = mock seed |
| Session | 无 group→session 映射 |
| Actor 查找 | `lookupActor` 查本地 mock agents，真实 UUID 匹配不到 |

目标：删除全部 mock seam，接入真实后端 `/ws/sessions/{sid}`。

---

## 二、数据流架构

```
用户 "@AgentA 帮我看看"
  │
  ▼ GroupComposer.onSend(text)
  │
  ├─ groupStore.sendGroup(groupId, text)
  │   ├─ parseMentions → ["AgentA"]
  │   ├─ 本地回显用户气泡（messagesByGroup[groupId] append）
  │   └─ WS send {type:"message", content, mentions:["AgentA"]}
  │
  ▼ /ws/sessions/{session_id}
  │
  │  后端 ChatService.send_and_stream → Agent 执行 → StreamEvent 逐个推送
  │
  ▼ useGroupWebSocket.onmessage
  │
  └─ groupStore.applyGroupStreamEvent(groupId, event)
      ├─ type='text'   → 找/建哨兵消息，累加 content
      ├─ type='done'   → 哨兵替换为正式 id，streaming: false
      └─ type='error'  → 哨兵移除，追加 error 消息
```

### 与私聊 ChatView 的对比

| | 私聊 | 群聊 |
|---|---|---|
| 消息桶 key | `agentId:convId` | `groupId` |
| Session 创建 | `createPrivate(agentId)` | `createGroup(groupId)` |
| WS hook | `useWebSocket(sid, convKey)` | `useGroupWebSocket(gid, sid)` |
| 流式聚合 key | `convKey`（单人） | `groupId:sender_agent_id`（多人） |
| 发送格式 | `{type:"message", content}` | `{type:"message", content, mentions}` |
| Actor 来源 | `agent` prop 固定 | `agentStore.agents` 按 UUID 查 |

---

## 三、详细设计

### 3.1 API 层（2 个文件）

#### `api/sessions.ts` — 加 `createGroup`

```ts
createGroup: (groupId: string, title = "") =>
  api.post<Session>("/api/sessions", {
    type: "group",
    group_id: groupId,
    title,
  }),
```

`MessageOut` 补后端字段：

```ts
interface MessageOut {
  id: string
  role: string
  content: string
  content_type: string
  sender_agent_id?: string | null   // 新增
  created_at?: string               // 新增
}
```

> 后端 `schemas/session.py` 的 `MessageOut` 需同步加 `sender_agent_id` + `created_at`。

#### `api/groups.ts` — 加 `findOrCreateSession`

双调用策略：先 GET `/api/sessions` 找已有，找不到再 POST 创建。若后端先加了 `group_id` query 参数则直接传。

```ts
findOrCreateSession: async (groupId: string): Promise<Session> => {
  const all = await sessionsApi.list()
  const hit = all.find((s) => s.group_id === groupId && s.type === "group")
  if (hit) return hit
  return sessionsApi.createGroup(groupId)
},
```

---

### 3.2 Store 层 — `groupStore.ts`

#### 新增状态

```ts
sessionIdsByGroup: Record<string, string>        // groupId → sessionId
_wsRef: { current: WebSocket | null }            // 供 sendGroup 取 WS 实例
connected: boolean
```

#### 新增 action

**`setGroupSession(groupId, sessionId)`** — 写入映射。

**`loadGroupHistory(groupId)`** — GET `/api/sessions/{sid}/messages` → 转 `GroupMessage[]` 写入 `messagesByGroup[groupId]`。`who` 从 `sender_agent_id` 取，缺失时 fallback `'unknown'`。

**`applyGroupStreamEvent(groupId, event)`** — 核心流式聚合逻辑：

| event.type | 行为 |
|-----------|------|
| `text` | 按 `groupId:sender_agent_id` 找哨兵消息 → 累加 content；无哨兵则新建，`streaming: true` |
| `done` | 哨兵消息 → 替换正式 id + `streaming: false` |
| `error` | 删除哨兵 → 追加 error 消息 |
| `thinking` / `tool_*` 等 | MVP 忽略 |

哨兵 key 用 `__streaming__{groupId}:{senderId}`，确保不同发言人独立聚合。

**`setConnected(v)`** — WS 连接状态。

#### 改造 `sendGroup`

```ts
sendGroup: (groupId, text, opts) => {
  const mentions = parseMentions(text)
  // 1. 本地回显
  set(s => ({ messagesByGroup: { ...s.messagesByGroup, [groupId]: [..., userMsg] } }))
  // 2. WS 发送
  const ws = get()._wsRef?.current
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "message", content: text, mentions }))
  }
}
```

#### 删除

- `simulateGroupReply` 整个函数
- `import { agents } from '../data/mock'`
- `import { coordinator, groupMessages, groups } from '../data/groups'`
- 初值：`groups: []`、`messagesByGroup: {}`

---

### 3.3 Hook 层 — `useGroupWebSocket.ts`（新建）

复用 `useWebSocket` 的骨架（指数退避重连、WS 生命周期），差异化：

- `onmessage` → `groupStore.applyGroupStreamEvent(groupId, event)`
- `wsRef` 写入 `groupStore._wsRef`，供 `sendGroup` 取用
- 不依赖 `chatStore` 和 `convKey`

```ts
export function useGroupWebSocket(groupId: string, sessionId: string | null) {
  const wsRef = useRef<WebSocket | null>(null)
  const gidRef = useRef(groupId)
  useEffect(() => { gidRef.current = groupId }, [groupId])

  const apply = useGroupStore(s => s.applyGroupStreamEvent)
  const setConnected = useGroupStore(s => s.setConnected)

  useEffect(() => {
    if (!sessionId) return
    let closed = false, attempts = 0, timer: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      const ws = new WebSocket(`${WS_BASE}/ws/sessions/${sessionId}`)
      wsRef.current = ws
      useGroupStore.getState()._setWsRef({ current: ws })

      ws.onopen = () => { setConnected(true); attempts = 0 }
      ws.onclose = () => {
        setConnected(false)
        if (closed) return
        timer = setTimeout(connect, Math.min(1000 * 2 ** attempts++, 10000))
      }
      ws.onmessage = (e) => {
        try { apply(gidRef.current, JSON.parse(e.data)) } catch {}
      }
    }

    connect()
    return () => {
      closed = true
      if (timer) clearTimeout(timer)
      wsRef.current?.close()
      useGroupStore.getState()._setWsRef({ current: null })
    }
  }, [sessionId])

  return { wsRef }
}
```

---

### 3.4 组件层（3 个文件）

#### `actors.ts` — 重构 `lookupActor`

```ts
import { useAgentStore } from '../../stores/agentStore'
import { useGroupStore } from '../../stores/groupStore'
import type { AgentColor } from '../../types'

export interface Actor {
  name: string
  color: AgentColor
  initial: string
  online?: boolean
}

const COLORS: AgentColor[] = ['brand', 'sage', 'clay', 'rose', 'blue']

export function lookupActor(who: string, groupId?: string): Actor {
  if (who === 'user') return { name: '你', color: 'neutral', initial: '你' }

  const { agents } = useAgentStore.getState()

  // 1. 查 agentStore
  const a = agents.find(x => x.id === who)
  if (a) return { name: a.name, color: a.color, initial: a.name[0] ?? '?', online: a.online }

  // 2. 查协调者
  if (groupId) {
    const { groups } = useGroupStore.getState()
    const g = groups.find(x => x.id === groupId)
    if (g?.coordinatorId === who) {
      const c = agents.find(x => x.id === who)
      return {
        name: c?.name ?? '协调者',
        color: c?.color ?? 'brand',
        initial: c?.name?.[0] ?? '协',
        online: c?.online,
      }
    }
  }

  // 3. fallback
  const short = who.slice(0, 8)
  return {
    name: short,
    color: COLORS[who.length % COLORS.length] ?? 'neutral',
    initial: short[0] ?? '?',
  }
}
```

**关键变更**: 移除 `import { agents } from '../../data/mock'` 和 `import { coordinator } from '../../data/groups'`。数据源切换为 `agentStore.agents`（App 启动时 `loadAgents()` 已填充）。

需要 `groupId` 参数来查协调者。所有调用点（`GroupMessageItem`、`GroupMembersStrip`、`CoordinatorPlan`、`GroupChatView` tasks tab）需传入 `group.id`。

#### `GroupComposer.tsx` — 改 mentionables 数据源

移除 `import { agents } from '../../data/mock'` 和 `import { coordinator } from '../../data/groups'`。改为：

```ts
const agents = useAgentStore(s => s.agents)

const mentionables = useMemo(() => {
  const list: Mentionable[] = []
  if (group.coordinatorId) {
    const c = agents.find(a => a.id === group.coordinatorId)
    list.push({ id: group.coordinatorId, name: c?.name ?? '协调者', hint: '拆分并分发任务' })
  }
  for (const id of group.members) {
    const a = agents.find(x => x.id === id)
    list.push({ id, name: a?.name ?? id, hint: a?.role ?? '' })
  }
  return list
}, [agents, group.members, group.coordinatorId])
```

#### `GroupChatView.tsx` — 生命周期接入

在现有渲染逻辑前加入三个 effect：

```tsx
const { sessionIdsByGroup, setGroupSession, loadGroupHistory } = useGroupStore()
const sessionId = activeGroupId ? (sessionIdsByGroup[activeGroupId] ?? null) : null

// 1. 获取或创建 session
useEffect(() => {
  if (!activeGroupId || sessionId) return
  let cancelled = false
  groupsApi.findOrCreateSession(activeGroupId).then(s => {
    if (!cancelled) setGroupSession(activeGroupId, s.id)
  }).catch(() => { /* 后端不可用，保持 mock 降级 */ })
  return () => { cancelled = true }
}, [activeGroupId, sessionId])

// 2. session 就绪后拉历史
useEffect(() => {
  if (!activeGroupId || !sessionId) return
  loadGroupHistory(activeGroupId)
}, [activeGroupId, sessionId])

// 3. attach WS
useGroupWebSocket(activeGroupId ?? '', sessionId)
```

---

### 3.5 类型层 — `types/index.ts`

#### `GroupMessage` 补字段

```ts
export interface GroupMessage {
  id: string
  from: 'user' | 'agent'
  who: string
  time: string
  text?: string
  kind?: 'plan'
  plan?: CoordinatorPlan
  requiresApproval?: boolean
  streaming?: boolean    // 新增：流式中 UI 显示打字光标
  mentions?: string[]    // 新增：用户消息的 @mention 列表
}
```

#### `Group` 加 `coordinatorId`

```ts
export interface Group {
  id: string
  name: string
  description: string
  members: string[]
  coordinatorId?: string   // 新增：来自 ApiGroup.coordinator.id
  pinnedTask?: string
}
```

`groupStore.toUiGroup` 同步：

```ts
function toUiGroup(g: ApiGroup): Group {
  return {
    id: g.id,
    name: g.name,
    description: g.description,
    members: g.members.map(m => m.id),
    coordinatorId: g.coordinator.id,
  }
}
```

#### `Coordinator` 类型

保留不改。但不再作为硬编码字符串 `'coordinator'` 使用。协调者的 `id` 在后端是普通 UUID agent，前端通过 `group.coordinatorId` 找到。

---

### 3.6 流式 UI — `GroupMessageItem.tsx`

`msg.streaming === true` 时在文本末尾渲染闪烁光标：

```tsx
{msg.text && (
  <div className="text-[14px] leading-[1.6] [text-wrap:pretty]">
    {/* 现有 renderRichText 段落渲染 */}
    {msg.streaming && (
      <span className="inline-block w-2 h-4 ml-0.5 bg-foreground/60 animate-pulse align-text-bottom" />
    )}
  </div>
)}
```

---

## 四、后端需同步的改动

| 改动 | 位置 | 优先级 |
|------|------|--------|
| `MessageOut` 加 `sender_agent_id` | `schemas/session.py` | **必须** |
| `MessageOut` 加 `created_at` | `schemas/session.py` | 建议 |
| `GET /api/sessions?group_id=X` | `routers/sessions.py` + `session_service.py` | 可选 |

不改后端的话：历史消息 `who` fallback `'unknown'`（灰色默认头像）、`time` 用当前时间（刷新后时间跳跃）、session 用双调用（多一次 HTTP 往返，忽略不计）。

---

## 五、实施顺序

按依赖排列：

| # | 文件 | 改动 | 估时 | 依赖 |
|---|------|------|------|------|
| 1 | `types/index.ts` | GroupMessage 加 `streaming`/`mentions`；Group 加 `coordinatorId` | 0.25h | — |
| 2 | `api/sessions.ts` | 加 `createGroup`；`MessageOut` 加字段 | 0.25h | — |
| 3 | `api/groups.ts` | 加 `findOrCreateSession` | 0.5h | 2 |
| 4 | `stores/groupStore.ts` | 加字段 + 3 action + 改造 sendGroup + 删 MOCK SEAM | 2.5h | 1, 3 |
| 5 | `hooks/useGroupWebSocket.ts` | **新建** | 1.5h | 4 |
| 6 | `components/group/actors.ts` | 重构 lookupActor | 1h | 1, 4 |
| 7 | `components/group/GroupComposer.tsx` | 改 mentionables | 0.5h | 6 |
| 8 | `components/group/GroupChatView.tsx` | 加生命周期 | 0.5h | 4, 5 |
| 9 | `components/group/GroupMessageItem.tsx` | 加流式光标 | 0.25h | 1 |

**总估时：~7h**（不含后端修改）

并行策略：1+2 并行 → 3+4+5 并行 → 6+7+8+9 顺序推进。

---

## 六、降级行为

| 场景 | 行为 |
|------|------|
| 后端不可用 | `findOrCreateSession` catch → 无 session；`sendGroup` 只做本地回显 |
| WS 断开 | 指数退避重连（1s→2s→4s→...→10s max） |
| `sender_agent_id` 为 null | fallback `who = 'system'` |
| `agentStore.agents` 为空 | `lookupActor` fallback UUID 前 8 位 + 颜色循环 |
| 历史消息无 `sender_agent_id` | `who = 'unknown'`，灰色默认头像 |
