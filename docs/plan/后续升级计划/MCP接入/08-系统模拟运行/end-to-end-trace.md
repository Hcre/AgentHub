# 端到端执行轨迹 — AgentHub MCP 接入（修订版）

> ⚠️ **路径 ERRATA（2026-06-03 整理）**：本文出现的 `api/v1/mcp`、`application/mcp/*`、`infrastructure/agentruntime/mcp_injector`、`infrastructure/db/models/mcp.py`、`docker_sandbox`、`BaseAgentRuntime.spawn` 等为修订前命名，仅用于标注"代码空间待落地"。实际落点以 `06-详细设计/FS-MCP §1` + `docs/specs/04-commands §2.6` 为准（URL `/api/mcp/`，无 `/v1/`；`attach_mcp` 落 `domain/llm/protocol.py::AgentRuntime`）。

> **版本**：V1.0-rev（2026-06-03 重写）
> **棒位**：⑧ 系统运行模拟与闭环
> **场景**：R-03（Agent 使用者）Alice 在 AgentHub 安装并绑定一个 MCP 工具
> **结论先给**：
> - 🟢 **计划空间自洽**（按修订后 FS/SA/MD/IC/UI 切片，链路设计上可走通）
> - 🔴 **代码空间未启动**（`src/backend/app/` 与 `src/frontend/src/` 均无 MCP 实现，0 命中）
> - 真正"零修改走通"需在 P1 → P2 → P3 → P4 4 阶段实施后
> **单一权威入口**：[`../README-REVISION.md`](../README-REVISION.md)

---

## 0. 修订要点

| 项 | 上一版 | **修订版** |
|----|--------|-----------|
| 场景基线 | 22 模块 / 30 实体 / 132 异常全部就位（虚构空间） | 修订后 4 表 + 8+2 端点 + 3 页 + 1 Tab + 1 store（计划空间） |
| 闭环结论 | 🟢 三层闭环均建立且收敛；零修改可走通（**仅在虚构 `src/agenthub/` 空间成立**） | 🟢 计划空间自洽（设计无矛盾） / 🔴 代码空间未启动（4 阶段实施后才可走通） |
| 拍数 | 18 拍 | 仍 18 拍，但**每拍的"就位"判定基线改成修订后模块** |
| 沙箱路径 | macos_sandbox / windows_jobobj / linux_cgroup 矩阵 | 单 Docker 容器（E-03 简化） |
| 进程路径 | 自建 `pool` / `eventbus` | 复用 `BaseAgentRuntime` + CLI Adapter + `attach_mcp(...)` |
| 工具调用 SDK | F-013 SDK Adapter | **下期 NB-02**；本期仅 CLI |

---

## 1. 真实代码空间现状（2026-06-03 扫描）

| 检查项 | 结果 |
|--------|------|
| `src/backend/app/infrastructure/db/models/mcp.py` | ❌ 不存在 |
| `src/backend/app/api/v1/mcp.py` | ❌ 不存在 |
| `src/backend/app/api/ws/toolcall.py` | ❌ 不存在（既有 ws/chat.py 是聊天通道） |
| `src/backend/app/domain/mcp/` | ❌ 不存在 |
| `src/backend/app/application/mcp/` | ❌ 不存在 |
| `src/backend/app/infrastructure/agentruntime/mcp_injector.py` | ❌ 不存在 |
| `src/backend/app/infrastructure/docker_sandbox/` | ❌ 不存在 |
| `src/frontend/src/pages/McpMarketPage.tsx` | ❌ 不存在（无 `pages/` 目录） |
| `src/frontend/src/components/mcp/` | ❌ 不存在 |
| `src/frontend/src/components/agent/AgentDetailPage.tsx` 现有 4 Tab | ✅ 已存在（概览/能力/记忆/设置），**无 MCP 接入** |
| `src/frontend/src/components/chat/MessageBubble.tsx` | ✅ 已存在（可扩展嵌入 ToolCallBubble） |
| `src/backend/alembic/versions/0006_*` | ❌ 不存在（既有 0001-0005 不可见） |
| 端点 8+2 全部实现 | ❌ 0/10 |
| UI 组件全部实现 | ❌ 0/6 |
| 文档引用真实代码 | 🔴 0%（原版引用 `src/agenthub/`，与真实 0 匹配） |

