# FS-MCP-V1.0-20260602（修订版）— MCP 接入文件结构规范

> **版本**：V1.0-rev（2026-06-03 重写）
> **修订依据**：[可行性问题清单_2026-06-03.md](../可行性问题清单_2026-06-03.md) I-01/I-02/I-03/I-04
> **上一版**：22 模块 + `src/agenthub/` Poetry monorepo（**虚构空间**）
> **本文档**：MCP 接入的**实际文件落点**权威说明
> **单一权威入口**：[`../README-REVISION.md`](../README-REVISION.md)

---

## 0. 修订要点

| 项 | 上一版 | **修订版** |
|----|--------|-----------|
| 落地包 | 虚构的 `src/agenthub/` | 真实 `src/backend/app/`（AGENTHUB 既有代码树） |
| 分层 | Layer 1=Access → Layer 2=Application → Layer 3=Infrastructure → Layer 4=Data（**与 AR-01 反向**） | L1 Infrastructure → L2 Domain → L3 Application → L4 API → L5 Presentation（AR-01） |
| 模块数 | 22 模块（13 个与 MCP 正交） | MCP 主链路必需项（详见 §3 清单） |
| 进程运行时 | 自建 `pool` / `sandbox` / `eventbus` | **复用现有 AgentRuntime + CLI Adapter**（AR-02：扩展只加 Adapter） |
| 工具链 | Poetry + gRPC + Vault + OTel + K8s | 现有 `requirements.txt` / `pyproject.toml` (pip) + docker compose + Redis |
| 迁移 | 全新 `migrations/`（新 alembic env） | **续在现有 alembic 0001-0005 之后**（0006+，CR-03） |

---

## 1. 现有 `src/backend/app/` 5 层洋葱（AR-01，本期目标态）

> ⚠️ **本树已按真实代码结构校正（2026-06-03）**：现有 API 在 `api/routers/`（**无 `v1/`**）；DB 模型是**单文件** `infrastructure/db/models.py`；Runtime 在 `infrastructure/llm/`；Runtime 抽象基类在 `domain/llm/protocol.py`（非 `agentruntime/base.py`）。落点与 `docs/specs/01-architecture` §MCP.1 一致。

