# 前端交互设计 — 协调者任务执行 MVP

> 日期：2026-06-06 | 基于：[[coordinator-dag-driven-design-v2]] §14.1 MVP + [[coordinator-mvp-phase5-wiring-spec]]
> 范围：Phase 5 接线对应的前端改动。MVP 只做聊天流，不做独立任务面板。

---

## 0. 设计原则

1. **聊天流是主界面**。任务分解、执行进度、完成汇总全部在聊天时间线展示，不跳转到独立页面。
2. **系统消息承载状态**。Coordinator 的 plan / task 状态变更 / final_answer 都以消息形式出现在聊天流，与用户和 Agent 的对话自然交织。
3. **组件复用，不做新轮子**。已有 `CoordinatorPlan` / `GroupMessageItem` / `groupStore.applyGroupStreamEvent` / `actors.lookupActor`。增量改，不重写。
4. **MVP 无实时 task 面板**。task tab 保留现有静态 mock 数据。per-task Worker 流式输出不进聊天（刷屏），走 Phase 5b 任务面板。

---

## 1. 消息流全景

```
用户: "帮我创建登录页面"
  │
  ▼  ChatService gate 判 decompose → CoordinatorRun 启动 → Planner.plan()
  │
[系统] 📋 任务分解完成                              ← task_plan 事件
  ┌─ CoordinatorPlan ──────────────────────────┐
  │ 分发方案 · 3 步                              │
  │ t-1  前端Agent  LoginForm 组件    ⚪ 等待    │
  │ t-2  后端Agent  auth API 端点     ⚪ 等待    │
  │ t-3  测试Agent  E2E 测试          ⚪ 等待    │
  │                            [自动执行中…]     │
  └─────────────────────────────────────────────┘
  │
  │  Orchestrator dispatch → Worker 执行
  │
[系统] 🟡 t-1 LoginForm 组件 执行中…               ← task_update 事件
[系统] ✅ t-1 LoginForm 组件 完成（耗时 45s）
[系统] 🟡 t-2 auth API 端点 执行中…
[系统] ✅ t-2 auth API 端点 完成（耗时 25s）
[系统] 🟡 t-3 E2E 测试 执行中…
[系统] ✅ t-3 E2E 测试 完成（耗时 30s）
  │
  │  Orchestrator 全部 COMPLETED → Planner.final_answer()
  │
[协调者] 登录页面创建完成 ✅                        ← coordinator 发言
  │ 创建了 3 个文件，验收全部通过
  │
  │  用户追问
  │
[用户] @协调者 后端接口有做限流吗？
[协调者] 已确认：t-2 实现了连续 5 次失败锁定 30 分钟。
```

---

## 2. 数据结构变更

### 2.1 类型层（`types/index.ts`）

```typescript
// ── 新增：任务执行状态更新 ──

export interface TaskUpdate {
  taskId: string
  title: string
  status: 'running' | 'done' | 'failed'
  duration?: string   // 耗时，如 "45s"
  reason?: string     // 失败原因
}

// ── 改动：GroupMessage 扩字段 ──

export interface GroupMessage {
  // … 现有字段不变 …
  role?: 'user' | 'agent' | 'system'  // ★ 新增 system
  kind?: 'plan' | 'task_update'       // ★ 新增 task_update
  taskUpdate?: TaskUpdate             // ★ 新增
}

// ── 改动：CoordinatorPlan step 加状态 ──

export interface PlanStep {
  // … 现有字段不变 …
  status?: 'pending' | 'running' | 'done' | 'failed'  // ★ 新增
}
```

### 2.2 Store 层（`groupStore.ts` — `applyGroupStreamEvent`）

现有 `applyGroupStreamEvent` 处理 text/done/error 三种事件，thinking/tool_*/task_plan 被忽略。

**改动**：新增两种事件处理 + 对 done 事件做 sender 区分。

