# 域2：Agent 编排系统 — 任务清单

> 职责：Agent 管理、群组管理、任务分解、DAG 执行、HITL 审批、Worker 调度
> 技术栈：FastAPI (Coordinator/TaskEngine) + asyncio.gather + PostgreSQL (tasks/events) + Redis (限流)

---

## 一、域2 系统范围

```
┌─ 前端（域1 组件复用）──────────────┐
│ AgentPanel (创建/列表/详情)         │
│ AgentDetail (6 Tab)                 │
│ TaskBoard (列表/看板)               │
│ GroupDetail (成员+协调者)            │
└────────────┬───────────────────────┘
             │ REST + WS
┌────────────┴───────────────────────┐
│ L4: AgentRouter / GroupRouter /    │
│     TaskRouter / ApprovalRouter    │
└────────────┬───────────────────────┘
             │
┌────────────┴───────────────────────┐
│ L3: AgentService / GroupService /  │
│     TaskService / CoordinatorService│
└────────────┬───────────────────────┘
             │
┌────────────┴───────────────────────┐
│ L2: TaskEngine                     │
│   Coordinator Agent (LLM)          │
│   Harness (FSM+Guard+DAG+Budget)   │
│   Blackboard (tasks/events/artifacts)│
└────────────┬───────────────────────┘
             │
┌────────────┴───────────────────────┐
│ L1: asyncio.gather + Redis 限流    │
│   PostgreSQL (tasks/agents/groups) │
└────────────────────────────────────┘
```

---

## 二、全部任务

### M1（5/20-22）：脚手架 + Adapter

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 2.1 | FastAPI + Docker Compose + Alembic | 4h | 前后端通信 OK |
| 2.2 | 12 张表 migration + SQLAlchemy ORM | 4h | migrate/rollback 成功 |
| 2.3 | ClaudeAdapter (调用 Claude Code CLI) | 8h | 发送 prompt → 流式响应 |
| 2.4 | CodexAdapter | 4h | 同上 |
| 2.5 | TraeAdapter | 4h | 同上 |
| 2.6 | Agent CRUD API + agent_system 两级选择 | 4h | 创建/列表/详情/更新/删除 |
| 2.7 | API Key AES-256-GCM 加密存储 | 2h | 明文不可查看 |

### M2（5/23-27）：私聊执行

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 2.8 | dispatch_mode=direct: 消息→创建Task→Worker执行 | 6h | 私聊发消息→Agent回复 |
| 2.9 | L3 ChatService + L2 Worker 基础链路 | 8h | 消息→L2→L1 Adapter→流式→L5 |
| 2.10 | Agent Context 构建 (Global+Private) | 4h | 上下文正确注入 |
| 2.11 | 热上下文 (Redis 滑动窗口 20条) | 4h | Agent 理解多轮对话 |

### M3（5/28-6/1）：编排核心

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 2.12 | Group CRUD + 协调者自动创建 | 6h | 创建群组→协调者出现 |
| 2.13 | dispatch_mode=auto + @mentions 路由 | 6h | @协调者→触发 / @Agent→路由 / 无@→检测 |
| 2.14 | Coordinator Agent Prompt + Few-shot | 10h | 输入需求→结构化 TaskPlan JSON |
| 2.15 | Harness: TaskPlan 校验 + 环检测 | 4h | 非法 plan 拒绝 |
| 2.16 | Harness: DAG → asyncio.gather 编译 | 4h | asyncio.gather() 入队 |
| 2.17 | Worker 并行执行 (asyncio.gather) | 6h | 2 Agent 并行→结果各自产出 |
| 2.18 | Task FSM (8态) + Guard Functions | 6h | 合法转换通过/非法拒绝 |
| 2.19 | tasks.status 状态字段 | 4h | 追加不可变，崩溃可恢复 |
| 2.20 | Budget Controller (四道硬闸) | 2h | 超限自动终止 |

### M4（6/2-5）：Agent 管理 + 审批 + 任务看板

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 2.21 | Agent 详情页 6 Tab API (概览/能力/任务/活动/群组/记忆) | 6h | 各 Tab 数据正确 |
| 2.22 | 对话式创建 Agent: 描述→草案→确认 | 4h | LLM 生成 system_prompt + tags |
| 2.23 | HITL 审批: AWAITING_APPROVAL 状态 + APPROVE/REJECT/EDIT/RESPOND | 6h | 暂停→审批→继续/取消 |
| 2.24 | Notification 创建 + Redis 未读计数 | 4h | 收件箱 Badge 实时更新 |
| 2.25 | 任务看板 API (筛选/排序/分页) | 6h | 多条件组合筛选 |
| 2.26 | 父任务+子任务 DAG 关系维护 | 4h | 嵌套深度≤1 校验 |

### M5（6/6-9）：可靠性

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 2.27 | Worker 故障隔离 + 重试 + 指数退避 | 4h | 3次失败→隔离→重新分配 |
| 2.28 | Token 监控 + 每日预算 | 4h | 达80%告警/95%阻止 |
| 2.29 | 审批超时自动拒绝 (24h) | 2h | 超时→CANCELLED |

---

## 三、工时汇总

| M | 工时 |
|----|------|
| M1 | 30h |
| M2 | 22h |
| M3 | 48h |
| M4 | 30h |
| M5 | 10h |
| **合计** | **140h** |

---

## 四、关键文件

```
src/backend/app/
├── api/
│   ├── agents.py              # L4 Agent CRUD
│   ├── groups.py              # L4 Group CRUD + member
│   ├── tasks.py               # L4 Task CRUD + list
│   └── approvals.py           # L4 Approval handlers
├── services/
│   ├── agent_service.py       # L3 Agent 用例编排
│   ├── group_service.py       # L3 Group + Coordinator
│   ├── chat_service.py        # L3 消息发送 + 路由判断
│   ├── task_service.py        # L3 任务 CRUD + 筛选
│   ├── coordinator_service.py # L3 协调者入口
│   └── inbox_service.py       # L3 通知 + 审批
├── domain/
│   ├── agent.py               # L2 Agent 聚合根
│   ├── group.py               # L2 Group 聚合根
│   ├── task.py                # L2 Task 聚合根 + FSM
│   ├── task_engine.py         # L2 FSM + Guard + DAG编译 + Budget
│   ├── coordinator.py         # L2 Coordinator Agent (LLM) + Harness
│   └── events.py              # L2 Domain Events 定义
├── adapters/
│   ├── base.py                # L1 LLMAdapter 抽象
│   ├── claude_adapter.py      # L1 Claude Code CLI
│   ├── codex_adapter.py       # L1 Codex CLI
│   └── trae_adapter.py        # L1 TRAE API
└── infrastructure/
    ├── repositories/          # L1 PG Repos
    ├── redis.py               # L1 Redis: Pub/Sub + 热上下文 + 限流
    └── encryption.py          # L1 API Key AES 加密
```
