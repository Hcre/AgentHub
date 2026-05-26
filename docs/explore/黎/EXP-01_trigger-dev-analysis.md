# EXP-01: Trigger.dev 开源项目深度分析

> 分析日期：2026-05-26
> 仓库：https://github.com/triggerdotdev/trigger.dev
> Stars: 15.1k | 版本：v4.5.0-rc.2 | License: Apache-2.0

## 一、项目概述

Trigger.dev 是一个**开源的后台任务/AI Agent 运行时平台**，用 TypeScript 编写。它的核心定位是填补传统 Serverless 平台（Lambda、Vercel）的执行时长限制空白，专为长时间运行的 AI Agent 和工作流设计。

关键能力：**无限执行时长** + **checkpoint/resume 耐久性** + **Human-in-the-Loop** + **弹性伸缩**。

---

## 二、Monorepo 结构（58 个工作区）

```
trigger.dev/
├── apps/                    # 5 个可部署服务
│   ├── webapp/              # Remix 全栈应用（主 API + 仪表盘）
│   ├── supervisor/          # K8s/Docker 任务编排器
│   ├── coordinator/         # 任务运行 pod 内协调器
│   ├── docker-provider/     # Docker 运行时提供者
│   └── kubernetes-provider/ # K8s 运行时提供者
│
├── packages/                # 10 个公开 npm 包
│   ├── trigger-sdk/         # @trigger.dev/sdk — 核心 SDK
│   ├── core/                # @trigger.dev/core — 共享类型和工具
│   ├── cli-v3/              # trigger.dev CLI（npm: trigger.dev）
│   ├── build/               # @trigger.dev/build — 构建扩展
│   ├── react-hooks/         # @trigger.dev/react-hooks — 前端 SDK
│   ├── redis-worker/        # @trigger.dev/redis-worker — Redis Worker 抽象
│   ├── python/              # @trigger.dev/python — Python 运行时
│   ├── rsc/                 # @trigger.dev/rsc — React Server Components
│   ├── schema-to-json/      # Schema → JSON Schema 转换
│   └── plugins/             # @trigger.dev/plugins — 插件接口
│
├── internal-packages/       # 17 个内部包
│   ├── database/            # Prisma schema + 生成客户端
│   ├── run-engine/          # 核心任务执行引擎
│   ├── schedule-engine/     # Cron 调度引擎
│   ├── redis/               # Redis 客户端封装
│   ├── cache/               # 缓存层
│   ├── compute/             # 计算资源管理
│   ├── tracing/             # OpenTelemetry 追踪
│   ├── clickhouse/          # ClickHouse 分析数据库
│   ├── tsql/                # 类型安全 SQL 构建器
│   ├── replication/         # 数据复制
│   ├── zod-worker/          # Zod schema 验证 Worker
│   ├── llm-model-catalog/   # LLM 模型目录
│   ├── rbac/                # 基于角色的访问控制
│   ├── otlp-importer/       # OTLP 遥测导入
│   ├── emails/              # 邮件发送
│   ├── testcontainers/      # 测试容器
│   └── sdk-compat-tests/    # SDK 兼容性测试
│
└── references/              # 24 个示例/参考项目
```

**依赖中心**：`@trigger.dev/core` 是所有包的枢纽，`webapp` 是最连通的消费者（依赖 15+ 内部包）。

---

## 三、核心编程模型

### 3.1 任务定义

```typescript
// 最简任务
import { task } from "@trigger.dev/sdk/v3";

export const helloWorld = task({
  id: "hello-world",
  run: async (payload: { url: string }) => {
    return { hello: "world" };
  },
});
```

### 3.2 任务调用

```typescript
// 触发并忘记
await tasks.trigger(helloWorld, { url: "..." });

// 触发并等待结果
const result = await tasks.triggerAndWait(helloWorld, { url: "..." });

// 批量触发
await tasks.batchTrigger(helloWorld, [{ url: "a" }, { url: "b" }]);

// 触发并订阅实时更新
await tasks.triggerAndSubscribe(helloWorld, { url: "..." });
```

### 3.3 生命周期钩子

