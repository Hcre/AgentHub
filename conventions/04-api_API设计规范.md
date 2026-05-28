# API 设计规范 — AgentHub

> **本规范是 [ai-workflow 第二步·迭代开发 §2.1 实现](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md) 的细化**，约束 HTTP API + WebSocket 命令接口的设计。
>
> AgentHub 接口完整定义在 [docs/specs/04-commands_命令接口.md](../docs/specs/04-commands_命令接口.md)；本规范定义**设计原则**而非端点清单。AgentHub 用 FastAPI（async + Pydantic v2），主路径走 WebSocket，HTTP 用作配置/创建/历史查询。

---

## 一、红线（必守）

| # | 红线 | 怎么自动抓 |
|---|------|-----------|
| **AP-01** | 资源用名词复数 + kebab-case，URL 内无动词（特殊操作走 `POST /resource/:id/action`） | `spectral` OpenAPI lint |
| **AP-02** | 错误响应统一外层 `{"error": {"code": ..., "message": ...}}`；HTTP 状态码与 `error.code` 语义对齐 | 全局 exception_handler（§二）+ CR |
| **AP-03** | 所有接口默认需 JWT 认证（`Authorization: Bearer <token>`），公开接口显式标注 `@public` | FastAPI dependency 默认拦截 |
| **AP-04** | 所有 API 输入必须经 Pydantic v2 model 校验（落 [CR-05](02-coding_代码编写规范.md)） | tsc/mypy + CR |
| **AP-05** | API 版本号在 URL 路径 `/api/v1/...`；主版本号变 = 不兼容；同时维护 ≥ 2 个大版本 | URL lint + spec diff |
| **AP-06** | 向后兼容：不删 / 不重命名已有字段；新增字段必须为 optional | spec diff + CR |
| **AP-07** | WS 消息必须包含 `type` + `payload`；服务端推送带 `request_id` 与原 HTTP 请求关联 | CR |
| **PR-01** | API 接口先冻结再实现：endpoint 路径 + Request/Response Schema 在 spec 中冻结 → 2 人 Review → 才能开始实现 | 流程规则（见 [99-process-rules](99-process-rules_流程红线全集.md)） |

---

## 二、落地：统一响应 + 全局异常 + 输入校验

**FastAPI 全局异常处理（`backend/app/api/error_handlers.py`）**：

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from app.domain.errors import AppError

@app.exception_handler(AppError)
async def handle_app_error(req: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.http_status,
        content={"error": {"code": exc.code, "message": exc.message}},
    )

@app.exception_handler(ValidationError)
async def handle_validation(req: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": exc.errors()}},
    )

@app.exception_handler(Exception)
async def handle_unexpected(req: Request, exc: Exception):
    logger.exception("未处理异常 | path=%s", req.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "服务异常"}},
    )
```

**Pydantic v2 输入模型（`backend/app/schemas/agent.py`）**：

```python
from pydantic import BaseModel, Field

class AgentCreateIn(BaseModel):
    agent_system: Literal["claude", "codex", "trae"]
    name: str = Field(min_length=1, max_length=50)
    provider: str
    model: str
    api_key: SecretStr                            # 自动从日志中脱敏
    base_url: HttpUrl | None = None
    skills: list[str] = Field(default_factory=list, max_length=20)
```

**WS 消息契约（`backend/app/api/ws/protocol.py`）**：

```python
class WSMessage(BaseModel):
    type: Literal["chat.send", "chat.delta", "task.update", ...]
    request_id: str                                # 关联 HTTP/WS 上下文
    payload: dict
    ts: datetime
```

**OpenAPI lint —— `.spectral.yaml`**：

```yaml
extends: ["spectral:oas"]
rules:
  path-kebab-case:
    given: "$.paths[*]~"
    then: { function: pattern, functionOptions: { match: "^[a-z0-9-/{}]+$" } }
  no-verb-in-path:
    given: "$.paths[*]~"
    then: { function: pattern, functionOptions: { notMatch: "(get|create|update|delete)[A-Z]" } }
