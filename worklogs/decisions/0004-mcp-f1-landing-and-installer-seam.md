# ADR-04：MCP F1 落地口径 — 二次对账（schema↔代码）+ 安装探针架构

> 日期：2026-06-03 | 状态：**Accepted** | 决策人：袁（Claude Agent 协助）
> 关联：[ADR-03](0003-mcp-url-prefix-and-ap05-deferral.md) · [README-REVISION §9](../../docs/plan/后续升级计划/MCP接入/README-REVISION.md) · `docs/specs/03-data-model` §MCP · `docs/specs/04-commands` §2.6 · 收束报告 [`docs/reports/收束报告-MCP-F1.md`](../../docs/reports/收束报告-MCP-F1.md)

## 一、背景

MCP F1（市场 + 安装）实现前，对修订版计划逐文件复核 plan→code，发现首轮可行性 review（宏观路径审计）漏掉一类缺陷：**计划引用了真实代码里不存在的表/依赖/协议/类型**。共 10 项（R1-R10，详见 README-REVISION §9）。这些若直接落代码会迁移失败 / 测试全红 / 契约冲突。ADR-03 已记 URL 前缀与 AP-05；本 ADR 记 F1 实现的**数据/鉴权/类型/安装架构**落地决策。

## 二、关键决策

### D1 租户维度 = 裸 UUID 无 FK（R1/R2）
现库无 `workspaces`、`users` 表（workspace = `sessions.workspace_path` 字符串；user = JWT subject；`NotificationModel.user_id` 已是裸 Uuid 先例）。

- `workspace_id`（installations / tool_call_logs）：**裸 UUID 无 FK，暂存 `session_id`** 作 workspace 维度 stand-in，前向兼容未来真实 workspaces 表。
- `created_by` / `installed_by`：**裸 UUID 无 FK**，存 JWT `sub`。
- 仅对真实存在的表加 FK：`agent_id`→`agents`、`mcp_id`→`mcp_servers`、`installation_id`→`workspace_mcp_installations`、`binding_id`→`agent_mcp_bindings`。

### D2 鉴权 = JWT 仅解析，不做成员校验（R3）
全库现状零端点强制 JWT（`decode_access_token` 此前从未被调用）。MCP 不单独制造鉴权门槛：新增 `get_current_user`（`HTTPBearer(auto_error=False)`）**仅解析** Bearer，取 `sub` 充 `created_by`/`installed_by`；无 token → 匿名（不抛 401）。workspace 成员校验因无 membership 模型**暂缺**，随全局鉴权统一补（NB-02）。

### D3 错误体 = 沿用全库 `{detail}`（R9）
`main.py` 异常处理实际发 `{"detail": str}`（全库违反 AP-02，早于 MCP）。MCP 端点**对齐现状**，不单独引入 `{error:{code,message}}`；`E_MCP_*` 作语义/日志逻辑码。AP-02 统一信封随全库清理一起补（NB-02）。

### D4 列类型 = 可移植（R10，强制约束）
测试经 `conftest.py` 走 SQLite `Base.metadata.create_all`。MD-MCP 的 `JSONB/TEXT[]/ENUM/BIGSERIAL/CHAR/GIN` 在 SQLite 不可用 → 模型/迁移一律用 `JSON / String / BigInteger().with_variant(Integer,"sqlite") / DateTime(tz)`，无 GIN（`tags` 普通存 JSON）。PG 专属优化 defer（NB-02）。

### D5 安装架构 = 校验探针 + McpInstaller 端口（非进程拉起）
本架构下 MCP server 不由后端长驻，其 config 在**绑定时**经 `attach_mcp` 注入 Agent 的 CLI 运行时（P2）。故 F1「安装」的真实行为 = **结构校验**（stdio 需 `command`，远程需合法 `url`；失败 → 422 `E_MCP_SCHEMA_INVALID`），而非拉起进程。抽象 `McpInstaller` 端口（L2）+ `LocalMcpInstaller`（L1）做校验；真实可达性/进程探针/dry-run 是 P2/P3 扩展点（在实现内补，不改端口签名）。安装幂等键 = `(workspace_id + mcp_id + args_hash)`。

## 三、影响 / 后续

- spec 已三处同步（PR-09）：`03-data-model §MCP`、`04-commands §2.6`、`README-REVISION §9`。
- NB-02 backlog（defer 项）：真实 workspaces/users 实体 + FK 回填 · 全局 JWT 鉴权 + workspace 成员校验 · AP-02 错误信封统一 · PG 专属类型/分区优化 · API 版本化（AP-05，见 ADR-03）。
- P2 起点：`attach_mcp(...)` 扩展点（`domain/llm/protocol.py::AgentRuntime` + 3 runtime 实现）；`agent_mcp_bindings` 的 `UNIQUE(agent_id, installation_id)` 与软删 rebind 冲突需一并解（见 `models.py` NOTE）。
- 方法固化：plan 写 `FK→X / 既有 X / 复用现有 X` 必须逐文件求证（查 `models.py`/`deps.py`/`ws/`/`conftest.py`），列入 PR-09 自检。
