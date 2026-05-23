# AgentHub PRD — 产品需求文档（⚠️ 已废弃）

> ⚠️ **v4 已取代**。请阅读 `PRD_AgentHub_v4_统一方案.md`（唯一权威版本）。
>
> 本文件保留为历史参考，不再维护。
>
> 版本：v1.0 | 日期：2026-05-21 | 状态：已废弃

---

## 一、产品概述

### 1.1 产品定位

IM 聊天式多 Agent 协作平台。用户通过类飞书聊天界面与 AI Agent 对话，支持单聊、群聊（@mentions 多 Agent 协作）、任务自动分解与并行调度。

### 1.2 核心价值

- **类 IM 交互**：用最自然的聊天方式调度 AI Agent，无需学习命令行或 API
- **多 Agent 协作**：群组内协调者自动分解任务、分配 Agent、合并结果
- **富媒体产物**：代码 Diff、网页预览、文件附件直接在聊天流中预览和操作
- **任务管理**：同一套数据支持 IM 视角和看板视角，子任务从属于父任务


### 1.4 Non-Goals（本期明确不做）

| 条目 | 原因 |
|------|------|
| 移动端原生 App | 优先保证 Web 端完整体验，移动端 P3 |
| 自研 Agent 引擎（底层 LLM 推理） | Agent 能力全部通过适配器层调用外部平台 API |
| 完整 CI/CD 流水线 | v1 聚焦聊天协作+产物预览，部署发布 P2 |
| 语音/视频通话 | 不在 IM 文字协作范式中 |

### 1.5 User Personas

**主要 Persona：小飞 — 独立全栈开发者**

小飞日常用 Claude Code 写后端、用 Codex 写前端。厌倦在两个终端间反复复制上下文。希望在一个界面上像用微信一样：新建群聊，拉入"前端 Agent"和"后端 Agent"，说一句需求，两个 Agent 各自产出、自动协调。

**次要 Persona：阿豆 — 非技术产品经理**

阿豆不会写代码但有清晰的产品想法。希望像和设计师沟通一样和 AI Agent 对话，Agent 直接生成可预览的网页，在聊天流中看到效果、提出修改意见，不打开任何代码编辑器。

### 1.6 Core User Stories（BDD 格式）

**Story 1 — 单聊模式完成任务**
> 与单个 Agent 进行 1v1 对话并下达编码任务，快速获得代码产出并在聊天流中预览结果。

- [ ] Given 用户创建了与 "Claude Code" Agent 的私聊，when 用户发送"用 React 写一个计数器组件"，then Agent 返回代码块 + 可点击的网页预览卡片
- [ ] Given Agent 已返回代码，when 用户点击"预览"卡片，then 在右侧面板/弹窗中渲染可交互的页面
- [ ] Given 对话已有多轮历史，when 用户发送"把按钮改成蓝色"，then Agent 基于上下文理解修改意图并返回 Diff 视图

**Story 2 — 群聊模式多 Agent 协作**
> 在群聊中 @协调者 或直接发送任务，由协调者自动协调分工，前后端代码在一个对话中协同产出。

- [ ] Given 用户创建群聊并拉入 FrontendAgent + BackendAgent，when 用户发送"帮我做一个博客系统，前端 React + 后端 Express"，then 协调者自动拆解为前端和后端子任务并分派
- [ ] Given 协调者分派完毕，when 子 Agent 完成各自任务，then 各 Agent 产出（前端代码 + 后端代码 + API 文档）按依赖关系在群聊流中展示
- [ ] Given 两个子任务无依赖，when 协调者判断可并行，then 两个 Agent 并行执行（不串行等待）
- [ ] Given 某个子 Agent 执行失败，when 协调者检测到失败，then 在群聊中报告降级结果并尝试重新分派

**Story 3 — 产物内联预览与迭代**
> 在聊天流中直接预览 Agent 产出物（网页、代码 Diff、文档），无需切换工具完成"需求→预览→修改→确认"闭环。

