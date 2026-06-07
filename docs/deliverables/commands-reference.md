# AgentHub 命令速查（REST + WebSocket）

> 版本: v1.0 | 2026-06-07 | 权威契约来源: [docs/specs/04-commands_命令接口.md v2.2](../specs/04-commands_命令接口.md)
>
> 本文件 = **快速参考表**，速查"哪些端点 + 怎么调用 + 错误码"。完整契约（请求体 schema + 错误体 + WS 信封）见权威文件。
>
> **数量**: 37 REST 端点（不含 MCP 8 端点，共 45）/ 11 WebSocket 事件 / 4 错误码族 / 13 WS 信封规范

---

## 〇、基础约定

| 项 | 值 |
|----|-----|
| Base URL | `http://localhost:8000/api` |
| WebSocket | `ws://localhost:8000/ws/sessions/{id}` |
| Content-Type | `application/json` |
| 鉴权 | `Authorization: Bearer <jwt_token>`（L4 AP-03）|
| 错误响应 | `{"error": {"code": "E_XXX", "message": "...", "details": {...}}}`（L4 AP-02）|
| 时间格式 | ISO 8601 / TIMESTAMPTZ |
| ID 格式 | UUID v4 |
| 速率限制 | 100 req/min（middleware RateLimit）|

---

## 一、REST 端点索引（37 个，按域分组）

### 1.1 全局设置 API（2）

| Method | Path | 说明 | 错误码 |
|--------|------|------|--------|
| `GET`  | `/api/settings` | 获取全局设置（coordinator 模型 + defaults + approval_mode）| 401 |
| `PATCH`| `/api/settings` | 修改全局设置 | 401 / 422 |

### 1.2 Agent API（9）

| Method | Path | 说明 | 错误码 |
|--------|------|------|--------|
| `POST`  | `/api/agents` | 创建 Agent（表单式：选系统→配模型→填 api_key）| 401 / 409 `E_AGENT_NAME_CONFLICT` / 422 `E_AGENT_API_KEY_INVALID` / 422 `E_AGENT_SYSTEM_INVALID` / 422 `E_AGENT_CLI_NOT_AVAILABLE` |
| `POST`  | `/api/agents/draft` | 对话式创建（自然语言 → system_prompt 草案 + 推荐 tags）| 401 / 502 `E_AGENT_DRAFT_LLM_UNAVAILABLE` |
| `GET`   | `/api/agents` | 列表 `?agent_system=claude&status=online&capability=react` | 401 |
| `GET`   | `/api/agents/{id}` | 详情（含 channels/tasks/capability_tags/settings/memory_config）| 401 / 404 `E_AGENT_NOT_FOUND` |
| `PATCH` | `/api/agents/{id}` | 更新（name/role/provider/model/api_key/base_url/skills/tags/system_prompt/settings）| 401 / 404 / 409 / 422 |
| `DELETE`| `/api/agents/{id}` | 软删除（从群组中移除）| 401 / 404 |
| `GET`   | `/api/agents/{id}/tasks` | Agent 任务列表 `?status=running&page=1` | 401 / 404 |
| `GET`   | `/api/agents/{id}/activities` | 活动日志 `?page=1` | 401 / 404 |
| `GET`   | `/api/agents/{id}/memory` | 记忆（L1-L4 记忆参数 + 记忆条目）| 401 / 404 |
| `PATCH` | `/api/agents/{id}/memory` | 更新记忆配置 | 401 / 404 / 422 |
| `GET`   | `/api/agents/{id}/channels` | 所属群组列表 | 401 / 404 |
| `GET`   | `/api/agents/{id}/workspace_path` | 工作目录（[P1-1] 工作目录 UI）| 401 / 404 |

> 9 + 4 = 13 端点（含子资源）。注：9 处只列了 9 个核心 + 4 子资源标 `[可选]`。

### 1.3 Group API（7）

