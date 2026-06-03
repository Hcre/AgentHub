"""M-B04 — allowlist.py Cache Proxy 测试.

[文件] tests/test_allowlist.py  [所属模块] M-B04  [作者] DD-M-B04-20260603
[来源] [DD-001:MD:M-B04 类设计 #4 + IC-005]

[测试场景 1] test_is_allowed_cache_hit_no_pg_call
  断言: 返回 True；mock_repo.exists 未被调用
  Mock: fake_redis 预置 key
[测试场景 2] test_is_allowed_cache_miss_pg_hit_then_backfill
  断言: 返回 True；fake_redis 出现 key (TTL≈30d)
[测试场景 3] test_is_allowed_double_miss_returns_false
  断言: 返回 False；fake_redis 不写入
[测试场景 4] test_is_allowed_redis_down_falls_back_to_pg
  断言: Redis raises ConnectionError → 仍能查 PG 返回结果；WARN 日志
[测试场景 5] test_is_allowed_pg_error_raises_db_unavailable
  断言: ApprovalDBUnavailable
[测试场景 6] test_set_allowed_writes_pg_and_redis
  断言: PG UPSERT + Redis SETEX (TTL=2592000)
[测试场景 7] test_set_allowed_redis_failure_does_not_fail_pg
  断言: Redis raises → 不抛出；PG 写入成功；WARN 日志
[测试场景 8] test_invalidate_removes_both
  断言: Redis DEL + PG DELETE
[测试场景 9] test_invalidate_idempotent
  断言: 重复 invalidate 不抛
[测试场景 10] test_build_key_deterministic
  断言: 相同入参产生相同 64-hex
[测试场景 11] test_build_key_distinguishes_inputs
  断言: 不同 ws/mcp/tool/hash 任一变化 → key 变化
[测试场景 12] test_ttl_exactly_30_days
  断言: TTL == 30*24*3600 = 2_592_000
"""
