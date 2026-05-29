# 群聊前端审查 — 代码级逐项验证

**日期**: 2026-05-26
**分支**: feature/chat/group-chat-impl
**验证方式**: 逐文件读取 + 后端接口对照

---

## 一、视觉层：气泡/UI — mock 下完整，真实数据下全部崩

### 1.1 `lookupActor` 硬编码 mock 数据

**文件**: `frontend/src/components/group/actors.ts`

```ts
// L1-2: 直接从 mock 文件 import
import { agents, user } from '../../data/mock'
import { coordinator } from '../../data/groups'

// L13-26: 查找逻辑
export function lookupActor(who: string): Actor {
  if (who === 'user') return { name: user.handle, color: 'neutral', initial: user.initial }
  if (who === coordinator.id) {  // coordinator.id === 'coordinator'（字符串字面量）
    return { name: coordinator.name, color: coordinator.color, ... }
  }
  const a = agents.find((x) => x.id === who)  // mock agents: editor/copywriter/researcher
  if (a) return { name: a.name, color: a.color, initial: a.name[0] ?? '?', online: a.online }
  return { name: who, color: 'neutral', initial: who[0] ?? '?' }  // FALLBACK
}
```

**后果**: 真实后端 `sender_agent_id` 是 UUID（如 `f47ac10b-58cc-4372-a567-0e02b2c3d479`），匹配不到 mock agent（id 为 `editor`/`copywriter`/`researcher`），命中 fallback → 气泡显示 UUID 作为名字，所有 Agent 灰色 neutral。

**影响面**（全部调用 `lookupActor`）:
- `GroupMessageItem.tsx:24` — 每条消息气泡的人名/Avatar
- `GroupMembersStrip.tsx:15` — 成员头像条
- `CoordinatorPlan.tsx:24` — 分发方案卡中每个步骤的负责人
- `GroupChatView.tsx:139` — 任务 Tab 中的 assignee 显示

### 1.2 `Coordinator` 类型硬编码

**文件**: `frontend/src/types/index.ts:110-117`

```ts
export interface Coordinator {
  id: 'coordinator'  // 类型字面量，不是通用 string
  ...
}
```

真实协调者 agent 是 UUID，与 `'coordinator'` 字符串不匹配。`lookupActor(coordinator.id)` → `lookupActor('coordinator')` → 找 mock coordinator，永远找不到真实协调者。

### 1.3 `agentStore.agents` 初始为空，无人调用 `loadAgents`

**文件**: `frontend/src/stores/agentStore.ts`

```ts
// L73: 初始化为空数组
agents: [],

// L76-89: loadAgents 从后端拉数据并入 store
loadAgents: async () => {
  const list = await agentsApi.list()
  // ... 去重合并到 agents[]
}
```

群聊相关的任何组件 (`GroupChatView`, `GroupComposer`, `GroupMembersStrip`, `actors.ts`) 都**没有调用** `loadAgents()`。即使把 `lookupActor` 改为从 `agentStore` 读，store 也是空的。

`agentStore.loadAgents()` 的调用方需要确认——当前只可能在 App 初始化或 Agent 管理页面触发。

### 1.4 UI 组件现状总结（mock 数据下可用）

| 组件 | 文件 | 关键依赖 mock | 状态 |
|------|------|-------------|------|
| 气泡渲染 | `GroupMessageItem.tsx` | `lookupActor` → mock agents | ✓ mock / ✗ 真实 |
| @mention 高亮 | `GroupMessageItem.tsx:8-21` | 纯文本正则，无数据依赖 | ✓ 始终正常 |
| 协调者方案卡 | `CoordinatorPlan.tsx` | `lookupActor` 查步骤负责人 | ✓ mock / ✗ 真实 |
| 成员头像条 | `GroupMembersStrip.tsx` | `lookupActor` | ✓ mock / ✗ 真实 |
| @下拉候选 | `GroupComposer.tsx:26-31` | `agents` + `coordinator` 直接 import | ✓ mock / ✗ 真实 |
| 需批准开关 | `GroupComposer.tsx:24` | 纯 UI toggle | ✓ 始终正常 |

---

## 二、数据通道层 — 全部 mock，无一接通

### 2.1 发送链路

**文件**: `frontend/src/stores/groupStore.ts:175-202`

```ts
sendGroup: (groupId, text, opts) => {
  // 1. append 用户消息到本地
  const userMsg: GroupMessage = { id: uid('gu'), from: 'user', who: 'user', ... }
  set(...)

  // 2. 1.2s 后调 simulateGroupReply（纯前端假回复）
  window.setTimeout(() => {
    const reply = simulateGroupReply(group, text)  // ❌ 不走任何网络请求
    set(...)
  }, 1200)
}
```

