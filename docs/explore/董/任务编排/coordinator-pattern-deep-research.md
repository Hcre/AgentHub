# 协调者模式深度调研报告

> 日期：2026-06-04 | 调研方法：两阶段深度搜索法 | 关联：[[coordinator-design-decision]] [[task-execution-open-questions]]

---

## 执行摘要

本次调研围绕「协调者应该是纯 LLM 调用还是完整 Agent」这一核心决策，通过两阶段搜索法对 Anthropic 官方指南、主流框架实现、学术研究数据和行业实践进行了系统性分析。

**核心发现**：

1. **Anthropic 官方立场明确支持方案 1**（纯 LLM 调用）：在 "Building Effective Agents" 中，Orchestrator-Workers 被明确归类为 **Workflow 模式**（预定义代码路径），而非 Agent 模式（LLM 自主决策）。协调者是"一个中央 LLM 动态分解任务、委托给 Worker、合成结果"——这是一次调用，不是持久 Agent。

2. **协调者作为完整 Agent 的可靠性数据触目惊心**：MAST 论文（NeurIPS 2025 Spotlight）分析 1600+ 执行轨迹显示，多 Agent 系统的**协调失败率高达 36.94%**，规格模糊占 41.77%，验证缺口占 21.30%。五个 Agent 各 95% 可靠性的链，端到端成功率仅 77%。

3. **所有主流框架都在"降级"协调者**：CrewAI Manager Agent 社区反馈不可靠；OpenAI Swarm 定位为 educational-only 且已被 Agents SDK 取代；LangGraph Supervisor 是显式图节点而非自治 Agent。行业趋势是**协调者越轻量、越可控越好**。

4. **方案 2 仅适用特殊场景**：Anthropic 自己的多 Agent 研究系统（Claude Research）使用持久 Lead Researcher，但这对应的是"不可预测的开放式信息任务"，且消耗 15x token。对 AgentHub 的代码生成场景，方案 1 是正确的起点。

---

## 第一阶段：宽口径概览扫描

### 1.1 关键概念与术语

| # | 概念/术语 | 定义 | 与本项目的关联 |
|---|----------|------|---------------|
| 1 | **Orchestrator-Workers** | Anthropic 定义的 workflow 模式：中央 LLM 动态分解任务，委托给 Worker，合成结果 | 本项目方案 1 的理论基础 |
| 2 | **Supervisor Agent** | LangGraph/CrewAI 中的持久协调 Agent，有独立 context window 和决策能力 | 本项目方案 2 的参照 |
| 3 | **Hierarchical Process** | CrewAI 的内置协调模式，Manager Agent 自动委派任务 | 方案 2 的行业实现案例 |
| 4 | **Task Decomposition (DAG)** | 将高层目标拆解为依赖图，拓扑排序后并行执行 | Coordinator.decompose() 的核心输出 |
| 5 | **Handoff/Router Pattern** | 分类输入并路由到专业 Agent，无持久协调者 | 与 Selector 角色最接近 |
| 6 | **Augmented LLM** | Anthropic 基础构建块：LLM + 检索 + 工具 + 记忆 | AgentHub Agent 的基础能力 |
| 7 | **Specification Ambiguity** | MAST 分类法中 41.77% 失败根源：角色模糊、任务定义不清 | 纯 LLM Coordinator 的 prompt 工程关键 |
| 8 | **Inter-Agent Misalignment** | MAST 分类法中 36.94% 失败根源：通信断裂、状态不同步 | 持久 Coordinator Agent 的主要风险 |
| 9 | **Swarm Pattern** | OpenAI Swarm 的轻量级 handoff 模式：无层级、无状态、函数级路由 | 与 AgentHub 群聊讨论模式的设计对比 |
| 10 | **ACI (Agent-Computer Interface)** | Anthropic 提出的工具设计原则：工具文档与 prompt 同等重要 | Coordinator 输出的 TaskPlan schema 设计 |

