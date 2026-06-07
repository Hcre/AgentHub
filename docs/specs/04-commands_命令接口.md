# AgentHub 命令接口

> 版本: v2.2 | 基于 PRD v4.0 + 架构设计 v1.0 | 2026-06-07
> v2.1: 环境变量摘除 Celery/LiteLLM，新增 CLI 相关配置
> v2.2: 新增 §六 BDD 验收场景（Given/When/Then），覆盖 PRD 6 大核心功能 + roadmap §8 P0-4/P1-2/P1-3 + 11 项 P2 缺口

---

## 一、环境变量

```bash
# 必需
AGENTHUB_SECRET_KEY=<随机64字符>         # JWT 签名密钥
AGENTHUB_ENCRYPTION_KEY=<Fernet密钥>     # API Key 加密密钥
AGENTHUB_ENV=development

# 数据库
DATABASE_URL=postgresql://agenthub:password@localhost:5432/agenthub
REDIS_URL=redis://localhost:6379/0

# LLM 适配器
LLM_ADAPTER_MODE=mock|anthropic_api|claude_code
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_MODEL=claude-sonnet-4-20250514

# CLI 模式
CLAUDE_CLI_TIMEOUT=300
AGENT_WORKSPACE_DIR=.agenthub/workspaces
CLAUDE_ALLOWED_TOOLS=Read,Write,Edit,Grep,Glob

# 可选
AGENTHUB_PORT=8000
AGENTHUB_LOG_LEVEL=INFO
MAX_TOKENS=16000
MAX_TOOL_TURNS=10
```

---

## 二、REST API

### 基础约定

```
Base URL:  http://localhost:8000/api
Content-Type: application/json
Authorization: Bearer <jwt_token>
错误响应:  { "error": { "code": "...", "message": "..." } }
```

### 2.0 全局设置 API

```
GET    /api/settings
  returns: {
    "coordinator": {
      "intent_model": {           # 意图检测模型 (快速分类, 消息级调用)
        "provider": "deepseek",
        "model": "deepseek-chat",
        "api_key_encrypted": "...",
        "base_url": null
      },
      "decompose_model": {        # 任务分解模型 (复杂推理, 触发时调用)
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "api_key_encrypted": "...",
        "base_url": null
      }
    },
    "defaults": {
      "agent_system": "claude",   # 创建 Agent 时默认选中
      "daily_token_budget": 1000000
    },
    "approval_mode": "normal"     # "normal" | "execute"
  }

PATCH  /api/settings
  body: { "coordinator"?: { "intent_model"?: {...}, "decompose_model"?: {...} },
          "defaults"?: { "agent_system"?: "claude"|"codex"|"trae",
                         "daily_token_budget"?: int },
          "approval_mode"?: "normal" | "execute" }
  # 修改 approval_mode 时:
  #   → 不影响已运行的 Agent 会话
  #   → 新启动的 Agent 使用新模式
```

### 2.1 Agent API

```
POST   /api/agents
  body: {
    "agent_system": "claude" | "codex" | "trae",
    "name": "FrontendAgent",
    "avatar": "https://...",
    "role": "前端开发专家",
    "provider": "deepseek",
    "model": "deepseek-chat",
    "api_key": "sk-...",
    "base_url": "https://api.deepseek.com",     // 可选
    "skills": ["react", "typescript"],
    "system_prompt": "你是前端专家...",           // 可选
    "capability_tags": ["react", "css", "ui"]    // 可选
  }
  returns: 201 { id, name, agent_system, provider, model, status, created_at }

POST   /api/agents/draft
  # 对话式创建：用自然语言描述 Agent → 返回 system_prompt 草案 + 推荐标签
  body: { "description": "专攻 Python 数据分析的 Agent，擅长 pandas 和 matplotlib" }
  returns: 200 { "system_prompt_draft": "...", "capability_tags": ["python", "pandas", "matplotlib"] }

GET    /api/agents
  query: ?agent_system=claude&status=online&capability=react
  returns: { "items": [...], "total": int }

GET    /api/agents/{id}
  returns: 完整 Agent 信息 (含 channels, tasks, capability_tags, settings, memory_config)

PATCH  /api/agents/{id}
  body: { "name"?, "role"?, "provider"?, "model"?, "api_key"?, "base_url"?,
          "skills"?, "capability_tags"?, "system_prompt"?, "settings"? }
  returns: 200 更新后的 Agent

DELETE /api/agents/{id}
  returns: 204  (软删除，从群组中移除)

GET    /api/agents/{id}/tasks     ?status=running&page=1
GET    /api/agents/{id}/activities ?page=1
GET    /api/agents/{id}/memory
PATCH  /api/agents/{id}/memory
GET    /api/agents/{id}/channels
```

### 2.2 Group API

```
POST   /api/groups
  body: { "name": "前端开发组", "description"?: "", "member_ids"?: [uuid...] }
  returns: 201 { id, name, coordinator: {id, name}, members: [...] }
  说明: 自动创建协调者 Agent (is_system=true, agent_system=coordinator)

GET    /api/groups
GET    /api/groups/{id}           # 含 members 列表 + coordinator 信息
PATCH  /api/groups/{id}           # { name?, description? }
DELETE /api/groups/{id}           # 级联删除协调者

POST   /api/groups/{id}/members   # { "agent_id": uuid }
DELETE /api/groups/{id}/members/{agent_id}
```

### 2.3 Session & Message API

```
POST   /api/sessions
  body: { "type": "group"|"private", "group_id"?: uuid, "agent_id"?: uuid, "title"?: "" }

GET    /api/sessions
GET    /api/sessions/{id}
GET    /api/sessions/{id}/messages  ?before=uuid&limit=50
GET    /api/sessions/{id}/history   ← 读取 CLI transcript.jsonl 完整回放（含 tool_call/thinking）

POST   /api/sessions/{id}/messages
  body: { "content": "...", "mentions": ["AgentName"], "dispatch_mode": "auto"|"direct",
          "reply_to"?: uuid, "content_type"?: "text" }

POST   /api/messages/{id}/pin
DELETE /api/messages/{id}/pin
```

### 2.4 Task API

```
POST   /api/tasks
  body: { "title": "...", "description"?: "", "assignee_id"?: uuid, "assignee_type"?: "agent"|"group",
          "due_date"?: iso, "priority"?: "medium", "tags"?: [], "parent_task_id"?: uuid }

GET    /api/tasks
  query: ?status=running,pending&priority=high&assignee_id=uuid&tags=frontend
         &due_before=2026-06-30&due_after=2026-05-01
         &sort_by=due_date&sort_order=asc&page=1&page_size=20

GET    /api/tasks/{id}            # 含子任务 + DAG 依赖
PATCH  /api/tasks/{id}            # { status?, priority?, assignee_id?, due_date?, tags? }
GET    /api/tasks/{id}/events
GET    /api/tasks/{id}/artifacts
```

### 2.5 Inbox & Approval API

```
GET    /api/inbox                  ?category=all|approval|task&is_read=false&page=1
GET    /api/inbox/unread-count     → { "total": 5, "by_category": {"approval": 3, "task": 2} }
PATCH  /api/inbox/read             → { "notification_ids": [uuid...] }

POST   /api/approvals/{task_id}/approve
POST   /api/approvals/{task_id}/reject
POST   /api/approvals/{task_id}/edit     # { "payload": {"edits": {...}} }
POST   /api/approvals/{task_id}/respond  # { "payload": {"response": "更多信息..."} }

GET    /api/inbox/calendar         ?from=2026-05-01&to=2026-06-30
```

