"""Approval 域 Repository 集合 - M-D01.

[文件路径] src/agenthub/data/metadata/repositories/approval_repos.py
[文件职责] 聚合 InboxQueue / InboxDecision / Allowlist30d 3 个 Repository
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-009/010/011 + IC-005/IC-006 + MD:M-B04 + ADR-006]
[功能描述]
  功能1: InboxQueueRepository - 审批待办增/查/状态变更 + 行锁
  功能2: InboxDecisionRepository - append-only 决策写入 + 哈希链查询
  功能3: Allowlist30dRepository - 30 天许可缓存写入与查询（Cache-aside 由 M-B04 协调）
[依赖关系]
  依赖文件: ./base.py, ../models/inbox_queue.py, ../models/inbox_decision.py,
            ../models/allowlist_30d.py, ./specifications.py
  被依赖文件: ../unit_of_work.py, M-B04 services
[注意事项]
  注意1: decide 流程必须 lock_pending(queue_id) → INSERT inbox_decision → UPSERT allowlist 一个事务（UoW 保证）
  注意2: InboxDecisionRepository.update/delete 必须 raise AppendOnlyViolation（双重保险）
  注意3: 重复 decide（同 queue_id + decision_hash）由 UNIQUE 约束返回 IntegrityError；调用方需捕获并返回幂等结果（[IC-006 幂等性]）
  注意4: PG 写后 500ms 异步刷 Redis allowlist 由 M-B04 协调，本模块不发起（[AR洞察-3]）
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-009/010/011 + IC-005/006 + ADR-006 + AR洞察-3 + DD洞察-5]
"""

# ============================================================
# [类名] InboxQueueRepository
# [职责] inbox_queue 表 CRUD + 行锁 + Spec 查询
# [继承] BaseRepository[InboxQueue]
# [方法列表]
#   async add_pending(workspace_id, mcp_id, tool, args_hash, submitter_id, expires_at) → UUID
#     - INSERT；遇 partial UNIQUE 冲突返回已有 id（幂等，[IC-005]）
#   async lock_pending(queue_id: UUID) → InboxQueue - SELECT FOR UPDATE；status=pending 才返回
#   async mark_decided(queue_id: UUID, decision: str) → None - 更新 status 为 allowed/denied
#   async list_expired_pending(now_ts: datetime) → list[InboxQueue] - timeout_scan
#   async mark_timeout(queue_id: UUID) → None
# [关联接口契约] IC-005 check_and_queue / IC-006 decide
# [来源标注] [DD-001:DS-009 + IC-005/006]
# ============================================================

# ============================================================
# [类名] InboxDecisionRepository
# [职责] inbox_decision 表 append-only 写入 + 哈希链查询
# [继承] BaseRepository[InboxDecision]
# [方法列表]
#   async add(entity: InboxDecision) → UUID
#     - INSERT；遇 (queue_id, decision_hash) UNIQUE 冲突上抛 IntegrityError 由调用方做幂等
#   async get_last_decision(queue_id: UUID) → InboxDecision | None
#   async get_chain(start_decision_id: UUID, limit: int = 100) → list[InboxDecision] - 哈希链回溯
#   update/delete → raise AppendOnlyViolation（覆盖父类禁用）
# [来源标注] [DD-001:DS-010 + IC-006 + DD洞察-5]
# ============================================================

# ============================================================
# [类名] Allowlist30dRepository
# [职责] allowlist_30d 表 UPSERT + Spec 查询
# [继承] BaseRepository[Allowlist30d]
# [方法列表]
#   async upsert(workspace_id, mcp_id, tool, args_hash, expires_at) → UUID - ON CONFLICT DO UPDATE
#   async is_allowed(workspace_id, mcp_id, tool, args_hash, now_ts) → bool - DB 直查（cache miss 时）
#   async cleanup_expired(now_ts: datetime) → int - Cron 调用，DELETE WHERE expires_at < now_ts
# [来源标注] [DD-001:DS-011 + ADR-006]
# ============================================================
