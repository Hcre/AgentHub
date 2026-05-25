# 群组创建功能实现文档

> 设计依据：`group-creation_群组创建功能设计方案.md`（同目录）。本文档是它的**可执行实现说明**——逐文件、含骨架代码、对齐前端现有风格、锚定真实行号。
> 工作树：`/home/huishuohuademao/workspace/AgentHub-group-creation`　分支：`feature/group/creation`（基于 main @ `8c01ac8`）。

---

## 0. 实现前必读：两处对设计文档的校正

实现前发现设计文档两处需要修正，**以本文档为准**：

### 0.1 左栏「频道」渲染的是 `channels`，不是 `groupStore.groups`（设计 §5.5 遗漏）

`LeftPanel.tsx:148-162` 当前的列表来源是 `data/mock.ts` 的 `channels`（静态数组），**不是** `groupStore` 的 `groups`：

```tsx
import { channels, nav, org, user } from '../../data/mock'   // :3
...
{channels.map((c) => (                                        // :151
  <NavRow ... onClick={() => openGroup(c.id)} />
))}
```

只是因为 `channels` 与 `data/groups.ts` 的 `groups` 恰好用了同一组 id（content / design / growth），mock 下看起来一致。

**后果**：若只按设计 §5.3 给 `groupStore` 加 `createGroup()`，新建的群组写进 `groupStore.groups`，但左栏读的还是 `channels`——**新群组不会出现在侧边栏**。

**修正**：LeftPanel 群组列表必须切到 `groupStore.groups`（见 §5.5 改动 0）。这是本功能「创建后即时可见」的前提，非可选项。

### 0.2 `sendGroup` mock 必须保留（设计 §5.3 与 §六 自相矛盾）

设计 §5.3 step 1 写「删掉 `simulateGroupReply` + MOCK SEAM 整段」，但 §六 又声明「群聊消息保持 mock，仅创建接真实 API」。两者冲突。

**裁定**：群聊不在本次范围（§六），故 `simulateGroupReply` / `groupMessages` / `sendGroup` **整段保留**。`groupStore` 本次只**新增** `fetchGroups()` / `createGroup()`，不删除既有 mock 聊天逻辑。设计 §5.3 step 1/2 的「删除」指令作废。

---

## 1. 文件改动清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `frontend/src/types/index.ts` | 改 | 在「后端 API DTO」段（`:280` 后）新增 `ApiGroup` / `ApiGroupMember` / `ApiGroupCoordinator` |
| `frontend/src/api/groups.ts` | 新建 | `groupsApi.list / create / checkName`，对齐 `api/agents.ts` |
| `frontend/src/hooks/useDebounce.ts` | 新建 | 通用防抖 hook（名称实时校验 + 成员搜索用） |
| `frontend/src/stores/groupStore.ts` | 改 | 新增 `fetchGroups` / `createGroup`（API-first + 降级），对齐 `agentStore`；mock 聊天段保留 |
| `frontend/src/components/group/CreateGroupModal.tsx` | 新建 | 创建弹窗，对齐 `CreateAgentModal` |
| `frontend/src/components/layout/LeftPanel.tsx` | 改 | 数据源切到 `groupStore.groups` + 「频道」→「群组」+「+」入口 + 挂载弹窗 |
| `frontend/src/App.tsx` | 改 | 挂载时 `void fetchGroups()`，与 `loadAgents()` 并列 |

后端文件清单与流程见设计文档 §四，本文档不重复；前端依赖的后端契约见 §7。

---

## 2. 实现顺序（带依赖）

```
后端（设计 §四，可与前端并行）
  1. Migration → 2. Model/Entity → 3. Repository → 4. Service → 5. Schema → 6. Router

前端（本文档）
  A. types DTO          ← 无依赖，先做
  B. api/groups.ts      ← 依赖 A
  C. hooks/useDebounce  ← 无依赖
  D. groupStore 改造    ← 依赖 A、B
  E. CreateGroupModal   ← 依赖 B、C、D
  F. LeftPanel 改造     ← 依赖 D、E
  G. App 启动 fetch     ← 依赖 D
```

