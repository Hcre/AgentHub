"""M-B04 Approval Engine — InboxQueue Repository Adapter.

[文件路径] src/agenthub/application/approval/queue_repo.py
[文件职责] 桥接 M-D01 通用 Repository 与 M-B04 业务语义（Service Layer ↔ Data Layer）
[所属模块] M-B04
[关联设计规范] FS-008 / MD:M-B04 子模块"queue" + DS:inbox_queue / inbox_decision / allowlist_30d 表
[关联接口契约] IC-017 (Metadata DAO) / IC-005 / IC-006
[功能描述]
  功能1: enqueue_pending(ws, mcp, tool, args_hash, args, trace_id) → queue_id
  功能2: fetch_pending(queue_id) → InboxQueueRow（FOR UPDATE 行锁）
  功能3: append_decision(queue_id, decision, decider, decision_hash, ...) → decision_id
  功能4: list_pending_expired(now_ts, limit) → list[queue_id]（供 timeout_scan）
  功能5: mark_timeout(queue_ids) → int
[输入输出]
  输入: 业务参数（UUID/str/dict）
  输出: PG 行对象 / 受影响行数
[依赖关系]
  依赖文件: schemas (DTO) / exceptions
  跨模块依赖（只读，通过抽象 Repository 协议）:
    - agenthub.data.metadata.repositories.inbox_queue.InboxQueueRepository (M-D01)
    - agenthub.data.metadata.repositories.inbox_decision.InboxDecisionRepository (M-D01)
    - agenthub.data.metadata.unit_of_work.UnitOfWork (M-D01)
  被依赖文件: services.py / scanner.py / allowlist.py (PG fallback)
[注意事项]
  注意1: 本文件不直接 import SQLAlchemy；仅通过 M-D01 Repository 抽象
  注意2: 必须显式使用 UnitOfWork 上下文管理事务，禁止裸 commit
  注意3: append_decision 必须利用 UNIQUE(queue_id, decision_hash) 触发 DuplicateDecision
  注意4: fetch_pending 必须 SELECT ... FOR UPDATE（防止并发决策竞争）
[代码风格] 遵循 CS §1.3 类型注解 + §1.6 异常链
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B04 - 初始框架（仅注释）
[作者] DD-M-B04-20260603
[来源标注] [DD-001:MD:M-B04 子模块"queue" + IC-017 + AR洞察-3]
"""

from __future__ import annotations

# 实际 import 由 DD-S 阶段补全

# ---------------------------------------------------------------------------
# 类注释 — InboxQueueRepository (Adapter)
# ---------------------------------------------------------------------------
# [类名] InboxQueueRepository
# [职责] 业务语义封装 M-D01 的通用 inbox_queue/inbox_decision Repository
# [关联设计规范] MD:M-B04 子模块"queue" + DS:inbox_queue
# [属性]
#   uow:           UnitOfWork                 M-D01 工作单元
#   queue_repo:    BaseRepository[InboxQueue] M-D01 inbox_queue 通用 Repo
#   decision_repo: BaseRepository[InboxDecision]
# [方法列表]
#   async enqueue_pending(...) → UUID
#   async fetch_pending(queue_id) → InboxQueueRow  (FOR UPDATE)
#   async append_decision(...) → UUID  (UNIQUE(queue_id, decision_hash))
#   async list_pending_expired(now_ts, limit=1000) → list[UUID]
#   async mark_timeout(queue_ids) → int
# [状态机] 表层状态: pending → allowed | denied | timeout
# [异常处理]
#   DBIntegrityError → ApprovalDuplicate（UNIQUE 冲突，幂等返回）
#   DBDeadlockError  → 自动重试 3 次（依赖 M-D01 BaseRepository 行为）
#   DBConnectError   → ApprovalDBUnavailable
# [来源标注] [DD-001:MD:M-B04 + DS:inbox_queue/inbox_decision/allowlist_30d]


