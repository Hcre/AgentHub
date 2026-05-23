# ADR-01: 从 API 重心转向 CLI 优先

> 架构决策记录 | 日期：2026-05-23 | 状态：已采纳

---

## 一、背景

AgentHub 的 PRD 和架构设计文档（v1.0, 2026-05-21）基于 L1-L5 五层洋葱模型定义了 LLM Adapter 作为 **单一抽象接口**：`UnifiedAgent`。初始设计默认 LLM 调用方式为 HTTP/SDK（Anthropic API），即：

```
ChatService → UnifiedAgent.stream(AgentRequest) → Anthropic API → StreamEvent
```

架构文档 S12/S13/S14 场景中描述的 **Harness（FSM/Guard/DAG/Worker 调度）** 全部假定 API 模式下 AgentHub 自建。这一假设隐含了一个巨大的工程量——自建完整 Agent 运行时。

## 二、问题发现

### 2.1 API 模式的实际工程量

| 组件 | 所需能力 | 预估工时 |
|------|---------|---------|
| Tool Loop 编排 | 多轮 tool_use 循环 | 20h+ |
| Tool 执行引擎 | ToolRegistry + FileSystem/Process 沙箱 | 25h+ |
| HITL 审批 | 危险操作拦截 + 用户决策恢复 | 15h+ |
| 会话状态管理 | L1-L4 记忆体系 + 上下文注入 | 15h+ |
| Worker Pool | Celery Canvas + 并发限流 | 10h+ |
| 多模型路由 | Claude/OpenAI/Gemini adapter | 10h+ |
| **合计** | | **95h+** |

这些工时远超 M2 6 天窗口。

### 2.2 CLI 自带完整 Harness

2026-05-22 审查 Claude Code CLI 的 `--print` / `--session-id` / `--resume` / `--output-format stream-json` 四个核心参数后发现：Claude Code CLI 不是 "LLM 的 HTTP 代理"，而是一个**自带完整 Agent 运行时的进程**：

| 能力 | API 模式 | CLI 模式 |
|------|---------|---------|
| Tool 执行（文件编辑/Bash/MCP） | 需自建 | ✅ CLI 自带 |
| 会话状态管理 | 需自建 L1-L4 | ✅ `--resume` sqlite 持久化 |
| Tool loop 编排 | 需自建 | ✅ CLI 内部完成 |
| 权限控制 | 需自建 HITL | ✅ `--permission-mode` |
| 流式输出 | ✅ Anthropic SDK | ✅ `--output-format stream-json` |

**Claude Code CLI 提供的恰好是 Harness 的全部能力，且零人力成本。**

### 2.3 对比分析

两种路线的实际差距：

| | API-centric（API 模式） | CLI-first（CLI 模式） |
|------|------|------|
| 会话维持 | ❌ 每次新建进程，全量传历史 | ✅ `--resume` 持久会话 |
| 工具执行 | ❌ 需自建 | ✅ CLI 自带 |
| 上下文膨胀 | ❌ 每轮传完整历史 | ✅ CLI 内部增量 |
| 实现复杂度 | 数千行自建 Harness | <300 行进程管理 + 事件转发 |

将 CLI 当作 API 使用（每次新建进程、全量传历史）是反模式。正确用法是 `--resume` 维持长驻会话，利用 CLI 自带的会话管理能力。

## 三、决策

**将架构从 API 单重心改为双轨：CLI Runtime（P0 优先）+ API Adapter（M3 以后扩展）。**

### 3.1 双轨架构

```
UnifiedAgent (ABC)
    ├── LLMAdapter (ABC)          ← API 模式：AgentHub 自建 Harness
    │   ├── ClaudeAdapter          (Anthropic API)
    │   └── OpenAICompatAdapter   (DeepSeek/Groq/vLLM — 未来)
    │
    └── AgentRuntime (ABC)        ← CLI 模式：复用 CLI 自带 Harness
        ├── ClaudeCodeRuntime      (Claude Code CLI — P0 当前)
        ├── CodexRuntime           (OpenAI Codex CLI — 未来)
        └── TraeRuntime            (Trae CLI — 未来)
```

### 3.2 CLI P0 优先的理由

1. **M2 时间约束**：6 天内跑通全链路（Agent 创建 → 私聊消息 → 流式回复 → 前端渲染），自建 Harness 不可能
2. **Harness 零成本**：Claude Code CLI 自带 tool 执行、会话状态、权限控制
3. **代码量可控**：`ClaudeCodeRuntime` 仅需 ~300 行进程管理 + 事件解析
4. **API 接口保留**：`UnifiedAgent` 抽象不变，后续随时加回 API Adapter
5. **AgentHub 核心价值不损**：前端交互层、会话/消息管理、多 Agent 权限体系仍然由 AgentHub 控制

### 3.3 统一的上下文入口

两种模式共享同一个 `AgentRequest` 结构体，CLI 模式通过可选增强字段注入额外上下文：
- `identity_prompt`：身份与角色描述（Agent 实体 + Group 上下文）
- `capability_prompt`：工具 + Skills 文本描述
- `peer_context`：其他 Agent 消息（群聊场景）