### 1.2 代表性资源清单

#### 权威文章/论文

| 资源 | 类型 | 核心主张 | 可深挖点 |
|------|------|---------|---------|
| **Anthropic "Building Effective Agents"** (2024.12) | 官方指南 | 从最简开始；Orchestrator-Workers 是 workflow 不是 agent；三个原则：简单性、透明性、ACI 设计 | Workflow vs Agent 的边界定义；工具设计案例（SWE-bench） |
| **Anthropic "Multi-Agent Research System"** (2025) | 工程博客 | 90%+ 性能提升来自跨 context window 并行推理；15x token 消耗；Lead Researcher 是持久 Agent | Rainbow deployment 策略；Checkpoint/retry 机制 |
| **MAST: Multi-Agent System Failure Taxonomy** (NeurIPS 2025 Spotlight) | 学术论文 | 1600+ 轨迹分析；79% 失败来自规格模糊 + 协调失败 + 验证缺口 | 14 种失败模式细分类；跨模型泛化验证 |
| **ByteByteGo: How Anthropic Built a Multi-Agent Research System** | 技术分析 | Lead Researcher = Opus；Workers = Sonnet；Citation Agent 独立验证；15x token | 模型选择策略的经济学分析 |
| **LangChain "Choosing the Right Multi-Agent Architecture"** (2025) | 框架指南 | 4 种模式对比（Subagents/Skills/Handoffs/Router）；Subagents 最适合集中式编排 | 各模式的 token 消耗和延迟数据 |
| **Kore.ai "Choosing the Right Orchestration Pattern"** (2025) | 行业指南 | 3 种模式（Supervisor/Adaptive Network/Custom）；Supervisor 延迟高但可追溯 | 从配置到代码的演进路径 |

#### 开源项目

| 项目 | Stars | 语言 | 定位 | 协调者模式 | 可深挖点 |
|------|-------|------|------|-----------|---------|
| **CrewAI** | ~25k+ | Python | 角色驱动多 Agent 框架 | Hierarchical Process（Manager Agent） | Manager Agent 的内部 tool 注入机制；社区反馈的可靠性问题 |
| **Microsoft Agent Framework** | ~11k | Python/.NET | 企业级多 Agent 框架 | Graph-based Supervisor | 图模式（sequential/concurrent/group）；生产级特性 |
| **Open Multi-Agent** | ~6.3k | TypeScript | 目标驱动任务编排 | 临时 Coordinator Agent（用完即销毁） | Task DAG + Scheduler + AgentPool 的实现细节 |
| **LangGraph** | ~10k+ | Python | 有状态 Agent 工作流图 | Supervisor Node + Conditional Edge | StateGraph 编译机制；checkpoint 持久化 |
| **OpenAI Swarm** | ~18k | Python | **教育/实验性** 多 Agent 编排 | 无持久协调者（函数级 handoff） | 极简设计哲学；已被 Agents SDK 取代 |
| **Kestra** | ~8k | Java | 声明式工作流编排 | YAML 定义的任务 DAG | 可视化 DAG 编辑器；事件驱动触发 |

#### 权威网站

| 网站 | URL | 主要栏目 | 可深挖点 |
|------|-----|---------|---------|
| **Anthropic Research** | anthropic.com/research | Building Effective Agents, Multi-Agent System, MCP | 官方对 agent 边界的定义演化 |
| **LangChain Blog** | blog.langchain.com | Multi-Agent Architectures, LangGraph Supervisor | 4 种模式的 token/延迟基准数据 |
| **LangChain Docs** | docs.langchain.com | langgraph-supervisor library | `create_supervisor()` API 和源码 |
| **arXiv** | arxiv.org | MAST paper (2503.13657), STRATUS system | 学术界的失败模式和缓解策略 |
| **AugmentCode Guides** | augmentcode.com/guides | Multi-Agent Failure Analysis | 生产部署的 MAST 分类实践 |

