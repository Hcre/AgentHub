# SA-MCP-V1.0-20260602（修订版）— MCP 接入整体结构与架构概览

> ⚠️ **路径 ERRATA（2026-06-03 整理）**：本文以下出现的 `api/v1/mcp`、`application/mcp/*`、`infrastructure/agentruntime/mcp_injector`、`infrastructure/db/models/mcp.py`、`docker_sandbox`、`BaseAgentRuntime` 均为修订前残留。**实际落点以三处权威为准**：文件结构 → `06-详细设计/FS-MCP §1`；接口契约 → `docs/specs/04-commands §2.6`；架构映射 → `docs/specs/01-architecture §MCP.1`。URL 统一 `/api/mcp/`（无 `/v1/`，见 [ADR-0003](../../../../../worklogs/decisions/0003-mcp-url-prefix-and-ap05-deferral.md)）。

> **版本**：V1.0-rev（2026-06-03 重写）
> **修订依据**：可行性清单 I-01/I-02/I-03
> **上一版**：Layer 1=Access → Layer 2=Application → Layer 3=Infrastructure → Layer 4=Data（**与 AR-01 反向**）
> **本文档**：MCP 接入的**架构总览**权威
> **单一权威入口**：[`../README-REVISION.md`](../README-REVISION.md)

---

## 0. 修订要点

| 项 | 上一版 | **修订版** |
|----|--------|-----------|
| 分层编号 | L1 Access / L2 Application / L3 Infrastructure / L4 Data | **沿用项目 AR-01 洋葱**：L1 Infrastructure → L2 Domain → L3 Application → L4 API → L5 Presentation |
| 依赖方向 | 自顶向下（L4 Data → L3 Infrastructure → L2 Application → L1 Access） | **AR-01 标准方向**：L5→L4→L3→L2←L1（L1 实现 L2 接口，依赖倒置） |
| 落地包 | `agenthub/access` + `agenthub/application` + `agenthub/infrastructure` + `agenthub/data` + `agenthub/eventbus` | **真实 `src/backend/app/`**：直接复用既有 `api` / `application` / `domain` / `infrastructure` / `schemas` 五层 |
| 进程运行时 | 自建 pool + sandbox + eventbus | **复用现有 `BaseAgentRuntime` + CLI Adapter**，MCP 注入作为 Adapter 扩展（AR-02） |
| 接入层定位 | 独立 Layer 1「接入层」（含 API gateway / WS gateway / webhook / cron） | **API 是 L4**（不是独立层）；MCP 端点 = `app/api/v1/mcp.py`；MCP 工具调用走既有 `app/api/ws/toolcall.py`（F-014 复用） |
| 业务编排 | 独立 Layer 2（market/pool/binding/approval/create） | **L3 application/mcp/{market,install,binding,create}.py**（无独立 pool/approval 编排） |
| 基础设施 | 独立 Layer 3（sandbox/k4/template/dns_pinning/network_acl/ssrf_guard/secret/naming/acl_migration） | **L1 infrastructure/{db/models,agentruntime,docker_sandbox}**（仅保留 MCP 主链路必需项；其余移 NB-02） |
| 数据层 | 独立 Layer 4（metadata/ts_log/cache）+ 独立 eventbus 调度 | **既有 SQLAlchemy 模型 + alembic 0006+ 迁移**（无独立 metadata/ts_log/cache/eventbus） |

---

## 1. 5 层洋葱（AR-01）映射

