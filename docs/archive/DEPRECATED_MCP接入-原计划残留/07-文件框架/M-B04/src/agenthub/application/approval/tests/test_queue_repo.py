"""M-B04 — queue_repo.py 测试.

[文件] tests/test_queue_repo.py  [所属模块] M-B04  [作者] DD-M-B04-20260603
[来源] [DD-001:MD:M-B04 + IC-017 + AR洞察-3]

[测试场景 1] test_enqueue_pending_creates_row
  断言: inbox_queue 新增 1 行；status='pending'
[测试场景 2] test_enqueue_pending_duplicate_returns_existing_id
  断言: 同 (ws,mcp,tool,args_hash) 第二次 enqueue → 返回首次 queue_id（幂等）
[测试场景 3] test_enqueue_pending_db_error_raises
  断言: ApprovalDBUnavailable
[测试场景 4] test_fetch_pending_returns_row_with_lock
  断言: 返回行；FOR UPDATE 标记已加（用 SQL 拦截验证）
[测试场景 5] test_fetch_pending_not_found_raises
  断言: ApprovalNotFound
[测试场景 6] test_append_decision_inserts_row
  断言: inbox_decision 新增；返回 decision_id
[测试场景 7] test_append_decision_unique_conflict_raises_duplicate
  断言: 第二次相同 (queue_id, decision_hash) → ApprovalDuplicate(original_decision_id)
[测试场景 8] test_append_decision_db_error_raises
  断言: ApprovalDBUnavailable
[测试场景 9] test_list_pending_expired_filters_by_time
  断言: 仅返回 created_at < now-60s 的 pending 行
[测试场景 10] test_list_pending_expired_respects_limit
  断言: 1500 行候选 → 返回 limit=1000
[测试场景 11] test_mark_timeout_updates_status
  断言: 受影响行数 == 输入长度；status='timeout'
[测试场景 12] test_mark_timeout_idempotent_skips_already_timeout
  断言: 输入含已 timeout 行 → WHERE status='pending' 过滤掉，受影响行数减少
"""