后端未就绪时，前端靠 `createGroup` / `fetchGroups` 的 try/catch 降级到本地 mock（对齐 `agentStore`），UI 不卡——可先全量自测前端，再联调。

---

## 3. 前端实现

### 3.1 `types/index.ts`（改）—— 新增后端 DTO 类型

在 `ApiAgent`（`:283`）之后、同一「后端 API DTO」段内追加。命名与 `ApiAgent` 一致（`Api*` 前缀、snake_case 字段）：

```ts
/** 对应 backend `GroupMemberOut`。 */
export interface ApiGroupMember {
  id: string
  name: string
  role: string
}

/** 对应 backend 协调者摘要（GroupOut.coordinator）。 */
export interface ApiGroupCoordinator {
  id: string
  name: string
  role: string
  agent_system: string
  is_system: boolean
}

/** 对应 backend `GroupOut`（schemas/group.py）。注意与 UI 的 `Group` 区分。 */
export interface ApiGroup {
  id: string
  name: string
  description: string
  coordinator: ApiGroupCoordinator
  members: ApiGroupMember[]
  created_at: string
}
```

> 不动既有 UI 类型 `Group`（`:101`）——它是前端视图模型（`members: string[]`），由 store 从 `ApiGroup` 映射得到。

### 3.2 `api/groups.ts`（新建）—— 对齐 `api/agents.ts`

完整复刻 `api/agents.ts` 的结构：co-locate 输入类型，导出一个 `*Api` 对象，方法体一行调 `api.*`。

```ts
import { api } from './client'
import type { ApiGroup } from '../types'

export interface CreateGroupInput {
  name: string
  description?: string
  /** 初始成员 Agent id 列表；协调者由后端自动加入，不在此列。 */
  member_ids?: string[]
}

export interface NameCheckResult {
  available: boolean
  reason?: string
}

export const groupsApi = {
  list: () => api.get<ApiGroup[]>('/api/groups'),
  create: (input: CreateGroupInput) => api.post<ApiGroup>('/api/groups', input),
  checkName: (name: string) =>
    api.get<NameCheckResult>(`/api/groups/check-name?name=${encodeURIComponent(name)}`),
}
```

对照 `api/agents.ts`：`CreateAgentInput` 同样 co-locate；`agentsApi` 同样是方法对象。零新增模式。

### 3.3 `hooks/useDebounce.ts`（新建）

用全局规则里的标准实现（`rules/typescript/patterns.md`），供名称校验与成员搜索复用：

```ts
import { useEffect, useState } from 'react'

export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState<T>(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}
```

> 若已存在 `hooks/` 目录里的等价实现，复用之，不要重复造。先 `grep -rn "useDebounce" frontend/src`。

### 3.4 `stores/groupStore.ts`（改）—— 对齐 `agentStore` 的 API-first + 降级

**保留**：`simulateGroupReply`、`groupMessages`、`sendGroup` 整段（§0.2）。
**新增**：`toUiGroup` 映射、`fetchGroups`、`createGroup`。模式 1:1 对照 `agentStore.loadAgents` / `createAgent`。

顶部 import 增加：

```ts
import { groupsApi, type CreateGroupInput } from '../api/groups'
import type { ApiGroup, Group, GroupMessage } from '../types'
```

`ApiGroup → UI Group` 映射（紧邻 MOCK SEAM 之外，与 `agentStore.toUiAgent` 同位）：

```ts
/** 后端 ApiGroup → UI Group。members 仅保留 agentId（协调者已含在后端 members 内）。 */
function toUiGroup(g: ApiGroup): Group {
  return {
    id: g.id,
    name: g.name,
    description: g.description,
    members: g.members.map((m) => m.id),
  }
}
```

`GroupState` 接口扩展：

