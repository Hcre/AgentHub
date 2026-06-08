# 协调者设计调研报告：Agent vs LLM 调用

> 日期：2026-06-04 | 方法：两阶段深度搜索 | 来源：6 次宽口径扫描 + 3 个资源深入分析

---

## 第一阶段：宽口径概览

### 1.1 关键概念与术语

| 概念 | 定义 | 与协调者设计的关系 |
|------|------|-------------------|
| **Orchestrator-Worker** | 中央 LLM 分解任务 → 委派 Worker → 合成结果 | 两种方案都基于此模式，分歧在"协调者是什么" |
| **Agent as Tool** | Manager Agent 通过 `as_tool()` 调用子 Agent 作为工具 | 方案 2（Agent 协调者）的核心机制 |
| **Handoff** | 控制权从 router 转移到 specialist，不再回来 | 方案 1（LLM 调用）的类比——分解后移交 Harness |
| **Planner vs Orchestrator** | Planner 产出计划后交给 Worker 独立执行；Orchestrator 持续生成所有 Agent 动作 | 论文验证了 Planner 比 Orchestrator 更高效 |
| **Event-Driven Coordination** | Agent 通过共享事件日志异步协作，无中央连接管理 | 方案 1 的事件驱动执行层 |
| **Harness** | 纯代码层：校验 + FSM + DAG 编译 + 预算管控 | Anthropic 推荐的"结构、记忆、问责"包装器 |
| **Stateless vs Stateful** | Stateless = 每次全量注入上下文；Stateful = `--resume` 恢复 | 方案 2 需要 stateful，方案 1 可以是 stateless |

### 1.2 代表性项目

| 项目 | ⭐ | 协调者定位 | 与方案 1 (LLM 调用) | 与方案 2 (Agent) |
|------|---|-----------|:---:|:---:|
| **OpenAI Agents SDK** | 19k | Agent as Tool / Handoff 两种原语 | ✅ 支持 | ✅ 支持 |
| **LangGraph** | 24.8k | StateGraph + 代码驱动编排 | ✅ 核心模式 | ❌ 不推荐 |
| **CrewAI** | 44.3k | Manager Agent（完整 LLM Agent） | ❌ | ✅ 核心模式 |
| **AutoGen 0.4** | 54.6k | GroupChatManager + Swarm Handoff | ⚠️ 部分 | ✅ 主要 |
| **open-multi-agent** | 新项目 | 临时 Coordinator Agent（用完销毁） | ✅ 最接近 | ⚠️ 临时而非永久 |
| **Microsoft Agent Framework** | GA 2026.4 | Graph-based（代码编排） | ✅ | ❌ |

### 1.3 关键论文/文章

| 标题 | 来源 | 核心主张 | 可深挖点 |
|------|------|---------|---------|
| **Building Effective Agents** | Anthropic, 2024.12 | 从简单开始；workflow（预定义路径）vs agent（自主循环）有本质区别；协调者-workers 是 workflow 不是 agent | workflow/agent 边界定义 |
| **Multi-Agent Research System** | Anthropic 工程博客 | Lead Agent 是完整 Agent，有 Memory，自主多轮迭代，但子 agent 不同步通信 | Memory 持久化 + resume 机制 |
| **Planner vs Orchestrator** | arXiv:2504.02051v2, 2025 | Planner（中央计划 + Worker 独立执行）比 Orchestrator（中央控制每一步）在成本效率上显著更好 | 定量数据：Claude Orchestrator $27.10 vs Planner $15.90 |
| **Event-Driven Multi-Agent** | Confluent, 2025 | 事件日志替代中央协调，消除 Worker 连接管理 | Kafka topic 分区策略 |
| **Functions as AI Agents** | Inferable, 2025 | 纯函数 Agent 可缓存（同输入同输出），比有状态 Agent 更可预测 | determinism + caching |
| **AutoGen Swarm Handoff** | Microsoft, 2025 | 去中心化 handoff：当前发言人决定下一个人，无需中央选择器 | 与 AgentHub Selector 的设计对比 |

### 1.4 权威网站

