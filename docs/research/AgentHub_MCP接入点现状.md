# AgentHub MCP 接入点现状梳理

> 写于: 2026-06-02 | 角色: mcp-system-analyst | 任务 ID: `agenthub-mcp-status`
> 配套计划: `docs/plan/MCP功能计划_v0.md`（P1→P3→P2→P4 顺序, 4 收束, 6/15 截止）
> 任务在 Plan A 第 3 块: 调研现状 + 输出文件清单

---

## 摘要（TL;DR）

AgentHub **目前没有自研的 MCP 客户端/服务器**。所有"工具调用"都依赖 CLI 工具（Claude Code / OpenCode / Pi Agent）**自身 Harness** 自带的 MCP 能力。
**3 个空白点**：

1. **客户端层空白** — 没有 `mcp` Python 包依赖，没有 manifest 拉取/缓存/工具发现/JSON-RPC stdio/SSE 客户端
2. **服务器管理层空白** — 没有 MCP server 进程管理（启/停/超时/日志），只有 `claude_code_process_pool` 管理 CLI
3. **领域模型空白** — 没有 `mcp_servers` / `mcp_installations` / `agent_mcp_bindings` 三张表，只有 `agents` 表带 `capability_tags` / `skills`

**最近参考**：
- `docs/explore/EXP-08_PageIndex技术影响分析.md` 提出过 "AgentHub → MCP Client → PageIndex MCP Server" 设想（仅 PPT 级，无代码）
- `docs/explore/EXP-04_关键指标数据.md` §四 调研列出 Claude Code / 微软 / Codex / Google Cloud 均原生支持 MCP
- `docs/plan/MCP功能计划_v0.md` 已规划 4 阶段实施，本文件是其 Plan A 第 3 块（现状摸底）

---

## 1. 现状 — 哪些地方已经用 MCP 了？

### 1.1 代码层（实际实现）— 1 处提及

```
$ grep -r "mcp|MCP" src/backend/ --include="*.py"
→ 1 matches in provider_scanner.py line 37
  description="sst/opencode — 75+ provider, 支持 agent/mcp/acp"
```

**仅一处**字符串提及 MCP，位于 `src/backend/app/infrastructure/llm/provider_scanner.py` 的 ProviderDef 描述字段，**没有任何 MCP 客户端/服务器代码**。

### 1.2 CLI 工具自身支持（间接借用）

AgentHub 当前 5 种 CLI Runtime **都支持 MCP client**（通过 CLI 自身 Harness），但 AgentHub 进程**完全不知道、不参与、不拦截**：

| AgentSystem | Runtime 类 | 工具生态 | MCP 角色 |
|------|------|------|------|
| `claude_code` | `ClaudeCodeRuntime` | CLI 内置 55+ 工具 + Skills | CLI 内置 client，可读 `~/.claude.json` 里配置的 mcp server |
| `pi_agent` | `PiAgentRuntime` | 内置 7 件套 + Extension | CLI 内置 client + extension 机制 |
| `opencode` | `OpenCodeRuntime` | 75+ provider + agent + **mcp + acp** | CLI 内置 client，描述里就写了 "支持 mcp/acp" |
| `codex` | (未实现) | OpenAI 编码 Agent | 原生支持 MCP client |
| `gemini` | (未实现) | Google Gemini CLI | 部分支持 |

**关键认知**：所有 `tool_use` / `tool_result` 事件是 CLI **自己跑** MCP 工具后产生的；AgentHub 只是在 `_parse_line()` 里**被动透传**。

### 1.3 EXP-08 PageIndex（PPT 级设想）

`docs/explore/EXP-08_PageIndex技术影响分析.md` §2.3 提议 "PageIndex MCP Server → AgentHub → MCP Client" 集成路径，但**未落到代码、未写 spec**。当前 Pgvector 仍是 L4 知识库唯一实现。

### 1.4 工具调用事件全链路（不区分工具来源）

| 事件类型 | 来源 | 协议位置 |
|------|------|------|
| `TOOL_CALL` (name/input) | 任何 LLM/CLI 工具 | `app/domain/llm/protocol.py:48` `StreamEventType.TOOL_CALL` |
| `TOOL_RESULT` (success/content/error) | CLI 内部执行完，stdout 透传 | 同上 L48 `StreamEventType.TOOL_RESULT` |
| `_parse_line()` 解析 tool_use/tool_result 块 | 4 个 Runtime 共用 | `claude_code_runtime.py:501-544` / `claude_adapter.py:181-194` / `pi_agent_runtime.py:337-360,432-444` / `opencode_runtime.py:231-259` |

**问题**：当前 `StreamEvent.tool_call` 只带 `name` + `arguments`，**没有"来自哪个 MCP server"** 这个字段。要做"工具调用展示"必须先扩展 `ToolCall` 数据结构。

### 1.5 工具调用 UI（前端 MVP 忽略）

```typescript
// src/frontend/src/stores/chatStore.ts:131
// thinking / tool_* / task_plan / request_approval：MVP 暂不渲染
// src/frontend/src/stores/groupStore.ts:218
// thinking / tool_* / request_approval / task_plan：MVP 不渲染
// src/frontend/src/components/agent/AgentDetailPage.tsx & types/index.ts:155
// 仅有 type-level 字段 tools: string[]（capability_tags 装饰用，非工具调用）
```

**前端不知道也不展示**任何 tool_call 事件。`MCP功能计划_v0.md` P4 阶段才会做"工具调用内联卡片"。

### 1.6 类似参考实现：Skill Marketplace

`src/backend/app/api/routers/skills.py` 是**最接近 MCP 市场**的现有模式：
- `GET /api/skills/library` 列本地已装 skill
- `POST /api/skills/marketplace/search` 代理 skillsmp.com 搜索
- `POST /api/skills/marketplace/install` 从 GitHub 递归拉取

但 skill 是**文本文件**（`SKILL.md`），注入到 system_prompt 头部；MCP 是**进程级**服务（stdio 子进程 / SSE HTTP），量级完全不同。

### 1.7 现状清单（结论）