```
src/backend/
├── alembic/                    # 现有 alembic 链
│   ├── env.py
│   └── versions/
│       ├── 0001_initial.py
│       ├── 0002_add_agent_system_base_url.py
│       ├── 0003_partial_unique_name.py
│       ├── 0004_create_groups.py
│       ├── 0005_add_workspace_path.py
│       └── 0006_mcp_*.py       # ← 本期新增（4 张 MCP 表）
│
├── app/
│   ├── main.py                 # FastAPI 入口（已存在，include_router 注册 mcp.router）
│   │
│   ├── api/                    # L4 API 层（FastAPI routers）
│   │   ├── deps.py             # 现有
│   │   ├── routers/            # 现有：agents/groups/sessions/tasks/skills/inbox/providers/proxy
│   │   │   └── mcp.py          # ← 本期新增：APIRouter(prefix="/api/mcp")，8 端点
│   │   └── ws/
│   │       ├── chat.py         # 现有
│   │       ├── runner.py       # 现有
│   │       └── toolcall.py     # ← 本期新增：tool_call:* 事件（复用既有会话 WS）
│   │
│   ├── application/            # L3 Application 层（编排，按类型分层 commands/dto/services）
│   │   ├── commands/
│   │   ├── dto/
│   │   └── services/           # 现有扁平 *_service.py（agent_service / chat_service / ...）
│   │       ├── mcp_market_service.py   # ← 新增 F-001/F-002/F-003
│   │       ├── mcp_install_service.py  # ← 新增 F-004/F-005
│   │       ├── mcp_binding_service.py  # ← 新增 F-008~F-011
│   │       └── mcp_create_service.py   # ← 新增 F-018/F-019/F-020
│   │
│   ├── core/                   # 横切（已存在）
│   │   ├── config.py
│   │   └── ...                 # trace_id 贯穿（不用 OTel，PRD B-11）
│   │
│   ├── domain/                 # L2 Domain 层（实体 + 业务规则）
│   │   ├── entities/           # 现有扁平实体（agent/group/message/session/task）
│   │   ├── enums.py            # 现有（MCP 枚举追加于此或子包内）
│   │   ├── llm/
│   │   │   └── protocol.py     # 现有：LLMAdapter / AgentRuntime(ABC) ← 新增 attach_mcp 抽象方法
│   │   ├── repositories/       # 现有 repo 接口
│   │   │   └── mcp_repository.py    # ← 本期新增：MCP repo 接口
│   │   ├── task_engine/
│   │   └── mcp/                # ← 本期新增子包（与 llm/、task_engine/ 子包先例一致）
│   │       ├── mcp_server.py        # MCPServer 实体
│   │       ├── mcp_installation.py  # WorkspaceMCPInstallation 实体
│   │       ├── mcp_binding.py       # AgentMCPBinding 实体
│   │       └── rules.py             # 业务规则：批量≤50、版本≤50、args_hash=SHA256(sorted_json)
│   │
│   ├── infrastructure/         # L1 Infrastructure 层
│   │   ├── db/
│   │   │   ├── base.py         # 现有
│   │   │   └── models.py       # 现有单文件（8 表）← 本期追加 4 张 MCP 表（不新建 models/ 包）
│   │   ├── llm/                # 现有：Runtime + Adapter 实现都在此
│   │   │   ├── claude_adapter.py
│   │   │   ├── claude_code_runtime.py    # ← 实现 attach_mcp
│   │   │   ├── opencode_runtime.py       # ← 实现 attach_mcp
│   │   │   ├── pi_agent_runtime.py       # ← 实现 attach_mcp
│   │   │   └── factory.py
│   │   ├── repositories/       # 现有 repo 实现
│   │   │   └── mcp_repository.py    # ← 本期新增：MCP repo 实现
│   │   ├── mcp/                # ← 本期新增
│   │   │   └── dry_run.py      # 简化版 dry-run：单 Docker 容器 + compose 资源限额
│   │   ├── cache/              # 现有（redis_client.py 等）
│   │   ├── queue/              # 现有（celery_app.py）
│   │   └── ws/                 # 现有
│   │
│   └── schemas/                # Pydantic 模型（已存在）
│       └── mcp.py              # ← 本期新增
│
├── tests/                      # pytest（已存在）
│   └── ...                     # ← 本期新增 mcp_*.py（unit/integration/e2e）
│
├── pyproject.toml              # 现有（pip），不引 Poetry
├── requirements.txt            # 现有
└── Dockerfile                  # 现有
```

---

## 2. 前端落地（`src/frontend/src/`）

```
src/frontend/src/
├── pages/                      # ← 本期新增目录
│   ├── McpMarketPage.tsx       # /mcp-market 列表
│   ├── McpMarketDetailPage.tsx # /mcp-market/:id 详情
│   └── McpCreatePage.tsx       # /mcp-create
│
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx        # 现有：注册新路由
│   │   └── LeftPanel.tsx       # 现有：新增「MCP 市场」入口
│   ├── agent/
│   │   ├── AgentDetailPage.tsx # 现有：新增「MCP 接入」Tab
│   │   └── McpBindingPanel.tsx # ← 本期新增：MCP 接入 Tab 内容
│   ├── mcp/
│   │   ├── McpServerCard.tsx       # ← 本期新增
│   │   ├── McpInstallButton.tsx    # ← 本期新增（一键安装）
│   │   ├── McpCreateForm.tsx       # ← 本期新增（stdio/sse/http 三选一表单）
│   │   ├── McpTemplateList.tsx     # ← 本期新增（5 个官方模板）
│   │   └── ToolCallBubble.tsx      # ← 本期新增（嵌 MessageBubble）
│   ├── chat/
│   │   └── MessageBubble.tsx    # 现有：嵌入 ToolCallBubble
│   └── ui/                     # 现有（Button/Card/Tabs/...）
│
├── stores/
│   ├── chatStore.ts            # 现有
│   └── mcpStore.ts             # ← 本期新增（Zustand）
│
├── api/
│   ├── chat.ts                 # 现有
│   └── mcp.ts                  # ← 本期新增（fetch wrapper，调用后端 8+2 端点）
│
├── routes.tsx                  # ← 本期新增（react-router 路由注册）
├── App.tsx                     # 现有（套 Router）
└── main.tsx                    # 现有
```

---

## 3. 本期 MCP 主链路模块清单（按 4 阶段顺序）