| 网站 | URL | 主要栏目 | 可深挖点 |
|------|-----|---------|---------|
| Anthropic Research | anthropic.com/research | Building Effective Agents, Multi-Agent Research System | workflow vs agent 的正式定义 |
| OpenAI Agents SDK | openai.github.io/openai-agents-python | multi_agent, handoffs, tools | Agents as Tools 的代码实现 |
| LangGraph Docs | langchain-ai.github.io/langgraph | concepts, tutorials, how-tos | StateGraph 的确定性执行模型 |
| Confluent Blog | confluent.io/blog | Event-Driven Multi-Agent Systems | Kafka 分区策略用于 Agent 编排 |
| Microsoft AutoGen | microsoft.github.io/autogen | user-guide, swarm, core | Swarm 的去中心化 handoff |

---

## 第二阶段：定向深入分析

### 选择理由

从 15+ 候选资源中选 3 个进行深入分析：

1. **OpenAI Agents SDK** — 唯一同时提供两种协调模式（Agent as Tool + Handoff）的框架，直接回答"协调者应该是工具还是 Agent"
2. **Confluent Event-Driven Multi-Agent** — 提出一种完全不同的范式（事件日志替代中央协调者），挑战"协调者必须存在"的前提
3. **arXiv:2504.02051v2** — 唯一的定量实验数据，直接比较 Orchestrator（中央控制）vs Planner（中央计划 + 自治执行）的成本和效率

---

### 2.1 OpenAI Agents SDK — 两种协调模式

**核心架构**：

```
模式 A: Agents as Tools（中央控制）

  Manager Agent（拥有对话控制权）
    │
    ├── tool: specialist_a = Agent.as_tool()    ← 子 Agent 被包装为工具
    ├── tool: specialist_b = Agent.as_tool()
    └── tool: specialist_c = Agent.as_tool()
    
  LLM 决策 → "调用 specialist_a tool" → 执行子 Agent → 结果返回 Manager
  Manager 合成所有结果 → 回复用户
  
  关键：Manager 从不放弃控制权
```

```
模式 B: Handoffs（控制权转移）

  Triage Agent（路由器）
    │
    ├── handoff: frontend_agent    ← 定义可转移的目标
    ├── handoff: backend_agent
    └── handoff: designer_agent
  
  LLM 决策 → "handoff 到 frontend_agent" → 控制权转移
  frontend_agent 直接回复用户 ← Triage 已不在循环中
  
  关键：控制权转移后不回来
```

**决策矩阵**：

| 维度 | Agents as Tools | Handoffs |
|------|:---:|:---:|
| 谁拥有最终回复 | Manager 始终控制 | Specialist 直接回复用户 |
| 控制流 | 中心化（委托-返回） | 去中心化（转移-不回） |
| Guardrail 位置 | 集中在 Manager | 分散在各 Specialist |
| 适用场景 | 需要合成多个输出、统一 guardrail | 需要专业 Agent 以自己身份回复 |
| 类比方案 1 (LLM 调用) | ✅ Coordinator.decompose() → Harness | ❌ |
| 类比方案 2 (Agent) | ✅ 协调者作为 Manager Agent | ⚠️ 可被 @ 触发时接近 |

**对 AgentHub 的启示**：

Agents as Tools 模式与方案 1（纯 LLM 调用）高度一致：Manager / Coordinator 做一次决策，产出结构化计划，控制权交给 Harness / 任务系统。Manager 不常驻。

Handoffs 模式与群聊的 Selector + @mention 机制一致：当前发言人把控制权交给下一个发言人。

OpenAI 的**混合模式**值得注意：「Triage Agent handoff 到 Specialist，Specialist 内部可以再用 Agents as Tools」。这支持我们的结论——协调者可以被 Selector 调动（类似 handoff），但分解本身是一次性的 LLM 调用（Agents as Tools 语义）。

---

### 2.2 Confluent Event-Driven Multi-Agent — 无中央协调者的架构

**核心洞察**：用共享事件日志替代中央协调者。

```
传统模型（中央协调者）：
  Orchestrator
    ├─→ Worker A  (管理连接、监控状态、处理故障)
    ├─→ Worker B
    └─→ Worker C
  问题：协调者必须管理所有连接 + 处理故障 + 负载均衡

事件驱动模型：
  Kafka Topic (tasks)
    ├─ Partition 0 → Worker A (消费者组)
    ├─ Partition 1 → Worker B
    └─ Partition 2 → Worker C
  Kafka Topic (results) ← Workers 写回
  协调者只负责"投递任务到 topic"，不管理连接
```

**四种模式**：

