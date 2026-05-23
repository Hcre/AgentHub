# 状态管理与故障恢复机制

> 清洗自: Augment 编排指南、Anthropic 研究系统、Google Cloud 架构、微软参考架构

## 一、五大状态管理模式 (来自 Augment 分析)

| 模式 | Token 成本 | 一致性 | 延迟 | 会话重启 | 适用场景 |
|------|-----------|--------|------|---------|---------|
| **Blackboard (黑板)** | 高 (~2x RAG) | 广播+自选择 | 可变 | 不支持 | 探索性协作 |
| **Graph-based Message Passing** | 低 (按需拉取) | 声明式依赖图 | 低 | 不支持 | 确定性流水线 |
| **Living Specifications (活文档)** | 极低 (外部读取) | 文件系统保证 | 无 (只读) | ✓ 支持 | 多会话协作、长周期任务 |
| **Hierarchical Summarization** | 中 (摊销) | 结构化交接 | 中 | 外部记忆 | 层次化Agent结构 |
| **Event-driven Delta Delivery** | 低 (仅增量) | 治理层管控 | 低 | 部分支持 | IM聊天、高频交互 |

## 二、五大故障模式及恢复机制 (来自 Augment + 多来源验证)

| 故障模式 | 发生率 | 根因 | 恢复机制 | 实现方案 |
|---------|--------|------|---------|---------|
| **Error Cascading (错误级联)** | 高 | 上游Agent输出被下游当作有效输入 | Schema Validation Gates | JSON Schema 校验 + 文件式通信合约 |
| **Infinite Loops (无限循环)** | 中 | Agent 输出触发另一个Agent，形成反馈环 | 迭代限制 + 退出条件 | LangGraph `RemainingSteps` + 布尔退出门控 |
| **Context Drift (上下文漂移)** | 中 | 上下文窗口填满后丢失关键信息 | Verifier Agent + 活文档 | 独立验证Agent检查结果 vs 活文档标准 |
| **Verifier False Passes (验证误通过)** | 低 | 验证Agent倾向于同意先前的输出 | 独立验证 + 协议检查 | 不同模型/Agent独立验证 + 跨协议一致性检查 |
| **Coordination Failure (协调故障)** | 36.94% | 多Agent间协调失败 | 全局一致性检查 | 结构化任务管理 + 约束解析 |

## 三、Token 成本控制策略

### Anthropic 实测数据
- 多 Agent 系统 Token 消耗 ≈ 单次聊天交互的 **15 倍**
- 需要通过状态管理策略控制

### 成本优化方案 (跨来源综合)

| 策略 | 预期节省 | 实现难度 | 来源 |
|------|---------|---------|------|
| Event-driven Delta Delivery | 30-50% | 中 | Augment |
| Living Specifications (代替全量上下文传递) | 40-60% | 低 | Augment |
| 分层摘要 (Hierarchical Summarization) | 20-30% | 中 | Augment |
| 文件式通信 (代替流式传递) | 10-20% | 低 | Anthropic |
| 上下文窗口优化分配 | 15-25% | 中 | 微软 |
| 按需拉取 (Graph-based) | 20-40% | 高 | Augment |

## 四、AgentHub 状态管理设计建议

| 场景 | 推荐模式 | 理由 |
|------|---------|------|
| 单聊 (1对1 Agent) | Event-driven Delta Delivery | 低延迟、低成本，适合 IM 高频交互 |
| 群聊 (@mentions) | Graph-based Message Passing | 按需拉取，减少不相关Agent的上下文污染 |
| 跨会话任务 (长时间运行) | Living Specifications | 会话重启后状态不丢失 |
| Orchestrator → Worker | Hierarchical Summarization | 结构化交接，层级清晰 |
| 创意/探索任务 | Blackboard | 允许 Agent 自主选择参与 |
