# AgentHub 分层架构设计

> 版本：v1.1 | 日期：2026-05-23 | 基于 PRD v4.0
> v1.1: 架构图标注双轨适配器；S8/S13/S14 数据流标注 Celery→asyncio.gather 待更新（v4 砍掉 Celery，实际实现以 v4 PRD 为准）

---

## 一、分层架构总览

### 1.1 五层架构图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  L5  Presentation                                                       │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  React 18 + TypeScript Strict                                       │ │
│  │                                                                      │ │
│  │  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │ │
│  │  │ ChatView │ │ AgentPanel│ │TaskBoard │ │  Inbox   │ │ Settings│ │ │
│  │  │ 聊天窗口  │ │ Agent管理 │ │ 任务看板  │ │  收件箱  │ │  设置    │ │ │
│  │  └──────────┘ └───────────┘ └──────────┘ └──────────┘ └─────────┘ │ │
│  │                                                                      │ │
│  │  Zustand Stores: agentStore / groupStore / chatStore /              │ │
│  │                   taskStore / inboxStore / wsStore                   │ │
│  │                                                                      │ │
│  │  Hooks: useAgent / useChat / useTask / useWebSocket /               │ │
│  │         useStreaming / useContext / useApproval                      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│        Request DTO / WS Message    │    Response DTO / WS Push           │
│                                    │                                     │
│  L4  API Gateway                                                        │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  FastAPI Routers                          FastAPI WebSocket Handlers │ │
│  │                                                                      │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │ │
│  │  │ AgentRouter  │ │ GroupRouter  │ │ TaskRouter   │                │ │
│  │  │ /api/agents  │ │ /api/groups  │ │ /api/tasks   │                │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │ │
│  │  │SessionRouter │ │ InboxRouter  │ │ WsHandler    │                │ │
│  │  │/api/sessions │ │ /api/inbox   │ │ /ws/sessions │                │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                │ │
│  │                                                                      │ │
│  │  Middleware: Auth(JWT) / CORS / RateLimit / RequestValidation       │ │
│  │                                                                      │ │
│  │  输入：HTTP Request (REST) / WebSocket Frame                         │ │
│  │  输出：调用 L3 Service，返回 HTTP Response / WS Push                 │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│           Command Object           │        Domain Event / Result        │
│                                    │                                     │
│  L3  Application (用例编排)                                              │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                                                                      │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │ │
│  │  │AgentService  │ │GroupService  │ │ ChatService  │                │ │
│  │  │· create      │ │· create      │ │· send_message │                │ │
│  │  │· update      │ │· add_member  │ │· stream       │ │ │
│  │  │· delete      │ │· remove_member│ │· get_history  │ │ │
│  │  │· get_detail  │ │· update_info │ │· pin_message  │                │ │
│  │  │· get_tasks   │ │· list_groups │ │· compress_ctx │                │ │
│  │  │· get_memory  │ │              │ │               │                │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                │ │
│  │                                                                      │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐        │ │
│  │  │ TaskService  │ │InboxService  │ │ CoordinatorService   │        │ │
│  │  │· create      │ │· list        │ │· decompose_and_dispatch│      │ │
│  │  │· list/filter │ │· mark_read   │ │· handle_failure      │        │ │
│  │  │· get_detail  │ │· get_unread  │ │· request_approval    │        │ │
│  │  │· update      │ │· get_calendar│ │· handle_human_decision│      │ │
│  │  └──────────────┘ └──────────────┘ └──────────────────────┘        │ │
│  │                                                                      │ │
│  │  职责：跨领域编排、事务管理、权限校验、事件发布                         │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│          Domain Object              │        Domain Event                │
│                                    │                                     │
│  L2  Domain (领域模型 + 核心规则)                                       │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                                                                      │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │ │
│  │  │  Agent   │ │  Group   │ │ Session  │ │ Message  │              │ │
│  │  │  (聚合根) │ │  (聚合根) │ │  (聚合根) │ │  (实体)   │              │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │ │
│  │  │  Task    │ │Notification│ │ Artifact │ │ApprovalReq│            │ │
│  │  │  (聚合根) │ │  (实体)   │ │  (实体)   │ │  (实体)    │            │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │ │
│  │                                                                      │ │
│  │  ┌──────────────────────────────────────────────────────┐          │ │
│  │  │  TaskEngine (核心引擎)                                │          │ │
│  │  │                                                      │          │ │
│  │  │  ┌───────────────┐  ┌───────────────┐               │          │ │
│  │  │  │ Coordinator   │  │   Harness     │               │          │ │
│  │  │  │ Agent (LLM)   │  │  (纯 Python)  │               │          │ │
│  │  │  │               │  │               │               │          │ │
│  │  │  │ · 任务分解    │  │ · FSM 流转    │               │          │ │
│  │  │  │ · 异常诊断    │  │ · Guard 校验  │               │          │ │
│  │  │  │ · Agent 推荐  │  │ · DAG 编译    │               │          │ │
│  │  │  │ · 审批建议    │  │ · 预算管控    │               │          │ │
│  │  │  └───────────────┘  │ · Worker 调度 │               │          │ │
│  │  │                      └───────────────┘               │          │ │
│  │  │                                                      │          │ │
│  │  │  ┌───────────────────────────────────────┐          │          │ │
│  │  │  │  Blackboard (PostgreSQL)              │          │          │ │
│  │  │  │  tasks + messages（v4 精简 6 表）       │          │          │ │
│  │  │  │  + Agent Registry + Session Store     │          │          │ │
│  │  │  └───────────────────────────────────────┘          │          │ │
│  │  └──────────────────────────────────────────────────────┘          │ │
│  │                                                                      │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │ │
│  │  │ TaskFSM      │ │ Validators   │ │ DomainEvents │                │ │
│  │  │ (状态机)      │ │ (领域校验)    │ │ (领域事件)    │                │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│          Repository Interface      │        Domain Event (待持久化)      │
│                                    │                                     │
│  L1  Infrastructure                                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                                                                      │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐      │ │
│  │  │PG Repo   │ │Redis Cache│ │ 双轨适配 (v4)    │                  │ │
│  │  │SQLAlchemy│ │· Session │ │                   │                  │ │
│  │  │· CRUD   │ │· Pub/Sub │ │ LLMAdapter (API)  │                  │ │
│  │  │· Migrate│ │· L1 记忆 │ │ ├ClaudeAdapter    │                  │ │
│  │  └──────────┘ └──────────┘ │ ├OpenAICompat    │                  │ │
│  │                             │ └MockAdapter     │                  │ │
│  │  ┌──────────┐ ┌──────────┐  │                   │                  │ │
│  │  │FileSystem│ │WS Bridge │  │ AgentRuntime(CLI) │                  │ │
│  │  │· Sandbox │ │· Redis→WS│  │ ├ClaudeCodeRT ←优先│                │ │
│  │  │· Virtual │ │· Broadcast│ │ ├CodexRT [未来]   │                  │ │
│  │  └──────────┘ └──────────┘  │ └TraeRT  [未来]   │                  │ │
│  │                             └──────────────────┘                  │ │
│  │  任务执行: asyncio.gather 并发（替代 Celery Canvas）                │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 1.2 层级边界定义

| 层级 | 职责 | 知道什么 | 不知道什么 | 依赖方向 |
|------|------|---------|-----------|---------|
| **L5 Presentation** | UI 渲染、用户交互、本地状态管理 | Zustand Store 结构、组件树、WebSocket 消息格式 | 后端实现细节、数据库结构、LLM 调用方式 | 仅依赖 L4 的 API 契约 |
| **L4 API Gateway** | HTTP/WS 端点、参数校验、序列化、鉴权 | Request/Response Schema、路由映射、中间件链 | 业务逻辑、领域模型、数据库 | 调用 L3 Service |
| **L3 Application** | 用例编排、跨领域协调、事务管理、权限校验、事件发布 | Service 接口、Command/DTO 定义、领域对象 | HTTP 细节、数据库实现、LLM 调用实现 | 依赖 L2 领域对象 + 发布事件 |
| **L2 Domain** | 领域模型、业务规则、Task Engine（FSM + Guard + DAG）、协调者决策 | 实体/值对象/聚合根、领域事件、状态机转换规则 | 持久化实现、HTTP 协议、UI 框架 | 仅定义接口，不依赖任何上层 |
| **L1 Infrastructure** | 持久化、缓存、任务执行、LLM 调用、文件系统 | PG 表结构、Redis 命令、LLM SDK / CLI 子进程 | 业务逻辑、UI、路由 | 实现 L2 定义的 Repository/Adapter 接口（双轨：LLMAdapter + AgentRuntime）。任务并发执行用 asyncio.gather |

### 1.3 依赖规则

```
L5 → L4 → L3 → L2 ← L1
              ↑
              └── L1 实现 L2 定义的接口（依赖倒置）
```

- L2 **不依赖** L1，L2 定义 `AgentRepository` / `TaskRepository` / `UnifiedAgent`（含 `LLMAdapter` + `AgentRuntime`）等抽象接口
- L1 **实现** L2 定义的接口（API 轨道：ClaudeAdapter 等；CLI 轨道：ClaudeCodeRuntime 等）
- L3 调用 L2 的领域对象 + L1 的实现（通过依赖注入）
- 跨层通信使用 **Command 对象（下行）** 和 **Domain Event（上行）**

---

## 二、跨层消息定义

### 2.1 消息流向总览

```
L5 → L4 : Request DTO (HTTP JSON / WebSocket Frame)
L4 → L3 : Command Object (Python dataclass)
L3 → L2 : Domain Method Call (领域对象的方法，参数为值对象)
L3 → L1 : StructuredContext (6层上下文结构体，见 §2.0)
L2 → L1 : Repository Interface / Adapter Interface
L1 → L2 : Domain Object (从 DB 重建的聚合根)
L2 → L3 : Domain Event (领域事件)
L3 → L4 : Response DTO / WS Push Event
L4 → L5 : HTTP Response JSON / WebSocket Push Frame
```