### 2.6 MCP API 〔🔒 PR-01 冻结草案 · 2026-06-03 · 待 2 人 Review〕

> 单一权威需求：`docs/plan/后续升级计划/MCP接入/README-REVISION.md`；契约来源：`06-详细设计/IC-MCP-V1.0-20260602.md`。
> **冻结时校正的口径漂移**（与全库现状对齐）：
> ① URL 前缀 `/api/v1/mcp/...` → **`/api/mcp/...`**（全库无 `/v1/` 段，对齐 `/api/agents`）。
> ② WS 事件 `{"event":...}` 扁平格式 → **`{"type":"...","payload":{...}}`** 信封（对齐 `message:stream`），并按 AP-07 带 `request_id`。
> ③ 错误格式统一 `{ "error": { "code": "E_MCP_*", "message": "..." } }`（AP-02）。

```
# —— 市场类（3）——
GET    /api/mcp/market
  query: workspace_id(必填) & q? & tag? & transport?(stdio|sse|streamable_http)
         & official_only?(bool) & page=1 & page_size=20(max 100)
  returns: { "items":[{ "mcp_id","name","slug","description","transport",
                        "version","tags":[],"official":bool,"install_count":int }],
             "total":int, "page":int, "page_size":int }
  errors: 401 E_MCP_UNAUTHORIZED / 403 E_MCP_PERMISSION_DENIED / 422

GET    /api/mcp/market/{mcp_id}
  returns: { "mcp_id","name","slug","description","transport","config_schema":{},
             "version","tags":[],"created_by","created_at","updated_at","dry_run_result":{}|null }
  errors: 401 / 404 E_MCP_NOT_FOUND

GET    /api/mcp/market/templates
  query: workspace_id(必填)
  returns: { "templates":[{ "template_id","name","mcp_config":{}, ... }] }   # 本期官方 5 模板
  errors: 401 / 403

# —— 安装类（2）——
POST   /api/mcp/installations
  body: { "workspace_id","mcp_id","instance_name", "config_overrides":{} }
  returns 201: { "installation_id","status":"installing"|"ready","mcp_id",
                 "instance_name","created_at" }
  幂等: 同 workspace_id+mcp_id+args_hash 重复调用 → 返回同一 installation_id（F-004 验收③）
  errors: 400 / 401 / 403 / 404 / 409 E_MCP_NAME_CONFLICT / 422 / 500 E_MCP_INSTALL_TIMEOUT
          | E_MCP_INSTALL_DEPENDENCY_MISSING | E_MCP_INSTALL_PERMISSION_DENIED(403)

DELETE /api/mcp/installations/{installation_id}
  query: workspace_id(必填, 鉴权)
  returns 204
  errors: 401 / 403 / 404 E_MCP_NOT_FOUND / 409（仍有 active binding，需先解绑） / 500

# —— 绑定类（2）——
POST   /api/mcp/bindings
  body: { "agent_id","installation_id", "tool_subset":["read_file",...]? }   # 省略=全选
  returns 201: { "binding_id","agent_id","installation_id","tool_subset":[],
                 "status":"active","created_at" }
  副作用: 无运行时有状态 attach（P2/ADR-05 请求携带）——下次该 agent 的 stream 由
          ContextBuilder 经 McpBindingService.build_request_mcp_servers 解析 active 绑定
          → AgentRequest.mcp_servers → Runtime 写 .mcp.json 注入
  errors: 400 / 401 / 403 / 404 / 409 E_MCP_BINDING_CONFLICT / 500

DELETE /api/mcp/bindings/{binding_id}
  returns 204
  副作用: 经既有 WS 通道更新路由表（≤5s，F-011）
  errors: 401 / 403 / 404 E_MCP_NOT_FOUND / 500

# —— 创建类（1）——
POST   /api/mcp/servers
  body: { "name","slug"(^[a-z0-9-]+$),"description"?,"transport"(stdio|sse|streamable_http),
          "config_json":{},"version"(≤50),"tags":[]?, "template_id"?:uuid|null, "dry_run":true }
  returns 201: { "mcp_id","status":"draft","dry_run_result":{} }
  干跑(dry_run=true): 单 Docker 容器 + compose 限额（30s 超时·CPU=1·Mem=512MB·net=none）
  errors: 400 / 401 / 403 / 409 E_MCP_SLUG_CONFLICT
          / 422 E_MCP_SCHEMA_INVALID | E_MCP_VERSION_TOO_LONG | E_MCP_DRY_RUN_TIMEOUT | E_MCP_DRY_RUN_FAILED / 500
```

**错误码清单（AP-02/03，`E_` 前缀，对齐 chat 端点风格）**

| code | 含义 | HTTP |
|------|------|------|
| `E_MCP_NOT_FOUND` | mcp_id/installation_id/binding_id 不存在 | 404 |
| `E_MCP_NAME_CONFLICT` | 同 workspace instance_name 冲突 | 409 |
| `E_MCP_SLUG_CONFLICT` | 创建 slug 冲突 | 409 |
| `E_MCP_BINDING_CONFLICT` | 重复绑定 | 409 |
| `E_MCP_INSTALL_TIMEOUT` / `_DEPENDENCY_MISSING` | 安装超时 / 依赖缺失 | 500 |
| `E_MCP_INSTALL_PERMISSION_DENIED` / `E_MCP_PERMISSION_DENIED` | 权限不足 | 403 |
| `E_MCP_DRY_RUN_TIMEOUT` / `_FAILED` / `E_MCP_SCHEMA_INVALID` / `E_MCP_VERSION_TOO_LONG` / `E_MCP_BATCH_TOO_LARGE` | 干跑/校验类 | 422 |
| `E_MCP_TOOL_CALL_TIMEOUT` / `_CANCELLED` / `_RUNTIME_ERROR` | 工具调用类 | 500 |
| `E_MCP_UNAUTHORIZED` | 未登录/JWT 失效 | 401 |
| `E_MCP_INTERNAL` | 内部错误 | 500 |

> Pydantic schemas 落 `schemas/mcp.py`（字段见 IC-MCP §3）。
>
> **二次对账修订（2026-06-03，schema↔代码）**——以下三点把契约改为与真实代码一致，已经 Reviewer 确认：
> - **鉴权（R3）**：现库**所有端点零 JWT 强制**（`decode_access_token` 未被任何路由调用）。MCP 写操作**只做 JWT 解析**（新增 `get_current_user` 依赖，取 `sub` 充 `created_by`/`installed_by`），**不做 workspace 成员校验**（无 membership 模型，随全局鉴权一起上，列 P4+ TODO）。`E_MCP_PERMISSION_DENIED(403)` 本期不触发，保留占位。
> - **workspace_id 语义（R1）**：现库无 `workspaces` 实体，workspace=`sessions.workspace_path` 字符串。`workspace_id` 字段**暂存 `session_id`** 作为 workspace 维度 stand-in；**裸 UUID、不加 FK**（前向兼容未来真实 workspaces 表）。
> - **WS 信封（R5，P4 范围）**：既有会话 WS 实为扁平 `{"type","seq","content"}`，**不含 `payload`/`request_id`**。§三 的 `tool_call:*` 事件采用**新** `{type,payload,request_id}` 信封（符合 AP-07），与既有消息**在同通道并存两种信封**；是否统一既有 WS 留 P4 决策。

---

## 三、WebSocket 协议

```
连接: ws://localhost:8000/ws/sessions/{id}
心跳: client→server: {"type":"ping"} / server→client: {"type":"pong"}  间隔30s
```

### 客户端 → 服务端