### 3.1 P1（数据 + 基础 API，2026-06-02 ~ 06-05）

| 模块 | 后端文件 | 前端文件 | 备注 |
|------|----------|----------|------|
| 4 张表 SQLAlchemy 模型 | `infrastructure/db/models.py`（追加） | — | alembic 0006 迁移 |
| MCPServer 实体 + 规则 | `domain/mcp/mcp_server.py` + `domain/mcp/rules.py` | — | 沿用 §十 实体 |
| MCP 市场服务（list/search/detail） | `application/services/mcp_market_service.py` | `pages/McpMarketPage.tsx` + `pages/McpMarketDetailPage.tsx` | F-001/F-002/F-003 |
| 安装服务 | `application/services/mcp_install_service.py` | `components/mcp/McpInstallButton.tsx` | F-004（idempotent，E-01 表名修正） |
| Pydantic schemas | `schemas/mcp.py` | — | request/response |
| L4 端点（list/detail/install） | `api/routers/mcp.py`（`prefix="/api/mcp"`） | `api/mcp.ts` | 走 PR-01 冻结（§2.6） |

### 3.2 P3（前端 + 工具展示，2026-06-06 ~ 06-08）

| 模块 | 后端文件 | 前端文件 | 备注 |
|------|----------|----------|------|
| ToolCallBubble 工具展示 | `infrastructure/db/models.py` 增 `mcp_tool_call_logs` 表 | `components/mcp/ToolCallBubble.tsx` + 嵌入 `MessageBubble.tsx` | F-014 复用现有 WS 通道 |
| 审计日志服务 | `application/services/mcp_audit_service.py` | `components/mcp/McpAuditPanel.tsx` | F-017 |
| McpStore | — | `stores/mcpStore.ts` | 状态管理 |
| 路由注册 | — | `routes.tsx` | 注册 3 页 + 1 Tab |

### 3.3 P2（binding + create，2026-06-09 ~ 06-11）

| 模块 | 后端文件 | 前端文件 | 备注 |
|------|----------|----------|------|
| 绑定服务 | `application/services/mcp_binding_service.py` | `components/agent/McpBindingPanel.tsx` | F-008/F-009/F-010/F-011 |
| 创建服务（stdio/sse/http） | `application/services/mcp_create_service.py` | `pages/McpCreatePage.tsx` + `components/mcp/McpCreateForm.tsx` + `components/mcp/McpTemplateList.tsx` | F-018/F-019/F-020 |
| **CLI Adapter `attach_mcp(...)` 扩展点** | `domain/llm/protocol.py::AgentRuntime`（抽象方法）+ `infrastructure/llm/{claude_code,opencode,pi_agent}_runtime.py`（实现） | — | 关键：本期只做 CLI 注入；下期 SDK 沿扩展点 |
| dry-run 沙箱（简化版） | `infrastructure/mcp/dry_run.py` | `components/mcp/McpCreateForm.tsx` 内联「试运行」 | E-03：单 Docker + compose 资源限额 |

### 3.4 P4（收束，2026-06-12 ~ 06-15）

| 产物 | 位置 | 内容 |
|------|------|------|
| ADR | `worklogs/decisions/NNNN-mcp-cli-adapter-extension.md` | `attach_mcp(...)` 协议 + 下期 SDK Adapter 接入计划 |
| 收束报告 | `worklogs/袁/2026-06-15_mcp-p4-closure.md` | 4 阶段硬闸门（整理/测试/审计/验证）+ 测试覆盖率 + 性能 SLO |
| NB-02 下期清单 | `worklogs/袁/2026-06-15_mcp-nb02-backlog.md` | 沙箱矩阵 / K4 / SSRF / Vault / SDK / Codex+Trae |

---

## 4. 不在本期范围（NB-02 下期清单，存档 §README §4）

