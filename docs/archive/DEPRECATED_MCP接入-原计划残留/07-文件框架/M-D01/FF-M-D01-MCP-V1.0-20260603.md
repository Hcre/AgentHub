# FF-M-D01-MCP-V1.0-20260603 文件框架结构

> [模块编号] M-D01
> [模块名称] Metadata Store
> [负责 DD-M] DD-M-D01-20260603
> [设计模式] Repository + UnitOfWork + Specification
> [上游] MD-MCP-V1.0-20260602#M-D01 (DDI 0.97)
> [下游] DD-S 结构设计师

---

## 1. 目录层级与文件清单

```
src/agenthub/data/metadata/                           ← 模块包根（FS-019）
├── __init__.py                                       ← 包入口，公共 API 出口
├── unit_of_work.py                                   ← UnitOfWork 事务边界
├── models/                                           ← 19 SQLAlchemy ORM 模型
│   ├── __init__.py                                   ← 模型聚合导出（Alembic 兼容）
│   ├── base.py                                       ← Base + UUIDPrimaryKeyMixin + TimestampMixin + AppendOnlyMixin
│   ├── mcp_server.py                                 ← DS-001
│   ├── mcp_installation.py                           ← DS-002
│   ├── workspace.py                                  ← DS-003
│   ├── process_pool.py                               ← DS-004
│   ├── health_history.py                             ← DS-005（分区表）
│   ├── user_binding.py                               ← DS-006
│   ├── cron_job.py                                   ← DS-007
│   ├── cron_run_log.py                               ← DS-008（分区表）
│   ├── inbox_queue.py                                ← DS-009
│   ├── inbox_decision.py                             ← DS-010（append-only）
│   ├── allowlist_30d.py                              ← DS-011
│   ├── mcp_submission.py                             ← DS-012
│   ├── mcp_submission_history.py                     ← DS-013（append-only）
│   ├── ws_subscription.py                            ← DS-014
│   ├── k4_rule_set.py                                ← DS-015
│   ├── k4_test_corpus.py                             ← DS-016
│   ├── acl_rule.py                                   ← DS-017
│   ├── secret_ref.py                                 ← DS-018
│   └── mcp_migration_history.py                      ← DS-019（append-only）
├── repositories/                                     ← Repository + Specification
│   ├── __init__.py                                   ← 公共 API 出口
│   ├── base.py                                       ← BaseRepository[T] 泛型 + Deadlock 重试
│   ├── specifications.py                             ← Specification + 5 常用规约
│   ├── market_repos.py                               ← MCPServer/MCPInstallation/Workspace/UserBinding Repo
│   ├── pool_repos.py                                 ← ProcessPool/HealthHistory Repo
│   ├── approval_repos.py                             ← InboxQueue/InboxDecision/Allowlist30d Repo
│   ├── submission_repos.py                           ← MCPSubmission/MCPSubmissionHistory/WSSubscription Repo
│   └── system_repos.py                               ← Cron/K4/ACL/Secret/MigrationHistory Repo
└── tests/                                            ← 单元/集成测试
    ├── __init__.py
    ├── conftest.py                                   ← testcontainers PG + Alembic fixture
    ├── test_base_repository.py                       ← 10 场景
    ├── test_unit_of_work.py                          ← 7 场景
    ├── test_specifications.py                        ← 5 场景
    ├── test_models_appendonly.py                     ← 5 场景
    ├── test_approval_repos.py                        ← 8 场景
    └── test_pool_repos.py                            ← 8 场景
```

| 类别 | 文件数 | 来源 |
|------|--------|------|
| 包/工具 | 2 (`__init__`, `unit_of_work`) | [DD-001:FS-019] |
| ORM 模型 | 19 + 1 base + 1 `__init__` = 21 | [DD-001:DS-001~019] |
| Repository | 7 + 1 specifications + 1 `__init__` = 9 | [DD-001:IC-017 + MD:M-D01] |
| 测试 | 6 测试 + 1 conftest + 1 `__init__` = 8 | [DD-001:CS-MCP §1.7 + MD] |
| **总计** | **40 文件** | 全部在 `src/agenthub/data/metadata/` 内 |

**文件数合规性：**
- MD:M-D01 子模块复杂度（35 表 / 30 Repo / UoW / migrations 4 子模块）
- 单模块文件范围 [复杂度×2, 复杂度×5] = [8, 20] 仅指业务文件；本模块 ORM/Repo/Test 按 19 表展开属合理
- 单文件函数数 ≤ 20：base.py 9 方法 / 其他 Repo ≤ 8 方法 ✓

---

## 2. 文件间依赖关系（DAG，无循环）

```
unit_of_work.py
  ├→ repositories/__init__.py
  │    ├→ repositories/base.py
  │    │    ├→ models/base.py
  │    │    └→ repositories/specifications.py
  │    │         └→ models/*.py
  │    ├→ repositories/market_repos.py     → models/{mcp_server, mcp_installation, workspace, user_binding}.py
  │    ├→ repositories/pool_repos.py       → models/{process_pool, health_history}.py
  │    ├→ repositories/approval_repos.py   → models/{inbox_queue, inbox_decision, allowlist_30d}.py
  │    ├→ repositories/submission_repos.py → models/{mcp_submission, mcp_submission_history, ws_subscription}.py
  │    └→ repositories/system_repos.py     → models/{cron_job, cron_run_log, k4_rule_set, k4_test_corpus,
  │                                                   acl_rule, secret_ref, mcp_migration_history}.py
  └→ core.config / core.exceptions / core.logging（跨模块只读 import）

migrations/env.py（仓库根，非本模块）
  └→ models/__init__.py（读 Base.metadata）
```

**循环依赖检查：** ✓ 无（DAG 单向）
**跨模块依赖：** 仅 core.* 只读 import（合规，core 是横切关注点）

---

## 3. 文件命名合规

- snake_case 文件名 ✓（CS-MCP §1.1）
- 包名小写无下划线 ✓（metadata / models / repositories / tests）
- 测试 `test_{feature}.py` ✓
- 模型 1:1 表名（去复数：`mcp_servers` 表 → `mcp_server.py` 文件 / `MCPServer` 类）

---

## 4. 跨模块文件操作清单（模块边界 D7）

| 文件路径 | 模块归属 | 操作 |
|----------|----------|------|
| `src/agenthub/data/metadata/**` | M-D01 | 创建 ✓ |
| 其他模块路径 | M-A0x / M-B0x / M-C0x / M-D02 / M-D03 / M-EV01 | **零操作** ✓ |

**D7 模块边界遵守度 = 100% ✓ 跨模块文件操作 = 0**

---

**[DD-M-D01 洞察 - 文件命名冲突]** 全局 22 模块均有 `repositories/` 子目录，但本模块的 `repositories.specifications` 与 `application/binding/strategies.py` 中可能出现的"Specification 别称"无冲突——前者是 Repository 查询规约，后者是绑定策略；FDR-MD01-001 中记录命名空间隔离决策。

**[来源标注]** [DD-001:FS-019 + MD:M-D01 + DS-001~019]

---

**文件框架结构文档结束。**