# ---------------------------------------------------------------------------
# 函数注释 — enqueue_pending
# ---------------------------------------------------------------------------
# [函数名] enqueue_pending
# [职责] 新增 pending 行到 inbox_queue
# [关联接口契约] IC-005 (DB 直查路径)
# [参数说明]
#   ws:        UUID  必填
#   mcp:       UUID  必填
#   tool:      str   必填
#   args_hash: str   必填  (ArgsHasher 输出)
#   args:      dict  必填  (原始参数，存 JSONB)
#   trace_id:  str   必填
# [返回值]
#   类型: UUID
#   描述: 新建的 queue_id
#   特殊值: 若 (ws, mcp, tool, args_hash) 已存在 pending → 返回已有 queue_id (幂等)
# [错误码]
#   ApprovalDBUnavailable - DB 不可达
# [前置条件] 已在 UoW 事务中
# [后置条件] inbox_queue 新增一行，status='pending'，created_at=now
# [并发安全] PG UNIQUE(ws, mcp, tool, args_hash, status) 约束防重
# [幂等性] 是
# [性能约束] P95 ≤ 50ms (含 RTT)
# [来源标注] [DD-001:IC-005 时序图 + DS:inbox_queue]


# ---------------------------------------------------------------------------
# 函数注释 — fetch_pending
# ---------------------------------------------------------------------------
# [函数名] fetch_pending
# [职责] 读取 pending 行并加行锁
# [关联接口契约] IC-006 (decide 流程)
# [参数说明]
#   queue_id: UUID 必填
# [返回值]
#   类型: InboxQueueRow
#   描述: 行对象（含 args_hash 用于 verify）
# [错误码]
#   ApprovalNotFound - queue_id 不存在
# [前置条件] 已在 UoW 事务中
# [后置条件] PG row-lock 持有至事务结束
# [并发安全] SELECT ... FOR UPDATE NOWAIT (拒绝并发决策)
# [性能约束] P95 ≤ 30ms
# [来源标注] [DD-001:IC-006 时序图 + AR洞察-3]


# ---------------------------------------------------------------------------
# 函数注释 — append_decision
# ---------------------------------------------------------------------------
# [函数名] append_decision
# [职责] append-only 写 inbox_decision；触发 UNIQUE 即为幂等命中
# [关联接口契约] IC-006
# [参数说明]
#   queue_id:      UUID  必填
#   decision:      str   必填  enum {allow, deny}
#   decider:       UUID  必填
#   decision_hash: str   必填  (decision + decider + custom_args 的复合哈希)
#   custom_args:   dict | None  可选
#   applied_at:    datetime    必填
# [返回值]
#   类型: UUID
#   描述: 新生成 decision_id；UNIQUE 冲突时返回已有 decision_id (幂等)
# [错误码]
#   ApprovalDuplicate     - UNIQUE(queue_id, decision_hash) 冲突 (调用方应捕获)
#   ApprovalDBUnavailable - DB 不可达
# [前置条件] queue_id 行锁已持有；decider ∈ ws.admins (调用方已校验)
# [后置条件] inbox_decision 新增一行（append-only，不可 UPDATE/DELETE）
# [并发安全] UNIQUE(queue_id, decision_hash) + 行锁
# [幂等性] 是；append-only 永久幂等
# [性能约束] P95 ≤ 50ms
# [来源标注] [DD-001:IC-006 时序图 + AR洞察-3]


# ---------------------------------------------------------------------------
# 函数注释 — list_pending_expired / mark_timeout
# ---------------------------------------------------------------------------
# [函数名] list_pending_expired
# [职责] 查询 pending 且 created_at < now - 60s 的 queue_id 列表
# [参数说明]
#   now_ts: int  必填  毫秒时间戳
#   limit:  int  可选 = 1000
# [返回值] list[UUID]
# [幂等性] 是（只读）
# [性能约束] P95 ≤ 100ms（索引 idx_inbox_queue_status_created_at）
# [来源标注] [DD-M-B04 推断: MD timeout_scan 子模块 + APPROVAL_TIMEOUT 错误码]

# [函数名] mark_timeout
# [职责] 批量更新 status pending → timeout
# [参数说明]
#   queue_ids: list[UUID] 必填
# [返回值] int  受影响行数
# [错误码] ApprovalDBUnavailable
# [并发安全] WHERE status='pending' 保证仅原 pending 才被改写
# [幂等性] 是
# [性能约束] 1000 行 ≤ 200ms
# [来源标注] [DD-M-B04 推断: 配套 list_pending_expired]