| Method | Path | 说明 | 错误码 |
|--------|------|------|--------|
| `POST`  | `/api/groups` | 创建群组（自动生成 Coordinator, `is_system=true`）| 401 / 422 |
| `GET`   | `/api/groups` | 列表 | 401 |
| `GET`   | `/api/groups/{id}` | 详情（members + coordinator）| 401 / 404 |
| `PATCH` | `/api/groups/{id}` | 更新 name/description | 401 / 404 |
| `DELETE`| `/api/groups/{id}` | 级联删除协调者 | 401 / 404 |
| `POST`  | `/api/groups/{id}/members` | 添加成员 `{"agent_id": "uuid"}` | 401 / 404 / 409 `E_GROUP_MEMBER_DUPLICATE` |
| `DELETE`| `/api/groups/{id}/members/{agent_id}` | 移除成员 | 401 / 404 |

### 1.4 Session & Message API（7）

| Method | Path | 说明 | 错误码 |
|--------|------|------|--------|
| `POST`  | `/api/sessions` | 创建会话 `{type, group_id?, agent_id?, title?}` | 401 / 422 |
| `GET`   | `/api/sessions` | 列表（[P2] `?q=&archived=&pinned_only=&page=1`）| 401 |
| `GET`   | `/api/sessions/{id}` | 详情 | 401 / 404 |
| `GET`   | `/api/sessions/{id}/messages` | 消息历史 `?before=uuid&limit=50` | 401 / 404 |
| `GET`   | `/api/sessions/{id}/history` | CLI 完整 transcript.jsonl（含 tool_call/thinking）| 401 / 404 |
| `POST`  | `/api/sessions/{id}/messages` | 发送 `{content, mentions, dispatch_mode, reply_to?, content_type?}` | 401 / 404 / 422 `E_MESSAGE_REPLY_TARGET_NOT_FOUND` |
| `POST`  | `/api/messages/{id}/pin?session_id=<sid>` | Pin（[P0-4 修复中] session 所有权校验）| 401 / 403 `E_MESSAGE_PIN_NOT_OWNER` / 404 / 422 `E_MESSAGE_PIN_SESSION_MISMATCH` |
| `DELETE`| `/api/messages/{id}/pin?session_id=<sid>` | 取消 Pin | 401 / 404 |
| `POST`  | `/api/messages/{id}/regenerate` | 重新生成（[P0-5 扩展] 文档/Diff/Code）| 401 / 404 / 502 `E_REGENERATE_TIMEOUT` |
| `POST`  | `/api/sessions/{id}/pin-top` | 会话置顶（[P2] B-1-P0-S02）| 401 / 404 |
| `DELETE`| `/api/sessions/{id}/pin-top` | 取消置顶 | 401 / 404 |

### 1.5 Task API（5）

| Method | Path | 说明 | 错误码 |
|--------|------|------|--------|
| `POST`  | `/api/tasks` | 手动创建 `{title, assignee_id?, parent_task_id?, ...}` | 401 / 422 |
| `GET`   | `/api/tasks` | 列表 `?status=running,pending&priority=high&assignee_id=&tags=&due_before=&sort_by=` | 401 |
| `GET`   | `/api/tasks/{id}` | 详情（含子任务 + DAG 依赖）| 401 / 404 |
| `PATCH` | `/api/tasks/{id}` | 更新 status/priority/assignee_id/due_date/tags | 401 / 404 / 422 |
| `GET`   | `/api/tasks/{id}/events` | 事件流（task_events / 状态转换历史）| 401 / 404 |
| `GET`   | `/api/tasks/{id}/artifacts` | 任务制品（输入/输出/错误/Token 用量）| 401 / 404 |

### 1.6 Inbox & Approval API（6）

| Method | Path | 说明 | 错误码 |
|--------|------|------|--------|
| `GET`   | `/api/inbox` | 收件箱 `?category=all|approval|task&is_read=false&page=1` | 401 |
| `GET`   | `/api/inbox/unread-count` | 未读统计 `{total, by_category}` | 401 |
| `PATCH` | `/api/inbox/read` | 标记已读 `{notification_ids: [uuid...]}` | 401 |
| `POST`  | `/api/approvals/{task_id}/approve` | 审批通过 | 401 / 404 |
| `POST`  | `/api/approvals/{task_id}/reject` | 审批拒绝 | 401 / 404 |
| `POST`  | `/api/approvals/{task_id}/edit` | 编辑后提交 `{payload: {edits: {...}}}` | 401 / 404 / 422 |
| `POST`  | `/api/approvals/{task_id}/respond` | 补充信息 `{payload: {response: "..."}}` | 401 / 404 |
| `GET`   | `/api/inbox/calendar` | 日历事件 `?from=&to=` | 401 |

