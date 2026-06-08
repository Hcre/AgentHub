# Microsoft Agent Framework — 协调者+任务系统实现分析

> 日期：2026-06-04 | 方法：git clone + 源码分析 | 关联：[[task-execution-open-questions]] [[coordinator-design-decision]]

---

## 一、项目概述

| 属性 | 值 |
|------|-----|
| 项目名 | Microsoft Agent Framework (MAF) |
| 仓库 | https://github.com/microsoft/agent-framework |
| Stars | ~11,000 |
| 语言 | Python + .NET（双语言） |
| 许可证 | MIT |
| 定位 | 企业级多 Agent 编排框架，图式工作流执行引擎 |
| 分析版本 | main 分支 HEAD（2026-06-04 clone） |

### 选择理由

MAF 是目前将**"协调者作为图节点（LLM 调用）"与"确定性任务编排引擎"结合得最好的开源实现**。其架构与 AgentHub 方案 1（协调者 = 纯 LLM 调用）高度相似：

| 概念 | MAF | AgentHub 方案 1 |
|------|-----|-----------------|
| 协调者 | MagenticOrchestrator（Executor 节点，内部使用 Manager LLM） | Coordinator（LLM 调用） |
| 任务执行器 | AgentExecutor（包装 Agent 实例） | Worker Agent（CLI session） |
| 流程控制 | WorkflowBuilder + Edge（有向图） | Harness（DAG + FSM） |
| 人在环 | request_info（工作流暂停点，支持多层审批） | TaskPanel 操作 |
| 状态持久化 | CheckpointStorage（快照+恢复） | task_events 表（追加不可变，设计中） |
| 并行执行 | fan-out/fan-in edges + superstep | DAG 拓扑排序 + wave dispatch |

---

## 二、架构分层

```
┌──────────────────────────────────────────────────────────────┐
│                    用户 API 层                               │
│  workflow.run(input, stream=True/False, thread_id=...)       │
│  - 同步/流式两种模式                                          │
│  - thread_id 关联多次运行（checkpoint 恢复）                   │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                   Orchestration Builders                      │
│  SequentialBuilder   ConcurrentBuilder   MagenticBuilder     │
│  HandoffBuilder      GroupChatBuilder                        │
│  - 声明式定义参与者 + 流程拓扑                                 │
│  - 每个 Builder 提供 fluent API（.with_*() 链式调用）         │
│  - .build() → Workflow（编译为不可变有向图）                   │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    Workflow Engine                            │
│  WorkflowBuilder → Workflow（有向图）                         │
│  - start_executor → edges → executors → output               │
│  - fan-out edges：一对多并行分发                              │
│  - fan-in edges：多对一聚合收集                               │
│  - conditional edges：基于消息内容的条件路由                   │
│  - superstep-based execution：BSP 模型（Barrier Synchronization│
│    Parallel），每个 superstep 内所有 executor 并行执行，       │
│    superstep 边界自动 checkpoint                              │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    Executor 层                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ AgentExecutor: 包装 SupportsAgentRun → 对话循环     │    │
│  │   - 接收 AgentExecutorRequest → 运行 agent.run()    │    │
│  │   - 返回 AgentExecutorResponse                     │    │
│  │   - 内部管理 AgentSession（对话历史持久化）          │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │ Custom Executor: @handler 装饰器 → 自定义逻辑       │    │
│  │   - 类型安全的输入/输出 message 路由                 │    │
│  │   - handler 方法签名决定接收的 message 类型          │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │ MagenticOrchestrator: LLM 驱动的协调者 Executor     │    │
│  │   - 内循环（coordination）+ 外循环（planning）       │    │
│  │   - 进度评估、卡死检测、自动 replan                  │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │ AgentApprovalExecutor: HITL 包装器                  │    │
│  │   - request_info 暂停 → 外部响应 → 继续执行          │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    基础设施层                                  │
│  CheckpointStorage   │ Event System  │ AgentSession          │
│  Message             │ WorkflowContext│ SupportsAgentRun      │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、核心实现模式分析

### 3.1 SequentialBuilder — 流水线任务编排

**文件**：`packages/orchestrations/agent_framework_orchestrations/_sequential.py`

**适用场景**：任务有明确的先后依赖关系，前一个的输出是后一个的输入。

**实现机制**：

```
Input → _InputToConversation → participant1 → participant2 → ... → participantN
```

每个 participant 是 `AgentExecutor`（包装 Agent）或自定义 `Executor`。Agent 共享完整对话历史（`list[Message]`），自定义 Executor 可以变换/过滤消息。

**关键源码结构**：

```python
class SequentialBuilder:
    def __init__(self, *, participants, checkpoint_storage=None,
                 chain_only_agent_responses=False,  # 只传递 Agent 回复，减少 context
                 output_from=None,                   # 指定哪些 participant 的输出作为 workflow output
                 intermediate_output_from=None):     # 指定哪些输出作为中间事件
        ...

    def with_request_info(self, *, agents=None):
        """在指定 Agent 前后插入 HITL 暂停点"""
        ...

    def build(self) -> Workflow:
        # 1. 解析 participant → AgentExecutor 或 AgentApprovalExecutor
        # 2. 创建 WorkflowBuilder
        # 3. add_edge(input_conv, p1) → add_edge(p1, p2) → ...
        # 4. builder.build() 编译为不可变 Workflow
