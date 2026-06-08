# 任务执行问题完整性审查 + 协调者任务系统实现分析

> 日期：2026-06-04 | 调研方法：两阶段深度搜索 + 源码分析 | 关联：[[task-execution-open-questions]] [[coordinator-design-decision]]

---

## Part A：task-execution-open-questions.md 完整性审查

### A.1 已有问题的评估

| # | 当前问题 | 覆盖度 | 评价 |
|---|---------|:---:|------|
| 1 | 任务路径不可达 | ✅ 完整 | 4 选项对比清晰；分层处理（自治重试→回调协调者→人工兜底）与 MAST 论文的补救策略一致；子树修复计划的设计方向正确 |
| 2 | 任务进度管理 | ✅ 完整 | 覆盖了指标定义、推送机制、群聊汇报、存储；缺口表诚实列出了 6 个待实现项 |
| 3 | 人在环调整 | ✅ 完整 | 覆盖路径调整（5 种操作）、执行查看（4 层信息）、文件冲突（4 种策略）；约束条件明确 |

### A.2 识别到的缺失维度

通过搜索 MAST 论文、Temporal/Prefect 架构、MAF 实现和行业实践，识别出以下 **7 个缺失或未充分覆盖的维度**：

| # | 缺失维度 | 严重度 | 为什么重要 | 应放在哪个问题下 |
|---|---------|:---:|------|-----------------|
| **4** | **任务超时与僵尸清理** | Critical | 长时间运行的 Agent 可能挂死、死循环或变成僵尸进程。没有超时机制，整个 DAG 永远卡住。MAST 论文中"missing termination condition"是 41.77% 规格模糊中最常见的子类。 | 问题 1（路径不可达）的子场景 |
| **5** | **任务幂等性与精确一次执行** | High | 重试机制（已设计）要求任务可安全重试。如果 Worker 执行了副作用（如发送邮件、写数据库）但崩溃前未标记完成，重试会重复执行。Temporal 的 Saga 模式和补偿事务是行业标准解法。 | 新问题或问题 1 的扩展 |
| **6** | **状态持久化与崩溃恢复** | High | FSM 已在内存，但 Harness 崩溃后如何恢复 DAG 执行状态？MAF 的 CheckpointStorage + Rainbow Deploy 是不停机更新的参考。当前文档只说"task_events 表追加不可变"，未涉及运行时状态恢复。 | 问题 2（进度管理）的扩展 |
| **7** | **动态图修改（执行中增删 Task）** | High | 协调者的 replan 会产出子树修复计划，这本质上是 DAG 的运行时修改。当前文档描述 Harness "将修复计划合并到原 DAG"，但未定义合并算法（替换 vs 插入 vs 追加）和边界条件（运行中 Task 能否被替换？）。 | 问题 3（人在环调整）的扩展 |
| **8** | **Token 预算与成本控制** | High | Anthropic 研究系统消耗 15x token。AgentHub 的生产环境需要：每个 Task 的 token 上限、整个 TaskPlan 的总预算、超额时的降级策略（切换廉价模型 / 跳过非关键 Task）。 | 新问题 |
| **9** | **Worker 输出格式标准化** | Medium | 当前 Task.result 是自由文本。但下游 Task 需要结构化输入（如 Task-A 输出 JSON → Task-B 解析字段）。AWS Builder 文章指出结构化协议可将 token 消耗降低 70%。需要定义 Task 间的输出/输入契约。 | 协调者 prompt 设计的关联问题 |
| **10** | **并发上限与资源调度** | Medium | 问题 3 涉及文件冲突，但未涉及：同时最多运行几个 Worker？Worker 的 CLI session 如何池化？GPU/内存资源如何分配？ | 新问题或问题 3 的扩展 |

### A.3 已有问题中需要深化的点

**问题 1（路径不可达）— 子树修复计划的合并算法需要明确**：

当前文档只说"Harness 将修复计划合并到原 DAG 中（替换失败子树）"。参考 MAF Magentic 的 replan 机制，需要定义：

```
合并策略:
├── REPLACE: 用新子树完全替换失败子树（包括 running 状态的 Task？）
├── INSERT_AFTER: 在失败点之后插入新的恢复路径
├── RETRY_WITH_MODIFICATION: 原 Task 不变，修改其 description/assignee
└── PRUNE: 移除失败子树，将依赖它的 Task 直接 unblock（跳过该子树）
```

**问题 2（进度管理）— 需要增加"卡死检测"**：