| 模式 | 协调逻辑 | 通信方式 |
|------|---------|---------|
| **Orchestrator-Worker** | 中央投递任务到 topic | key-based 分区 → Worker 消费者组拉取 |
| **Hierarchical** | 非叶节点是其子树的协调者 | 递归 topic 分区 |
| **Blackboard** | 无中央协调者 | 共享 topic，Agent 自由读/写 |
| **Market-based** | Market Maker 匹配 bid/ask | 独立 bid/ask 双 topic |

**关键优势（相比中央协调者）**：

1. **不需要管理 Worker 连接** — Worker 增减由 Kafka Consumer Rebalance 自动处理
2. **故障恢复免费** — 从 partition offset 重放即可
3. **消除 N² 连接** — Market 模式中 solvers 不需要互相知道对方
4. **协调者不再是单点故障** — 协调者挂了，topic 里积压的任务不丢

**对 AgentHub 的启示**：

方案 1（LLM 调用 + Harness + 任务系统）天然适合事件驱动后端。Coordinator 产出 TaskPlan，Harness 写入 PG（作为"伪事件日志"），Worker Pool 按 task status 拉取就绪任务。不需要协调者常驻监控——FSM + Repository 替代了连接管理。

方案 2（完整 Agent 协调者）如果采用事件驱动，协调者向 Worker 发私聊消息分配任务的模式反而退回到"点对点连接管理"，增加了协调者需要维护的状态。

---

### 2.3 arXiv:2504.02051v2 — 定量证明：Planner 优于 Orchestrator

**实验设计**：

- 模拟餐厅环境，Agent 需要协作完成订单（取食材 → 烹饪 → 上菜）
- 三种协调方法：Individual（各自为政）、Orchestrator（一个 LLM 生成所有 Agent 的所有动作）、Planner（一个 LLM 产出计划，Worker 自治执行，仅在关键事件时重新评估）

**关键数据**：

| 方法 | 最佳完成订单(6 agents) | 关键特征 |
|------|:---:|------|
| **Orchestrator (Claude 3.7)** | **98** | 最高原始产出，但最贵 |
| Planner (Claude + Llama 70B) | 77 | **最高成本效率** |
| Orchestrator (GPT-4o) | 40 | 更多 idle actions |
| Individual (Llama 70B) | 40 | 去中心化 baseline |

**成本对比**：

| 方法 | 成本(6 agents) | 每订单成本效率 |
|------|:---:|:---:|
| Orchestrator (Claude 控制 6 个 Agent 每一步) | **$27.10** | 低 |
| Planner (Claude 产计划 + Llama70B Worker) | **$15.90** | 高（节省 41%） |

**四条设计建议**：

1. **用 Planner 架构而非完整 Orchestrator** — Planner 只在关键事件时重新评估，减少协调开销
2. **向 Planner 提供 Worker 能力元数据** — 相比让 LLM 自己推断，显式标注 Worker 成功率大幅提升效率
3. **优先同质化小型强团队** — 混合强弱模型降低平均效率
4. **协调者模型大小应与任务复杂度匹配** — 复杂任务用大模型，简单任务用小模型

**对 AgentHub 的启示**：

这直接支持方案 1。论文的 "Planner" 就是我们的 Coordinator（产出 TaskPlan 后退出），论文的 "Orchestrator" 对应方案 2（协调者持续控制每一步）。定量结果清晰：Planner 更高效。

更重要的是发现 #2："向 Planner 提供 Worker 能力元数据"。这正是 `Agent.capability_tags` 应该做的事——不是让 Coordinator 从群聊推断"这个 Agent 能做什么"，而是直接注入 capability_tags 到 decompose prompt。

---

## 第三阶段：综合产出

### 3.1 三种协调范式的对比矩阵

| 维度 | 方案 1: LLM 调用 (Planner) | 方案 2: 完整 Agent (Orchestrator) | Event-Driven (无中央) |
|------|:---:|:---:|:---:|
| **代表** | Anthropic Workflow, OpenAI Agents as Tools | CrewAI Manager, Anthropic Lead Agent | Confluent Kafka, AutoGen Swarm |
| **协调者是什么** | 一次性 LLM 调用 | 持久 Agent (CLI session + state) | 不存在 / 退化为 topic producer |
| **任务分解** | ✅ 核心能力 | ✅ 核心能力 | ❌ 由消费者自治 |
| **进度监控** | ❌ FSM/Harness 接管 | ✅ 协调者持续跟踪 | ❌ 事件日志自动记录 |
| **Worker 通信** | ❌ 不直接通信 | ✅ 协调者可发消息 | ✅ 通过 topic pub/sub |
| **成本效率** | ✅ 41% cost savings (论文数据) | ❌ 最贵 (15x token) | ✅ 只支付 worker 成本 |
| **原始产出** | ⚠️ 论文: 77 orders | ✅ 论文: 98 orders | ❌ 论文: 40 orders (无协调) |
| **故障恢复** | ✅ 协调者无状态，F5 重试 | ❌ 协调者是单点 | ✅ Kafka 重放 |
| **人在环支持** | ✅ 通过 FSM PAUSE + UI | ✅ 协调者可等确认 | ⚠️ 需额外机制 |
| **AgentHub 适配度** | ✅ 已有 FSM/Harness/Selector | ⚠️ 与 Selector 角色重叠 | ⚠️ 需引入 Kafka，运维复杂 |