---

## 第二阶段：定向深入挖掘

### 2.1 Anthropic "Building Effective Agents" — 权威指南深度分析

**选择理由**：这是协调者设计决策的核心引用来源，也是 Anthropic 对 agent 模式的官方定义。需要精确理解其分类体系以验证方案 1 的合理性。

**内容主旨**：定义 agentic 系统的完整光谱——从简单的 prompt engineering 到自治 Agent——并提供"何时增加复杂度"的决策框架。

**核心论点链条**：

```
Augmented LLM（基础构建块）
  → Workflows（预定义代码路径控制）
    → Prompt Chaining → Routing → Parallelization → Orchestrator-Workers → Evaluator-Optimizer
  → Agents（LLM 自主控制流程）
    → Autonomous Agent（工具循环 + 环境反馈）

关键区分：控制权在哪里？
  - Workflows: 代码预定义路径
  - Agents: LLM 动态决定步骤
```

**Orchestrator-Workers 的精确定位**：

> Orchestrator-Workers 被**明确归类为 Workflow 模式**，不是 Agent 模式。原因是：虽然 Orchestrator 动态决定子任务，但它的调用时机和后续流程由代码控制（Harness），Orchestrator 本身不自主决定"何时出手"。

这意味着 Anthropic 的分类体系**直接支持方案 1**：
- Coordinator 的 `decompose()` 是一次 workflow 节点调用
- Coordinator 不维护自己的 CLI session
- Coordinator 不自主决定何时介入（由 Harness/Selector 触发）

**设计原则与本项目的映射**：

| Anthropic 原则 | AgentHub 实现 | 状态 |
|---------------|--------------|------|
| **简单性**：从最简开始 | Coordinator = 纯 LLM 调用（方案 1） | ✅ 已决策 |
| **透明性**：展示规划步骤 | TaskPlan → TaskPlanCard 可视化 | ⚠️ 前端 stub |
| **ACI 设计**：工具文档与 prompt 同等重要 | Coordinator 的 TaskPlan schema 设计 | ⚠️ prompt 占位 |
| **框架慎用**：理解底层代码 | AgentHub 自建编排，不依赖 CrewAI/LangGraph | ✅ |
| **评估驱动**：量化验证 | Task 成功率、端到端延迟、token 消耗 | ❌ 未设计 |

**评估**：
- **时效性**：2024.12，仍为行业权威参考。2025 年 Anthropic 的多 Agent 研究系统和 Agent Skills 发布是对该文的实践验证，未推翻其分类。
- **权威性**：Anthropic 官方研究博客，是该领域引用最多的文章之一。
- **与方案 1 的一致性**：高度一致。Orchestrator-Workers 作为 workflow 模式，协调者是一次调用而非持久 Agent。

---

### 2.2 Anthropic 多 Agent 研究系统 — 方案 2 的参照实现

**选择理由**：设计文档中引用了该系统作为"方案 2 仅适用特殊情况"的证据。需要深入理解其架构，明确它与方案 2 的异同。

**架构深度分析**：

```
用户查询
  │
  ▼
┌──────────────────────────────────────────────┐
│ Lead Researcher Agent (Claude Opus)          │
│ - 分析查询，制定策略                           │
│ - 写入计划到 memory（防止 context 丢失）        │
│ - 决定 spawn 哪些 subagent                    │
│ - 合成结果，决定是否继续                        │
└──────────┬───────────────────────────────────┘
           │ spawn & delegate
           ▼
┌──────────────────────┐  ┌──────────────────────┐
│ Subagent 1 (Sonnet)  │  │ Subagent 2 (Sonnet)  │  ...
│ - 独立 context window │  │ - 独立 context window │
│ - 搜索、评估、精炼     │  │ - 搜索、评估、精炼     │
└──────────┬───────────┘  └──────────┬───────────┘
           │                         │
           └─────────┬───────────────┘
                     ▼
┌──────────────────────────────────────────────┐
│ Citation Agent (独立验证)                      │
│ - 逐条核验声明与来源                            │
│ - 确保引用准确、可追溯                          │
└──────────────────────────────────────────────┘
```

