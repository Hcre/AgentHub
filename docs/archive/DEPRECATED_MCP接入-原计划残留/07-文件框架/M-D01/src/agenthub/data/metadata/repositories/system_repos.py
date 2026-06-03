"""System 域 Repository 集合 - M-D01.

[文件路径] src/agenthub/data/metadata/repositories/system_repos.py
[文件职责] 聚合 CronJob / CronRunLog / K4RuleSet / K4TestCorpus / ACLRule / SecretRef / MCPMigrationHistory 7 个 Repository
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-007/008/015/016/017/018/019]
[功能描述]
  功能1: CronJobRepository / CronRunLogRepository - Cron 任务与日志
  功能2: K4RuleSetRepository / K4TestCorpusRepository - K4 规则集 + 校准
  功能3: ACLRuleRepository - 网络 ACL 规则
  功能4: SecretRefRepository - Vault secret 元数据引用
  功能5: MCPMigrationHistoryRepository - ACL 迁移 append-only 记录
[依赖关系]
  依赖文件: ./base.py + ../models/{cron_job,cron_run_log,k4_rule_set,k4_test_corpus,acl_rule,secret_ref,mcp_migration_history}.py
  被依赖文件: ../unit_of_work.py + M-A04 / M-C02 / M-C05 / M-C07 / M-C09 services
[注意事项]
  注意1: SecretRefRepository 严禁存储 secret 明文（仅 name + 轮换时间）
  注意2: ACLRuleRepository.add 用 rule_hash UNIQUE 实现幂等（[IC-012]）
  注意3: MCPMigrationHistoryRepository append-only
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2 + SEC]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-007/008/015/016/017/018/019]
"""

# ============================================================
# [类名] CronJobRepository
# [职责] cron_jobs 表 CRUD
# [方法列表]
#   async get(name: str) → CronJob | None
#   async list_due(now_ts: datetime, limit: int = 100) → list[CronJob] - next_run <= now AND enabled
#   async update_next_run(name: str, last_run: datetime, next_run: datetime, fail_increment: bool = False) → None
# [来源标注] [DD-001:DS-007]
# ============================================================

# ============================================================
# [类名] CronRunLogRepository
# [职责] cron_run_log 分区表写入
# [方法列表]
#   async add(entity: CronRunLog) → int
#   async list_recent(job_name: str, limit: int = 50) → list[CronRunLog]
# [来源标注] [DD-001:DS-008]
# ============================================================

# ============================================================
# [类名] K4RuleSetRepository
# [职责] k4_rule_set 表 CRUD + 版本管理
# [方法列表]
#   async get_active() → K4RuleSet | None
#   async get_by_version(version: str) → K4RuleSet | None
#   async activate(id: UUID) → None - 旧 active 设 deprecated；新 id 设 active（单事务）
# [来源标注] [DD-001:DS-015]
# ============================================================

# ============================================================
# [类名] K4TestCorpusRepository
# [职责] k4_test_corpus 表 CRUD
# [方法列表]
#   async add(entity: K4TestCorpus) → UUID
#   async get_latest_by_rule_set(rule_set_id: UUID) → K4TestCorpus | None
# [来源标注] [DD-001:DS-016]
# ============================================================

# ============================================================
# [类名] ACLRuleRepository
# [职责] acl_rules 表 CRUD + 幂等 apply
# [方法列表]
#   async add_idempotent(entity: ACLRule) → UUID - 用 rule_hash UNIQUE 实现幂等
#   async list_by_workspace(workspace_id: UUID) → list[ACLRule]
#   async revoke(id: UUID) → None
# [来源标注] [DD-001:DS-017 + IC-012]
# ============================================================

# ============================================================
# [类名] SecretRefRepository
# [职责] secret_refs 表 CRUD（仅元数据，不存明文）
# [方法列表]
#   async get_by_name(name: str) → SecretRef | None
#   async list_due_rotation(now_ts: datetime) → list[SecretRef] - next_rotation <= now
#   async mark_rotated(name: str, rotated_at: datetime, next_rotation: datetime) → None
# [安全约束] 任何 add/update 入参严禁含 value/plaintext 字段（mypy 类型边界）
# [来源标注] [DD-001:DS-018 + TDR-010]
# ============================================================

# ============================================================
# [类名] MCPMigrationHistoryRepository
# [职责] mcp_migration_history append-only 写入
# [方法列表]
#   async append(workspace_id: UUID, snapshot_hash: str, status: str, applied_count: int) → int
#   async list_by_workspace(workspace_id: UUID) → list[MCPMigrationHistory]
#   update/delete → raise AppendOnlyViolation
# [来源标注] [DD-001:DS-019]
# ============================================================
