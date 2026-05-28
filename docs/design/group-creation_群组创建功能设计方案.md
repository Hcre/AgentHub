# 群组创建功能设计方案

> 基于 spec 现有架构定义，仅覆盖**创建群组**流程，不涉及消息路由/任务引擎等 M3 后续内容。

## 一、功能范围

- 创建群组频道（名称 + 描述 + 初始成员）
- 自动生成协调者 Agent
- 左侧栏「+」入口 → 弹出创建表单
- 成员选择器（复用已有 Agent 列表）
- 名称校验（服务端规则 + 唯一性）

不在此范围：群聊消息、@mention 路由、Coordinator 任务分解、成员增删（后续接口）。

## 二、API 设计

与 `docs/specs/04-commands_命令接口.md` 对齐，路径统一为 `/api/groups`。

### 2.1 创建群组

```
POST /api/groups

Request:
{
  "name": "design-review",           // 必填，规则见 §2.4
  "description": "设计评审频道",      // 可选，默认 ""
  "member_ids": ["uuid1", "uuid2"]   // 可选，初始成员 Agent ID 列表
}

Response 201:
{
  "id": "uuid",
  "name": "design-review",
  "description": "...",
  "coordinator": {
    "id": "uuid",
    "name": "协调者-design-review",
    "role": "Coordinator",
    "agent_system": "coordinator",
    "is_system": true
  },
  "members": [
    { "id": "uuid1", "name": "技术负责人 AI", "role": "..." },
    ...
  ],
  "created_at": "2026-05-24T..."
}

Error 409:
{ "detail": "群组名称 'design-review' 已存在" }

Error 422:
{ "detail": "群组名称格式不合法：仅允许小写字母、数字、连字符、下划线，2-32 字符" }
```

### 2.2 名称校验（可选，前端实时校验用）

```
GET /api/groups/check-name?name=design-review

Response 200:
{
  "available": true
}

Response 200:
{
  "available": false,
  "reason": "名称已存在"
}
```

如果不想加独立端点，前端也可直接用 409/422 错误响应处理。建议加上，改善 UX。

### 2.3 成员列表（复用已有接口）

```
GET /api/agents?search=keyword&page=1&limit=20
```

响应为 `ApiAgent[]`，前端类型已定义（`src/types/index.ts:283`）。Agent 列表本身就代表可选成员，不需要新建 `/api/workspace/members`。

### 2.4 名称规则

| 规则 | 说明 |
|------|------|
| 字符集 | `[a-z0-9_-]` |
| 长度 | 2-32 字符 |
| 首字符 | 必须为字母 |
| 唯一性 | 全局不重复 |

这些规则在 Pydantic schema 用 regex 校验。

## 三、数据模型

完全沿用 `docs/specs/03-data-model_数据模型.md` 定义：

### groups

```sql
CREATE TABLE groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    coordinator_id UUID NOT NULL,            -- 关联协调者 Agent，需在 agents 表创建后填入
    coordinator_config JSONB DEFAULT '{}',   -- 协调者模型/参数覆盖；创建时不暴露，运行时缺省读全局配置
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

**相对 spec（docs/specs/03-data-model §2.4）的差异**：

| 差异 | 说明 |
|------|------|
| `name` 加 `UNIQUE` | spec 为 `name TEXT NOT NULL`（无唯一约束）。本方案名称全局唯一（§2.4、§4.3 step1）依赖此约束，故显式加 `UNIQUE`。 |
| 新增 `coordinator_id` | spec 无此列。显式 FK 指向协调者 Agent，比仅靠 `coordinator_config` 更明确表达「哪个 Agent 是协调者」。 |
| 保留 `coordinator_config` | 列保留以对齐 spec，但**创建 API 不接收、不返回**；协调者运行时缺省读全局配置（`/api/settings.coordinator`，docs/specs/04-commands §2.0）。M3 编排需要按群覆盖模型时直接启用，无需再加 migration。 |

### group_members

```sql
CREATE TABLE group_members (
    id BIGSERIAL PRIMARY KEY,
    group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (group_id, agent_id)
);

CREATE INDEX idx_gm_group ON group_members (group_id);
CREATE INDEX idx_gm_agent ON group_members (agent_id);
```

## 四、后端实现

### 4.1 文件清单

```
backend/
├── app/
│   ├── infrastructure/db/models.py          # + GroupModel, GroupMemberModel
│   ├── domain/entities/group.py             # 新建：Group, GroupMember 实体
│   ├── domain/repositories/__init__.py      # + GroupRepository 接口
│   ├── infrastructure/repositories/
│   │   └── group_repository.py              # 新建：PostgresGroupRepository
│   ├── application/services/
│   │   └── group_service.py                 # 新建：GroupService
│   ├── application/commands/
│   │   └── group_commands.py               # 新建：CreateGroupCommand
│   ├── api/schemas/group.py                 # 新建：GroupCreate, GroupOut
│   ├── api/routers/groups.py               # 重写：完整 CRUD 端点
│   └── api/deps.py                          # 可选：get_group_service DI
├── alembic/versions/
│   └── 0003_create_groups.py               # 新建 Migration
```

### 4.2 层间调用

```
Router (groups.py)
  → Depends(get_group_service) → GroupService
      → GroupRepository (domain interface)
          → PostgresGroupRepository (infra impl)
      → AgentRepository (查已有 Agent)
      → 创建协调者 Agent（调用 AgentRepository.create）
      → 创建 Group 实体 → 持久化
      → 添加成员到 group_members