**关键数据点**：

| 指标 | 数据 | 来源 |
|------|------|------|
| 性能提升 vs 单 Agent | 90%+ | ByteByteGo 分析 |
| Token 消耗 vs 标准聊天 | **15x** | Anthropic 工程博客 |
| Lead 模型 | Claude Opus（强推理） | ByteByteGo |
| Worker 模型 | Claude Sonnet（低成本） | ByteByteGo |
| 并行能力 | 多个 subagent 同时执行 | Anthropic 工程博客 |
| 可靠性机制 | Checkpoint + Retry + Rainbow Deploy | Anthropic 工程博客 |

**与 AgentHub 方案 2 的差异**：

| 维度 | Anthropic 研究系统 | AgentHub 方案 2 |
|------|-------------------|----------------|
| **触发方式** | 用户直接向 Lead Researcher 提需求 | Selector 路由 → Coordinator Agent 被 @ 触发 |
| **协调者生命周期** | 单次研究任务期间存在，任务结束即销毁 | 群组**永久成员**，有自己的 CLI session |
| **任务类型** | 信息检索 + 综合分析 | 代码生成 + 文件修改 |
| **并行粒度** | 独立搜索线程（无文件冲突） | 并行代码修改（有文件冲突风险） |
| **验证机制** | 独立 Citation Agent | 无独立验证层（方案 2 未设计） |
| **成本** | 15x token（可接受，因产出价值高） | 需评估 AgentHub 场景下的投入产出比 |

**关键结论**：

Anthropic 研究系统的 Lead Researcher 虽然在单次任务中是持久 Agent，但它**不是群组的永久成员**——它是临时创建、用完即销毁的。这与方案 2 的"永久 CLI session"有本质区别。实际上，这种"临时 Coordinator Agent"模式更接近 open-multi-agent 的设计（已在本项目分析过）。

---

### 2.3 MAST 论文 — 多 Agent 系统失败模式量化分析

**选择理由**：设计文档中引用"36.94% 协调失败率"作为方案 2 的主要反对依据。需要验证该数据的具体含义和可信度。

**论文信息**：
- 标题：Multi-Agent System Failure Taxonomy (MAST)
- 发表：NeurIPS 2025 Spotlight
- 数据规模：1600+ 执行轨迹，7 个主流框架
- 模型覆盖：GPT-4, Claude 3, Qwen 2.5, CodeLlama（跨模型泛化）

**14 种失败模式 → 3 大根因**：

```
Specification Ambiguity (41.77%)
├── Role ambiguity — Agent 不清楚自己的角色边界
├── Task underspecification — 任务描述缺少关键约束
├── Missing termination condition — 不知道何时停止
├── Constraint violation — 违反隐性约束
└── Prompt misinterpretation — 对指令的系统性误解

Inter-Agent Misalignment (36.94%)  ← 这就是"协调失败"
├── Communication breakdown — Agent 间消息丢失/忽略
├── State synchronization failure — 共享状态不一致
├── Conflicting objectives — Agent 目标互相矛盾
├── Information withholding — Agent 不传递关键信息
├── Reasoning-action mismatch — 说一套做一套
└── Cascading delegation errors — 委派链中的错误传播

Verification Gaps (21.30%)
├── Missing output validation — 没有检查输出质量
├── Incorrect success criteria — 验收标准与需求不一致
└── Unverified handoff results — 未验证交接结果
```

**可靠性衰减数学**：

| Agent 链长度 | 单 Agent 可靠性 95% | 单 Agent 可靠性 99% |
|-------------|--------------------|--------------------|
| 3 agents | 85.7% | 97.0% |
| 5 agents | **77.4%** | 95.1% |
| 10 agents | 59.9% | 90.4% |
| 20 agents | 35.8% | 81.8% |