- [ ] Given Agent 返回 HTML/CSS/JS 代码，when 消息中含网页产物，then 聊天流中渲染网页预览卡片（内联 iframe）
- [ ] Given Agent 返回代码修改，when 以 Diff 格式呈现，then 聊天流中渲染 Diff 视图（绿色/红色标注增删行）
- [ ] Given 用户选中聊天流中一段代码并发送"把这个函数改成 async"，when 消息发出，then Agent 理解引用上下文并仅修改指定代码段
- [ ] Given Agent 返回 Markdown 文档，when 用户点击文档卡片，then 展开渲染后的富文本视图

**Story 4 — 对话上下文管理与 Agent 切换**
> 在不同 Agent 之间通过 Harness 自动传递关键上下文，用户无需重复解释项目背景。

- [ ] Given 用户在与 Agent A 的对话中已讨论项目需求，when 用户创建新对话并选择 Agent B，then Harness 自动携带 Agent A 的关键上下文摘要注入 Agent B
- [ ] Given 用户在群聊中触发协调者分解任务，when 协调者将子任务分派给 Worker Agent，then Worker 自动获得 Harness 构建的 GlobalContext（任务定义+共享制品引用+需求摘要）
- [ ] Given 用户在某条消息上 Pin，when 后续 Agent 在此对话中回复，then Pin 消息始终作为长期上下文可用

**Story 5 — 创建自定义 Agent**
> 通过表单或对话创建自定义 Agent（System Prompt + 模型配置 + 工具集），为特定场景定制 Agent 行为。

- [ ] Given 用户点击"新建 Agent"进入表单，when 填写 name/role/provider/model/api_key 并提交，then Agent 创建成功并出现在列表中
- [ ] Given 用户点击"对话式创建"，when 用自然语言描述 Agent 的职责和能力，then 系统自动生成 System Prompt 草案 + 推荐能力标签供用户确认
- [ ] Given 自建 Agent 已被添加到群聊，when 协调者分派任务，then 自建 Agent 和内置 Agent 平等参与调度

---

## 二、功能需求

### 2.1 Agent 管理

#### 2.1.1 Agent 创建

添加 Agent 时需要传输的**必要信息**（其他字段可后续修改）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | Agent 唯一名称，如 "FrontendAgent" |
| avatar | string(url) | 是 | Agent 头像 URL |
| role | string | 是 | Agent 角色描述，如 "前端开发专家" |
| provider | enum | 是 | LLM 提供商：`anthropic` / `openai` / `azure` |
| model | string | 是 | 模型名称，如 `claude-sonnet-4-20250514` |
| api_key | string | 是 | 对应 provider 的 API Key（加密存储） |
| skills | string[] | 否 | 初始技能列表，如 `["react", "typescript"]` |
| system_prompt | string | 否 | 初始 system prompt，不填则使用默认模板 |

**对话式创建（备选方式）**：

用户可用自然语言描述 Agent 职责，系统自动生成 System Prompt 草案和能力标签推荐：
- 输入："你是一个专攻 Python 数据分析的 Agent，擅长 pandas 和 matplotlib"
- 系统输出 → `system_prompt` 草案 + `capability_tags: ["python", "pandas", "matplotlib"]`
- 用户确认后，补填 provider/model/api_key → 创建

**验收标准**：
- [ ] 表单式：填写必填字段后点击"添加"，Agent 创建成功并出现在列表中
- [ ] 对话式：自然语言描述 → 系统生成草案 → 用户确认后创建
- [ ] API Key 在前端输入框使用密码模式，传输时加密
- [ ] 相同 name 的 Agent 不允许重复创建

#### 2.1.2 Agent 属性（完整）

除创建时的字段外，Agent 还包含以下**系统自动维护**的属性：

| 属性 | 类型 | 维护方式 | 说明 |
|------|------|---------|------|
| id | UUID | 系统生成 | Agent 唯一标识 |
| status | enum | 系统检测 | `online` / `offline` / `busy` / `error` |
| workload | int | 系统更新 | 当前正在执行的任务数 |
| channels | UUID[] | 加入/退出群组时更新 | 所属群组 ID 列表 |
| workspace | UUID | 系统创建 | 虚拟命名空间 ID（逻辑隔离） |
| tasks | UUID[] | 任务分配时更新 | 已分配的任务 ID 列表 |
| activities | Activity[] | 系统记录 | Agent 活动日志 |
| capability_tags | string[] | 可手动修改 | 能力标签，用于协调者任务匹配 |
| memory | MemoryConfig | 可查看/编辑 | L1-L4 记忆配置 |
| settings | AgentSettings | 可修改 | Agent 详细设置 |
| created_at | datetime | 系统生成 | 创建时间 |
| updated_at | datetime | 系统更新 | 最后修改时间 |