```

---

## 三、决策表 / 速查

### URL 与方法（REST 风格）

```
GET    /api/v1/agents             # 列表
POST   /api/v1/agents             # 创建
GET    /api/v1/agents/:id         # 详情
PATCH  /api/v1/agents/:id         # 部分更新
DELETE /api/v1/agents/:id         # 删除
GET    /api/v1/agents/:id/skills  # 子资源
POST   /api/v1/tasks/:id/cancel   # 特殊操作（非 CRUD）
```
层级 ≤ 3 层。

### 错误响应结构（AgentHub 现行约定）

```json
{ "error": { "code": "AGENT_NOT_FOUND", "message": "Agent abc-123 不存在" } }
```

### 成功响应

GET 列表 / 详情 / PATCH / POST 创建：**直接返回资源对象**（不强制外层包装，与 spec 现状对齐）。
```json
{ "id": "agent-001", "name": "FrontendAgent", "agent_system": "claude", ... }
```
列表带分页时：
```json
{ "items": [...], "total": 100, "page": 1, "page_size": 20 }
```

### 错误码（语义化字符串，禁数字魔法值）

| 类别 | 错误码示例 |
|------|-----------|
| 资源 | `AGENT_NOT_FOUND` / `TASK_NOT_FOUND` / `GROUP_NOT_FOUND` |
| 认证 | `UNAUTHORIZED` / `TOKEN_EXPIRED` / `INVALID_TOKEN` |
| 权限 | `FORBIDDEN` / `BOUNDARY_VIOLATION`（参考 [99-boundaries](99-boundaries_边界矩阵.md)） |
| 输入 | `VALIDATION_ERROR` / `MISSING_REQUIRED_FIELD` |
| 状态 | `INVALID_STATE_TRANSITION`（落 AR-05） |
| 配额 | `TOKEN_BUDGET_EXCEEDED` / `RATE_LIMITED` |
| 系统 | `INTERNAL_ERROR` / `LLM_PROVIDER_TIMEOUT` |

### HTTP 状态码

| HTTP | 场景 | error.code 示例 |
|------|------|----------------|
| 400 | 参数不合法 | `VALIDATION_ERROR` / `MISSING_REQUIRED_FIELD` |
| 401 | 未认证/过期 | `UNAUTHORIZED` / `TOKEN_EXPIRED` |
| 403 | 权限不足 | `FORBIDDEN` / `BOUNDARY_VIOLATION` |
| 404 | 不存在 | `AGENT_NOT_FOUND` |
| 409 | 冲突 | `INVALID_STATE_TRANSITION` |
| 422 | 语义错误 | `TOKEN_BUDGET_EXCEEDED` |
| 429 | 限流 | `RATE_LIMITED` |
| 500 | 服务端 | `INTERNAL_ERROR` |
| 503 | 上游不可用 | `LLM_PROVIDER_TIMEOUT` |

### 分页 / 版本 / 安全

| 项 | 约定 |
|----|------|
| 分页 | `?page=1&page_size=20`（默认 20，上限 100）；列表带 `total` |
| 排序 / 过滤 | `?sort_by=created_at&sort_order=desc`；`?status=active` |
| 版本 | URL 路径 `/api/v1/`；当前 v1 |
| 认证 | `Authorization: Bearer <jwt_token>` |
| CORS | 配置白名单（dev 允许 `http://localhost:5173`） |
| 限流 | 全局 60 req/min/IP；WS 单连接 10 msg/s |
| 密钥 | `api_key` 等敏感字段：入参用 `SecretStr`；出参一律 `api_key_encrypted` 或 `api_key_masked: "sk-...****"` |

### WebSocket 消息约定

```typescript
// Client → Server
{ type: "chat.send", request_id: "uuid", payload: { group_id, content } }

// Server → Client (流式)
{ type: "chat.delta", request_id: "uuid", payload: { agent_id, delta, done: false } }
{ type: "chat.delta", request_id: "uuid", payload: { agent_id, delta: "", done: true } }

// 错误
{ type: "error", request_id: "uuid", payload: { code, message } }
```

完整 WS 命令表见 `docs/specs/04-commands_命令接口.md §三`。

---

## 四、反模式

### ❌ 动词 URL
`GET /api/getAgentList`、`POST /api/createTask` → 一个资源裂成 4 个无关 URL。
✅ `/api/v1/agents` 一个资源 + HTTP 方法表达操作。