```

### 4.3 核心流程：GroupService.create()

```
1. 校验 name 唯一性
2. 校验 member_ids 中所有 Agent 存在（不存在 → 422）
3. 校验成员数量 ≤ 20（boundaries_边界矩阵.md 红线）
4. 创建协调者 Agent：
   - name: "协调者-{group.name}"
   - agent_system: "coordinator"
   - is_system: True
   - provider/model: 默认配置（暂用项目默认值）
5. 创建 Group（关联 coordinator_id）
6. 将 member_ids + coordinator_id 写入 group_members
7. 返回 GroupOut（含 coordinator + members 详情）
```

整个流程在一个数据库事务内完成。

### 4.4 边界条件

| 场景 | 处理 |
|------|------|
| name 空字符串 | 422 |
| name 不符合规则 | 422 + 规则说明 |
| name 重复 | 409 |
| member_ids 含不存在的 Agent | 422 + 指出无效 ID |
| member_ids 为空 | 允许，仅创建者（协调者）在群内 |
| member_ids 含重复 ID | 去重后处理 |
| 成员数 > 20 | 422 + "单群组 Agent 上限 20" |
| DB 连接失败 | 500（事务回滚） |

## 五、前端实现

### 5.1 文件清单

```
frontend/src/
├── api/groups.ts                  # 新建：groupsApi（create, list, checkName）
├── stores/groupStore.ts           # 修改：替换 mock 为真实 API
├── components/group/
│   └── CreateGroupModal.tsx       # 新建：创建群组弹窗
├── components/layout/
│   └── LeftPanel.tsx              # 修改：「频道」段重命名为「群组」+ 复用 SectionHeader 的「+」入口（见 §5.5）
```

### 5.2 CreateGroupModal 表单

样式参考 `docs/design/image.png`。**不含可见性（私密/公开）设计**——见 §六。
成员区为左右两栏：左侧搜索 + 勾选列表，右侧「已选成员」，频道创建者（协调者）自动包含、不在选择列表中。

```
┌────────────────────────────────────────────────────────┐
│  新建群组频道                                       ✕   │
│  和合适的队友一起开始共享对话。                         │
│                                                        │
│  频道名称 *                                            │
│  ┌──────────────────────────────────────────────┐     │
│  │ design-review                                  │     │
│  └──────────────────────────────────────────────┘     │
│  小写字母、数字、连字符或下划线。        ✓ 名称可用    │  ← 实时校验（debounce 300ms）
│                                                        │
│  描述                                                  │
│  ┌──────────────────────────────────────────────┐     │
│  │ 这个频道用于什么?                              │     │
│  │                                                │     │
│  └──────────────────────────────────────────────┘     │
│                                                        │
│  成员                                       已选择 0 位│
│  ┌──────────────────────────┐ ┌─────────────────────┐  │
│  │ 🔍 搜索工作区成员        │ │ 已选成员            │  │
│  ├──────────────────────────┤ │ 频道创建者会自动    │  │
│  │ ☐ 👤 技术负责人 AI       │ │ 包含在内。          │  │
│  │      ai-6a12…@id.helio.im│ │                     │  │
│  │ ☐ 👤 Content writer AI   │ │                     │  │
│  │      ai-6a0e…@id.helio.im│ │   还没有选择        │  │
│  │ ☐ 👤 Researcher AI       │ │   其他成员。        │  │
│  │      ai-6a0e…@id.helio.im│ │                     │  │
│  └──────────────────────────┘ └─────────────────────┘  │
│                                                        │
│                              [取消]            [创建]  │
└────────────────────────────────────────────────────────┘
```

### 5.3 Store 改造

`groupStore.ts` 变更：

1. **删掉** `simulateGroupReply` 函数 + MOCK SEAM 整段
2. **删掉** `import { groups, coordinator, groupMessages }` 的 mock 数据引用
3. 新增 action：`fetchGroups()` → `GET /api/groups`
4. 新增 action：`createGroup(input)` → `POST /api/groups`
5. `sendGroup` 保留但改为调用 `POST /api/groups/{id}/messages`（或继续 mock，待 M3 消息系统就绪后替换）

启动时调用 `fetchGroups()` 初始化数据。

### 5.4 创建流程

```
左栏「群组」段「+」点击（见 §5.5）
  → open: CreateGroupModal
  → 输入 name → debounce 300ms → GET /api/groups/check-name
  → 显示名称可用/不可用状态
  → 搜索工作区成员 → GET /api/agents?search=...（debounce）
  → 勾选成员（进入右侧「已选成员」，协调者自动包含）
  → 点击「创建」
  → POST /api/groups { name, description, member_ids }
  → 201: 关闭弹窗 → 刷新频道列表 → 自动进入新频道
  → 4xx: 弹窗内显示错误信息