```typescript
applyGroupStreamEvent: (groupId, event) => {
  set((s) => {
    const list = s.messagesByGroup[groupId] ?? []
    const senderId = event.sender_agent_id ?? 'unknown'

    // === 现有：text 流式聚合（不改） ===
    if (event.type === 'text') { /* … 不变 … */ }

    // === 现有：done 结束流式哨兵（扩展：区分普通 agent vs 协调者） ===
    if (event.type === 'done') {
      // sender 是协调者 → final_answer 文本作为单独系统消息
      // （协调者的文本已经在 text 事件里流式聚合了，done 只是清哨兵）
      const next = list.map((m) =>
        m.id === streamingKey(groupId, senderId)
          ? { ...m, id: uid('gm'), streaming: false }
          : m,
      )
      return { messagesByGroup: { ...s.messagesByGroup, [groupId]: next } }
    }

    // === 现有：error（不改） ===
    if (event.type === 'error') { /* … 不变 … */ }

    // ★ 新增：task_plan → 系统消息嵌 CoordinatorPlan
    if (event.type === 'task_plan') {
      const plan = event.metadata?.plan as CoordinatorPlan | undefined
      if (!plan) return {}
      const msg: GroupMessage = {
        id: uid('tp'),
        from: 'agent',
        who: senderId,
        role: 'system',
        time: nowStamp(),
        text: '📋 任务分解完成',
        kind: 'plan',
        plan,
      }
      return {
        messagesByGroup: { ...s.messagesByGroup, [groupId]: [...list, msg] },
      }
    }

    // ★ 新增：task_update → 系统消息
    if (event.type === 'task_update') {
      const update = event.metadata as TaskUpdate | undefined
      if (!update) return {}
      const emoji = update.status === 'running' ? '🟡' :
                    update.status === 'done' ? '✅' : '❌'
      const dur = update.duration ? `（耗时 ${update.duration}）` : ''
      const reason = update.reason ? ` — ${update.reason}` : ''
      const msg: GroupMessage = {
        id: uid('tu'),
        from: 'agent',
        who: senderId,
        role: 'system',
        time: nowStamp(),
        text: `${emoji} ${update.title} ${update.status === 'running' ? '执行中…' : update.status === 'done' ? '完成' : '失败'}${dur}${reason}`,
        kind: 'task_update',
        taskUpdate: update,
      }
      // 同步更新已存在的 plan 卡中对应 step 的 status
      const updated = list.map((m) => {
        if (m.kind === 'plan' && m.plan) {
          const steps = m.plan.steps.map((s) =>
            s.id === update.taskId ? { ...s, status: update.status } : s,
          )
          return { ...m, plan: { ...m.plan, steps } }
        }
        return m
      })
      return {
        messagesByGroup: {
          ...s.messagesByGroup,
          [groupId]: [...updated, msg],
        },
      }
    }

    // thinking / tool_* / request_approval：MVP 不渲染
    return {}
  })
},
```

### 2.3 StreamEvent 类型层（`types/index.ts`）

```typescript
export type StreamEventType =
  | 'text' | 'thinking' | 'tool_call' | 'tool_result'
  | 'request_approval' | 'task_plan' | 'task_update'  // ★ 新增 task_update
  | 'error' | 'done'
```

后端 `StreamEventType` enum 对应新增 `TASK_UPDATE = "task_update"`（Phase 5 接线时加）。

---

## 3. 组件层改动

### 3.1 GroupMessageItem — 系统消息样式

```tsx
export function GroupMessageItem({ msg, group }: { msg: GroupMessage; group?: Group }) {
  const isSystem = msg.role === 'system'

  // ── 系统消息：无头像、灰底、小字、左缩进 ──
  if (isSystem) {
    return (
      <div className="-mx-2 flex gap-3 rounded-lg px-2 py-1">
        {/* 左侧时间线竖线 + 状态点 */}
        <div className="flex w-8 flex-shrink-0 flex-col items-center pt-1.5">
          <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40" />
          <div className="mt-0.5 w-px flex-1 bg-border/50" />
        </div>
        <div className="min-w-0 flex-1 pb-1">
          <div className="text-[12.5px] leading-relaxed text-muted-foreground">
            {msg.text}
          </div>
          {/* plan 卡嵌在系统消息内 */}
          {msg.kind === 'plan' && msg.plan && (
            <CoordinatorPlan plan={msg.plan} group={group} live />
          )}
        </div>
      </div>
    )
  }

  // ── 现有用户/Agent 消息渲染（不改）──
  // … 现有代码 …
}
```