| 模块 | 上一版编号 | 下期路径 |
|------|------------|----------|
| 多 OS 沙箱矩阵 | M-C01 | `infrastructure/sandbox/{macos,windows,linux}/` |
| K4 gRPC 安全扫描器 | M-C02 | `infrastructure/k4_scanner/`（gRPC + proto） |
| DNS pinning | M-C04 | `infrastructure/dns_pinning/` |
| 网络 ACL（iptables/ipset） | M-C05 | `infrastructure/network_acl/` |
| SSRF guard | M-C06 | `infrastructure/ssrf_guard/` |
| Vault secret transit | M-C07 | `infrastructure/secret/vault_client.py` |
| Webhook 验签 | M-A03 | `api/v1/webhook/{github,gitlab,bitbucket}.py` |
| 分布式 cron + leader 选举 | M-A04 | `infrastructure/cron/` + Redis lock |
| 进程池 | M-B02 | **本期不引入**（违反 AR-02） |
| ACL 迁移 Saga | M-C09 | `application/mcp/saga.py` |
| SDK Adapter | F-013 | 沿 `attach_mcp(...)` 扩展点增量交付 |
| OpenTelemetry | 散落 | 不引入（B-11 明确不做） |
| gRPC / K8s | 散落 | 不引入（非现有栈） |

---

## 5. 命名与文件约束

| 项 | 规范 | 依据 |
|----|------|------|
| Python 文件 | snake_case | CR-02 |
| Python 类 | PascalCase | CR-02 |
| Python 包 | 全小写无下划线 | CR-02 |
| Pydantic 模型 | `schemas/mcp.py` 内集中 | CR-04 |
| 数据库表 | `snake_case`（与 §十 口径统一） | CR-03 |
| 前端组件 | PascalCase.tsx | CR-07 |
| 前端 store | camelCase.ts（Zustand） | CR-07 |
| API 端点 | kebab-case + `{error:{code,message}}` | AP-01~07 |
| WS 消息 | snake_case 事件名 | 沿用 chatStore 既有 |
| 日志 | 项目既有 logger（不用 structlog） | I-04 |
| 配置 | 环境变量 + 现有 `core/config.py` | 不用 Vault |
| 监控 | trace_id 贯穿（不用 OTel） | B-11 |

---

## 6. 跨层依赖（AR-01 洋葱方向）

```
L5 Presentation (React)
       │  HTTP/WS
       ↓
L4 API (FastAPI routers)
       │  调用
       ↓
L3 Application (编排服务)
       │  依赖
       ↓
L2 Domain (实体 + 业务规则)
       ↑  实现接口
L1 Infrastructure (DB / AgentRuntime / Docker sandbox)
```

- L1 实现 L2 接口（依赖倒置）
- L3 调用 L2 实体；不直接碰 L1
- L4 只做协议层；不写业务
- L5 只做 UI；不直接查 DB

MCP 注入链路（满足 AR-02）：

```
L4 API (POST /api/mcp/bindings)
       ↓
L3 Application (mcp_binding_service.create)
       ↓
L2 Domain (AgentMCPBinding 校验 + AgentRuntime.attach_mcp 抽象)
       ↓ 实现接口（依赖倒置）
L1 Infrastructure (infrastructure/llm/*_runtime.py 实现 attach_mcp)
       ↓ 注入到 Runtime 进程（stdio/env/CLI 参数）
CLI Adapter (claude_code_runtime 等)
```

---

## 7. 与既有代码的兼容

- 现有抽象基类 `AgentRuntime(ABC)`（`domain/llm/protocol.py`）保留，新增 `attach_mcp` 抽象方法；3 个 `infrastructure/llm/*_runtime.py` 实现
- 现有 alembic 0001-0005 不动，0006 起续写（MCP 相关迁移）
- 现有 L4 API 端点不动，mcp.py 是新文件
- 现有 L5 UI（AppShell / AgentDetailPage）扩展，不重写
- 现有 `messages_ops` 风格的 Redis 通道复用，不引 eventbus

---

## 8. 部署形态

| 项 | 本期 |
|----|------|
| Docker | 沿用 `src/docker/docker-compose.yml` |
| 后端容器 | `backend`（既有） |
| 前端容器 | `frontend`（既有） |
| DB | `postgres`（既有） |
| 缓存 | `redis`（既有） |
| dry-run 沙箱 | 与 backend 同一 compose 网络的 `mcp-sandbox` 服务（`docker_sandbox` image，单容器 + resources.limits） |
| Nginx | 沿用 |
| K8s | **不引入**（I-04） |

---

*本 FS-MCP 是 MCP 接入的**实际落点**唯一权威。落地时按 §3 的 4 阶段节奏推进，每阶段先 PR-01 冻结端点 → PR-09 同步 specs/ → 实现 → verify。*
