# MD-MCP-V1.0-20260602（修订版）— MCP 接入数据模型

> **版本**：V1.0-rev（2026-06-03 重写）
> **修订依据**：可行性清单 I-01/I-05/I-08/I-10（30 实体 → 3 表；`user_mcp_installations` → `workspace_mcp_installations`）
> **上一版**：30 个数据实体 + 22 模块 + 新建 alembic env（与现链 0001-0005 不衔接）
> **本文档**：MCP 接入的**数据模型**权威（4 张表 = §十 + 工具调用日志）
> **单一权威入口**：[`../../README-REVISION.md`](../../README-REVISION.md)

---

## 0. 修订要点

| 项 | 上一版 | **修订版** |
|----|--------|-----------|
| 实体数 | 30 | **4 张表**（mcp_servers / workspace_mcp_installations / agent_mcp_bindings / mcp_tool_call_logs） |
| 表名口径 | `user_mcp_installations`（PRD F-004） | **`workspace_mcp_installations`**（§十 + E-01 决策） |
| 迁移 | 新建 `migrations/`（新 alembic env） | **续在现有 alembic 链（0006+）** |
| 多租户/工作区 | 散落多表 | **统一 workspace 维度**（与现有 workspace 模型一致） |
| 工具调用日志 | 散落 | **新增 `mcp_tool_call_logs` 表**（F-014 + F-017） |
| 业务规则文档 | 散落 | **集中在 `domain/mcp/rules.py`**（批量≤50、版本≤50、args_hash=SHA256(sorted_json)） |

---

## 1. 4 张表（沿用 §十 + 工具调用日志）

> 同步在 `docs/specs/03-data-model` 增补（PR-09），本节为本期权威。
>
> **⚠️ 二次对账 errata（2026-06-03，见 [`../README-REVISION.md` §9](../README-REVISION.md)）**：下表 FK 与类型为**逻辑表述**。落地时：`workspace_id`/`created_by`/`installed_by` 现库无对应表 → **裸 UUID 无 FK**（`workspace_id` 暂存 `session_id`，R1/R2）；ENUM/JSONB/TEXT[]/CHAR/BIGSERIAL/GIN → **可移植类型**（`String/JSON/BigInteger.with_variant`，SQLite 测试强制，R10）；`trace_id` 为净新增非"既有"（R4）。

### 1.1 `mcp_servers` — MCP 元数据

| 字段 | 类型 | 约束 | 备注 |
|------|------|------|------|
| `mcp_id` | UUID | PK | |
| `name` | VARCHAR(128) | NOT NULL, UNIQUE | 显示名 |
| `slug` | VARCHAR(128) | NOT NULL, UNIQUE | URL 友好标识 |
| `description` | TEXT | | |
| `transport` | ENUM(`stdio`,`sse`,`streamable_http`) | NOT NULL | F-018/F-019 |
| `config_schema` | JSONB | NOT NULL | 入参 schema（用于 F-024 校验） |
| `config_json` | JSONB | NOT NULL | 实际入参（环境变量、命令等） |
| `args_hash` | CHAR(64) | NOT NULL | SHA256(sorted_json(config)) — 用于幂等去重 |
| `version` | VARCHAR(32) | NOT NULL, ≤50 字符 | 业务规则：版本字符串 ≤50 |
| `latest` | BOOLEAN | NOT NULL DEFAULT FALSE | 是否最新版本 |
| `official` | BOOLEAN | NOT NULL DEFAULT FALSE | R-01 官方 vs 社区 |
| `tags` | TEXT[] | | F-002 搜索用 |
| `status` | ENUM(`draft`,`published`,`deprecated`) | NOT NULL DEFAULT `draft` | R-01 审核 |
| `created_by` | UUID | NOT NULL, FK→users | R-02 创建者 |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `dry_run_result` | JSONB | | E-03 干跑结果（30s 超时 + CPU/Mem） |
| `dry_run_at` | TIMESTAMPTZ | | 干跑时间 |
| `install_count` | INT | NOT NULL DEFAULT 0 | 业务规则：批量≤50 同 workspace 限制 |

**索引**：
- `idx_mcp_servers_name` (name)
- `idx_mcp_servers_slug` (slug)
- `idx_mcp_servers_args_hash` (args_hash) — 幂等去重
- `idx_mcp_servers_tags` GIN (tags) — 搜索
- `idx_mcp_servers_status_latest` (status, latest) — 列表分页