```

**对 AgentHub 的启发**：
- `chain_only_agent_responses` 模式可用于降低下游 Task 的 context 大小（不传递完整对话历史，只传递上一个 Agent 的最终回复）
- `output_from` / `intermediate_output_from` 模式可用于 TaskPlanCard 的信息分层（哪些 Task 的结果是"最终输出"，哪些是"中间过程"）

### 3.2 ConcurrentBuilder — 并行任务编排

**文件**：`packages/orchestrations/agent_framework_orchestrations/_concurrent.py`

**适用场景**：多个独立子任务可同时执行，结果需要聚合。

**实现机制**：

```
Dispatcher → fan-out → [participant1, participant2, participant3]
                         ↓              ↓              ↓
                    AgentExecutor  AgentExecutor  AgentExecutor
                         ↓              ↓              ↓
                    fan-in → Aggregator → output (AgentResponse)
```

**关键源码结构**：

```python
class ConcurrentBuilder:
    def __init__(self, *, participants, checkpoint_storage=None):
        ...

    def with_aggregator(self, aggregator):
        """自定义聚合器：Executor 实例 或 callback 函数
        callback 签名：(results: list[AgentExecutorResponse]) -> Any
        """
        ...

    def build(self) -> Workflow:
        dispatcher = _DispatchToAllParticipants(id="dispatcher")
        aggregator = self._aggregator or _AggregateAgentConversations(id="aggregator")
        participants = self._resolve_participants()

        builder = WorkflowBuilder(start_executor=dispatcher, ...)
        builder.add_fan_out_edges(dispatcher, participants)   # 一对多
        builder.add_fan_in_edges(participants, aggregator)     # 多对一
        return builder.build()
```

**默认 Aggregator 逻辑**（`_AggregateAgentConversations`）：

```python
class _AggregateAgentConversations(Executor):
    @handler
    async def aggregate(self, results: list[AgentExecutorResponse], ctx):
        # 从每个 participant 的 response 中提取最后一条 assistant 消息
        assistant_replies = []
        for r in results:
            final = next((m for m in reversed(r.agent_response.messages)
                         if m.role == "assistant"), None)
            if final:
                assistant_replies.append(final)
        await ctx.yield_output(AgentResponse(messages=assistant_replies))