MAF Magentic 的 `stall_count` + `is_in_loop` 检测是重要参考。当前进度指标只有"完成/总数"，缺少"是否有进展"的语义判断。建议增加：
- `stall_count`：连续 N 轮无 Task 状态变更 → 触发告警
- 死循环检测：同一 Task 在短时间内反复 `FAILED → QUEUED → RUNNING → FAILED`

**问题 3（人在环调整）— HITL 的实现机制需要明确**：

当前文档只说操作和触发方式，未涉及实现机制。MAF 的 `request_info` 模式是成熟参考：
- `ctx.request_info(payload, response_type)` → 工作流暂停，等待外部响应
- 支持流式和非流式两种模式
- Checkpoint 在暂停点保存状态

### A.4 完整性总结

| 维度 | 状态 |
|------|:---:|
| 原始 3 个问题 | ✅ 覆盖完整，设计方向正确 |
| 识别的 7 个缺失维度 | ⚠️ 4 Critical + 3 High/Medium |
| 已标记的 9 项协调者缺口（coordinator-design-decision.md §待补） | ✅ 已记录，与本文形成互补 |
| 与行业实践的吻合度 | ✅ 分层处理、事件驱动、人在环操作均与 MAF/Temporal 一致 |

**建议**：将 7 个缺失维度补充到 `task-execution-open-questions.md`，其中 §3（状态持久化）、§5（Token 预算）、§7（子图合并算法）应优先解决。

---

## Part B：Microsoft Agent Framework — 协调者+任务系统实现分析

### B.1 项目基本信息

| 属性 | 值 |
|------|-----|
| 项目名 | Microsoft Agent Framework (MAF) |
| 仓库 | https://github.com/microsoft/agent-framework |
| Stars | ~11,000 |
| 语言 | Python + .NET（双语言） |
| 许可证 | MIT |
| 定位 | 企业级多 Agent 编排框架，图式工作流执行引擎 |

### B.2 选择理由

MAF 是目前**将"协调者作为图节点（LLM 调用）"与"确定性任务编排引擎"结合得最好的开源实现**。其架构与 AgentHub 方案 1 高度相似：

| 概念 | MAF | AgentHub |
|------|-----|---------|
| 协调者 | MagenticOrchestrator（Executor 节点，内部使用 LLM） | Coordinator（LLM 调用） |
| 任务执行器 | AgentExecutor（包装 Agent 实例） | Worker Agent（CLI session） |
| 流程控制 | WorkflowBuilder + Edge | Harness（DAG + FSM） |
| 人在环 | request_info（工作流暂停点） | TaskPanel 操作 |
| 状态持久化 | CheckpointStorage | task_events 表（设计中） |

### B.3 架构分层

```
┌──────────────────────────────────────────────────────────────┐
│                    用户 API 层                               │
│  workflow.run(input, stream=True/False, thread_id=...)       │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                   Orchestration Builders                      │
│  SequentialBuilder  ConcurrentBuilder  MagenticBuilder       │
│  HandoffBuilder     GroupChatBuilder                         │
│  - 声明式定义参与者 + 流程拓扑                                 │
│  - .build() → Workflow（编译为不可变图）                       │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    Workflow Engine                            │
│  WorkflowBuilder → Workflow（有向图）                         │
│  - start_executor → edges → executors                        │
│  - fan-out / fan-in edges（并行）                             │
│  - conditional edges（条件路由）                               │
│  - superstep-based execution（BSP 模型）                      │
│  - checkpoint at superstep boundaries                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    Executor 层                                │
│  AgentExecutor: 包装 SupportsAgentRun → 对话循环             │
│  Custom Executor: @handler 装饰器 → 自定义逻辑               │
│  MagenticOrchestrator: LLM 驱动的协调者 Executor             │
│  AgentApprovalExecutor: 人在环包装（request_info 暂停）       │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    基础设施层                                  │
│  CheckpointStorage | Event System | AgentSession | Message   │
└──────────────────────────────────────────────────────────────┘
```

### B.4 核心实现模式分析

#### B.4.1 SequentialBuilder — 流水线任务编排

**适用场景**：任务有明确的先后依赖关系，前一个的输出是后一个的输入。

**实现机制**（`_sequential.py`）：

```python
# 核心 wiring pattern
Input → _InputToConversation → participant1 → participant2 → ... → participantN
                                 ↓                       ↓
                         AgentExecutor            AgentExecutor
                    (接收 conversation,       (接收 conversation,
                     追加 assistant msg)       追加 assistant msg)
```