**缺失**: 没有获取 session_id → 没有 WS send → 没有 HTTP fallback。

### 2.2 接收链路

**文件**: `frontend/src/hooks/useWebSocket.ts`

- L3: `import { useChatStore } from "../stores/chatStore"` — 写死私聊 store
- L22-24: `applyStreamEvent`, `setConnected`, `addUserMessage` 全部来自 `chatStore`
- L49-57: `ws.onmessage` 用 `convKey` 路由到 `chatStore.messages[key]`

群聊没有对应的 WS hook。`StreamEvent` 类型已含 `sender_agent_id` 字段（`types/index.ts:354`），但前端没有任何消费它的代码。

### 2.3 历史消息

**文件**: `frontend/src/stores/groupStore.ts:109`

```ts
messagesByGroup: { ...groupMessages },  // 直接引用 mock/seed 数据
```

`groupMessages` 来自 `data/groups.ts:40-87`，写死在代码里。没有 `fetchMessages` / `loadGroupHistory` action。

### 2.4 Session 映射

- `groupStore` 没有 `sessionIdsByGroup` 字段
- `sessionsApi`（`api/sessions.ts`）有 `createPrivate(agentId, title)` 但没有 `createGroup(groupId, title)` 方法
- 群组在前端只有 `group.id`（可能是 `'content'` 这种 mock id，也可能是后端 UUID），不知道对应的 session_id

---

## 三、后端接口对照（已验证）

### 3.1 已就绪（无需改动）

| 接口 | 验证 |
|------|------|
| `POST /api/sessions` 支持 `group_id` | `schemas/session.py:15` — `group_id: UUID \| None = None`；L21-22 校验 `type==GROUP` 时必须提供 |
| `WS /ws/sessions/{sid}` 群聊 | `ws/chat.py:43-108` — `_handle_message` 走 `ChatService`，已路由群聊路径 |
| `GET /api/sessions/{sid}/messages` | `routers/sessions.py:55-63` — 支持分页拉取历史 |
| `StreamEvent.sender_agent_id` | `types/index.ts:354` — 前端类型已定义 |

### 3.2 需要补的

| 缺口 | 说明 |
|------|------|
| `GET /api/sessions` 不支持 `group_id` 过滤 | `routers/sessions.py:43-45` — 只有 `type` + `q` 参数；`session_service.py:49` — `list(type, query)` 无 group_id |
| 前端 `sessionsApi` 缺少 `createGroup` 方法 | `api/sessions.ts:13-18` — 只有 `createPrivate` |
| `Session` 类型有 `group_id` 字段 | `types/index.ts:331` — `group_id: string \| null` ✓，但前端从未使用 |

---

## 四、需要改动的文件清单（含具体改动）

### 4.1 API 层（2 个文件）

**`frontend/src/api/sessions.ts`** — 加 `createGroup`:
```ts
createGroup: (groupId: string, title = "") =>
  api.post<Session>("/api/sessions", {
    type: "group",
    group_id: groupId,
    title,
  }),
```

**`frontend/src/api/groups.ts`** — 加 `findOrCreateSession`（双调用: 先 list 找已有，找不到再 create）:
```ts
// 伪代码
findOrCreateSession: async (groupId: string) => {
  // 1. GET /api/sessions?type=group → 过滤 group_id 匹配的
  // 2. 有 → 返回 session_id
  // 3. 无 → POST /api/sessions {type:"group", group_id}
}
```
> 如果后端先加了 `GET /api/sessions?group_id=X`，则简化为单次查询。

### 4.2 Store（1 个文件，多处改动）

**`frontend/src/stores/groupStore.ts`**:

| 改动 | 说明 |
|------|------|
| 加字段 `sessionIdsByGroup: Record<string, string>` | groupId → sessionId 映射 |
| 加 action `setGroupSession(groupId, sessionId)` | 写入映射 |
| 加 action `loadGroupHistory(groupId)` | 调 `GET /api/sessions/{sid}/messages`，转 `GroupMessage[]` 写入 `messagesByGroup` |
| 加 action `applyGroupStreamEvent(groupId, event)` | 按 `sender_agent_id` 聚合流式 TEXT，类 `chatStore.applyStreamEvent`，key 为 `groupId:agentId` |
| 改 `sendGroup` | 拿 `sessionIdsByGroup[groupId]` → WS send `{type:"message", content, mentions}` → 删 `simulateGroupReply` |
| 删 `simulateGroupReply` 函数 | 整个 MOCK SEAM（L18-77） |