即使每个 Agent 有 99% 的可靠性，20 个 Agent 的链式调用也会掉到 81.8%。

**与本项目的关联**：

方案 1 的失败域更小：
- Coordinator 是一次 LLM 调用 → 失败可重试，不影响其他组件
- Harness 是确定性代码 → 不引入 Agent 的不确定性
- FSM 状态机是确定性的 → 不依赖 Agent 自主判断

方案 2 引入了方案 1 没有的失败模式：
- Coordinator 的 CLI session 可能崩溃/超时/死循环
- Coordinator 的 context window 可能溢出（长时间群聊）
- Coordinator 与 Worker 之间的通信可能断裂
- Coordinator 可能做出错误的路由/委派决策且无人纠正

**评估**：
- **权威性**：NeurIPS 2025 Spotlight（顶级 ML 会议，接收率 <5%）
- **时效性**：2025 年发表，数据覆盖至 2025 年初
- **可信度**：跨 7 个框架 + 4 个模型家族的泛化验证

---

### 2.4 CrewAI Hierarchical Process — 方案 2 的行业案例

**选择理由**：CrewAI 是方案 2（Manager Agent）最知名的实现。需要了解其实际表现和社区反馈。

**Manager Agent 的实现机制**：

```
Crew(process=Process.hierarchical, manager_llm=llm)
  │
  ▼
Manager Agent（自动生成或自定义）
  │ 内置两个专属 tool：
  │   ├── Delegate work to coworker
  │   └── Ask question to coworker
  │
  ▼
运行时循环：
  1. Manager 分析任务 → 决定委派给哪个 Worker
  2. 创建临时内部 Task → Worker 执行
  3. 接收 Worker 结果 → 决定：继续委派 / 追问 / 合成最终答案
  4. 重复直到 Manager 判断任务完成
```

**社区反馈的问题**：

1. **"Does hierarchical process even work?"**（CrewAI 社区帖，高关注度）：用户报告 Manager Agent 行为不可预测，委派错误频繁
2. **Manager + 自定义 tool = "orange error"**（StackOverflow）：Manager Agent 使用自定义工具时出现内部错误
3. **无限委派循环**：Manager 可能在 Worker 之间反复委派而不合成结果
4. **Token 膨胀**：Manager 的 context 随委派次数线性增长，最终溢出

**与方案 2 的共性风险**：

| CrewAI Manager 的问题 | AgentHub 方案 2 的对应风险 |
|----------------------|--------------------------|
| Manager 作为永久协调者 | Coordinator 作为永久群组成员 |
| 委派决策不可预测 | Coordinator 的路由/分解决策不可预测 |
| Context 随对话膨胀 | Coordinator 的 CLI session 长时间运行后 context 溢出 |
| Manager 工具调用报错 | Coordinator 的 tool 调用失败 |
| 无限委派循环 | Coordinator 在 Agent 间反复协调不产出结果 |

**关键教训**：CrewAI 社区的经验表明，**即便是专门设计的 Manager Agent，在生产中也频繁出现可靠性问题**。如果 AgentHub 自建方案 2，需要面对同样的挑战。

---

### 2.5 LangGraph Supervisor Pattern — 方案 2 的图式实现

**选择理由**：LangGraph 的 Supervisor 是最可控的"协调者作为 Agent"实现。需要理解它如何通过图结构约束 Agent 行为。

**架构**：

```python
from langgraph_supervisor import create_supervisor

workflow = create_supervisor(
    agents=[research_agent, code_agent],
    model=llm,
    prompt="You are a supervisor. Route tasks to appropriate agents."
)
app = workflow.compile()
```

**Supervisor 不是自治 Agent，而是图中的一个节点**：

