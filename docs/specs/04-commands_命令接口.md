# AgentHub 命令接口

> 版本: v2.1 | 基于 PRD v4.0 + 架构设计 v1.0 | 2026-05-23
> v2.1: 环境变量摘除 Celery/LiteLLM，新增 CLI 相关配置

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
  副作用: 调用 AgentRuntime.attach_mcp(bindings)（F-012），把 MCP config 注入 Agent Runtime 进程
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
