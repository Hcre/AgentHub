# IC-MCP-V1.0-20260602（修订版）— MCP 接入接口契约

> **版本**：V1.0-rev（2026-06-03 重写）
> **修订依据**：可行性清单 I-01/I-11（22 IC → 8+2 端点；走 PR-01 冻结）
> **上一版**：22 个接口契约（散布在 22 模块）
> **本文档**：MCP 接入的**8+2 端点 + WS 事件**契约
> **PR-01 待办**：本节端点需在 P1 启动前冻结到 `docs/specs/04-commands`（2 人 Review）
> **单一权威入口**：[`../../README-REVISION.md`](../../README-REVISION.md)

> ⚠️ **ERRATA（2026-06-03 PR-01 冻结时校正）**：本文档下方仍用 `/api/v1/mcp/...` 前缀与 `{"event":...}` 扁平 WS 格式，**已在冻结时按全库现状校正**，以 `docs/specs/04-commands_命令接口.md` §2.6 + §三 为准：① URL → `/api/mcp/...`（无 `/v1/`）；② WS → `{"type":"tool_call:*","payload":{...}}` 信封 + `request_id`（AP-07）；③ `attach_mcp` 落 `domain/llm/protocol.py::AgentRuntime`（非 `mcp_injector`）。本文档其余字段/错误码仍有效。

---

## 0. 修订要点

| 项 | 上一版 | **修订版** |
|----|--------|-----------|
| IC 总数 | 22（散布在 22 模块） | **8 HTTP + 2 WS 事件** = 8+2 |
| 端点命名 | 散落 | 全部 `kebab-case`，`/api/v1/mcp/...` 前缀（AP-01） |
| 错误格式 | 散落 | 统一 `{error:{code,message}}`（AP-02） |
| 鉴权 | 散落 | JWT（既有，AP-04） |
| 响应模型 | 散落 | Pydantic（既有 `schemas/mcp.py`） |
| WS 路径 | 散落 | 既有 `api/ws/toolcall.py`（F-014 复用） |

---

## 1. 8 个 HTTP 端点（PR-01 冻结对象）

> 全部为 `/api/v1/mcp/...` 前缀；`Authorization: Bearer <jwt>`（既有 AP-04）。

### 1.1 市场类（3 个）

#### `GET /api/v1/mcp/market` — MCP 市场列表
- 描述：F-001 列表 + F-002 搜索
- Query: `workspace_id` (required), `q` (optional, 搜索关键字), `tag` (optional), `page` (default=1), `page_size` (default=20, max=100), `transport` (optional: `stdio`|`sse`|`streamable_http`), `official_only` (optional bool)
- Response 200:
```json
{
  "items": [
    {
      "mcp_id": "uuid",
      "name": "Filesystem MCP",
      "slug": "filesystem",
      "description": "...",
      "transport": "stdio",
      "version": "1.2.0",
      "tags": ["fs", "io"],
      "official": true,
      "install_count": 42
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```
- 错误：401 / 403（无 workspace 权限） / 422（参数错误）

#### `GET /api/v1/mcp/market/{mcp_id}` — MCP 详情
- 描述：F-003 详情
- Path: `mcp_id` (UUID)
- Response 200: `{ mcp_id, name, slug, description, transport, config_schema, version, tags, ... }`
- 错误：401 / 404

#### `GET /api/v1/mcp/market/templates` — 模板库列表（F-022）
- 描述：F-022 5 个官方模板
- Query: `workspace_id` (required)
- Response 200: `{ templates: [{ template_id, name, mcp_config, ... }] }`

---

### 1.2 安装类（2 个）

#### `POST /api/v1/mcp/installations` — 一键安装
- 描述：F-004
- Body:
```json
{
  "workspace_id": "uuid",
  "mcp_id": "uuid",
  "instance_name": "fs-prod",
  "config_overrides": { "ROOT_PATH": "/data" }
}
```
- Response 201: `{ installation_id, status: "installing" | "ready", mcp_id, instance_name, created_at, ... }`
- 幂等：同 `workspace_id` + `mcp_id` + `args_hash` 重复调用 → 返回同一 `installation_id`（F-004 验收 ③）
- 错误：400 / 401 / 403 / 404 / 409（已存在但 instance_name 冲突） / 422 / 500
- 错误码示例：`E_INSTALL_TIMEOUT` / `E_INSTALL_DEPENDENCY_MISSING` / `E_INSTALL_PERMISSION_DENIED`