| 洋葱层 | 职责 | 本期 MCP 落点 |
|--------|------|---------------|
| **L1 Infrastructure** | DB / 进程 / 沙箱 / 缓存 / 外部协议 | `infrastructure/db/models/mcp.py`（3 张表 SQLAlchemy 模型）；`infrastructure/agentruntime/mcp_injector.py`（`attach_mcp(...)` 协议）；`infrastructure/docker_sandbox/runner.py`（dry-run 简化版） |
| **L2 Domain** | 实体 + 业务规则 | `domain/mcp/mcp_server.py` / `mcp_installation.py` / `mcp_binding.py` / `rules.py` |
| **L3 Application** | 业务编排（事务、跨域、策略） | `application/mcp/market.py` / `install.py` / `binding.py` / `create.py` / `audit.py` |
| **L4 API** | HTTP/WS 协议层 | `api/v1/mcp.py`（8+2 端点）；`api/ws/toolcall.py`（复用既有） |
| **L5 Presentation** | React UI | `pages/McpMarket*` / `McpCreate*` + `components/mcp/*` + `components/agent/McpBindingPanel.tsx` + `stores/mcpStore.ts` + `routes.tsx` |

---

## 2. 依赖方向（AR-01 标准）

```
L5 Presentation  ───→  L4 API  ───→  L3 Application  ───→  L2 Domain  ◀───  L1 Infrastructure
   (React)            (FastAPI)        (编排)              (实体+规则)        (实现 L2 接口)
```

**关键约束**（AR-01）：
- L1 **实现** L2 的接口（依赖倒置）
- L2 **不依赖** L1 的具体实现
- L3 只调 L2 实体 + L1 接口；不直接查 DB
- L4 只做协议层；不写业务
- L5 不直接访问 L1（数据走 L4→L3→L2→L1）

**MCP 注入链路**（AR-02 关键）：

```
L4 API: POST /api/v1/mcp/bindings
        │
        ↓
L3 Application: application/mcp/binding.create()
        │
        ↓
L2 Domain: 校验 AgentMCPBinding（rule: 唯一性/工具子集/状态）
        │
        ↓
L1 Infrastructure: agentruntime/mcp_injector.attach_mcp(handle, bindings)
        │
        ↓
   BaseAgentRuntime（现有 claude_code/opencode/pi_agent）
        │  注入 stdio / env / CLI 参数
        ↓
   Runtime 进程
```

> **没有新的运行时层**。MCP 注入是 Runtime 的能力扩展（AR-02），不另起进程池/sandbox/eventbus。

---

## 3. 不再是「独立层」的概念消除

| 上一版的「独立概念」 | 修订后去向 |
|----------------------|------------|
| Layer 1「接入层」API gateway | **消除**：沿用既有 L4 API 目录 + FastAPI app（main.py） |
| Layer 1「接入层」WS gateway | **消除**：沿用既有 L4 API/WS 目录 |
| Layer 1「接入层」webhook | **下期 NB-02**：与 MCP 正交 |
| Layer 1「接入层」cron | **下期 NB-02**：与 MCP 正交 |
| Layer 2「应用层」pool（进程池） | **消除**（AR-02）：Runtime 进程由 BaseAgentRuntime 现有管理 |
| Layer 2「应用层」approval | **下期 NB-02**：HITL 流程本期不引入 |
| Layer 3「基础设施」sandbox 多 OS 矩阵 | **下期 NB-02**：本期用 docker_sandbox 单容器（E-03） |
| Layer 3「基础设施」k4 gRPC | **下期 NB-02**：与 MCP 正交 |
| Layer 3「基础设施」dns_pinning | **下期 NB-02**：与 MCP 正交 |
| Layer 3「基础设施」network_acl | **下期 NB-02**：与 MCP 正交 |
| Layer 3「基础设施」ssrf_guard | **下期 NB-02**：与 MCP 正交 |
| Layer 3「基础设施」secret（Vault） | **下期 NB-02**：本期用环境变量 |
| Layer 3「基础设施」naming | **下期 NB-02**：与 MCP 正交 |
| Layer 3「基础设施」acl_migration（Saga） | **下期 NB-02**：与 MCP 正交 |
| Layer 4「数据层」metadata | **消除**：沿用既有 L1 infrastructure/db/models/ |
| Layer 4「数据层」ts_log | **消除**：时序日志用既有 logger + Postgres |
| Layer 4「数据层」cache | **消除**：用既有 Redis（infrastructure/redis/） |
| **独立 eventbus** | **消除**：用既有 Redis pub/sub 或既有 WS 通道 |