### ❌ 错误响应格式不一致
端点 A `{success: false, msg: ...}`、端点 B `{code: "ERR", message: ...}` → 前端每端点写一套解析。
✅ 全部 `{error: {code, message}}`，前端一个拦截器通吃。

### ❌ HTTP 200 + 错误
```json
HTTP 200 OK
{ "error": { "code": "AGENT_NOT_FOUND", ... } }
```
浏览器/SDK 重试逻辑、监控告警判错全部失效。
✅ HTTP 404 + body `{error:{code:"AGENT_NOT_FOUND",...}}`。

### ❌ 不兼容升级
v2 顺手把 `agent_id` 改成 `agentId` → 未迁移调用方生产事故。
✅ 新增 `agentId` 字段 + 保留 `agent_id`；监控旧字段调用量归零后再下线。

### ❌ 密钥/Token 出现在响应/日志
`{api_key: "sk-...xxx"}` 出现在 GET 响应或 INFO 日志 → 泄密风险（CR-10 + 02-§四 日志脱敏）。
✅ 用 `SecretStr` 入参；响应只返回 `api_key_masked` 或 `api_key_encrypted`；日志输出 `api_key=***`。

### ❌ WS 消息无 request_id
前端发送任务请求 → 服务端推 5 条 delta → 前端无法分清哪条是回应哪个请求（多 group/agent 并发场景必崩）。
✅ 客户端生成 `request_id` 随消息发送，服务端原样回带。

---

## 五、检查清单

- [ ] **AP-01** URL 名词复数 + kebab-case，无动词（spectral 已校）
- [ ] HTTP 方法语义正确（GET 读 / POST 建 / PUT 全量 / PATCH 部分 / DELETE 删）
- [ ] **AP-02** 错误响应统一 `{error: {code, message}}`，HTTP 状态码对齐
- [ ] 错误码用语义化字符串（`AGENT_NOT_FOUND`），不用数字魔法值
- [ ] **AP-03** 默认需 JWT；公开接口显式 `@public` 标注
- [ ] **AP-04** 输入用 Pydantic v2 model，含 Field 校验
- [ ] **AP-05** 版本号在 URL 路径
- [ ] **AP-06** 未删 / 重命名已有字段（向后兼容）
- [ ] **AP-07** WS 消息含 `type` + `payload` + `request_id`
- [ ] **PR-01** API 接口已在 spec 冻结 + 2 人 Review，再开始实现
- [ ] 分页参数统一（`page` + `page_size`）
- [ ] 密钥/Token 字段用 `SecretStr` 入参；出参脱敏
- [ ] CORS 白名单 + 全局限流已配
- [ ] 文档同步：`docs/specs/04-commands_命令接口.md` 已更新

---

## 六、关联

| 方向 | 链接 |
|------|------|
| 细化自 | [ai-workflow 第二步 §2.1 实现](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md) |
| 完整 endpoint 清单 | [docs/specs/04-commands_命令接口.md](../docs/specs/04-commands_命令接口.md) |
| CLI 适配器 API 流程 | [docs/specs/04b-adapter-cli-flow_适配器CLI流程分析.md](../docs/specs/04b-adapter-cli-flow_适配器CLI流程分析.md) |
| Adapter 接口契约 | [docs/specs/04c-adapter-interface_适配器接口规范.md](../docs/specs/04c-adapter-interface_适配器接口规范.md) |
| 错误处理 / 异常类型 | [02-代码编写规范 §四](02-coding_代码编写规范.md) |
| Agent 权限 / 边界 | [99-boundaries_边界矩阵](99-boundaries_边界矩阵.md) |
| 流程红线（接口先行）| [99-process-rules_流程红线全集 PR-01](99-process-rules_流程红线全集.md) |
| API 路由全景图 | [08-代码理解与图谱规范](08-code-understanding_代码理解与图谱规范.md) |

---

## 更新记录

| 日期 | 版本 | 变更说明 |
|------|------|---------|
| 2026-05-28 | v3.0 | 按模板骨架重写；红线新增 AP-01~07；错误响应改为 AgentHub 实际约定 `{error:{code,message}}`（与模板的 `{code,message,data}` 不同）；错误码改语义化字符串；新增 WS 消息契约 + request_id 必带；接入 PR-01 接口先行流程 |