```

**对 AgentHub 的启发**：
- DAG 的并行 wave 本质上是 ConcurrentBuilder 的泛化（多 wave 而非单 wave）
- `_DispatchToAllParticipants` 广播输入给所有 Worker — AgentHub 需要"定向分发"（每个 Worker 收到不同输入）
- Aggregator 的 callback 模式可复用于 AgentHub 的 TaskResultAggregation（问题 7）
- 确定性聚合顺序：results 按 participant 定义顺序排列（非完成顺序）

### 3.3 MagenticBuilder — LLM 驱动的协调者模式（重点）

**文件**：`packages/orchestrations/agent_framework_orchestrations/_magentic.py`（1802 行）

这是 MAF 中最接近 AgentHub Coordinator 设计的实现。Magentic 模式源自 Microsoft Research 的 Magentic-One 系统。

#### 3.3.1 核心组件关系

```
MagenticBuilder.build()
  │
  ├── MagenticOrchestrator (Executor)
  │     │  继承自 BaseGroupChatOrchestrator
  │     │  管理整个工作流的生命周期
  │     │
  │     ├── StandardMagenticManager (LLM 调用封装)
  │     │     │  内部使用 SupportsAgentRun 做 LLM 调用
  │     │     │  有自己的 AgentSession（对话历史管理）
  │     │     │
  │     │     ├── plan(): 分析任务 → 生成 facts + plan
  │     │     │     └── 产出: MagenticTaskLedger {facts, plan}
  │     │     │
  │     │     ├── replan(): 卡死时更新 facts + 重新规划
  │     │     │     └── 产出: 更新后的 MagenticTaskLedger
  │     │     │
  │     │     ├── create_progress_ledger(): JSON 格式进度评估
  │     │     │     └── 产出: MagenticProgressLedger {
  │     │     │           is_request_satisfied, is_in_loop,
  │     │     │           is_progress_being_made, next_speaker,
  │     │     │           instruction_or_question
  │     │     │         }
  │     │     │
  │     │     └── prepare_final_answer(): 综合所有结果生成最终输出
  │     │
  │     ├── 外循环（planning phase）
  │     │     1. manager.plan() → task_ledger
  │     │     2. [可选] 人审批 plan（require_plan_signoff）
  │     │     3. 进入内循环
  │     │     4. 如需 replan → 回到外循环
  │     │
  │     └── 内循环（coordination phase）
  │           1. round_count++
  │           2. manager.create_progress_ledger()
  │           3. 检查 is_request_satisfied → prepare_final_answer()
  │           4. 检查 !is_progress_being_made || is_in_loop → stall_count++
  │           5. stall_count > max_stall_count → reset_and_replan()
  │           6. 选择 next_speaker → send_request_to_participant()
  │           7. 等待 participant response → 内循环继续
  │           8. 检查 round_count / reset_count 上限 → 终止
  │
  └── MagenticAgentExecutor[] (Worker 包装)
        │  继承自 AgentExecutor
        │
        └── handle_magentic_reset(): 协调者要求重置时
              清理 cache、conversation、pending_requests、session
```

#### 3.3.2 关键数据结构

```python
# 进度账本（每次内循环迭代生成，LLM 调用的 JSON 输出）
@dataclass
class MagenticProgressLedger:
    is_request_satisfied:     ProgressLedgerItem  # {reason, answer: bool}
    is_in_loop:               ProgressLedgerItem  # 死循环检测
    is_progress_being_made:   ProgressLedgerItem  # 是否有进展
    next_speaker:             ProgressLedgerItem  # 下一个发言的 Agent
    instruction_or_question:  ProgressLedgerItem  # 给该 Agent 的指令

# 任务上下文（外循环维护）
@dataclass
class MagenticContext:
    task: str                          # 用户原始任务
    chat_history: list[Message]        # 完整对话历史
    participant_descriptions: dict     # {agent_name: description}
    round_count: int = 0               # 当前内循环轮次
    stall_count: int = 0               # 连续无进展计数（hysteresis）
    reset_count: int = 0               # replan 重置次数

# 任务账本（plan 阶段生成）
@dataclass
class MagenticTaskLedger:
    facts: Message    # LLM 分析的任务事实
    plan: Message     # LLM 生成的执行计划
```

#### 3.3.3 卡死检测与自动恢复（核心逻辑）

```python
# 内循环中的 stall 检测（_run_inner_loop_helper）
# 来自源码第 1110-1118 行

# 检查是否有进展
if not progress.is_progress_being_made.answer or progress.is_in_loop.answer:
    stall_count += 1
else:
    stall_count = max(0, stall_count - 1)  # hysteresis: 有进展时递减

# 超过阈值 → 触发 reset + replan
if stall_count > max_stall_count:  # 默认 3
    context.reset()                 # 清空 chat_history，保留 task + descriptions
    manager.replan()                # 基于新事实重新规划
    # 可选：request_info 通知人类
```

**hysteresis 机制的关键**：`stall_count` 不是简单的累加器——连续无进展才累加，一旦有进展就递减。这避免了偶发的单轮卡顿触发不必要的 replan。

#### 3.3.4 进度评估的 JSON Prompt 设计

```python
# ORCHESTRATOR_PROGRESS_LEDGER_PROMPT（源码第 193-242 行）
# 要求 LLM 输出严格 JSON，包含 5 个维度：