**关键设计决策**：
1. **共享 conversation 上下文**：每个 Agent 看到的是完整对话历史（`list[Message]`），而非仅上一个的输出
2. **`chain_only_agent_responses`**：可选只传递 Agent 回复，减少 context 膨胀
3. **HITL 插入点**：`with_request_info(agents=[agent2])` 可在特定 Agent 前后插入暂停

**对 AgentHub 的启发**：
- Harness 的 DAG 拓扑排序后可生成多个 Sequential 链
- 共享 conversation vs 隔离 context 是重要设计权衡
- `chain_only_agent_responses` 模式可用于降低下游 Task 的 context 大小

#### B.4.2 ConcurrentBuilder — 并行任务编排

**适用场景**：多个独立子任务可同时执行，结果需要聚合。

**实现机制**（`_concurrent.py`）：

```python
# Wiring pattern（fan-out/fan-in）
                         ┌→ participant1 ─┐
Dispatcher → fan-out →  ─┼→ participant2 ─┼→ fan-in → Aggregator → output
                         └→ participant3 ─┘

# 每个 participant 是独立的 AgentExecutor，有自己的 AgentSession
# Aggregator 接收 list[AgentExecutorResponse]，合成最终输出
```

**关键设计决策**：
1. **Dispatcher 广播**：输入消息广播给所有参与者（无定向分发）
2. **确定性聚合顺序**：`results` 顺序 = participants 定义顺序（非完成顺序）
3. **自定义 Aggregator**：可以是 Executor 实例或简单 callback 函数
4. **每个参与者独立 session**：互不干扰，真正的并行

**对 AgentHub 的启发**：
- Harness 的 DAG 并行 wave 本质上是 ConcurrentBuilder 的泛化（多 wave 而非单 wave）
- Aggregator 的设计可复用于 AgentHub 的 TaskResultAggregation
- 注意：MAF 的并行是"同一输入广播给所有参与者"，AgentHub 需要"不同输入分发给不同 Worker"

#### B.4.3 MagenticBuilder — LLM 驱动的协调者模式（重点）

这是 MAF 中最接近 AgentHub Coordinator 设计的实现。

**架构**：

```
MagenticBuilder.build()
  │
  ├── MagenticOrchestrator (Executor)
  │     │
  │     ├── StandardMagenticManager (LLM 调用封装)
  │     │     ├── plan(): 分析任务 → 生成 facts + plan
  │     │     ├── replan(): 卡死时更新 facts + 重新规划
  │     │     ├── create_progress_ledger(): JSON 格式进度评估
  │     │     │     → {is_request_satisfied, is_in_loop, is_progress_being_made,
  │     │     │        next_speaker, instruction_or_question}
  │     │     └── prepare_final_answer(): 综合所有结果生成最终输出
  │     │
  │     ├── 内循环（coordination phase）
  │     │     1. round_count++
  │     │     2. manager.create_progress_ledger()
  │     │     3. 检查完成 → prepare_final_answer()
  │     │     4. 检查卡死 → reset_and_replan()
  │     │     5. 选择 next_speaker → send_request_to_participant()
  │     │     6. 等待 response → 内循环继续
  │     │
  │     └── 外循环（planning phase）
  │           1. plan() → task_ledger
  │           2. [可选] 人审批 plan
  │           3. 进入内循环
  │           4. 如需 replan → 回到外循环
  │
  └── MagenticAgentExecutor[] (Worker 包装)
        └── handle_magentic_reset(): 协调者要求重置时清理 session
```

**协调者的关键数据结构**：

```python
# 进度账本（每次内循环迭代生成）
MagenticProgressLedger:
  is_request_satisfied:     {reason: str, answer: bool}
  is_in_loop:               {reason: str, answer: bool}    # ← 死循环检测！
  is_progress_being_made:   {reason: str, answer: bool}    # ← 卡死检测！
  next_speaker:             {reason: str, answer: str}     # ← Agent 选择
  instruction_or_question:  {reason: str, answer: str}     # ← 委派指令

# 任务账本（外循环生成）
MagenticContext:
  task: str                        # 用户原始任务
  chat_history: list[Message]      # 完整对话历史
  participant_descriptions: dict   # Agent 能力描述
  round_count: int                 # 当前内循环轮次
  stall_count: int                 # 连续无进展计数
  reset_count: int                 # 重置次数

# 任务账本（plan 阶段生成）
MagenticTaskLedger:
  facts: Message                   # LLM 分析的任务事实
  plan: Message                    # LLM 生成的执行计划
```

**卡死检测与自动恢复**：