```ts
interface GroupState {
  groups: Group[]
  messagesByGroup: Record<string, GroupMessage[]>

  /** 拉后端真实群组并入列表（按 id 去重）；失败保持 seed mock。 */
  fetchGroups: () => Promise<void>
  /** 创建群组：先同步后端取真实 UUID；后端不可用则本地降级 mock。返回新群 id。 */
  createGroup: (input: CreateGroupInput) => Promise<string>
  sendGroup: (groupId: string, text: string, opts?: SendGroupOptions) => void
}
```

action 实现（放在 `sendGroup` 之前）——逐行对照 `agentStore`：

```ts
  fetchGroups: async () => {
    try {
      const list = await groupsApi.list()
      set((s) => {
        const existing = new Set(s.groups.map((g) => g.id))
        const incoming = list.filter((g) => !existing.has(g.id)).map(toUiGroup)
        return { groups: [...s.groups, ...incoming] }
      })
    } catch {
      // 后端不可用 → 保持 seed mock
    }
  },

  createGroup: async (input) => {
    try {
      const created = await groupsApi.create(input)
      const group = toUiGroup(created)
      set((s) => ({ groups: [...s.groups, group] }))
      return group.id
    } catch {
      // 后端不可用 → 本地降级 mock，保证 UI 不卡
      const id = uid('grp')
      const group: Group = {
        id,
        name: input.name,
        description: input.description ?? '',
        members: input.member_ids ?? [],
      }
      set((s) => ({ groups: [...s.groups, group] }))
      return id
    }
  },
```

> `uid` 已在文件顶部 import。降级分支与 `agentStore.createAgent` 的 catch 块同形——这是项目既定「后端不可用不阻断 UI」的约定，照搬即可。

### 3.5 `components/group/CreateGroupModal.tsx`（新建）—— 对齐 `CreateAgentModal`

骨架 = `CreateAgentModal` 的外壳 + 状态机：`Dialog`/`DialogContent` 包裹，`header(border-b)` / 内容 `p-4` / `footer(border-t)` 三段，本地 `Label` 组件，`submitting` 守卫，`reset()`，`try/finally`。差异只在表单字段（名称校验 + 双栏成员选择器）。

成员候选直接取 `agentStore.agents`（启动已 `loadAgents` 过滤掉 system agent），**客户端**按名称过滤——避免为搜索再开一个 fetch；服务端 `GET /api/agents?search=`（设计 §2.3）留作后续替换点。