```typescript
tasks.onSuccess(taskX, async ({ payload, output }) => { /* ... */ });
tasks.onFailure(taskX, async ({ payload, error }) => { /* ... */ });
tasks.onComplete(taskX, async ({ payload, output, error }) => { /* ... */ });
tasks.onWait(taskX, async ({ payload }) => { /* ... */ });
tasks.onResume(taskX, async ({ payload }) => { /* ... */ });
tasks.onCancel(taskX, async ({ payload }) => { /* ... */ });
tasks.middleware(taskX, async ({ payload, next }) => { /* ... */ });
```

### 3.4 Human-in-the-Loop（Waitpoint 系统）

这是 Trigger.dev 最具特色的功能：

```typescript
// 创建等待令牌（暂停任务）
const token = await wait.createToken({
  idempotencyKey: `approve-document-${docId}`,
  timeout: "24h",
  tags: [`document-${docId}`],
});

// 在另一处完成等待
await wait.completeToken(token, { status: "approved", comment: "OK" });

// 在任务中等待令牌
const result = await wait.forToken<ApprovalData>(token);
if (result.ok) {
  console.log(result.output); // ApprovalData 类型
}
```

Waitpoint 有 4 种类型：
- **MANUAL**：人工审批/输入
- **DATETIME**：定时等待
- **RUN**：等待另一个任务完成
- **BATCH**：等待整批任务完成

### 3.5 定时调度

```typescript
// 声明式（在任务定义中）
export const dailyReport = task({
  id: "daily-report",
  cron: "0 9 * * *",  // 每天 9am
  run: async () => { /* ... */ },
});

// 命令式（通过 SDK）
await schedules.create({ task: myTask, cron: "*/30 * * * *" });
```

### 3.6 队列和并发

```typescript
const myQueue = queue({ name: "my-queue", concurrencyLimit: 5 });

export const myTask = task({
  id: "my-task",
  queue: myQueue,
  run: async (payload) => { /* ... */ },
});
```

---

## 四、后端架构

### 4.1 基础设施

| 组件 | 用途 |
|------|------|
| **PostgreSQL** | 主数据库（Prisma ORM），含 pg_partman 分区扩展 |
| **Redis** | 任务队列 + 分布式锁 + 缓存 |
| **ClickHouse** | 分析/事件数据库（运行日志、追踪） |
| **MinIO/S3** | 大负载卸载（>512KB 的任务 payload） |
| **ElectricSQL** | Postgres → 前端实时同步 |
| **S2 StreamStore** | 实时流基础设施（v2，替代 WebSocket） |
| **Docker Registry** | 存储用户部署的任务镜像 |

### 4.2 核心数据模型

```
BackgroundWorker       # 部署版本（用户代码的快照）
  ├── BackgroundWorkerTask   # 该版本中的每个任务
  ├── BackgroundWorkerFile   # 源代码文件
  └── WorkerDeployment       # 部署记录

TaskRun               # 单次任务执行实例
  ├── TaskRunAttempt        # 每次重试尝试
  ├── TaskRunCheckpoint     # Checkpoint 快照
  ├── TaskRunDependency     # 子任务依赖
  ├── TaskRunTag            # 标签
  ├── TaskRunWaitpoint      # 等待点关联
  └── TaskEvent             # 执行事件 / 日志

Waitpoint             # 等待点（暂停任务直到条件满足）
  ├── 类型: RUN | DATETIME | MANUAL | BATCH
  └── 状态: PENDING | COMPLETED

Checkpoint            # Docker/K8s 容器快照
  └── CheckpointRestoreEvent  # 快照/恢复事件

TaskSchedule          # Cron 调度定义
  └── TaskScheduleInstance   # 调度 × 环境的关联

Session               # 双向 I/O 会话（Agent 对话）
  └── SessionRun           # 会话的历史运行记录
```

### 4.3 RunEngine 架构

`RunEngine` 是核心编排器的类，位于 `internal-packages/run-engine/`：