### 2.0 L3→L1 上下文结构体：StructuredContext

L3 调用 L1 Adapter 前，将分散在各个模块的上下文组装为统一的分层结构体。详细设计见 `docs/DOC-16-structured-context-design.md`。

```
StructuredContext（6层）
  ├── identity       — 身份与角色（Agent 实体 + Group 上下文）
  ├── conversation   — 对话历史（L1 Redis + pinned + 当前消息）
  ├── capabilities   — 工具 + Skills（ToolRegistry + SkillRegistry）
  ├── memory         — L2/L3/L4 记忆（MemoryContextBuilder）
  ├── project        — 项目上下文（.agenthub/ 目录）
  └── params         — 调用参数（Agent.settings）
```

每层独立 ownership、独立修改。API 适配器将其拆解为 function calling schema + system prompt + messages；CLI 适配器将其拼接为完整文本传入子进程。

设计原则：
- 添加新上下文类型时只需加一层，不改接口
- 各填充方只负责自己负责的那一层
- 适配器不增删内容，只按目标协议格式化

### 2.1 LLM 适配器双轨架构

L1 基础设施层将 LLM 调用拆分为两种本质不同的模式：

| 轨道 | 基类 | 模式 | 实现类 |
|------|------|------|--------|
| API 管道 | `LLMAdapter` | 无状态 HTTP/SDK 调用 | `ClaudeAdapter`、`OpenAICompatAdapter` |
| CLI 运行时 | `AgentRuntime` | 有状态子进程管理 | `ClaudeCodeRuntime`、`CodexRuntime` |

统一消费 `StructuredContext`，区别仅在于格式化方式：
- API 模式：`StructuredContext` → `{system, messages, tools, params}`（Anthropic SDK kwargs）
- CLI 模式：`StructuredContext` → 文本字符串（子进程 stdin / `--system-prompt` + `-p`）

`UnifiedAgent = LLMAdapter | AgentRuntime`，调用方（ChatService / CoordinatorService）只依赖 `UnifiedAgent.stream(ctx)`，不感知下游是 API 还是 CLI。

### 2.2 Command 对象目录

```python
# === Agent Commands ===
CreateAgentCommand(
    name: str,
    avatar: str,
    role: str,
    provider: Literal["anthropic", "openai", "azure"],
    model: str,
    api_key: str,        # 明文传入，L3 加密后交给 L1 存储
    skills: list[str] = [],
    system_prompt: str | None = None,
)
UpdateAgentCommand(
    agent_id: UUID,
    name: str | None = None,
    avatar: str | None = None,
    role: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    skills: list[str] | None = None,
    capability_tags: list[str] | None = None,
    settings: dict | None = None,
    system_prompt: str | None = None,
)
DeleteAgentCommand(agent_id: UUID)

# === Group Commands ===
CreateGroupCommand(
    name: str,
    description: str = "",
    member_ids: list[UUID] = [],   # 初始成员 Agent ID 列表
)
AddMemberCommand(
    group_id: UUID,
    agent_id: UUID,
)
RemoveMemberCommand(
    group_id: UUID,
    agent_id: UUID,
)
UpdateGroupCommand(
    group_id: UUID,
    name: str | None = None,
    description: str | None = None,
)

# === Session / Chat Commands ===
CreateSessionCommand(
    type: Literal["group", "private"],
    group_id: UUID | None = None,   # 群聊时必填
    agent_id: UUID | None = None,   # 私聊时必填
    title: str = "",
)
SendMessageCommand(
    session_id: UUID,
    content: str,
    content_type: str = "text",
    mentions: list[str] = [],       # @ 的 Agent name 列表
    reply_to: UUID | None = None,
    dispatch_mode: Literal["auto", "direct"] = "auto",
    # auto: 系统自动判断（@协调者 → 触发；@Agent → 直接路由；无@ → LLM意图检测）
    # direct: 直接发给目标 Agent（私聊固定使用）
)
PinMessageCommand(
    session_id: UUID,
    message_id: UUID,
)

# === Task Commands ===
CreateTaskCommand(
    title: str,
    description: str = "",
    assignee_id: UUID | None = None,    # 负责人 Agent 或群组
    assignee_type: Literal["agent", "group"] | None = None,
    due_date: datetime | None = None,
    priority: Literal["critical", "high", "medium", "low"] = "medium",
    tags: list[str] = [],
    parent_task_id: UUID | None = None,  # 从属的父任务
)
ListTasksCommand(
    status: list[str] | None = None,     # 多选筛选
    priority: list[str] | None = None,
    assignee_id: UUID | None = None,
    due_before: datetime | None = None,
    due_after: datetime | None = None,
    tags: list[str] | None = None,
    parent_task_id: UUID | None = None,
    sort_by: Literal["created_at", "due_date", "priority"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    page: int = 1,
    page_size: int = 20,
)
UpdateTaskCommand(
    task_id: UUID,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: UUID | None = None,
    due_date: datetime | None = None,
    tags: list[str] | None = None,
)

# === Inbox Commands ===
ListInboxCommand(
    category: Literal["all", "approval", "task", "calendar"] = "all",
    is_read: bool | None = None,
    page: int = 1,
    page_size: int = 20,
)
MarkReadCommand(notification_ids: list[UUID])

# === Approval Commands ===
HandleApprovalCommand(
    task_id: UUID,
    decision: Literal["approve", "reject", "edit", "respond"],
    payload: dict | None = None,   # edit/respond 时附带修改内容或补充信息
)
```

### 2.3 Domain Event 目录

```python
# === Agent Events ===
AgentCreated(agent_id: UUID, name: str, provider: str, model: str, timestamp: datetime)
AgentUpdated(agent_id: UUID, changed_fields: list[str], timestamp: datetime)
AgentDeleted(agent_id: UUID, timestamp: datetime)

# === Group Events ===
GroupCreated(group_id: UUID, name: str, coordinator_id: UUID, timestamp: datetime)
MemberAdded(group_id: UUID, agent_id: UUID, timestamp: datetime)
MemberRemoved(group_id: UUID, agent_id: UUID, timestamp: datetime)

# === Session Events ===
SessionCreated(session_id: UUID, type: str, participants: list[UUID], timestamp: datetime)
MessageSent(session_id: UUID, message_id: UUID, role: str, content_type: str, timestamp: datetime)
MessagePinned(session_id: UUID, message_id: UUID, timestamp: datetime)
StreamingStarted(session_id: UUID, message_id: UUID)
StreamingToken(session_id: UUID, message_id: UUID, token: str, seq: int)
StreamingCompleted(session_id: UUID, message_id: UUID)
StreamingFailed(session_id: UUID, message_id: UUID, error: str)

# === Task Events ===
TaskCreated(task_id: UUID, parent_task_id: UUID | None, title: str, priority: str, assignee: UUID | None, timestamp: datetime)
TaskStateChanged(task_id: UUID, from_state: str, to_state: str, actor: str, timestamp: datetime)
SubTaskCreated(task_id: UUID, parent_task_id: UUID, assignee: UUID, timestamp: datetime)
TaskProgressUpdated(task_id: UUID, completed_subtasks: int, total_subtasks: int)

# === Approval Events ===
ApprovalRequested(task_id: UUID, agent_id: UUID, action: str, reason: str, checkpoint: dict, timestamp: datetime)
ApprovalResolved(task_id: UUID, decision: str, by_user: UUID, timestamp: datetime)

# === Inbox Events ===
NotificationCreated(notification_id: UUID, user_id: UUID, category: str, title: str, timestamp: datetime)
NotificationRead(notification_ids: list[UUID], timestamp: datetime)
```

---

## 三、功能场景 —— 完整数据流

### 场景分类索引

| 编号 | 场景 | 类型 |
|------|------|------|
| S1 | 添加 Agent | CRUD |
| S2 | 编辑 Agent | CRUD |
| S3 | 删除 Agent | CRUD |
| S4 | 查看 Agent 详情（概览/任务/活动/群组/记忆/设置） | 查询 |
| S5 | 创建群组 | CRUD |
| S6 | 添加 Agent 到群组 | 关系操作 |
| S7 | 从群组移除 Agent | 关系操作 |
| S8 | 群聊发送任务消息（触发协调者） | 核心流程 |
| S9 | 群聊 @指定 Agent | 消息路由 |
| S10 | 群聊 @All | 消息路由 |
| S11 | 私聊 Agent | 消息路由 |
| S12 | 流式输出 | 实时推送 |
| S13 | 协调者分解任务 → 生成 DAG | 核心流程 |
| S14 | Worker 执行子任务 | 核心流程 |
| S15 | 任务状态流转 (FSM) | 状态管理 |
| S16 | 手动创建任务 | CRUD |
| S17 | 任务列表筛选 | 查询 |
| S18 | Agent 请求审批 | 审批流 |
| S19 | 用户 APPROVE/REJECT | 审批流 |
| S20 | 通知生成 + 未读计数 | 收件箱 |
| S21 | 日历视图 | 查询 |
| S22 | 上下文注入 | 上下文管理 |
| S23 | Pin 消息 | 上下文管理 |
| S24 | 长对话压缩 | 上下文管理 |

---

### S1: 添加 Agent（表单式 + 对话式）

**两种创建方式**：

| 方式 | 流程 | 前端组件 |
|------|------|---------|
| 表单式 | 填写 name/role/provider/model/api_key → POST `/api/agents` | `AgentForm` |
| 对话式 | 自然语言描述职责 → 系统生成 System Prompt 草案 + 能力标签 → 用户补填 provider/model/api_key → 确认 → POST `/api/agents` | `AgentDialogCreate` |

**数据流图**：

