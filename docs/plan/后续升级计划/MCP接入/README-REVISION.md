# MCP 接入计划 — 修订版单一权威入口

> **版本**：REVISION-2026-06-03 · **修订发起人**：袁（Claude Agent 协助）
> **修订依据**：[可行性问题清单_2026-06-03.md](./可行性问题清单_2026-06-03.md)（12 项问题）
> **上一版**：01-需求澄清 ~ 08-系统模拟运行 全套原计划（v1.0-20260602）
> **本文档作用**：MCP 接入的**单一权威入口**。roadmap §十 链接此处；后续开发以本文档为基准。

---

## 0. 修订结论速览

| 维度 | 上一版（v1.0） | 修订版（REVISION-2026-06-03） |
|------|----------------|------------------------------|
| 落地代码树 | 虚构的 `src/agenthub/` Poetry monorepo（**不存在**） | 真实 `src/backend/app/` 5 层洋葱（AR-01） |
| 模块数 | 22 模块（13 个与 MCP 正交） | MCP 主链路必需项（清单见 §3） |
| 技术栈 | Poetry/gRPC/Vault/OTel/K8s | 现有 FastAPI app + `requirements.txt` + 现有 alembic 0001-0005 + Docker Compose + Redis |
| 进程运行时 | 自建 `pool`/`sandbox`/`eventbus` | 复用现有 `AgentRuntime` + CLI Adapter（MCP 注入作为 Adapter 扩展，AR-02） |
| MCP 安装表名 | `user_mcp_installations`（本 PRD F-004） | `workspace_mcp_installations`（§十 口径 + 现有 workspace 模型一致） |
| dry-run | macos_sandbox/windows_jobobj/linux_cgroup 多 OS 沙箱矩阵（**本机不可运行**） | 单 Docker 容器 + compose 资源限额（简化版） |
| SDK Adapter（F-013） | 本期做 | **移下期**，但在 CLI Adapter 上**预留 `attach_mcp(...)` 扩展点** + 制定下期接入计划 |
| 端点 | 22 个 IC | 8+2 端点（需走 PR-01 冻结） |
| 数据实体 | 30 个 | 4 张表 = 3 实体（`mcp_servers` / `workspace_mcp_installations` / `agent_mcp_bindings`）+ 1 日志表（`mcp_tool_call_logs`），以 `docs/specs/03-data-model` §MCP 为准 |
| 文档规模 | 8 棒 × 22 模块 × 5 文档 ≈ 100 份 | 主链路切片（约 15-18 份） |
| 闭环判定 | 「零修改可走通」（仅在虚构空间成立） | 「计划空间自洽 / 代码空间未启动」双口径 |

> ⚠️ **本期目标仍然是 MVP 收尾冲刺**（commit `dcc6fff`）：3 分钟 Demo 跑通。下期再考虑生产化基础设施。

---

## 1. 可行性清单 12 项问题 → 处置

| ID | 严重度 | 标题 | 修订处置 |
|----|--------|------|----------|
| I-01 | 🔴 阻断 | 落地目标是虚构的 `src/agenthub/` 新仓 | 全部模块重新映射到 `src/backend/app/` 5 层洋葱（见 §3） |
| I-02 | 🔴 阻断 | 分层语义和 AR-01 洋葱相反 | 统一采用项目洋葱术语：L1 Infrastructure → L5 Presentation，依赖方向 `L5→L4→L3→L2←L1` |
| I-03 | 🔴 阻断 | 违反 AR-02：新增能力本应只加 Adapter | MCP 注入作为现有 CLI Adapter 的能力扩展（`attach_mcp(...)`），不另起进程池/sandbox/eventbus 运行时 |
| I-04 | 🔴 阻断 | 技术栈漂移（Poetry/gRPC/Vault/OTel/K8s） | 删。沿用现有栈：FastAPI + Pydantic v2 + SQLAlchemy + alembic 0006+ + docker compose + Redis |
| I-05 | 🔴 阻断 | 13/22 模块与 MCP 正交 | 全部移入「下期/生产化」清单（NB-02）；本期只保留 MCP 产品主链路（§3） |
| I-06 | 🟠 高 | 多 OS 沙箱 / iptables / cgroup 本机不可运行 | 干跑改为「单 Docker 容器 + compose 资源限额」（dry-run 简化版） |
| I-07 | 🟠 高 | PRD 自相矛盾（B-11 不做 OTel，但 FS-MCP 引入） | 删除 OTel；可观测仅保留 `trace_id` 贯穿。已全量复查 B-01~B-13 一致性 |
| I-08 | 🟠 高 | 与 roadmap §十 既有的 MCP v1 方案重复且口径不一 | **合并去重**：本文档是单一权威，roadmap §十 链接指到此处；表名统一为 `workspace_mcp_installations` |
| I-09 | 🟡 中 | 07 文件框架是巨型 docstring + 空桩 + 引用不存在的包 | 不直接复用 `07-文件框架/*/src/`；只采纳其接口契约/方法清单作设计参考 |
| I-10 | 🟡 中 | 数据模型/迁移与现有 alembic 不衔接 | 续在现有 alembic 链上（0006+），表名/字段与 §十 口径统一；先改 `docs/specs/03-data-model` 再迁移（CR-03 + PR-09） |
| I-11 | 🟡 中 | 未走 PR-01 接口冻结 / PR-09 SPEC 同步 | 修订后：①端点写入 `docs/specs/04-commands` 冻结（PR-01）②架构改动同步 `docs/specs/01-architecture`（PR-09） |
| I-12 | 🟢 低 | 计划体量超 MVP 维护能力 | 按 §十 4 阶段节奏裁剪文档密度，遵守 D 系列红线 |