```json
// 发送消息
{"type":"message:send", "payload":{"content":"...", "mentions":["FrontendAgent"], "dispatch_mode":"auto"}}

// 审批决策
{"type":"approval:decide", "payload":{"task_id":"uuid", "decision":"approve", "payload":{}}}

// 标记已读
{"type":"message:read", "payload":{"message_ids":["uuid..."]}}
```

### 服务端 → 客户端

```json
// 流式输出
{"type":"message:stream", "payload":{"message_id":"uuid", "agent_name":"..", "chunk":"我", "index":0}}
{"type":"message:stream_end", "payload":{"message_id":"uuid", "content_type":"text", "tokens_used":1200}}

// 任务进度
{"type":"task:progress", "payload":{"task_id":"uuid", "state":"running", "step":"generating_code", "progress":0.6}}

// 审批请求
{"type":"approval:required", "payload":{"task_id":"uuid", "agent_name":"..", "reason":"..", "checkpoint":{...}}}

// 收件箱更新
{"type":"inbox:update", "payload":{"unread_count":5, "latest":{...}}}

// Token 消耗
{"type":"token:update", "payload":{"session_tokens":15000, "daily_tokens":250000, "daily_budget":1000000}}

// 〔🔒 PR-01 冻结草案〕MCP 工具调用（F-014，复用既有会话 WS；信封对齐 + request_id 按 AP-07）
{"type":"tool_call:request",  "payload":{"request_id":"uuid","trace_id":"trace-abc","agent_id":"uuid","binding_id":"uuid","tool_name":"read_file","args":{"path":"/data/x.txt"},"ts":"2026-06-03T12:34:56.789Z"}}
{"type":"tool_call:progress", "payload":{"request_id":"uuid","trace_id":"trace-abc","binding_id":"uuid","tool_name":"read_file","progress":60,"message":"...","duration_ms":120}}
{"type":"tool_call:response", "payload":{"request_id":"uuid","trace_id":"trace-abc","binding_id":"uuid","tool_name":"read_file","result":{}, "duration_ms":340}}
{"type":"tool_call:error",    "payload":{"request_id":"uuid","trace_id":"trace-abc","binding_id":"uuid","tool_name":"read_file","error_code":"TIMEOUT|PERMISSION_DENIED|RUNTIME_ERROR","error_message":"...","duration_ms":30000}}
// 取消（F-016，客户端→服务端）：{"type":"tool_call:cancel","payload":{"request_id":"uuid"}} → 后端转 Runtime（≤2s）
// 后端动作：tool_call:request 落 mcp_tool_call_logs(status=pending) 并广播 IM；response/error 更新日志
```

---

## 四、CLI 命令

```bash
# 聊天
agenthub chat                              # 交互式聊天
agenthub chat --agent FrontendAgent        # 指定 Agent 私聊
agenthub send "修复这个 bug"               # 单条消息
git diff | agenthub send --agent Reviewer  # 管道集成

# Agent 管理
agenthub agent create                      # 创建 Agent (交互式: 选系统→配模型→填信息)
agenthub agent list                        # 列出 Agent
agenthub agent list --system claude        # 按系统筛选
agenthub agent info <name>

# 会话
agenthub session list
agenthub session info <id>

# 任务
agenthub task list
agenthub task list --status running --priority high
```

---

## 五、启动命令

```bash
# 首次启动
cp .env.example .env
docker compose up -d postgres redis
make install && make db-migrate

# 开发
make dev
# Backend: http://localhost:8000
# Frontend: http://localhost:3000

# 测试
make test           # pytest + vitest
make lint           # ruff + eslint + tsc
```

---

## 六、BDD 验收场景（覆盖 PRD 6 大核心功能 + roadmap §8 P0/P1/P2）

> **本节目的**：把 PRD 6 大核心功能 + roadmap §8 P0-1~6 / P1-1~4 / P2 缺口 **逐一落成 Given/When/Then BDD 场景**，作为实现前冻结的验收契约。任何 P 任务开工前，先在本节找到对应 BDD，按 T-01~06 + AAA + `test_<方法>_<场景>_<期望>` 转成单元/集成/E2E 测试。
>
> **关联**：[PRD 6 大核心功能](../plan/背景.md) · [roadmap §8 P0/P1/P2 任务表](../plan/开发清单_roadmap.md) · [测试策略 §三 单元 + §四 集成](../specs/05-testing-strategy_测试策略.md) · [测试规范 T-01~06](../conventions/05-testing_测试规范.md) · [STATUS 已知 6 gap](../../STATUS.md)
>
> **场景编号约定**：`B-<PRD章节编号>-<P级别>-<序号>`（如 `B-1-P0-04` = PRD 1 IM 聊天 / P0 / 第 04 项）。
>
> **每个 BDD 场景三件套**：
> 1. **Given**（前置：用户/数据/会话状态）
> 2. **When**（触发：HTTP 请求 / WS 事件 / UI 动作）
> 3. **Then**（断言：HTTP 状态 / 响应体 / DB 副作用 / WS 推送 / UI 状态）

### 6.1 IM 聊天式交互（PRD §1）

#### 6.1.1 对话列表搜索

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-1-P0-S01` 对话列表搜索 |
| **对应任务** | roadmap §8.2 P2 缺口「对话列表搜索/置顶」（STATUS.md PRD 对照段 ⚠️ 部分）|
| **API 端点** | `GET /api/sessions?q=<keyword>&archived=false&pinned_only=true&page=1` |
| **Given** | (a) 存在 4 个会话：S1 私聊「帮我看看代码」、S2 群组「前端开发组」、S3 私聊「修改 bug」、S4 群组「运维 SRE」；(b) 用户 U1 已登录（Bearer JWT） |
| **When** | `GET /api/sessions?q=代码&pinned_only=false&page=1` |
| **Then** | (a) HTTP 200，body `{items:[S1], total:1, page:1, page_size:20}`；(b) S2/S3/S4 不在 items 内（标题不匹配） |
| **边界 1（无匹配）** | `GET /api/sessions?q=不存在的关键词` → 200 `{items:[], total:0}` |
| **边界 2（空 q）** | `GET /api/sessions` → 返回全部未归档会话（4 个），按 `last_active_at desc` 排序 |
| **边界 3（archived=true）** | `GET /api/sessions?archived=true&q=` → 返回已归档的 S3（如果已归档）|
| **错误 401** | 无 JWT → `{error:{code:"E_AUTH_REQUIRED",message:"..."}}` |
| **UI 验收（Playwright E2E）** | 在会话列表 search box 输入「代码」→ 列表 1.5s 内筛掉 S2/S3/S4，剩 S1 高亮 |

#### 6.1.2 对话列表置顶

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-1-P0-S02` 对话列表置顶 |
| **对应任务** | roadmap §8.2 P2 缺口「对话列表置顶」|
| **API 端点** | `POST /api/sessions/{id}/pin-top`  ·  `DELETE /api/sessions/{id}/pin-top` |
| **Given** | (a) S1 私聊未置顶，`pinned_at=null`；(b) U1 已登录 |
| **When** | `POST /api/sessions/S1/pin-top` |
| **Then** | (a) HTTP 204；(b) DB `sessions.pinned_at = now()`；(c) WS 推送 `{type:"session:pin_changed", payload:{session_id:"S1", pinned:true}}` |
| **二次置顶** | 重复 `POST` → 204 幂等（`pinned_at` 不变） |
| **取消置顶** | `DELETE /api/sessions/S1/pin-top` → 204 + `pinned_at=null` + WS 推送 `pinned:false` |
| **跨设备同步** | 设备 A 置顶 → 设备 B 在 ≤2s 内看到会话列表顶部出现 S1（WS 推送 + 本地 store 更新）|
| **UI 验收（Playwright）** | 在 S1 卡片右键菜单选「置顶」→ S1 列表第 1 位 + 图钉 icon 实色；F5 刷新 → 仍置顶 |