#### `DELETE /api/v1/mcp/installations/{installation_id}` — 卸载（F-005）
- 描述：F-005 卸载（级联检查 binding 占用）
- Path: `installation_id` (UUID)
- Query: `workspace_id` (required, 鉴权用)
- Response 204
- 错误：401 / 403 / 404 / 409（仍有 active binding，需先解绑） / 500

---

### 1.3 绑定类（2 个）

#### `POST /api/v1/mcp/bindings` — 绑定（F-009）
- 描述：F-009 绑定 MCP 到 Agent
- Body:
```json
{
  "agent_id": "uuid",
  "installation_id": "uuid",
  "tool_subset": ["read_file", "list_dir"]   // 可选；默认全选
}
```
- Response 201: `{ binding_id, agent_id, installation_id, tool_subset, status: "active", created_at }`
- 副作用：调用 `mcp_injector.attach_mcp(...)`（F-012）— 实际把 MCP config 注入 Agent 的 Runtime 进程
- 错误：400 / 401 / 403 / 404 / 409（重复绑定） / 500

#### `DELETE /api/v1/mcp/bindings/{binding_id}` — 解绑（F-010/F-011）
- 描述：F-010 解绑 + F-011 5s 内 WS 路由表更新
- Path: `binding_id` (UUID)
- Response 204
- 副作用：调用既有 WS 通道更新路由（≤5s）
- 错误：401 / 403 / 404 / 500

---

### 1.4 创建类（1 个）

#### `POST /api/v1/mcp/servers` — 创建自定义 MCP（F-018/F-019）
- 描述：F-018 stdio / F-019 sse+streamable_http
- Body:
```json
{
  "name": "My Custom MCP",
  "slug": "my-custom-mcp",
  "description": "...",
  "transport": "stdio",     // or "sse" or "streamable_http"
  "config_json": { "command": "npx", "args": ["-y", "@my/mcp"] },
  "version": "0.1.0",
  "tags": ["custom"],
  "template_id": null,      // 可选：从模板创建
  "dry_run": true           // 默认 true：E-03 干跑后再入库
}
```
- Response 201: `{ mcp_id, status: "draft", dry_run_result: {...} }`
- 干跑：调用 `docker_sandbox.runner.run(...)`，30s 超时 + CPU=1 + Mem=512MB + net=none
- 错误：400 / 401 / 403 / 409（slug 冲突） / 422（config_schema 校验失败） / 500

---

## 2. 2 个 WS 事件（F-014 复用既有 `api/ws/toolcall.py`）

### 2.1 `tool_call_request`（Runtime → 后端）
- 方向：Runtime → AgentHub backend
- 触发：Runtime 检测到 Agent 需调用 MCP 工具
- Payload:
```json
{
  "event": "tool_call_request",
  "trace_id": "trace-abc123",
  "agent_id": "uuid",
  "binding_id": "uuid",
  "tool_name": "read_file",
  "args": { "path": "/data/x.txt" },
  "ts": "2026-06-03T12:34:56.789Z"
}
```
- 后端动作：落 `mcp_tool_call_logs` (status=pending)；广播到 IM 会话

### 2.2 `tool_call_response` / `tool_call_progress` / `tool_call_error`（Runtime → 后端）
- 方向：Runtime → AgentHub backend
- 触发：工具调用返回 / 进度 / 错误
- Payload 公共字段：`event`, `trace_id`, `binding_id`, `tool_name`, `duration_ms`
- `tool_call_response` 附加：`result` (any)
- `tool_call_progress` 附加：`progress` (0-100), `message`
- `tool_call_error` 附加：`error_code`（如 `TIMEOUT`/`PERMISSION_DENIED`/`RUNTIME_ERROR`）, `error_message`
- 后端动作：更新 `mcp_tool_call_logs` + 推 IM 会话

> **取消协议**（F-016）：前端发 `tool_call_cancel`，后端转 Runtime（≤2s），Runtime 收到 SIGTERM 沙箱进程。

---

## 3. Pydantic schemas（`schemas/mcp.py`）

> 待 P1 实现时落地，本节为契约占位。

