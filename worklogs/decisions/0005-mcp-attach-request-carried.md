# ADR-05：MCP `attach_mcp` 机制 = 请求携带（AgentRequest.mcp_servers），非运行时有状态

> 日期：2026-06-03 | 状态：**Accepted** | 决策人：袁（Claude Agent 协助）
> 关联：[ADR-04](0004-mcp-f1-landing-and-installer-seam.md) · `docs/specs/01-architecture` §MCP.2 · `docs/specs/04-commands` §2.6（bindings 副作用）

## 一、背景

F2（Agent 绑定）需把「某 agent 绑定了哪些 MCP」喂给 CLI 运行时。原 §MCP.2 草案写「`AgentRuntime` 新增有状态 `attach_mcp(bindings)` 抽象方法，注入下一次 stream」，并注明精确签名 P2 冻结。

实现前发现关键约束：`AgentRuntime` 实例是**池化 / 进程级共享**的（`claude_code_process_pool.py` 按 session_key 复用长驻进程；factory 单例），若把「当前 agent 的绑定」存到 runtime 实例上，**跨 agent 会串号**。

## 二、选项

| 选项 | 机制 | 代价 |
|------|------|------|
| A 运行时有状态 `attach_mcp(bindings)` | POST 绑定后调 runtime 存实例，下次 stream 生效 | 池化/共享 runtime 跨 agent 串号；需按 agent_id 分桶，复杂易错 |
| **B 请求携带（选定）** | `AgentRequest.mcp_servers` 带 config；runtime 在 build_cmd 时读取写 .mcp.json | 无状态、零串号；对齐董既有 per-request `_write_mcp_config(request.agent_id)` 模式 |
| C 运行时注入 binding provider | runtime 持 repo/回调，stream 时按 agent_id 现查 | 把 L3 查询下沉 L1，AR-01 依赖方向需谨慎 |

## 三、决策

**选项 B：请求携带。** `attach_mcp` 不作为 `AgentRuntime` 有状态方法存在。

- `AgentRequest` 加 `mcp_servers: list[dict]`（MCP 2025-06-18 config 条目）
- L3 `McpBindingService.build_request_mcp_servers(agent_id)`：active 绑定 → installation → server → `build_mcp_config_entry`
- `ContextBuilder` 经可选 `mcp_resolver`（注入 `build_request_mcp_servers`）在私聊/群聊两处装配时填 `mcp_servers`；解析失败不阻塞对话
- Runtime 在 build_cmd 读 `request.mcp_servers` 写 `.mcp.json`（claude_code 复用并扩展董记忆工具的 `_write_mcp_config`，合并 `agenthub-memory` + 绑定 servers）

POST `/api/mcp/bindings` 的「副作用」因此**不是主动调用**，而是持久化绑定 + 下次 stream 自动携带（解绑软删后自动不再携带，满足 F-011 ≤5s 生效）。

## 四、影响 / 后续

- spec 同步（PR-09）：`01-architecture §MCP.2` + `04-commands §2.6` 已改为请求携带口径。
- 绑定唯一性：`agent_mcp_bindings` 改 `status='active'` 部分唯一（alembic 0010），解绑后可 rebind（修 F1 遗留 NOTE）。
- 已接线：claude_code runtime（主，含记忆工具合并）。**opencode / pi_agent runtime 的 `request.mcp_servers` 注入为增量**（各自 CLI config 机制：opencode.json mcp 字段 / pi-agent 待定）。
- `/api/mcp` 路径与董记忆 MCP ASGI mount 的重叠（见 STATUS 技术债）需在 P4 前裁定。
- tool_subset 暂未进 .mcp.json（CLI 不一定支持工具级过滤）；工具级暴露/过滤留 P4。