---

## 4. AR-02 满足度自检

> AR-02：新 Agent 能力只通过 Adapter 扩展，不另起运行时。

| 项 | 是否满足 | 说明 |
|----|----------|------|
| 现有 `BaseAgentRuntime` 不动 | ✅ | 仅新增 `attach_mcp(...)` Protocol 方法 |
| 不另起进程池 | ✅ | 复用 Runtime 进程 |
| 不另起 sandbox 进程 | ✅ | 单 Docker 容器（仅用于创建时的 dry-run） |
| 不另起 eventbus | ✅ | 用既有 Redis + WS 通道 |
| MCP 配置以 CLI 参数/env 注入 | ✅ | `attach_mcp(...)` 序列化为 MCP `config` JSON 注入 |
| 3 个 Runtime（ClaudeCode/OpenCode/PiAgent）都能挂 MCP | ✅ | 协议层抽象，3 个 Adapter 都实现 `attach_mcp` |
| SDK Adapter 路径（下期） | ⏳ NB-02 | 沿 `attach_mcp(...)` 扩展点 + Python/Node SDK |

---

## 5. 关键决策

1. **MCP 注入 = 现有 CLI Adapter 的能力扩展**（不是新运行时）
2. **dry-run 沙箱 = 单 Docker + compose 资源限额**（不是多 OS 沙箱矩阵）
3. **3 张表** = `mcp_servers` / `workspace_mcp_installations` / `agent_mcp_bindings`（与 §十 一致）
4. **5 层全部沿用项目既有结构**，不新建任何层
5. **所有「生产化基础设施」（沙箱矩阵 / K4 / SSRF / Vault / cron / webhook）下期 NB-02**

---

## 6. 与既有代码的对接

- `BaseAgentRuntime.spawn()` 既有 → `attach_mcp(handle, bindings)` 新增 Protocol
- `api/v1/skills.py` 既有 → `api/v1/mcp.py` 新增（沿用 `kebab-case` + `{error:{code,message}}` 规范）
- `api/ws/chat.py` 既有 → `api/ws/toolcall.py` 复用（F-014 工具调用事件直接挂既有通道）
- `AppShell.tsx` 既有 → 注册 3 个新路由 + AgentDetailPage 增 MCP Tab
- `MessageBubble.tsx` 既有 → 嵌入 `ToolCallBubble`（F-014 工具展示）

---

## 7. 模块清单（本期 vs 下期）

### 7.1 本期（22 → 6 业务模块 + 1 扩展点）

| 洋葱层 | 模块 |
|--------|------|
| L1 | `models/mcp.py`（3 表）· `mcp_injector.py`（attach_mcp）· `docker_sandbox/runner.py`（dry-run） |
| L2 | `mcp_server.py` · `mcp_installation.py` · `mcp_binding.py` · `rules.py` |
| L3 | `market.py` · `install.py` · `binding.py` · `create.py` · `audit.py` |
| L4 | `mcp.py`（8+2 端点）+ 既有 `ws/toolcall.py` |
| L5 | 3 页 + 1 Tab + 1 store + 6 组件 + 1 routes |

### 7.2 下期（NB-02）

见 `FS-MCP-V1.0-20260602.md` §4 完整列表（沙箱矩阵 / K4 / SSRF / DNS pinning / ACL / Vault / cron / webhook / SDK Adapter / Codex+Trae 等）。

---

*本 SA-MCP 是 MCP 接入**架构总览**唯一权威。所有设计评审以此为基准。落地细节见 `FS-MCP-V1.0-20260602.md`（文件落点）、`MD-MCP-V1.0-20260602.md`（数据模型）、`IC-MCP-V1.0-20260602.md`（接口契约）、`MCP-UI-frontend-V1.0-20260602.md`（前端）。*
