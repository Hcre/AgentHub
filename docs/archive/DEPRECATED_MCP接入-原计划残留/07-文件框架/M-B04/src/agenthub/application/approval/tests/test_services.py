"""M-B04 — services.py 测试（核心 35 用例的主体）.

[文件路径] src/agenthub/application/approval/tests/test_services.py
[文件职责] ApprovalService 三个方法的完整覆盖（含异常 / 并发 / 幂等 / 一致性）
[所属模块] M-B04
[关联设计规范] CS §1.7 + MD:M-B04 测试策略（35 用例核心）
[依赖] pytest-asyncio / fixtures / fakeredis
[作者] DD-M-B04-20260603
[来源标注] [DD-001:MD:M-B04 测试策略 + IC-005 + IC-006]

# -----------------------------------------------------------------------------
# 测试场景注释 — check_and_queue (14 用例)
# -----------------------------------------------------------------------------
[CS-01] test_check_when_redis_cache_hit_then_allowed
  断言: 返回 Decision.ALLOWED；不查 PG；不写入；不 publish
  Mock: fake_redis SETEX 预置 allowlist key

[CS-02] test_check_when_redis_miss_pg_hit_then_allowed_and_backfill
  断言: ALLOWED；fake_redis 中出现 key (TTL=30d)
  Mock: AllowlistRepository.exists → True

[CS-03] test_check_when_double_miss_then_pending_enqueue
  断言: PENDING；queue_id 非空；EventBus 收到 approval.requested

[CS-04] test_check_when_redis_down_then_fallback_pg
  断言: 仍能返回 ALLOWED/PENDING；WARN 日志含 "redis_unavailable"
  Mock: fake_redis raises ConnectionError

[CS-05] test_check_when_pg_down_then_fail_safe_pending
  断言: PENDING + fail_safe=True；不抛异常
  Mock: queue_repo.enqueue_pending → raises ApprovalDBUnavailable

[CS-06] test_check_args_key_order_independent
  断言: hash({"a":1,"b":2}) == hash({"b":2,"a":1})；命中同 allowlist key
  关联: ADR-006

[CS-07] test_check_concurrent_same_args_dedup
  断言: 100 并发 same args 仅产生 1 个 queue_id
  Mock: asyncio.gather + UNIQUE 约束

[CS-08] test_check_concurrent_different_args_no_collision
  断言: 100 并发 different args 产生 100 个 queue_id

[CS-09] test_check_publish_failure_does_not_block_decision
  断言: EventBus.publish raises → 决策仍返回 PENDING (warn 日志)；inbox_queue 已写

[CS-10] test_check_hash_mismatch_does_not_occur_in_check_path
  断言: check 路径无 hash verify 步骤（只在 decide 调用）

[CS-11] test_check_tool_max_length
  断言: tool=64 字符通过；65 字符触发 ValidationError

[CS-12] test_check_args_max_size
  断言: 16KB args 通过；16KB+1 byte 触发 ValidationError

[CS-13] test_check_returns_trace_id
  断言: 响应 trace_id == 入参 trace_id

[CS-14] test_check_invalid_args_type
  断言: args 含 set/datetime 等不可序列化对象 → ValueError

# -----------------------------------------------------------------------------
# 测试场景注释 — decide (14 用例)
# -----------------------------------------------------------------------------
[DS-01] test_decide_allow_then_inserts_decision_and_allowlist
  断言: inbox_decision 新增；allowlist_30d UPSERT；Redis SETEX；publish approval.decided

[DS-02] test_decide_deny_then_inserts_decision_no_allowlist
  断言: inbox_decision 新增；allowlist_30d 不变；Redis 不写；publish approval.decided

[DS-03] test_decide_duplicate_then_returns_original_id
  断言: ApprovalDuplicate(original_decision_id) 抛出；不重复写入
  Mock: UNIQUE 冲突第二次调用

[DS-04] test_decide_when_not_found_then_raises
  断言: ApprovalNotFound

[DS-05] test_decide_when_decider_not_admin_then_permission_denied
  断言: ApprovalPermissionDenied

[DS-06] test_decide_when_decision_ts_too_old_then_replay
  断言: ApprovalReplay；decision_ts = now - 6min

[DS-07] test_decide_when_nonce_already_used_then_replay
  断言: ApprovalReplay
  Mock: fake_redis SETNX 已存在

[DS-08] test_decide_when_hash_mismatch_then_raises
  断言: ApprovalHashMismatch；ERROR 日志
  Mock: 修改 inbox_queue.args_hash 后再 decide

[DS-09] test_decide_concurrent_two_deciders_only_one_wins
  断言: 2 并发 SELECT FOR UPDATE → 仅 1 成功，另 1 收到 Duplicate
  Mock: PG 真实事务 (testcontainers) 或显式锁 Mock

[DS-10] test_decide_with_custom_args_overrides_original
  断言: inbox_decision.custom_args 记录新参数；allowlist key 使用 custom_args 的 hash

[DS-11] test_decide_event_bus_publish_failure_rollback
  断言: publish failed → 整个事务 rollback；inbox_decision 不存在
  Mock: bus.publish raises；UoW 回滚

[DS-12] test_decide_allowlist_ttl_set_to_30d
  断言: fake_redis TTL == 2_592_000

[DS-13] test_decide_returns_applied_at_iso8601
  断言: 响应字段格式正确

[DS-14] test_decide_db_unavailable_then_503
  断言: ApprovalDBUnavailable 抛出
  Mock: append_decision raises DBError

# -----------------------------------------------------------------------------
# 测试场景注释 — timeout_scan (7 用例)
# -----------------------------------------------------------------------------
[TS-01] test_scan_marks_expired_pending_as_timeout
  断言: 60s+ pending 行 status → timeout；新事件 approval.timeout 发布
  Mock: freeze_time + 预置 5 行 pending

[TS-02] test_scan_skips_recent_pending
  断言: < 60s 的 pending 不变

[TS-03] test_scan_idempotent_on_already_timeout
  断言: 已 timeout 的行不被再次 UPDATE；不重复 publish

[TS-04] test_scan_when_not_leader_returns_minus_one
  断言: 返回 -1，不查 PG
  Mock: LeaderElector.is_leader → False

[TS-05] test_scan_db_error_retries_max_3
  断言: DBError 时重试 3 次后告警；任务不崩溃

[TS-06] test_scan_batch_limit_1000
  断言: 1500 行 pending → 单轮处理 1000 行；下轮处理剩余

[TS-07] test_scan_under_5s_budget
  断言: 1000 行场景总耗时 ≤ 5s（性能契约）
"""
