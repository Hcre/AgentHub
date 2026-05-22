# AgentHub 分层架构定义

> 版本：v2.0 | 基于 PRD v1.0 + 架构设计 v1.0
> 详细场景数据流见 [`架构设计_分层与数据流.md`](架构设计_分层与数据流.md)

---

## 一、五层架构

```
L5  Presentation    React 18 + TypeScript Strict
                    ChatView / AgentPanel / TaskBoard / Inbox / Settings
                    Zustand Stores + Hooks
        │                          ↑
        ▼                          │
L4  API Gateway      FastAPI Routers + WebSocket Handlers
                    AgentRouter / GroupRouter / TaskRouter / SessionRouter / InboxRouter
                    Middleware: Auth(JWT) / CORS / RateLimit
        │                          ↑
        ▼                          │
L3  Application      AgentService / GroupService / ChatService / TaskService
                    InboxService / CoordinatorService
                    跨领域编排、事务管理、权限校验、事件发布
        │                          ↑
        ▼                          │
L2  Domain           Agent / Group / Session / Message / Task (聚合根)
                    TaskEngine: Coordinator Agent(LLM) + Harness(纯代码)
                    TaskFSM + Validators + DomainEvents
        │                          ↑
        ▼                          │
L1  Infrastructure   PostgreSQL (SQLAlchemy) / Redis / Celery / FileSystem
                    LLM Adapters: ClaudeAdapter / CodexAdapter / TraeAdapter
                    WS Bridge (Redis→WS Broadcast)
```

### 层级边界

| 层 | 职责 | 依赖 |
|----|------|------|
| **L5** | UI 渲染、用户交互、本地状态 | L4 API 契约 |
| **L4** | HTTP/WS 端点、参数校验、鉴权 | 调用 L3 Service |
| **L3** | 用例编排、事务管理、权限校验、事件发布 | L2 领域对象 + 发布事件 |
| **L2** | 领域模型、业务规则、Task Engine | 仅定义接口，不依赖上层 |
| **L1** | 持久化、缓存、队列、LLM 调用 | 实现 L2 定义的接口（依赖倒置） |

### 依赖规则

```
L5 → L4 → L3 → L2 ← L1
              ↑
              └── L1 实现 L2 定义的接口（依赖倒置）
```

跨层通信：**Command（下行）** + **Domain Event（上行）**

---

## 二、核心模块

### 2.1 Adapter 内部代理架构

借鉴 cccswitch 模式，每个 Adapter 内部通过**本地协议代理**完成 API 格式转换：

```
ClaudeAdapter 内部:
┌─────────────────────────────────────────────────────┐
│                                                     │
│  Claude Code CLI                                    │
│  │ (通过 ANTHROPIC_BASE_URL 重定向到本地代理)        │
│  ▼                                                  │
│  ┌──────────────────────────────────┐               │
│  │  LiteLLM Proxy (子进程, 动态端口)  │               │
│  │                                  │               │
│  │  if provider == "anthropic":     │               │
│  │    → 直通, 不转换                │               │
│  │                                  │               │
│  │  if provider == "deepseek":      │               │
│  │    → Anthropic Messages 格式     │               │
│  │    → 转换为 OpenAI Chat 格式     │               │
│  │    → POST https://api.deepseek.com              │
│  │                                  │               │
│  │  if provider == "openai":        │               │
│  │    → 同样的转换逻辑               │               │
│  │                                  │               │
│  │  转换规则:                        │               │
│  │    messages[].role → 透传        │               │
│  │    system prompt → system role   │               │
│  │    stop_sequences → stop         │               │
│  │    stream: true → stream: true   │               │
│  │    响应: chunk delta → 透传      │               │
│  └──────────────────────────────────┘               │
│                                                     │
│  三种 Adapter 都复用同一个 LiteLLM 代理模块:          │
│  ClaudeAdapter → ANTHROPIC_BASE_URL=localhost:{port} │
│  CodexAdapter  → OPENAI_BASE_URL=localhost:{port}    │
│  TraeAdapter   → TRAE 特定配置                       │
│                                                     │
│  Adapter 工厂:                                       │
│  adapter_factory(agent_system, provider, model,      │
│                  api_key, base_url) → LLMAdapter:    │
│    claude → ClaudeAdapter(model, api_key, base_url)  │
│    codex  → CodexAdapter(model, api_key, base_url)   │
│    trae   → TraeAdapter(model, api_key, base_url)    │
└─────────────────────────────────────────────────────┘
```

### 2.2 审批模式

| 模式 | 说明 | Agent 工作区操作 | 危险操作 | Claude Code 内置权限 |
|------|------|:---:|:---:|:---:|
| **正常模式**（默认） | 捕获 Claude Code 权限请求 → 转为 AgentHub 审批卡片 | Always | Ask First | 捕获 permission_request 事件 → 转审批 |
| **执行模式** | 用户明确信任当前会话 | Always | Always | `--dangerously-skip-permissions` 完全跳过 |

```
正常模式下 Claude Code 权限传递:
Claude Code 输出: { type: "permission_request", path: "src/xxx", action: "write" }
  → Adapter 截获 → 查询 AgentHub boundaries 矩阵
    ├─ Always 操作 (创建/编辑文件) → 自动写 "yes\n" 到 Claude Code stdin
    ├─ Ask First 操作 (删除/Git/部署) → 创建审批卡片 → 用户点击 → 写 "yes/no\n"
    └─ Never 操作 (../ / .env) → 自动写 "no\n" → 通知用户被拒绝

执行模式下:
  Claude Code 启动参数加 --dangerously-skip-permissions
  → 所有操作自动通过
```