| 维度 | 现状 | 说明 |
|------|------|------|
| MCP 客户端库 | ❌ 无 | 没有任何 mcp Python 包依赖（pyproject 未引入） |
| MCP 服务器进程管理 | ❌ 无 | 没有 stdio 启停/超时/日志 |
| manifest 缓存/发现 | ❌ 无 | 没有 list_tools 缓存层 |
| `mcp_servers` / `mcp_installations` / `agent_mcp_bindings` 表 | ❌ 无 | 当前 6 表精简版不含 |
| Agent 配置可绑定 MCP | ❌ 无 | `Agent` 实体无 `mcp_bindings` 字段 |
| CLI Adapter 动态挂载 MCP | ❌ 无 | `_build_cmd()` 只设 `--permission-mode` / `--max-turns`，不注入 mcp config |
| `StreamEvent.tool_call` 含 server 来源 | ❌ 无 | 当前只有 name/arguments，没有 server_name 字段 |
| 前端工具调用展示 | ❌ 无 | MVP 注释掉，未来 P4 做 |

**实质状态**：MCP 借助 4 种 CLI 工具的 Harness 能力**已经能用**（用户在本地 Claude Code 配置 MCP server 后，AgentHub 调度时自动通过 CLI 调用），但 AgentHub 自身**对此完全黑盒**，无法控制、无法展示、无法市场分发。

---

## 2. MCP 客户端代码位置 — 在 5 层洋葱哪一层？哪个文件？

### 2.1 结论：客户端代码目前不存在

**整个 src/backend 下没有 MCP 客户端代码**。现有的"tool"相关代码全部是被动解析 CLI/SDK 输出的 stream-json，按 `StreamEvent` 协议归一化到 L2。

### 2.2 当前"工具"处理分散在以下文件

| 文件 | 层级 | 作用 | 关键行 |
|------|------|------|------|
| `src/backend/app/domain/llm/protocol.py` | L2 | 定义 `StreamEvent` / `ToolCall` / `ToolResult` 数据结构 | L29, L48, L56-77 |
| `src/backend/app/domain/llm/protocol.py` | L2 | `AgentRequest.available_tools: list[str]` 占位字段 | L29 |
| `src/backend/app/infrastructure/llm/claude_adapter.py` | L1 | Anthropic SDK tool_use → `TOOL_CALL` 事件 | L142-194 |
| `src/backend/app/infrastructure/llm/claude_code_runtime.py` | L1 | Claude CLI stdout tool_use/tool_result 解析 | L501-544 |
| `src/backend/app/infrastructure/llm/pi_agent_runtime.py` | L1 | Pi RPC toolcall_end/tool_execution_end 解析 | L432-444, L340-360 |
| `src/backend/app/infrastructure/llm/opencode_runtime.py` | L1 | OpenCode tool_call/tool_result 解析 | L231-259 |
| `src/backend/app/application/services/selector.py` | L3 | Selector LLM 决策（独立 tool loop） | L301-309, L374-455 |
| `src/backend/app/application/services/chat_service.py` | L1 引用 | `_stream_one_agent` 不解析 tool，透传；仅检测 `permission_denials` → `REQUEST_APPROVAL` | L216-251 |

### 2.3 协议层（`app/domain/llm/protocol.py`）的扩展点

```python
# 当前
class AgentRequest(BaseModel):
    available_tools: list[str] = []           # 仅 string 列表，无 schema
    # 无 mcp_bindings / mcp_servers 字段

class ToolCall(BaseModel):
    call_id: str
    name: str
    arguments: dict[str, Any]
    # 无 server_name / server_id 字段

class StreamEventType(StrEnum):
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    # 已是统一事件，无需新增
```

**MCP 接入后必须扩展**（按影响面排）：
1. `ToolCall.server_name: str | None` — 区分是 CLI 内置工具还是 MCP 工具（P4 内联展示用）
2. `ToolCall.server_id: UUID | None` — 记录来自哪个 `mcp_installation`
3. `AgentRequest.mcp_config_path: str | None` — runtime 用它知道 mcp.json 在哪
4. `AgentRequest.mcp_bindings: list[UUID]` — 让 runtime 知道要挂载哪些 server
5. （可选）`StreamEventType.MCP_TOOL_CALL = "mcp_tool_call"` 与内置工具区分

### 2.4 LLMAdapter `claude_adapter.py` 的 ToolRegistry 占位

```python
# src/backend/app/infrastructure/llm/claude_adapter.py:246-257
def _build_tool_definitions(available_tools: list[str]) -> list[dict[str, Any]]:
    """将 available_tools 名称列表转换为 Anthropic tools 参数。
    当前阶段：ToolRegistry 尚未实现，返回空列表。
    M3 实现后，此函数从 ToolRegistry 查询完整 JSON Schema。
    """
    # TODO(M3): 从 ToolRegistry 获取 ToolDefinition 并转为 Anthropic schema
```

**这是 L1 为未来 MCP 接入预留的钩子**。但 ToolRegistry 本身不存在，且该 TODO 已与"CLI 优先"战略冲突 — 实际 API 模式（`anthropic_api`）调用越来越边缘。

---

## 3. MCP server 进程管理 — 怎么启？怎么关？怎么超时？日志？

### 3.1 结论：当前没有任何 MCP server 进程管理

**唯一存在的进程管理是 `claude_code_process_pool.py`，专管 Claude CLI 长驻进程**。MCP server 进程管理需从零开始，但可参考该池子的设计。

### 3.2 当前 Claude CLI 进程管理可借鉴

| 维度 | `claude_code_process_pool.py` | 未来 MCP server pool 需补 |
|------|------|------|
| 启动方式 | `asyncio.create_subprocess_exec("claude", ...)` | stdio: `asyncio.create_subprocess_exec("mcp-server-fs", ...)`; SSE: `httpx.AsyncClient(url)` |
| 关闭（优雅） | `proc.stdin.close()` + `terminate()` + `wait(3s)` | stdio: 同左; SSE: 关闭 httpx 连接 |
| 关闭（强制） | `kill()` after 3s timeout | 同左 |
| 超时 | `_idle_ttl_seconds=300`（idle 淘汰） | 需新增：单次 RPC 超时（如 30s）、idle 淘汰、硬上限 |
| 进程池上限 | `soft_max=32` / `hard_max=64` / LRU 淘汰 | 同上 |
| 后台扫描 | `start_sweeper()` 每 60s 扫 idle | 同上 |
| 启动/结束钩子 | FastAPI lifespan (`shutdown_pool`) | 同上 |
| per-key 锁 | 防同 session_key 并发 spawn 竞态 | 同上，按 mcp_installation_id 锁 |
| stdin 写锁 | handle 自带，防 JSONL 交错 | stdio MCP 同样需要 |
| 崩溃恢复 | `runtime._stream_long_running` 捕 RuntimeError → drop + `--resume` 重 spawn | stdio MCP: 捕 EOF → 重 spawn; SSE: 重连 |
| **stdout 解析** | `_parse_line` 5 类事件 | **MCP：JSON-RPC 2.0 over stdio / SSE**（全新协议） |
| **stdin 协议** | stream-json user message | **MCP：JSON-RPC request（initialize / tools/list / tools/call）** |
| 日志 | 通过 `logger.info/warning/exception` | 同样复用，但需对 stdio stderr 单独捕获（区分协议输出） |