#### 2.1.3 Agent 详情页

点击 Agent 进入详情页，包含以下 Tab：

| Tab | 内容 |
|-----|------|
| **概览** | 基本信息（名称、头像、角色、状态、负载、所属群组） |
| **能力** | capability_tags 标签列表，支持添加/删除 |
| **记忆** | 系统管理的 L1-L4 记忆，支持筛选、查看详情、编辑 |
| **任务** | 分配给此 Agent 的任务列表（进行中/已完成） |
| **活动** | Agent 的活动日志时间线 |
| **设置** | 模型、API Key、system_prompt、max_tokens、并发数等 |

#### 2.1.4 Agent 权限控制

| 操作 | 默认权限 | 审批要求 |
|------|---------|---------|
| 读取文件 | 自动 | 无需审批 |
| 创建/编辑文件 | 自动 | 无需审批 |
| 删除文件 | 需审批 | 用户在收件箱中确认 |
| Git push | 需审批 | 用户在收件箱中确认 + Diff 预览 |
| Docker 部署 | 需审批 | 用户在收件箱中确认 + 部署预览 |
| 访问外部网络 | 需审批 | 每次请求确认 |

---

### 2.2 群组功能（= 频道）

群组 = 频道，Agent 可以同时存在于多个群组中。

#### 2.2.1 群组创建

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 群组名称 |
| description | string | 否 | 群组描述 |
| members | UUID[] | 否 | 已选 Agent ID 列表（可后续添加） |

**关键机制**：群组创建时自动生成一个**协调者**（Coordinator = AI + Harness）。协调者是群组的常驻角色，**在群组成员列表中可见**（显示为系统蓝色标识，不可移除），用户可直接 @协调者 指定任务。

协调者身份标识：
- 名称：`协调者-{群组名称}`（如 "协调者-前端开发组"）
- 头像：系统预设（区分于普通 Agent）
- 角色标签：`系统 · 任务协调`
- `is_system=True`，provider=`system`（内部路由，使用系统默认 Orchestrator 模型）

#### 2.2.2 协调者工作机制

```
用户/成员发送消息到群组
  │
  ▼
协调者程序接收消息（包含：对话上下文 + 群组内所有 Agent 信息）
  │
  ├─ 用户 @协调者 或 消息包含任务意图（自动检测）
  │    │
  │    ▼
  │   协调者 AI 进行任务分解
  │    │  → 分析需求 → 生成子任务列表 → 匹配群组内 Agent 能力
  │    │  → 返回结构化 JSON（子任务 + 被分配的 Agent）
  │    │
  │    ▼
  │   协调者程序（Harness）校验 → 编译 DAG → 分发执行
  │    │
  │    ▼
  │   群组内 Agent 并行/串行执行 → 结果合并 → 回复到群聊
  │
  └─ 非任务（普通聊天消息 / @指定 Agent）
       → 不触发任务分解，仅作为对话上下文保留
       → @指定 Agent 的消息直接路由到该 Agent，协调者不介入
```

#### 2.2.3 群组消息发送

| 功能 | 操作 | 行为 |
|------|------|------|
| 发送给全体 | 直接发送（不 @任何人 或 @All） | 消息进入群聊，全体可见；系统自动检测是否有任务意图 |
| @协调者 | `@协调者 消息内容` | 显式触发协调者进行任务分解，不自动检测 |
| @指定 Agent | `@AgentName 消息内容` | 仅被 @ 的 Agent 处理该消息，协调者不介入 |
| @All | `@All 消息内容` | 群组内所有 Agent 响应（不含协调者） |

**协调者触发判定**：