```
        ┌──────────┐
        │  START   │
        └────┬─────┘
             ▼
        ┌──────────┐
        │Supervisor│ ← LLM 调用（不是持久 Agent）
        │  Node    │   决策：goto research_agent / code_agent / END
        └────┬─────┘
             │ conditional edge
      ┌──────┼──────┐
      ▼      ▼      ▼
┌──────────┐ ┌──────────┐ ┌──────┐
│ research │ │  code    │ │ END  │
│  agent   │ │  agent   │ └──────┘
└────┬─────┘ └────┬─────┘
     │            │
     └─────┬──────┘
           ▼ (always return to supervisor)
     ┌──────────┐
     │Supervisor│
     └──────────┘
```

**关键洞察**：LangGraph 的 Supervisor 虽然是 Agent（有 LLM 调用），但它：
1. **不是永久运行的** — 每次调用都是独立的一次图节点执行
2. **不维护独立 session** — 共享 StateGraph 的 State
3. **决策被图结构约束** — 只能 `goto` 预定义的节点，不能自由委派
4. **每次 Worker 完成后返回** — Supervisor 不持续"观察"

这实际上是**方案 1 和方案 2 的混合**：
- Supervisor 是 Agent 节点（LLM 调用），类似方案 1
- 但它可以在任务执行过程中多次介入（不像方案 1 的 "decompose once"），类似方案 2
- 图结构提供硬约束，防止 Agent 失控

**对 AgentHub 的启发**：

AgentHub 的方案 1 可以扩展为"多次调用的 Coordinator"而不变成方案 2：
- Coordinator 在任务失败时可以被 Harness 回调重新分解（已设计：`Coordinator.decompose()` 回调）
- 每次回调是一次独立的 LLM 调用，不要求 Coordinator 维持 session
- 这等价于 LangGraph Supervisor 的模式：按需调用，不持久

---

### 2.6 OpenAI Swarm — 极简主义协调模式

**选择理由**：Swarm 代表了与方案 2 完全相反的极端——用最少的抽象实现多 Agent 协调。

**设计哲学**：

> "Swarm is experimental, educational. It's not intended for production use."
> — OpenAI Swarm README

已被 **OpenAI Agents SDK** 取代用于生产环境。

**两个原语**：

```python
# 原语 1: Agent
agent = Agent(
    name="Triage",
    instructions="Route user to appropriate department",
    functions=[transfer_to_sales, transfer_to_support]
)

# 原语 2: Handoff（函数返回 Agent）
def transfer_to_sales():
    return sales_agent  # 返回另一个 Agent → 执行权转移
```

**核心循环**（`client.run()`）：
1. 获取当前 Agent 的 chat completion
2. 执行 tool call，追加结果
3. 如果 tool 返回 Agent → 切换当前 Agent
4. 更新 context_variables
5. 重复直到无更多 function call

**与主流框架的关键差异**：

| 维度 | Swarm | CrewAI | LangGraph |
|------|-------|--------|-----------|
| 抽象数量 | 2（Agent + handoff） | 5+（Agent, Task, Crew, Process, Tool） | 10+（StateGraph, Node, Edge, Channel, Checkpoint…） |
| 状态管理 | 完全无状态，手动传 | 框架管理 | StateGraph + Checkpoint |
| 协调者 | 无（handoff 链） | Manager Agent | Supervisor Node |
| 约束 | 无（任意 handoff） | Role/Process 约束 | DAG 结构约束 |
| 生产就绪 | ❌ 教育用途 | ⚠️ 社区争议 | ✅ 企业级 |

**核心教训**：

Swarm 的设计证明了：**协调不一定需要协调者**。通过函数级 handoff，Agent 之间的任务传递可以是完全程序化的，不依赖 LLM 做路由决策。这是对方案 1 的进一步简化——连 Coordinator 的 `decompose()` 调用都可以被用户/Selector 的直接指令替代。

---

## 第三阶段：综合产出