```
RunEngine
├── EnqueueSystem        # 入队新任务
├── DequeueSystem        # 出队并分配给 Worker
├── CheckpointSystem     # 容器快照管理
├── WaitpointSystem      # 等待点生命周期
├── BatchSystem          # 批量任务协调
├── DebounceSystem       # 去抖处理
├── DelayedRunSystem     # 延迟执行
├── TtlSystem            # 超时管理
├── ExecutionSnapshotSystem  # 执行状态快照
├── PendingVersionSystem # 版本等待管理
├── RunAttemptSystem     # 重试逻辑
├── BillingCache         # 计费缓存
├── RunLocker            # 分布式锁（Redis）
├── RunQueue             # 任务队列（Redis）
└── EventBus             # 内部事件总线
```

---

## 五、部署架构

### 5.1 部署流程

```
用户 CLI (trigger deploy --push)
  → 打包用户代码为 Docker 镜像
  → 推送到 Registry
  → 通知 Webapp 新版本
  → Supervisor 出队任务
  → 创建 Pod/容器（K8s 或 Docker）
  → Coordinator 在容器内协调执行
  → 日志/追踪 → ClickHouse
  → 实时更新 → ElectricSQL / S2 Streams
```

### 5.2 自托管选项

| 方案 | 适用场景 |
|------|---------|
| **Docker Compose** | 单机 / 测试 |
| **Kubernetes Helm** | 生产集群 |
| **Cloud** | 无需管理基础设施 |

### 5.3 K8s Helm Chart 依赖

- PostgreSQL（Bitnami chart 16.7.14）
- Redis（Bitnami chart 21.2.6）
- ClickHouse（Bitnami chart 9.4.4）
- MinIO（Bitnami chart 17.0.9）
- 可选：Electric、Registry、Ingress、ServiceMonitor

---

## 六、关键设计决策分析

### 6.1 容器级任务隔离

所有用户任务在独立容器中执行。这提供了：
- **安全隔离**：用户代码不会互相影响
- **资源限制**：通过 vCPU/RAM 配置控制
- **Checkpoint/Restore**：利用 Docker/K8s CRIU 做容器快照实现无限执行

### 6.2 Checkpoint/Restore 耐久性

这不是简单的"持久化状态"——它是**操作系统级别的进程快照**：
- 任务可以在任何时刻暂停
- 恢复时完全还原内存状态
- 这是实现"无限执行时长"的关键技术

### 6.3 版本化部署

- 新部署创建新的 `BackgroundWorker` 版本
- 正在运行的任务不受影响（继续在旧版本上执行）
- 新任务自动路由到最新版本
- `WorkerDeploymentPromotion` 支持 "current" 标签

### 6.4 多环境支持

- DEV / PREVIEW / STAGING / PROD 四种环境类型
- Preview 环境与 Vercel 预览分支集成
- 每个环境独立的 API key、队列、调度

### 6.5 可观测性

- **OpenTelemetry** 全链路追踪（贯穿所有任务执行层级）
- **ClickHouse** 存储所有事件用于分析
- **S2 StreamStore** 提供实时流（任务运行状态实时推送到前端）
- **Prometheus metrics**（`/metrics` endpoint）

---

## 七、对 AgentHub 的启发

以下按与 AgentHub 项目的相关度排序：

### 7.1 核心启发：Waitpoint 系统 → Agent 协作阻塞机制

**Trigger.dev 的做法**：任务可以通过 `wait.forToken()` 在任意位置暂停，等待外部事件（人工审批、webhook、子任务完成）后恢复。

**对 AgentHub 的启示**：
AgentHub 的多 Agent 协作中，Agent A 经常需要等待 Agent B 的中间结果。当前设计可能依赖消息传递，但 Trigger.dev 的 waitpoint 模式更优雅——Agent 创建一个等待令牌，暂停自己，另一个 Agent 完成任务后通过令牌恢复它。这比轮询或复杂的消息回调干净得多。

**建议**：在 AgentHub 的 Task Engine（L2 Domain）中引入类似 Waitpoint 的抽象：
- `WaitpointType`: AGENT | HUMAN | DATETIME | EVENT
- 等待点关联到具体的 agent run
- 支持 idempotency key 防止重复
- REST API + WebSocket 推送完成通知

### 7.2 任务运行层级（Parent-Child）

**Trigger.dev 的做法**：`TaskRun` 有 `parentTaskRun` / `childRuns` / `rootTaskRun` / `depth` 字段，构成完整的执行树。