#### 6.1.3 消息操作 — 回复

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-1-P0-S03` 消息操作回复 |
| **对应任务** | roadmap §8.2 P2 缺口「消息操作回复」|
| **API 端点** | `POST /api/sessions/{id}/messages`  body `reply_to=<message_uuid>` |
| **Given** | (a) S1 私聊存在 5 条历史消息 M1~M5；(b) M3 是 Agent 回复「代码结构如下…」；(c) U1 已登录 |
| **When** | 在 M3 上点「回复」按钮 → Composer 弹出 `reply_to` 提示条「回复 M3」+ 引用预览 → 输入「请把 utils.ts 拆成 3 个文件」 → 点发送 |
| **Then** | (a) HTTP 201，返回新消息 M6；(b) M6 渲染含引用块「╭ M3 · code agent · 代码结构如下…」缩略；(c) 发送时只触发一次 `POST /api/sessions/S1/messages`（无重复发送）|
| **边界（reply_to 不存在）** | 引用已删除消息 → 422 `{error:{code:"E_MESSAGE_REPLY_TARGET_NOT_FOUND",message:"..."}}` |
| **边界（跨 session）** | `reply_to` 是 S2 的 M3 → 422 `E_MESSAGE_REPLY_TARGET_NOT_FOUND` |
| **UI 验收（Playwright）** | M3 hover → 回复按钮出现 → 点击 → 输入 → 发送 → 滚动条自动滚到 M6，引用块显示 M3 缩略内容 |

#### 6.1.4 消息操作 — 引用（选中消息 → 引用插入 Composer）

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-1-P0-S04` 消息操作引用 |
| **对应任务** | roadmap §8.2 P2 缺口「消息操作引用」|
| **API 端点** | 同 6.1.3（quote 字段而非 reply_to，引用不形成父子关系，仅引用） |
| **Given** | S1 私聊 M1~M5，U1 已登录 |
| **When** | 在 M2 hover → 选「引用」按钮 → Composer 出现引用预览（可关闭）+ 输入框清空 |
| **Then** | (a) Composer 内出现引用 chip「M2 · user · 帮我看看代码」可点 X 关闭；(b) 输入新文本 → 发送后 M6 含 quote 字段 `{message_id:"M2", preview:"帮我看看代码..."}` |
| **多个引用** | 同时引用 M2 + M3 → quote 数组含 2 项，按选择顺序 |
| **UI 验收（Playwright）** | 引用 chip hover 显示完整内容 tooltip + 点 X 立即消失 |

#### 6.1.5 消息操作 — 重新生成（已实现扩展）

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-1-P0-S05` 消息操作重新生成（已完成 P0-5 私聊 + 群聊，扩展到全部消息类型）|
| **对应任务** | P0-5 复制代码/重新生成（已做）；扩展到 P2 文档/Diff 消息 |
| **API 端点** | `POST /api/sessions/{id}/messages/{message_id}/regenerate` |
| **Given** | S1 私聊，M3 是 Agent 代码回复（content_type="code"），U1 已登录 |
| **When** | M3 hover → 点「重新生成」→ loading spinner 1-3s |
| **Then** | (a) HTTP 202 + 返回新 `message_id="M3-v2"`；(b) 旧 M3 标 `superseded=true` 不在流中显示（保留 DB 记录可回查）；(c) WS 推送 `message:stream` 新 M3-v2 |
| **文档/Diff 消息** | M3 是 `content_type=document` 或 `diff` → 同样 202 + 流式重生成（llm 重抽结构化内容）|
| **失败（LLM 超时）** | 30s 内无响应 → 502 `{error:{code:"E_REGENERATE_TIMEOUT",message:"..."}}` + 旧 M3 不变 |

#### 6.1.6 上下文管理 — Pin 消息（**P0-4 后端 session 所有权校验**）

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-1-P0-04` Pin 消息 session 所有权校验 |
| **对应任务** | roadmap §8.1 P0-4 Pin 消息 UI（前端 ✅ 凌晨冲刺 `e667579`，后端校验 ⚠️ probe 2 FAIL STATUS.md gap #3）|
| **API 端点** | `POST /api/messages/{id}/pin?session_id=<sid>`  ·  `DELETE /api/messages/{id}/pin?session_id=<sid>` |
| **Given** | (a) S1 私聊 U1 + U2 两人均参与；(b) S1 中 M1（U1 发） + M2（U2 发）；(c) U1 持有效 JWT |
| **When-1（合法）** | `POST /api/messages/M1/pin?session_id=S1` （U1 操作自己的消息）|
| **Then-1** | (a) HTTP 204；(b) DB `messages.pinned_by_user_id=U1.id, pinned_at=now()`；(c) 跨会话可见（U1 在 S2 私聊发消息时，context_builder 注入 M1 作为 pinned）|
| **When-2（**非法 — 跨用户**）** | `POST /api/messages/M2/pin?session_id=S1`（U1 想 pin U2 的消息）|
| **Then-2** | **HTTP 403** `{error:{code:"E_MESSAGE_PIN_NOT_OWNER",message:"..."}}` ← **本 BDD 是修复 STATUS.md gap #3 的契约** |
| **When-3（**非法 — session 不一致**）** | `POST /api/messages/M1/pin?session_id=S99`（M1 不在 S99）|
| **Then-3** | HTTP 422 `{error:{code:"E_MESSAGE_PIN_SESSION_MISMATCH",message:"..."}}` |
| **When-4（取消）** | `DELETE /api/messages/M1/pin?session_id=S1` |
| **Then-4** | HTTP 204 + `pinned_by_user_id=null, pinned_at=null` |
| **幂等** | 重复 `POST /api/messages/M1/pin?session_id=S1` → 204（不报错，不更新时间戳）|
| **WS 推送** | 任意 Pin 状态变更 → WS 推 `{type:"message:pin_changed", payload:{message_id, session_id, pinned, pinned_by}}`，同会话所有客户端 ≤1s 收到 |
| **UI 验收（Playwright）** | M1 hover → Pin 按钮 → click → M1 顶部出现图钉 icon + Pin 列表抽屉显示 M1；U2 私聊发新消息 → M1 出现在 M2 之前作为 pinned context |

### 6.2 Orchestrator 协调器（PRD §2）