| 条件 | 行为 |
|------|------|
| 消息中 @协调者 | 直接触发协调者任务分解 |
| 未 @任何人，消息包含任务意图（LLM 快速分类判断） | 自动触发协调者 |
| @指定 Agent | 直接路由到目标 Agent，不触发协调者 |
| 普通聊天（无任务意图） | 不触发，仅作为对话上下文 |

**验收标准**：
- [ ] 用户 @协调者 发送任务指令时，协调者进行任务分解
- [ ] 未 @ 任何人发送任务指令时，系统自动检测意图并触发协调者
- [ ] @指定 Agent 时，只有被 @ 的 Agent 响应，协调者不介入
- [ ] 协调者在群组成员列表中可见（蓝色系统标识），不可移除
- [ ] 协调者的分解结果以结构化消息卡片展示（子任务列表 + 负责人）

#### 2.2.4 多会话并行

- 左侧会话列表支持同时打开多个对话窗口
- 每个群组/私聊是独立会话，互不干扰
- 会话列表按最近活跃时间排序
- 支持会话置顶、搜索、归档

**验收标准**：
- [ ] 同时打开 3 个群组窗口 + 2 个私聊窗口，各窗口消息不串
- [ ] 关闭窗口后重新打开，历史消息完整保留

#### 2.2.5 上下文连续

每个会话保持完整聊天历史，分为三层：

| 层级 | 范围 | 存储 | 用途 |
|------|------|------|------|
| **热上下文** | 最近 15-20 条消息 | Redis（实时） | 直接注入 LLM prompt |
| **长期上下文** | 被 pin 的关键消息 + 摘要 | PostgreSQL | 跨会话持久化上下文 |
| **历史预览** | 更早的对话摘要占位 | 本地文件系统 | 用户可展开查看完整对话 |

**验收标准**：
- [ ] Agent 能基于最近的对话历史理解上下文，支持多轮迭代
- [ ] 用户可 pin 任意消息作为长期上下文
- [ ] 长对话自动压缩为摘要，不撑爆 LLM 上下文窗口

#### 2.2.6 产物内联

Agent 回复中的富媒体产物在聊天流中直接展示：

| 产物类型 | 展示方式 | 交互 |
|---------|---------|------|
| **代码 Diff** | 内联 Monaco Diff Editor | 展开/折叠、行内批注、接受/拒绝修改 |
| **网页预览** | 内嵌 iframe 卡片 | 点击展开全屏预览 |
| **文件附件** | 文件卡片（文件名、大小、类型） | 下载、预览 |
| **文档渲染** | 文档预览卡片（Markdown/PDF） | 点击全屏浏览 |
| **PPT 浏览** | P2 待实现 | - |
| **部署状态** | 状态卡片（构建中/成功/失败） | 查看日志、访问 URL |
| **任务计划** | 结构化的子任务列表卡片 | 查看详情、修改分配 |

**验收标准**：
- [ ] 代码 Diff 在聊天中渲染为可视化对比（diff2html）
- [ ] 网页预览以 iframe 形式嵌入聊天窗口
- [ ] 点击代码卡片可展开全屏代码编辑器（Monaco）
- [ ] 支持选中代码 → 在聊天中描述修改 → 对话式局部修改（P2）

---

### 2.3 私聊功能

#### 2.3.1 入口

- 在 Agent 列表或群组成员列表中点击 Agent 头像 → 进入私聊窗口
- 私聊窗口与群聊窗口结构一致（消息区域 + 产物内联）

#### 2.3.2 功能

| 功能 | 描述 |
|------|------|
| 派发任务 | 直接向该 Agent 发任务，不走群组协调者 |
| 上下文连续 | 私聊保持完整聊天历史，三层上下文机制 |
| 产物内联 | 与群聊相同的富媒体产物展示 |
| 预览卡片 | Diff 预览、网页预览、文件预览 |
| 记忆可见 | 对话自动纳入 Agent 的 L1 短期记忆 |

**验收标准**：
- [ ] 私聊消息不干扰群聊上下文
- [ ] 私聊历史可独立查看，不被群聊消息污染

---

### 2.4 任务管理

聊天中派发的任务 = 任务界面的任务，**同一套数据**。

#### 2.4.1 任务模型

