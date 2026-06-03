"""M-B04 Approval Engine — FastAPI 控制器层.

[文件路径] src/agenthub/application/approval/controllers.py
[文件职责] HTTP 入口层；解析请求、调用 ApprovalService、返回标准响应
[所属模块] M-B04
[关联设计规范] FS-008 / MD:M-B04
[关联接口契约] IC-005 (check_and_queue) / IC-006 (decide)
[关联 API] API-130 / API-131
[功能描述]
  功能1: POST /approvals/check        → ApprovalService.check_and_queue
  功能2: POST /approvals/{queue_id}/decide → ApprovalService.decide
  功能3: GET  /approvals/{queue_id}    → 查询当前 pending 状态（轮询用）
[输入输出]
  输入: Pydantic 请求体 (CheckRequest / DecideRequest) + JWT 用户上下文（M-A01 注入）
  输出: 标准响应 {code, message, trace_id, data, timestamp}（统一格式来自 IC-001）
[依赖关系]
  依赖文件: services.ApprovalService / schemas.* / exceptions.*
  被依赖文件: agenthub.access.api_gateway 路由注册器
[注意事项]
  注意1: 控制器层禁止包含业务逻辑（CS §架构纪律）；仅做参数转换+异常映射
  注意2: 所有异常必须映射为标准错误码（参考 IC-005/006 错误码表）
  注意3: trace_id 由 TraceMiddleware 注入；本层从 request.state.trace_id 取
[代码风格] 遵循 CS §1.1-1.6 / FastAPI 推荐布局
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B04 - 初始框架（仅注释）
[作者] DD-M-B04-20260603
[来源标注] [DD-001:IC-005 + IC-006 + FS-008 + CS §1.6]
"""

from __future__ import annotations

# 实际 import 由 DD-S 骨架阶段补全（FastAPI / Depends / 本模块 services 等）

# ---------------------------------------------------------------------------
# 类注释 — ApprovalController
# ---------------------------------------------------------------------------
# [类名] ApprovalController
# [职责] HTTP 入口适配，桥接 FastAPI Router 与 ApprovalService
# [关联设计规范] MD:M-B04 (类设计 #1)
# [属性]
#   service: ApprovalService  注入的业务服务实例（依赖注入）
#   router:  APIRouter         FastAPI 路由对象（前缀 /approvals）
# [方法列表]
#   check(body: CheckRequest, ctx: UserCtx)  → CheckResponse
#       - 实现 IC-005；返回 decision ∈ {allowed, pending, denied}
#   decide(queue_id: UUID, body: DecideRequest, ctx: UserCtx) → DecideResponse
#       - 实现 IC-006；幂等：(queue_id, decision_hash) 唯一
#   query(queue_id: UUID, ctx: UserCtx) → QueueStatus
#       - 轮询用，供客户端在 APPROVAL_TIMEOUT (408) 后查询
# [状态机] 无（无状态控制器）
# [异常处理]
#   ApprovalDBUnavailable    → 503 APPROVAL_DB_UNAVAILABLE
#   ApprovalHashMismatch     → 500 APPROVAL_HASH_MISMATCH
#   ApprovalNotFound         → 404 APPROVAL_NOT_FOUND
#   ApprovalPermissionDenied → 403 APPROVAL_PERMISSION_DENIED
#   ApprovalDuplicate        → 409 APPROVAL_DUPLICATE（返回上次决策，幂等）
#   ApprovalReplay           → 409 APPROVAL_REPLAY
# [来源标注] [DD-001:MD:M-B04 类设计 #1 + IC-005/IC-006 错误码]