```tsx
import { useEffect, useMemo, useState } from 'react'
import { groupsApi } from '../../api/groups'
import { useDebounce } from '../../hooks/useDebounce'
import { useAgentStore } from '../../stores/agentStore'
import { useGroupStore } from '../../stores/groupStore'
import { useUIStore } from '../../stores/uiStore'
import { Avatar, Button, Dialog, DialogContent, Icon, Input, Textarea } from '../ui'

function Label({ children }: { children: string }) {
  return <span className="text-[12px] font-medium text-muted-foreground">{children}</span>
}

type NameState = 'idle' | 'checking' | 'ok' | 'taken' | 'invalid'

// 与后端 §2.4 规则一致：小写字母开头，[a-z0-9_-]，2-32 字符
const NAME_RE = /^[a-z][a-z0-9_-]{1,31}$/

export function CreateGroupModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const agents = useAgentStore((s) => s.agents)
  const createGroup = useGroupStore((s) => s.createGroup)
  const openGroup = useUIStore((s) => s.openGroup)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [nameState, setNameState] = useState<NameState>('idle')
  const [submitting, setSubmitting] = useState(false)

  const debouncedName = useDebounce(name, 300)

  // 名称实时校验：本地格式 → 服务端唯一性（后端不可用时退回 idle，提交时由后端 409 兜底）
  useEffect(() => {
    if (!debouncedName) return setNameState('idle')
    if (!NAME_RE.test(debouncedName)) return setNameState('invalid')
    let alive = true
    setNameState('checking')
    groupsApi
      .checkName(debouncedName)
      .then((r) => alive && setNameState(r.available ? 'ok' : 'taken'))
      .catch(() => alive && setNameState('idle'))
    return () => {
      alive = false
    }
  }, [debouncedName])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? agents.filter((a) => a.name.toLowerCase().includes(q)) : agents
  }, [agents, query])

  const reset = () => {
    setName('')
    setDescription('')
    setQuery('')
    setSelected([])
    setNameState('idle')
  }

  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  const canSubmit = NAME_RE.test(name) && nameState !== 'taken' && nameState !== 'checking' && !submitting

  const submit = async () => {
    if (!canSubmit) return
    setSubmitting(true)
    try {
      const id = await createGroup({
        name: name.trim(),
        description: description.trim() || undefined,
        member_ids: selected,
      })
      reset()
      onClose()
      openGroup(id) // 创建后自动进入新群（设计 §5.4）
    } finally {
      setSubmitting(false)
    }
  }

  const hint: Record<NameState, { text: string; cls: string }> = {
    idle: { text: '小写字母开头，可用小写字母、数字、连字符或下划线。', cls: 'text-muted-foreground' },
    checking: { text: '校验中…', cls: 'text-muted-foreground' },
    ok: { text: '✓ 名称可用', cls: 'text-emerald-600' },
    taken: { text: '名称已存在', cls: 'text-destructive' },
    invalid: { text: '格式不合法：小写字母开头，2-32 字符。', cls: 'text-destructive' },
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <header className="border-b px-4 py-3">
          <div className="flex items-center justify-between">
            <h3 className="text-[15px] font-medium">新建群组频道</h3>
            <Button variant="ghost" size="iconSm" onClick={onClose}>
              <Icon name="x" className="h-3.5 w-3.5" />
            </Button>
          </div>
          <p className="mt-0.5 text-[12px] text-muted-foreground">和合适的队友一起开始共享对话。</p>
        </header>

        <div className="flex flex-col gap-3 overflow-y-auto p-4">
          <label className="flex flex-col gap-1">
            <Label>频道名称 *</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="design-review"
              autoFocus
            />
            <span className={`text-[11px] ${hint[nameState].cls}`}>{hint[nameState].text}</span>
          </label>

          <label className="flex flex-col gap-1">
            <Label>描述</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="这个频道用于什么?"
              className="min-h-[60px]"
            />
          </label>

          <div className="flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <Label>成员</Label>
              <span className="text-[11px] text-muted-foreground">已选择 {selected.length} 位</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {/* 左：搜索 + 勾选 */}
              <div className="flex flex-col rounded-md border">
                <div className="flex items-center gap-2 border-b px-2.5 py-1.5 text-muted-foreground">
                  <Icon name="search" className="h-3.5 w-3.5" />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="搜索工作区成员"
                    className="min-w-0 flex-1 bg-transparent text-[13px] outline-none placeholder:text-muted-foreground/70"
                  />
                </div>
                <div className="max-h-[180px] overflow-y-auto p-1">
                  {filtered.map((a) => {
                    const on = selected.includes(a.id)
                    return (
                      <button
                        key={a.id}
                        onClick={() => toggle(a.id)}
                        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                      >
                        <span className="grid h-4 w-4 place-items-center rounded border">
                          {on && <Icon name="check" className="h-3 w-3 text-brand" />}
                        </span>
                        <Avatar initial={a.name[0] ?? '?'} color={a.color} size={20} />
                        <span className="flex-1 truncate">{a.name}</span>
                      </button>
                    )
                  })}
                  {filtered.length === 0 && (
                    <p className="px-2 py-4 text-center text-[12px] text-muted-foreground">无匹配成员</p>
                  )}
                </div>
              </div>

              {/* 右：已选成员 */}
              <div className="flex flex-col rounded-md border">
                <div className="border-b px-2.5 py-1.5 text-[12px] font-medium text-muted-foreground">
                  已选成员
                </div>
                <div className="max-h-[180px] overflow-y-auto p-1">
                  <p className="px-2 pt-1 text-[11px] text-muted-foreground">频道创建者会自动包含在内。</p>
                  {selected.length === 0 ? (
                    <p className="px-2 py-4 text-center text-[12px] text-muted-foreground">
                      还没有选择其他成员。
                    </p>
                  ) : (
                    selected.map((id) => {
                      const a = agents.find((x) => x.id === id)
                      if (!a) return null
                      return (
                        <div
                          key={id}
                          className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                        >
                          <Avatar initial={a.name[0] ?? '?'} color={a.color} size={20} />
                          <span className="flex-1 truncate">{a.name}</span>
                          <button
                            onClick={() => toggle(id)}
                            className="grid h-4 w-4 place-items-center rounded hover:bg-accent"
                            title="移除"
                          >
                            <Icon name="x" className="h-3 w-3" />
                          </button>
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        <footer className="flex justify-end gap-2 border-t px-4 py-3">
          <Button variant="outline" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button variant="brand" size="sm" onClick={submit} disabled={!canSubmit}>
            创建
          </Button>
        </footer>
      </DialogContent>
    </Dialog>
  )
}
```