```python
# 内循环中的 stall 检测逻辑
if not progress.is_progress_being_made or progress.is_in_loop:
    stall_count += 1
else:
    stall_count = max(0, stall_count - 1)  # 有进展时递减（hysteresis）

if stall_count > max_stall_count:  # 默认 3 轮
    # 触发 reset + replan
    context.reset()                # 清空 chat_history，保留 task
    manager.replan()               # 基于新事实重新规划
    # 可选：通知人类（with_human_input_on_stall）
```

**对 AgentHub 的直接启发**：

| MAF 特性 | AgentHub 可复用的设计 |
|---------|---------------------|
| `ProgressLedger` 结构 | Coordinator 除了输出 TaskPlan，还应输出 `ProgressCriteria`（每个 Task 的成功标准） |
| `stall_count` + hysteresis | Harness 应增加卡死检测：N 轮无 Task 状态变更 → 触发 replan |
| `manager.create_progress_ledger()` | Harness 可以周期性调用 Coordinator 做进度评估（不仅是失败时 replan） |
| `context.reset()` | replan 时需要保留原始 task + agent 列表，清理中间对话历史 |
| `require_plan_signoff` | 高风险 TaskPlan 可在执行前要求用户审批（人在环第一道防线） |
| Checkpoint + restore | 运行时状态持久化：允许 Harness 崩溃后从最近 checkpoint 恢复 |

#### B.4.4 人在环（Human-in-the-Loop）实现

MAF 提供了多层 HITL 机制：

```
Level 1: Plan Review（计划审批）
  MagenticBuilder.with_plan_review()
  → 计划生成后 → request_info(MagenticPlanReviewRequest)
  → 人: APPROVE / REVISE / REJECT

Level 2: Task Approval（任务审批）
  SequentialBuilder/ConcurrentBuilder.with_request_info(agents=[...])
  → 每个 Agent 执行前/后 → request_info
  → 人: 注入指导 / 批准继续 / 拒绝重做

Level 3: Stall Intervention（卡死干预）
  MagenticBuilder.with_human_input_on_stall()
  → stall_count 超限 → request_info(MagenticHumanInterventionRequest)
  → 人: CONTINUE / REPLAN / GUIDANCE

Level 4: Tool Approval（工具审批）
  Agent 内部 tool call → function_approval_request
  → 人: APPROVE / REJECT（适合 deploy、付款等高风险操作）
```

**request_info 机制**（工作流暂停/恢复的核心）：

```python
# Executor 内发送暂停信号
await ctx.request_info(payload, ResponseType)
# → 工作流暂停，向外部 emit request_info 事件
# → 外部通过 workflow.run(responses={request_id: reply}) 恢复
```

**对 AgentHub 的启发**：
- TaskPanel 的"暂停/跳过/取消"操作可通过类似的 request_info 模式实现
- 审批粒度可以分层：Plan 级 → Task 级 → Tool 级
- Checkpoint 在暂停点自动保存，恢复时从暂停点继续

### B.5 可复用的设计模式总结

| 模式 | 来源 | AgentHub 复用建议 |
|------|------|------------------|
| **Builder → Workflow 编译** | SequentialBuilder/ConcurrentBuilder | Coordinator 输出 TaskPlan → Harness 编译为 DAG（已有设计） |
| **fan-out/fan-in 并行** | ConcurrentBuilder | DAG 的并行 wave 调度（已有设计） |
| **ProgressLedger 进度评估** | MagenticOrchestrator | Coordinator 除 decompose 外，增加 `evaluate_progress()` 调用 |
| **stall_count + hysteresis** | Magentic 内循环 | Harness 增加卡死检测，触发 replan |
| **request_info 暂停机制** | AgentApprovalExecutor | TaskPanel 操作的后端实现参考 |
| **CheckpointStorage** | Checkpoint | Harness 运行时状态持久化 |
| **MagenticResetSignal** | MagenticAgentExecutor | replan 时通知 Worker 清理 session |
| **output_from/intermediate_output_from** | 所有 Builder | TaskPlanCard 的信息分层展示（output vs intermediate） |

### B.6 MAF 的不足与 AgentHub 的差异化

| 维度 | MAF 的不足 | AgentHub 的优势/差异化 |
|------|-----------|----------------------|
| **群聊交互** | GroupChat 是轮次制（一轮一个 Agent），非真正的自由讨论 | AgentHub 的群聊讨论模式是真正的 IM 聊天 |
| **CLI 集成** | Agent 通过 SupportsAgentRun 接口执行，不绑定 CLI | AgentHub 深度集成 Claude CLI（CLI 优先） |
| **文件冲突** | 未涉及 | AgentHub 设计了 4 种文件冲突策略 |
| **多租户** | 单 process 设计 | AgentHub 有 PostgreSQL + Redis，天然支持多租户 |
| **任务可视化** | 无内置 Web UI | AgentHub 有 TaskPlanCard + TaskPanel 前端设计 |
| **持久化** | Checkpoint 是可选的 | AgentHub task_events 表是核心设计 |