"""
Please output an answer in pure JSON format according to the following schema.
DO NOT OUTPUT ANYTHING OTHER THAN JSON:

{
    "is_request_satisfied": {
        "reason": string,
        "answer": boolean
    },
    "is_in_loop": {
        "reason": string,
        "answer": boolean
    },
    "is_progress_being_made": {
        "reason": string,
        "answer": boolean
    },
    "next_speaker": {
        "reason": string,
        "answer": string (select from: {names})
    },
    "instruction_or_question": {
        "reason": string,
        "answer": string
    }
}
"""
```

**JSON 解析容错**（`_extract_json` 函数，源码第 406-449 行）：

```python
def _extract_json(text: str) -> dict:
    # 多层容错策略:
    # 1. 尝试提取 markdown code fence 内的 JSON
    # 2. 查找第一个平衡的 {} 块
    # 3. 替换 Python 关键字（True→true, False→false, None→null）
    # 4. 如果以上都失败，尝试 ast.literal_eval
    # 最多重试 progress_ledger_retry_count 次（默认 3）
```

**对 AgentHub 的启发**：Coordinator 的 JSON 输出解析应实现类似的容错机制，而不是假设 LLM 一定返回合法 JSON。

#### 3.3.5 人在环集成

MAF 提供了 4 层 HITL 机制：

```
Level 1: Plan Review（计划审批）
  MagenticBuilder.with_plan_review()
  → plan 生成后 → request_info(MagenticPlanReviewRequest)
  → 人: APPROVE / REVISE → handle_plan_review_response()

Level 2: Task Approval（任务级审批）
  SequentialBuilder/ConcurrentBuilder.with_request_info(agents=[...])
  → 每个 Agent 执行前/后 → request_info
  → 人: 注入指导 / 批准继续

Level 3: Stall Intervention（卡死干预）
  MagenticBuilder.with_human_input_on_stall()
  → stall_count 超限 → request_info(MagenticHumanInterventionRequest)
  → 人: CONTINUE / REPLAN / GUIDANCE

Level 4: Tool Approval（工具审批）
  Agent 内部 tool call → function_approval_request
  → 人: APPROVE / REJECT
```

**request_info 暂停/恢复机制**：

```python
# Executor 内发送暂停信号
await ctx.request_info(payload, ResponseType)
# → 工作流暂停，emit request_info 事件（id + type + data）
# → 外部处理：workflow.run(responses={request_id: reply})
# → 匹配的 response_handler 方法被调用
# → 工作流从暂停点继续
```

### 3.4 Checkpoint 持久化机制

MAF 的 checkpoint 在 superstep 边界自动保存。每个 Executor 实现 `on_checkpoint_save()` / `on_checkpoint_restore()`：

```python
# MagenticOrchestrator 的 checkpoint（源码第 1267-1321 行）
async def on_checkpoint_save(self) -> dict:
    return {
        "terminated": self._terminated,
        "magentic_context": self._magentic_context.to_dict(),
        "task_ledger": message_to_payload(self._task_ledger),
        "progress_ledger": self._progress_ledger.to_dict(),
        "manager_state": self._manager.on_checkpoint_save(),  # 含 AgentSession
    }

async def on_checkpoint_restore(self, state: dict):
    self._terminated = state.get("terminated", False)
    self._magentic_context = MagenticContext.from_dict(state["magentic_context"])
    self._task_ledger = message_from_payload(state["task_ledger"])
    self._progress_ledger = MagenticProgressLedger.from_dict(state["progress_ledger"])
    self._manager.on_checkpoint_restore(state["manager_state"])