### 3.2 CoordinatorPlan — 实时状态 + 移除 manual 派发

```tsx
export function CoordinatorPlan({
  plan,
  group,
  live = false,  // ★ 新增：true = 执行中，显示实时状态
}: {
  plan: Plan
  group?: Group
  live?: boolean
}) {
  // 统计各状态步骤数
  const stats = {
    done: plan.steps.filter((s) => s.status === 'done').length,
    running: plan.steps.filter((s) => s.status === 'running').length,
    failed: plan.steps.filter((s) => s.status === 'failed').length,
    pending: plan.steps.filter((s) => !s.status || s.status === 'pending').length,
  }
  const total = plan.steps.length
  const done = stats.done + (stats.failed > 0 ? stats.failed : 0)  // failed 也算"已结束"
  const progressPct = total > 0 ? Math.round((done / total) * 100) : 0

  return (
    <div className="mt-2 overflow-hidden rounded-xl border bg-card">
      {/* header */}
      <header className="flex items-center gap-2 border-b border-border/70 bg-brand/5 px-4 py-2.5">
        <Icon name="network" className="h-3.5 w-3.5 text-brand" />
        <span className="font-mono text-[10.5px] uppercase tracking-wider text-brand">
          分发方案 · {total} 步
        </span>
        {/* ★ 进度条（仅 live 模式） */}
        {live && (
          <>
            <div className="mx-2 h-1 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-brand transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="font-mono text-[10.5px] text-brand">
              {done}/{total}
            </span>
          </>
        )}
        <div className="flex-1" />
        <Badge variant="brand">协调者</Badge>
      </header>

      {/* summary */}
      <div className="px-4 py-3">
        <p className="text-[13.5px] leading-relaxed text-foreground/90">
          {plan.summary}
        </p>
      </div>

      {/* steps */}
      <ol className="divide-y border-t">
        {plan.steps.map((s) => {
          const a = lookupActor(s.who, group)
          const statusIcon =
            s.status === 'running' ? '🟡' :
            s.status === 'done' ? '🟢' :
            s.status === 'failed' ? '🔴' : '⚪'
          return (
            <li
              key={s.id}
              className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-muted/30"
            >
              {/* ★ 状态指示器（live 模式） */}
              {live && <span className="w-4 text-center text-[11px]">{statusIcon}</span>}
              <span className="w-7 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
                {s.id}
              </span>
              <div className="flex w-[120px] flex-shrink-0 items-center gap-2">
                <Avatar initial={a.initial} color={a.color} size={20} />
                <span className="truncate text-[12.5px] font-medium">{a.name}</span>
              </div>
              <span className="flex-1 truncate text-[13px]">{s.label}</span>
              {/* 静态模式：显示 ETA；live 模式：显示状态文本 */}
              {!live && (
                <span className="hidden items-center gap-1 font-mono text-[10.5px] text-muted-foreground md:inline-flex">
                  <Icon name="clock" className="h-3 w-3" />~{s.eta} min
                </span>
              )}
              {!live && (
                <span className="hidden font-mono text-[10.5px] text-muted-foreground lg:inline">
                  {s.depends.length ? `依赖 ${s.depends.join(', ')}` : '可立即开始'}
                </span>
              )}
            </li>
          )
        })}
      </ol>

      {/* watchouts */}
      {plan.watchouts.length > 0 && (
        <div className="border-t bg-amber-50/40 px-4 py-2.5 dark:bg-amber-950/20">
          <div className="flex items-start gap-2">
            <Icon name="info" className="mt-0.5 h-3.5 w-3.5 text-amber-700 dark:text-amber-400" />
            <div className="space-y-0.5">
              {plan.watchouts.map((w, i) => (
                <div key={i} className="text-[12.5px] text-amber-800 dark:text-amber-300">
                  {w}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ★ footer：live 模式显示进度，静态模式保留"派发"按钮 */}
      {live ? (
        <footer className="flex items-center border-t bg-muted/20 px-4 py-2">
          <span className="font-mono text-[11px] text-muted-foreground">
            {stats.running > 0
              ? `${stats.running} 个任务执行中 · 自动执行`
              : stats.pending > 0
                ? '等待依赖完成…'
                : '全部完成'}
          </span>
        </footer>
      ) : (
        <footer className="flex items-center justify-between border-t bg-muted/20 px-4 py-2">
          <span className="font-mono text-[11px] text-muted-foreground">
            每个子任务会作为独立任务进入「任务」标签
          </span>
          <div className="flex gap-1.5">
            <Button variant="ghost" size="sm">改一下</Button>
            <Button variant="brand" size="sm">
              <Icon name="zap" className="h-3 w-3" />派发
            </Button>
          </div>
        </footer>
      )}
    </div>
  )
}
```