#### 6.2.1 失败降级

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-2-P2-F01` Orchestrator 失败降级 |
| **对应任务** | roadmap §8.3 P2 缺口「Orchestrator 失败降级 + 代码冲突」（STATUS.md PRD 对照段 ❌ 未做）|
| **API 端点** | 无新端点；后端任务编排 service 内 fallback |
| **Given** | (a) S2 群组「前端开发组」含 Coordinator + 3 个子 Agent（ClaudeCode/OpenCode/MockBot）；(b) U1 发送「重构 utils.ts」；(c) Coordinator 拆解出 3 个 TaskPlan 子任务（T1 ClaudeCode 拆文件 / T2 OpenCode 重命名 / T3 MockBot 写测试）|
| **When-1（**单 Agent 失败**）** | T2 OpenCode 进程 30s 超时（exit 124）|
| **Then-1** | (a) Coordinator 不中断整体流程；(b) T2 标 `status=failed, error_code=E_TASK_TIMEOUT, retry_count=1`；(c) 自动 fallback 到 MockBot 重做 T2 内容（MockBot 改写为简化版测试）；(d) S2 群聊流显示「OpenCode 失败 → MockBot 接替」通知 |
| **When-2（**全部失败**）** | 3 个子 Agent 全超时（30s × 3 = 90s）|
| **Then-2** | (a) Coordinator 标 `status=aborted`；(b) 群聊流显示「⚠️ 任务失败，已暂停。请人工 @ 单个 Agent 重试」；(c) Inbox 推送 1 条 `task:failed` 通知给 U1（U1 可 APPROVE 重试 / REJECT 取消）|
| **When-3（**重试成功**）** | U1 在 Inbox 点 APPROVE → 自动重试失败的 T2（用 MockBot）→ 30s 内完成 |
| **Then-3** | (a) T2 标 `status=success (retry)`；(b) Coordinator 聚合 → 群聊流显示完整结果 |
| **When-4（**重试仍失败**）** | MockBot 二次失败（同样 timeout）|
| **Then-4** | (a) T2 永久 `status=failed, retry_count=2`；(b) 群聊流标 ❌ 在 T2 行 + 提示「该子任务已放弃」 |
| **降级矩阵** | 见 [roadmap §七 降级策略](../plan/开发清单_roadmap.md) + [架构 §3.2 协调者降级路径](../specs/01-architecture_架构定义.md) |
| **UI 验收（Playwright）** | 触发 OpenCode 不可用（环境变量 `OPENCODE_BIN=/dev/null`）→ 群聊流显示降级通知 + 任务列表 T2 行出现「重试中」标 |

### 6.3 多 Agent 接入（PRD §3）

#### 6.3.1 用户自建 Agent — 对话式创建

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-3-P0-A01` 对话式自建 Agent |
| **对应任务** | roadmap §四 M4-3 对话式创建（STATUS.md PRD 对照段 ⚠️ 部分 — `CreateAgentModal` 存在但接 API 待补）|
| **API 端点** | `POST /api/agents/draft`  body `{description:<text>}` |
| **Given** | U1 已登录 |
| **When** | 在 CreateAgentModal 「对话式创建」tab 输入「专攻 Python 数据分析的 Agent，擅长 pandas 和 matplotlib」→ 点「生成草稿」|
| **Then** | (a) HTTP 200 返回 `{system_prompt_draft:"你是 Python 数据分析专家...", capability_tags:["python","pandas","matplotlib"], recommended_avatar:"https://..."}`；(b) 前端展示 system_prompt 可编辑 + tags 三个 chip 可改 |
| **生成后流程** | U1 点「继续 → 选系统」→ 进入表单式 tab（agent_system=claude/provider=deepseek）→ POST `/api/agents` 创建 |
| **失败（LLM 不可用）** | provider 503 → 502 `{error:{code:"E_AGENT_DRAFT_LLM_UNAVAILABLE",message:"..."}}` + 提示「切换到表单式创建」 |
| **UI 验收（Playwright）** | 输入描述 → 1.5s 内显示草稿 → 编辑 system_prompt → 进入下一 tab → 选 Claude + DeepSeek → 创建成功 → 跳转 Agent 详情页 |

#### 6.3.2 用户自建 Agent — 表单式创建

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-3-P0-A02` 表单式自建 Agent |
| **对应任务** | 同 6.3.1（互补）|
| **API 端点** | `POST /api/agents` |
| **Given** | U1 已登录 |
| **When** | 表单填写：`agent_system=claude, name=DataAnalyst, role=Python 数据分析, provider=deepseek, model=deepseek-chat, api_key=sk-xxx, skills=[python,pandas]` → 提交 |
| **Then** | (a) HTTP 201 返回 `{id, name, agent_system, status, created_at}`；(b) DB `api_key` 字段 Fernet 加密落库（`api_key_encrypted` 列）；(c) `agents` 表新增 1 行 + 跳转到 `/agents/<id>` 详情页 |
| **name 重复** | 同 name 已存在 → 409 `{error:{code:"E_AGENT_NAME_CONFLICT",message:"..."}}` |
| **api_key 格式错** | `api_key=""` 或非 sk- 开头 → 422 `E_AGENT_API_KEY_INVALID` |
| **agent_system 非法** | `agent_system=unknown` → 422 `E_AGENT_SYSTEM_INVALID` |
| **UI 验收（Playwright）** | 完整填写 → 提交 → 跳转详情页 → 6 个 Tab 内容正确（概览/能力/记忆/任务/活动/设置）|

### 6.4 产物预览与编辑（PRD §4）

#### 6.4.1 文档渲染

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-4-P2-D01` 文档渲染（MarkdownBody 升级到独立 DocumentRenderer）|
| **对应任务** | roadmap §8.3 P2 缺口「文档渲染」（STATUS.md PRD 对照段 ⚠️ 部分）|
| **API 端点** | 无新端点；前端组件升级 |
| **Given** | (a) Agent 回复 content_type="document" + content 字段含 Markdown `# Heading\n\n- list\n\n\`\`\`ts\ncode\n\`\`\``；(b) U1 在 S1 私聊 |
| **When** | 消息流渲染该 document 消息 |
| **Then** | (a) 显示 H1 标题 + 列表 + 围栏代码块（语法高亮 ts）；(b) 代码块右上角出现「复制」+「全屏预览」icon；(c) 文档内图片/链接可点击 |
| **大文档（>10k 字符）** | 自动折叠（默认显示前 1000 字符 + 「展开全文」按钮） |
| **XSS 防护** | content 含 `<script>alert(1)</script>` → 渲染为纯文本（DOMPurify 过滤）|
| **UI 验收（Playwright）** | 文档消息渲染正确 + 代码块复制按钮可点 + 全屏预览 modal 打开/关闭 |

#### 6.4.2 全屏预览

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-4-P2-D02` 全屏预览（WebPreviewCard / DiffView / DocumentRenderer 共用 modal）|
| **对应任务** | roadmap §8.3 P2 缺口「全屏预览」（STATUS.md PRD 对照段 ⚠️ 部分 — 缺全屏 modal）|
| **API 端点** | 无新端点；前端组件新增 FullscreenModal |
| **Given** | S2 群聊内嵌 WebPreviewCard（agent 返回的 URL `https://example.com/preview`）|
| **When** | 点击 WebPreviewCard 的「⛶ 全屏」icon |
| **Then** | (a) 弹出 modal 占满视口 95%（top/left/bottom/right 5% 边距）；(b) iframe 内容真实渲染（sandbox 限制去掉 allow-same-origin 保留）；(c) 顶部 toolbar 含「关闭」+「在新窗口打开」+「复制 URL」 |
| **Esc 关闭** | 按 Esc 键 → modal 关闭 + 焦点回到原消息 |
| **DiffView 全屏** | 点击 DiffCard 的「⛶」→ 同样的 modal 渲染彩色 diff（无 iframe，纯文本 + 行号）|
| **DocumentRenderer 全屏** | 点击文档代码块的「⛶」→ modal 渲染代码（无图片/链接，专注代码）|
| **响应式** | 视口 < 768px → modal 全屏无 5% 边距 |
| **UI 验收（Playwright）** | 触发三种内容（web/diff/document）的全屏 → modal 正确渲染 + Esc 关闭 + 焦点回归 |