```
父任务 (Task)
  ├── 子任务 1 (SubTask) → 负责人: FrontendAgent → 状态: completed
  ├── 子任务 2 (SubTask) → 负责人: BackendAgent  → 状态: running
  └── 子任务 3 (SubTask) → 负责人: ReviewerAgent  → 状态: pending (依赖 1,2)
```

| 属性 | 类型 | 说明 |
|------|------|------|
| id | UUID | 任务唯一标识 |
| title | string | 任务标题（从用户需求中提取） |
| description | string | 任务描述 |
| status | enum | `pending` / `queued` / `running` / `completed` / `failed` / `cancelled` |
| priority | enum | `critical` / `high` / `medium` / `low` |
| assignee | UUID | 负责人/负责群组 ID |
| due_date | datetime | 截止日期 |
| tags | string[] | 标签 |
| parent_task_id | UUID? | 父任务 ID（为 null 则为根任务） |
| subtasks | UUID[] | 子任务 ID 列表 |
| source | enum | `chat` (聊天派发) / `manual` (手动创建) |
| session_id | UUID | 来源会话 ID（聊天派发时关联） |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

#### 2.4.2 任务列表界面

| 功能 | 描述 |
|------|------|
| **筛选** | 按状态、优先级、负责人、时间范围、标签筛选 |
| **排序** | 按创建时间、截止日期、优先级排序 |
| **视图** | 列表视图 / 看板视图（按状态分列）/ 甘特图（P2） |
| **搜索** | 按标题/描述关键词搜索 |
| **批量操作** | 批量修改状态、批量分配负责人 |

#### 2.4.3 创建任务（手动）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 是 | 任务标题 |
| description | string | 否 | 任务描述（Markdown） |
| assignee | UUID | 否 | 负责人 Agent 或负责群组 |
| due_date | datetime | 否 | 截止日期 |
| priority | enum | 否 | 优先级，默认 `medium` |
| tags | string[] | 否 | 标签列表 |
| parent_task_id | UUID | 否 | 从属的父任务 |

**验收标准**：
- [ ] 聊天派发的子任务自动出现在任务列表中，且显示从属的父任务
- [ ] 任务列表筛选条件可组合使用
- [ ] 点击任务可展开详情（子任务列表、执行日志、产物）

#### 2.4.4 父任务详情页

展示：
- 父任务基本信息 + 状态
- 子任务 DAG 可视化（依赖关系图）
- 各子任务执行状态（实时更新）
- 产物汇总（所有子任务的输出合并）

---

### 2.5 收件箱

#### 2.5.1 分类

| 分类 | 内容 |
|------|------|
| **全部** | 所有通知的时间线汇总 |
| **审批** | Agent 操作审批请求（文件删除、部署、Git push、外网访问等） |
| **任务** | 任务状态变更通知（分配、完成、失败、超时） |
| **日历** | 任务截止日期日历视图 |

#### 2.5.2 审批流程

```
Agent 请求审批（如删除文件）
  │
  ▼
收件箱 → 审批 Tab 出现待处理项
  │
  ├─ 用户点击 APPROVE → Agent 继续执行
  └─ 用户点击 REJECT  → 任务取消 / Agent 寻找替代方案
```

审批项展示：
- 发起者（哪个 Agent）
- 操作描述（要做什么）
- 影响范围（文件路径 / 部署目标 / 网络目标）
- Diff 预览（涉及代码变更时）
- APPROVE / REJECT 按钮

#### 2.5.3 日历视图

- 以月/周/日视图展示任务截止日期
- 过期任务标红
- 点击日期查看当天截止的任务列表

**验收标准**：
- [ ] 有新审批请求时，收件箱图标显示未读 Badge
- [ ] 审批操作后 Agent 立即收到结果继续/中止
- [ ] 日历中任务状态变更后自动同步

---

## 三、非功能需求

### 3.1 性能

| 指标 | 目标 |
|------|------|
| 消息发送到显示延迟 | < 500ms |
| WebSocket 重连时间 | < 3s |
| 流式输出首 token 延迟 | < 2s |
| 任务列表加载（100 条） | < 1s |
| 并发会话支持 | ≥ 20 个会话同时在线 |

### 3.2 安全

