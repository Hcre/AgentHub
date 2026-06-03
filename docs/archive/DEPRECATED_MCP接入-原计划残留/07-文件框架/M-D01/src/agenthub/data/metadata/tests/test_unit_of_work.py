"""UnitOfWork 事务边界与状态机测试 - M-D01.

[文件路径] src/agenthub/data/metadata/tests/test_unit_of_work.py
[文件职责] 验证 UnitOfWork 上下文管理、commit/rollback 语义、连接池处理
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:IC-017 + MD:M-D01]
[依赖关系] ../unit_of_work.py + conftest.py
[代码风格] 遵循 [DD-001:CS-MCP §1.7]
[创建日期] 2026-06-03
[作者] DD-M-D01-20260603
[来源标注] [DD-001:IC-017]
"""

# ============================================================
# [测试场景 1: test_uow_when_exit_normally_then_auto_commits]
# [断言: __aexit__(None,None,None) 后数据已持久化；外部 session 可见]
# [Mock: 真 PG]
# ============================================================

# ============================================================
# [测试场景 2: test_uow_when_exception_inside_then_auto_rolls_back]
# [断言: 异常后数据未持久化；外部查询返回空]
# [Mock: 真 PG；在 with 块内抛 ValueError]
# ============================================================

# ============================================================
# [测试场景 3: test_uow_when_double_commit_then_raises_runtime_error]
# [断言: 状态机违规，抛 RuntimeError]
# [Mock: 真 PG]
# ============================================================

# ============================================================
# [测试场景 4: test_uow_when_pool_exhausted_then_raises_db_unavailable]
# [断言: TimeoutError 包装为 DBUnavailable(503)]
# [Mock: 设置 pool_size=1，并发占用]
# ============================================================

# ============================================================
# [测试场景 5: test_uow_repositories_are_lazy_constructed_then_same_session]
# [断言: uow.mcp_servers._session is uow.inbox_queue._session]
# [Mock: 真 PG]
# ============================================================

# ============================================================
# [测试场景 6: test_uow_when_appendonly_violation_then_rolls_back_and_propagates]
# [断言: AppendOnlyViolation 上抛；事务回滚]
# [Mock: 真 PG + InboxDecisionRepository.update]
# ============================================================

# ============================================================
# [测试场景 7: test_uow_cross_task_share_then_raises]
# [断言: 跨 asyncio task 共享 UoW 抛错（warning 或 RuntimeError）]
# [Mock: 真 PG + asyncio.gather]
# ============================================================