#### 6.4.3 Monaco 代码编辑器

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-4-P2-D03` Monaco 代码编辑器 |
| **对应任务** | roadmap §8.3 P2 缺口「Monaco 编辑器」（STATUS.md PRD 对照段 ❌ 未做 — Composer 仅有 textarea）|
| **API 端点** | 无新端点；前端 `CodeEditor.tsx` 组件 + `@monaco-editor/react` 依赖 |
| **Given** | S1 私聊，U1 hover Agent 代码回复 M3（含 ```ts 围栏代码 50 行） |
| **When-1（编辑）** | 点 M3 代码块右上「✎ 编辑」icon → 弹出 CodeEditor modal（占视口 80%）|
| **Then-1** | (a) Monaco 加载 + 语法高亮 ts + 行号 + minimap；(b) 顶部 toolbar：「保存」+「应用到对话」+「关闭」+「格式化」+「字数 X」 |
| **When-2（应用到对话）** | 编辑代码（修改 1 行）→ 点「应用到对话」|
| **Then-2** | (a) HTTP `POST /api/sessions/S1/messages` body `{content_type:"code_edit", parent_message_id:"M3", edited_code:"<new>"}` → 201；(b) S1 群聊流新增 M6（标 `parent=M3` + `code_edit` 类型）；(c) U1 可继续对话讨论此修改 |
| **When-3（保存到草稿）** | 点「保存」→ `POST /api/drafts` body `{content, scope:"agent", agent_id, title:"..."}` → 201 |
| **语法切换** | 顶部下拉切 language（ts/python/json/yaml）→ Monaco 重新高亮 |
| **大文件（>10k 行）** | Monaco 自动 virtual scroll + 警告「文件较大，已启用懒加载」 |
| **UI 验收（Playwright）** | 触发编辑 → 修改 → 应用 → 群聊新增 M6 → 内容正确回显 |

#### 6.4.4 部署卡（**P2 部署**）

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-5-P2-DP01` 部署卡 |
| **对应任务** | roadmap §8.3 P2 缺口「部署发布」（STATUS.md PRD 对照段 ❌ 未做）|
| **API 端点** | `POST /api/deployments`  body `{session_id, target:"static_site"|"container"|"package", entry_file?, framework?}`  ·  `GET /api/deployments/{id}`  ·  `DELETE /api/deployments/{id}` |
| **Given** | (a) S1 私聊，Agent 写完 `index.html` + `app.js`（含在 M3 代码块内）；(b) U1 选中 M3 代码 → 点「部署」|
| **When-1（静态站点）** | 选 `target=static_site` + 入口 `index.html` → 提交 |
| **Then-1** | (a) HTTP 202 + 返回 `deployment_id="D1" status="building"`；(b) 群聊流新增消息 M4 content_type="deploy_card" 含进度条；(c) WS 推送 `{type:"deployment:progress", payload:{deployment_id:"D1", progress:0, stage:"uploading"}}` |
| **When-2（完成）** | 30s 后 |
| **Then-2** | (a) `GET /api/deployments/D1` → 200 `{status:"ready", preview_url:"https://agenthub-deploy.com/d1-xxx", build_logs:[...], ttl:3600}`；(b) deploy_card 渲染：进度 100% + 预览 URL 可点击 iframe + 「在新窗口打开」+「删除」|
| **When-3（容器化）** | 选 `target=container` + framework=docker |
| **Then-3** | 进度阶段：building image → pushing → starting → running；最长 5min；超时 504 `E_DEPLOY_TIMEOUT` |
| **When-4（源码打包）** | 选 `target=package` |
| **Then-4** | 返回 `download_url="https://.../d1.zip"`（zip 含 index.html + app.js）|
| **When-5（删除）** | `DELETE /api/deployments/D1` → 204 + preview URL 失效 |
| **失败（构建错）** | index.html 引用不存在的 script.js → build_logs 报错 + status="failed" + deploy_card 标 ❌ |
| **UI 验收（Playwright）** | 选 M3 部署 → 选 static_site → 进度条更新 → 完成显示 URL → 点击 URL 打开预览 iframe |

### 6.5 多端支持（PRD §6 P2）

#### 6.5.1 移动端 H5

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-6-P2-M01` 移动端 H5（轻量 IM）|
| **对应任务** | roadmap §8.3 P2 缺口「移动端 H5」（STATUS.md PRD 对照段 ❌ 未做）|
| **API 端点** | 复用现有 `/api/sessions` + `/api/messages` + WS |
| **Given** | U1 用手机（iOS Safari / Android Chrome）访问 `https://<agenthub-host>/m` |
| **When-1（会话列表）** | H5 页面加载（<3s） |
| **Then-1** | (a) 显示会话列表（卡片堆叠纵向，每卡 1 行：头像 + 标题 + 最近 1 条预览 + 时间）；(b) 无 Monaco / 无 WebPreviewCard / 无 DiffView（按需加载）；(c) 顶部 nav 含「新会话」+「设置」|
| **When-2（聊天）** | 点 S1 私聊 → 进入聊天页 |
| **Then-2** | (a) 消息流纵向滚动；(b) 输入框底部固定 + 「+」按钮（附件/语音/拍照，附件复用 P0-3 multipart）；(c) WS 连接建立（自动重连，断网恢复 ≤3s 同步增量）|
| **When-3（审批）** | U1 收到 Inbox 审批通知 → 点开 → 看到 Approve/Reject/Edit/Respond 4 按钮 |
| **Then-3** | 点 Approve → 调 `POST /api/approvals/{task_id}/approve` → 通知 Inbox 「已处理」 |
| **When-4（产物预览）** | 收到 WebPreviewCard 消息（agent 返回 URL）|
| **Then-4** | H5 显示「在新窗口打开」按钮（无 iframe — iOS Safari iframe 受限）|
| **When-5（响应式断点）** | 视口 ≥ 768px → 自动跳到 web 端 SPA（不带 /m 前缀）|
| **断网** | 飞行模式 → 输入框上方出现「⚠️ 离线」banner → 恢复后自动重连 + 队列消息发送 |
| **UI 验收（Playwright mobile viewport）** | 设 viewport `iPhone 12` (390x844) → 验证 5 个 When/Then 全部通过 + 截图 |