```

**对 AgentHub 的启发**：
- 事件溯源（event sourcing）vs 快照（snapshot）：MAF 用快照，AgentHub 用 task_events 重放。两者互补——快照恢复快，事件溯源可审计。
- 建议 AgentHub 采用混合：task_events（审计追溯）+ 定期快照（快速恢复）

---

## 四、可复用的设计模式

| 模式 | MAF 来源 | AgentHub 复用建议 | 优先级 |
|------|---------|------------------|:---:|
| **Builder → Workflow 编译** | SequentialBuilder/ConcurrentBuilder | Coordinator 输出 TaskPlan → Harness 编译为 DAG（已有设计） | — |
| **fan-out/fan-in 并行** | ConcurrentBuilder | DAG 的并行 wave 调度（已有设计） | — |
| **ProgressLedger 进度评估** | MagenticOrchestrator | Coordinator 除 decompose 外，增加 `evaluate_progress()` 调用 | P1 |
| **stall_count + hysteresis** | Magentic 内循环 | Harness 增加卡死检测，触发 replan | P1 |
| **request_info 暂停机制** | AgentApprovalExecutor | TaskPanel 操作的后端实现参考 | P1 |
| **CheckpointStorage** | Checkpoint | Harness 运行时状态持久化 | P1 |
| **MagenticResetSignal** | MagenticAgentExecutor | replan 时通知 Worker 清理 session | P2 |
| **output_from/intermediate_output_from** | 所有 Builder | TaskPlanCard 的信息分层展示 | P2 |
| **多层 HITL** | Plan/Task/Stall/Tool | AgentHub 的审批粒度分层设计 | P2 |
| **JSON 解析容错** | _extract_json 多层回退 | Coordinator 输出的 JSON 解析 | P0 |

---

## 五、MAF 的不足与 AgentHub 的差异化优势

| 维度 | MAF 的局限 | AgentHub 的优势 |
|------|-----------|----------------|
| **群聊交互** | GroupChat 是轮次制（一轮一个 Agent），非真正的自由讨论 | IM 聊天式群聊，多 Agent 自然对话 |
| **CLI 集成** | Agent 通过 `SupportsAgentRun` 抽象接口执行，不绑定 CLI | 深度集成 Claude CLI（CLI 优先），原生 thinking/tool use |
| **文件冲突** | 未涉及 | 设计了 4 种文件冲突策略（预分配/先读后写/Git 隔离/锁） |
| **多租户** | 单 process 设计，无多租户概念 | PostgreSQL + Redis 架构，天然支持多租户 |
| **任务可视化** | 无内置 Web UI | TaskPlanCard + TaskPanel + DAG 可视化（设计中） |
| **持久化** | Checkpoint 是可选的存储后端 | task_events 表是核心设计，追加不可变 |
| **工具生态** | 需自行实现工具 | 复用 Claude CLI 的全部工具能力 |
| **群组管理** | Team 是 Builder 参数，无持久化 | Group 是核心领域实体，有完整 CRUD |

---

## 六、关键源码索引

```
packages/orchestrations/agent_framework_orchestrations/
├── _sequential.py          # SequentialBuilder（270 行）
│   ├── SequentialBuilder   # 流水线编排
│   └── _InputToConversation# 输入标准化
│
├── _concurrent.py          # ConcurrentBuilder（432 行）
│   ├── ConcurrentBuilder   # 并行编排
│   ├── _DispatchToAllParticipants
│   ├── _AggregateAgentConversations  # 默认聚合器
│   └── _CallbackAggregator           # 回调聚合器
│
├── _magentic.py            # MagenticBuilder（1802 行）★ 重点
│   ├── MagenticOrchestrator        # 协调者 Executor
│   ├── StandardMagenticManager     # LLM 调用管理器
│   ├── MagenticBuilder             # Builder API
│   ├── MagenticAgentExecutor       # Worker 包装器
│   ├── MagenticContext             # 任务上下文
│   ├── MagenticTaskLedger          # 任务账本
│   ├── MagenticProgressLedger      # 进度账本
│   ├── MagenticPlanReviewRequest   # 人在环：计划审批
│   ├── MagenticResetSignal         # 重置信号
│   └── 内置 Prompt 模板 × 6        # 完整的 prompt 工程
│
├── _group_chat.py          # GroupChat（群聊轮次制）
├── _handoff.py             # Handoff（Agent 间传递）
├── _orchestration_state.py # 编排状态管理
└── _orchestration_request_info.py  # HITL 暂停机制
```

---

## 七、参考来源

1. Microsoft Agent Framework. GitHub. https://github.com/microsoft/agent-framework （`git clone --depth 1` 分析）
2. Microsoft Agent Framework Workflows 文档. https://learn.microsoft.com/en-us/agent-framework/workflows/
3. Microsoft DevBlogs. "Unlocking Enterprise AI Complexity: Multi-Agent Orchestration with MAF." 2025.
4. Anthropic. "Building Effective Agents." Dec 2024. https://www.anthropic.com/research/building-effective-agents
5. MAST: Multi-Agent System Failure Taxonomy. NeurIPS 2025 Spotlight. arXiv:2503.13657

---

## 关联文档

- [[task-execution-open-questions]] 任务执行待解问题（17 项，含 MAF 启发的新增维度）
- [[coordinator-design-decision]] 协调者设计决策
- [[coordinator-pattern-deep-research]] 协调者模式深度调研
- [[task-execution-completeness-and-implementation-analysis]] 完整性审查+实现分析（本文的原始版本）
- [[open-multi-agent_analysis_report]] open-multi-agent 项目分析

> MAF 完整源码已 clone 至 `/tmp/agent-framework`，如需查看具体文件可通过该路径访问。