```
┌──────────┐     POST /api/agents      ┌──────────────┐
│  L5 前端  │ ──────────────────────────▶│  L4 API      │
│AgentPanel│ ◀──────────────────────────│ AgentRouter   │
│ 创建表单  │    201 + AgentResponse     │              │
└──────────┘                           └──────┬───────┘
                                               │
                            CreateAgentCommand  │
                                               ▼
                                      ┌──────────────┐
                                      │  L3          │
                                      │AgentService  │
                                      │ .create()    │
                                      └──────┬───────┘
                                             │
                       1. 校验 name 唯一性     │
                       2. AES 加密 api_key    │
                       3. 创建 Agent 聚合根   │
                                             │
                                     ┌───────┴───────┐
                                     │               │
                                     ▼               ▼
                              ┌──────────┐   ┌──────────────┐
                              │  L2      │   │  L1           │
                              │  Agent   │   │AgentRepository│
                              │ (聚合根)  │   │ .save()       │
                              └──────────┘   └──────┬───────┘
                                                    │
                                     INSERT INTO     │
                                     agents +        │
                                     agent_capabilities │
                                                    │
                                                    ▼
                                            ┌──────────────┐
                                            │  PostgreSQL  │
                                            └──────────────┘

事件发布: AgentCreated
  → Redis Pub/Sub → (无实时推送需求，仅日志)
```

**时序图**：

```
前端(AddAgentForm)    L4(AgentRouter)    L3(AgentService)   L2(Agent)   L1(AgentRepo)    Redis/DB
     │                      │                   │               │             │              │
     │ POST /api/agents     │                   │               │             │              │
     │ {name,avatar,role,   │                   │               │             │              │
     │  provider,model,key} │                   │               │             │              │
     │─────────────────────▶│                   │               │             │              │
     │                      │                   │               │             │              │
     │                      │ CreateAgentCmd    │               │             │              │
     │                      │──────────────────▶│               │             │              │
     │                      │                   │               │             │              │
     │                      │                   │ check_unique  │             │              │
     │                      │                   │──────────────────────────▶│              │
     │                      │                   │◀──────────────────────────│              │
     │                      │                   │               │             │              │
     │                      │                   │ encrypt_api_key            │              │
     │                      │                   │               │             │              │
     │                      │                   │ Agent(name,role,provider..)│              │
     │                      │                   │──────────────▶│             │              │
     │                      │                   │               │             │              │
     │                      │                   │ validate()    │             │              │
     │                      │                   │◀──────────────│             │              │
     │                      │                   │               │             │              │
     │                      │                   │ save(agent)   │             │              │
     │                      │                   │──────────────────────────▶│              │
     │                      │                   │               │             │ INSERT       │
     │                      │                   │               │             │──────────────▶│
     │                      │                   │               │             │◀──────────────│
     │                      │                   │◀──────────────────────────│              │
     │                      │                   │               │             │              │
     │                      │                   │ AgentCreated  │             │              │
     │                      │                   │──────────────────────────────────────────▶│
     │                      │                   │               │             │   Pub/Sub    │
     │                      │                   │               │             │              │
     │                      │  AgentResponse    │               │             │              │
     │                      │◀──────────────────│               │             │              │
     │                      │                   │               │             │              │
     │ 201 Created          │                   │               │             │              │
     │ {id, name, status..} │                   │               │             │              │
     │◀─────────────────────│                   │               │             │              │
```

**层间消息**：

| 方向 | 消息 | 携带数据 |
|------|------|---------|
| L5→L4 | `POST /api/agents` | `{name, avatar, role, provider, model, api_key, skills?, system_prompt?}` |
| L4→L3 | `CreateAgentCommand` | 同上，经 Pydantic 校验 |
| L3→L1 | `AgentRepository.check_name_unique(name)` | `name: str` |
| L3→L1 | `AgentRepository.save(agent)` | Agent ORM 对象 |
| L2→L1 | 聚合根持久化 | Agent 所有属性 |
| L3→EventBus | `AgentCreated` | `{agent_id, name, provider, model, timestamp}` |
| L4→L5 | `201 AgentResponse` | `{id, name, avatar, role, status, created_at, ...}` |

---

### S2: 编辑 Agent

**数据流图**：

```
┌──────────┐   PATCH /api/agents/{id}  ┌──────────────┐
│  L5 前端  │ ──────────────────────────▶│  L4 API      │
│AgentEdit │ ◀──────────────────────────│ AgentRouter   │
│ 编辑表单  │    200 + AgentResponse     │              │
└──────────┘                           └──────┬───────┘
                                               │
                            UpdateAgentCommand  │
                                               ▼
                                      ┌──────────────┐
                                      │  L3          │
                                      │AgentService  │
                                      │ .update()    │
                                      └──────┬───────┘
                                             │
                       1. 从 L1 加载 Agent 聚合根  │
                       2. 调用 agent.update(...)   │
                       3. 如果修改 api_key → 重新加密
                       4. 持久化                    │
                                             │
                                      ┌──────┴──────┐
                                      ▼              ▼
                               ┌──────────┐  ┌──────────────┐
                               │  L2      │  │  L1           │
                               │  Agent   │  │AgentRepository│
                               │ .update()│  │ .save()       │
                               └──────────┘  └──────────────┘
```

**层间消息**：

| 方向 | 消息 | 数据 |
|------|------|------|
| L5→L4 | `PATCH /api/agents/{id}` | `{name?, role?, provider?, model?, api_key?, skills?, capability_tags?, settings?, system_prompt?}` |
| L4→L3 | `UpdateAgentCommand` | 同上 + `agent_id` |
| L3→L1 | `AgentRepository.get_by_id(id)` | `agent_id: UUID` |
| L1→L3 | Agent 聚合根 | 当前持久化状态 |
| L3→L2 | `agent.update(**changed_fields)` | 变更字段 dict |
| L3→L1 | `AgentRepository.save(agent)` | 更新后的 Agent |
| L3→EventBus | `AgentUpdated` | `{agent_id, changed_fields[], timestamp}` |

---

### S3: 删除 Agent

**数据流图**：

```
┌──────────┐  DELETE /api/agents/{id}  ┌──────────────┐
│  L5 前端  │ ──────────────────────────▶│  L4 API      │
│AgentList │ ◀──────────────────────────│ AgentRouter   │
│ 删除确认  │    204 No Content          │              │
└──────────┘                           └──────┬───────┘
                                               │
                                               ▼
                                      ┌──────────────┐
                                      │  L3          │
                                      │AgentService  │
                                      │ .delete()    │
                                      └──────┬───────┘
                                             │
                       1. 检查 Agent 是否在群组中  │
                       2. 从所有群组移除          │
                       3. 标记为 deleted          │
                                             │
                                      ┌──────┴──────┐
                                      ▼              ▼
                               ┌──────────┐  ┌──────────────┐
                               │  L2      │  │  L1           │
                               │  Agent   │  │AgentRepository│
                               │ .mark_   │  │ + GroupRepo   │
                               │ deleted()│  │               │
                               └──────────┘  └──────────────┘
```

**层间消息**：

| 方向 | 消息 | 数据 |
|------|------|------|
| L5→L4 | `DELETE /api/agents/{id}` | - |
| L4→L3 | `DeleteAgentCommand(agent_id)` | - |
| L3→L1 | `GroupRepository.get_groups_by_agent(agent_id)` | 查询所属群组 |
| L3→L1 | `GroupRepository.remove_member(group_id, agent_id)` | 逐群组移除 |
| L3→L1 | `AgentRepository.soft_delete(agent_id)` | 软删除 |
| L3→EventBus | `AgentDeleted` | `{agent_id, timestamp}` |

---

### S4: 查看 Agent 详情（含 Tab 切换）

```
┌──────────┐   GET /api/agents/{id}    ┌──────────────┐
│  L5 前端  │ ──────────────────────────▶│  L4 API      │
│AgentDetail│◀───────────────────────── │ AgentRouter   │
│ · 概览    │   GET /api/agents/{id}/tasks       │              │
│ · 任务    │   GET /api/agents/{id}/activities  │              │
│ · 活动    │   GET /api/agents/{id}/memory      │              │
│ · 群组    │   GET /api/agents/{id}/channels    │              │
│ · 记忆    │                           │              │
│ · 设置    │                           │              │
└──────────┘                           └──────┬───────┘
                                               │
                                   并行查询     │
                                   ┌───────────┼───────────┐
                                   ▼           ▼           ▼
                            AgentService  TaskService  GroupService
                            .get_detail() .get_by_agent() .get_by_agent()
                                   │           │           │
                                   ▼           ▼           ▼
                            AgentRepo    TaskRepo    GroupRepo
```

**各 Tab 数据来源**：

| Tab | API | L3 Service | 数据内容 |
|-----|-----|-----------|---------|
| 概览 | `GET /api/agents/{id}` | `AgentService.get_detail()` | 基本信息、状态、负载、所属群组数 |
| 任务 | `GET /api/agents/{id}/tasks` | `TaskService.list_by_agent()` | 分配给此 Agent 的任务（支持状态筛选） |
| 活动 | `GET /api/agents/{id}/activities` | `AgentService.get_activities()` | Agent 活动日志时间线 |
| 群组 | `GET /api/agents/{id}/channels` | `GroupService.get_by_agent()` | 所属群组列表 |
| 记忆 | `GET /api/agents/{id}/memory` | `AgentService.get_memory()` | L1-L4 记忆内容 + 配置 |
| 工作区 | `GET /api/agents/{id}/workspace` | `AgentService.get_workspace()` | 虚拟命名空间信息 |
| 技能 | 嵌入在 `GET /api/agents/{id}` 的 `capability_tags` | - | 能力标签列表 |
| 设置 | 嵌入在 `GET /api/agents/{id}` 的 `settings` | - | 模型、系统提示词、并发数等 |