```

### 5.5 LeftPanel 群组入口改造（具体改法）

目标文件：`frontend/src/components/layout/LeftPanel.tsx`。

**定位**：现有「频道」段标题在 `LeftPanel.tsx:148`：

```tsx
<SectionHeader label="频道" collapsed={!openCh} onToggle={() => setOpenCh((v) => !v)} />
```

下方列表 `channels.map(...)`（`:151-159`）点击调用 `openGroup(c.id)`——这些「频道」本就是群组，重命名为「群组」语义一致。

**改动 1 — 重命名 +「+」入口。** `SectionHeader` 已内置 `onAdd`/`addTitle`，会在标题行末尾渲染一个 hover 显形的「+」按钮（与「AI 队友」段 `:164-170` 同一套实现，**无需改 SectionHeader 组件**）：

```tsx
<SectionHeader
  label="群组"
  collapsed={!openCh}
  onToggle={() => setOpenCh((v) => !v)}
  onAdd={() => setGroupCreateOpen(true)}
  addTitle="创建群组"
/>
```

**改动 2 — 新增弹窗开关 state**（与 `createOpen` 并列，`:104`）：

```tsx
const [groupCreateOpen, setGroupCreateOpen] = useState(false)
```

**改动 3 — 挂载弹窗**（紧随现有 `CreateAgentModal`，`:272`；import 与 `:7` 并列）：

```tsx
import { CreateGroupModal } from '../group/CreateGroupModal'
// ...
<CreateGroupModal open={groupCreateOpen} onClose={() => setGroupCreateOpen(false)} />
```

创建成功后由 `CreateGroupModal` 调 `groupStore.createGroup()` → 刷新列表 → `openGroup(newId)` 进入新群（见 §5.3/§5.4）。

**注意事项**：

- 「+」当前为 hover 显形（`SectionHeader:79` 的 `opacity-0 group-hover:opacity-100`）。如需常显，把该 `<button>` 的 className 去掉 `opacity-0`/`group-hover:opacity-100` 即可；但建议与「AI 队友」段保持一致（hover 显形）。
- **不要动** `data/mock.ts:76` 的「频道」标签——那是中间面板的 `centerTabs` Tab，与左栏群组段是两回事，不在本次范围。

## 六、不变更范围声明

以下功能**不在本次实现**，避免扩大范围：

- ❌ 群聊消息发送/接收（前端 `sendGroup` 保持 mock，仅将创建功能接真实 API）
- ❌ 协调者任务分解/LLM 编排
- ❌ @mention 路由（auto/direct）
- ❌ Harness DAG 编译
- ❌ 成员增删 API（`POST/DELETE /api/groups/{id}/members`）
- ❌ 群组编辑/删除
- ❌ 审批流程
- ❌ 文件/任务 Tab
- ❌ 频道可见性（私密/公开）—— 参考图 `image.png` 含该控件，但本方案**刻意不实现**：可见性会引入工作区级访问控制（谁可见 / 可搜索 / 可加入），超出「创建群组」范围。数据模型不加 `visibility` 字段，前端不渲染该区块。

这些属于 M3 后续任务，PRD §Milestones 已有规划。

## 七、实现顺序

| 步骤 | 内容 | 估时 |
|------|------|------|
| 1 | Migration：创建 groups + group_members 表 | 0.5h |
| 2 | ORM Model + Domain Entity | 0.5h |
| 3 | GroupRepository（接口 + Postgres 实现） | 0.5h |
| 4 | GroupService（含协调者自动创建） | 1h |
| 5 | Pydantic Schema | 0.5h |
| 6 | Router（POST + GET + check-name） | 0.5h |
| 7 | 前端 API 模块 `groups.ts` | 0.5h |
| 8 | CreateGroupModal 组件 | 1.5h |
| 9 | LeftPanel 「+」按钮 + Store 改造 | 0.5h |
| 10 | 联调 + 边界测试 | 1h |
| **合计** | | **~7h** |

## 八、参考

| 文档 | 相关内容 |
|------|---------|
| `docs/specs/01-architecture_架构定义.md` §2.2 | 群组与协调者定义 |
| `docs/specs/03-data-model_数据模型.md` §2.4-2.5 | groups/group_members DDL |
| `docs/specs/04-commands_命令接口.md` §2.2 | Group API 规范 |
| `conventions/99-boundaries_边界矩阵.md` §二 | 群组管理权限 + 20 人上限 |
| `conventions/arch-rules_架构红线.md` | 架构约束（五层洋葱，依赖方向） |
| `frontend/src/components/group/HANDOFF.md` | 前端 mock seam 说明 |