---

## Part C：综合对比与建议

### C.1 协调者+任务系统的实现方案矩阵

| 实现维度 | 方案 A：最简 MVP | 方案 B：MAF 级完整 | 当前设计位置 |
|---------|-----------------|-------------------|-------------|
| **任务分解** | 单次 Coordinator LLM 调用 → TaskPlan | 多轮 plan + replan + progress_ledger | ✅ 方案 A（已决策） |
| **DAG 执行** | Kahn 拓扑排序 + 串行执行 | Superstep 并行 + fan-out/fan-in | ⚠️ 设计中有但未实现 |
| **失败恢复** | 重试 3 次 + 级联失败 | stall 检测 + replan + reset + 人审批 | ⚠️ 分层设计已有，未编码 |
| **进度跟踪** | TaskPlanCard 状态颜色 | ProgressLedger LLM 评估 + stall 检测 | ⚠️ 前端 stub |
| **人在环** | TaskPanel 按钮操作 | request_info 多层暂停 + plan 审批 | ⚠️ 只有操作定义，无实现机制 |
| **状态持久化** | task_events 表（追加不可变） | CheckpointStorage（快照+恢复） | ⚠️ task_events 表未创建 |
| **并发控制** | 无 | AgentPool + Semaphore | ❌ 未设计 |

### C.2 优先级建议

基于 MAF 实现分析和 A.2 缺失维度审查：

```
P0 (阻塞 M3 代码落地):
  1. Coordinator prompt + JSON Schema 设计（4 个 Critical 之首）
  2. Worker 能力发现机制（Coordinator 需要知道有哪些 Agent 可用）
  3. 任务超时与僵尸清理（没有超时 = DAG 永远卡死）
  4. 子树修复计划的合并算法（replan 产出的修复计划如何合并入 DAG）

P1 (M3 首批交付):
  5. 状态持久化与崩溃恢复（Checkpoint）
  6. Token 预算与成本控制
  7. 卡死检测（stall_count）

P2 (M3 迭代):
  8. 并发上限与资源调度
  9. Worker 输出格式标准化
  10. 任务幂等性
```

---

## 参考来源

1. Microsoft Agent Framework. GitHub. https://github.com/microsoft/agent-framework （已 clone 分析）
2. Anthropic. "Building Effective Agents." Dec 2024. https://www.anthropic.com/research/building-effective-agents
3. MAST: Multi-Agent System Failure Taxonomy. NeurIPS 2025 Spotlight. arXiv:2503.13657
4. AugmentCode. "Why Multi-Agent LLM Systems Fail." 2025. https://www.augmentcode.com/guides/why-multi-agent-llm-systems-fail-and-how-to-fix-them
5. AugmentCode. "How to Run a Multi-Agent Coding Workspace." 2025. https://www.augmentcode.com/guides/how-to-run-a-multi-agent-coding-workspace
6. Temporal. "Error Handling in Distributed Systems." https://temporal.io/blog/error-handling-in-distributed-systems
7. AWS Builder. "From Prompt Spaghetti to Structured Multi-Agent Systems." 2025. https://builder.aws.com/content/3AfCno58Bsm4AbKaFKYiaDgeOkK/
8. ByteByteGo. "How Anthropic Built a Multi-Agent Research System." 2025. https://blog.bytebytego.com/p/how-anthropic-built-a-multi-agent
9. CrewAI. "Tasks Documentation." https://docs.crewai.com/en/concepts/tasks
10. LangChain. "Choosing the Right Multi-Agent Architecture." 2025. https://www.langchain.com/blog/choosing-the-right-multi-agent-architecture

---

## 关联文档

- [[task-execution-open-questions]] 任务执行待解问题（本文 Part A 是对其的完整性审查）
- [[coordinator-design-decision]] 协调者设计决策（含 9 项待补缺口）
- [[coordinator-pattern-deep-research]] 协调者模式深度调研（2026-06-04）
- [[open-multi-agent_analysis_report]] open-multi-agent 项目分析
- MAF 源码（已 clone 至 `/tmp/agent-framework`）：关键文件已分析，详见 Part B