### 1.7 Attachment API（3，[P0-3]）

| Method | Path | 说明 | 错误码 |
|--------|------|------|--------|
| `POST`  | `/api/attachments` | Multipart 上传（10 MiB max，7 MIME：png/jpg/gif/webp/pdf/zip/txt）| 401 / 413 `E_ATTACHMENT_TOO_LARGE` / 415 `E_ATTACHMENT_MIME_UNSUPPORTED` |
| `GET`   | `/api/attachments/{id}` | 下载/预览 | 401 / 404 |
| `DELETE`| `/api/attachments/{id}` | 删除 | 401 / 404 |

### 1.8 Usage API（3，[P1-2] Token 消耗监控）

| Method | Path | 说明 | 错误码 |
|--------|------|------|--------|
| `GET`   | `/api/usage` | 全局 `?agent_id=&session_id=&window=1h|24h|7d` | 401 |
| `GET`   | `/api/usage/{agent_id}` | Agent 维度（by_session + budget_pct）| 401 / 404 `E_USAGE_AGENT_NOT_FOUND` |
| `GET`   | `/api/usage/sessions/{session_id}` | Session 维度（by_agent + by_msg）| 401 / 404 |

### 1.9 CLI Scan API（2，[P1-3] CLI PATH 扫描）

| Method | Path | 说明 | 错误码 |
|--------|------|------|--------|
| `GET`   | `/api/cli/scan` | CLI 二进制扫描结果 `?bins=claude,codex,opencode,pi,trae` | 401 |
| `POST`  | `/api/cli/scan/refresh` | 手动重新扫描 | 401 / 202（async）|

### 1.10 MCP API（8，[🔒 PR-01 冻结草案] 详见 [04-commands §2.6](../specs/04-commands_命令接口.md#26-mcp-api--pr-01-冻结草案--2026-06-03--待-2-人-review)）

| Method | Path | 说明 | 错误码 |
|--------|------|------|--------|
| `GET`   | `/api/mcp/market` | 市场列表（分页 + 筛选）| 401 `E_MCP_UNAUTHORIZED` / 403 `E_MCP_PERMISSION_DENIED` / 422 |
| `GET`   | `/api/mcp/market/{mcp_id}` | 市场详情 | 401 / 404 `E_MCP_NOT_FOUND` |
| `GET`   | `/api/mcp/market/templates` | 官方模板（本期 5）| 401 / 403 |
| `POST`  | `/api/mcp/installations` | 安装（F-004 幂等）| 400 / 401 / 403 / 404 / 409 `E_MCP_NAME_CONFLICT` / 422 / 500 `E_MCP_INSTALL_TIMEOUT` / 500 `E_MCP_INSTALL_DEPENDENCY_MISSING` / 500 `E_MCP_INSTALL_PERMISSION_DENIED` |
| `DELETE`| `/api/mcp/installations/{id}` | 卸载 | 401 / 403 / 404 / 409（仍有 active binding）|
| `POST`  | `/api/mcp/bindings` | 绑定 Agent + installation（tool_subset 可选）| 400 / 401 / 403 / 404 / 409 `E_MCP_BINDING_CONFLICT` / 500 |
| `DELETE`| `/api/mcp/bindings/{id}` | 解绑 | 401 / 403 / 404 / 500 |
| `POST`  | `/api/mcp/servers` | 自建 MCP（dry_run 验证）| 400 / 401 / 403 / 409 `E_MCP_SLUG_CONFLICT` / 422 `E_MCP_SCHEMA_INVALID` / 422 `E_MCP_VERSION_TOO_LONG` / 422 `E_MCP_DRY_RUN_TIMEOUT` / 422 `E_MCP_DRY_RUN_FAILED` / 500 |

### 1.11 Deploy API（3，[P2-6.4.4] 部署卡）

| Method | Path | 说明 | 错误码 |
|--------|------|------|--------|
| `POST`  | `/api/deployments` | 创建部署 `{session_id, target, entry_file?, framework?}` | 401 / 422 |
| `GET`   | `/api/deployments/{id}` | 查询 `{status, preview_url, build_logs, ttl}` | 401 / 404 |
| `DELETE`| `/api/deployments/{id}` | 销毁部署 | 401 / 404 |