**业务规则**（集中 `domain/mcp/rules.py`）：
- name 全局唯一
- args_hash = SHA256(sorted_json(config))（F-024 幂等）
- 单 workspace 批量安装 ≤ 50（F-022 模板库）
- version 字符串 ≤ 50 字符

---

### 1.2 `workspace_mcp_installations` — 工作区 MCP 安装（E-01 修正）

| 字段 | 类型 | 约束 | 备注 |
|------|------|------|------|
| `installation_id` | UUID | PK | F-004「生成 instance_id」 |
| `workspace_id` | UUID | NOT NULL, FK→workspaces | **E-01 关键：按 workspace 维度，不是 user** |
| `mcp_id` | UUID | NOT NULL, FK→mcp_servers | |
| `installed_by` | UUID | NOT NULL, FK→users | R-03 安装者（审计） |
| `instance_name` | VARCHAR(128) | NOT NULL | workspace 内可重名 |
| `config_overrides` | JSONB | | 用户覆盖（环境变量等） |
| `status` | ENUM(`installing`,`ready`,`failed`) | NOT NULL DEFAULT `installing` | F-004 验收：5s 内 ready |
| `error_code` | VARCHAR(64) | | 失败时填 |
| `error_message` | TEXT | | |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `last_health_check_at` | TIMESTAMPTZ | | |

**索引**：
- `idx_workspace_mcp_installations_workspace` (workspace_id, status)
- `idx_workspace_mcp_installations_mcp` (mcp_id)
- `uq_workspace_mcp_installations_workspace_mcp_name` UNIQUE (workspace_id, instance_name)

**业务规则**（F-004 验收）：
- 同 `workspace_id` + 同 `mcp_id` + 同 `args_hash` 重复安装 → 返回同一 `installation_id`（**幂等**）
- 不同 `workspace_id` 可独立安装同一 `mcp_id`
- 同 `workspace_id` 内 `instance_name` 唯一

---

### 1.3 `agent_mcp_bindings` — Agent 绑定

| 字段 | 类型 | 约束 | 备注 |
|------|------|------|------|
| `binding_id` | UUID | PK | F-009 |
| `agent_id` | UUID | NOT NULL, FK→agents | R-03 绑定 |
| `installation_id` | UUID | NOT NULL, FK→workspace_mcp_installations | |
| `tool_subset` | TEXT[] | | 默认 = MCP 全部 tool；F-009「暴露的 tools 子集」 |
| `status` | ENUM(`active`,`paused`,`removed`) | NOT NULL DEFAULT `active` | |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `unbound_at` | TIMESTAMPTZ | | 解绑时间（软删） |

**索引**：
- `idx_agent_mcp_bindings_agent` (agent_id, status)
- `idx_agent_mcp_bindings_installation` (installation_id)
- `uq_agent_mcp_bindings_agent_installation` UNIQUE (agent_id, installation_id) — 唯一绑定

**业务规则**（F-009 验收）：
- 一个 `agent_id` 对同一 `installation_id` 至多 1 条 active 绑定
- 解绑是软删（`status=removed` + `unbound_at`），保留审计
- F-011 验收：解绑 5s 内 WS 路由表更新

---

### 1.4 `mcp_tool_call_logs` — 工具调用日志（F-014 + F-017 审计）

| 字段 | 类型 | 约束 | 备注 |
|------|------|------|------|
| `log_id` | BIGSERIAL | PK | 高写入，分区候选（下期） |
| `trace_id` | VARCHAR(32) | NOT NULL | 既有 trace_id 格式，**不用 OTel** |
| `binding_id` | UUID | NOT NULL, FK→agent_mcp_bindings | |
| `agent_id` | UUID | NOT NULL, FK→agents | |
| `workspace_id` | UUID | NOT NULL, FK→workspaces | |
| `mcp_id` | UUID | NOT NULL, FK→mcp_servers | |
| `tool_name` | VARCHAR(128) | NOT NULL | |
| `args_hash` | CHAR(64) | NOT NULL | SHA256(sorted_json(args)) |
| `result_code` | VARCHAR(32) | NOT NULL | SUCCESS / TIMEOUT / ERROR / CANCELLED |
| `duration_ms` | INT | NOT NULL | |
| `error_message` | TEXT | | 失败时填 |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | 默认索引 |