- API Key 使用 AES-256-GCM 加密存储
- 数据传输使用 TLS 1.3
- Agent 文件操作禁止路径遍历（`.env`、`.git` 等）
- WebSocket 连接需要 JWT 鉴权
- 所有 Agent 操作日志保留 30 天

### 3.3 可用性

- 前端支持暗色/亮色主题
- 支持中英文切换（P2）
- 浏览器兼容：Chrome/Firefox/Edge 最新两个大版本
- 移动端响应式布局（P3）

---

## 四、UI 布局草案

### 4.1 主界面布局

```
┌─────────┬──────────────────────────────┬─────────────┐
│  左侧    │        中间                   │   右侧       │
│ 导航栏   │       聊天区域                │  详情面板    │
│         │                              │ (可收起)    │
│ ┌─────┐ │ ┌──────────────────────────┐ │             │
│ │会话  │ │ │ 群组名称 / Agent 名称    │ │ Agent 详情  │
│ │列表  │ │ │ ─────────────────────── │ │ 任务详情    │
│ │     │ │ │                        │ │ 产物预览    │
│ │🔍   │ │ │ 消息 1                 │ │             │
│ │📌   │ │ │ 消息 2 (含 Diff 卡片)   │ │             │
│ │     │ │ │ 消息 3 (含预览卡片)     │ │             │
│ │     │ │ │                        │ │             │
│ │     │ │ ├────────────────────────┤ │             │
│ │     │ │ │ 输入框                 │ │             │
│ └─────┘ │ └──────────────────────────┘ │             │
├─────────┤                              ├─────────────┤
│ Tab 切换│                              │             │
│ □ Agent │                              │             │
│ □ 任务  │                              │             │
│ □ 收件箱│                              │             │
└─────────┘                              └─────────────┘
```

### 4.2 左侧导航

- **会话列表**：群组 + 私聊，按活跃时间排序
- **Agent 列表**：所有已添加的 Agent，支持搜索和筛选
- **任务**：切换到任务管理视图
- **收件箱**：切换到收件箱视图（带未读 Badge）

### 4.3 右侧面板

上下文相关的详情面板（可切换 Tab）：
- 当前会话中 @ 的 Agent 详情
- 当前任务的子任务列表和进度
- 当前 Diff 的全屏预览

---

## 五、数据模型概要

### 5.1 核心实体关系

```
User ──┬── Session (会话) ──── Message (消息)
       │       │                    │
       │       ├── GroupSession     ├── text
       │       └── PrivateSession   ├── diff
       │                            ├── preview_card
       │                            ├── task_plan
       │                            └── approval_request
       │
       ├── Agent ──── AgentConfig (模型/APIKey/Settings)
       │    │
       │    ├── capability_tags[]
       │    ├── channels[] (所属群组)
       │    ├── workspace (虚拟命名空间)
       │    └── memory_config
       │
       ├── Group (群组/频道) ──── Coordinator (协调者，1:1)
       │    │
       │    ├── members[] (Agent 列表)
       │    └── sessions[] (群组内会话)
       │
       └── Task (任务)
            ├── parent_task_id (从属关系)
            ├── assignee
            ├── subtasks[]
            └── task_events[] (事件日志)
```

### 5.2 最简 MVP 表清单

| 表 | 核心字段 | 存储引擎 |
|----|---------|---------|
| users | id, name, email, avatar | PostgreSQL |
| agents | id, name, avatar, role, provider, model, api_key_encrypted, status, settings | PostgreSQL |
| agent_capabilities | agent_id, tag | PostgreSQL |
| groups | id, name, description, coordinator_config | PostgreSQL |
| group_members | group_id, agent_id | PostgreSQL |
| sessions | id, type(group/private), title, created_at | PostgreSQL |
| messages | id, session_id, role, content, content_type, metadata, reply_to, status | PostgreSQL |
| tasks | id, title, description, status, priority, assignee, due_date, parent_task_id, session_id | PostgreSQL |
| task_events | id, task_id, event_type, event_data, actor, idempotency_key | PostgreSQL |
| task_artifacts | id, task_id, step_name, status, input, output, tokens_used | PostgreSQL |
| notifications | id, user_id, type(approval/task/system), title, content, is_read, action_url | PostgreSQL |