**对 AgentHub 的启示**：
AgentHub 的 Agent 协作天然形成层级关系——用户触发根任务 → Agent A 分解为子任务 → 分配给 Agent B/C。这个父子关系需要被追踪和可视化。

**建议**：
- `agent_run` 表增加 `parent_run_id` / `root_run_id` / `depth` 字段
- UI 中展示任务分解树
- 支持级联取消（取消父任务自动取消所有子任务）

### 7.3 幂等性设计

**Trigger.dev 的做法**：每个 TaskRun 有 `idempotencyKey` + `idempotencyKeyExpiresAt`，Duplicate 检测在 RunEngine 层面处理。

**对 AgentHub 的启示**：
消息重复投递在分布式系统中不可避免。AgentHub 的消息处理需要幂等性保证。

**建议**：
- 每条消息带上 `idempotency_key`（由发送方生成）
- L2 层在 `process_message` 前检查是否已处理
- Redis 缓存已处理的 key（TTL 24h）
- 数据库 unique constraint 兜底

### 7.4 Schema 验证

**Trigger.dev 的做法**：任务输入/输出使用 Zod/Valibot/ArkType schema 定义，运行时自动验证。

**对 AgentHub 的启示**：
Agent 间的通信需要结构化。当前如果是自由文本传递，随着 Agent 数量增加会变得不可维护。

**建议**：
- Agent 声明其输入/输出 Schema（Pydantic v2）
- 调用 Agent 时验证 payload 是否符合 Schema
- Schema Registry 存储所有 Agent 的接口定义
- 不匹配时早期失败，给出清晰的错误信息

### 7.5 生命周期钩子

**Trigger.dev 的做法**：onStart / onSuccess / onFailure / onComplete / onWait / onResume / onCancel / middleware。

**对 AgentHub 的启示**：
AgentHub 的 Agent 执行生命周期也需要可观测和可插拔的钩子。

**建议**：
- 参考 Trigger.dev 的钩子设计
- middleware 模式用于：日志记录、metrics 收集、权限检查
- 钩子失败不应阻止主流程（fire-and-forget 语义）

### 7.6 队列和并发控制

**Trigger.dev 的做法**：命名队列 + `concurrencyLimit` + `concurrencyLimitBurstFactor`。

**对 AgentHub 的启示**：
不同用户/组织的 Agent 任务应该被隔离和限流。

**建议**：
- 按 organization 分 queue
- 每 queue 设 concurrency limit
- Redis 实现（AgentHub 已有 Redis，无需引入新组件）
- 优先级支持（付费用户优先）

### 7.7 Session 模型（双向 I/O）

**Trigger.dev 的做法**：`Session` 模型拥有 S2 流的输入/输出对，支持 `externalId` 做 idempotent upsert。特别为 AI Chat 设计——创建 Session 同时触发第一个 run，每个后续 turn 触发新 run。

**对 AgentHub 的启示**：
AgentHub 的核心体验就是 IM 聊天。Session 模型的设计直接借鉴 Trigger.dev：

**建议**：
- 当前 `sessions` 表增加 `externalId`（用于客户端去重）
- Session 维护 `currentRunId` 指针（当前活跃的 agent run）
- `SessionRun` 表记录历史（类似 Trigger.dev）
- 支持 session 级别的配置（agent 选择、上下文窗口大小等）

### 7.8 CLI 工具链

**Trigger.dev 的做法**：`trigger.dev` CLI 提供 `dev` / `deploy` / `login` 命令。

**对 AgentHub 的启示**：
AgentHub 需要 Agent 开发者工具链。可以参考 Trigger.dev 的 CLI 设计：

**建议**：
- `agenthub dev`：本地开发 Agent 并测试
- `agenthub deploy`：部署 Agent 到平台
- `agenthub login`：认证
- 开发时热重载（类似 Trigger.dev 的 `trigger dev`）

### 7.9 可观测性

**Trigger.dev 的做法**：每个 TaskRun 有 traceId/spanId，全链路 OpenTelemetry 追踪，ClickHouse 存储事件。

