# ADR-03：MCP 端点 URL 前缀 = `/api/mcp`，AP-05（URL 版本号）暂缓

> 日期：2026-06-03 | 状态：**Accepted** | 决策人：袁（Claude Agent 协助）
> 关联：[规范导航 §2 AP-05](../../docs/conventions/CLAUDE-规范导航.md) · `docs/specs/04-commands_命令接口.md` §2.6 · [MCP README-REVISION](../../docs/plan/后续升级计划/MCP接入/README-REVISION.md)

## 一、背景

MCP 接入 PR-01 端点冻结时发现规范与现状冲突：

- **AP-05 红线**（`04-api_API设计规范.md` §一）：API 版本号必须在 URL 路径 `/api/v1/...`；04-api 自身示例为 `/api/v1/agents`。
- **现存代码现状**：`src/backend/app/api/routers/*.py` 全部注册为 `/api/agents`、`/api/groups`、`/api/sessions`…（`APIRouter(prefix="/api/agents")`），**无 `/v1/` 段**。即**现存全部端点已违反 AP-05**，是早于 MCP 的 spec↔code 漂移。

MCP 新增 8 端点需在二者间取舍前缀。原 `IC-MCP` 稿写的是 `/api/v1/mcp/...`（符合 AP-05、不符合现状）。

## 二、选项对比

| 选项 | URL | 优点 | 代价 |
|------|-----|------|------|
| A 遵守 AP-05 | `/api/v1/mcp/...` | 合规红线 | MCP 成为全库唯一带 v1 的端点，前端/路由心智分裂；需为旧端点补迁移 ADR |
| **B 对齐现状（选定）** | `/api/mcp/...` | 与 `/api/agents` 等全库一致，前端统一 | 继续违反 AP-05，需显式记录暂缓 |
| C v1 + 修订 AP-05 | `/api/v1/mcp/` + 改规范/全库迁移 | 最彻底 | 工作量最大，超 MVP 收尾冲刺范围 |

## 三、决策

**采用选项 B：MCP 端点统一 `/api/mcp/...`**（与现有 `/api/agents` 一致）。

**AP-05 暂缓（defer）**，不在本期纠正：
- 现状是全库无 `/v1/`，MCP 单独加 `/v1/` 只会制造不一致，违背 AP-05 的初衷（一致的版本策略）。
- 版本化是平台化议题，留待后续统一迁移（新建 NB-02 backlog 项：「API 版本化统一」），届时全库一次性引入 `/api/v1/` 或在网关层做版本路由。
- 本期 MVP 收尾冲刺（commit `dcc6fff`）优先 Demo 跑通，不做跨全库 URL 重构。

## 四、附带确认（PR-01 冻结时一并校正的口径）

| 项 | 旧稿（IC-MCP） | 冻结口径（04-commands §2.6 / §三） |
|----|----------------|-----------------------------------|
| URL 前缀 | `/api/v1/mcp/` | `/api/mcp/`（本 ADR） |
| WS 事件格式 | `{"event":...}` 扁平 | `{"type":"tool_call:*","payload":{...}}` 信封 + `request_id`（AP-07） |
| 错误格式 | 散落 | `{error:{code:"E_MCP_*",message}}`（AP-02） |
| `attach_mcp` 落点 | `infrastructure/agentruntime/mcp_injector.py`（虚构目录） | `domain/llm/protocol.py::AgentRuntime` 抽象方法，3 个 `infrastructure/llm/*_runtime.py` 实现 |

## 五、影响 / 后续

- `04-commands §2.6` 已按 `/api/mcp/` 落草案（🔒 仍待 PR-01 两人 Review，本 ADR 不代替 Review）。
- 实现端：`api/routers/mcp.py` 用 `APIRouter(prefix="/api/mcp")`，与现有 routers 一致。
- AP-05 的修订/迁移另立 backlog，不在 MCP 本期范围。
- 若未来 review 推翻本决策（要求合规 v1），只需改 router prefix + §2.6 URL，端点设计不受影响。

## 六、addendum：记忆 MCP 协议端路径分离（2026-06-03）

F1+记忆系统 merge 后发现路径重叠：董记忆 MCP **协议服务端**（FastMCP SSE）`app.mount("/api/mcp", ...)` 与本 MCP **市场 REST** router（`prefix=/api/mcp`，§2.6 冻结）同基路径——mount 通配会遮蔽 REST 子路径（当时仅靠注册顺序消歧，脆弱）。

**决策**：协议端（squatter）让路——mount 移到 **`/api/mcp-memory`**，`/api/mcp/*` 归市场 REST（§2.6 契约不动，无需 PR-01 重冻）。`settings.mcp_memory_url` 示例同步 `.../api/mcp-memory/sse`；`_AgentMCPWrapper` 的 `/sse`/`/messages/` 判断 mount 前缀无关，迁移透明。加 `test_mcp_routes_registered` 回归断言（`/api/mcp` 不得有裸 mount）。运维设 `MCP_MEMORY_URL` 时用新路径。