---

## 二、WebSocket 事件协议（11 事件）

### 2.1 连接

```
URL: ws://localhost:8000/ws/sessions/{id}
心跳: client→server: {"type":"ping"} / server→client: {"type":"pong"}  间隔 30s
认证: 连接时携带 Bearer token（Query param ?token= 或首条消息）
```

### 2.2 信封（AP-07，request_id 贯穿）

```json
// 客户端 → 服务端
{
  "type": "<event_type>",
  "request_id": "<uuid>",  // 可选（用于关联 client→server 响应）
  "payload": { /* 事件特定字段 */ }
}

// 服务端 → 客户端
{
  "type": "<event_type>",
  "request_id": "<uuid>",  // 必有（按 AP-07）
  "payload": { /* 事件特定字段 */ }
}
```

### 2.3 客户端 → 服务端（4 事件）

| Event Type | Payload | 说明 |
|------------|---------|------|
| `message:send` | `{content, mentions?, dispatch_mode?, reply_to?, content_type?}` | 发消息 |
| `approval:decide` | `{task_id, decision, payload?}` | 审批决策（approve/reject/edit/respond）|
| `message:read` | `{message_ids: [uuid...]}` | 标记已读 |
| `tool_call:cancel` | `{request_id}` | 取消工具调用（P4 / MCP F-016）|

### 2.4 服务端 → 客户端（7 事件）

| Event Type | Payload | 触发时机 |
|------------|---------|----------|
| `message:stream` | `{message_id, agent_name, chunk, index}` | 流式输出逐 token |
| `message:stream_end` | `{message_id, content_type, tokens_used}` | 流式结束 |
| `task:progress` | `{task_id, state, step, progress}` | 任务进度更新 |
| `approval:required` | `{task_id, agent_name, reason, checkpoint}` | 需要用户审批 |
| `inbox:update` | `{unread_count, latest}` | 收件箱新通知 |
| `token:update` | `{session_tokens, daily_tokens, daily_budget}` | Token 消耗实时推送 |
| `message:pin_changed` | `{message_id, session_id, pinned, pinned_by}` | Pin 状态变更（[P0-4 修复]）|
| `session:pin_changed` | `{session_id, pinned}` | 会话置顶状态变更 |
| `tool_call:request` | `{request_id, trace_id, agent_id, binding_id, tool_name, args, ts}` | 工具调用请求（P4 / F-014）|
| `tool_call:progress` | `{request_id, trace_id, binding_id, tool_name, progress, message, duration_ms}` | 工具调用进度 |
| `tool_call:response` | `{request_id, trace_id, binding_id, tool_name, result, duration_ms}` | 工具调用完成 |
| `tool_call:error` | `{request_id, trace_id, binding_id, tool_name, error_code, error_message, duration_ms}` | 工具调用失败 |

> 11 事件 = 4 客户端 → 服务端 + 7 服务端 → 客户端（含 message:stream / stream_end / task:progress / approval:required / inbox:update / token:update + 4 MCP 工具调用事件）。

---

## 三、错误码字典

### 3.1 通用（AP-02，4xx/5xx）

| HTTP | code 族 | 含义 |
|------|---------|------|
| 400 | `E_BAD_REQUEST` | 请求体格式错 |
| 401 | `E_AUTH_REQUIRED` / `E_AUTH_TOKEN_INVALID` / `E_AUTH_TOKEN_EXPIRED` | 鉴权失败 |
| 403 | `E_PERMISSION_DENIED` | 权限不足 |
| 404 | `E_NOT_FOUND` | 资源不存在 |
| 409 | `E_CONFLICT` | 资源冲突 |
| 413 | `E_PAYLOAD_TOO_LARGE` | 请求体超限 |
| 415 | `E_UNSUPPORTED_MEDIA_TYPE` | MIME 不支持 |
| 422 | `E_VALIDATION_FAILED` | Pydantic 校验失败 |
| 429 | `E_RATE_LIMITED` | 速率超限 |
| 500 | `E_INTERNAL` | 服务器内部错 |
| 502 | `E_UPSTREAM` / `E_LLM_UNAVAILABLE` | 上游服务不可用 |
| 504 | `E_UPSTREAM_TIMEOUT` | 上游超时 |

