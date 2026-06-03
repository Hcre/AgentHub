"""AppendOnly 模型保护测试 - M-D01.

[文件路径] src/agenthub/data/metadata/tests/test_models_appendonly.py
[文件职责] 验证 InboxDecision / MCPSubmissionHistory / MCPMigrationHistory 拒绝 UPDATE/DELETE
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-010/013/019 + DD洞察-5]
[依赖关系] ../models/{inbox_decision, mcp_submission_history, mcp_migration_history}.py + conftest.py
[代码风格] 遵循 [DD-001:CS-MCP §1.7]
[创建日期] 2026-06-03
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-010/013/019 + DD洞察-5]
"""

# ============================================================
# [测试场景 1: test_inbox_decision_when_update_attempted_then_raises_appendonly_violation]
# [断言: ORM event 拦截，抛 AppendOnlyViolation]
# [Mock: 真 PG + ORM update]
# ============================================================

# ============================================================
# [测试场景 2: test_inbox_decision_when_delete_attempted_then_raises_appendonly_violation]
# [断言: ORM event 拦截 + PG trigger 二次拦截]
# [Mock: 真 PG]
# ============================================================

# ============================================================
# [测试场景 3: test_inbox_decision_when_raw_sql_update_then_pg_trigger_blocks]
# [断言: 绕过 ORM 用 raw SQL UPDATE，PG trigger 抛错（双重防护）]
# [Mock: 真 PG + execute("UPDATE inbox_decision ...")]
# ============================================================

# ============================================================
# [测试场景 4: test_submission_history_when_append_only_then_works]
# [断言: append 成功；后续 update/delete 抛 AppendOnlyViolation]
# [Mock: 真 PG]
# ============================================================

# ============================================================
# [测试场景 5: test_migration_history_when_append_then_chain_visible]
# [断言: list_by_workspace 按 occurred_at 顺序返回历史]
# [Mock: 真 PG]
# ============================================================