### 3.1 协调者模式对比矩阵

| 维度 | 方案 1：纯 LLM 调用 | 方案 2：完整 Agent | LangGraph Supervisor | Anthropic 研究系统 | CrewAI Manager | OpenAI Swarm |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| **协调者类型** | 一次性 LLM 调用 | 持久 CLI session | 图节点（多次 LLM 调用） | 临时 Agent（任务级） | 持久 Agent + tool 注入 | 无协调者（handoff 链） |
| **Anthropic 分类** | Workflow ✅ | Agent ⚠️ | Workflow ✅ | Agent | Agent | Router Pattern |
| **与 Anthropic 简单性原则一致** | ✅ 从最简开始 | ❌ 预先增加复杂度 | ⚠️ 中等复杂度 | ❌ 复杂度高 | ❌ 复杂度高 | ✅ 极简 |
| **协调失败风险** | 低（单次调用，可重试） | **高**（MAST: 36.94% 协调失败率） | 中（图约束降低风险） | 中（临时性降低风险） | 高（社区反馈不可靠） | 低（无 LLM 协调） |
| **Token 成本** | 1x（单次分解调用） | **15x+**（持久 session） | 2-5x（多次调用+state） | 15x | 10x+ | 1x |
| **延迟** | 低（一次 LLM 往返） | 高（多轮 agent loop） | 中（多次图节点执行） | 高 | 高 | 低 |
| **可追溯性** | 高（Harness 确定性控制） | 低（Agent 自主决策） | 高（图结构可审计） | 中 | 低 | 中 |
| **灵活性（不可预测任务）** | 低 | 高 | 中 | 高 | 中 | 低 |
| **与 Harness/FSM 互补** | ✅ 职责清晰 | ❌ 功能重叠 | ⚠️ 部分重叠 | N/A | N/A | N/A |
| **人在环集成** | 通过 Harness + UI | Agent 直接交互 | 通过图 breakpoint | 通过 Lead | 有限 | 无 |
| **文件冲突处理** | Harness 编译时检测 | Agent 自主协商 | 未涉及 | 不适用（只读） | 未涉及 | 无 |
| **适用场景** | **可预测子任务的代码生成** | 不可预测的开放式探索 | 复杂多阶段流程 | 信息检索+综合分析 | 简单角色委派 | 路由式客服 |

### 3.2 方案 1 的增强建议

基于本次调研，对方案 1（纯 LLM 调用）提出以下增强：

#### A. 从单次 decompose 到按需多次回调（借鉴 LangGraph Supervisor）

```
当前设计：
  Selector 返回 decompose → Coordinator.decompose() 一次 → TaskPlan → 结束

增强设计：
  Selector 返回 decompose → Coordinator.decompose() → TaskPlan
    → Harness 执行 → Task 失败 → Harness 回调 Coordinator.replan(subtree)
    → Coordinator 再次调用 → 子树修复计划 → Harness 合并 → 继续执行
```

这与 LangGraph Supervisor 的"按需多次调用"模式一致，但不要求 Coordinator 维护 session。

#### B. TaskPlan Schema 的形式化验证（借鉴 MAST 教训）

MAST 论文指出 41.77% 失败来自规格模糊。Coordinator 输出的 TaskPlan 应该通过 JSON Schema 做硬约束：

```python
class TaskPlan(BaseModel):
    tasks: list[TaskDef]
    # 每个 TaskDef 必须包含：id, title, description, depends_on, expected_output_schema
    # Harness 在编译前校验 DAG 完整性
```

#### C. 引入验证 Agent（借鉴 Anthropic Citation Agent）

在任务执行流程中增加独立的验证步骤：
- Task 完成后 → Verifier Agent 检查输出是否满足 TaskDef.expected_output_schema
- 不满足 → 触发重试或 replan
- 验证 Agent 的 prompt 与 Worker Agent 隔离（借鉴 MAST 建议："judge 共享 context 就变成了集体幻觉的参与者"）