---

### S5: 创建群组（含自动生成协调者）

**数据流图**：

```
┌──────────┐   POST /api/groups        ┌──────────────┐
│  L5 前端  │ ──────────────────────────▶│  L4 API      │
│CreateGroup│◀───────────────────────── │ GroupRouter   │
│ 表单:     │   201 + GroupResponse     │              │
│ 名称/描述  │   (含 coordinator 信息)   │              │
│ 可选成员  │                           │              │
└──────────┘                           └──────┬───────┘
                                               │
                            CreateGroupCommand  │
                                               ▼
                                      ┌──────────────┐
                                      │  L3          │
                                      │GroupService  │
                                      │ .create()    │
                                      └──────┬───────┘
                                             │
                   ┌─────────────────────────┼──────────────────┐
                   │                         │                  │
                   ▼                         ▼                  ▼
           创建 Group 聚合根          创建 Coordinator      添加初始成员
           Group(name,desc)          Agent (系统角色)      group.add_members()
                   │                         │                  │
                   ▼                         ▼                  ▼
            GroupRepo.save()         AgentRepo.save()    GroupRepo.add_members()
                   │                         │                  │
                   └─────────────────────────┼──────────────────┘
                                             │
                                      ┌──────┴──────┐
                                      ▼             ▼
                              ┌──────────┐  ┌──────────────┐
                              │  L2      │  │  L1           │
                              │  Group   │  │GroupRepository│
                              │ (聚合根)  │  │ + AgentRepo  │
                              └──────────┘  └──────────────┘

事件发布:
  GroupCreated → Redis Pub/Sub → (通知相关 Agent 有新群组)
  AgentCreated → Coordinator Agent 上线
```

**时序图**：

```
前端(CreateGroup)  L4(GroupRouter)  L3(GroupService)  L2(Group/Agent)  L1(Repo)   Redis
     │                   │                 │                │              │          │
     │ POST /api/groups  │                 │                │              │          │
     │ {name,desc,members}│                │                │              │          │
     │──────────────────▶│                 │                │              │          │
     │                   │ CreateGroupCmd  │                │              │          │
     │                   │────────────────▶│                │              │          │
     │                   │                 │                │              │          │
     │                   │                 │ 1. Group(name,desc)           │          │
     │                   │                 │───────────────▶│              │          │
     │                   │                 │                │              │          │
     │                   │                 │ 2. CoordinatorAgent(          │          │
     │                   │                 │    name="Coordinator-{id}",   │          │
     │                   │                 │    role="system_coordinator", │          │
     │                   │                 │    provider=system,           │          │
     │                   │                 │    is_system=True)            │          │
     │                   │                 │───────────────▶│              │          │
     │                   │                 │                │              │          │
     │                   │                 │ 3. save(group)                │          │
     │                   │                 │──────────────────────────────▶│          │
     │                   │                 │◀──────────────────────────────│          │
     │                   │                 │                │              │          │
     │                   │                 │ 4. save(coordinator_agent)    │          │
     │                   │                 │──────────────────────────────▶│          │
     │                   │                 │◀──────────────────────────────│          │
     │                   │                 │                │              │          │
     │                   │                 │ 5. add_members(initial_members)         │
     │                   │                 │──────────────────────────────▶│          │
     │                   │                 │◀──────────────────────────────│          │
     │                   │                 │                │              │          │
     │                   │                 │ GroupCreated   │              │          │
     │                   │                 │─────────────────────────────────────────▶│
     │                   │                 │ AgentCreated   │              │          │
     │                   │                 │(coordinator)   │              │          │
     │                   │                 │─────────────────────────────────────────▶│
     │                   │                 │                │              │          │
     │                   │ GroupResponse   │                │              │          │
     │                   │◀────────────────│                │              │          │
     │                   │ {id, name,      │                │              │          │
     │                   │  coordinator:   │                │              │          │
     │                   │  {id,name},     │                │              │          │
     │                   │  members:[...]} │                │              │          │
     │ 201 Created       │                 │                │              │          │
     │◀──────────────────│                 │                │              │          │
```

**群组协调者说明**：
- 协调者是系统自动创建的 Agent，`is_system=True`
- 协调者在群组成员列表中**可见**（蓝色系统标识），不可移除
- 协调者名称：`协调者-{群组名称}`，头像为系统预设
- 协调者的 provider 固定为 `system`（内部路由），model 使用系统配置的默认 Orchestrator 模型
- 群组删除时，协调者 Agent 同步删除

---

### S6: 添加 Agent 到群组

```
┌──────────┐ POST /api/groups/{id}/members ┌──────────────┐
│  L5 前端  │ ──────────────────────────────▶│  L4 API      │
│GroupDetail│◀───────────────────────────── │ GroupRouter   │
│ 添加成员  │  200 + updated members list   │              │
└──────────┘                               └──────┬───────┘
                                                   │
                                AddMemberCommand    │
                                                   ▼
                                          ┌──────────────┐
                                          │  L3          │
                                          │GroupService  │
                                          │ .add_member()│
                                          └──────┬───────┘
                                                 │
                      1. 加载 Group 聚合根          │
                      2. group.add_member(agent_id) │
                      3. 校验: Agent 不存在? 已在群组?│
                      4. 持久化                     │
                                                 │
                                          ┌──────┴──────┐
                                          ▼              ▼
                                   ┌──────────┐  ┌──────────────┐
                                   │  L2      │  │  L1           │
                                   │  Group   │  │GroupRepository│
                                   └──────────┘  └──────────────┘

事件: MemberAdded → Redis Pub/Sub → WS 通知群组内其他成员
```

---

### S7: 从群组移除 Agent

```
┌──────────┐ DELETE /api/groups/{id}/    ┌──────────────┐
│  L5 前端  │        members/{agent_id}   │  L4 API      │
│GroupDetail│ ──────────────────────────▶ │ GroupRouter   │
└──────────┘                             └──────┬───────┘
                                                 │
                                  RemoveMemberCmd │
                                                 ▼
                                        ┌──────────────┐
                                        │  L3          │
                                        │GroupService  │
                                        │ .remove_member()
                                        └──────────────┘

事件: MemberRemoved → Redis Pub/Sub → WS 通知
```

---

### S8: 群聊发送任务消息（触发协调者） ⭐ 核心流程

> ⚠️ v4: Celery Canvas 已砍，替换为 `asyncio.gather` 并发执行。下方数据流保留原始设计思路，实现以 `PRD_AgentHub_v4_统一方案.md` §七为准。

**数据流图**：

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        S8: 群聊任务消息 — 完整链路                         │
│                                                                          │
│  L5 前端 (ChatView)                                                      │
│  │  用户发送: "帮我做一个登录页面"（auto模式）                              │
│  │  或 @协调者 发送: "帮我做一个登录页面"（显式触发）                      │
│  │  dispatch_mode = "auto" (默认) 或 "direct" (私聊固定)                  │
│  ▼                                                                       │
│  WS → send_message frame →                                               │
│                                                                          │
│  L4 (WS Handler)                                                         │
│  │  反序列化 → SendMessageCommand                                        │
│  ▼                                                                       │
│                                                                          │
│  L3 (ChatService.send_message)                                           │
│  │                                                                       │
│  ├─ 1. 保存 Message 到 L1 (role=user, status=sent)                      │
│  ├─ 2. 发布 MessageSent 事件 → WS 广播给会话所有在线客户端               │
│  │                                                                       │
│  ├─ 3. 判定 dispatch_mode:                                              │
│  │     "direct" → 私聊，直接发给 Agent                                    │
│  │     "auto" → 检查:                                                     │
│  │       · 是否 @协调者? (是 → 直接触发)                                  │
│  │       · 是否有 @AgentName? (有 → 直接路由到对应 Agent)                 │
│  │       · 消息是否包含任务意图? (LLM 快速分类)                            │
│  │       · 是任务 → 触发协调者                                             │
│  │       · 否 → 仅作为对话上下文，不触发                                    │
│  │                                                                       │
│  └─ 4. 触发协调者:                                                      │
│        CoordinatorService.decompose_and_dispatch(                       │
│          message=content,                                               │
│          session_id=session_id,                                          │
│          group_id=group_id,                                             │
│          available_agents=[group.members],  # 群组内所有 Agent           │
│          conversation_history=[recent 20 messages]                       │
│        )                                                                 │
│        │                                                                 │
│        ▼                                                                 │
│                                                                          │
│  L2 (TaskEngine / Coordinator Agent)                                     │
│  │                                                                       │
│  │  ┌── Coordinator Agent (LLM 调用) ──────────────┐                    │
│  │  │  输入:                                         │                    │
│  │  │    · 用户消息                                   │                    │
│  │  │    · 对话历史（最近 20 条）                      │                    │
│  │  │    · 群组内可用 Agent 列表（能力标签+当前负载）   │                    │
│  │  │                                                │                    │
│  │  │  输出: 结构化 JSON                              │                    │
│  │  │  {                                             │                    │
│  │  │    "action": "decompose_and_dispatch",          │                    │
│  │  │    "plan": {                                   │                    │
│  │  │      "tasks": [                                │                    │
│  │  │        {"id": "task-1", "intent": "ui",       │                    │
│  │  │         "description": "创建登录页面UI",        │                    │
│  │  │         "suggested_worker": "frontend_agent",  │                    │
│  │  │         "dependencies": []},                   │                    │
│  │  │        {"id": "task-2", "intent": "api",      │                    │
│  │  │         "description": "创建登录API",           │                    │
│  │  │         "suggested_worker": "backend_agent",   │                    │
│  │  │         "dependencies": []},                   │                    │
│  │  │        {"id": "task-3", "intent": "review",   │                    │
│  │  │         "description": "审查代码",              │                    │
│  │  │         "suggested_worker": "reviewer_agent",  │                    │
│  │  │         "dependencies": ["task-1", "task-2"]}  │                    │
│  │  │      ]                                         │                    │
│  │  │    }                                           │                    │
│  │  │  }                                             │                    │
│  │  └──────────────────────────────────────────────┘                    │
│  │                                                                       │
│  │  ┌── Harness (纯代码，校验 + 编译 + 入队) ────────┐                   │
│  │  │  1. Pydantic 校验 JSON                          │                   │
│  │  │  2. detect_cycle(plan) → pass                  │                   │
│  │  │  3. route_worker(suggested, workload, quality)  │                   │
│  │  │     → 可能覆盖 Agent 建议的 Worker              │                   │
│  │  │  4. compile_to_canvas(plan)                    │                   │
│  │  │     → Celery Canvas: group([task-1, task-2])   │                   │
│  │  │                      | chord([t1,t2], task-3)  │                   │
│  │  │  5. 写入 tasks 表（父任务 + 子任务）            │                   │
│  │  │  6. 写入 task_events（task_created × N）       │                   │
│  │  │  7. apply_async() → Celery 入队               │                   │
│  │  └──────────────────────────────────────────────┘                    │
│  │                                                                       │
│  ▼                                                                       │
│                                                                          │
│  L1 (Celery + PostgreSQL)                                                │
│  │  · Worker 从队列拉取 task-1, task-2（并行执行）                       │
│  │  · task-1,task-2 完成后 chord callback 触发 task-3                   │
│  │                                                                       │
│  ▼                                                                       │
│  事件发布时序:                                                            │
│    TaskCreated (父任务) → Redis Pub/Sub → WS 推送到群聊                   │
│    SubTaskCreated × 3  → WS 推送子任务卡片                               │
│    TaskStateChanged (task-1: pending→queued→running)                     │
│    ...                                                                    │
└──────────────────────────────────────────────────────────────────────────┘
```

**层间消息**：

| 方向 | 消息 | 数据 |
|------|------|------|
| L5→L4 | WS Frame: `{type: "send_message", session_id, content, dispatch_mode, mentions}` | |
| L4→L3 | `SendMessageCommand` | `{session_id, content, content_type, mentions, dispatch_mode}` |
| L3→L1 | `MessageRepository.save(message)` | Message ORM |
| L3→L1 | `SessionRepository.get_context(session_id, limit=20)` | 最近 20 条消息 |
| L3→L2 | `CoordinatorService.decompose_and_dispatch(...)` | 消息 + Agent 列表 + 历史 |
| L2→L1 | `LLMAdapter.chat(prompt)` | 构造的 system/user prompt |
| L2→L1 | `TaskRepository.create_task(task)` × N | 父任务 + 子任务 |
| L2→L1 | `TaskRepository.create_event(task_id, event)` × N | 事件日志 |
| L2→L1 | `Celery.apply_async(canvas)` | 编译后的 DAG Canvas |
| L3→EventBus | `MessageSent` → WS Broadcast | |
| L2→EventBus | `TaskCreated + SubTaskCreated` → WS Push 任务卡片 | |

---

### S9: 群聊 @指定 Agent

**与 S8 的关键区别**：消息中有明确的 `@AgentName`，协调者**不介入**。

```
用户发送: "@FrontendAgent 把按钮颜色改成蓝色"