> **结论**：原版"零修改可走通"在**真实代码空间**完全不成立。本文档是修订版模拟：把"就位"判定从「计划自身有」改成「真实代码树有」，于是结论从 🟢 翻转为 🔴。

---

## 2. 18 拍端到端执行轨迹（修订后）

> 每拍标注：**真实代码状态**（✅ 已实现 / ❌ 未实现 / ⏳ 修订后规划）+ **修订后模块归属**。

### 拍 1：用户发起「浏览 MCP 市场」
- **修订后模块**：`L4 API GET /api/v1/mcp/market` + `L5 McpMarketPage.tsx`
- 真实状态：❌（前后端均未实现）
- 实施后行为：LeftPanel「MCP 市场」→ `/mcp-market` → `mcpApi.listMarket()` → 后端 SQLAlchemy 查 `mcp_servers` WHERE status='published' → 返回 20 条/页

### 拍 2：API 网关鉴权
- **修订后模块**：`L4 既有 JWT 中间件`（沿用 AP-04，不引新中间件）
- 真实状态：✅（既有，AP-04）
- 行为：`Authorization: Bearer <jwt>` → 解码 → 取 `user_id`

### 拍 3：L3 Application 编排（市场）
- **修订后模块**：`L3 application/mcp/market.py:list_market()`
- 真实状态：❌
- 行为：组合 workspace 权限过滤 + 分页 + tag 过滤 + 5min Redis 缓存

### 拍 4：L2 Domain 校验（市场列表）
- **修订后模块**：`L2 domain/mcp/rules.py:validate_market_query(...)`
- 真实状态：❌
- 行为：参数校验、page_size 上限 100

### 拍 5：L1 Infrastructure 查 DB
- **修订后模块**：`L1 infrastructure/db/models/mcp.py:MCPServer` + 索引 `idx_mcp_servers_status_latest`
- 真实状态：❌（表与模型都未建）
- 行为：SQLAlchemy ORM 查询，PG `GIN(tags)` 索引命中

### 拍 6：返回结果
- **修订后模块**：`L4 序列化 Pydantic MCPServerListItem`
- 真实状态：❌
- 行为：JSON 返回 `{items, total, page, page_size}`

### 拍 7：用户点击 MCP 进入详情
- **修订后模块**：`L4 GET /api/v1/mcp/market/{mcp_id}` + `L5 McpMarketDetailPage.tsx`
- 真实状态：❌
- 行为：S-01 验收：详情页 P95 LCP ≤ 1.5s

### 拍 8：用户点击「安装」
- **修订后模块**：`L4 POST /api/v1/mcp/installations` + `L3 application/mcp/install.py:install()` + `L5 McpInstallButton.tsx`
- 真实状态：❌
- 行为：实例化 `WorkspaceMCPInstallation`，计算 `args_hash`，幂等去重

### 拍 9：L2 Domain 幂等校验
- **修订后模块**：`L2 domain/mcp/rules.py:is_idempotent_install(...)`
- 真实状态：❌
- 行为：同 `workspace_id` + `mcp_id` + `args_hash` → 返回已有 `installation_id`

### 拍 10：L1 Infrastructure 启动 Runtime 注入
- **修订后模块**：`L1 infrastructure/agentruntime/mcp_injector.py:attach_mcp(...)`
- 真实状态：❌
- 行为：序列化 MCP config 为 MCP 2025-06-18 协议格式，注入到 `claude_code_runtime` 进程的 stdio / env
- **关键 AR-02 满足点**：Runtime 进程**不另起**，复用现有 spawn 出来的 handle

### 拍 11：L3 Application binding 创建
- **修订后模块**：`L3 application/mcp/binding.py:create()` + `L4 POST /api/v1/mcp/bindings`
- 真实状态：❌
- 行为：写 `agent_mcp_bindings` 表 + 触发 `attach_mcp(...)`

### 拍 12：L2 Domain 绑定唯一性校验
- **修订后模块**：`L2 domain/mcp/rules.py:validate_binding_uniqueness(...)`
- 真实状态：❌
- 行为：UNIQUE (agent_id, installation_id) 兜底

