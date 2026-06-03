"""M-B04 Approval Engine — Pydantic DTO 集合.

[文件路径] src/agenthub/application/approval/schemas.py
[文件职责] 集中定义 controllers/services 之间的请求/响应 DTO
[所属模块] M-B04
[关联设计规范] FS-008 / IC-005 / IC-006
[功能描述]
  功能1: CheckRequest / CheckResponse  (IC-005)
  功能2: DecideRequest / DecideResponse (IC-006)
  功能3: Decision (Enum) / QueueStatus
  功能4: ApprovalEvent (publish to EventBus)
[输入输出]
  输入: HTTP body → Pydantic 反序列化
  输出: Service 调用值对象 / HTTP 响应
[依赖关系]
  依赖文件: 无（仅 Pydantic + std-lib enum/uuid/datetime）
  被依赖文件: controllers / services / scanner / tests
[注意事项]
  注意1: 所有 DTO 必须使用 pydantic.BaseModel + ConfigDict(frozen=True) 形成不可变值对象
  注意2: enum 使用 str 派生（Pydantic v2 自动序列化）
  注意3: 必须实现 IC-005/006 全部字段；不可遗漏 trace_id / timestamp
[代码风格] 遵循 CS §1.3 类型注解
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B04 - 初始框架（仅注释）
[作者] DD-M-B04-20260603
[来源标注] [DD-001:IC-005 + IC-006 + DD-M-B04 推断: 独立 schemas 文件便于复用]
"""

from __future__ import annotations

# 实际 import 由 DD-S 阶段补全（pydantic / enum / uuid / datetime）

# ---------------------------------------------------------------------------
# 枚举 — Decision
# ---------------------------------------------------------------------------
# [类名] Decision (str, Enum)
# [职责] 审批决策枚举
# [属性]
#   ALLOWED = "allowed"   IC-005 check_and_queue 返回；命中 allowlist
#   PENDING = "pending"   IC-005；入队等待
#   DENIED  = "denied"    IC-005；显式拒绝（如黑名单）
#   ALLOW   = "allow"     IC-006 decide 入参；审批人选择允许
#   DENY    = "deny"      IC-006 decide 入参；审批人选择拒绝
#   TIMEOUT = "timeout"   timeout_scan 内部标记
# [来源标注] [DD-001:IC-005 + IC-006]

# ---------------------------------------------------------------------------
# DTO — CheckRequest
# ---------------------------------------------------------------------------
# [类名] CheckRequest (BaseModel, frozen=True)
# [职责] IC-005 入参
# [属性]
#   workspace_id: UUID                 必填
#   mcp_id:       UUID                 必填
#   tool:         str (max_length=64)  必填
#   args:         dict[str, object]    必填  (序列化后 ≤ 16KB 由 Validator 校验)
# [校验]
#   - tool ≤ 64 (Pydantic Field(max_length=64))
#   - args JSON 序列化字节数 ≤ 16384 (自定义 model_validator)
# [来源标注] [DD-001:IC-005 入参]

# ---------------------------------------------------------------------------
# DTO — CheckResponse
# ---------------------------------------------------------------------------
# [类名] CheckResponse (BaseModel)
# [属性]
#   decision:  Decision               必填  ∈ {ALLOWED, PENDING, DENIED}
#   queue_id:  UUID | None            decision=PENDING 时必填
#   trace_id:  str                    必填
#   timestamp: datetime               必填
#   fail_safe: bool = False           [DD-M-B04 推断: fail-safe pending 时为 True，便于监控]
# [来源标注] [DD-001:IC-005 出参 + DD-M-B04 推断]

# ---------------------------------------------------------------------------
# DTO — DecideRequest
# ---------------------------------------------------------------------------
# [类名] DecideRequest (BaseModel, frozen=True)
# [职责] IC-006 入参
# [属性]
#   decision:    Decision (literal=ALLOW|DENY)  必填
#   custom_args: dict | None                    可选
#   decider:     UUID                           必填
#   decision_ts: int                            必填  毫秒；5min 窗口校验
#   nonce:       str                            必填  防重放
# [校验]
#   - decision ∈ {ALLOW, DENY}
#   - abs(now_ms - decision_ts) ≤ 300_000 (5min)
#   - nonce 长度 16-64
# [来源标注] [DD-001:IC-006 入参 + SEC-005]

# ---------------------------------------------------------------------------
# DTO — DecideResponse
# ---------------------------------------------------------------------------
# [类名] DecideResponse (BaseModel)
# [属性]
#   decision_id:          UUID         必填
#   applied_at:           datetime     必填
#   trace_id:             str          必填
#   duplicate:            bool = False  [DD-M-B04 推断: 幂等命中时为 True]
#   original_decision_id: UUID | None   duplicate=True 时返回上次的 decision_id
# [来源标注] [DD-001:IC-006 出参 + DD-M-B04 推断洞察 2]

# ---------------------------------------------------------------------------
# DTO — QueueStatus
# ---------------------------------------------------------------------------
# [类名] QueueStatus (BaseModel)
# [属性]
#   queue_id:   UUID
#   status:     Decision        ∈ {PENDING, ALLOWED, DENIED, TIMEOUT}
#   decided_at: datetime | None
#   decider:    UUID | None
# [来源标注] [DD-M-B04 推断: 配套 controllers.query]

# ---------------------------------------------------------------------------
# DTO — ApprovalEvent
# ---------------------------------------------------------------------------
# [类名] ApprovalEvent (BaseModel)
# [职责] 发布到 M-EV01 的事件 payload（topic = approval.requested | approval.decided | approval.timeout）
# [属性]
#   event_type:   str   "approval.requested" | "approval.decided" | "approval.timeout"
#   queue_id:     UUID
#   workspace_id: UUID
#   mcp_id:       UUID
#   tool:         str
#   args_hash:    str
#   decision:     Decision | None    decided 事件必填
#   decider:      UUID | None        decided 事件必填
#   trace_id:     str
#   emitted_at:   datetime
#   fail_safe:    bool = False
# [来源标注] [DD-001:IC-005 时序图 publish + IC-006 时序图 publish + IC-020 schema]