L3 ChatService.send_message():
  │
  ├─ 检测到 mentions = ["FrontendAgent"]
  │
  ├─ dispatch_mode == "auto" + 有 @mentions
  │   → 判定为 direct 模式，不触发协调者
  │
  ├─ 创建 task (直接分配):
  │   Task(
  │     title="用户直接指令",
  │     description="把按钮颜色改成蓝色",
  │     assignee_id=frontend_agent.id,
  │     assignee_type="agent",
  │     source="chat",
  │     parent_task_id=None  # 没有父任务，不是协调者分解的
  │   )
  │
  ├─ 入队执行
  │
  └─ WS 推送到群聊: "@FrontendAgent 收到指令，正在处理..."
```

**时序图**：

```
用户      前端(群聊)    L4(WS)      L3(ChatService)   L2(TaskEngine)   FrontendAgent
 │           │            │              │                 │               │
 │ @Frontend │            │              │                 │               │
 │──────────▶│            │              │                 │               │
 │           │ WS send    │              │                 │               │
 │           │───────────▶│              │                 │               │
 │           │            │ SendMessageCmd                │               │
 │           │            │─────────────▶│                 │               │
 │           │            │              │                 │               │
 │           │            │              │ 检测到 @mentions │               │
 │           │            │              │ → direct模式     │               │
 │           │            │              │                 │               │
 │           │            │              │ CreateTask(assignee=Frontend)  │
 │           │            │              │────────────────▶│               │
 │           │            │              │                 │               │
 │           │            │              │                 │ enqueue_task  │
 │           │            │              │                 │──────────────▶│
 │           │            │              │                 │               │
 │           │  WS push   │              │                 │               │
 │           │ "FrontendAgent 处理中..." │                 │               │
 │           │◀───────────│◀─────────────│                 │               │
```

---

### S10: 群聊 @All

```
用户发送: "@All 检查一下最新的代码变更"

L3 ChatService.send_message():
  │
  ├─ mentions = ["All"]
  │
  ├─ dispatch_mode → direct 模式，但目标为群组内全体 Agent
  │
  ├─ 遍历 group.members，为每个 Agent 创建独立 task:
  │   for agent in group.members:
  │     Task(
  │       title="用户 @All 指令",
  │       description="检查一下最新的代码变更",
  │       assignee_id=agent.id,
  │       assignee_type="agent",
  │       source="chat"
  │     )
  │
  ├─ 并行入队执行 (group of tasks)
  │
  └─ 各 Agent 回复汇总到群聊（各自独立消息卡片）
```

---

### S11: 私聊 Agent

**与群聊的区别**：
- 没有群组上下文，没有协调者
- 消息直接发给目标 Agent
- Agent 响应进入私聊会话，不广播

```
┌──────────┐  点击 Agent 头像进入私聊   ┌──────────────┐
│  L5 前端  │ ──────────────────────────▶│  L4 API      │
│ 私聊窗口  │  POST /api/sessions        │SessionRouter │
│          │  {type:"private", agent_id} │              │
│          │ ◀────────────────────────── │              │
│          │  201 + session_id            │              │
└──────────┘                            └──────┬───────┘
                                                │
                            CreateSessionCommand │
                                                ▼
                                       ┌──────────────┐
                                       │  L3          │
                                       │ChatService   │
                                       │ .create_     │
                                       │  session()   │
                                       └──────┬───────┘
                                              │
                         创建 Session(type=private)  │
                         绑定 user ↔ agent          │
                                              │
                                       ┌──────┴───────┐
                                       ▼               ▼
                                ┌──────────┐   ┌──────────────┐
                                │  L2      │   │  L1           │
                                │ Session  │   │SessionRepo    │
                                └──────────┘   └──────────────┘

发送消息:
  L5 → WS send → L3 ChatService.send_message()
    → dispatch_mode = "direct" (私聊固定)
    → 创建 Task(assignee=agent, parent_task_id=None)
    → Worker 执行 → 回复到私聊会话
```

---

### S12: 流式输出

**数据流**：

```
Agent (LLM) 生成 token
  │
  ▼
L1 LLMAdapter.stream(prompt) → AsyncGenerator[token]
  │
  ▼
L2 Worker 逐 token 产出
  │
  ├─ 每个 token → StreamingToken(message_id, session_id, token, seq)
  │                 │
  │                 ▼
  │           Redis Pub/Sub: "stream:{session_id}:{message_id}"
  │                 │
  │                 ▼
  │           L4 WS Handler 订阅 → WS Frame → L5 前端
  │
  ├─ 完成 → StreamingCompleted(message_id, session_id)
  │          → 消息 status 从 streaming → done
  │
  └─ 失败 → StreamingFailed(message_id, session_id, error)
             → 消息 status 从 streaming → error
```

**时序图**：

```
L1(LLMAdapter)    L2(Worker)    Redis Pub/Sub    L4(WS Handler)    L5(前端)
     │                │               │                │               │
     │ stream()       │               │                │               │
     │───────────────▶│               │                │               │
     │ token:"我"     │               │                │               │
     │───────────────▶│ StreamingToken│                │               │
     │                │──────────────▶│                │               │
     │                │               │ WS push: "我"  │               │
     │                │               │───────────────▶│               │
     │                │               │                │ setState("我")│
     │                │               │                │──────────────▶│
     │ token:"来"     │               │                │               │
     │───────────────▶│──────────────▶│───────────────▶│──────────────▶│
     │ token:"创建"   │               │                │               │
     │───────────────▶│──────────────▶│───────────────▶│──────────────▶│
     │  ...           │   ...         │     ...        │     ...       │
     │                │               │                │               │
     │ (stream结束)   │               │                │               │
     │                │StreamCompleted│                │               │
     │                │──────────────▶│                │               │
     │                │               │ message.done   │               │
     │                │               │───────────────▶│──────────────▶│
```

---

### S13: 协调者分解任务 → 生成 DAG ⭐

此场景详细展示了 Task Engine 的内部工作流。

**数据流**：

```
CoordinatorAgent (LLM) 拿到:
  → 用户消息: "帮我做一个登录页面"
  → 群组可用 Agent: [
      {name:"FrontendAgent", capabilities:["react","typescript","css"], workload:0},
      {name:"BackendAgent",  capabilities:["python","fastapi","postgresql"], workload:1},
      {name:"ReviewerAgent", capabilities:["code_review","testing"], workload:0}
    ]
  → 对话历史(最近20条): [...]