```python
class MCPServerListItem(BaseModel):
    mcp_id: UUID
    name: str
    slug: str
    description: str | None
    transport: Literal["stdio", "sse", "streamable_http"]
    version: str
    tags: list[str]
    official: bool
    install_count: int

class MCPServerDetail(MCPServerListItem):
    config_schema: dict
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    dry_run_result: dict | None

class MCPServerCreate(BaseModel):
    name: str = Field(max_length=128)
    slug: str = Field(max_length=128, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    transport: Literal["stdio", "sse", "streamable_http"]
    config_json: dict
    version: str = Field(max_length=50)
    tags: list[str] = []
    template_id: UUID | None = None
    dry_run: bool = True

class WorkspaceMCPInstallationCreate(BaseModel):
    workspace_id: UUID
    mcp_id: UUID
    instance_name: str = Field(max_length=128)
    config_overrides: dict = {}

class WorkspaceMCPInstallationItem(BaseModel):
    installation_id: UUID
    workspace_id: UUID
    mcp_id: UUID
    instance_name: str
    status: Literal["installing", "ready", "failed"]
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

class AgentMCPBindingCreate(BaseModel):
    agent_id: UUID
    installation_id: UUID
    tool_subset: list[str] | None = None   # None = 全选

class AgentMCPBindingItem(BaseModel):
    binding_id: UUID
    agent_id: UUID
    installation_id: UUID
    tool_subset: list[str]
    status: Literal["active", "paused", "removed"]
    created_at: datetime
    unbound_at: datetime | None
```

---

## 4. 错误码清单（AP-02 + AP-03）

> 全部以 `E_` 前缀，与既有 chat 端点风格一致。

| 错误码 | 含义 | HTTP |
|--------|------|------|
| `E_MCP_NOT_FOUND` | mcp_id / installation_id / binding_id 不存在 | 404 |
| `E_MCP_NAME_CONFLICT` | 同 workspace 内 instance_name 冲突 | 409 |
| `E_MCP_SLUG_CONFLICT` | 创建时 slug 冲突 | 409 |
| `E_MCP_BINDING_CONFLICT` | 重复绑定 | 409 |
| `E_MCP_INSTALL_TIMEOUT` | 安装 5s 内未 ready | 500 |
| `E_MCP_INSTALL_DEPENDENCY_MISSING` | 依赖缺失（stdio 命令找不到） | 500 |
| `E_MCP_INSTALL_PERMISSION_DENIED` | 权限不足 | 403 |
| `E_MCP_DRY_RUN_TIMEOUT` | 干跑 30s 超时 | 422 |
| `E_MCP_DRY_RUN_FAILED` | 干跑失败（initialize/tools/list 错误） | 422 |
| `E_MCP_SCHEMA_INVALID` | config_schema 校验失败 | 422 |
| `E_MCP_VERSION_TOO_LONG` | version > 50 字符 | 422 |
| `E_MCP_BATCH_TOO_LARGE` | 单 workspace 批量 > 50 | 422 |
| `E_MCP_TOOL_CALL_TIMEOUT` | 工具调用 30s 超时 | 500 |
| `E_MCP_TOOL_CALL_CANCELLED` | 用户取消 | 500 |
| `E_MCP_TOOL_CALL_RUNTIME_ERROR` | 运行时错误 | 500 |
| `E_MCP_PERMISSION_DENIED` | 无 workspace 操作权限 | 403 |
| `E_MCP_UNAUTHORIZED` | 未登录 / JWT 失效 | 401 |
| `E_MCP_INTERNAL` | 内部错误 | 500 |

---

## 5. 鉴权与限流

- **JWT**（既有 AP-04）：`Authorization: Bearer <jwt>`
- **Workspace 权限**：所有写操作需校验 `user_id` 对 `workspace_id` 的成员关系（既有 `workspaces` 权限模型）
- **速率限制**：沿用既有 FastAPI 限流中间件（不引新限流）
- **审计**：所有写操作异步落 `mcp_tool_call_logs`（F-017）

---

## 6. 不在本期范围（端点层）

- ❌ 22 模块中其它 14 个端点（webhook / cron / 多 Runtime 协议转换 / K4 扫描等）—— 下期 NB-02
- ❌ 模板市场（NB-01 + B-13，本期仅官方 5 模板）
- ❌ 跨租户分享（B-02，本期不做）
- ❌ MCP 进程级调试（B-04，本期仅日志导出）
- ❌ Saga 补偿端点（M-C09，NB-02）

---

## 7. PR-01 冻结检查清单

> 本节端点**必须**在 P1 启动前同步到 `docs/specs/04-commands` §MCP 子节，并经过 2 人 Review。

- [ ] 8 个端点的 HTTP 方法、Path、Query、Body、Response、错误码
- [ ] 2 个 WS 事件的 Payload 字段
- [ ] Pydantic schemas 字段与类型
- [ ] 错误码清单 E_MCP_*
- [ ] 鉴权与 workspace 权限说明
- [ ] 至少 1 人（不含作者）Approve（PR-06）
- [ ] verify.bat 通过（PR-07）

---

*本 IC-MCP 是 MCP 接入**接口契约**唯一权威。PR-01 冻结后写入 `docs/specs/04-commands`，实现时按本契约 + schemas/mcp.py 落地。*