### 拍 13：Agent 启动时 CLI Adapter 注入
- **修订后模块**：`L1 BaseAgentRuntime.spawn() + attach_mcp(...)`（**关键**）
- 真实状态：❌（`attach_mcp` 未实现）
- 行为：MCP config → stdio 转发给 Runtime

### 拍 14：用户发送 IM 消息触发工具调用
- **修订后模块**：`L4 既有 chat WS` + `L5 ChatView` + `MessageBubble`
- 真实状态：✅（既有）
- 行为：消息 → agent → 决策调用 tool → 触发 Runtime

### 拍 15：Runtime 上报 `tool_call_request`
- **修订后模块**：`L4 api/ws/toolcall.py`（**新增/复用**）+ `L1 mcp_injector`
- 真实状态：❌
- 行为：Runtime → WS → 后端落 `mcp_tool_call_logs (status=pending)` + 广播 IM 会话

### 拍 16：后端路由到 MCP server
- **修订后模块**：`L3 application/mcp/runtime.py:dispatch_tool_call(...)`（**新增**）
- 真实状态：❌
- 行为：按 `binding_id` 找到 `installation_id` → MCP `config_json` → stdio 启 MCP → 调用 tool

### 拍 17：MCP 返回结果
- **修订后模块**：Runtime → `tool_call_response` → 后端
- 真实状态：❌
- 行为：更新 `mcp_tool_call_logs (status=success)` + WS 推 IM 会话

### 拍 18：审计落盘 + UI 展示
- **修订后模块**：`L1 mcp_tool_call_logs`（F-017 异步）+ `L5 ToolCallBubble` 嵌 `MessageBubble`
- 真实状态：❌
- 行为：MessageBubble 检测 `tool_calls` 字段 → 渲染 ToolCallBubble → 展示 tool_name / args / duration / result

---

## 3. 闭环判定（修订版）

### 3.1 计划空间（自洽性）

| 维度 | 判定 | 依据 |
|------|------|------|
| 接口契约可调用 | ✅（设计层） | 8+2 端点 IC-MCP §1-2 已写；PR-01 待冻结 |
| 模块文件已就位 | ✅（设计层） | FS-MCP §1 已映射到 `src/backend/app/` 5 层 + `src/frontend/src/` 真实路径 |
| 数据实体已建表 | ⏳（设计层 OK，等迁移） | MD-MCP §1 4 张表已写；alembic 0006-0009 待 PR-09 后落地 |
| 业务规则有仲裁 | ✅ | `domain/mcp/rules.py` 8 条规则已集中 |
| 异常有兜底 | ✅ | IC-MCP §4 18 个 E_MCP_* 错误码 |
| 性能 SLO 满足 | ⏳（设计指标已定，测后再校准） | S-01~07 沿用 PRD V1.3 |
| 安全约束满足 | ✅（本期最小化） | 沿用既有 JWT + 干跑单 Docker |
| 可观测完整 | ✅ | trace_id 贯穿（不用 OTel，B-11） |

### 3.2 代码空间（落地性）

| 维度 | 判定 | 依据 |
|------|------|------|
| 后端模块已实现 | ❌ 0/15 | `src/backend/app/` 内 MCP 目录/文件 0 命中 |
| 前端 UI 已实现 | ❌ 0/11 | `src/frontend/src/` 内 MCP 文件 0 命中 |
| 3 张表已迁移 | ❌ | alembic 0006-0009 不存在 |
| 8+2 端点已实现 | ❌ | `api/v1/mcp.py` 与 `api/ws/toolcall.py` 不存在 |
| CLI Adapter `attach_mcp` 已实现 | ❌ | `mcp_injector.py` 不存在 |
| 端到端真实可走通 | 🔴 **否** | 需 4 阶段实施后 |

### 3.3 闭环总判定

| 闭环 | 上一版 | **修订版** |
|------|--------|-----------|
| PRD 迭代闭环 | 🟢（虚构空间） | 🟢（修订后 V1.3.1 errata 4 项决策已落） |
| 下游反馈闭环 | 🟢（虚构空间） | 🟢（修订后 4 阶段无未消化的反馈） |
| 终局闭环 | 🟢 零修改可走通（**虚构 `src/agenthub/` 空间**） | 🟢 计划空间自洽 / 🔴 代码空间未启动（**真实 `src/backend/app/` 空间**） |