### 2.3 Agent 系统

创建 Agent 时分两级选择：

```
第1级: Agent 系统 (agent_system)
  ├── Claude  ──→ Anthropic 生态
  ├── Codex   ──→ OpenAI 生态
  └── TRAE    ──→ 字节跳动 TRAE IDE

第2级: 底层模型 (provider + model)
  根据所选系统自动推荐可选模型
```

| Agent 系统 | 典型底层模型 |
|-----------|------------|
| **Claude** | claude-sonnet-4-20250514, claude-opus-4-20250514... |
| **Codex** | gpt-4o, gpt-4o-mini... |
| **TRAE** | TRAE 内置模型 |

创建流程：选系统 → 填写 name/avatar/role → 选 provider/model → 填 api_key → 可选 skills/system_prompt/capability_tags

### 2.2 群组与协调者

- 群组 = 频道，Agent 可同时存在于多个群组
- 创建群组时**自动生成协调者**（Coordinator = AI + Harness）
- 协调者在成员列表中**可见**（蓝色系统标识，不可移除）
- `is_system=True`，名称：`协调者-{群组名称}`

### 2.3 消息路由

| 消息类型 | 行为 |
|---------|------|
| @协调者 | 显式触发任务分解 |
| 自动检测（无@，含任务意图） | LLM 分类 → 触发协调者 |
| @AgentName | 直接路由，协调者不介入 |
| @All | 群组内所有 Agent 响应 |
| 普通聊天 | 仅作为对话上下文 |

### 2.4 Task Engine（Agent-Harness 分离）

| Coordinator Agent (LLM) | Harness (纯 Python) |
|------------------------|---------------------|
| 任务分解方案 | FSM 状态机 + Guard 校验 |
| 异常诊断 | DAG 编译 + 环检测 |
| Agent 推荐 | 预算管控（四道硬闸） |
| 审批建议 | Worker 池管理 + 并发限流 |
| 重试/降级建议 | 失败处理策略执行 |

**Harness 永远不含 LLM 调用。**

### 2.5 任务状态机

```
PENDING → QUEUED → RUNNING → COMPLETED (终态)
                    ↓  ↓  ↓
                    │  │  └── AWAITING_APPROVAL → RUNNING / CANCELLED
                    │  ├── FAILED → QUEUED (重试 max 3)
                    │  └── PAUSED → RUNNING / CANCELLED
                    └── CANCELLED (终态)
```

### 2.6 上下文三层体系

| 层 | 范围 | 存储 | 用途 |
|----|------|------|------|
| 热上下文 | 最近 15-20 条消息 | Redis | 直接注入 LLM prompt |
| 长期上下文 | Pin 消息 + 会话摘要 | PostgreSQL | 跨会话持久化 |
| 历史预览 | 更早对话的摘要占位 | 本地文件系统 | 用户可展开查看 |

---

## 三、核心数据流

```
用户消息 (L5)
  → L4 WS 反序列化 → SendMessageCommand
  → L3 ChatService.send_message()
    ├─ dispatch_mode == "auto":
    │   · @协调者? → 触发
    │   · @AgentName? → 直接路由
    │   · 无@ → LLM 意图检测
    └─ dispatch_mode == "direct" (私聊固定) → 直接发给目标
  → L2 CoordinatorService.decompose_and_dispatch()
    ├─ Coordinator Agent (LLM): 任务分解 → JSON
    └─ Harness: 校验 → DAG 编译 → Celery 入队
  → L1 Celery Worker → LLMAdapter.chat() → 流式输出
  → Redis Pub/Sub → L4 WS Bridge → L5 StreamingText
```

---

## 四、文件系统布局

```
agenthub/
├── frontend/              # React + TypeScript (L5)
│   ├── src/
│   │   ├── components/    # chat/ agent/ task/ inbox/ common/
│   │   ├── hooks/         # useWebSocket, useStreaming, useAgent...
│   │   ├── stores/        # Zustand: agent/group/chat/task/inbox/ws
│   │   └── services/      # REST + WS 封装
├── backend/               # FastAPI Python (L1-L4)
│   ├── app/
│   │   ├── api/           # L4: Routers + WS Handlers
│   │   ├── services/      # L3: AgentService, ChatService, TaskService...
│   │   ├── domain/        # L2: Agent, Group, Task, TaskFSM, TaskEngine...
│   │   ├── adapters/      # L1: ClaudeAdapter, CodexAdapter, TraeAdapter
│   │   ├── infrastructure/# L1: PG Repos, Redis, Celery, FileSystem
│   │   └── schemas/       # Pydantic v2 Request/Response
│   ├── migrations/        # Alembic
│   └── tests/
├── docker/                # Docker Compose + Nginx
├── spec/                  # SPEC + PRD + 架构设计
└── skill/                 # Claude Code Skills
```

---

## 五、技术栈

| 层次 | 技术 | 版本 |
|------|------|------|
| 前端 | React 18 + TypeScript Strict + Vite + Tailwind 3 + Zustand 4 | |
| 后端 | FastAPI (Python 3.12+) + Pydantic v2 + SQLAlchemy | |
| 数据库 | PostgreSQL 16 + pgvector 0.7+ | |
| 缓存/队列 | Redis 7 + Celery 5 | |
| 实时通信 | WebSocket (socket.io) + SSE | |
| LLM 网关 | LiteLLM | |
| 部署 | Docker 24+ + Nginx 1.25+ | |
| CLI/PWA | Click 8.x + Rich 13.x / Workbox 7.x | |