#### 6.5.1.1 4 栏 shell 响应式（移动 H5 已落地部分）

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-6-P2-M02` 4 栏 shell 响应式（AppShell mobile 折叠）|
| **对应任务** | roadmap §8.3 P2 缺口「移动端 H5」**已落地部分**（STATUS.md 22:00 E2E 校正段 ❌ → 本 BDD 落地后变 ✅）|
| **API 端点** | 无；前端 `useMediaQuery` hook + `AppShell` 条件渲染（**`src/frontend/src/hooks/useMediaQuery.ts`** + **`src/frontend/src/components/layout/AppShell.tsx`**）|
| **Given** | (a) 浏览器加载 AgentHub SPA；(b) AppShell 已挂载；(c) `useMediaQuery('(max-width: 767px)')` 响应窗口 resize / 设备方向 |
| **When-1（视口 375 / 移动）** | Playwright `browser_resize {"width":375,"height":667}` 或手机访问 |
| **Then-1** | (a) DOM 含 `data-testid="app-shell-mobile"`，**不**含 `app-shell-desktop`；(b) 顶部 mobile bar 显示：hamburger (`mobile-hamburger`) + 当前 section 标题 + 右侧 panel toggle (`mobile-right-toggle`)；(c) NavRail/LeftPanel 不再作为 4 栏并列元素渲染；(d) CenterPanel 占据全部宽度 |
| **When-2（视口 768 / 临界）** | Playwright `browser_resize {"width":768,"height":1024}` |
| **Then-2** | (a) 768 ≥ 768 触发 → 切换到桌面 shell（`app-shell-desktop` 出现）；(b) 4 栏并排：NavRail + LeftPanel + CenterPanel + RightPanel；(c) 桌面原有 `showLeftExpand` / RightPanelResizeHandle 行为不变 |
| **When-3（视口 1280 / 桌面）** | Playwright `browser_resize {"width":1280,"height":800}` |
| **Then-3** | (a) `app-shell-desktop` 渲染；(b) 4 栏并排 + NavRail 不被 hamburger 替代 |
| **When-4（hamburger 触发左抽屉）** | 移动端点 hamburger |
| **Then-4** | (a) `mobile-left-drawer` 出现（含 NavRail + LeftPanel 滑出）；(b) 抽屉内 NavRail 的 4 主功能（chat/agent/group/skill）可点 → `setSection(...)`；(c) 点 scrim 或按 Esc → 抽屉关闭 |
| **When-5（右侧 toggle 触发右抽屉）** | 移动端 section ∈ {chat, group, agent-detail} 时点 `mobile-right-toggle` |
| **Then-5** | (a) `mobile-right-drawer` 出现（含 RightPanel 滑出）；(b) 点 scrim 或 Esc → 关闭 |
| **响应式断点** | 临界 768px 走桌面路径；< 768 走 mobile 路径（不动画，瞬间显示/隐藏 per brief downscope）|
| **边界（无 matchMedia 旧浏览器）** | `window.matchMedia` 不存在 → `useMediaQuery` 返回 false → 走桌面 shell（SSR-safe + 旧浏览器降级）|
| **UI 验收（Playwright mobile viewport）** | 三个 viewport 375 / 768 / 1280 各截图 + 1 张 hamburger 打开后截图；3+1 张落 `docs/deliverables/screenshots/e2e-mobile-{375,768,1280,hamburger}-2026-06-08.png` |
| **vitest 验收** | `useMediaQuery.test.ts` 5 测 + `AppShell.responsive.test.tsx` 6 测 = 11 新测；全项目 85/85 绿 |

#### 6.5.2 v6 录制脚本（基于真实工作流）

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-6-P2-V01` v6 Demo 录制脚本（替代 v4 wallpaper 残留）|
| **对应任务** | STATUS.md gap #5 + roadmap §8.4 Demo 脚本（v6 重录待做）|
| **API 端点** | 无；基于 Playwright 录制脚本 |
| **Given** | (a) Docker frontend 容器 vite dev mode + volume mount（commit `f0a2cb5` 改代码 HMR 实时刷新）；(b) 浏览器 Chrome 启动参数 `--start-maximized`（per agent memory「Playwright 录 demo 视频核心约束」） |
| **When-1（录制）** | 跑 `python scripts/demo_v6.py` → Playwright 启 1920x1080 Chrome → ffmpeg gdigrab `-i desktop -video_size 1920x1080` 录屏 |
| **Then-1** | (a) 录制 200s mp4 + 13KB 脚本（6 章节：开场 / S1 私聊 / S2 群聊 / S3 预览 / S4 自建 Agent / S5 任务看板 / 收尾）；(b) **零 wallpaper 残留**（v4 DISPLAY1 偏移 44.9% 修掉）；(c) 7 段 TTS zho + 27 字幕 mov_text + 2 AI cover |
| **When-2（章节验收）** | 6 章节每章节 ≥20s，每章节末有 TTS 语音总结 |
| **Then-2** | 时长合计 200s ±5s；Mp4 moov atom 在文件头（web 可播）|
| **When-3（基于 commit `079cdca` + `f0a2cb5`）** | S2 群聊章节演示 G1 修复后的 Pin/复制代码；vite dev mode 改代码 HMR 验证可见 |
| **Then-3** | 视频 S2 群聊章节能完整演示 Pin 按钮（hover → click → 图钉 icon 实色）+ 复制代码（click → 浏览器原生「已复制」tooltip）|
| **当替代 v4 时** | 旧 `AgentHub-Demo-Video.mp4` v4 移到 `docs/deliverables/video/v4-deprecated.mp4` + ADR 记录 |
| **验收** | `ffprobe AgentHub-Demo-Video-v6.mp4` 显示 1920x1080 h264+aac+mov_text 字幕 zho；人工 review 无明显 wallpaper 残留 |

### 6.6 Token 消耗监控（**P1-2**）

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-5.3-P1-2` Token 消耗监控 |
| **对应任务** | roadmap §6 M5-5.3 Token 消耗监控（待办，per STATUS.md M5 段 ⬜）|
| **API 端点** | `GET /api/usage?agent_id=<uuid>&session_id=<uuid>&window=1h|24h|7d`  ·  `GET /api/usage/{agent_id}`  ·  `GET /api/usage/sessions/{session_id}` |
| **Given-1（**agent 维度**）** | (a) Agent A1（ClaudeCode）今天消耗 input=12000 + output=8000 = 20000 tokens；(b) 5 个 session 复用 A1 |
| **When-1** | `GET /api/usage/A1?window=24h` |
| **Then-1** | (a) HTTP 200 `{agent_id, total_input:12000, total_output:8000, total:20000, by_session:[{session_id, input, output, msg_count}], budget_pct:0.02}`；(b) 字段 = `usage_records` 表 group by session_id |
| **Given-2（**session 维度**）** | (a) S1 私聊含 10 轮对话（user 5 + agent 5）；(b) 5 条 agent 消息共 8000 tokens |
| **When-2** | `GET /api/usage/sessions/S1?window=24h` |
| **Then-2** | (a) HTTP 200 `{session_id:"S1", total:8000, by_agent:[{agent_id:"A1", input, output}], by_msg:[{message_id, tokens, ts}]}` |
| **Given-3（**预算超限**）** | `daily_token_budget=10000`，今日已用 10500 |
| **When-3** | WS 推送 `{type:"token:budget_exceeded", payload:{agent_id, daily_tokens:10500, daily_budget:10000, pct:1.05}}` |
| **Then-3** | (a) 前端顶部出现红色 banner「⚠️ Token 已超预算 5%」；(b) 设置页 PATCH `/api/settings` 改 `daily_token_budget` → 报警解除 |
| **实时推送** | 新消息流式输出 → WS 推 `{type:"token:update", payload:{session_id, agent_id, session_tokens:16000, daily_tokens:250000, daily_budget:1000000}}`（已存在于 §三，本节为端点契约）|
| **失败（agent 不存在）** | `GET /api/usage/A99` → 404 `E_USAGE_AGENT_NOT_FOUND` |
| **UI 验收（Playwright）** | Agent 详情页 Tab「设置」显示 token 实时统计（每小时刷新） + 会话列表卡片右下显示当日消耗 |

### 6.7 CLI PATH 扫描（**P1-3**）

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-5.4-P1-3` CLI PATH 扫描 |
| **对应任务** | roadmap §8.2 P1-3 CLI PATH 扫描前端实时展示（待办，per STATUS.md M5 段 ⬜）|
| **API 端点** | `GET /api/cli/scan?bins=claude,codex,opencode,pi,trae`  ·  `POST /api/cli/scan/refresh`（手动触发）|
| **Given** | (a) 后端启动时自动跑 `which claude codex opencode pi trae` + `--version` 探测；(b) 用户 PATH 含 `/usr/local/bin/claude` + `/opt/opencode/bin/opencode`（无 pi / codex / trae）|
| **When-1（自动扫描）** | Docker compose up → backend 启动 5s 内 |
| **Then-1** | (a) DB `cli_binaries` 表新增 5 行扫描结果：`{name:"claude", path:"/usr/local/bin/claude", version:"1.0.15", available:true, last_scan_at}`、`{name:"codex", available:false, error:"not in PATH"}` 等；(b) 缓存 1h（避免每次启动扫）|
| **When-2（API 拉取）** | 前端设置页加载 → `GET /api/cli/scan` |
| **Then-2** | (a) HTTP 200 `{items:[{name, path, version, available, error?}], scanned_at, next_scan_at}`；(b) 前端表格渲染：5 行 + 状态徽章（✅ 可用 / ❌ 缺失 / ⚠️ 版本过低）|
| **When-3（手动刷新）** | 点设置页「🔄 重新扫描」→ `POST /api/cli/scan/refresh` |
| **Then-3** | (a) HTTP 202 + 后台 async 跑扫描；(b) 完成后 WS 推 `{type:"cli:scan_complete", payload:{...}}`；(c) 前端表格原地刷新 |
| **When-4（CLI 不可用 → 适配器降级）** | `codex` 不在 PATH → 创建 Agent 选 `agent_system=codex` 时显示「⚠️ codex 未安装，无法调度」+ 不允许创建 |
| **Then-4** | 表单提交 → 422 `E_AGENT_CLI_NOT_AVAILABLE` |
| **UI 验收（Playwright）** | 设置页打开 → 看到 5 行 CLI 状态 + 「重新扫描」按钮工作 + 缺失 CLI 标红 |