`applyGroupStreamEvent` 需要处理:
- `event.type === 'text'` + `sender_agent_id` → 找或建 `STREAMING_ID` 哨兵消息，累加 content
- `event.type === 'done'` → 哨兵消息替换为正式 id，`streaming: false`
- `event.type === 'error'` → 哨兵移除，加 error 消息
- 按 `seq` 去重（防止 WS 重连重复）

### 4.3 Hook（新建 1 个文件）

**`frontend/src/hooks/useGroupWebSocket.ts`**（新建）:

复用 `useWebSocket` 的连接/重连骨架，差异化:
- 不依赖 `chatStore`，改为调 `groupStore` 的方法
- `onmessage` 路由到 `groupStore.applyGroupStreamEvent(groupId, event)`
- `sendMessage` 改为群聊格式（带 `mentions` 字段）

### 4.4 组件层（3 个文件）

**`frontend/src/components/group/actors.ts`** — 改 `lookupActor`:
- 移除 `import { agents, user } from '../../data/mock'`
- 移除 `import { coordinator } from '../../data/groups'`
- 改为从 `useAgentStore.getState().agents` 按 id 查找
- 协调者从当前 `group` 的 `coordinator` 字段（来自后端 `ApiGroup.coordinator`）查找
- 需要额外参数传入 `group` 或 `coordinatorId`

**`frontend/src/components/group/GroupComposer.tsx`** — 改 mentionables:
- 移除 `import { agents } from '../../data/mock'`
- 移除 `import { coordinator } from '../../data/groups'`
- `mentionables` 从 `useAgentStore` + `group` prop（含 coordinator）构建
- 或者改为接收 `mentionables` 作为 prop

**`frontend/src/components/group/GroupChatView.tsx`** — 接入生命周期:
- `useEffect` 中:
  1. 调 `groupsApi.findOrCreateSession(group.id)` 获取 sessionId
  2. 调 `groupStore.setGroupSession(group.id, sessionId)`
  3. 调 `groupStore.loadGroupHistory(group.id)`
  4. `useGroupWebSocket(group.id, sessionId)` attach

### 4.5 类型层（1 个文件）

**`frontend/src/types/index.ts`** — `GroupMessage` 类型补全:

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
  streaming?: boolean   // 新增：流式增量渲染中
  mentions?: string[]   // 新增：用户消息中的 @mention 列表
}
```

### 4.6 初始化（1 处）

需要在 App 启动时确保 `agentStore.loadAgents()` 被调用。检查 `App.tsx` 是否有初始化逻辑，如果没有则加 `useEffect` 调 `loadAgents()`。

---

## 五、改动汇总与估时

| # | 文件 | 改动类型 | 估时 |
|---|------|---------|------|
| 1 | `api/sessions.ts` | 加 `createGroup` 方法 | 0.25h |
| 2 | `api/groups.ts` | 加 `findOrCreateSession` | 0.5h |
| 3 | `stores/groupStore.ts` | 加字段 + 3 个 action + 改 sendGroup + 删 MOCK SEAM | 2.5h |
| 4 | `hooks/useGroupWebSocket.ts` | **新建** | 1.5h |
| 5 | `components/group/actors.ts` | 重构 lookupActor | 1h |
| 6 | `components/group/GroupComposer.tsx` | 改 mentionables 数据源 | 0.5h |
| 7 | `components/group/GroupChatView.tsx` | 加生命周期接入 | 0.5h |
| 8 | `types/index.ts` | GroupMessage 加字段 | 0.25h |
| 9 | `App.tsx`（或入口） | agentStore 初始化 | 0.25h |
| **合计** | | | **~7h** |

---

## 六、后端可选改动

如果后端加 `GET /api/sessions?group_id=X` 过滤:
- `routers/sessions.py:43` — 加 `group_id: UUID | None = None` 参数
- `session_service.py:49-50` — `list()` 方法加 `group_id` 参数，透传 repository

不改后端的话前端用「list(type="group") → 客户端过滤 group_id → 找不到再 create」双调用模式，多一次 HTTP 往返，成本可忽略。

---

## 七、判断

- **mock 数据下**: UI 完整可用，演示效果好
- **真实后端下**: 气泡显示 UUID 作为名字（`lookupActor` fallback），无颜色区分，发送不走 WS，接收无 hook，session 映射缺失 — **完全不可用**
- **核心瓶颈**: `actors.ts` 的数据源 + `groupStore` 的 MOCK SEAM + 缺少 WS hook
- **最简打通路径**: 改 `actors.ts`（1h）+ 改 `groupStore.sendGroup`（2.5h）+ 新建 `useGroupWebSocket`（1.5h）+ 接 `GroupChatView`（0.5h）= **~5.5h 可看到第一条真实流式回复**