### 3.2 业务（按域分组）

| 域 | code | HTTP | 含义 |
|----|------|------|------|
| Agent | `E_AGENT_NAME_CONFLICT` | 409 | Agent name 重复 |
| Agent | `E_AGENT_API_KEY_INVALID` | 422 | api_key 格式错 |
| Agent | `E_AGENT_SYSTEM_INVALID` | 422 | agent_system 非法 |
| Agent | `E_AGENT_CLI_NOT_AVAILABLE` | 422 | CLI 不在 PATH（[P1-3] 联动）|
| Agent | `E_AGENT_DRAFT_LLM_UNAVAILABLE` | 502 | 对话式创建 LLM 不可用 |
| Group | `E_GROUP_MEMBER_DUPLICATE` | 409 | 成员已存在 |
| Group | `E_COORDINATOR_IMMUTABLE` | 422 | 协调者不可移除 |
| Message | `E_MESSAGE_REPLY_TARGET_NOT_FOUND` | 422 | reply_to 不存在/跨 session |
| Message | `E_MESSAGE_PIN_NOT_OWNER` | 403 | [P0-4] Pin 跨用户 |
| Message | `E_MESSAGE_PIN_SESSION_MISMATCH` | 422 | [P0-4] session_id 不一致 |
| Message | `E_REGENERATE_TIMEOUT` | 502 | [P0-5] 重新生成超时 |
| Attachment | `E_ATTACHMENT_TOO_LARGE` | 413 | 附件超 10 MiB |
| Attachment | `E_ATTACHMENT_MIME_UNSUPPORTED` | 415 | MIME 不在 7 种内 |
| Usage | `E_USAGE_AGENT_NOT_FOUND` | 404 | [P1-2] Agent 不存在 |
| MCP | `E_MCP_NOT_FOUND` | 404 | mcp_id/installation/binding 不存在 |
| MCP | `E_MCP_NAME_CONFLICT` | 409 | 同 workspace instance_name 冲突 |
| MCP | `E_MCP_SLUG_CONFLICT` | 409 | slug 冲突 |
| MCP | `E_MCP_BINDING_CONFLICT` | 409 | 重复绑定 |
| MCP | `E_MCP_INSTALL_TIMEOUT` | 500 | 安装超时 |
| MCP | `E_MCP_INSTALL_DEPENDENCY_MISSING` | 500 | 依赖缺失 |
| MCP | `E_MCP_INSTALL_PERMISSION_DENIED` | 500 | 安装权限不足 |
| MCP | `E_MCP_PERMISSION_DENIED` | 403 | MCP 通用权限 |
| MCP | `E_MCP_DRY_RUN_TIMEOUT` | 422 | 干跑超时 30s |
| MCP | `E_MCP_DRY_RUN_FAILED` | 422 | 干跑失败 |
| MCP | `E_MCP_SCHEMA_INVALID` | 422 | config_schema 校验失败 |
| MCP | `E_MCP_VERSION_TOO_LONG` | 422 | version > 50 字符 |
| MCP | `E_MCP_BATCH_TOO_LARGE` | 422 | 批量安装 > 50 |
| MCP | `E_MCP_TOOL_CALL_TIMEOUT` | 500 | 工具调用超时 |
| MCP | `E_MCP_TOOL_CALL_CANCELLED` | 500 | 工具调用取消 |
| MCP | `E_MCP_TOOL_CALL_RUNTIME_ERROR` | 500 | 工具调用运行时错 |
| MCP | `E_MCP_UNAUTHORIZED` | 401 | MCP 未登录 |
| MCP | `E_MCP_INTERNAL` | 500 | MCP 内部错 |
| Deploy | `E_DEPLOY_TIMEOUT` | 504 | [P2] 部署超时 |

---

## 四、调用示例（cURL）

### 4.1 创建 Agent

```bash
curl -X POST http://localhost:8000/api/agents \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_system": "claude",
    "name": "DataAnalyst",
    "avatar": "https://example.com/avatar.png",
    "role": "Python 数据分析",
    "provider": "deepseek",
    "model": "deepseek-chat",
    "api_key": "sk-xxx",
    "base_url": "https://api.deepseek.com",
    "skills": ["python", "pandas"],
    "capability_tags": ["python", "data"]
  }'
```