**关键差异**：CLI 跑 Anthropic 协议（agent 内对话），MCP 跑 JSON-RPC 2.0（工具调用）。**进程管理可复用，协议栈必须新写**。

### 3.3 进程管理需落地的关键状态机

```
McpServer (mcp_servers 表)
  id, name, transport (stdio/sse), manifest (JSON), owner
  
McpInstallation (workspace_mcp_installations 表)
  id, server_id, installed_at, raw_config (env/cmd/args/url/auth), status
  
McpBinding (agent_mcp_bindings 表)
  id, agent_id, installation_id, override (env/args 覆盖), created_at

ProcessManager 内存状态
  {installation_id: McpProcessHandle}   # 类比 ProcessPool
    - proc / client
    - last_used, idle_ttl
    - stdin_lock (stdio only)
    - capabilities: list[str]  # tools/list 缓存
    - transport: "stdio" | "sse"
```

### 3.4 日志/可观测性现状（可复用）

- `app/core/logging.py` 提供统一 logger（`logging.getLogger(__name__)`）
- 所有进程级事件用 `logger.info` / `logger.warning` / `logger.exception`
- 进程 stderr 当前**只在错误时 dump 一次**（`claude_code_runtime.py:357-364`），MCP 需持续捕获到独立日志文件
- 无 stdout/stderr 持续透传 → 需补 `McpProcessHandle` 加 stderr reader 协程，写 `logs/mcp/{installation_id}.log`

### 3.5 进程启停接口（建议设计，落到 P1）

```python
# 未来 app/infrastructure/mcp/process_manager.py 草案
class McpTransport(StrEnum):
    STDIO = "stdio"
    SSE = "sse"

class McpProcessHandle:
    installation_id: UUID
    transport: McpTransport
    # stdio 模式
    proc: asyncio.subprocess.Process | None
    stdin_lock: asyncio.Lock
    # sse 模式
    client: httpx.AsyncClient | None
    # 共享
    capabilities: list[ToolDef]   # tools/list 缓存
    last_used: float
    alive: bool

class McpProcessPool:
    async def acquire(installation_id, transport, spawn_fn) -> McpProcessHandle
    async def drop(installation_id)
    async def shutdown()  # FastAPI lifespan
    async def _sweep_once()  # idle TTL
```

**与现有 pool 的关系**：建议**不合并**，因为：
- CLI pool 按 session_key（每个会话一个长驻进程）
- MCP pool 按 installation_id（每个 server 一个进程，跨 session 共享）
- LRU / 软硬上限阈值不同（CLI 32/64 vs MCP 期望 8-16）

---

## 4. 5 层洋葱接入新模块的最佳位置

### 4.1 总体布局（按 5 层依赖规则 L5→L4→L3→L2←L1）

```
L5 Presentation (React)
└── /mcp-market          列表/搜索/详情
└── /mcp-create          提交表单（stdIO/SSE）
└── AgentDetailPage 新 Tab  "MCP 接入"
└── ChatView/MsgBubble    tool_call 内联卡片 (P4)

L4 API Gateway (FastAPI Router)
└── app/api/routers/mcp.py         GET/POST /api/mcp/...
└── app/api/routers/agent_mcp.py   GET/POST /api/agents/{id}/mcp

L3 Application (Service)
└── app/application/services/mcp_market_service.py     列表/搜索/详情
└── app/application/services/mcp_installation_service.py 安装/卸载/启停
└── app/application/services/mcp_binding_service.py    绑定/解绑/override
└── app/application/commands/    CreateMcpServerCmd / BindMcpCmd 等

L2 Domain (Entity + Repository Interface)
└── app/domain/entities/mcp_server.py         McpServer 聚合根
└── app/domain/entities/mcp_installation.py   McpInstallation 聚合根
└── app/domain/entities/mcp_binding.py        McpBinding 实体
└── app/domain/enums.py        + McpTransportType, McpServerStatus
└── app/domain/repositories/mcp_server_repository.py
└── app/domain/repositories/mcp_installation_repository.py
└── app/domain/repositories/mcp_binding_repository.py

L1 Infrastructure
└── app/infrastructure/db/models.py        + 3 张 ORM (McpServerModel 等)
└── app/infrastructure/repositories/mcp_server_repository.py    SQLAlchemy 实现
└── app/infrastructure/repositories/mcp_installation_repository.py
└── app/infrastructure/repositories/mcp_binding_repository.py
└── app/infrastructure/mcp/process_manager.py     进程池 + idle sweeper
└── app/infrastructure/mcp/mcp_client.py         JSON-RPC 2.0 client (stdio + SSE)
└── app/infrastructure/mcp/mcp_registry.py       manifest 缓存 + 工具发现
└── app/infrastructure/mcp/manifest_validator.py  manifest JSON Schema 校验
└── alembic/versions/0006_xxx_mcp_*.py            3 张表 migration
```

### 4.2 关键 L2 实体（建议骨架，P1 阶段冻结）

```python
# app/domain/entities/mcp_server.py
@dataclass
class McpServer:
    """MCP server 模板（市场里的"商品"）。"""
    id: UUID
    name: str                              # 唯一标识 "filesystem"
    display_name: str
    description: str
    transport: McpTransportType            # stdio | sse
    manifest: dict                         # {"tools":[{"name":"read_file",...}]}
    category: str                          # "filesystem" | "search" | "github" ...
    tags: list[str]
    user_submitted: bool                   # 区分官方 vs 用户自建
    template_id: str | None                # P3 模板引用
    raw_config: dict | None                # P3 用户提交的配置
    status: McpServerStatus                # active | deprecated
    created_at: datetime
    updated_at: datetime

# app/domain/entities/mcp_installation.py
@dataclass
class McpInstallation:
    """某个 workspace 安装的 MCP 实例（"商品"被装到本地）。"""
    id: UUID
    server_id: UUID                        # → McpServer.id
    workspace_id: UUID                     # 当前 session/agent 所在 workspace
    raw_config: dict                       # stdio: {cmd,args,env}; sse: {url,auth}
    status: McpInstallationStatus          # installed | running | stopped | error
    last_error: str | None
    last_started_at: datetime | None
    installed_at: datetime

# app/domain/entities/mcp_binding.py
@dataclass
class McpBinding:
    """Agent 绑定某个 Installation（"商品"被谁使用）。"""
    id: UUID
    agent_id: UUID                         # → Agent.id
    installation_id: UUID                  # → McpInstallation.id
    override: dict | None                  # 覆盖 env/args（如填入用户的 key）
    enabled: bool
    created_at: datetime
```

