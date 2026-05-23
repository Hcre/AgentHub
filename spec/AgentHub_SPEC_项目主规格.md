# AgentHub SPEC v3.0

> 版本: v3.0 | 日期: 2026-05-23 | 基于 PRD v4 | v4: Celery→asyncio.gather, LiteLLM→暂缓, 12表→6表, CLI优先
> 六大要素：Objective · Commands · Project Structure · Code Style · Testing · Boundaries

---

## 一、Objective — 我们要做什么

### 1.1 产品定义

IM 聊天式多 Agent 协作平台。用户创建 Agent（选系统+配模型）、拉群、像飞书一样 @Agent 下达任务，协调者自动分解、分派、合并结果。代码 Diff、网页预览直接在聊天流中展示。

### 1.2 User Stories（BDD 格式，5 个核心场景）

| # | Story | Given/When/Then |
|---|-------|-----------------|
| S1 | 单聊完成任务 | Given 创建与 Claude Agent 的私聊，When 发送"用 React 写一个计数器"，Then Agent 返回代码块 + 可点击预览卡片 |
| S2 | 群聊多 Agent 协作 | Given 群聊拉入 Frontend + Backend Agent，When 发送"做一个博客系统"，Then 协调者拆解为前后端子任务并分派 |
| S3 | 产物内联预览 | Given Agent 返回代码，When 以 Diff 格式呈现，Then 聊天流中渲染绿色/红色标注的 Diff 视图 |
| S4 | 跨 Agent 上下文传递 | Given 群聊中协调者分解任务，When Worker 收到子任务，Then 自动获得 GlobalContext（任务+制品引用+需求摘要） |
| S5 | 创建自定义 Agent | Given 点击"新建 Agent"，When 选系统(Claude/Codex/Trae)→配模型(任意provider)→填api_key，Then Agent 出现在列表并可调度 |

### 1.3 Non-Goals（本期不做）

- 生产级安全体系（OAuth/RBAC/多用户）— Demo 单用户
- 移动端原生 App — Web 优先
- 完整 CI/CD — v1 聚焦聊天协作
- 语音/视频通话

### 1.4 假设清单

见 [`assumptions_假设清单.md`](assumptions_假设清单.md)。

---

## 二、Commands — 可执行命令

完整见 [`commands_命令接口.md`](commands_命令接口.md)。核心速查：

```bash
# 环境
docker compose up -d postgres redis
make install && make db-migrate && make dev

# CLI
agenthub chat
agenthub agent create   # 选系统→配模型→填信息
agenthub agent list --system claude
```

### 核心 API

```
POST   /api/agents              # 创建 Agent {agent_system, provider, model, api_key...}
GET    /api/agents               # 列表 ?agent_system=claude
POST   /api/groups               # 创建群组（自动生成协调者）
GET    /api/sessions/{id}/messages
POST   /api/sessions/{id}/messages  # {content, mentions, dispatch_mode}
WS     /ws/sessions/{id}          # 实时通信 + 流式
POST   /api/tasks                 # 手动创建任务
GET    /api/tasks                 # 筛选 ?status=running&priority=high
GET    /api/inbox                 # 收件箱 ?category=approval
POST   /api/approvals/{task_id}/approve
```

---

## 三、Project Structure

### 3.1 五层架构

```
L5  Presentation    React + TypeScript  UI (ChatView/AgentPanel/TaskBoard/Inbox)
L4  API Gateway      FastAPI Routers + WS Handlers + Auth Middleware
L3  Application      AgentService / ChatService / TaskService / InboxService...
L2  Domain           Agent/Group/Task 聚合根 + TaskEngine (Coordinator+Harness分离)
L1  Infrastructure   PostgreSQL/Redis/ClaudeCodeRuntime/ClaudeAdapter/MockAdapter
```

完整架构见 [`architecture_架构定义.md`](architecture_架构定义.md)。

### 3.2 Agent 系统与模型（两级选择 + 本地协议代理）

```
Agent 系统 (选运行时)            底层模型 (任意 API)
┌─────────────────────┐     ┌──────────────────────────┐
│ Claude Code         │     │ DeepSeek/GLM/GPT/Claude  │
│ Codex               │────▶│ ...任意 OpenAI 格式 API  │
│ TRAE                │     │                          │
└─────────────────────┘     └──────────────────────────┘

Adapter 内部:
  Claude Code CLI → ANTHROPIC_BASE_URL=localhost:{port}
    → SDK 直连 (v4: LiteLLM 暂缓，降级为未来选项)
      if provider != anthropic:
        Anthropic Messages ↔ OpenAI Chat 格式转换
      → 转发到实际 API
```