**对 AgentHub 的启示**：
多 Agent 协作的调试难度远超单体应用。需要完整的可观测性。

**建议**：
- 为每个 agent run 生成 traceId
- 子调用使用 spanId（OpenTelemetry 语义）
- 日志/事件集中在 ClickHouse 或至少 PostgreSQL（Phase 1 用 PG 够用）
- 前端实时展示 run 的执行树（类似 Trigger.dev 的 dashboard）

### 7.10 构建扩展（Build Extensions）

**Trigger.dev 的做法**：`@trigger.dev/build` 包允许用户在构建阶段运行 Python 脚本、FFmpeg、浏览器等。

**对 AgentHub 的启示**：
Agent 可能有不同的运行环境需求（Python/Node/自定义 Docker）。

**建议**：
- Phase 2+ 考虑支持自定义 Agent 运行时
- 初期 CLI 模式 Agent 在本地运行，已满足 MVP 需求
- 后续可考虑 Docker-in-Docker 执行

---

## 八、不应该借鉴的部分

### 8.1 容器级 Checkpoint/Restore

Trigger.dev 用 CRIU（操作系统级进程快照）实现耐久性。这对 AgentHub 来说**过度设计**：
- AgentHub 的 Agent 执行时间远短于 Trigger.dev 动辄数小时的任务
- 实现复杂度极高（需要 Docker/K8s + CRIU 支持）
- AgentHub 用数据库持久化 + 状态机就足够

### 8.2 多运行时 Provider（Docker/K8s Provider）

Trigger.dev 需要 docker-provider 和 kubernetes-provider 两个独立的执行运行时。AgentHub 当前不需要：
- CLI 模式 Agent 在用户本地运行
- SDK 模式可能只需要 HTTP API
- Phase 1-2 不需要容器隔离

### 8.3 ElectricSQL 实时同步

Trigger.dev 用 ElectricSQL 做 Postgres → 前端的实时数据同步。AgentHub 已有 WebSocket，不需要引入另一个实时同步层。

---

## 九、架构对比总结

| 维度 | Trigger.dev | AgentHub |
|------|------------|----------|
| **定位** | 通用任务/AI Agent 运行时 | IM 聊天式多 Agent 协作 |
| **规模** | 15k stars, 621 releases | Phase 1 MVP |
| **执行模型** | 容器隔离 + Checkpoint/Restore | CLI 本地执行 + SDK HTTP |
| **核心抽象** | Task → TaskRun → Attempt | Message → Session → AgentRun |
| **耐久性** | CRIU 进程快照 | DB 持久化状态机 ✅ |
| **Human-in-Loop** | Waitpoint 系统 ⭐ | 天然支持（IM 交互） |
| **多 Agent** | 单 Task 触发 + 子任务 | 多 Agent 群聊 @mentions |
| **调度** | Cron + 延迟队列 | 可参考 |
| **可观测性** | OTel + ClickHouse + S2 | 初期 PG + WS 足够 |
| **部署** | Docker Compose / K8s Helm | Docker Compose |
| **CLI** | trigger dev/deploy/login | 未来需要 |
| **Schema** | Zod/Valibot/ArkType | Pydantic v2 ✅ |

---

## 十、优先级建议

对 AgentHub Phase 1-2 的建议优先级：

| 优先级 | 启发点 | 理由 |
|--------|--------|------|
| **P0** | Session 双向 I/O 模型 | 直接对应 IM 核心体验 |
| **P0** | 幂等性设计 | 分布式基础保障 |
| **P1** | Waitpoint 系统 | 多 Agent 协作阻塞的核心机制 |
| **P1** | 任务运行层级 | Agent 执行树可视化 |
| **P2** | Schema 验证 Agent 通信 | 提升可靠性 |
| **P2** | 生命周期钩子 | 可观测性基础 |
| **P3** | 队列和并发控制 | 多租户隔离 |
| **P3** | CLI 工具链 | Agent 开发者体验 |
| **P4** | Build Extensions | 自定义运行时 |

---

> 分析人：Claude Code (Opus 4.7)
> 下次建议：可选分析 Temporal.io（更重的工作流引擎）或 Inngest（更轻的事件驱动任务），做横向对比。