**三实体关系**（呼应 `MCP功能计划_v0.md` §一 P1 阶段的 3 张表）：
```
McpServer (1) ── (N) McpInstallation (1) ── (N) McpBinding (N) ── (1) Agent
   模板              安装实例                   绑定关系                使用方
```

### 4.3 现有 L1 进程管理可借鉴

`src/backend/app/infrastructure/llm/claude_code_process_pool.py` 设计完美可参考：
- `ProcessPool` 类的 acquire/drop/shutdown 接口
- per-key spawn 锁 + LRU 淘汰 + idle sweeper
- 全局单例 + FastAPI lifespan 钩子

**建议**：`app/infrastructure/mcp/process_manager.py` 复用 90% 设计，独立成池。

### 4.4 L1 MCP 客户端（全新，必须新写）

- **依赖**：MCP 官方 Python SDK `mcp` 包（`pip install mcp`），或自实现 JSON-RPC 2.0 over stdio
- **stdio 协议**：JSON-RPC 2.0 per line
  - `initialize` → server info
  - `tools/list` → manifest
  - `tools/call` → 实际调用
  - `notifications/*` → server → client push
- **SSE 协议**：HTTP POST 发请求，SSE 流收通知
- **manifest 验证**：JSON Schema 校验（用 `jsonschema` 包）

### 4.5 L1 配置文件惯例

CLI 加载 MCP 的方式（关键事实，决定扩展点）：

| CLI | MCP config 路径 | 加载方式 |
|------|------|------|
| Claude Code | `~/.claude.json` 的 `mcpServers` 字段 / `~/.claude/mcp.json` | CLI 启动时读 |
| OpenCode | `~/.config/opencode/opencode.jsonc` 的 `mcp` 字段 | CLI 启动时读 |
| Pi Agent | 通过 extension | runtime 注册 |
| Codex | `~/.codex/config.toml` | CLI 启动时读 |

**P2 阶段（CLI Adapter 扩展）关键**：AgentHub 要在 spawn CLI 前**动态写入这些文件**。详见 §5。

### 4.6 L4 API 路由设计（草案）

```
GET    /api/mcp/servers                  列表（市场浏览）
GET    /api/mcp/servers/search?q=&tag=   搜索
GET    /api/mcp/servers/{id}             详情（manifest 完整）
POST   /api/mcp/servers                  P3: 用户提交
POST   /api/mcp/servers/{id}/validate    P3: 干跑沙箱

POST   /api/mcp/installations            安装到 workspace
GET    /api/mcp/installations            列出当前 workspace 安装的
DELETE /api/mcp/installations/{id}       卸载
POST   /api/mcp/installations/{id}/start 手动启动
POST   /api/mcp/installations/{id}/stop  手动停止

GET    /api/agents/{id}/mcp              列出 Agent 绑定
POST   /api/agents/{id}/mcp              绑定
PATCH  /api/agents/{id}/mcp/{bid}        改 override
DELETE /api/agents/{id}/mcp/{bid}        解绑
```

对齐现有 `04-commands_命令接口.md` 的 kebab-case + 复数 + `{error:{code,message}}` 规范。

### 4.7 L5 前端

- 路由 `/mcp-market` / `/mcp-create`
- AgentDetailPage 新 Tab "MCP 接入"（仿 SkillMarketplacePage 风格）
- P4 阶段：MessageBubble 内联 tool_call 卡片（折叠/展开/复制）

---

## 5. CLI Adapter 扩展点 — AgentRuntime 动态挂载 MCP server

### 5.1 核心问题

P2 阶段要让 AgentRuntime（CLI 子进程）**动态知道**自己该挂载哪些 MCP server，且要支持：
1. **每个 Agent 独立 bindings**（不能全局共享）
2. **override 生效**（用户在 binding 上填的 key/env 覆盖模板默认）
3. **长驻进程 sp 变化要重 spawn** — 同样地，**mcp config 变化也要重 spawn**
4. **不能影响现有流式协议**（继续走 `StreamEvent`）

### 5.2 4 个 Runtime 的扩展点（按改造量从少到多）

#### Claude Code (优先级最高，CLI 优先)

**扩展位置**：`src/backend/app/infrastructure/llm/claude_code_runtime.py`

```python
class ClaudeCodeRuntime(AgentRuntime):
    def __init__(
        self,
        *,
        model: str = "",
        agent_id: str = "",
        proxy_base: str = "",
        permission_mode: str = _DEFAULT_PERMISSION_MODE,
        max_turns: int = _DEFAULT_MAX_TURNS,
        timeout: int = _DEFAULT_TIMEOUT,
        # ↓ 新增
        mcp_config_path: str | None = None,   # 动态生成的 ~/.claude/mcp-{agent_id}.json
    ):
        ...
        self._mcp_config_path = mcp_config_path

    def _build_cmd(self, request, session_key, *, resume):
        cmd = [...]
        if resume:
            cmd.extend(["--resume", session_key])
        else:
            cmd.extend(["--session-id", session_key])
        if request.system_prompt:
            cmd.extend(["--system-prompt", request.system_prompt])
        # ↓ 新增（Claude Code 1.x 通过 --mcp-config 加载）
        if self._mcp_config_path:
            cmd.extend(["--mcp-config", self._mcp_config_path])
        return cmd
```

**关键决策**：
- **每个 agent 一个 mcp config 文件**（`~/.claude/mcp-{agent_id}.json`）而不是全局
- 文件在 `factory.py` 构造 runtime 时**预先写盘**（基于该 agent 的 bindings + overrides）
- **长驻进程的 sp 守卫**已经在 `claude_code_runtime.py:199-208` 实现，需要**同步加 mcp config 守卫**：mcp config 变了就 drop + 重 spawn

