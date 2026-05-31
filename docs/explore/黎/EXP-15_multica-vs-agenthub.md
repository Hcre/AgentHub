# Multica vs AgentHub — 架构对比分析

> 日期: 2026-05-28 | 对比对象: [multica-ai/multica](https://github.com/multica-ai/multica)

---

## 1. 一句话总结

**Multica** 是 Board（看板）+ CLI 执行代理。把 AI Agent 当同事，在 GitHub Issue 风格的看板上分配任务，由本地 Daemon 扫描 PATH、调起 CLI 执行。

**AgentHub** 是 IM（聊天）+ 双轨适配器。把 AI Agent 当群聊成员，在飞书/钉钉风格的聊天界面里 @mention 协作，Adapter 负责屏蔽 CLI/API 差异。

同一个终点（多 Agent 协作），两条完全不同的交互路径。

---

## 2. 核心架构对比

| 维度 | Multica | AgentHub |
|------|---------|----------|
| **交互范式** | Board + Issue 分配 | IM 聊天 + @mention |
| **Agent 发现** | Daemon 扫描 PATH，自动检测已安装 CLI | 手动创建 Agent，配置 agent_system + provider |
| **执行层** | 本地 Daemon 作为唯一特权进程，shell out 到 CLI | 后端进程直接 spawn CLI 子进程，或通过 SDK 调 API |
| **适配器模式** | 隐式（provider 字段 + CLI wrapper） | 显式（LLMAdapter / AgentRuntime 抽象基类 + 工厂模式） |
| **状态模型** | enqueue→claim→start→complete/fail | Session 内流式事件（TEXT/THINKING/TOOL_CALL/DONE/ERROR） |
| **群组协作** | Squad（leader agent 路由分发） | Group Chat（@mention + dispatch_mode: at_routing/discussion） |
| **定时任务** | Autopilot（cron/webhook 触发） | 无内置支持 |
| **技能复用** | Skill（版本化、跨 workspace 共享） | Skill（Markdown 文件，挂载到 system prompt） |
| **前端** | Next.js 16 App Router | React 18 + Vite + Zustand |
| **后端** | Go (Chi + sqlc + gorilla/websocket) | Python FastAPI + SQLAlchemy + Celery |
| **数据库** | PostgreSQL 17 + pgvector | PostgreSQL 16 + pgvector（开发用 SQLite） |
| **消息推送** | WebSocket（gorilla/websocket） | WebSocket（FastAPI + ws_manager） |

---

## 3. 关键差异深度分析

### 3.1 PATH 扫描 vs 手动配置

**Multica** 的 PATH 扫描是杀手级特性：
```
PATH 里有 claude  → 自动检测 → 注册为可用 Runtime
PATH 里有 pi     → 自动检测 → 注册为可用 Runtime
PATH 里有 codex  → 自动检测 → 注册为可用 Runtime
```
用户装完 CLI 就能用，零配置。Daemon 启动时扫一遍，CLI 能力自动上报服务端。

**AgentHub** 需要手动在 UI 里创建 Agent，填写 provider、model、api_key、base_url。好处是可以精确控制每个 Agent 的配置（不同的 key、不同的 endpoint），坏处是有配置成本。

**→ AgentHub 可采纳**：在 `PiAgentRuntime` 或其他 CLI Runtime 初始化时，仿照 Multica 做 `shutil.which()` 扫描，自动发现可用的 CLI 并提示用户。当前 `PiAgentRuntime._pi_binary()` 已做了这一步的雏形。

### 3.2 Daemon vs 内嵌子进程

**Multica** 的 Daemon 是独立进程：
```
multica daemon start  →  后台长驻  →  WebSocket 连服务端  →  接收任务  →  调 CLI
```
好处是 daemon 作为唯一特权进程，服务端不需要知道 CLI 的细节。daemon 可以重启、升级而不影响服务端。

**AgentHub** 是服务端直接 spawn：
```
ChatService  →  Factory  →  PiAgentRuntime  →  asyncio.create_subprocess_exec("pi", ...)
```
好处是简单直接，坏处是后端进程耦合了 CLI 的安装位置和版本。

**→ AgentHub 可采纳**：不一定要做独立 daemon，但可以考虑把 CLI Runtime 抽象成「连接器」——支持本地子进程和远程 daemon 两种 backends。接口已经有了（`AgentRuntime`），只需多一个实现。

### 3.3 Agent-as-Teammate 的两种理解

**Multica** 的 Agent-as-Teammate 是**看板协作**模式：
- Agent 有头像、名称、Profile，出现在 Assignee 下拉框里
- 人类把 Issue 拖给 Agent，Agent 自己 claim、执行、comment
- Agent 的行为轨迹和人类一样（活动时间线）

**AgentHub** 的 Agent-as-Teammate 是**群聊协作**模式：
- Agent 在群聊里被 @mention，回复消息
- 私聊就是 1v1 对话
- Agent 产出 diff、preview_card、task_plan 等结构化卡片

两种理解不冲突，互补。Multica 更适合**异步任务**（「帮我修这个 bug」），AgentHub 更适合**同步对话**（「这段代码什么意思」）。

**→ AgentHub 可采纳**：在群聊中加入 Agent「认领任务」的交互——不是每次 @ 都自动执行，而是 Agent 先回复「收到，开始处理」，然后在 Task Engine 里执行。

### 3.4 Squad vs Group Chat

**Multica Squad** 是树形路由：
```
@FrontendTeam  →  Leader Agent  →  分发给 member Agent A / B / C
```
Leader 决定谁来做，对上层透明。

**AgentHub Group Chat** 是平面路由：
```
@AgentA @AgentB  →  串行逐个执行  →  各自回复
```
或者 discussion 模式下 Selector 选择一个人回复。

Multica 的 Squad 更接近真实的团队结构。AgentHub 的群聊更接近 Slack 频道。

### 3.5 Autopilot（定时触发器）

Multica 有 Autopilot：cron 表达式 + webhook + 手动触发 → 自动创建 Issue → 分配给 Agent。

AgentHub 没有这个能力。这是 Multica 最值得 AgentHub 采纳的特性之一——可以自动做日报、周报、定时巡检。

---

## 4. 架构决策对比表

| 决策 | Multica 选择 | AgentHub 选择 | 评价 |
|------|-------------|--------------|------|
| Agent 发现 | PATH 自动扫描 | UI 手动配置 | Multica 更自动化 |
| 执行模型 | 独立 Daemon 进程 | 后端嵌入子进程 | Multica 更解耦 |
| 交互入口 | Board（Issue 看板） | IM（聊天界面） | 不同场景，互补 |
| 适配器模式 | 隐式（provider 字段） | 显式（ABC + Factory） | AgentHub 更规范 |
| 群组模型 | Squad（Leader 路由） | Group（@ 路由） | Multica 更有层级 |
| 定时任务 | Autopilot | 无 | Multica 独有 |
| 记忆系统 | 无明确设计 | L1-L4 四层记忆 | AgentHub 独有 |
| API Key 管理 | 未明确 | 加密存储 + Proxy 注入 | AgentHub 更安全 |
| 部署方式 | Homebrew + Docker | Docker Compose | 两者类似 |

---

## 5. 我们该采纳什么

### 5.1 低代价、高收益（建议立即采纳）

| 特性 | 做法 |
|------|------|
| **PATH 扫描** | `PiAgentRuntime._pi_binary()` 已做 `shutil.which()`，扩展到 `ClaudeCodeRuntime`，启动时扫一遍可用的 CLI，在 Agent 创建 UI 中提示「检测到 pi / claude」|
| **Agents-as-Teammates 心智** | 群聊中 Agent 不只是回复文本，应该能「认领任务」「评论」「报告进度」，在 Task Engine 中增加状态推送 |

### 5.2 中代价、高收益（建议短期规划）

| 特性 | 做法 |
|------|------|
| **Autopilot** | 新增 `CronTrigger` + `AutopilotService`，cron 表达式触发 → 创建 Task → 分配给 Agent |
| **Squad 层级路由** | 扩展 `DispatchMode`，新增 `SQUAD` 模式，Leader Agent 决定分发策略 |

### 5.3 长期参考（不纳入当前路线图）

| 特性 | 说明 |
|------|------|
| **独立 Daemon** | 如果未来需要 Agent 在用户本机执行（访问本地文件、浏览器），值得做。当前云端 Proxy 模式更简单 |
| **Skill 市场** | Multica 的 skill 版本化 + lockfile 机制值得参考，但 AgentHub 当前 skill 量还不需要 |

---

## 6. 结论

Multica 和 AgentHub 解决同一个问题（多 Agent 协作），但选择了互补的交互范式：

- **Multica = Board × Daemon**：适合异步任务、多项目看板管理、定时自动化
- **AgentHub = IM × Adapter**：适合同步对话、群聊协作、快速问答

两者的适配器层设计思路一致（CLI wrapper → 统一协议），但 AgentHub 的显式 `AgentRuntime` 抽象比 Multica 的隐式 provider 字段更清晰。Multica 的 PATH 扫描 + Daemon + Autopilot 是 AgentHub 最值得借鉴的三个特性。
