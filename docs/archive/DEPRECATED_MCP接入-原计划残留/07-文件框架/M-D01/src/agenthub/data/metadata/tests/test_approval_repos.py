"""Approval 域 Repository 集成测试 - M-D01.

[文件路径] src/agenthub/data/metadata/tests/test_approval_repos.py
[文件职责] 验证 InboxQueueRepository / InboxDecisionRepository / Allowlist30dRepository 业务路径
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:IC-005/006 + DS-009/010/011 + ADR-006]
[依赖关系] ../repositories/approval_repos.py + conftest.py
[代码风格] 遵循 [DD-001:CS-MCP §1.7]
[创建日期] 2026-06-03
[作者] DD-M-D01-20260603
[来源标注] [DD-001:IC-005/006 + ADR-006]
"""

# ============================================================
# [测试场景 1: test_add_pending_when_duplicate_then_returns_existing_id_idempotent]
# [断言: 第二次调用返回第一次的 id（partial UNIQUE 幂等）]
# [Mock: 真 PG]
# ============================================================

# ============================================================
# [测试场景 2: test_lock_pending_when_concurrent_then_serializes]
# [断言: 两个 asyncio task 顺序获取锁，第二个等待]
# [Mock: 真 PG + asyncio.gather + 两个 UoW 实例]
# ============================================================

# ============================================================
# [测试场景 3: test_mark_decided_when_already_decided_then_idempotent]
# [断言: 重复 mark_decided 不抛错；状态保持]
# [Mock: 真 PG]
# ============================================================

# ============================================================
# [测试场景 4: test_decision_add_when_unique_violation_then_idempotent]
# [断言: (queue_id, decision_hash) UNIQUE 冲突时返回已有 decision_id]
# [Mock: 真 PG]
# ============================================================

# ============================================================
# [测试场景 5: test_list_expired_pending_when_some_expired_then_returns_filtered]
# [断言: 仅返回 expires_at < now AND status='pending']
# [Mock: 真 PG + 预置 5 行（3 expired, 2 valid）]
# ============================================================

# ============================================================
# [测试场景 6: test_allowlist_upsert_when_repeat_then_extends_expires]
# [断言: ON CONFLICT DO UPDATE 更新 expires_at]
# [Mock: 真 PG]
# ============================================================

# ============================================================
# [测试场景 7: test_allowlist_cleanup_when_expired_then_removed]
# [断言: cleanup_expired 删除 expires_at < now 行]
# [Mock: 真 PG]
# ============================================================

# ============================================================
# [测试场景 8: test_appendonly_decision_when_update_attempted_then_raises]
# [断言: AppendOnlyViolation]
# [Mock: 真 PG]
# ============================================================
