"""M-B04 Approval Engine — 模块领域异常.

[文件路径] src/agenthub/application/approval/exceptions.py
[文件职责] 集中定义本模块抛出的领域异常，继承全局 AgentHubError 基类
[所属模块] M-B04
[关联设计规范] FS-008 / CS §1.6 (异常处理规范)
[关联接口契约] IC-005 / IC-006 全部错误码
[功能描述]
  功能1: 定义模块基类 ApprovalError
  功能2: 定义子类 1:1 对应 IC 错误码（DBUnavailable / HashMismatch / NotFound / PermissionDenied / Duplicate / Replay）
  功能3: 每个异常携带 code (HTTP status) 与 error_code (业务码) 属性
[输入输出]
  输入: 业务流程触发抛出
  输出: 异常实例 + log.error
[依赖关系]
  依赖文件: 无（仅 agenthub.core.exceptions.AgentHubError 基类）
  被依赖文件: services / controllers / queue_repo / allowlist / scanner / tests
[注意事项]
  注意1: 必须继承 AgentHubError 基类（CS §1.6 自定义异常基类规范）
  注意2: 异常链使用 `raise X from e` 保留原因（CS §1.6）
  注意3: 禁止吞异常（ruff E722 强制）
  注意4: HTTP code 与 IC 错误码表一致；变更必须同步更新 controllers 映射
[代码风格] 遵循 CS §1.6
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B04 - 初始框架（仅注释）
[作者] DD-M-B04-20260603
[来源标注] [DD-001:CS §1.6 + IC-005 错误码 + IC-006 错误码]
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 类注释 — 异常体系
# ---------------------------------------------------------------------------
# [类名] ApprovalError (AgentHubError)
# [职责] M-B04 异常基类
# [属性]
#   http_status: int   HTTP 状态码（由子类指定）
#   error_code:  str   业务错误码（IC 表定义）
#   trace_id:    str | None
# [来源标注] [DD-001:CS §1.6]

# [类名] ApprovalDBUnavailable (ApprovalError)
# [HTTP] 503  [error_code] APPROVAL_DB_UNAVAILABLE
# [触发] PG 不可用；fail-safe 走 pending；WARN 日志
# [来源标注] [DD-001:IC-005 错误码]

# [类名] ApprovalHashMismatch (ApprovalError)
# [HTTP] 500  [error_code] APPROVAL_HASH_MISMATCH
# [触发] services.decide 中 verify_hash 失败；ERROR 告警；走 pending
# [来源标注] [DD-001:IC-005 错误码 + ADR-006]

# [类名] ApprovalTimeout (ApprovalError)
# [HTTP] 408  [error_code] APPROVAL_TIMEOUT
# [触发] 入队后 60s 无决策，timeout_scan 标记；客户端可轮询 query 端点
# [来源标注] [DD-001:IC-005 错误码]

# [类名] ApprovalNotFound (ApprovalError)
# [HTTP] 404  [error_code] APPROVAL_NOT_FOUND
# [触发] queue_id 在 inbox_queue 中不存在
# [来源标注] [DD-001:IC-006 错误码]

# [类名] ApprovalPermissionDenied (ApprovalError)
# [HTTP] 403  [error_code] APPROVAL_PERMISSION_DENIED
# [触发] decider 不在 workspace.admins 集合
# [来源标注] [DD-001:IC-006 错误码 + SEC-005]

# [类名] ApprovalDuplicate (ApprovalError)
# [HTTP] 409  [error_code] APPROVAL_DUPLICATE
# [触发] UNIQUE(queue_id, decision_hash) 冲突；属于幂等命中
# [属性额外] original_decision_id: UUID  (用于 controllers 返回 body)
# [来源标注] [DD-001:IC-006 错误码 + AR洞察-3]

# [类名] ApprovalReplay (ApprovalError)
# [HTTP] 409  [error_code] APPROVAL_REPLAY
# [触发] decision_ts 超 5min 窗口 或 nonce 已被使用
# [来源标注] [DD-001:IC-006 错误码 + SEC-005]