---

## 2. 与 roadmap §十 的合并关系

roadmap §十 原口径：

- 范围：F1 MCP 市场 / F2 Agent 接入 / F3 创建 MCP / F5 工具调用展示
- 数据：3 张表 `mcp_servers` / `workspace_mcp_installations` / `agent_mcp_bindings`
- 端点：8+2
- 前端：3 个新页（`/mcp-market` 列表/详情 + `/mcp-create`）+ 1 个 Tab（Agent「MCP 接入」）
- 顺序：P1(6/2-6/5) → P3(6/6-6/8) → P2(6/9-6/11) → P4(6/12-6/15)
- 工时：159h（52+34+40+33）

**修订版对齐**：
- ✅ 范围沿用 §十
- ✅ 数据沿用 §十
- ✅ 端点沿用 §十（待 PR-01 冻结）
- ✅ 前端沿用 §十
- ✅ 4 阶段节奏沿用 §十
- ✅ 工时沿用 §十
- ➕ **新增**：CLI Adapter 扩展点（`attach_mcp(...)`）—— 满足 AR-02
- ➕ **新增**：本 README-REVISION + 7 份关键文档重写
- ➖ **删除**：22 模块中的 13 个生产化模块（NB-02）

---

## 3. 本期 MCP 主链路（修订后范围）

### 3.1 落到 `src/backend/app/` 5 层洋葱的具体映射

> ⚠️ 路径已按真实代码树校正（2026-06-03）。下表落点与 `docs/specs/01-architecture_架构定义.md` §MCP.1 完全一致。

| 洋葱层 | 本期 MCP 模块 | 备注 |
|--------|---------------|------|
| **L2 Domain** | `domain/mcp/{mcp_server,mcp_installation,mcp_binding,rules}.py`：3 实体 + 业务规则（批量≤50、版本≤50、args_hash=SHA256(sorted_json)、安装幂等）；`domain/repositories/mcp_repository.py`（repo 接口） | 子包与现有 `domain/llm/`、`domain/task_engine/` 先例一致 |
| **L1 Infrastructure** | `infrastructure/db/models.py` **追加** 4 表（与现有 8 表同文件，不新建 `models/` 包）+ alembic 0006；`infrastructure/repositories/mcp_repository.py`（repo 实现）；MCP 注入实现落现有 `infrastructure/llm/{claude_code,opencode,pi_agent}_runtime.py`；`infrastructure/mcp/dry_run.py`（dry-run 简化版） | 续在 alembic 0001-0005 之后 |
| **L3 Application** | `application/services/{mcp_market,mcp_install,mcp_binding,mcp_create}_service.py`：列表/搜索/详情、安装/卸载幂等、绑定/解绑、stdio/sse 提交 + 模板 | 扁平 `*_service.py` 与现有命名一致；不建 `application/mcp/` 子包 |
| **L4 API** | `api/routers/mcp.py`（8 端点，与 `agents.py` 同级，无 `v1/` 目录）+ `api/ws/toolcall.py`（2 WS 事件，复用既有 `api/ws/`） | 端点先冻结 `docs/specs/04-commands`（PR-01） |
| **L5 Presentation** | `/mcp-market` 列表/详情、`/mcp-create`、Agent「MCP 接入」Tab | 3 页 + 1 Tab + 1 store + 工具展示嵌入 MessageBubble |

### 3.2 关键模块清单（按 4 阶段顺序）

