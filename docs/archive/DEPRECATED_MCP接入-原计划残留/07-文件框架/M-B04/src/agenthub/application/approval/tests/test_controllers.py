"""M-B04 — controllers.py 测试.

[文件路径] src/agenthub/application/approval/tests/test_controllers.py
[文件职责] 测试 ApprovalController 三个端点的请求/响应/异常映射
[所属模块] M-B04
[关联设计规范] CS §1.7 测试规范
[依赖] pytest / pytest-asyncio / httpx.AsyncClient / fixtures from conftest
[作者] DD-M-B04-20260603
[来源标注] [DD-001:IC-005 + IC-006]

# -----------------------------------------------------------------------------
# 测试场景注释
# -----------------------------------------------------------------------------
[测试场景 1] test_check_when_allowlist_hit_then_returns_allowed
  断言: 响应 decision=ALLOWED, queue_id=None, status=200
  Mock: AllowlistCache.is_allowed → True
  关联: IC-005 cache hit 分支

[测试场景 2] test_check_when_cache_miss_then_returns_pending
  断言: decision=PENDING, queue_id 非空, status=200, EventBus 收到 approval.requested
  Mock: AllowlistCache.is_allowed → False; mock_queue_repo enqueue 返回 uuid
  关联: IC-005 DB 直查 + 入队

[测试场景 3] test_check_when_db_unavailable_then_returns_pending_fail_safe
  断言: decision=PENDING, fail_safe=True, status=200, WARN 日志
  Mock: queue_repo.enqueue_pending → raises ApprovalDBUnavailable
  关联: IC-005 错误码 APPROVAL_DB_UNAVAILABLE 的 fail-safe 行为

[测试场景 4] test_check_when_args_too_large_then_422
  断言: HTTP 422 (Pydantic 校验错误)
  Mock: 无（请求体本身违规：args 序列化 > 16KB）
  关联: IC-005 入参约束

[测试场景 5] test_check_when_tool_too_long_then_422
  断言: HTTP 422
  Mock: 无（tool=65 字符）
  关联: IC-005 入参约束

[测试场景 6] test_decide_when_first_time_then_returns_decision_id
  断言: status=200, decision_id 非空, duplicate=False
  Mock: queue_repo.fetch_pending → 返回行; append_decision → 新 uuid
  关联: IC-006 正常路径

[测试场景 7] test_decide_when_duplicate_then_returns_409_with_original
  断言: status=409, error_code=APPROVAL_DUPLICATE, original_decision_id 非空, duplicate=True
  Mock: append_decision → raises ApprovalDuplicate(original_decision_id=...)
  关联: IC-006 幂等命中

[测试场景 8] test_decide_when_not_found_then_404
  断言: status=404, error_code=APPROVAL_NOT_FOUND
  Mock: fetch_pending → raises ApprovalNotFound
  关联: IC-006

[测试场景 9] test_decide_when_decider_not_admin_then_403
  断言: status=403, error_code=APPROVAL_PERMISSION_DENIED
  Mock: 权限校验失败
  关联: IC-006 + SEC-005

[测试场景 10] test_decide_when_replay_then_409
  断言: status=409, error_code=APPROVAL_REPLAY
  Mock: freeze_time 让 decision_ts 超 5min 窗口
  关联: IC-006 + SEC-005

[测试场景 11] test_query_when_pending_then_returns_status
  断言: status=PENDING, decided_at=None
  Mock: fetch by id → pending row
  关联: 客户端轮询路径

[测试场景 12] test_query_when_not_found_then_404
  断言: status=404
  关联: IC-005 错误码

[测试场景 13] test_trace_id_propagation
  断言: 响应体 trace_id == request header X-Trace-ID
  Mock: TraceMiddleware 注入
  关联: IC-001 trace 链路
"""
