# 多 Agent 架构模式对比矩阵

> 清洗自 11 份原始资料，去除注释性内容，仅保留可对比的结构化数据。

## 一、各厂商架构核心组件对比

| 组件角色 | 微软 | Anthropic | Google Cloud | AWS | Augment |
|---------|------|-----------|-------------|-----|---------|
| **编排器** | Semantic Kernel Orchestrator | Lead Agent (Orchestrator) | ADK / Vertex AI Agent Builder | Strands Agents SDK | Orchestration Layer |
| **分类器/路由** | Classifier (NLU/SLM/LLM) | Lead Agent 内置 | Agent 设计模式选择 | Agent Graphs (DAG) | Routing (四大原语之一) |
| **Agent 注册** | Agent Registry (服务网格) | 内置子Agent管理 | Vertex AI Agent Registry | Strands SDK 内置 | 无独立组件 |
| **知识层** | Knowledge Layer + Vector DB | 文件系统 | Vertex AI Search / AlloyDB | Nova 模型内置 | Living Specifications (活文档) |
| **存储层** | Persistent Storage | 文件系统 | Cloud Memorystore / Spanner | AWS 托管存储 | State Management (五大模式) |
| **工具集成** | MCP Server | Custom Tools + MCP | MCP + Google APIs | Nova Tools | Skill-based |
| **通信协议** | Agent-to-Agent (9种模式) | 文件式通信 | Cloud Pub/Sub | Agent Graphs / Swarms | 四大原语中的 Routing |

## 二、编排拓扑 (Orchestration Topologies) 对比

| 拓扑类型 | 微软 | Anthropic | Google Cloud | AWS | Augment |
|---------|------|-----------|-------------|-----|---------|
| **Sequential Pipeline** | ✓ (Planner链式) | - | ✓ | - | ✓ |
| **Orchestrator-Worker** | ✓ (核心模式) | ✓ (核心模式) | ✓ (Hierarchical) | ✓ (Agents as Tools) | ✓ |
| **Peer-to-Peer Mesh** | - | - | - | ✓ (Swarms) | ✓ |
| **Hierarchical** | ✓ (Onion Arch) | ✓ (Sub-agents) | ✓ | ✓ (Agent Graphs) | ✓ |
| **Debate/Discussion** | - | - | ✓ | - | - |

## 三、Agent 协作模式对比 (AWS 四种模式 vs 其他厂商)

| AWS 模式 | 对应其他厂商实现 | 控制程度 | 灵活性 | AgentHub 适用度 |
|---------|----------------|---------|--------|----------------|
| **Agents as Tools** | Claude Code Subagents, MS Orchestrator | 高 | 低 | ★★★★★ 核心模式 |
| **Agent Graphs (DAG)** | LangGraph StateGraph, Augment 工作流 | 高 | 中 | ★★★★ 开发流水线 |
| **Agent Workflows** | n8n Workflows, MS Planner | 高 | 中 | ★★★★ 一键部署 |
| **Swarms** | - | 低 | 高 | ★★ 创意探索 |

## 四、设计模式全集 (跨来源合并去重)

| # | 设计模式 | 来源 | 说明 |
|---|---------|------|------|
| 1 | Semantic Router + LLM Fallback | 微软 | 语义路由优先，失败回退LLM |
| 2 | Dynamic Agent Registry | 微软 | 服务网格式的Agent注册发现 |
| 3 | Orchestrator + Skills | 微软/Anthropic | 中央编排器 + 可插拔技能 |
| 4 | Local & Remote Agent Execution | 微软 | 混合本地/远程Agent执行 |
| 5 | Onion Architecture | 微软 | 分层关注点分离 |
| 6 | MCP Integration | 微软/Claude Code | 标准化的Agent-工具通信协议 |
| 7 | RAG Pipeline | 微软/Google | 检索增强生成 |
| 8 | Conversation-Aware State | 微软 | 对话感知的上下文管理 |
| 9 | File-based Communication | Anthropic | Agent间通过文件交换数据 |
| 10 | Living Specifications | Augment | 外部活文档作为状态标准 |
| 11 | Event-driven Delta Delivery | Augment | 事件驱动的增量上下文传递 |
| 12 | Human-in-the-Loop | 微软/Claude Code | 关键决策需要人类审批 |
| 13 | @mentions Routing | n8n | 通过@指令触发特定Agent |