风格对齐核对：`Dialog`+`DialogContent`、`Label` 组件、`header border-b px-4 py-3` / `footer border-t px-4 py-3`、`outline`+`brand` 两个 `size="sm"` 按钮、`submitting` 守卫、`reset()`、`try/finally`、复用 `Avatar`/`Icon`/`Input`/`Textarea`——全部取自 `CreateAgentModal`，无自创组件。

### 3.6 `components/layout/LeftPanel.tsx`（改）—— 4 处改动

**改动 0（数据源，§0.1 必做）**——群组列表从 `channels` 切到 `groupStore.groups`：

```tsx
// :3  去掉 channels（若文件内无其他引用）
import { nav, org, user } from '../../data/mock'
// 顶部新增
import { useGroupStore } from '../../stores/groupStore'
import { CreateGroupModal } from '../group/CreateGroupModal'

// 组件内（与 agents 取法并列，约 :99）
const groups = useGroupStore((s) => s.groups)
```

列表渲染（替换 `:149-162`）。`Group` 无 `unread` 字段，去掉 `badge`（unread 红点超出本次范围，后续接消息系统再补）：

```tsx
{openCh && (
  <div className="space-y-px">
    {groups.map((g) => (
      <NavRow
        key={g.id}
        label={g.name}
        dotted
        active={section === 'group' && activeGroupId === g.id}
        onClick={() => openGroup(g.id)}
      />
    ))}
  </div>
)}
```

**改动 1**——「频道」→「群组」+「+」入口（`SectionHeader` 已内置 `onAdd`/`addTitle`，无需改组件，与「AI 队友」段 `:164-170` 同一套）：

```tsx
<SectionHeader
  label="群组"
  collapsed={!openCh}
  onToggle={() => setOpenCh((v) => !v)}
  onAdd={() => setGroupCreateOpen(true)}
  addTitle="创建群组"
/>
```

**改动 2**——弹窗开关 state（与 `createOpen` 并列，`:104`）：

```tsx
const [groupCreateOpen, setGroupCreateOpen] = useState(false)
```

**改动 3**——挂载弹窗（紧随现有 `<CreateAgentModal>`，`:272`）：

```tsx
<CreateGroupModal open={groupCreateOpen} onClose={() => setGroupCreateOpen(false)} />
```

**注意**：不要动 `data/mock.ts:76` 的 `centerTabs` 里的「频道」Tab——那是中间面板的 Tab，与左栏群组段无关。

### 3.7 `App.tsx`（改）—— 启动拉取群组

与 `loadAgents`（`:12,:19-21`）完全并列：

```tsx
const fetchGroups = useGroupStore((s) => s.fetchGroups)
// ...
useEffect(() => {
  void fetchGroups()
}, [fetchGroups])
```

（顶部 `import { useGroupStore } from './stores/groupStore'`。）

---

## 4. 风格对齐对照表