---

## 六、API 概要

### 6.1 Agent 相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agents` | 创建 Agent（传入必要信息） |
| GET | `/api/agents` | 获取 Agent 列表（支持筛选） |
| GET | `/api/agents/{id}` | 获取 Agent 详情 |
| PATCH | `/api/agents/{id}` | 更新 Agent 配置/设置 |
| DELETE | `/api/agents/{id}` | 删除 Agent |
| GET | `/api/agents/{id}/tasks` | 获取 Agent 的任务列表 |
| GET | `/api/agents/{id}/activities` | 获取 Agent 活动日志 |
| GET | `/api/agents/{id}/memory` | 获取 Agent 记忆（L1-L4） |
| PATCH | `/api/agents/{id}/memory` | 编辑 Agent 记忆 |

### 6.2 群组相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/groups` | 创建群组（自动生成协调者） |
| GET | `/api/groups` | 获取群组列表 |
| GET | `/api/groups/{id}` | 获取群组详情 |
| PATCH | `/api/groups/{id}` | 修改群组名称/描述 |
| DELETE | `/api/groups/{id}` | 删除群组 |
| POST | `/api/groups/{id}/members` | 添加 Agent 到群组 |
| DELETE | `/api/groups/{id}/members/{agent_id}` | 从群组移除 Agent |

### 6.3 会话与消息

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sessions` | 创建会话（群组/私聊） |
| GET | `/api/sessions` | 获取会话列表 |
| GET | `/api/sessions/{id}/messages` | 获取消息历史（分页+压缩） |
| POST | `/api/sessions/{id}/messages` | 发送消息 |
| WS | `/ws/sessions/{id}` | WebSocket 实时通信 + 流式输出 |
| POST | `/api/messages/{id}/pin` | Pin 消息为长期上下文 |

### 6.4 任务相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/tasks` | 创建任务（手动） |
| GET | `/api/tasks` | 获取任务列表（支持筛选/排序） |
| GET | `/api/tasks/{id}` | 获取任务详情（含子任务） |
| PATCH | `/api/tasks/{id}` | 更新任务属性 |
| GET | `/api/tasks/{id}/events` | 获取任务事件日志 |
| GET | `/api/tasks/{id}/artifacts` | 获取任务产物 |