**`factory.py` 调用点**（line 87-98）：
```python
if system == AgentSystem.CLAUDE_CODE:
    if not _cli_installed(system):
        return _build_api_fallback(agent)

    from app.infrastructure.llm.claude_code_runtime import ClaudeCodeRuntime
    from app.infrastructure.mcp.config_writer import write_mcp_config_for_agent  # 新增

    # ↓ 新增：动态写 mcp config
    mcp_config_path = await write_mcp_config_for_agent(agent.id, settings.workspace_dir)

    return ClaudeCodeRuntime(
        model=agent.model,
        agent_id=str(agent.id),
        proxy_base=settings.proxy_base_url,
        permission_mode=s.get("permission_mode", "acceptEdits"),
        max_turns=s.get("max_turns", 10),
        timeout=s.get("cli_timeout", settings.claude_cli_timeout),
        mcp_config_path=mcp_config_path,   # 新增
    )
```

#### OpenCode (次高，含 mcp/acp 字样)

**扩展位置**：`src/backend/app/infrastructure/llm/opencode_runtime.py`

OpenCode 本身已支持 mcp（描述里就写了），只需在 `_write_provider_config` 旁加 `_write_mcp_config`：

```python
def _write_mcp_config(agent_id: str, bindings: list[dict]) -> str:
    """动态写 ~/.config/opencode/mcp-{agent_id}.json"""
    config_path = Path.home() / ".config" / "opencode" / f"mcp-{agent_id}.json"
    config_path.write_text(json.dumps({"mcp": bindings}, ensure_ascii=False), encoding="utf-8")
    return str(config_path)
```

在 `_build_cmd` 加 `--mcp-config <path>`（OpenCode v1.15+ 支持，需验证）。

#### Pi Agent

`src/backend/app/infrastructure/llm/pi_agent_runtime.py` 通过 extension 机制注册 MCP，需研究 Pi 的 extension API（已记入 P2 风险）。

#### Codex (未实现)

未来扩展，按 OpenCode 模式写。

### 5.3 长驻进程的 MCP 守卫（与 sp 守卫对称）

**当前** `claude_code_runtime.py:199-208` `_acquire_with_sp_guard`：
```python
async def _acquire_with_sp_guard(pool, session_key, sp):
    spawn = partial(self._spawn_long, sp, session_key)
    handle = await pool.acquire(session_key, spawn)
    if handle.spawn_system_prompt and handle.spawn_system_prompt != sp:
        await pool.drop(session_key)
        handle = await pool.acquire(session_key, spawn)
    handle.spawn_system_prompt = sp
    return handle
```

**改造为** `_acquire_with_guards(pool, session_key, sp, mcp_config_path, mcp_config_hash)`：
- 计算 mcp_config 文件 hash（避免长字符串比较）
- sp 或 mcp_config 任何一个变了 → drop + 重 spawn
- handle 同时记录 `spawn_mcp_hash`

### 5.4 tools/list 缓存与 tool_call 拦截

**当前**：CLI 自己在内部完成 tool_call → tool_result 循环，AgentHub 透传。
**MCP 接入后**：
- CLI 启动时通过 mcp config 加载 server，server 在 CLI 内部被调用
- AgentHub **仍然只透传** tool_use / tool_result 事件
- 但 `ToolCall` 数据结构要扩展（加 `server_name` 字段，详见 §2.3）
- P4 阶段前端才能展示"该工具来自 XXX MCP"

### 5.5 LLMAdapter (ClaudeAdapter) 路径

MCP 主要面向 CLI Runtime。LLMAdapter (API) 模式下：
- 当前 `_build_tool_definitions` 是 TODO(M3)，未实现
- MCP 接入后，理论上可以走 API 模式 + MCP server 调工具（"function calling + MCP client"双链路）
- 但**优先级最低**：CLI 优先架构下，API 模式用户越来越少
- 建议 P4 之后做，不在 P2 范围

---

## 6. 现有数据模型 / API / 工具调用链

### 6.1 现有数据模型（6 张表 + workspace_path 字段）

| 表 | 主要字段 | 关系 | 关注点 |
|------|------|------|------|
| `agents` | id, name, agent_system, provider, model, api_key_encrypted, system_prompt, **capability_tags**, **skills**, settings, is_system | 1:N → sessions, tasks | **缺 mcp_bindings 关联** |
| `sessions` | id, type, group_id, agent_id, **workspace_path**, long_term_context | N:1 → group, agent | **workspace_path 是 MCP installation 的天然归属** |
| `messages` | id, session_id, role, content, content_type, **metadata**, mentions | 1:N | metadata 预留，可存 tool_call JSON |
| `tasks` | id, title, status, assignee_id, parent_task_id, session_id, budget_max_* | N:1 → agent, parent | budget_max_steps=10（红线） |
| `task_events` | id, task_id, event_type, event_data, actor | N:1 → task | 事件溯源 |
| `notifications` | id, user_id, category, title, is_read, action_url | 1:N | 现有审批已用，可作 MCP 失败通知 |
| `groups` | id, name, coordinator_id, coordinator_config | 1:N → members | — |
| `group_members` | group_id, agent_id, joined_at | N:N | — |

**关键发现**：`sessions.workspace_path` 已经存在（migration 0005），是 MCP installation 归属的天然位置。

### 6.2 现有 API 路由（8 个 prefix）

```
GET/POST/PATCH/DELETE  /api/agents            [router/agents.py]
GET/POST/PATCH/DELETE  /api/groups            [router/groups.py]
GET/POST               /api/sessions          [router/sessions.py]
GET/POST/PATCH         /api/tasks             [router/tasks.py]
GET/PATCH              /api/inbox             [router/inbox.py]
GET/POST               /api/providers/...     [router/providers.py, ping/scanner]
GET/*                  /proxy/agents/{id}/... [router/proxy.py, CLI 透传]
GET/POST               /api/skills/...        [router/skills.py, market+library]
WS                     /ws/sessions/{id}      [ws/chat.py + ws/runner.py]
```

**最可参考**：`/api/skills` (marketplace + install 完整流程)，但**数据模型不同**（skill = 文件，MCP = 进程）。

### 6.3 现有 Schema 模式

- Pydantic v2 BaseModel（`app/schemas/agent.py` 等）
- Create/Update/Out 三段式
- 字段 `Field(min_length=, max_length=)` 校验
- `api_key: str | None = Field(repr=False)` 防止日志泄露
- 路由用 `response_model=...` + `status_code=201` for create

### 6.4 工具调用链完整路径（5 层）