CoordinatorAgent 输出 (结构化JSON):
{
  "action": "decompose_and_dispatch",
  "plan": {
    "tasks": [
      {"id":"task-1","intent":"ui","description":"创建登录页面UI组件",
       "suggested_worker":"FrontendAgent","dependencies":[],
       "input_schema":{"framework":"react","styling":"tailwind"},
       "validation_gate":"UI组件渲染正常，表单有邮箱+密码字段"},
      {"id":"task-2","intent":"api","description":"创建POST /api/auth/login",
       "suggested_worker":"BackendAgent","dependencies":[],
       "input_schema":{"framework":"fastapi","auth":"jwt"},
       "validation_gate":"API返回200，token格式正确"},
      {"id":"task-3","intent":"review","description":"审查前后端代码",
       "suggested_worker":"ReviewerAgent","dependencies":["task-1","task-2"],
       "input_schema":{},
       "validation_gate":"无Critical问题"}
    ]
  }
}

Harness 编译:
  → detect_cycle(plan) → False ✓
  → route_worker 确认:
      FrontendAgent 负载=0 → 分配给 task-1 ✓
      BackendAgent 负载=1 → 低于并发上限 → 分配给 task-2 ✓
      ReviewerAgent 负载=0 → 分配给 task-3 ✓
  → compile_to_canvas:
      roots = [task-1, task-2]  # 无依赖 → 并行
      task-3 depends on [task-1, task-2] → chord
      canvas = chord([task-1, task-2], task-3)

  DAG 可视化:
      [task-1: UI] ──┐
                      ├──▶ [task-3: Review]
      [task-2: API] ──┘

  → apply_async(canvas) → Celery Worker Pool
```

**关键决策点**：

| 步骤 | 执行者 | 可被否决？ |
|------|--------|-----------|
| 任务分解（怎么拆、拆几个） | Coordinator Agent (LLM) | Harness 可拒绝（环检测失败 / schema 不合法） |
| Agent 推荐（分配给谁） | Coordinator Agent (LLM) | Harness 可覆盖（负载过高 / 能力不匹配） |
| 执行策略（并行/串行） | Coordinator Agent (LLM) → DAG 结构决定 | Harness 编译为 Canvas 时验证 |
| 最终路由 | Harness | 硬约束（权限、预算、负载）不可突破 |

---

### S14: Worker 执行子任务

**数据流**：

```
┌── Celery Worker 拉取任务 ─────────────────────────────────┐
│                                                            │
│  L2 Harness: worker_execute(task_id)                       │
│  │                                                         │
│  ├─ 1. guard_transition(QUEUED → RUNNING)                  │
│  │       · 状态合法性检查                                    │
│  │       · Worker 已分配                                    │
│  │                                                         │
│  ├─ 2. BudgetController.check(task)                        │
│  │       · steps < max_steps (10)                          │
│  │       · tokens_used < max_tokens (100,000)              │
│  │       · elapsed < max_duration (600s)                   │
│  │                                                         │
│  ├─ 3. build_agent_context(task)                           │
│  │       → GlobalContext(task_def, shared_artifact_refs,    │
│  │                       conversation_summary)              │
│  │       → PrivateContext(tool_history=[], intermediate=[]) │
│  │       → AgentContext(global, private)                    │
│  │                                                         │
│  ├─ 4. agent_execute(context)                               │
│  │       │                                                 │
│  │       ▼                                                 │
│  │  L1 LLMAdapter.chat(                                    │
│  │       system=context.to_prompt(),                        │
│  │       messages=[task_description],                       │
│  │       tools=[read_file, write_file, edit_file, ...],     │
│  │       stream=True                                       │
│  │     )                                                    │
│  │       │                                                 │
│  │       ▼ (流式输出到 WS，见 S12)                          │
│  │       │                                                 │
│  │  Agent 调用 Tool (如 write_file)                        │
│  │       │→ 权限检查                                        │
│  │       │→ 如果是 "危险操作" → request_approval (见 S18)   │
│  │       │→ 否则执行 + 写入 task_artifacts                  │
│  │                                                         │
│  ├─ 5. 验证 gate: 任务是否达到 validation_gate?            │
│  │       · 成功 → transition(COMPLETED)                     │
│  │       · 失败 → transition(FAILED) → retry / escalate    │
│  │                                                         │
│  └─ 6. 写入 task_events + task_artifacts                   │
│       发布 TaskStateChanged 事件 → WS 推送                  │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**Worker 上下文注入内容**：

```
┌── 构造的 System Prompt ──────────────────────────┐
│                                                    │
│  ## 当前任务                                       │
│  创建登录页面UI组件，包含邮箱+密码+提交按钮          │
│                                                    │
│  ## 用户需求背景                                   │
│  用户要求做一个完整的登录页面，包含前端UI和后端API    │
│                                                    │
│  ## 共享制品引用                                   │
│  · api_contract:v1 (read_artifact 可获取完整内容)  │
│                                                    │
│  ## 输出规范                                       │
│  使用 React + Tailwind CSS                         │
│                                                    │
│  ## 你的工作记忆                                   │
│  (Agent 私有上下文，跨步骤累积)                     │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

### S15: 任务状态流转 (FSM)

**完整状态机**：

```
                    ┌──────────┐
                    │  PENDING │  任务已创建（手动创建或协调者生成）
                    └────┬─────┘
                         │ Harness 入队
                         ▼
                    ┌──────────┐
                    │  QUEUED  │  等待 Worker 领取
                    └────┬─────┘
                         │ Worker 领取 + Guard 校验通过
                         ▼
                    ┌──────────┐
              ┌─────│ RUNNING  │─────┐
              │     └────┬─────┘     │
              │          │           │
              │     ┌────┼────┐      │
              │     │    │    │      │
              ▼     ▼    │    ▼      ▼
         ┌──────────┐    │  ┌───────────────┐
         │ COMPLETED│    │  │AWAITING_      │  人工介入请求
         │  (终态)  │    │  │APPROVAL       │
         └──────────┘    │  └───┬───┬───┬───┘
                         │      │   │   │
                         │  APPROVE│   │ REJECT
                         │      │   │   │
          ┌──────────┐   │      ▼   │   ▼
          │  FAILED  │───┘  ┌──────────┐  ┌───────────┐
          └────┬─────┘      │  RUNNING │  │ CANCELLED │
               │            │ (恢复执行)│  │  (终态)   │
               │ 重试       └──────────┘  └───────────┘
               │ (retry_count < 3)
               ▼
          ┌──────────┐
          │  QUEUED  │  (重新入队，可能换 Worker)
          └──────────┘

          ┌──────────┐
          │  PAUSED  │  用户手动暂停
          └────┬─────┘
               │ 恢复
               ▼
          ┌──────────┐
          │ RUNNING  │
          └──────────┘
```

**状态转换表**：

```python
VALID_TRANSITIONS = {
    PENDING:             {QUEUED, CANCELLED},
    QUEUED:              {RUNNING, CANCELLED},
    RUNNING:             {COMPLETED, FAILED, AWAITING_APPROVAL, PAUSED, CANCELLED},
    AWAITING_APPROVAL:   {RUNNING, CANCELLED},
    PAUSED:              {RUNNING, CANCELLED},
    FAILED:              {QUEUED, CANCELLED},
    COMPLETED:           set(),    # 终态
    CANCELLED:           set(),    # 终态
}
```

**Guard 校验规则**：

| 目标状态 | 前置条件 | 失败处理 |
|---------|---------|---------|
| QUEUED | task 已创建，worker_type 已确定 | fail |
| RUNNING | worker 已分配（assigned_worker 非空） | retry |
| RUNNING | BudgetController.check() 全部通过 | fail |
| COMPLETED | gates_passed = True（验证门控通过） | escalate |
| FAILED | 无限制（任何状态都可标记失败） | - |
| AWAITING_APPROVAL | 当前状态必须是 RUNNING | fail |

---

### S16: 手动创建任务

**数据流**：

```
┌──────────┐  POST /api/tasks           ┌──────────────┐
│  L5 前端  │ ──────────────────────────▶│  L4 API      │
│TaskCreate│ ◀──────────────────────────│ TaskRouter    │
│ 表单:     │  201 + TaskResponse        │              │
│ 标题/描述  │                            │              │
│ 负责人/群组│                            │              │
│ 截止日期  │                            │              │
│ 优先级    │                            │              │
│ 标签      │                            │              │
│ 父任务    │                            │              │
└──────────┘                            └──────┬───────┘
                                                │
                             CreateTaskCommand   │
                                                ▼
                                       ┌──────────────┐
                                       │  L3          │
                                       │TaskService   │
                                       │ .create_task()│
                                       └──────┬───────┘
                                              │
                    1. 校验 assignee 存在且可用  │
                    2. 如果 parent_task_id 非空: │
                       → 校验父任务存在             │
                       → 校验嵌套深度 ≤ 1          │
                    3. 创建 Task 聚合根            │
                    4. 如果 assignee_type=agent:  │
                       → 直接创建子任务并入队执行    │
                    5. 如果 assignee_type=group:  │
                       → 触发该群组的协调者分解      │
                                              │
                                       ┌──────┴──────┐
                                       ▼              ▼
                                ┌──────────┐  ┌──────────────┐
                                │  L2 Task │  │  L1 TaskRepo │
                                └──────────┘  └──────────────┘

事件: TaskCreated → Redis Pub/Sub → 通知相关方
     如果 parent_task_id 非空 → 也通知父任务的关注者