# ---------------------------------------------------------------------------
# 函数注释 — check
# ---------------------------------------------------------------------------
# [函数名] check
# [职责] 处理 POST /approvals/check；危险工具调用的前置审批检查
# [关联接口契约] IC-005
# [参数说明]
#   body: CheckRequest  必填  请求体 {workspace_id, mcp_id, tool, args}
#                       校验: tool 长度 ≤ 64；args 序列化后 ≤ 16KB（IC-005 入参约束）
#   ctx:  UserCtx       必填  当前用户上下文（由 JWT 解析注入）
# [返回值]
#   类型: CheckResponse
#   描述: {decision, queue_id, trace_id, timestamp}
#   特殊值: decision=allowed 时 queue_id=None；pending 时 queue_id 必返
# [错误码]
#   APPROVAL_DB_UNAVAILABLE 503  PG 不可用     保守走 pending（fail-safe）
#   APPROVAL_HASH_MISMATCH  500  hash 不一致   告警 + 走 pending
# [前置条件] JWT 已通过 M-A01 网关验证；trace_id 已注入
# [后置条件] cache 命中直返；否则 inbox_queue 新增 pending 行，approval.requested 已发布
# [并发安全] 委托 service 层处理（PG SELECT FOR UPDATE on inbox_queue）
# [幂等性] 是；幂等键 (workspace_id, mcp_id, tool, args_hash)；有效期 30 天
# [性能约束] P95 ≤ 200ms（allowlist 命中）；P95 ≤ 500ms（DB 直查）
# [示例]
#   POST /approvals/check
#   {
#     "workspace_id": "uuid", "mcp_id": "uuid",
#     "tool": "fs.write", "args": {"path": "/tmp/x"}
#   }
#   → 200 {"decision": "pending", "queue_id": "uuid", "trace_id": "...", "timestamp": "..."}
# [来源标注] [DD-001:IC-005 + AR洞察-3]


# ---------------------------------------------------------------------------
# 函数注释 — decide
# ---------------------------------------------------------------------------
# [函数名] decide
# [职责] 处理 POST /approvals/{queue_id}/decide；审批人对 pending 项做决策
# [关联接口契约] IC-006
# [参数说明]
#   queue_id: UUID         必填  路径参数；inbox_queue.id
#   body:     DecideRequest 必填  {decision, custom_args, decider, decision_ts, nonce}
#                          校验:
#                            - decision ∈ {allow, deny}
#                            - decision_ts 在 5min 窗口内（防重放）
#                            - nonce 不可重复（Redis SETNX 校验）
#   ctx:      UserCtx       必填  当前审批人上下文（必须 ∈ workspace.admins）
# [返回值]
#   类型: DecideResponse
#   描述: {decision_id, applied_at, trace_id}
#   特殊值: 幂等场景返回上次的 decision_id（不重新生成）
# [错误码]
#   APPROVAL_NOT_FOUND          404  queue_id 不存在
#   APPROVAL_PERMISSION_DENIED  403  decider 非该 ws 审批人
#   APPROVAL_DUPLICATE          409  已决策（幂等返回上次结果）
#   APPROVAL_REPLAY             409  decision_ts 超出 5min 窗口
# [前置条件] decider ∈ workspace.admins；queue_id 状态 = pending
# [后置条件] inbox_decision 不可变 append；allowlist_30d UPSERT；approval.decided 已发布
# [并发安全] service 层 PG row-lock + UNIQUE(queue_id, decision_hash)（[AR洞察-3]）
# [幂等性] 是；append-only 永久幂等
# [性能约束] P95 ≤ 300ms
# [来源标注] [DD-001:IC-006 + SEC-005 + AR洞察-3]


# ---------------------------------------------------------------------------
# 函数注释 — query
# ---------------------------------------------------------------------------
# [函数名] query
# [职责] GET /approvals/{queue_id}；客户端在 408 APPROVAL_TIMEOUT 后轮询使用
# [关联接口契约] IC-005 (扩展查询)
# [参数说明]
#   queue_id: UUID    必填
#   ctx:      UserCtx 必填  (调用方 = 原发起者或 ws 成员)
# [返回值]
#   类型: QueueStatus
#   描述: {queue_id, status ∈ {pending|allowed|denied|timeout}, decided_at?, decider?}
# [错误码]
#   APPROVAL_NOT_FOUND 404
# [并发安全] 只读
# [幂等性] 是（只读）
# [性能约束] P95 ≤ 50ms (PG 主键查询)
# [来源标注] [DD-M-B04 推断: MD 未明确暴露 query 端点但 IC-005 408 错误码要求客户端轮询，故补 GET 入口]