| 阶段 | 范围 | 文档 |
|------|------|------|
| **P1 数据 + 基础 API** | 4 张表迁移（alembic 0006）+ 3 端点（list/detail/install） | `06-详细设计/MD-MCP-V1.0-20260602.md`（已重写）+ `IC-MCP-V1.0-20260602.md`（已重写） |
| **P3 前端 + 工具展示** | 3 页 + 1 Tab + 1 store + 工具展示组件（嵌 MessageBubble） | `06-详细设计/MCP-UI-frontend-V1.0-20260602.md`（新增） |
| **P2 binding + create** | binding（绑定/解绑）+ create（stdio/sse 提交 + 模板）+ CLI Adapter `attach_mcp(...)` 扩展点 | `06-详细设计/FS-MCP-V1.0-20260602.md`（已重写）+ `IC-MCP`（已重写） |
| **P4 收束** | 4 阶段硬闸门（整理/测试/审计/验证）+ ADR + 收束报告 | `worklogs/decisions/NNNN-mcp-cli-adapter-extension.md`（新增） |

### 3.3 CLI Adapter 扩展点（满足 AR-02）

在抽象基类 `domain/llm/protocol.py::AgentRuntime(ABC)`（现有契约 `stream(request)` / `stop()`）上新增抽象方法，由 `src/backend/app/infrastructure/llm/` 下 3 个 Runtime（`claude_code_runtime.py` / `opencode_runtime.py` / `pi_agent_runtime.py`）实现：

```python
# 实装在 domain/llm/protocol.py 的 AgentRuntime(ABC)
class AgentRuntime(ABC):
    @abstractmethod
    def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]: ...
    @abstractmethod
    async def stop(self) -> None: ...
    # ↓ 新增（精确签名待 PR-09 + PR-01 冻结）↓
    @abstractmethod
    def attach_mcp(self, bindings: list[AgentMCPBinding]) -> None: ...
```

- 实现要点：把 `bindings` 序列化成 MCP 2025-06-18 `config` JSON，注入到下一次 `stream` 启动的 Runtime 进程的 CLI 参数 / env / stdio 转发
- 签名是否随 `AgentRequest` 透传 / 是否返回 handle，由 P2 实现前 PR-09 冻结；本节只定扩展点位置
- SDK Adapter 路径（F-013 下期）在 `attach_mcp` 内增加 if 分支即可，不影响本期

---

## 4. 下期 / 生产化清单（NB-02，不在本期）

> 全部移出本期，列入下期 backlog（NB-02）。

| 模块 | 上一版编号 | 下期原因 |
|------|------------|----------|
| 多 OS 沙箱矩阵 | M-C01 | 本机不可运行（I-06） |
| K4 gRPC 安全扫描器 | M-C02 | 安全平台化，超 MVP（I-05） |
| DNS pinning / SSRF guard | M-C04 / M-C06 | 安全平台化，超 MVP（I-05） |
| 网络 ACL（iptables/ipset） | M-C05 | 需要 root，本机跑不起来（I-06） |
| Vault secret transit | M-C07 | 现有环境变量注入足够（I-04） |
| Webhook 验签（github/gitlab/bitbucket） | M-A03 | 与 MCP 正交（I-05） |
| 分布式 cron + leader 选举 | M-A04 | 现有 WS/任务编排足够（I-05） |
| 进程池 | M-B02 | 违反 AR-02（I-03） |
| ACL 迁移 Saga | M-C09 | 与 MCP 正交（I-05） |
| SDK Adapter | F-013 | 本期 CLI Adapter 注入已覆盖；SDK 路径纳入下期（你定的决策） |
| OpenTelemetry | 散落多文档 | PRD V1.3 B-11 明确不做（I-07） |
| gRPC / K8s | 散落多文档 | 非现有栈（I-04） |

---

## 5. 文档地图（修订后实际可读/可用的文件）

### 5.1 ✅ 已重写（本期权威）

| 路径 | 内容 | 状态 |
|------|------|------|
| `README-REVISION.md`（本文件） | 单一权威入口 | ✅ |
| `01-需求澄清/PRD-MCP-V1.3-20260602.md` | V1.3.1 errata 追加（表名 / SDK 移下期 / dry-run 简化 / 前端真实状态） | ✅ |
| `04-整体结构设计/SA-MCP-V1.0-20260602.md` | 架构概览重写 → 5 层洋葱 + AR-01 + AR-02 | ✅ |
| `05-技术架构设计/TA-MCP-V1.0-20260602.md` | 技术栈重写 → 真实栈 | ✅ |
| `06-详细设计/FS-MCP-V1.0-20260602.md` | 文件结构重写 → `src/backend/app/` 映射 | ✅ |
| `06-详细设计/MD-MCP-V1.0-20260602.md` | 数据模型重写 → 4 表（3 实体 + 1 日志表） | ✅ |
| `06-详细设计/IC-MCP-V1.0-20260602.md` | 接口契约重写 → 8+2 端点（顶部 ERRATA 指向冻结草案） | ✅ |
| `06-详细设计/MCP-UI-frontend-V1.0-20260602.md` | 前端 UI 切片（新增） | ✅ |
| `08-系统模拟运行/closure-verdict.md` | 双口径闭环（计划空间 / 代码空间） | ✅ |
| `08-系统模拟运行/end-to-end-trace.md` | 端到端轨迹改写 → 仅在「代码实现后」可走通 | ✅ |
| `docs/specs/04-commands_命令接口.md` §2.6 + §三 | PR-01 端点冻结草案（🔒 待 2 人 Review） | ✅ |