```
[用户] → 浏览器
  ↓ ChatView 输入消息
  ↓ useWebSocket.send({type: "message:send", payload: {content, mentions, ...}})
L5: React → WebSocket
  ↓
L4: ws/chat.py 接收
  ↓ SendMessageCommand
L3: ChatService.send_and_stream(cmd)  [app/application/services/chat_service.py:96]
  ↓ 1. 持久化 user message
  ↓ 2. 写 L1 滑动窗口
  ↓ 3. dispatch_mode 路由
  ↓ 4. _stream_one_agent(session, group, target, trigger)  [chat_service.py:190]
  ↓ 5. ContextBuilder.build_for_agent → AgentRequest  [context_builder.py:54]
  ↓ 6. adapter = build_adapter_for_agent(target)         [infrastructure/llm/factory.py:59]
  ↓ 7. async for raw_event in adapter.stream(request):
  ↓    ↑↑↑ 这里面跑 CLI/Anthropic SDK，CLI 内部完成 tool_call → tool_result 循环
  ↓    ↑↑↑ AgentHub 仅透传 StreamEvent
  ↓ 8. ChatService 落库 + 写 L1 + 推 watermark + 发 StreamingCompleted
  ↓
L4: WebSocket Push  [ws/chat.py 通过 connection_manager 广播]
  ↓
L5: useWebSocket 收到 {type:"message:stream", payload: {message_id, content, seq}}
  ↓ MessageBubble 渲染
```

**MCP 接入后需要修改的环节**：
- **L3 step 6**：`build_adapter_for_agent(target)` → 注入 `mcp_config_path`
- **L1 runtime 内部**：spawn CLI 时加 `--mcp-config`
- **L1 adapter 内部**：CLI 内部的 MCP 工具调用已发生，AgentHub 透传
- **L1 protocol 扩展**：`ToolCall` 加 `server_name` 字段
- **L4 step 7**：WS push 时把 `server_name` 也带上
- **L5 MessageBubble**：识别 `server_name` 渲染内联卡片

### 6.5 关键约束（已有，套用即可）

| 约束 | 来源 | MCP 接入需注意 |
|------|------|------|
| AR-01 5 层洋葱 | `01-architecture_架构设计规范.md` | McpServer/McpInstallation/McpBinding 必须按 L1-L5 落地 |
| AR-02 新 Agent 只加 Adapter | 同上 | MCP **不**是新 Agent 系统，是 CLI 的扩展能力 |
| AR-05 FSM 事件溯源 | 同上 | McpInstallation 状态机要 events 化 |
| AR-06 system-model 解耦 | 同上 | domain 实体不引入 ORM/HTTP 概念 |
| AP-04 Pydantic | `04-api_API设计规范.md` | 请求/响应 schema 必须 Pydantic v2 |
| T-05 Adapter & FSM 必测 | `05-testing_测试规范.md` | McpProcessManager 必须单测覆盖 |
| D-12 hooks 已安装 | `06-documentation_文档规范.md` | 新建 migration / spec 必须过 pre-commit |

---

## 7. 建议新增/修改的文件清单

> 按 `MCP功能计划_v0.md` P1→P3→P2→P4 顺序列出。**斜体** = 不在 P1 必做范围。
> 标记规约：[NEW]=新建 / [MOD]=修改 / [DOC]=纯文档

### 7.1 P1 阶段（F1 MCP 市场，6/2-6/5，3-4 天）— 4 个轨道

**轨道 1 — 数据层**：
- [NEW] `src/backend/alembic/versions/0006_create_mcp_servers.py` — `mcp_servers` 表 migration
- [NEW] `src/backend/alembic/versions/0006_create_mcp_installations.py` — `workspace_mcp_installations` 表
- [NEW] `src/backend/alembic/versions/0006_create_mcp_bindings.py` — `agent_mcp_bindings` 表
- [NEW] `src/backend/app/infrastructure/db/models.py` 添加 `McpServerModel` / `McpInstallationModel` / `McpBindingModel` (在 models.py 追加，不要新建文件)
- [NEW] `src/backend/app/domain/enums.py` 追加 `McpTransportType` / `McpServerStatus` / `McpInstallationStatus`
- [NEW] `src/backend/app/domain/entities/mcp_server.py`
- [NEW] `src/backend/app/domain/entities/mcp_installation.py`
- [NEW] `src/backend/app/domain/entities/mcp_binding.py`
- [NEW] `src/backend/app/domain/repositories/mcp_server_repository.py` (接口)
- [NEW] `src/backend/app/domain/repositories/mcp_installation_repository.py`
- [NEW] `src/backend/app/domain/repositories/mcp_binding_repository.py`
- [NEW] `src/backend/app/infrastructure/repositories/mcp_server_repository.py` (SQLAlchemy 实现)
- [NEW] `src/backend/app/infrastructure/repositories/mcp_installation_repository.py`
- [NEW] `src/backend/app/infrastructure/repositories/mcp_binding_repository.py`
- [NEW] `src/backend/app/schemas/mcp.py` (Pydantic 请求/响应)

**轨道 2 — API 层**：
- [NEW] `src/backend/app/api/routers/mcp.py` — 市场/搜索/详情/安装/启停 endpoint
- [NEW] `src/backend/app/api/routers/agent_mcp.py` — Agent 绑定/解绑 endpoint
- [MOD] `src/backend/app/api/routers/__init__.py` — 导出 mcp / agent_mcp
- [NEW] `src/backend/app/application/commands/mcp_commands.py` — CreateMcpServerCmd / InstallMcpServerCmd / BindMcpCmd
- [NEW] `src/backend/app/application/services/mcp_market_service.py`
- [NEW] `src/backend/app/application/services/mcp_installation_service.py`
- [NEW] `src/backend/app/application/services/mcp_binding_service.py`

**轨道 3 — UI 层**：
- [NEW] `src/frontend/src/api/mcp.ts` — REST 客户端
- [NEW] `src/frontend/src/stores/mcpStore.ts` — Zustand store
- [NEW] `src/frontend/src/components/mcp/McpMarketPage.tsx` — 列表/搜索
- [NEW] `src/frontend/src/components/mcp/McpDetailPage.tsx` — 详情/安装
- [NEW] `src/frontend/src/components/mcp/McpInstallButton.tsx`
- [MOD] `src/frontend/src/App.tsx` — 路由注册 `/mcp-market` / `/mcp-market/:id`
- [MOD] `src/frontend/src/components/layout/LeftPanel.tsx` — 导航入口