### 3.2 对方案 1 的增强建议（来自调研发现）

| 发现来源 | 对 AgentHub 的具体建议 |
|---------|----------------------|
| OpenAI "混合模式" | Coordinator.decompose() 产出的每个 Task 可以再嵌套 Coordinator 调用（如 Task 本身需要分解） |
| 论文 "能力元数据" | decompose prompt 必须显式注入 `[Agent.name, Agent.capability_tags, Agent.role]`，不依赖 LLM 推断 |
| Confluent "事件驱动" | Task FSM 的 `task_events` 表应作为 append-only 事件日志，Worker Pool 基于事件驱动拉取（而非协调者 push） |
| Anthropic "简单性原则" | 先实现 Coordinator.decompose() 作为单次 LLM 调用，验证够用。在够用之前不加状态/会话/监控 |
| AutoGen "Swarm Handoff" | Selector 的 @mention 路由机制已经实现了 de facto handoff——不需要协调者兼任路由器 |

### 3.3 待验证问题

| 问题 | 建议验证方式 | 优先级 |
|------|------------|:---:|
| 方案 1 的"无法迭代调整计划"在 AgentHub 场景下是否真实发生？ | 用 AgentHub 真实场景做端到端测试，记录需要"重新分解"的频率 | 高 |
| Coordinator 一次调用能否正确分解真实开发任务？ | 构建 eval set：10 个典型开发需求 → 人工评估 TaskPlan 质量 | 高 |
| Selector 的 `decompose` 出口触发准确率？ | 与 Coordinator eval 同步测试：Selector 对任务意图的识别准确率 | 中 |
| 不监控进度的情况下，用户满意度 vs 有监控进度？ | A/B 测试（方案 1 上线后再评估是否需补进度推送） | 低（后续迭代） |

### 3.4 结论

四个来源的共识汇聚到同一点：

- **Anthropic**：协调者-workers 是 workflow（预定义代码路径），不是 agent（自主循环）
- **OpenAI**：Agents as Tools 意味着 Manager 用工具调用子 Agent，不常驻
- **Confluent**：事件驱动架构下，中央协调者的连接管理职责被 topic 分区取代
- **论文**：Planner（计划+退出）在成本效率上显著优于 Orchestrator（中央控制每一步），节省 41%

**方案 1（纯 LLM 调用）是 4/4 来源支持的默认选择。**

方案 2（完整 Agent）的唯一优势是原始产出更高（论文：98 vs 77），但代价是 41% 的成本增加 + 新的单点故障 + 与 AgentHub 现有 Selector/Harness/FSM 的角色重叠。

---

## 参考

- OpenAI Agents SDK — Multi-Agent: https://openai.github.io/openai-agents-python/multi_agent/
- Confluent — Event-Driven Multi-Agent Systems: https://www.confluent.io/blog/event-driven-multi-agent-systems/
- arXiv:2504.02051v2 — Planner vs Orchestrator: https://arxiv.org/html/2504.02051v2
- Anthropic — Building Effective Agents: https://www.anthropic.com/research/building-effective-agents
- Anthropic — Multi-Agent Research System: https://www.anthropic.com/engineering/multi-agent-research-system
- Inferable — Functions as AI Agents: https://www.inferable.ai/blog/posts/functions-as-ai-agents
- AutoGen — Swarm Handoff: https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/swarm.html

## 关联文档

- [[coordinator-design-decision]] — 方案对比评估（已决策篇）
- [[task-execution-open-questions]] — 任务执行阶段待解决问题
- [[open-multi-agent_analysis_report]] — open-multi-agent 项目深度分析
- `docs/explore/EXP-02_编排器设计模式.md` — 编排器设计模式深度分析