### 6.5 收件箱

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/inbox` | 获取通知列表（支持分类筛选） |
| GET | `/api/inbox/unread-count` | 获取未读通知数 |
| PATCH | `/api/inbox/{id}/read` | 标记通知为已读 |
| POST | `/api/approvals/{id}/approve` | 审批通过 |
| POST | `/api/approvals/{id}/reject` | 审批拒绝 |

---

## 七、AI 协作规范沉淀

> 关键交付物：AI 协作能力占评审权重 30%，需在代码仓库中体现。

| 规范类型 | 内容要求 | 示例产出 |
|---------|---------|---------|
| **Spec 文档** | 每个核心功能模块的开发规格说明：输入/输出/边界条件/测试用例 | `specs/orchestrator.md`、`specs/chat-ui.md`、`specs/agent-management.md` |
| **Skill 定义** | 与 AI 协作时使用的 Skill 模板：如何让 AI 生成符合项目规范的代码 | `skills/react-component.skill`、`skills/api-endpoint.skill` |
| **Rules 规则** | 项目级编码规范、架构约束、命名约定，确保 AI 生成的代码风格一致 | `rules/coding-style.rule`、`rules/api-design.rule` |
| **Harness 流程** | 从需求到代码的协作工作流：何时用哪个 Agent、如何 review、如何合并产物 | `harness/workflow.md` |

---

## 八、技术依赖风险评估

| 依赖项 | 用途 | 风险等级 | 缓解措施 |
|--------|------|---------|---------|
| LLM Provider API（Anthropic/OpenAI/Azure） | 驱动 Agent + 协调者的 LLM 推理 | High — API 稳定性与速率限制 | 实现重试机制 + 指数退避；协调者降级为手动 @ 模式 |
| WebSocket 长连接 | 前端与后端实时消息推送 | Med — 断连风险 | PostgreSQL 持久化兜底 + 自动重连（< 3s） |
| Celery + Redis | 任务队列 + 缓存 + Pub/Sub | Med — 额外运维复杂度 | Docker Compose 一键部署；MVP 可降级为内存队列 |
| Monaco Editor + diff2html | 代码 Diff 视图 | Low — 成熟开源库 | 备选：纯文本 Diff 展示 |
| iframe Sandbox | 网页预览安全性 | Low — 浏览器原生支持 | CSP header + 独立源 |

**开发前需确认的开放问题**：

- [ ] Claude Code / Codex / OpenCode 的实际调用方式与 API 可用性验证
- [ ] 协调者 Prompt 策略：任务拆解粒度如何定义？是否需要预定义任务模板？
- [ ] 前端聊天 UI 实现方案：自研 vs 组件库？需评估开发成本与定制灵活度

---

## 九、里程碑计划

### 比赛里程碑（共 20 天）

| 里程碑 | 日期 | 交付标准 | 成功闸门 |
|--------|------|---------|---------|
| **M1 — 环境搭建 + 技术验证** | 5/20-22 | API 环境就绪、适配器层框架、前后端脚手架 | 成功调用至少 1 个外部 Agent API 并返回结果 |
| **M2 — 单聊 MVP** | 5/23-27 | 对话列表 + 1v1 聊天 + 消息流 + 代码块渲染 + 流式输出 | 用户能和一个 Agent 完成"需求→代码→预览"闭环 |
| **M3 — 群聊 + 协调者** | 5/28-6/1 | 群聊创建 + @协调者/自动检测 + 任务拆解分派 + DAG 编译 + 并行调度 | 复杂任务自动拆解分发到 ≥ 2 个 Agent，产物在群聊中依次展示 |
| **M4 — 产物预览 + 迭代** | 6/2-5 | 网页预览卡片 + Diff 视图 + 上下文 Pin + 自建 Agent（表单+对话式） | 用户在聊天流中预览、修改、确认产物 |
| **M5 — 文档 + 视频 + 打磨** | 6/6-9 | PRD 终稿 + 架构文档 + Spec/Skill/Rules 沉淀 + 3min Demo 视频 | 全部交付物完整，Demo 视频覆盖 5 个 Core User Stories |
| **M6 — 提交** | 6/10 | 代码仓库整理、README 完善、最终提交 | 所有材料通过提交渠道送达 |

### 降级策略

| 阻塞场景 | 降级方案 |
|---------|---------|
| M2 API 接入阻塞 | 使用 Mock Agent（返回预设响应）保证 UI 流程完整，API 接入后替换 |
| M3 协调者任务拆解不稳定 | 降级为手动 @Agent 模式（用户自行分派），协调者仅做建议 |
| M4 内联预览阻塞 | 降级为"新窗口打开预览"，放弃内联 iframe |
| 任一 LLM Provider 不可用 | 切换到备选 Provider；所有 Provider 不可用 → Mock 模式保证演示 |

---

## 十、风险与边界条件

### 10.1 已知风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 多 Agent 并发时上下文污染 | 任务结果不一致 | 全局-私有双层上下文 + 共享制品只读模式 |
| LLM token 消耗不可控 | 成本爆炸 | 四道硬闸（步骤/Token/时长/工具调用上限） |
| Agent 输出质量不稳定 | 子任务失败率高 | Harness 重试机制 + 失败自动人工介入 |
| WebSocket 连接不稳定 | 消息丢失 | PostgreSQL 持久化兜底 + 重连恢复 |
| API Key 泄露 | 安全事件 | AES-256-GCM 加密存储 + 前端密码模式输入 |
| Orchestrator 任务拆解质量不稳定 | 子任务不合理/遗漏 | 精心设计 System Prompt + Few-shot 示例；提供手动 @Agent 降级路径 |

### 10.2 关键边界条件

- 单个群组 Agent 上限：20 个（MVP 阶段）
- 单个会话热上下文：最近 20 条消息
- 单个 Agent 并发任务：默认 3 个
- 子任务最大嵌套深度：1 层（不支持子任务的子任务）
- API Key 输入后不可再查看明文，仅支持重置
- Agent name 全局唯一，修改 name 会使旧对话中的 @mention 失效