### 4.2 发送消息（私聊）

```bash
curl -X POST http://localhost:8000/api/sessions/{session_id}/messages \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "用 React 写一个计数器",
    "dispatch_mode": "direct",
    "content_type": "text"
  }'
```

### 4.3 Pin 消息

```bash
curl -X POST "http://localhost:8000/api/messages/{message_id}/pin?session_id=${SESSION_ID}" \
  -H "Authorization: Bearer ${TOKEN}"
```

### 4.4 WebSocket 连接（浏览器 JS）

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/sessions/${sessionId}?token=${token}`);

ws.onopen = () => {
  // 发送消息
  ws.send(JSON.stringify({
    type: "message:send",
    request_id: crypto.randomUUID(),
    payload: {
      content: "hello",
      dispatch_mode: "direct"
    }
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case "message:stream":
      // 追加 msg.payload.chunk
      break;
    case "message:stream_end":
      // 流式结束
      break;
    case "approval:required":
      // 显示审批卡片
      break;
  }
};

// 心跳
setInterval(() => ws.send(JSON.stringify({ type: "ping" })), 30000);
```

---

## 五、API 演化与版本

| 版本 | 日期 | 端点增量 | 来源 |
|------|------|---------|------|
| v0 | 2026-05-20 | Agent/Group/Session/Message/Task 5 域基础 | M1 出口 |
| v1 | 2026-05-23 | Pin/DiffPreview/工作目录/Inbox | M2-M4 |
| v2 | 2026-06-03 | MCP 8 端点（PR-01 冻结草案）| [ADR-0003](../worklogs/decisions/0003-mcp-url-prefix-and-ap05-deferral.md) |
| v2.1 | 2026-06-04 | MCP F2 2 端点（bind/unbind）+ UseAgentPwdAuth | MCP F1+F2 收束 |
| v2.2 | 2026-06-07 | 17 BDD 场景（契约冻结）+ P0-4 所有权校验 | M5 5.5 沉淀 |
| 计划 v3 | 待定 | P1-2 Usage 3 端点 / P1-3 CLI Scan 2 端点 / [P2] 会话置顶 + Deploy 3 端点 + 移动端 / 部署卡 | roadmap §6 + §8.3 |

> **AP-05 暂缓说明**：当前无 URL 版本段（`/api/mcp/...` 而非 `/api/v1/mcp/...`），依据 [ADR-0003](../worklogs/decisions/0003-mcp-url-prefix-and-ap05-deferral.md)。未来引入版本段时机：跨版本不兼容 schema 变更时。

---

## 六、关联文档

| 方向 | 链接 |
|------|------|
| 完整契约（权威）| [docs/specs/04-commands_命令接口.md v2.2](../specs/04-commands_命令接口.md) |
| 17 BDD 验收场景 | [04-commands §六](../specs/04-commands_命令接口.md#六bdd-验收场景覆盖-prd-6-大核心功能--roadmap-8-p0p1p2) |
| 数据模型（5 主表）| [docs/specs/03-data-model_数据模型.md](../specs/03-data-model_数据模型.md) |
| 5 层架构 | [docs/specs/01-architecture_架构定义.md](../specs/01-architecture_架构定义.md) |
| API 7 红线 | [docs/conventions/04-api_API设计规范.md](../conventions/04-api_API设计规范.md) |
| MCP URL 决策 | [ADR-0003](../worklogs/decisions/0003-mcp-url-prefix-and-ap05-deferral.md) |
| MCP 注入原则 | [ADR-0005](../worklogs/decisions/0005-mcp-attach-request-carried.md) + [ADR-0006](../worklogs/decisions/0006-mcp-injection-per-runtime-isolated-channel.md) |
| Roadmap 状态 | [docs/plan/开发清单_roadmap.md §6 M5 5.5](../plan/开发清单_roadmap.md) |

---

## 更新记录

| 日期 | 版本 | 变更说明 |
|------|------|---------|
| 2026-06-07 | v1.0 | 首版（37 REST 端点 + 11 WS 事件 + 错误码字典），基于 04-commands v2.2 整理 |
