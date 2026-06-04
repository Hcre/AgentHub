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

---

## §MCP 接入（2026-06-03 修订版）

> 本节由 PR-09 同步 `docs/plan/后续升级计划/MCP接入/README-REVISION.md`（单一权威入口）而来，落地范围与代码空间现状以 README-REVISION §3 §5.1 为准。

### §MCP.1 5 层映射（沿用 AR-01）

| 层 | 本期 MCP 落点（已按真实代码树校正，2026-06-03） |
|----|---------------|
| L1 Infrastructure | `infrastructure/db/models.py`（**追加** 4 表 SQLAlchemy 模型，与现有 8 表同文件，**不新建 `models/` 包**）；`infrastructure/repositories/mcp_repository.py`（repo 实现）；MCP 注入实现落现有 `infrastructure/llm/{claude_code,opencode,pi_agent}_runtime.py`（CLI Adapter 实现 `attach_mcp`）；`infrastructure/mcp/dry_run.py`（dry-run 简化版：单 Docker 容器 + compose 限额） |
| L2 Domain | `domain/mcp/{mcp_server,mcp_installation,mcp_binding,rules}.py`（3 实体 + 8 业务规则，子包与现有 `domain/llm/`、`domain/task_engine/` 先例一致）；`domain/repositories/mcp_repository.py`（repo 接口）；`attach_mcp(...)` 抽象方法加到 `domain/llm/protocol.py::AgentRuntime` |
| L3 Application | `application/services/{mcp_market,mcp_install,mcp_binding,mcp_create,mcp_audit}_service.py`（5 编排服务，扁平 `*_service.py` 与现有 `application/services/` 命名一致；application 按类型分层，**不按特性建 `application/mcp/` 子包**） |
| L4 API | `api/routers/mcp.py`（8 端点，与 `agents.py`/`groups.py` 同级，**无 `v1/` 目录**）+ `api/ws/toolcall.py`（2 WS 事件，复用既有 `api/ws/` 通道） |
| L5 Presentation | `src/frontend/src/pages/McpMarket*` + `McpCreate*` + `components/mcp/*` + `components/agent/McpBindingPanel.tsx` + `stores/mcpStore.ts` + `routes.tsx` |

### §MCP.2 AR-02 满足方式（关键，P2 冻结：请求携带）

> **P2 决策（2026-06-03，[ADR-05](../../worklogs/decisions/0005-mcp-attach-request-carried.md)）**：`attach_mcp` 机制定为**请求携带**而非运行时有状态方法——因 Runtime 池化/进程级共享，跨 agent 持有绑定状态会串号。

- 现有抽象基类 `AgentRuntime(ABC)`（`domain/llm/protocol.py`，契约 `stream(request)` / `stop()`）**不新增有状态方法**；改在 `AgentRequest` 上加 `mcp_servers: list[dict]` 字段（请求携带 MCP config 条目）
- L3 `McpBindingService.build_request_mcp_servers(agent_id)` 解析 agent 的 active 绑定 → installation → server → 序列化为 MCP 2025-06-18 条目；`ContextBuilder` 装配 `AgentRequest` 时经可选 `mcp_resolver` 注入（私聊 + 群聊两路径）
- **统一注入原则（2026-06-04，[ADR-06](../../worklogs/decisions/0006-mcp-injection-per-runtime-isolated-channel.md) 校正 R11）**：每个 Runtime 把 `request.mcp_servers` 翻译成该 CLI 原生 MCP schema，经该 CLI「隔离性最强的逐调用通道」注入；**永不改全局/共享配置**（串号根因）。通道优先级：逐调用 flag > env 指向临时文件 > 逐 workspace 项目配置 > ❌ 全局 mutation。
- **claude_code**：`--mcp-config <tempfile>`（董记忆工具 `_write_mcp_config`，已合并记忆 server + P2 绑定 servers）。✅ 已通。
- **opencode → 拉回本期**（NB-02 → 本期）：本机实测 `OPENCODE_CONFIG=<tmp>` 为逐进程隔离通道（非全局，零串号）。每次 `stream()` 写自包含临时配置（provider+`mcp` 块）经 env 注入；翻译层 `_entry_to_opencode()`（canonical→opencode：`command` 数组化 / env→`environment` / `enabled:true`）；顺带补齐 `agenthub-memory` 记忆。opencode 非长驻 spawn → 无需重 spawn 守卫。代码下一会话落地。
- **pi_agent → 保持 NB-02**：本机无 `pi` 二进制 / 无可查源码 / CLI 无确认 MCP flag → 不可运行验证。`_build_cmd` 留 seam + NB-02 注释；解除前置门 = 确认上游 MCP 支持后按统一原则接入并实测。
- **后续 CLI（codex/gemini，未实现）**：套统一原则——codex 经 `CODEX_HOME`/`-c`，gemini 经项目 `.gemini/settings.json`/env。
- 不另起进程池/sandbox/eventbus（现有 `claude_code_process_pool.py` 为既有进程复用）
- SDK Adapter（F-013）下期增量：在 build_cmd 等价位置读 `request.mcp_servers`

### §MCP.3 跨层依赖（依 AR-01）

```
L5 Presentation → L4 API → L3 Application → L2 Domain ◀── L1 Infrastructure
   (React)        (FastAPI)  (编排)           (实体+规则)  (实现 L2 接口)
```

L1 实现 L2 接口（依赖倒置）；L2 不依赖 L1 具体实现；L3 不直接碰 L1；L4 只做协议层；L5 不直接访问 L1。

### §MCP.4 不引入的层 / 栈

- ❌ 独立「接入层」（合并到 L4）
- ❌ 独立「数据层」（合并到 L1）
- ❌ 独立 eventbus（用既有 Redis pub/sub + WS）
- ❌ 进程池（违反 AR-02）
- ❌ 多 OS 沙箱矩阵（dev/demon 本机不可运行）
- ❌ gRPC / protobuf（现有只有 HTTP/JSON + WS）
- ❌ Vault（用环境变量 + `core/config.py`）
- ❌ OpenTelemetry（PRD B-11 明确不做，trace_id 字符串贯穿）
- ❌ Poetry monorepo（用 `requirements.txt` + `pyproject.toml` pip）
- ❌ Kubernetes（用 `src/docker/docker-compose.yml`）

### §MCP.5 单一权威 + 引用关系

- 单一权威：[`docs/plan/后续升级计划/MCP接入/README-REVISION.md`](../plan/后续升级计划/MCP接入/README-REVISION.md)
- 数据模型：本文件 `03-data-model_数据模型.md` §MCP 子节
- 接口契约（PR-01 冻结草案已落）：`docs/specs/04-commands_命令接口.md` §2.6 MCP API + §三 MCP WS 事件（🔒 待 2 人 Review，P1 启动前完成）
- 不重复叙述：本节仅列**架构层映射**与**AR-02 满足方式**；详细模块/表/端点见上述权威文件

### §MCP.6 修订决策

| 项 | 决策 | 来源 |
|----|------|------|
| 落地包 | 真实 `src/backend/app/`（**不**引 `src/agenthub/`） | 可行性清单 I-01 |
| 表名 | `workspace_mcp_installations`（E-01 修正） | 用户决策 |
| dry-run | 单 Docker 容器 + compose 资源限额（E-03 简化版） | 用户决策 |
| SDK Adapter | 移下期（NB-02），CLI Adapter 预留 `attach_mcp(...)` 扩展点 | 用户决策 |

