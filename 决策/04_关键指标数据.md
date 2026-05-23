# 关键指标数据汇总

> 清洗自所有 11 份原始资料中的量化数据

## 一、Token 消耗数据

| 指标 | 数值 | 来源 |
|------|------|------|
| 多Agent vs 单次聊天的 Token 倍数 | **15x** | Anthropic 实测 |
| Blackboard 模式相对 RAG 成本 | **~2x** | Augment |
| Living Specifications 相对全量传递 | **节省 40-60%** | Augment |
| Event-driven Delta 相对全量传递 | **节省 30-50%** | Augment |
| 分层摘要相对全量传递 | **节省 20-30%** | Augment |
| 文件式通信 vs 流式传递 | **节省 10-20%** | Anthropic |

## 二、故障率数据

| 指标 | 数值 | 来源 |
|------|------|------|
| 协调故障占总故障比例 | **36.94%** | 研究数据 (跨 AutoGen, CrewAI, LangGraph) |
| 错误级联发生率 | 高 (未精确量化) | Augment |
| 无限循环发生率 | 中 | Augment |
| 上下文漂移发生率 | 中 | Augment |
| 验证误通过发生率 | 低 | Augment |

## 三、编排框架成熟度

| 框架 | 成熟度 | 维护方 | 语言生态 |
|------|--------|--------|---------|
| Semantic Kernel | 高 | 微软 | C# / Python / Java |
| LangGraph | 高 | LangChain | Python |
| CrewAI | 中 | 社区 | Python |
| AutoGen | 中 | 微软 | Python |
| Strands Agents | 中 | AWS | Python |
| n8n | 高 | n8n GmbH | Node.js (TypeScript) |
| Claude Code Agent SDK | 高 | Anthropic | TypeScript / Python |
| OpenAI Codex | 高 | OpenAI | Node.js |

## 四、MCP (Model Context Protocol) 采用情况

| 平台/框架 | 是否支持 MCP | 角色 |
|----------|------------|------|
| Claude Code | ✓ 原生支持 | Client + Server |
| 微软多Agent架构 | ✓ 集成层 | Server |
| Codex CLI | ✓ 支持 | Client |
| Google Cloud | ✓ Google APIs + MCP | Server |
| AWS Strands | ✗ (使用 Nova Tools) | - |

## 五、核心论文量化指标 (arXiv:2511.01149)

| 验证维度 | 方法论 | 对比基线 |
|---------|--------|---------|
| 任务成功率 | 模块化分解 + 动态协作 | 优于现有方法 |
| 分解效率 | LLM 驱动的语义分解 | 优于传统分解 |
| 子任务覆盖率 | 层次化分解 + 约束解析 | 更全面的覆盖 |
| 协作平衡度 | 动态路由 + 负载均衡 | 更平衡的负载 |
| 鲁棒性 | 全局一致性 + 动态调整 | 更好的抗干扰能力 |