| 关注点 | 参照来源 | 本功能做法 |
|--------|---------|-----------|
| 弹窗外壳 | `CreateAgentModal` + `Dialog/DialogContent`（560px） | `CreateGroupModal` 同壳 |
| header / footer | `border-b px-4 py-3` / `border-t px-4 py-3` | 照搬 |
| 字段标签 | `CreateAgentModal` 内 `Label`（`text-[12px] text-muted-foreground`） | 同名本地组件复刻 |
| 主/次按钮 | `variant="brand"` + `variant="outline"`，`size="sm"` | 照搬 |
| 提交守卫 | `submitting` + `try/finally` + `disabled` | 照搬 |
| 表单重置 | `CreateAgentModal.reset()` | 同形 reset |
| API 模块 | `api/agents.ts`（co-locate 输入类型 + `*Api` 对象） | `api/groups.ts` 同构 |
| Store 降级 | `agentStore.loadAgents/createAgent`（API-first + catch 兜底） | `fetchGroups/createGroup` 同构 |
| 启动拉取 | `App.tsx` 的 `void loadAgents()` | `void fetchGroups()` |
| 「+」入口 | `SectionHeader.onAdd`（AI 队友段） | 同一套 props |
| 头像/图标 | `Avatar` / `Icon`（`check`/`search`/`x`/`plus` 均在 `IconName`） | 复用 |

---

## 5. 后端契约依赖（前端假设）

后端实现见设计文档 §四。前端只依赖以下契约，联调前需对齐：

- `POST /api/groups` 返回 `ApiGroup`（含 `coordinator` + `members[]`，`members` 已含协调者或前端忽略协调者条目均可——`toUiGroup` 只取 `member.id`）。
- `GET /api/groups` 返回 `ApiGroup[]`。
- `GET /api/groups/check-name?name=` 返回 `{ available, reason? }`；**该端点缺失时**前端名称校验退回 `idle`，提交由 `POST` 的 409/422 兜底（设计 §2.2 已说明可选）。
- 名称规则前后端一致：`^[a-z][a-z0-9_-]{1,31}$`（设计 §2.4）。前端 `NAME_RE` 与后端 Pydantic regex 必须同源，改一处同步另一处。

---

## 6. 自测清单

后端未起也应全绿（降级路径）：

- [ ] 左栏「频道」已改名「群组」，hover 标题行末尾显「+」
- [ ] 点「+」弹出 `CreateGroupModal`，样式与「创建助手」一致（壳/间距/按钮）
- [ ] 名称输入：空→提示规则；非法（大写/数字开头）→红字 invalid；合法→`checking`→`ok`/`taken`
- [ ] 左栏搜索过滤成员；勾选进入右「已选成员」，× 可移除；计数随选变化
- [ ] 「创建」在名称非法/重复/校验中时禁用；提交中禁用防重复
- [ ] 创建成功：弹窗关闭 → 新群出现在左栏 → 自动进入该群（`section==='group'`）
- [ ] 后端在线：`POST /api/groups` 真发，新群 id 为后端 UUID
- [ ] 后端离线：catch 降级，新群用本地 `grp_*` id，UI 不卡
- [ ] 刷新页面：`fetchGroups()` 把后端群组并入左栏（与 seed mock 去重）
- [ ] `npm run build`（tsc）通过；无 `console.log`、无 `any`

> dev server CSS 异常时用 `npm run build && npm run preview`（记忆：Vite dev 有缓存问题）。

---

## 7. 风险与取舍

| 项 | 取舍 |
|----|------|
| 左栏 unread 红点 | 切到 `groupStore.groups` 后丢失（`Group` 无 `unread`）。属可接受回退，待消息系统接入后由未读计数恢复。 |
| 成员搜索 | 客户端过滤 `agentStore.agents`，不走 `GET /api/agents?search`。规模小，零额外请求；列表很大时再换服务端搜索。 |
| 协调者展示 | 创建弹窗不渲染协调者（「自动包含」文案提示即可），与设计 §5.2 一致。 |
| 群聊 | `sendGroup` 仍 mock（§0.2），本次不动。 |