### 3.3 协调者发言人渲染（现有逻辑，无需改动）

`actors.ts` 已通过 `group.coordinatorId` 匹配协调者 UUID → 渲染 `品牌色 + "协调者" Badge`。`GroupMessageItem:43` 的 `isCoordinator` 判断和 L55 的 `<Badge variant="brand">协调者</Badge>` 已经工作。

Coordinator 发言：`from='agent'`, `who=coordinatorId` → `GroupMessageItem` 渲染为「协调者头像 + 蓝色 Badge + Markdown 正文」。和普通 Agent 消息外观一致，Badge 区分。

---

## 4. 改动清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `types/index.ts` | 改 | 加 `TaskUpdate` / `PlanStep.status` / `GroupMessage.role` / `GroupMessage.kind='task_update'` / `StreamEventType` 加 `task_update` |
| `stores/groupStore.ts` | 改 | `applyGroupStreamEvent` 处理 `task_plan` + `task_update` 事件；done 事件保持不变 |
| `components/group/GroupMessageItem.tsx` | 改 | 新增 `role==='system'` 分支（时间线样式） |
| `components/group/CoordinatorPlan.tsx` | 改 | 新增 `live` prop — 进度条 + 状态图标 + footer 文案自适应 |
| `components/group/actors.ts` | **不动** | 协调者渲染已有 |
| `components/group/GroupChatView.tsx` | **不动** | 聊天流自动渲染 |
| `components/tasks/*` | **不动** | MVP 不碰 |
| `stores/taskStore.ts` | **不动** | 保留 mock 数据 |

**净增量**：~80 行 TypeScript + ~60 行 TSX。不改任何 API 调用——全部通过现有 WS 管道推送。

---

## 5. 后端配合

前端需要的 WS 事件：

| StreamEvent.type | 触发时机 | metadata |
|-----------------|---------|---------|
| `task_plan` | `Orchestrator.run()` 中 `plan()` 完成后 | `{ plan: CoordinatorPlan }` |
| `task_update` | 每次 FSM transition（`RUNNING`/`COMPLETED`/`FAILED`）后 | `{ taskId, title, status, duration?, reason? }` |
| `text` + `done` | `Planner.final_answer()` 输出时 | `sender_agent_id = coordinator.id` |

`Orchestrator` 现有 `events` 列表记录了每次 transition。Phase 5 接线时，在 `_transition` 或 `_execute_and_settle` 的完成/失败点，通过 EventBus 发射对应的 `task_update` / `task_plan` StreamEvent 到前端 WS 管道。

---

## 6. 不做

| 不做 | 原因 | 何时做 |
|------|------|--------|
| 独立 TaskPanel（per-task 流式输出） | 刷屏聊天流 | Phase 5b（标准档） |
| DAG 可视化（节点连线图） | 复杂度高，MVP 用列表够用 | Phase 5b |
| plan review 审批确认 | MVP 无 plan review | 标准档 |
| 用户执行中 @worker 改需求 | MVP 执行态勿扰 | 标准档 A2 |
| tasks tab 实时同步 | 当前 mock 数据足够 | Phase 5b |

---

## 关联文档

- [[coordinator-mvp-phase5-wiring-spec]] Phase 5 接线 spec（后端）
- [[coordinator-dag-driven-design-v2]] §14.1 MVP 范围
- `src/frontend/src/components/group/` 现有组件源码