### 5.2 📦 保留作参考（不直接落地）

| 路径 | 保留理由 |
|------|----------|
| `02-调研验证/RESEARCH-*` + `SOURCES-*.json` | 调研事实引用（协议版本 2025-06-18 / Streamable HTTP 等） |
| `03-逻辑梳理/BR-MCP-V1.0-20260602.md` | 业务规则参考（批量 ≤50、版本 ≤50、args_hash=SHA256(sorted_json)、安装幂等） |
| `06-详细设计/IC-MCP-V1.0-20260602.md` 中的方法清单 | 端点设计参考（落地前需 PR-01 冻结） |
| `06-详细设计/MD-MCP-V1.0-20260602.md` 中的字段枚举 | 字段级参考 |

### 5.3 ❌ 不再使用（DEPRECATED，已归档）

> 2026-06-03 整理：以下残留已移至 [`docs/archive/DEPRECATED_MCP接入-原计划残留/`](../../../archive/DEPRECATED_MCP接入-原计划残留/README.md)（含 `07-文件框架/` 445 桩文件、`bak/` 备份、`02-重复变体/` 三份重复）。

| 路径（归档前） | 原因 |
|------|------|
| `07-文件框架/M-*/src/` 全部（445 文件） | 引用不存在的 `agenthub` 包 → 已归档 |
| `04-整体结构设计/SA-MCP` 的虚构分层 | 与 AR-01 反向 |
| `06-详细设计/FS-MCP` 的 Poetry monorepo 布局 | 虚构仓 + 漂移栈 |
| `05-技术架构设计/SEC-MCP` 的 5 层防御矩阵 | 沙箱/Vault 整层下期 |
| `08-系统模拟运行/closure-verdict` 的"零修改走通" | 仅在虚构空间自洽 |

---

## 6. PR 闸门红线（修订版必须走）

| 闸门 | 触发条件 | 产出 |
|------|----------|------|
| **PR-01 接口冻结** | P1 启动前 | `docs/specs/04-commands` 增 MCP 8+2 端点（2 人 Review） |
| **PR-03 Conventional Commits** | 每次 commit | `feature/mcp/<scope>` 分支命名 |
| **PR-06 ≥1 Approve** | 提 PR 前 | 至少 1 人 Review |
| **PR-07 verify** | 提 PR 前 | `scripts/verify.bat`（ruff + mypy + tsc + eslint） |
| **PR-09 SPEC 同步** | 架构/数据模型改动后 | `docs/specs/01-architecture` + `docs/specs/03-data-model` 同步 |
| **CR-03 Alembic** | 改数据库 | 续 alembic 0006+ 迁移，禁止手动改表 |

---

## 7. 修订决策日志

| 时间 | 决策 | 来源 |
|------|------|------|
| 2026-06-03 | 单一权威 = 修订版 MCP接入/，roadmap §十 链接此处 | 用户确认 §5 决策 1 |
| 2026-06-03 | MCP 安装表名 = `workspace_mcp_installations` | 用户确认 §5 决策 2 |
| 2026-06-03 | dry-run = 简化版（单 Docker + compose 资源限额） | 用户确认 §5 决策 3 |
| 2026-06-03 | SDK Adapter = 移下期；CLI Adapter 预留 `attach_mcp(...)` 扩展点 | 用户确认 §5 决策 4 |

---

## 8. 后续步骤

1. **本期不动代码**：修订完成后，按 ai-workflow 第一步（计划）切到 P1 任务
2. **P1 启动前**：先 PR-01 冻结端点到 `docs/specs/04-commands`
3. **P1 启动时**：先 PR-09 同步 `docs/specs/01-architecture` + `docs/specs/03-data-model`
4. **P1 → P3 → P2 → P4**：按 §十 节奏推进，每阶段走 4 阶段硬闸门（整理/测试/审计/验证）
5. **收束**：ADR `worklogs/decisions/NNNN-mcp-cli-adapter-extension.md` + 收束报告

---

*本 README 是 MCP 接入修订版的单一权威入口。后续以本文档 + §5.1 已重写文件 为准；其余文件作参考或 DEPRECATED。*
