# 2026-06-03 — MCP 接入计划修订批次（基于可行性清单）

> **作者**：袁（Claude Agent 协助）
> **状态**：✅ 修订完成
> **依据**：[`可行性问题清单_2026-06-03.md`](../../docs/plan/后续升级计划/MCP接入/可行性问题清单_2026-06-03.md) 12 项问题
> **触发**：用户问询"相应的前端界面是否做了"（暴露原计划与真实代码空间错位）

---

## 0. 一句话总结

按可行性清单 12 项问题，对 `docs/plan/后续升级计划/MCP接入/` 8 棒流水线文件做大盘修订：单一权威 + 真实代码空间对齐 + 4 项决策落地 + 22 模块 DEPRECATED 标记。

---

## 1. 用户 4 项决策

通过 `AskUserQuestion` 收到：

1. **权威来源**：§十 合并 MCP接入/（修订版 MCP接入/ 作为唯一权威入口）
2. **表名口径**：`workspace_mcp_installations`（与 §十 + 现有 workspace 模型一致）
3. **dry-run**：做，简化版（单 Docker + compose 资源限额）
4. **SDK Adapter**：移下期，但 CLI Adapter 预留 `attach_mcp(...)` 扩展点 + 制定下期接入计划

---

## 2. 产出清单（修订批）

### 2.1 新建 1 份

| 文件 | 作用 |
|------|------|
| `docs/plan/后续升级计划/MCP接入/README-REVISION.md` | **单一权威入口**（4 决策 / 12 问题处置 / 与 §十 合并 / 本期模块清单 / 下期 NB-02 / PR 闸门） |

### 2.2 重写 7 份（v1.0 → v1.0-rev）

| 文件 | 修订重点 |
|------|----------|
| `01-需求澄清/PRD-MCP-V1.3-20260602.md` | 顶部追加 §0.5 V1.3.1 errata（4 项决策落地，原 V1.3 完整保留） |
| `04-整体结构设计/SA-MCP-V1.0-20260602.md` | 4 层反向 → 5 层洋葱 AR-01；消除「接入层/数据层/eventbus」独立层 |
| `05-技术架构设计/TA-MCP-V1.0-20260602.md` | 删 Poetry/gRPC/Vault/OTel/K8s；用真实栈 |
| `06-详细设计/FS-MCP-V1.0-20260602.md` | 22 模块 + `src/agenthub/` → MCP 主链路 + `src/backend/app/` 5 层映射 |
| `06-详细设计/MD-MCP-V1.0-20260602.md` | 30 实体 → 4 张表（mcp_servers/workspace_mcp_installations/agent_mcp_bindings/mcp_tool_call_logs） |
| `06-详细设计/IC-MCP-V1.0-20260602.md` | 22 IC → 8+2 端点（PR-01 待冻结）+ 18 个 E_MCP_* 错误码 + Pydantic schemas |
| `08-系统模拟运行/closure-verdict.md` | "零修改可走通" → 双口径（计划空间🟢/代码空间🔴） |
| `08-系统模拟运行/end-to-end-trace.md` | 18 拍标注真实代码空间状态（0/15 后端 + 0/11 前端） |

### 2.3 新增 1 份（用户问询触发）

| 文件 | 作用 |
|------|------|
| `06-详细设计/MCP-UI-frontend-V1.0-20260602.md` | 前端 UI 切片：3 页（market list/detail/create）+ 1 Tab（Agent「MCP 接入」）+ 1 store + 6 组件 + 1 routes + 1 api wrapper；明确「未实现」状态 |

### 2.4 标记 22 份

| 文件 | 数量 | 处置 |
|------|------|------|
| `07-文件框架/M-*/DEPRECATED.md` | 22 | 全部 22 模块（M-A01~A04 / M-B01~B05 / M-C01~C09 / M-D01~D03 / M-EV01）各加 1 份 DEPRECATED.md；3 类处置：DEPRECATED（7）/ NB-02 下期（12）/ 保留作设计参考（3） |

### 2.5 同步 1 份

| 文件 | 修改 |
|------|------|
| `STATUS.md`（根） | 袁 那一行追加本批修订条目（不动其他列） |

---

## 3. 关键判断

### 3.1 与原版的关系

- **保留作参考**：02-调研验证/RESEARCH-*/SOURCES-*.json（MCP 协议版本 2025-06-18、Streamable HTTP 等事实引用）、03-逻辑梳理/BR-MCP（业务规则）、06-详细设计/IC-MCP/方法清单（端点设计参考）
- **DEPRECATED**：07-文件框架/M-*/src/ 全部、SA-MCP 虚构分层、FS-MCP Poetry monorepo、SEC-MCP 5 层防御矩阵、closure-verdict "零修改走通"
- **不在本期范围**（NB-02 列入下期 backlog）：13 个生产化模块（沙箱矩阵 / K4 / SSRF / DNS pinning / ACL / Vault / cron / webhook / SDK Adapter / Codex+Trae）