借鉴 [ccswitch](https://github.com/farion1231/cc-switch) 的本地代理模式。详见 [`architecture_架构定义.md`](architecture_架构定义.md) §2.1。

### 3.3 审批模式（嵌套权限处理）

| 模式 | 工作区操作 | 危险操作 | Claude Code 内置权限 |
|------|:---:|:---:|------|
| **正常模式** | Always | Ask First | 捕获 permission_request → 转 AgentHub 审批卡片 |
| **执行模式** | Always | Always | `--dangerously-skip-permissions` |

详见 [`boundaries_边界矩阵.md`](boundaries_边界矩阵.md) §零。

### 3.4 目录布局

```
agenthub/
├── frontend/src/
│   ├── components/    # chat/ agent/ task/ inbox/ common/
│   ├── hooks/         # useWebSocket, useStreaming, useAgent...
│   ├── stores/        # Zustand: agent/group/chat/task/inbox/ws
│   └── services/      # REST + WS 封装
├── backend/app/
│   ├── api/           # L4: Routers + WS Handlers
│   ├── services/      # L3: AgentService, ChatService, TaskService...
│   ├── domain/        # L2: Agent, Group, Task, TaskFSM, TaskEngine...
│   ├── adapters/      # L1: ClaudeAdapter, CodexAdapter, TraeAdapter
│   ├── infrastructure/# L1: PG Repos, Redis, asyncio.gather, FileSystem
│   └── schemas/       # Pydantic v2
├── docker/
├── spec/              # SPEC 文档
└── skill/             # Claude Code Skills
```

### 3.4 数据模型

见 [`data-model_数据模型.md`](data-model_数据模型.md)。核心 6 张表：agents / groups / group_members / sessions / messages / tasks（v4 精简，status 字段替代 task_events）。

### 3.5 任务状态机

```
PENDING → QUEUED → RUNNING → COMPLETED (终态)
                    ↓  ↓  ↓
                    │  ├── AWAITING_APPROVAL → RUNNING / CANCELLED
                    │  ├── FAILED → QUEUED (重试 max 3)
                    │  └── PAUSED → RUNNING / CANCELLED
                    └── CANCELLED (终态)
```

### 3.6 消息路由（dispatch_mode）

| dispatch_mode | 行为 |
|---------------|------|
| `auto` (群聊默认) | @协调者→触发 / @AgentName→路由 / 无@→LLM意图检测 |
| `direct` (私聊固定) | 直接发给目标 Agent |

---

## 四、Code Style — 代码规范

完整见规则文件。核心红线：

**Python:** FastAPI async + Pydantic v2 + SQLAlchemy ORM。禁止 print()、裸 SQL、同步阻塞在 async。详见 `rules/code-rules_代码红线.md`。

**TypeScript:** strict mode + Zustand + 组件<200行。禁止 any、console.log 生产路径。详见 `rules/code-rules_代码红线.md`。

**SQL:** Alembic migration 管理。禁止手动改表。

**提交:** Conventional Commits。`feat/fix/refactor/docs/test/chore`。

**架构红线:** 内层不依赖外层。新 Agent 系统只加 Adapter。Harness 不含 LLM。详见 `rules/arch-rules_架构红线.md`。

---

## 五、Testing Strategy

见 [`testing-strategy_测试策略.md`](testing-strategy_测试策略.md)。

- 后端覆盖率 >= 80%，前端 >= 70%
- Mock: LLM API(Fixture) / Tunnel(HTTP Mock)
- 不 Mock: PostgreSQL(Testcontainers) / Redis(Testcontainers) / WebSocket(真实)
- CI: ruff + tsc + pytest + vitest + Playwright E2E

---

## 六、Boundaries

见 [`boundaries_边界矩阵.md`](boundaries_边界矩阵.md)。关键速查：

| Always | Ask First | Never |
|--------|-----------|-------|
| 选系统、配模型 | 删除 Agent | API Key 明文查看 |
| 创建群组（自动协调者） | 删除文件/Git push/部署 | 路径遍历 ../ |
| 任务状态自动流转 | 移除群组成员 | 读写 .env/.git |
| 流式输出 | 审批决策(APPROVE/REJECT) | Harness 含 LLM 调用 |
| API Key AES 加密存储 | 修改 Agent name | 裸 SQL/print/硬编码密钥 |
| 审批超时自动拒绝 | 重置 API Key | 子任务嵌套>1层 |

---

## 七、里程碑

| 里程碑 | 时间 | 交付 |
|--------|------|------|
| M1 环境+验证 | 5/20-22 | 脚手架 + Adapter + 调通 1 个外部 Agent API |
| M2 单聊 MVP | 5/23-27 | 对话列表 + 1v1 聊天 + 流式 + 代码块 |
| M3 群聊+协调者 | 5/28-6/1 | 群聊 + @协调者/自动检测 + DAG + 并行 |
| M4 产物预览 | 6/2-5 | Diff 预览 + iframe 预览 + Pin + 自建 Agent |
| M5 文档+打磨 | 6/6-9 | PRD/架构/SPEC 终稿 + 3min Demo |
| M6 提交 | 6/10 | 仓库整理 + 最终提交 |

---

## 八、文档索引

| 文档 | 内容 |
|------|------|
| [`PRD_AgentHub_v4_统一方案.md`](../docs/PRD_AgentHub_v4_统一方案.md) | 产品需求文档（User Stories + 功能需求） |
| [`架构设计_分层与数据流.md`](架构设计_分层与数据流.md) | 24 个场景完整数据流 + 时序图 |
| [`architecture_架构定义.md`](architecture_架构定义.md) | 5 层架构 + 核心模块定义 |
| [`data-model_数据模型.md`](data-model_数据模型.md) | 6 张表 DDL + Pydantic Schema |
| [`commands_命令接口.md`](commands_命令接口.md) | REST API + WS + CLI 全集 |
| [`boundaries_边界矩阵.md`](boundaries_边界矩阵.md) | Always/Ask First/Never |
| [`testing-strategy_测试策略.md`](testing-strategy_测试策略.md) | 测试策略 + Mock 边界 |
| [`assumptions_假设清单.md`](assumptions_假设清单.md) | 显式假设 |
| [`rules/`](rules/) | 架构/代码/流程红线 |

---

> 版本: v2.1 | 日期: 2026-05-21
> 变更: 按新 PRD + 架构设计重写，5 层架构，Agent 系统两级选择
