# 技术栈与框架选型

> 清洗自: Claude Code SDK, Codex CLI, Google Cloud 架构, n8n 工作流, AWS Strands

## 一、Agent 平台适配器层对比

| 维度 | Claude Code | Codex CLI | 适配器层需求 |
|------|------------|-----------|------------|
| **API 接口** | Anthropic Messages API | OpenAI Chat Completions API | 统一消息格式 |
| **工具调用** | Tool Use (function calling) | Function Calling | 统一 Tool Schema |
| **文件操作** | read_file, write_file, edit_file | 文件系统直接操作 | 统一文件操作接口 |
| **命令执行** | exec_shell / bash | 终端命令 | 统一命令执行接口 |
| **会话管理** | Session (agent_open/eval/close) | Session-based | 统一会话生命周期 |
| **认证方式** | API Key / OAuth | ChatGPT 账户 / API Key | 统一认证层 |
| **MCP 支持** | ✓ 原生 | ✓ 支持 | 统一 MCP Client |
| **子Agent** | Subagents (agent_open) | 不支持原生子Agent | Orchestrator 实现 |
| **流式输出** | SSE Streaming | SSE Streaming | 统一流式适配 |

## 二、后端技术选型建议

| 层次 | 候选技术 | 推荐 | 理由 |
|------|---------|------|------|
| **API 框架** | FastAPI / Express / Hono | FastAPI (Python) | 异步支持好，AI 生态丰富 |
| **实时通信** | WebSocket / SSE / Socket.io | WebSocket (主) + SSE (流式) | 支持 IM 聊天 + Agent 流式输出 |
| **消息队列** | Redis Pub/Sub / RabbitMQ / Kafka | Redis Pub/Sub | 轻量级，适合 Agent 间通信 |
| **数据库** | PostgreSQL / MongoDB | PostgreSQL | 结构化会话 + JSONB 灵活存储 |
| **缓存** | Redis | Redis | 会话状态 + Token 计数 |
| **向量数据库** | Chroma / Pinecone / pgvector | pgvector (PostgreSQL 扩展) | 简化架构，与主库一体 |
| **LLM 网关** | LiteLLM / Portkey | LiteLLM | 统一 Claude + OpenAI API |

## 三、IM 聊天系统基础架构

| 组件 | 技术选项 | 说明 |
|------|---------|------|
| **消息格式** | 自定义 JSON Schema | 兼容飞书/微信消息模型 |
| **会话模型** | Chat → Threads → Messages | 类似飞书的层级结构 |
| **@mentions 解析** | 正则 + LLM 辅助 | 提取 @AgentName 触发特定 Agent |
| **多会话并行** | WebSocket Room 模式 | 每个会话独立 Room |
| **消息持久化** | PostgreSQL + Redis 缓存 | 历史消息查询 + 实时状态 |
| **通知推送** | WebSocket Push | Agent 完成通知、状态更新 |

## 四、代码开发全流程技术栈

| 流程环节 | 技术方案 | 说明 |
|---------|---------|------|
| **代码 Diff** | 统一 diff 格式 (unified diff) | 兼容 Claude Code + Codex 输出 |
| **Diff 预览** | Monaco Editor / diff2html | 可视化代码变更 |
| **Web 预览** | iframe Sandbox / Vite Dev Server | 前端项目实时预览 |
| **一键部署** | Docker + GitHub Actions / Vercel | 容器化 + CI/CD 集成 |
| **版本管理** | Git (libgit2 / isomorphic-git) | 代码变更追踪 |
| **项目模板** | 模板仓库 + Scaffold | 项目快速初始化 |

## 五、关键依赖库清单

```
# Python (FastAPI 后端)
fastapi
uvicorn
websockets
redis
asyncpg / sqlalchemy
litellm (统一 LLM 网关)
pydantic (数据验证)
httpx (HTTP 客户端)

# Node.js (前端)
react / vue
socket.io-client
monaco-editor / diff2html
```

## 六、部署架构

```
[用户浏览器] ←→ [Nginx 反向代理]
                    ↓
[FastAPI 应用服务器] ←→ [Redis 缓存/消息队列]
    ↓           ↓
[PostgreSQL]  [LiteLLM 网关]
    ↓           ↓        ↓
[pgvector]   [Claude API]  [OpenAI API]
```
