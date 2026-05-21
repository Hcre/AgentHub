# 编排器 (Orchestrator) 设计模式深度分析

> 清洗自: 微软参考架构、Anthropic 研究系统、Augment 编排指南、模块化任务分解论文

## 一、Orchestrator 的核心职责 (跨来源共识)

| 职责 | 微软 | Anthropic | Augment | 论文 (arXiv:2511.01149) |
|------|------|-----------|---------|------------------------|
| **任务分解** | Planner 分解 | Lead Agent 分解 | Decomposition 原语 | 模块化分解机制 + 层次化子任务 |
| **意图路由** | Classifier → Agent Registry | Lead Agent 决策 | Routing 原语 | 动态调度与路由 |
| **上下文管理** | Storage Layer + 上下文窗口分配 | Token 预算管理 (15x 聊天) | State 原语 (5种模式) | 约束解析 + 全局一致性 |
| **结果合并** | Supervisor Agent 合成 | Lead Agent 合并 | Living Spec 验证 | 协作平衡度验证 |
| **故障恢复** | Fallback 机制 | 文件式通信合约 | Recovery 原语 (5种故障) | 动态策略调整 |

## 二、任务分解 (Decomposition) 方法论

### 微软 Planner 方式
- 使用 Semantic Kernel 的 Planner 功能
- 支持语义函数编排和步骤排序
- 分解为多个 Functions/Plugins/Agents 调用

### Anthropic Lead Agent 方式
- 主 Agent 判断哪些子任务可以并行
- 将子任务委派给专门的 Sub-agent
- 通过文件进行 Agent 间数据交换

### 论文 (arXiv:2511.01149) 方式
- **步骤1**: 自然语言 → 统一语义表示 (LLM 驱动)
- **步骤2**: 模块化分解 → 层次化子任务 + 依赖关系图
- **步骤3**: 约束解析 → 确保子任务间连贯连接
- **步骤4**: 动态调度 → 根据环境反馈持续调整

### Augment 四大原语方式
- 确定子任务间依赖关系
- 定义每个子任务的输入/输出 Schema
- 在交接点设置验证门控

## 三、Orchestrator 实现框架对比

| 框架 | 语言 | 编排模式 | 适用场景 | 成熟度 |
|------|------|---------|---------|--------|
| **Semantic Kernel** | C#/Python/Java | Planner + Skills | 企业级多Agent | 高 (微软维护) |
| **LangGraph** | Python | StateGraph + DAG | 复杂工作流 | 高 (LangChain) |
| **CrewAI** | Python | Role-based | 角色扮演协作 | 中 |
| **AutoGen** | Python | Conversation-driven | 对话式多Agent | 中 |
| **Strands Agents (AWS)** | Python | 4种模式 | AWS 生态 | 中 |
| **n8n** | Node.js | Workflow | 低代码自动化 | 高 |

## 四、AgentHub 编排器设计建议 (基于以上分析)

| 设计点 | 建议 | 依据 |
|--------|------|------|
| 核心模式 | Orchestrator-Worker | 微软 + Anthropic 共同选择 |
| 任务分解 | LLM 驱动的模块化分解 | 论文 arXiv:2511.01149 验证最佳 |
| 通信协议 | MCP + 文件式混合 | 微软 MCP 标准 + Anthropic 文件模式 |
| 状态管理 | Living Specifications + Event-driven Delta | Augment 5种模式分析 |
| 路由策略 | Semantic Router + @mentions | 微软分类器 + n8n @mentions |
| 故障恢复 | Schema Validation + 迭代限制 | Augment 故障模式研究 |
