"""M-B04 — scanner.py arq 任务测试.

[文件] tests/test_scanner.py  [所属模块] M-B04  [作者] DD-M-B04-20260603
[来源] [DD-001:MD:M-B04 timeout_scan + DD-M-B04 推断]

[测试场景 1] test_scan_when_leader_processes_expired
  断言: 返回 N > 0；inbox_queue 中过期 pending → timeout
  Mock: LeaderElector.is_leader → True；预置 5 过期行
[测试场景 2] test_scan_when_not_leader_returns_minus_one
  断言: 返回 -1；queue_repo 未被调用
[测试场景 3] test_scan_db_error_retries_then_warns
  断言: 重试 3 次后告警；任务返回 0 而非抛出
[测试场景 4] test_scan_publishes_timeout_event_per_row
  断言: spy_event_bus 收到 N 条 approval.timeout 事件
[测试场景 5] test_scan_under_5s_for_1000_rows
  断言: 性能契约 < 5s
[测试场景 6] test_scan_leader_lost_mid_execution
  断言: 已处理批次仍提交；剩余批次放弃；返回部分计数
[测试场景 7] test_scan_idempotent_consecutive_runs
  断言: 连续两次扫描第二次受影响行数 == 0（已 timeout 不再处理）
"""