```

---

### S17: 任务列表筛选

**数据流**：

```
┌──────────┐  GET /api/tasks?            ┌──────────────┐
│  L5 前端  │    status=running,pending   │  L4 API      │
│TaskBoard │   &priority=high,critical   │ TaskRouter    │
│ 看板视图  │   &assignee_id=xxx          │              │
│ 筛选栏:   │   &sort_by=due_date         │              │
│ □ 状态    │   &sort_order=asc           │              │
│ □ 优先级  │ ──────────────────────────▶ │              │
│ □ 负责人  │ ◀────────────────────────── │              │
│ □ 时间    │  200 + TaskListResponse     │              │
│ □ 标签    │                             │              │
└──────────┘                             └──────┬───────┘
                                                 │
                              ListTasksCommand    │
                                                 ▼
                                        ┌──────────────┐
                                        │  L3          │
                                        │TaskService   │
                                        │ .list_tasks()│
                                        └──────┬───────┘
                                               │
                                   构造动态查询   │
                                               ▼
                                        ┌──────────────┐
                                        │  L1 TaskRepo │
                                        │ .filter(     │
                                        │   status IN [],│
                                        │   priority IN [],│
                                        │   assignee_id=, │
                                        │   due_between,  │
                                        │   tags @>,      │
                                        │   parent_task_id│
                                        │   ORDER BY ...  │
                                        │   LIMIT/OFFSET  │
                                        │ )              │
                                        └──────────────┘
```

---

### S18: Agent 请求审批

**触发条件**：Agent 执行过程中调用 `delete_file` / `git_push` / `deploy` / `network_access` 等需审批操作。

**数据流**：

```
L2 Worker 执行到危险操作
  │
  ├─ Worker 调用 Tool（如 delete_file）
  │
  ├─ Tool 检查操作权限: 需要审批
  │
  ├─ Harness: transition_state(RUNNING → AWAITING_APPROVAL)
  │     │
  │     ├─ Guard 校验: from_state = RUNNING → allowed ✓
  │     │
  │     ├─ 写入 task_events:
  │     │     event_type = "state_changed"
  │     │     event_data = {"new_state":"awaiting_approval", "checkpoint": {...}}
  │     │
  │     ├─ 创建 ApprovalRequest:
  │     │     task_id, agent_id, action="delete_file",
  │     │     reason="删除不再使用的 utils.ts",
  │     │     checkpoint={execution_context_snapshot}
  │     │
  │     └─ 发布 ApprovalRequested 事件
  │
  └─ L3 InboxService 接收事件
        │
        ├─ 创建 Notification:
        │     category = "approval"
        │     title = "FrontendAgent 请求删除文件"
        │     content = "utils.ts"
        │
        ├─ 持久化 Notification
        │
        └─ Redis Pub/Sub → WS Push 到用户客户端
            → 收件箱图标 Badge +1
```

---

### S19: 用户 APPROVE/REJECT

**数据流**：

```
用户在收件箱/聊天界面点击 APPROVE
  │
  ▼
L4 API: POST /api/approvals/{task_id}/approve
  │
  ▼
L3 InboxService.handle_approval()
  │
  ├─ 查找 task_id 对应的 AWAITING_APPROVAL 事件
  │
  ├─ 从 checkpoint 恢复执行上下文
  │
  ├─ 调用 Harness: handle_human_decision(task_id, APPROVE)
  │     │
  │     ├─ transition_state(AWAITING_APPROVAL → RUNNING, checkpoint)
  │     │     │
  │     │     └─ Guard 校验: from_state = AWAITING_APPROVAL → allowed ✓
  │     │
  │     ├─ Worker 从 checkpoint 恢复，继续执行
  │     │   （危险操作被批准，执行 delete_file / push / deploy）
  │     │
  │     └─ 写入 task_events:
  │           event_type = "human_approved"
  │           actor = "user:{user_id}"
  │
  ├─ 发布 ApprovalResolved(decision=APPROVE)
  │
  └─ 标记 Notification 为已读
       → Redis Pub/Sub → WS Push 更新收件箱
```

**REJECT 流程**：
```
用户 REJECT
  → transition_state(AWAITING_APPROVAL → CANCELLED)
  → 不会重新执行，任务以 CANCELLED 终态结束
  → 如果此子任务被其他任务依赖 → 父任务收到通知，协调者重新规划
```

**EDIT / RESPOND 流程**：
```
用户 EDIT:
  → checkpoint 合并用户的修改内容
  → transition_state(AWAITING_APPROVAL → RUNNING, updated_checkpoint)
  → Worker 基于修改后的上下文继续执行

用户 RESPOND:
  → checkpoint 注入 human_input
  → transition_state(AWAITING_APPROVAL → RUNNING, checkpoint_with_input)
  → Worker 基于补充信息重新处理
```

---

### S20: 通知生成 + 未读计数

**数据流**：

```
各场景触发通知:
  ├─ ApprovalRequested     → Notification(category="approval")
  ├─ TaskStateChanged      → Notification(category="task")
  │   (仅 completed/failed/assigned 时)
  ├─ MemberAdded           → Notification(category="task")
  │   ("你被加入群组 {name}")
  └─ TaskDueReminder       → Notification(category="calendar")

L3 InboxService 或 Event Handler:
  │
  ├─ 1. 创建 Notification 实体
  │
  ├─ 2. NotificationRepository.save(notification)
  │
  ├─ 3. Redis: INCR "unread_count:{user_id}"
  │
  └─ 4. Redis Pub/Sub → WS Push:
         {
           type: "inbox_update",
           unread_count: 5,
           latest_notification: { title, category, ... }
         }
  │
  ▼
L4 WS Handler → L5 前端
  → 左侧导航栏收件箱图标 Badge 更新
  → 如果用户正在收件箱页面 → 列表实时插入新通知
```

**未读计数 API**：

```
GET /api/inbox/unread-count

Response:
{
  "total": 5,
  "by_category": {
    "approval": 3,
    "task": 2,
    "calendar": 0
  }
}

实现: Redis GET "unread_count:{user_id}" (实时)
      如果 Redis 未命中 → PG COUNT(*) WHERE is_read=false
```

---

### S21: 日历视图

**数据流**：

```
GET /api/inbox?category=calendar&due_before=2026-06-30&due_after=2026-05-01

L3 InboxService → TaskRepository.get_tasks_with_due_date(
    assignee_id=当前用户相关的 Agent,
    due_between=[start, end]
  )

Response:
{
  "calendar_events": [
    {
      "date": "2026-05-25",
      "tasks": [
        {"id": "..", "title": "完成登录页面UI", "priority": "high", "status": "running"},
        {"id": "..", "title": "API 接口文档", "priority": "medium", "status": "pending"}
      ]
    },
    {
      "date": "2026-05-28",
      "tasks": [...]
    }
  ]
}

L5 渲染为月/周/日视图:
  · 过期任务标红
  · 点击日期展开任务列表
  · 拖拽修改截止日期 (PATCH /api/tasks/{id} {due_date: ...})
```

---

### S22: 上下文注入（发送消息时）

**时机**：每次 Agent 执行任务前，Harness 构建 AgentContext。

```
L2 Harness.build_agent_context(task):
  │
  ├─ 1. GlobalContext:
  │      · task_definition: 当前任务描述 + 输入 Schema
  │      · shared_artifact_refs: 与本任务相关的已接受共享制品引用列表
  │      · conversation_summary: 用户原始需求的压缩摘要 (<500 tokens)
  │
  ├─ 2. PrivateContext:
  │      · 从 Redis/L1 获取:
  │        - 该 Agent 在此会话中的前序工具调用历史
  │        - 该 Agent 的中间产物列表
  │        - 该 Agent 的跨步骤工作记忆
  │
  └─ 3. 编译为 System Prompt → 注入 LLM 调用

AgentContext.to_prompt():
"""
## 当前任务
{task_definition}

## 用户需求背景
{conversation_summary}

## 共享制品引用
{artifact_refs}  ← 只存引用，Agent 通过 read_artifact 工具获取完整内容

## 你的工作历史
{tool_results_summary}

## 你的工作记忆
{agent_memory}
"""
```

**上下文三层体系**：

| 层级 | 内容 | 存储 | 生命周期 | Token 估算 |
|------|------|------|---------|-----------|
| 热上下文 | 最近 15-20 条消息全文 | Redis | 当前会话窗口 | ~2000-4000 |
| 长期上下文 | Pin 消息 + 对话摘要 | PostgreSQL | 跨会话持久 | ~500-1000 |
| 历史预览 | 更早对话的摘要占位 | 本地 JSON | 用户手动查看 | 0（不占用 LLM 上下文） |

---

### S23: Pin 消息

```
用户长按消息 → 选择 "Pin 为长期上下文"

L5 → L4: POST /api/messages/{message_id}/pin

L4 → L3: PinMessageCommand(session_id, message_id)

L3 ChatService.pin_message():
  │
  ├─ 标记 message.pinned = True
  ├─ 重新生成会话摘要（包含 Pin 消息内容）
  ├─ 更新 Session 的 long_term_context 字段
  │
  └─ 发布 MessagePinned 事件

效果:
  · Pin 消息永久保留在长期上下文中，不随对话压缩丢失
  · 后续 Agent 调用的 system prompt 会包含 "## 长期上下文: {pinned_content}"
  · 最多 Pin 10 条消息（超限提示用户先取消旧的）
```

---

### S24: 长对话压缩

**触发条件**：会话消息数 > 20 条，且用户下一条消息到达时。

```
L3 ChatService.compress_context(session_id):
  │
  ├─ 1. 保留最近 20 条消息（热上下文，不压缩）
  │
  ├─ 2. 保留所有 Pin 消息（长期上下文，不压缩）
  │
  ├─ 3. 对 20 条之前的消息进行压缩:
  │      调用 LLM (小模型, 如 Haiku):
  │        "请将以下对话压缩为 3-5 句摘要，保留关键决策和任务结果"
  │
  ├─ 4. 存储压缩结果到 Session.compressed_summary
  │
  ├─ 5. 后续 Agent 调用的 system prompt:
  │      "## 历史对话摘要: {compressed_summary}"
  │
  ├─ 6. 完整对话历史保留在 本地文件系统 (.agenthub/sessions/{id}/full_history.json)
  │      用户可通过 "查看完整对话" 按钮展开
  │
  └─ 事件: ContextCompressed → 更新 Session 元数据