### 6.8 失败降级（PRD §2 + roadmap §七 降级策略）

| 项 | 内容 |
|----|------|
| **场景 ID** | `B-7-P2-FD01` 多场景失败降级 |
| **对应任务** | 整合 PRD §2 + roadmap §七 降级策略矩阵 |
| **API 端点** | 无新端点；服务级 fallback |
| **Given** | 各种降级触发场景（见下表）|
| **When & Then** | 见 [roadmap §七 降级策略表](../plan/开发清单_roadmap.md) 4 条 + [架构 §3.2 协调者降级路径](../specs/01-architecture_架构定义.md) |
| **降级矩阵** |  |
|   | 触发 | 降级 |
|   | Agent 系统 API 接入阻塞 | Mock Agent 返回预设响应（`LLMAdapterMode=mock`），UI 完整 |
|   | 协调者任务拆解不稳定 | 降级为手动 @Agent 模式（dispatch_mode="direct"）|
|   | 内联预览阻塞 | 新窗口打开预览（target="_blank"）|
|   | LLM Provider 不可用 | 切换备选 Provider；全部不可用 → Mock 演示 |
|   | Demo 录制当天环境挂 | 预备录屏备份（提前一周录制一次）|
|   | 任务 > 30s | 手动 @Agent 单步走 |
| **测试模式** | `LLM_ADAPTER_MODE=mock` env var → 所有 LLM 调用返回 fixture；E2E 用此模式跑通 |
| **UI 验收（Playwright）** | env 切 `LLM_ADAPTER_MODE=mock` → 重新创建 Agent → 私聊 5 轮 → 全部 200 OK 响应（fixture 数据）|

---

## 七、BDD ↔ 任务映射速查表

> 给实现者：「我接 P 任务 X，先在 §六 找 BDD Y」。

| Roadmap 任务 | STATUS 状态 | BDD 场景 ID | 端点 / 组件 |
|--------------|-----------|-------------|------------|
| P0-4 Pin 消息 UI | ✅ 后端待修 | `B-1-P0-04` | `POST/DELETE /api/messages/{id}/pin?session_id=...` |
| P1-2 Token 消耗监控 | ⬜ 待办 | `B-5.3-P1-2` | `GET /api/usage/{agent_id\|sessions/{id}}` |
| P1-3 CLI PATH 扫描 | ⬜ 待办 | `B-5.4-P1-3` | `GET/POST /api/cli/scan` |
| 对话列表搜索/置顶 | ⚠️ 部分 | `B-1-P0-S01` `B-1-P0-S02` | `GET /api/sessions?q=` `POST/DELETE /api/sessions/{id}/pin-top` |
| 消息操作回复/引用 | ⚠️ 部分 | `B-1-P0-S03` `B-1-P0-S04` | `POST /api/sessions/{id}/messages reply_to=` |
| 消息操作重新生成 | ✅ 部分（扩 doc/diff）| `B-1-P0-S05` | `POST /api/sessions/{id}/messages/{id}/regenerate` |
| 文档渲染 | ⚠️ 部分 | `B-4-P2-D01` | 前端 DocumentRenderer |
| 全屏预览 | ⚠️ 部分 | `B-4-P2-D02` | 前端 FullscreenModal |
| Monaco 编辑器 | ❌ 未做 | `B-4-P2-D03` | 前端 CodeEditor + `@monaco-editor/react` |
| 部署卡 | ❌ 未做 | `B-5-P2-DP01` | `POST/GET/DELETE /api/deployments` |
| 移动端 H5 — 4 栏 shell 响应式 | ✅ **已做**（`B-6-P2-M02` 落地，`useMediaQuery` + `AppShell` mobile 折叠 + 11 单测 + 4 viewport 截图）| `B-6-P2-M02` | `useMediaQuery` hook + `AppShell.tsx` mobile 分支 |
| 移动端 H5 — 独立 `/m` 路由 | ⬜ 未做 | `B-6-P2-M01` | 前端 `/m` 路由（待 6.5.1 全部 When 落地）|
| v6 录制脚本 | ⚠️ v4 wallpaper 残留 | `B-6-P2-V01` | `scripts/demo_v6.py` |
| 失败降级 | ❌ 未做 | `B-2-P2-F01` `B-7-P2-FD01` | 后端 service fallback |
| 对话式自建 Agent | ⚠️ 部分 | `B-3-P0-A01` | `POST /api/agents/draft` |
| 表单式自建 Agent | ⚠️ 部分 | `B-3-P0-A02` | `POST /api/agents` |

---

## 八、关联文档

| 方向 | 链接 |
|------|------|
| 完整功能列表 | [PRD 6 大核心功能](../plan/背景.md) |
| 任务清单 + 进度 | [roadmap §8 P0/P1/P2 任务表](../plan/开发清单_roadmap.md) |
| 测试策略（如何测）| [05-testing-strategy_测试策略.md](../specs/05-testing-strategy_测试策略.md) |
| 测试规范（测试编写规则）| [05-testing_测试规范.md](../conventions/05-testing_测试规范.md) |
| 数据模型 | [03-data-model_数据模型.md](../specs/03-data-model_数据模型.md) |
| 架构降级 | [01-architecture_架构定义.md](../specs/01-architecture_架构定义.md) §3.2 |
| 当前缺口 | STATUS.md 已知 6 gap + PRD 对照段（✅ 9 / ⚠️ 6 / ❌ 7 / 📋 1）|

---

## 更新记录

| 日期 | 版本 | 变更说明 |
|------|------|---------|
| 2026-05-23 | v2.1 | 初版（环境变量 + REST API + WS + CLI + 启动）|
| 2026-06-03 | v2.1 + §2.6 | MCP API 冻结草案（PR-01 待 Review）|
| 2026-06-07 | v2.2 | 新增 §六 BDD 验收场景（覆盖 P0-4/P1-2/P1-3 + 11 P2 缺口 + 失败降级）+ §七 BDD↔任务映射表 + §八 关联文档 |
| 2026-06-08 | v2.3 | 新增 §6.5.1.1 `B-6-P2-M02` 4 栏 shell 响应式（useMediaQuery + AppShell mobile 折叠 + 5 When/Then：375/768/1280/hamburger/右抽屉）；§七映射表拆 移动端 H5 — 4 栏 shell 响应式 ✅ 已做 / 移动端 H5 — 独立 /m 路由 ⬜ 未做 |