### 3.2 与 roadmap §十 的合并

按用户决策 1：roadmap §十 链接指到 `docs/plan/后续升级计划/MCP接入/README-REVISION.md`。§十 工程口径（3 表/8+2 端点/CLI Adapter 复用/4 阶段节奏/159h 工时）全部沿用。

### 3.3 真实代码空间状态（2026-06-03 扫描）

- `src/backend/app/` 内 MCP 目录/文件 0 命中
- `src/frontend/src/` 内 MCP 文件 0 命中（`pages/` 目录都不存在）
- 既有 `AgentDetailPage.tsx` 4 个 Tab（概览/能力/记忆/设置）**无 MCP 接入 Tab**
- 既有 alembic 0001-0005，无 MCP migration
- 既有 `api/v1/skills.py` 是 Skills（与 MCP 正交）

> 修订后明确：原版"🟢 三层闭环均建立且收敛；零修改可走通"——**仅在计划自身虚构的 `src/agenthub/` 空间成立**。修订版做「计划空间🟢 / 代码空间🔴」双口径判定。

---

## 4. PR 闸门（修订版必须走）

- **PR-01 接口冻结**：P1 启动前把 8+2 端点写到 `docs/specs/04-commands` §MCP（2 人 Review）
- **PR-03 Conventional Commits**：`feature/mcp/<scope>` 分支命名
- **PR-06 ≥1 Approve** + **PR-07 verify**：提 PR 前
- **PR-09 SPEC 同步**：`docs/specs/01-architecture` + `docs/specs/03-data-model` 同步
- **CR-03 Alembic**：续在 0001-0005 之后（0006+）

---

## 5. 给下一位的交接

### 5.1 启动 P1 之前要做的

1. **PR-01**：把 `06-详细设计/IC-MCP-V1.0-20260602.md` §1-2 端点 + §4 错误码同步到 `docs/specs/04-commands` §MCP 子节（2 人 Review）
2. **PR-09**：把 `06-详细设计/MD-MCP-V1.0-20260602.md` §1 4 张表同步到 `docs/specs/03-data-model` §MCP 子节
3. **审 `attach_mcp(...)` 协议签名**：本期 CLI Adapter 扩展点定义在 `README-REVISION.md` §3.3，需在 P2 实施时落到 `infrastructure/agentruntime/mcp_injector.py`

### 5.2 4 阶段实施顺序

- **P1**（数据 + 基础 API）：alembic 0006-0008 + 后端 market/install + 前端 market 3 页 + 1 store
- **P3**（前端 + 工具展示）：alembic 0009 + ToolCallBubble + McpStore + routes
- **P2**（binding + create）：binding/create 服务 + mcp_injector + docker_sandbox + McpCreatePage + AgentDetailPage 增 Tab
- **P4**（收束）：ADR `NNN-mcp-cli-adapter-extension.md` + 收束报告 + NB-02 清单

### 5.3 关键红线（执行时必查）

- ❌ 不要再引 `src/agenthub/` 任何代码
- ❌ 不要再引 Poetry/gRPC/Vault/OTel/K8s
- ❌ 不要再建独立「接入层 / 数据层 / eventbus / pool / 多 OS 沙箱」
- ❌ 不要再用 OTel（沿 trace_id 字符串贯穿）
- ✅ 表名用 `workspace_mcp_installations`（不是 `user_mcp_installations`）
- ✅ dry-run 用单 Docker 容器（不是多 OS 沙箱矩阵）
- ✅ SDK Adapter 走下期，但 `attach_mcp(...)` 扩展点必须预留
- ✅ 端点冻结走 PR-01；架构/数据模型走 PR-09

---

## 6. 后续 worklog 计划

- P1 启动后：`2026-06-XX_mcp-p1-data-api.md`（数据 + 基础 API 实施）
- P3 启动后：`2026-06-XX_mcp-p3-frontend-toolcall.md`
- P2 启动后：`2026-06-XX_mcp-p2-binding-create.md`
- P4 收束：`2026-06-XX_mcp-p4-closure.md` + ADR `worklogs/decisions/NNNN-mcp-cli-adapter-extension.md`
- 下期启动：`2026-06-XX_mcp-nb02-backlog.md`

---

*本 worklog 记录 MCP 接入计划修订批次。下一位接手者：先看 `README-REVISION.md` §0-2 速览，再按 §3 实施。*