---

## 4. 走通条件（必须满足才能"真"走通）

### 4.1 P1 阶段（数据 + 基础 API，2026-06-02 ~ 06-05）

- [ ] PR-09 同步 `docs/specs/03-data-model` §MCP（CR-03 + PR-09）
- [ ] PR-01 冻结 8+2 端点到 `docs/specs/04-commands` §MCP（2 人 Review）
- [ ] alembic 0006-0008 迁移：3 张表 + 索引
- [ ] 后端实现：`domain/mcp/` + `infrastructure/db/models/mcp.py` + `application/mcp/market.py` + `install.py` + `api/v1/mcp.py` (3 端点)
- [ ] 前端实现：`pages/McpMarket*` + `components/mcp/McpServerCard` + `McpInstallButton` + `api/mcp.ts`
- [ ] 单元测试：market 列表 / 安装幂等 / 错误码覆盖
- [ ] `verify.bat` 通过

### 4.2 P3 阶段（前端 + 工具展示，2026-06-06 ~ 06-08）

- [ ] 后端 alembic 0009：`mcp_tool_call_logs` 表
- [ ] 后端实现：`application/mcp/audit.py`
- [ ] 前端实现：`stores/mcpStore.ts` + `components/mcp/ToolCallBubble` + `McpAuditPanel`
- [ ] 前端实现：嵌入 `MessageBubble.tsx` 检测 `tool_calls`
- [ ] 集成测试：WS 工具调用事件端到端

### 4.3 P2 阶段（binding + create，2026-06-09 ~ 06-11）

- [ ] 后端实现：`application/mcp/binding.py` + `create.py` + `infrastructure/agentruntime/mcp_injector.py`（**关键**）
- [ ] 后端实现：`infrastructure/docker_sandbox/runner.py`（E-03 简化版）
- [ ] 前端实现：`pages/McpCreatePage` + `components/agent/McpBindingPanel` + `components/mcp/McpCreateForm` + `McpTemplateList`
- [ ] 前端修改：`AgentDetailPage.tsx` 增 Tab
- [ ] CLI Adapter 三个 Runtime（claude_code / opencode / pi_agent）均实现 `attach_mcp`
- [ ] 集成测试：创建 → 干跑 → 绑定 → 注入 → 调用 18 拍全链路
- [ ] 浏览器真实核验（headless Chrome 截图）

### 4.4 P4 阶段（收束，2026-06-12 ~ 06-15）

- [ ] ADR：`worklogs/decisions/NNNN-mcp-cli-adapter-extension.md`（`attach_mcp` 协议 + SDK Adapter 下期计划）
- [ ] 收束报告：4 阶段硬闸门 + 测试覆盖率 ≥ 80% + 性能 SLO 验证
- [ ] NB-02 清单：`worklogs/袁/2026-06-15_mcp-nb02-backlog.md`
- [ ] 真实浏览器跑通 18 拍全链路

---

## 5. 修订结论

| 维度 | 上一版 | **修订版** |
|------|--------|-----------|
| 计划自洽 | 🟢 | 🟢 保持 |
| 代码可走通 | 🟢（**虚构空间**） | 🔴 → 🟢 走通 **必须**完成 P1-P4 4 阶段 |
| 与 AR-01 一致 | 🔴（反向） | 🟢 沿用 5 层洋葱 |
| 与 AR-02 一致 | 🔴（自建运行时） | 🟢 Adapter 扩展 |
| 与现有栈一致 | 🔴（Poetry/gRPC/Vault/OTel/K8s） | 🟢 真实栈 |
| 范围合理 | 🔴（13/22 正交） | 🟢 主链路必需项 + 下期 NB-02 |
| PR 闸门 | 🔴（未走 PR-01/09） | 🟢 PR-01/03/06/07/09 列出 |

---

*本 end-to-end-trace 是 MCP 接入**端到端轨迹 + 真实可走通条件**唯一权威。P1 → P4 4 阶段实施后，闭环由 🔴 翻转为 🟢。*