### 3.3 待验证问题

| # | 问题 | 建议下一轮搜索 |
|---|------|--------------|
| 1 | Coordinator 的 prompt 工程最佳实践？如何让 LLM 产出高质量的 TaskPlan？ | Anthropic 的 ACI 设计附录 + SWE-bench 工具设计案例 |
| 2 | 方案 1 的实际 token 成本是多少？一次 decompose 调用消耗多少 token？ | 在 AgentHub 中用真实 task 做 benchmark |
| 3 | Harness DAG 检测文件冲突的算法复杂度？并行 Task 数量上限？ | 图论：Kahn 算法 + 冲突检测的复杂度分析 |
| 4 | 子树修复计划（replan）与原始 DAG 合并的边界条件？ | DAG 局部替换算法（graph patching） |
| 5 | Anthropic Agent Skills 是否适用于 Coordinator 的分解能力？ | Agent Skills 的官方文档 + 社区案例 |
| 6 | Google A2A 协议是否适合 AgentHub 的 Agent 间通信？ | A2A 规范 + MCP vs A2A 对比 |
| 7 | Claude Agent SDK 是否可以作为方案 1 的 LLM 调用后端？ | Agent SDK 文档 + 与直接 API 调用的对比 |

---

## 参考来源

1. Anthropic. "Building Effective Agents." Dec 2024. https://www.anthropic.com/research/building-effective-agents
2. Anthropic. "Multi-Agent Research System." 2025. https://www.anthropic.com/engineering/multi-agent-research-system
3. ByteByteGo. "How Anthropic Built a Multi-Agent Research System." 2025. https://blog.bytebytego.com/p/how-anthropic-built-a-multi-agent
4. MAST: Multi-Agent System Failure Taxonomy. NeurIPS 2025 Spotlight. arXiv:2503.13657
5. AugmentCode. "Why Multi-Agent LLM Systems Fail (And How to Fix Them)." 2025. https://www.augmentcode.com/guides/why-multi-agent-llm-systems-fail-and-how-to-fix-them
6. Kore.ai. "Choosing the Right Orchestration Pattern for Multi-Agent Systems." 2025. https://www.kore.ai/blog/choosing-the-right-orchestration-pattern-for-multi-agent-systems
7. LangChain. "Choosing the Right Multi-Agent Architecture." 2025. https://www.langchain.com/blog/choosing-the-right-multi-agent-architecture
8. LangChain. "LangGraph Multi-Agent Supervisor." 2025. https://www.langchain.com/blog/langgraph-multi-agent-workflows
9. OpenAI. "Swarm." GitHub. https://github.com/openai/swarm
10. CrewAI. "Hierarchical Process." https://docs.crewai.com/en/learn/hierarchical-process
11. Microsoft. "Agent Framework." GitHub. https://github.com/microsoft/agent-framework
12. Open Multi-Agent. GitHub. https://github.com/open-multi-agent/open-multi-agent
13. MindStudio. "The Multi-Agent Reliability Compounding Problem." 2025. https://www.mindstudio.ai/blog/multi-agent-reliability-compounding-problem-77-percent/
14. GetMaxim. "Multi-Agent System Reliability: Failure Patterns, Root Causes, and Production Validation Strategies." 2025. https://www.getmaxim.ai/articles/multi-agent-system-reliability-failure-patterns-root-causes-and-production-validation-strategies/

---

## 关联文档

- [[coordinator-design-decision]] 协调者设计决策（纯 LLM 调用，已定案）
- [[task-execution-open-questions]] 任务执行阶段三个待解问题
- [[open-multi-agent_analysis_report]] open-multi-agent 项目分析
- `docs/explore/EXP-02_编排器设计模式.md` 编排器设计模式深度分析
- `docs/design/group-chat-discussion-mode_群聊讨论模式设计方案.md` §6.1 Selector vs 协调者
