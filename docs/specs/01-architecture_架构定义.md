# AgentHub 分层架构定义

> 版本：v2.2 | 基于 PRD v4.0 + 架构设计 v1.0 | 2026-05-23
> v2.2: 摘除 Celery（asyncio.gather 替代）、LiteLLM（降级为未来方案）、对齐 v4 接口

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
L1  Infrastructure   PostgreSQL (SQLAlchemy) / Redis / FileSystem
                    LLM Adapters (API): ClaudeAdapter / OpenAICompatAdapter / MockAdapter
                    Agent Runtimes (CLI): ClaudeCodeRuntime / CodexRuntime / TraeRuntime
                    WS Bridge (Redis→WS Broadcast) + SessionStore (Redis)
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

### 2.1 双轨适配架构

> v2.1 变更：原 LiteLLM Proxy 方案替换为双轨架构。详见 `DOC-15-claude-adapter-design.md`。

CLI 工具（Claude Code / Codex / Trae）自带完整 Harness（tool 执行、会话记忆、权限控制），与 HTTP API 的无状态调用有本质差异。强行统一到同一抽象会丢失 CLI 的免费 Harness 能力。因此 L2 定义两个并行抽象基类：

```
L2 Domain — 接口定义
  UnifiedAgent (ABC)                    ← 顶层抽象，L3 只依赖此接口
    │
    ├── LLMAdapter (ABC)                ← API 模式：无状态，AgentHub 控制 tool loop
    │   stream(AgentRequest) → AsyncIterator[StreamEvent]
    │   chat_structured(prompt) → dict
    │
    └── AgentRuntime (ABC)              ← CLI 模式：有状态，CLI 自控 tool loop
        stream(AgentRequest) → AsyncIterator[StreamEvent]
        chat_structured(prompt) → dict
        kill(session_id) → None
        send_decision(session_id, decision) → None

L1 Infrastructure — 实现
  LLMAdapter 实现（API 轨道）
    ├── ClaudeAdapter           (Anthropic API)              ✅ 已实现
    ├── OpenAICompatAdapter     (DeepSeek / Groq / vLLM)     [未来扩展]
    └── MockAdapter             (本地假数据)                   ✅ 已实现

  AgentRuntime 实现（CLI 轨道）                               ← 当前优先
    ├── ClaudeCodeRuntime       (claude --resume + stdout)
    ├── CodexRuntime            (codex CLI)                   [未来]
    └── TraeRuntime             (trae CLI)                    [未来]
```

**L3 ChatService 对两轨的消费方式不同**：

```
LLMAdapter（API 模式）：
  ChatService 自己管 tool loop（M3 自建或引入 Agent SDK 作为 Harness）
  每次调用是一次无状态的 LLM 请求

AgentRuntime（CLI 模式）：
  ChatService 委托整个任务，只转发事件 + 拦截 HITL 审批
  CLI 自己管理 tool 调用、会话记忆、多轮推理
```

**适配器工厂**：
```python
build_adapter(mode, **kwargs) → UnifiedAgent:
  "anthropic_api" → ClaudeAdapter(api_key, model)
  "claude_code"   → ClaudeCodeRuntime(session_dir)
  "mock"          → MockAdapter()
```

**未来 API 多模型扩展路线**（不影响 CLI 轨道）：

| 方案 | 说明 | 适用时机 |
|------|------|---------|
| 直接 SDK | `OpenAICompatAdapter` 对接 DeepSeek/Groq | 短期，单个 provider |
| Agent SDK | OpenAI Agents SDK / Pydantic AI 做 Harness | 中期，需要 tool loop |
| 协议适配 | LiteLLM Proxy 统一 100+ 模型 | 长期，需要负载均衡/降级 |

> 注：Claude Agent SDK 仅支持 Anthropic 模型，不可用于多模型场景。
> Pydantic AI 和 OpenAI Agents SDK 支持运行时切换模型（含 DeepSeek）。

### 2.2 审批模式

> v2.2 更新：`--print` 模式非交互式，不支持 stdin 写 `y/n`。权限通过检测 result 中的 `permission_denials` + 用户确认后 `--permission-mode bypassPermissions` 重试实现。

| 模式 | Agent `permission_mode` | CLI `--permission-mode` | 行为 |
|------|------------------------|------------------------|------|
| **正常模式**（默认） | `acceptEdits` | `--permission-mode acceptEdits` | 编辑自动通过，Bash/git 等危险操作被阻断 |
| **执行模式** | `bypassPermissions` | `--permission-mode bypassPermissions` | 全自动，不阻断 |

```
正常模式下危险操作:
  1. CLI 执行 Bash: rm -f /tmp/build
  2. CLI 阻断 → tool_result: {is_error: true, content: "was blocked..."}
  3. result 中汇总 permission_denials
  4. ChatService 检测 → emit REQUEST_APPROVAL → 前端审批卡片
  5. 用户 [信任并重试] → ChatService 用 --permission-mode bypassPermissions 重新调用
  6. 用户 [换个方式] → ChatService 重新调用 + feedback 文本
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
    ├─ Coordinator Agent (LLM, API 模式): 任务分解 → JSON
    └─ Harness: 校验 → DAG 编译 → asyncio.gather 并发执行
  → L1 AgentRuntime.stream() 或 LLMAdapter.stream() → 流式输出
  → Redis Pub/Sub → L4 WS Bridge → L5 StreamingText
```

---

## 四、文件系统布局

```
agenthub/
├── src/frontend/              # React + TypeScript (L5)
│   ├── src/
│   │   ├── components/    # chat/ agent/ task/ inbox/ common/
│   │   ├── hooks/         # useWebSocket, useStreaming, useAgent...
│   │   ├── stores/        # Zustand: agent/group/chat/task/inbox/ws
│   │   └── services/      # REST + WS 封装
├── src/backend/               # FastAPI Python (L1-L4)
│   ├── app/
│   │   ├── api/           # L4: Routers + WS Handlers
│   │   ├── services/      # L3: AgentService, ChatService, TaskService...
│   │   ├── domain/        # L2: Agent, Group, Task, TaskFSM, TaskEngine...
│   │   ├── infrastructure/llm/
│   │   │   ├── claude_adapter.py         # ClaudeAdapter (API)
│   │   │   ├── mock_adapter.py           # MockAdapter
│   │   │   └── runtimes/                # AgentRuntime (CLI)
│   │   │       ├── claude_code.py        # ClaudeCodeRuntime
│   │   ├── infrastructure/# L1: PG Repos, Redis, SessionStore
│   │   └── schemas/       # Pydantic v2 Request/Response
│   ├── migrations/        # Alembic
│   └── tests/
├── src/docker/                # Docker Compose + Nginx
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
| 缓存/队列 | Redis 7 | |
| 实时通信 | WebSocket | |
| LLM 接入 | SDK/CLI 双轨（ClaudeAdapter + ClaudeCodeRuntime） | |
| 部署 | Docker 24+ + Nginx 1.25+ | |
