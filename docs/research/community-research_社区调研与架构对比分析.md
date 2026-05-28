# 社区调研与架构对比分析

> 调研日期：2026-05-23 | 基于 16 个社区项目 + 2 个参考项目

---

## 一、调研背景

重新审视两个根本性架构决策：

1. **Agent 接入深度**：完整接入 Claude CLI（子进程 pipe），还是套 SDK（Anthropic Messages API）
2. **IM 制作**：自己做消息管理（自定义 React + WebSocket），还是套飞书/微信 CLI

---

## 二、参考项目

| 项目 | Stars | 核心思路 |
|------|-------|---------|
| [cc-haha](https://github.com/NanmiCoder/cc-haha) | 11.5k | Fork Claude Code CLI，包 Tauri 桌面端 + IM 适配器层。CLI 子进程 per session，IM 适配器作为独立 Bun 进程通过 WebSocket bridge 连接 |
| [cc-connect](https://github.com/chenhg5/cc-connect) | - | 单 Node.js 进程，spawn CLI agent，支持 9 个 IM 平台。multi-bot relay 模式让多个 agent 在同一群聊对话 |
| [OpenClaw](https://github.com/openclaw/openclaw) | - | 最成熟的 agent gateway 框架。插件化架构，binding 系统路由 DM/群聊到特定 agent。生产部署跑 5 个 agent 协作 |
| [Ginnie Agents](https://github.com/nitaybz/ginnie-agents) | - | Slack 原生。每个 agent 有独立 Slack 身份。Docker 隔离 + episodic memory + cron 定时任务 |
| [agentchattr](https://github.com/bcurts/agentchattr) | - | 自定义 Web chat UI。@mention 触发 agent，MCP 工具协议。有 loop guard 防止 agent 无限互聊 |
| [AgentPipe](https://github.com/kevinelliott/agentpipe) | - | Go 写的 TUI 多 agent 聊天室。支持 14+ CLI。三种对话模式：round-robin / reactive / free-form。有 token 成本追踪 |

---

## 三、社区方案分类

### 3.1 按 Agent 接入方式

| 方式 | 采用项目 | 优势 | 劣势 |
|------|---------|------|------|
| **CLI 子进程** | cc-haha, cc-connect, clisbot, GolemBot, CodexBridge | 获得完整 Claude Code 能力（55+ 工具、MCP、skills、权限系统） | stdin/stdout 解析脆弱，资源占用大 |
| **SDK 套壳** | OpenClaw, HappyClaw, Ginnie Agents | 干净、轻量、可编程控制 | 需要自己实现工具系统、权限、记忆 |
| **混合** | AgentPipe, feishu-claude-code-bridge | 简单对话走 SDK，复杂任务走 CLI | 维护两套 |

**社区共识**：CLI 子进程是主流。因为 Claude Code CLI 的工具系统是 Anthropic 几百个工程师迭代的，自己用 SDK 重写不可行。

### 3.2 按 IM 方式

| 方式 | 采用项目 | 优势 | 劣势 |
|------|---------|------|------|
| **套现有 IM** | 几乎全部 16 个项目 | 免费获得身份认证、群组管理、消息投递、推送通知 | UI 受限（飞书卡片最多 4 按钮，微信不支持 iframe） |
| **自建 IM** | agentchattr, AgentPipe | 完全控制 UI，可嵌入 Diff/Preview/审批卡片 | 工程量巨大，本质上是另一个产品 |

---

## 四、社区关键架构模式

### 4.1 CLI 子进程 per Session

```
IM Platform (Feishu/WeChat/Telegram)
    │
    ▼
Adapter Process (独立进程，每种平台一个)
    │  WebSocket bridge
    ▼
Session Service (HTTP + WS server, ConversationService)
    │  spawn subprocess, stdin/stdout pipe
    ▼
Claude Code CLI (每个 session 一个独立子进程)
```

cc-haha 的核心模式。Session 存储在 JSONL 文件里，CLI 和服务端共享读写。每个 session 崩溃不影响其他 session。

### 4.2 @mention 路由

多 Agent 群聊的通用做法：用户在群里 @AgentName，消息路由到对应 Agent 的 session。OpenClaw 的 binding 系统、agentchattr 的 @mention trigger 都用此模式。

### 4.3 Loop Guard

agentchattr 和 OpenClaw 都实现了 loop guard —— 防止两个 Agent 在群里无限互聊。实现方式：检测连续 N 条消息都是 Agent 发送且互相 @，则强制静默。

### 4.4 流式消息缓冲

cc-haha 的 MessageBuffer 模式：累积文本 delta，200 字符或 500ms 超时刷新一次。各平台适配字符限制（Telegram 4096，微信 3500）。

---

## 五、与 AgentHub 当前方案的对比

### 5.1 Agent 接入

| | 社区方案 | AgentHub 当前 |
|---|---|---|
| **方式** | CLI 子进程为主 | SDK-first（Anthropic Messages API） |
| **当前实现** | — | `ClaudeAdapter`（SDK 流式已跑通） |
| **已规划** | — | Factory 支持 `claude_cli` 模式（未实现） |
| **工具系统** | 继承 CLI 内置 55+ 工具 | 自建 9 个 `BaseTool` + `ToolRegistry` + HITL |
| **权限** | 复用 CLI 内置权限 | 自建审批模式（正常/执行 + HITL 卡片） |
| **评价** | — | Adapter Factory 设计恰好兼容 CLI 模式，无需改架构，加一个 `ClaudeCLIAdapter` 即可 |

**差异本质**：你在用 SDK 重新实现 Claude Code CLI 已经内置的工具系统（文件读写、bash、git、MCP）。这不是可行性问题，是工程量问题——3 人 20 天不可能追平 Anthropic 团队迭代两年的工具生态。

### 5.2 IM 系统

| | 社区方案 | AgentHub 当前 |
|---|---|---|
| **方式** | 套飞书/微信/Telegram | 自建 React + WebSocket + Zustand |
| **工程量** | 每种平台 ~500 行 | 完整 IM 前端 + WS 服务端 + 消息持久化 |
| **已投入** | — | ChatView、MessageList、MessageInput、StreamingText、SessionList、Sidebar、useWebSocket、chatStore 等 |
| **社区采用** | **全部 16 个项目** | agentchattr、AgentPipe（实验性） |

**这是最大分歧**。但有一个关键判断：

> **你的产品是比赛 Demo，目标是展示多 Agent 协作能力。自建前端给你完全控制权：内联 Diff 卡片、iframe 预览嵌入、自定义任务卡片、审批交互。这些在飞书/微信里做不到。**

**结论：自建 IM 在这个场景下是合理的选择。**

### 5.3 多 Agent 编排

| | 社区方案 | AgentHub 当前 |
|---|---|---|
| **方式** | @mention 路由 + 简单对话 | Coordinator (LLM) + Harness (纯代码) + FSM (8态) + Celery Canvas DAG |
| **任务分解** | Agent 自行处理 | Coordinator Agent 产出结构化 JSON task plan |
| **任务调度** | 无（Agent 直接对话） | DAG 编译 → Celery Canvas → chord/group/chain |
| **状态管理** | 无 | 完整状态机 + Guard 校验 + 事件溯源 |
| **审批** | CLI 内置 | HITL 中断 + checkpoint 恢复 + 4 种决策 |

**你的编排层是最超出社区的部分。** 社区项目没有 Coordinator、没有 DAG、没有任务状态机。

Coordinator + Harness 分离是一个精心设计的模式——LLM 负责分解（不信任输出），纯代码负责校验和执行（硬约束）。这个设计在理论上是完整的。

**核心风险：双重编排**。Claude Code CLI 内部已经在做任务分解和工具调度。你在外面又包了一层编排器，可能导致两层都在做类似的事情。

### 5.4 记忆/上下文

| | 社区方案 | AgentHub 当前 |
|---|---|---|
| **方式** | 依赖 CLI 内部上下文 | 4 层记忆（L1 Redis 热 + L2 PG 摘要 + L3 文件 specs + L4 pgvector RAG） |
| **跨会话** | adapter-sessions.json 映射 | Session 表 + compressed_summary + Pin 机制 |

**4 层记忆是最有差异化价值的设计。** 社区项目基本没有这个层次。如果能跑通，是最大亮点。

### 5.5 架构复杂度

| | 社区方案 | AgentHub 当前 |
|---|---|---|
| **架构风格** | 适配器 + 服务 + 子进程 | 5 层洋葱 + DDD + 事件驱动 |
| **核心抽象数** | ~3 | ~30+ |
| **表数量** | 3-4 | 12 |
| **基础设施** | PG + Redis（可选） | PG + pgvector + Redis + Celery + RabbitMQ |
| **规则约束** | 无 | 27 条红线 |

---

## 六、建议：该改什么，不该改什么

### 保持（你的设计是正确的）

| 决策 | 理由 |
|------|------|
| **自建 IM 前端** | 比赛 Demo 需要完全控制 UI 展示层。内联 Diff/Preview/审批卡片必须有自定义渲染 |
| **4 层记忆体系** | 社区无此能力，差异化亮点。但 L3-L4 应降为可选项，优先把 L1-L2 做稳 |
| **Coordinator 分解** | LLM 驱动的任务分解是核心价值。保留 Coordinator Agent，简化下游调度 |
| **Agent 两级选择** | Agent 系统（Claude/Codex/Trae）与底层模型解耦，设计正确 |
| **StreamEvent 协议** | 统一的流式事件模型（TEXT/THINKING/TOOL_CALL/TOOL_RESULT/ERROR/DONE），设计良好 |

### 调整（跟社区对齐）

| 决策 | 当前 | 建议 | 理由 |
|------|------|------|------|
| **Agent 接入** | SDK-first | SDK + CLI 并存，加 `ClaudeCLIAdapter` | SDK 适合简单对话，CLI 适合复杂 coding。Adapter Factory 已支持这种扩展 |
| **工具系统** | 自建 9 个 BaseTool | CLI 模式直接用内置工具，SDK 模式保留自建 | 不要在 20 天内重新实现 Anthropic 的工具生态 |
| **任务调度** | Celery Canvas DAG | 简化为 task 表 + 轮询/回调执行 | DAG + Celery 的复杂度在 Demo 中不可见，性价比低 |
| **事件溯源** | task_events 表 | 可以保留表结构，但不要所有状态变更都写事件 | 审计/重放的收益在 Demo 中为零 |
| **依赖倒置** | Repository 接口 + Postgres 实现 | 单实现场景下直接 import SQLAlchemy 模型 | 减少 30% 样板代码。没有多实现切换需求 |

### 新增加

| 决策 | 理由 |
|------|------|
| **Loop Guard** | Agent 群聊中检测无限互聊循环，强制静默。agentchattr 已验证 |
| **@mention 路由** | 已在 spec 中设计，继续推进。这是多 Agent 交互的核心范式 |
| **流式消息缓冲** | 200 字符/500ms 刷新阈值，参考 cc-haha 的 MessageBuffer 模式 |
| **Session 文件持久化** | CLI 模式下 session 存为 JSONL 文件，Web 和 CLI 共享读写（参考 cc-haha） |

---

## 七、核心结论

**你的方案不是错了，是太重了。**

社区 16 个项目走了"薄包装 Claude CLI + 厚用现有 IM"的路，因为：
- 工具系统不值得重写
- IM 基础设施不值得重写
- 编排层在 CLI 内部已经有了

但你的约束不同：**比赛 Demo 场景下，展示效果 > 工程效率，差异化 > 成熟度。**

所以：

- **自建 IM 展示层**：值得。这是你的 Demo 核心体验。
- **4 层记忆**：值得。这是差异化。
- **Coordinator 分解**：值得。这是多 Agent 协作的核心。
- **Celery DAG + 事件溯源 + 依赖倒置**：砍掉。Demo 中看不见，纯消耗时间。
- **完整 CLI 接入**：加。SDK 已跑通，CLI 作为补充模式，两全其美。

**最终架构应该是**：

```
L5 自定义 React Chat UI（保留）
    │ WebSocket
L4 FastAPI Gateway（保留）
    │
L3 ChatService + CoordinatorService（保留，简化）
    │
L2 Agent Aggregate + Task FSM（保留）
    │
L1 ClaudeAdapter (SDK)  ←→  ClaudeCLIAdapter (子进程)  ←→  CodexAdapter
    │                         │
    ▼                         ▼
Anthropic API              Claude Code CLI subprocess
                           (完整工具生态，无需自建 Tool)
```

**社区项目教会我们的是偷懒，不是放弃。用 CLI 省掉工具系统的工程量，把时间花在 4 层记忆、Coordinator 分解、IM 展示这些真正有差异化的地方。**