**轨道 4 — 基础设施**：
- [NEW] `src/backend/app/infrastructure/mcp/__init__.py`
- [NEW] `src/backend/app/infrastructure/mcp/process_manager.py` — McpProcessPool（参考 `claude_code_process_pool.py`）
- [NEW] `src/backend/app/infrastructure/mcp/mcp_client.py` — JSON-RPC 2.0 client（stdio + SSE 双协议）
- [NEW] `src/backend/app/infrastructure/mcp/mcp_registry.py` — manifest 缓存 + 工具发现
- [NEW] `src/backend/app/infrastructure/mcp/manifest_validator.py` — JSON Schema 校验
- [MOD] `src/backend/app/main.py` — FastAPI lifespan 注册 `mcp_pool.shutdown()`
- [MOD] `src/backend/app/core/config.py` — 添加 `mcp_pool_soft_max` / `mcp_idle_ttl_seconds` / `mcp_workspace_dir`
- [NEW] `src/backend/requirements.txt` — 添加 `mcp` 或 `jsonschema` 依赖（决策 P1 第 1 天定）
- [NEW] `src/backend/tests/test_mcp_process_manager.py` — 必测（参考 T-05）
- [NEW] `src/backend/tests/test_mcp_client.py` — 必测（mock transport）
- [NEW] `src/backend/tests/test_mcp_registry.py`

**P1 收束**：
- [NEW] `worklogs/decisions/0002-mcp-market-design.md` (ADR)
- [NEW] `docs/reports/2026-06-05_P1_F1收束报告.md`
- [MOD] `docs/plan/MCP功能计划_v0.md` — 标记 P1 收束

### 7.2 P3 阶段（F3 创建 MCP，6/6-6/8，3 天）

- [MOD] `src/backend/app/infrastructure/db/models.py` — `McpServerModel` 添加 `user_submitted` / `template_id` / `raw_config` 字段
- [MOD] `src/backend/alembic/versions/0007_add_user_submitted_to_mcp_servers.py`
- [NEW] `src/backend/app/api/routers/mcp.py` 追加 `POST /api/mcp/servers` + `POST /api/mcp/servers/{id}/validate`
- [NEW] `src/frontend/src/components/mcp/McpCreatePage.tsx` — 提交表单
- [NEW] `src/frontend/src/components/mcp/McpTemplatePicker.tsx` — 内置模板（filesystem / github / postgres / brave-search / fetch）
- [NEW] `src/frontend/src/data/mcpTemplates.ts` — 5 个模板定义
- [NEW] `src/backend/app/infrastructure/mcp/template_loader.py` — 内置模板加载
- [NEW] `src/backend/tests/test_mcp_create.py` — dry-run 沙箱测试
- [NEW] `worklogs/decisions/0004-mcp-create-design.md`
- [NEW] `docs/reports/2026-06-08_P3_F3收束报告.md`

### 7.3 P2 阶段（F2 Agent 接入 MCP，6/9-6/11，3 天）— 关键扩展点

**CLI Adapter 动态挂载**：
- [MOD] `src/backend/app/infrastructure/llm/claude_code_runtime.py` — `__init__` 增 `mcp_config_path`；`_build_cmd` / `_spawn_long` 加 `--mcp-config`；`_acquire_with_sp_guard` → `_acquire_with_guards` 加 mcp_hash 守卫
- [MOD] `src/backend/app/infrastructure/llm/claude_code_process_pool.py` — `ProcessHandle` 增 `spawn_mcp_hash` 字段
- [MOD] `src/backend/app/infrastructure/llm/opencode_runtime.py` — 加 `_write_mcp_config` + `--mcp-config`
- [MOD] `src/backend/app/infrastructure/llm/pi_agent_runtime.py` — extension 注册 MCP（视 Pi API 复杂度决定）
- [MOD] `src/backend/app/infrastructure/llm/factory.py` — 4 个 runtime 构造都注入 `mcp_config_path`

**配置写入**：
- [NEW] `src/backend/app/infrastructure/mcp/config_writer.py` — `write_mcp_config_for_agent(agent_id, workspace_dir)` → 写 `~/.claude/mcp-{agent_id}.json` / `~/.config/opencode/mcp-{agent_id}.json`
- [NEW] `src/backend/tests/test_mcp_config_writer.py`

**协议扩展**：
- [MOD] `src/backend/app/domain/llm/protocol.py` — `ToolCall` 增 `server_name: str | None` / `server_id: UUID | None`；`AgentRequest` 增 `mcp_bindings: list[UUID]` / `mcp_config_path: str | None`
- [MOD] 4 个 runtime 的 `_parse_line` / `_parse_message_update` — 解析时填 `server_name`（前提 CLI stdout 包含 server 信息，否则暂时留 None）
- [MOD] `src/backend/app/domain/llm/protocol.py` — 可选 `StreamEventType.MCP_TOOL_CALL`（若要严格区分内置/MCP 工具）

**Agent 配置 UI**：
- [MOD] `src/frontend/src/components/agent/AgentDetailPage.tsx` — 新 Tab "MCP 接入"
- [NEW] `src/frontend/src/components/agent/McpBindingTab.tsx` — 列出已绑/绑定/解绑
- [NEW] `src/frontend/src/components/agent/McpBindingPicker.tsx` — 选 server 弹窗
- [MOD] `src/frontend/src/api/agents.ts` — 增 `getAgentMcpBindings` / `bindMcp` / `unbindMcp`

**P2 收束**：
- [NEW] `worklogs/decisions/0003-mcp-binding-design.md`（最关键，CLI 扩展架构决策）
- [NEW] `docs/reports/2026-06-11_P2_F2收束报告.md`

### 7.4 P4 阶段（F5 工具调用展示，6/12-6/15，2-3 天）

- [MOD] `src/backend/app/domain/llm/protocol.py` — `ToolCall` 字段最终确认（可能加 `status: "pending" | "running" | "done"`）
- [MOD] `src/backend/app/api/ws/chat.py` — WS push 协议加 `tool_call` / `tool_result` 事件（MVP 注释的代码启用）
- [MOD] `src/frontend/src/stores/chatStore.ts` — 取消注释 `tool_*` 事件处理
- [MOD] `src/frontend/src/stores/groupStore.ts` — 取消注释 `tool_*` 事件处理
- [NEW] `src/frontend/src/components/chat/ToolCallCard.tsx` — 折叠/展开/复制/状态
- [NEW] `src/frontend/src/components/chat/ToolResultCard.tsx`
- [MOD] `src/frontend/src/components/chat/MessageBubble.tsx` — 嵌入 ToolCallCard
- [MOD] `src/frontend/src/components/group/GroupMessageItem.tsx` — 群聊版
- [NEW] `src/backend/app/domain/events/tool_call_log.py` — 工具调用日志持久化（task_events 复用 vs 独立表，决策 P4 第 1 天）
- [NEW] `worklogs/decisions/0005-mcp-tool-display-design.md`
- [NEW] `docs/reports/2026-06-15_P4_F5收束报告.md`