**索引**：
- `idx_mcp_tool_call_logs_workspace_created` (workspace_id, created_at DESC) — 90 天查询
- `idx_mcp_tool_call_logs_agent_created` (agent_id, created_at DESC)
- `idx_mcp_tool_call_logs_trace` (trace_id) — 链路追踪

**业务规则**（F-017 验收）：
- 异步落盘（消息队列 + 后台写）
- R-04 可按 workspace + 时间范围查询 90 天
- 导出 CSV/JSONL（F-017 验收 ③）

---

## 2. 关系图

```
workspaces (既有)
    │
    │ 1:N
    ↓
workspace_mcp_installations ──→ mcp_servers
    │                              │
    │ 1:N                          │ 1:N
    ↓                              ↓
agent_mcp_bindings ────────→ mcp_tool_call_logs
    │
    │ N:1
    ↓
agents (既有)
```

---

## 3. 迁移计划（CR-03 + I-10）

### 3.1 续在现有 alembic 链

```
src/backend/alembic/versions/
├── 0001_initial.py
├── 0002_*.py
├── 0003_*.py
├── 0004_*.py
├── 0005_*.py
├── 0006_mcp_servers.py                    # ← 本期新增
├── 0007_workspace_mcp_installations.py     # ← 本期新增
├── 0008_agent_mcp_bindings.py              # ← 本期新增
└── 0009_mcp_tool_call_logs.py              # ← 本期新增
```

### 3.2 流程

1. **PR-09 先同步**：`docs/specs/03-data-model` 增 §MCP 子节（本 MD-MCP 引用）
2. **CR-03 顺序**：每张表一个 alembic revision，独立 review
3. **不引新 alembic env**：沿用 `src/backend/alembic/env.py`
4. **不下线迁移**：所有变更 forward-only，本期不引入 rollback 自动化（下期）

---

## 4. 缓存策略

| Key | Value | TTL | 失效 |
|-----|-------|-----|------|
| `mcp:list:{workspace_id}:{page}` | JSON 列表 | 5 min | mcp_servers.updated_at 变化时 |
| `mcp:detail:{mcp_id}` | JSON 详情 | 10 min | mcp_servers.updated_at 变化时 |
| `mcp:bindings:{agent_id}` | JSON 绑定列表 | 30s | agent_mcp_bindings 变化时 |
| `mcp:tool_calls:{trace_id}` | 工具调用链 | 24h | TTL 自动 |

---

## 5. 不在本期范围（数据模型层）

- ❌ 30 实体中其它 26 个（散落多领域，与 MCP 正交）
- ❌ Saga 分布式事务表（M-C09）
- ❌ 工具调用日志分区（90 天内单表足够；下期 NB-02 引入 TimescaleDB / 分区）
- ❌ ts_log 时序独立表（用既有 logger + Postgres JSONB）
- ❌ cache 独立元数据（用既有 Redis）

---

## 6. 业务规则（`domain/mcp/rules.py` 集中实现）

| 规则 | 出处 | 实现 |
|------|------|------|
| 安装幂等（workspace + mcp_id + args_hash） | F-004 | `is_idempotent_install(...)` |
| 批量安装 ≤ 50 | F-022 | `validate_batch_size(...)` |
| 版本字符串 ≤ 50 | F-020 | `validate_version(...)` |
| args_hash = SHA256(sorted_json) | F-024 | `compute_args_hash(...)` |
| 绑定唯一性（agent + installation） | F-009 | `validate_binding_uniqueness(...)` |
| 解绑 5s 内 WS 路由更新 | F-011 | `notify_ws_routing_on_unbind(...)`（沿用既有 WS 通道） |
| 干跑超时 30s | F-021 | `run_dry_run(... timeout=30)` |
| 干跑资源限额（CPU=1, Mem=512MB, net=隔离） | F-021 | `infrastructure/mcp/dry_run.run(...)` |

---

*本 MD-MCP 是 MCP 接入**数据模型**唯一权威。同步更新 `docs/specs/03-data-model`（PR-09）后，再开始 alembic 0006+ 迁移。*