```

---

## 四、接口清单

### 4.1 Agent

| 方法 | 路径 | Command | 权限 |
|------|------|---------|------|
| POST | `/api/agents` | `CreateAgentCommand` | 登录用户 |
| POST | `/api/agents/draft` | `{description: str}` → `{system_prompt, capability_tags}` | 登录用户（对话式创建用） |
| GET | `/api/agents` | - (Query: `status?, capability?`) | 登录用户 |
| GET | `/api/agents/{id}` | - | 登录用户 |
| PATCH | `/api/agents/{id}` | `UpdateAgentCommand` | 管理员 |
| DELETE | `/api/agents/{id}` | `DeleteAgentCommand` | 管理员 |
| GET | `/api/agents/{id}/tasks` | - (Query: `status?, page?`) | 登录用户 |
| GET | `/api/agents/{id}/activities` | - (Query: `page?`) | 登录用户 |
| GET | `/api/agents/{id}/memory` | - | 登录用户 |
| PATCH | `/api/agents/{id}/memory` | `UpdateMemoryCommand` | 管理员 |
| GET | `/api/agents/{id}/channels` | - | 登录用户 |

### 4.2 群组

| 方法 | 路径 | Command | 说明 |
|------|------|---------|------|
| POST | `/api/groups` | `CreateGroupCommand` | 自动生成协调者 |
| GET | `/api/groups` | - | 群组列表 |
| GET | `/api/groups/{id}` | - | 群组详情（含成员、协调者） |
| PATCH | `/api/groups/{id}` | `UpdateGroupCommand` | 修改名称/描述 |
| DELETE | `/api/groups/{id}` | - | 级联删除协调者 |
| POST | `/api/groups/{id}/members` | `AddMemberCommand` | 添加 Agent |
| DELETE | `/api/groups/{id}/members/{agent_id}` | - | 移除 Agent |

### 4.3 会话 & 消息

| 方法 | 路径 | Command | 说明 |
|------|------|---------|------|
| POST | `/api/sessions` | `CreateSessionCommand` | 群聊或私聊 |
| GET | `/api/sessions` | - (Query: `type?`) | 会话列表 |
| GET | `/api/sessions/{id}` | - | 会话详情 |
| GET | `/api/sessions/{id}/messages` | - (Query: `before?, limit?`) | 消息历史（分页） |
| POST | `/api/sessions/{id}/messages` | `SendMessageCommand` | 发送消息 |
| WS | `/ws/sessions/{id}` | - | WebSocket 双向通信 |
| POST | `/api/messages/{id}/pin` | `PinMessageCommand` | Pin 消息 |
| DELETE | `/api/messages/{id}/pin` | - | 取消 Pin |

### 4.4 任务

| 方法 | 路径 | Command | 说明 |
|------|------|---------|------|
| POST | `/api/tasks` | `CreateTaskCommand` | 手动创建 |
| GET | `/api/tasks` | `ListTasksCommand` (Query params) | 筛选列表 |
| GET | `/api/tasks/{id}` | - | 任务详情（含子任务） |
| PATCH | `/api/tasks/{id}` | `UpdateTaskCommand` | 更新属性 |
| GET | `/api/tasks/{id}/events` | - | 事件日志 |
| GET | `/api/tasks/{id}/artifacts` | - | 产物列表 |

**筛选 Query 参数（GET /api/tasks）**：

| 参数 | 类型 | 示例 |
|------|------|------|
| `status` | string (逗号分隔) | `running,pending` |
| `priority` | string (逗号分隔) | `high,critical` |
| `assignee_id` | UUID | |
| `due_before` | ISO 8601 | `2026-06-30T00:00:00Z` |
| `due_after` | ISO 8601 | `2026-05-01T00:00:00Z` |
| `tags` | string (逗号分隔) | `frontend,urgent` |
| `parent_task_id` | UUID | 筛选某个父任务的子任务 |
| `sort_by` | enum | `created_at` / `due_date` / `priority` |
| `sort_order` | enum | `asc` / `desc` |
| `page` | int | 默认 1 |
| `page_size` | int | 默认 20, 最大 100 |

### 4.5 审批

| 方法 | 路径 | Command | 说明 |
|------|------|---------|------|
| POST | `/api/approvals/{task_id}/approve` | `HandleApprovalCommand(decision=approve)` | 审批通过 |
| POST | `/api/approvals/{task_id}/reject` | `HandleApprovalCommand(decision=reject)` | 审批拒绝 |
| POST | `/api/approvals/{task_id}/edit` | `HandleApprovalCommand(decision=edit, payload={edits})` | 修改后继续 |
| POST | `/api/approvals/{task_id}/respond` | `HandleApprovalCommand(decision=respond, payload={response})` | 补充信息 |

### 4.6 收件箱

| 方法 | 路径 | Command | 说明 |
|------|------|---------|------|
| GET | `/api/inbox` | `ListInboxCommand` (Query params) | 通知列表 |
| GET | `/api/inbox/unread-count` | - | 未读计数 |
| PATCH | `/api/inbox/read` | `MarkReadCommand` | 标记已读 |
| GET | `/api/inbox/calendar` | Query: `from, to` | 日历视图事件 |

---

## 五、附录：事件总线全景

```
场景          发布的事件                   消费者
─────────────────────────────────────────────────────
S1 添加Agent  AgentCreated               (日志)
S2 编辑Agent  AgentUpdated               相关群组的 WS 通知
S3 删除Agent  AgentDeleted               GroupService(自动踢出) + 相关会话关闭
S5 创建群组    GroupCreated               WS 通知创建者
S6 添加成员    MemberAdded                WS 通知群组全体 + Agent 的 Agent 列表更新
S7 移除成员    MemberRemoved              WS 通知群组全体
S8 群聊消息    MessageSent               WS 广播给会话所有客户端
S8 分解任务    TaskCreated+SubTaskCreated  WS 推送到群聊(子任务卡片)
S13 入队执行   TaskStateChanged           WS 推送状态变更
S14 Worker执行 StreamingToken×N          WS 推送流式 token 到客户端
S14 执行完成   TaskStateChanged(completed) WS 推送 + 检查依赖解锁下游任务
S15 任务失败   TaskStateChanged(failed)   Harness(重试逻辑) + WS 推送
S18 请求审批   ApprovalRequested          InboxService(创建通知) + WS 推送
S19 APPROVE   ApprovalResolved           Harness(恢复执行) + 收件箱更新
S20 通知       NotificationCreated        WS 推送到收件箱客户端
S24 压缩上下文 ContextCompressed          (日志 + Session 元数据更新)
```

---

## 六、技术实现要点

### 6.1 L3 层 Service 的事务边界

```python
class AgentService:
    def __init__(self, agent_repo: AgentRepository, event_bus: EventBus):
        self.agent_repo = agent_repo
        self.event_bus = event_bus

    async def create(self, cmd: CreateAgentCommand) -> AgentResponse:
        # 1. 领域校验（L2）
        if await self.agent_repo.exists_by_name(cmd.name):
            raise DomainError("Agent name already exists")

        # 2. 创建聚合根（L2）
        agent = Agent(
            name=cmd.name,
            avatar=cmd.avatar,
            role=cmd.role,
            provider=cmd.provider,
            model=cmd.model,
            api_key_encrypted=encrypt(cmd.api_key),  # L3 负责加密
            skills=cmd.skills,
            system_prompt=cmd.system_prompt,
        )

        # 3. 持久化（L1）
        await self.agent_repo.save(agent)

        # 4. 发布事件
        await self.event_bus.publish(AgentCreated(
            agent_id=agent.id,
            name=agent.name,
            timestamp=datetime.utcnow(),
        ))

        return AgentResponse.from_domain(agent)
```

### 6.2 L2 Task Engine 的核心接口

```python
class CoordinatorService:
    """L3 调用此接口触发任务分解"""
    async def decompose_and_dispatch(
        self,
        message: str,
        session_id: UUID,
        group_id: UUID,
        available_agents: list[Agent],
        conversation_history: list[Message],
    ) -> TaskPlan:
        # 1. 构造 Coordinator Agent 的 prompt
        prompt = self._build_coordinator_prompt(
            message, available_agents, conversation_history
        )
        # 2. LLM 调用 → 结构化决策
        decision = await self.llm_adapter.chat_structured(prompt)
        # 3. Harness 校验 + 编译
        return self.harness.validate_and_execute(decision, session_id)


class Harness:
    """纯代码，不含 LLM 调用"""
    def validate_and_execute(self, decision: dict, session_id: UUID) -> TaskPlan:
        plan = TaskPlan(**decision["plan"])
        if detect_cycle(plan):
            raise RejectDecision("循环依赖")
        for task in plan.tasks:
            task.assigned_worker = self.route_worker(
                suggested=task.suggested_worker,
                workload=self.blackboard.get_worker_load(),
            )
        canvas = compile_to_canvas(plan)
        canvas.apply_async()
        return plan
```

### 6.3 依赖注入示意

```python
# L1 实现 L2 定义的抽象
class PostgresAgentRepository(AgentRepository):
    async def save(self, agent: Agent): ...
    async def get_by_id(self, id: UUID) -> Agent: ...
    async def exists_by_name(self, name: str) -> bool: ...

class CeleryTaskQueue(TaskQueue):
    def apply_async(self, canvas: Canvas): ...

class AnthropicLLMAdapter(LLMAdapter):
    async def chat_structured(self, prompt: str) -> dict: ...
    async def stream(self, prompt: str) -> AsyncGenerator[str]: ...

# FastAPI DI 组装
async def get_agent_service(
    repo: AgentRepository = Depends(get_agent_repo),
    event_bus: EventBus = Depends(get_event_bus),
) -> AgentService:
    return AgentService(repo, event_bus)
```