### 7.5 文档同步（横切，每个 P 阶段都要做）

- [MOD] `docs/specs/01-architecture_架构定义.md` — 加 MCP 层（§2.1 双轨架构 + §3 数据流补 McpProcessManager）
- [MOD] `docs/specs/03-data-model_数据模型.md` — 加 3 张表（§2.13/14/15）
- [MOD] `docs/specs/04-commands_命令接口.md` — 加 `/api/mcp/*` + `/api/agents/{id}/mcp/*`（§2.6/2.7）
- [MOD] `docs/specs/04b-adapter-cli-flow_适配器CLI流程分析.md` — §一骨架图加 mcp_config 注入；§二场景一加 `--mcp-config` 演示
- [NEW] `docs/specs/04d-mcp-protocol_MCP协议规范.md` — 整体 MCP 协议、JSON-RPC、stdio/SSE、工具调用流程（新建）
- [MOD] `docs/plan/开发清单_roadmap.md` — 4 阶段任务条目 + 验收状态
- [MOD] 根 `STATUS.md` — 各阶段 in_progress / done 状态

### 7.6 建议优先顺序（基于依赖 + 风险）

```
1.  P1 数据层（3 张表）    ← 0 依赖，最先做
2.  P1 协议/Manifest 验证  ← 数据层就绪
3.  P1 ProcessManager      ← 参考 claude_code_process_pool
4.  P1 API + 基础 UI       ← 依赖 1-3
5.  P3 创建 + 模板         ← P1 收束后做（不依赖 P1 UI，但共享后端）
6.  P2 CLI Adapter 扩展    ← P1 + P3 收束后（最复杂，claude_code 改动需 review）
7.  P4 工具展示            ← P2 收束后（最后做）
```

**关键风险**（在 99-boundaries 中已识别）：
- CLI 子进程的 mcp config 路径要兼容 4 个 Runtime（差异大）
- Pi Agent 的 extension 机制文档可能不完整
- Claude Code 长驻进程的 mcp config 变化触发重 spawn（需测试并发场景）
- P2 阶段最容易超出 3 天预算，建议**单跑 ClaudeCodeRuntime**（其他 3 个推到 P5）

### 7.7 不要在本次任务范围内做的事

- ❌ 自研 JSON-RPC 2.0 client（用官方 `mcp` Python SDK 即可）
- ❌ 重构现有 `claude_code_process_pool`（不必要）
- ❌ API 模式 (ClaudeAdapter) 接入 MCP（CLI 优先不在范围）
- ❌ 修改 ToolRegistry 占位（`_build_tool_definitions` 的 TODO(M3)，不在 P1-P4 范围）
- ❌ 全文重构 `claude_code_runtime._parse_line`（P4 时再优化）

---

## 8. 风险与待确认项

| 风险 | 等级 | 建议 |
|------|------|------|
| MCP Python SDK 在 6/2 时是否稳定 | 🟡 | 启动时先 `pip install mcp` 验证，必要时回退自实现 stdio JSON-RPC |
| Claude Code `--mcp-config` flag 是否 1.x 支持 | 🟡 | 6/2 第 1 天确认（看 `claude --help`），不支持则写 `~/.claude/mcp.json` 全局 |
| OpenCode `--mcp-config` flag 存在性 | 🟡 | 同上 |
| Pi Agent extension API 文档完整性 | 🟠 | 推迟到 P2 中段；优先做 ClaudeCodeRuntime + OpenCodeRuntime |
| 长驻进程 mcp config 变化触发重 spawn 的并发 | 🟡 | 压测 50 并发，重点测 group chat 多 Agent 同时 reload mcp config 场景 |
| ToolCall.server_name 是否能从 CLI stdout 提取 | 🔴 高 | Anthropic/Claude/OpenCode/Pi 的 tool_use 块**不一定**带 server 来源；可能需要 CLI 端 wrapper |
| P2 阶段 mcp config 写入并发 | 🟡 | 写 `mcp-{agent_id}.json` 不会冲突，但要避免读到半写状态（atomic rename） |

---

## 9. 与其他 agent 的协作

| 协作点 | 对接 agent | 时机 |
|------|------|------|
| 3 张表 migration 与现有 6 表一致性 | mcp-developer | P1 数据层启动时 |
| API 端点契约冻结 | mcp-pm（PRD）→ mcp-architect（API 冻结）| P1 第 1 天 |
| 长驻进程 mcp guard 与 sp guard 复用 | mcp-architect（已有 sp 守卫经验）| P2 |
| ToolCall 协议扩展 | mcp-architect（protocol.py 冻结）| P2 启动时 |
| 进程沙箱（避免 MCP server 滥用资源）| mcp-security-auditor | P1 + P3 收束时 |

---

## 10. 写文档位置说明

本文档的归属：**Plan A 第 3 块（系统分析师）**输出，不属于 P1-P4 实施阶段的交付物。
- 路径：`docs/research/AgentHub_MCP接入点现状.md`（按 `MCP功能计划_v0.md` §四 Plan A 设计）
- 用途：P1 启动前的"地形图"，让 mcp-architect / mcp-developer / mcp-pm 对齐现状
- 后续：P1 收束后可归档到 `docs/archive/` 或作为 ADR 附录

---

**写于**: 2026-06-02 by mcp-system-analyst  
**依据**:
- `docs/plan/MCP功能计划_v0.md` v0.2
- `docs/explore/EXP-08_PageIndex技术影响分析.md`
- `docs/explore/EXP-04_关键指标数据.md` §四
- `docs/specs/01-architecture_架构定义.md` v2.2
- `docs/specs/01b-architecture-design_分层与数据流.md` v1.1
- `docs/specs/03-data-model_数据模型.md` v2.0
- `docs/specs/04-commands_命令接口.md` v2.1
- `docs/specs/04b-adapter-cli-flow_适配器CLI流程分析.md` v1.5
- `docs/conventions/09-boundaries_边界矩阵.md` v2.1
- 5 层洋葱代码实勘（src/backend/app/ 全树）