区别仅在于适配器的消费方式：
- API 模式：`AgentRequest` → `{system, messages, tools, params}`（SDK kwargs）
- CLI 模式：`AgentRequest` → 文本字符串（各可选字段拼接 + `-p` 当前消息）

详细接口定义见 `PRD_AgentHub_v4_统一方案.md` §三。

## 四、后果

### 4.1 正面

- M2 可交付：CLI 模式 6h 实现 vs API 完整实现 95h+
- AgentHub 作为"多 Agent 协作 UI 层"的价值不受损——CLI Agent 的聊天界面、流式渲染、任务看板仍然由 AgentHub 前端呈现
- 双轨独立演进：CLI 轨道的优化（如 MCP Server 挂载自定义工具）不影响 API 轨道

### 4.2 负面（已知负债）

- CLI 模式下 AgentHub 的记忆体系（L1-L4）被绕过——CLI 用自己的 sqlite 存历史，AgentHub PG 只存 user/assistant 快照
- CLI 权限由用户终端确认，不走 AgentHub HITL 审批流（M3 需通过 `--permission-mode` 参数 + CLI 的 permission 事件桥接）
- 多模型支持需等各家的 CLI 成熟（OpenAI Codex CLI、Trae CLI 均处于早期）

### 4.3 缓解措施

- `AgentRequest` 通过可选增强字段（`identity_prompt` / `capability_prompt` / `peer_context`）支持渐进注入，M3 以后填充记忆相关字段
- SessionStore（Redis 映射 `chatId ↔ sessionId`）确保 AgentHub 与 CLI 会话对齐
- 自定义工具通过 MCP Server 挂载，不依赖 CLI 自带工具集

## 五、CLI 会话管理方案

决策落地后发现了一个具体问题：CLI 用 `--session-id {session.id}` 维持长对话，但 AgentHub 与 CLI 的会话状态未对齐。

### 5.1 问题

```
前端 SessionList
  │  GET /api/sessions/{id}/messages
  ▼
AgentHub PG messages 表
  │  ChatService 只存: user_msg + assistant_msg（文本快照）
  ▼
ClaudeCodeRuntime
  │  --session-id {session.id}  ← UUID 相同
  │  CLI 内部完整历史 (~/.claude/sessions/{id}/):
  │    user → thinking → tool_call → tool_result → assistant → done
  │  AgentHub PG 存的内容 ≠ CLI 内部存的完整内容
```

两个具体缺陷：

| 缺陷 | 表现 |
|------|------|
| 消息不完整 | 前端只能看到 user/assistant 文本，看不到 tool_call/thinking |
| 会话映射丢失 | AgentHub session 删除后，CLI session 仍留在 `~/.claude/`，成为孤儿 |
| 无 GC 机制 | WebSocket 断开后 CLI 进程立即 kill，用户刷新就丢会话 |

### 5.2 解决方案

#### SessionStore（Redis 持久化映射）

```
Redis key:
  cli_session:{session_id}    → {session_id, agent_id, workspace_dir, created_at, updated_at}
  cli_sessions:{agent_id}     → 反向索引集合

TTL: 7 天，每次对话刷新
首次创建时 register()，后续对话 touch()，删除时 remove()
```

#### 消息历史双路径

| 端点 | 数据源 | 用途 |
|------|--------|------|
| `GET /api/sessions/{id}/messages`（已有） | AgentHub PG | 快速列表 |
| `GET /api/sessions/{id}/history`（新增） | CLI `~/.claude/sessions/{id}/transcript.jsonl` | 完整回放（含 tool_call/thinking） |

#### Session 生命周期

```
首条消息 → --session-id UUID-A（新建）→ SessionStore.register()
后续消息 → --resume UUID-A（恢复）→ SessionStore.touch()
WS 断开  → 延迟 30s kill，30s 内重连复用同一进程
删除 Session → SessionStore.remove() + 清理 CLI 文件（或靠 7 天 TTL）
```

### 5.3 设计依据

SessionStore 模式（`chatId ↔ sessionId` 映射 + 7 天 TTL）和消息历史双路径（PG 快照 + CLI JSONL 完整回放）是基于 CLI `--resume` 机制的设计推导。使用 Redis 替代文件持久化，与现有基础设施一致。

## 六、相关文档

| 文档 | 内容 |
|------|------|
| `DOC-15-claude-adapter-design.md` v1.2 | 双轨架构详细设计 |
| `DOC-17-context-injection-problem.md` | CLI 模式上下文注入问题分析 |
| `PRD_AgentHub_v4_统一方案.md` | v4 统一方案（含接口定义 + AgentRequest 增强字段） |
| `架构设计_分层与数据流.md` | §2.0 StructuredContext + §2.1 双轨架构 |

> `DOC-16-structured-context-design.md` 中的全量替换方案已被 DOC-17 否定，以 v4 的 `AgentRequest` 增强字段方案为准。

---

*Decision by: 董 (域2 DRI).  Reviewer: 黎.*
