# 2026-06-03 · MCP P2 核心 — Agent 绑定 + 请求携带 attach

> 作者：袁（xiangbianpangde）· 分支 `feature/mcp/p2-binding-attach`（从 main，含 F1+收束-1+董记忆 merge）

## 背景

F1 收束-1 闭合并入 main 后，启动 P2（F2 Agent 绑定 + attach_mcp）。设计前读 runtime 契约发现：董记忆系统已在 claude_code runtime 用 `_write_mcp_config` 注入 MCP server——P2 在此基础上扩展。

## 关键决策（ADR-05）：attach = 请求携带

`AgentRuntime` 池化/进程级共享，存绑定状态会跨 agent 串号。故定为**请求携带**：
- `AgentRequest.mcp_servers: list[dict]` 字段
- L3 `McpBindingService.build_request_mcp_servers(agent_id)` 解析 active 绑定 → installation → server → `build_mcp_config_entry`
- `ContextBuilder` 经可选 `mcp_resolver` 在私聊/群聊两处装配时填充（失败不阻塞对话）
- claude_code runtime build_cmd 读 `request.mcp_servers`，扩展 `_write_mcp_config` 合并 `agenthub-memory` + 绑定 servers 写 `.mcp.json`

## 做了什么

- **L2**：`McpBindingRepository` 接口 + `AgentMcpBinding` 复用；`build_mcp_config_entry`（rules，按 transport 序列化）
- **L1**：`PostgresMcpBindingRepository`（save/get/find_active/list_active_by_agent）；`AgentMcpBindingModel` 改**部分唯一**（status=active）+ alembic `0010`（drop 旧 uq → 建 partial unique index，PG `postgresql_where`）；claude_code `_write_mcp_config` 合并注入
- **L3**：`McpBindingService`（bind 409 重复 / unbind 软删 / build_request_mcp_servers）；`ContextBuilder` 加 `mcp_resolver`
- **L4**：`POST /api/mcp/bindings` + `DELETE /api/mcp/bindings/{id}` + schemas + deps 接线（含 WS 手动构造路径）
- **spec（PR-09）**：`01-architecture §MCP.2` + `04-commands §2.6` 改请求携带口径 + ADR-05
- **测试**：test_mcp.py +8（绑定创建/重复 409/404、unbind 软删、**rebind 修复**、build_request_mcp_servers、config entry by transport、`_write_mcp_config` 合并、路由注册）→ 26 绿

## 验证

- MCP 26/26；全量 110/112（2 失败 = pi-agent CLI 未装，环境项；chat 管线未受 ContextBuilder/deps 改动影响）
- ruff lint + format 全过（顺手修 claude_code import 排序 + 给董 tempfile 加 SIM115 noqa——故意 delete=False 持久化）

## 给下一位的交接

1. **opencode / pi_agent runtime 注入未做**：二者未读 `request.mcp_servers`。用这两个 CLI 的 agent 暂不挂载绑定的 MCP。需按各自 config 机制补（opencode.json mcp 字段 / pi-agent 待查）。claude_code（主）已通。
2. **`/api/mcp` 路径重叠**（merge 引入）：董 `app.mount("/api/mcp", mcp_memory ASGI)` 与本市场 router 同基路径，现靠注册顺序（router 在 mount 前）消歧，P4 前需裁定划分。
3. **tool_subset 未进 .mcp.json**：CLI 不一定支持工具级过滤，工具级暴露留 P4。
4. **收束-2** 未做：P2 完整（含 opencode/pi_agent）后走四阶段 + ADR-06。
5. 缓存：`mcp:bindings:{agent_id}` 30s（MD §4）未接——每请求现查 DB，量大后加。

## 红线
PR-02 ✅(分支) · PR-03 ✅(Conventional) · PR-09 ✅(§MCP.2+§2.6 同步+ADR-05) · CR-03 ✅(alembic 0010) · AR-01 ✅(domain/mcp 无 ORM) · AR-02 ✅(只扩展 runtime 注入，未另起运行时) · T-05 ✅(adapter config 生成必测)

## 续：/api/mcp 路径分离（2026-06-03，分支 feature/mcp/split-api-mcp-paths）

F1+记忆 merge 引入的 `/api/mcp` 重叠（董记忆 MCP SSE mount vs 市场 REST router 同基）已解决：
- `main.py` mount `/api/mcp` → **`/api/mcp-memory`**；`config.py` `mcp_memory_url` 示例同步 `.../api/mcp-memory/sse`
- §2.6 REST 契约不动（`/api/mcp/*` 归市场）；`_AgentMCPWrapper` 路径判断 mount 前缀无关，迁移透明
- ADR-03 加 §六 addendum；`test_mcp_routes_registered` 加回归断言（`/api/mcp` 无裸 mount）；26 测试绿
- **运维注意**：设 `MCP_MEMORY_URL` 环境变量时用新路径 `/api/mcp-memory/sse`
