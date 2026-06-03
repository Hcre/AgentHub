"""M-B04 Approval Engine — 业务编排服务层.

[文件路径] src/agenthub/application/approval/services.py
[文件职责] ApprovalService 编排 hash/cache/repo/eventbus，实现 check_and_queue / decide / timeout_scan
[所属模块] M-B04
[关联设计规范] FS-008 / MD:M-B04 (类设计 #2)
[关联接口契约] IC-005 (check_and_queue) / IC-006 (decide)
[功能描述]
  功能1: check_and_queue —— 计算 args_hash → 查询 allowlist → 命中直允 / 未命中入队
  功能2: decide          —— 审批决策；append-only 写 inbox_decision + 更新 allowlist_30d
  功能3: timeout_scan    —— 周期扫描 pending 超时项（由 scanner.py 的 arq 任务调用）
[输入输出]
  输入: CheckRequest / DecideRequest（来自 controllers）
  输出: Decision / 触发 EventBus 事件 (approval.requested / approval.decided)
[依赖关系]
  依赖文件: hasher / allowlist / queue_repo / schemas / exceptions
  跨模块依赖（只读）:
    - agenthub.data.metadata.unit_of_work (UnitOfWork, M-D01)
    - agenthub.eventbus.bus (EventBus, M-EV01)
    - agenthub.core.logging
  被依赖文件: controllers.py / scanner.py
[注意事项]
  注意1: DB 不可用时必须 fail-safe 走 pending（IC-005 错误码语义）
  注意2: hash 不一致时必须 ERROR 日志 + 告警 + 走 pending（防止 false-allow）
  注意3: append-only 写不可变；幂等键 (queue_id, decision_hash) UNIQUE，重复返回上次
  注意4: timeout_scan 必须使用 Leader Election（与 M-A04 协调）避免多实例重复扫
[代码风格] 遵循 CS §1.1-1.8（async 强制 + 异常链 + 类型注解）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B04 - 初始框架（仅注释）
[作者] DD-M-B04-20260603
[来源标注] [DD-001:MD:M-B04 + IC-005 + IC-006 + ADR-006 + AR洞察-3]
"""

from __future__ import annotations

# 实际 import 由 DD-S 骨架阶段补全

# ---------------------------------------------------------------------------
# 类注释 — ApprovalService
# ---------------------------------------------------------------------------
# [类名] ApprovalService
# [职责] 审批引擎核心业务编排（Service Layer 模式）
# [关联设计规范] MD:M-B04 类设计 #2
# [属性]
#   hash_fn:   Callable[[dict], str]  ArgsHasher.compute_args_hash 引用
#   allowlist: AllowlistCache         allowlist 缓存代理
#   repo:      InboxQueueRepository   inbox_queue + inbox_decision Repository
#   bus:       EventBus              事件总线（M-EV01）
#   uow:       UnitOfWorkFactory      M-D01 工作单元工厂
# [方法列表]
#   async check_and_queue(ws, mcp, tool, args, trace_id) → Decision
#       - IC-005 实现；返回 allowed/pending/denied
#   async decide(queue_id, decision, custom_args, decider, decision_ts, nonce, trace_id) → DecisionResult
#       - IC-006 实现；append-only
#   async timeout_scan(now_ts) → int
#       - 标记 pending 超过 60s 的项为 timeout 状态；返回处理数量
# [状态机]
#   inbox_queue: pending → allowed | denied | timeout
#   decision 不可变（append-only），无状态转换
# [异常处理]
#   DBUnavailable → fail-safe 走 pending（503，告警 WARN）
#   HashMismatch  → 走 pending + 告警 ERROR（防 false-allow）
#   DuplicateDecision → 由 UNIQUE 约束触发；查询并返回上次结果（幂等）
#   ReplayDetected → APPROVAL_REPLAY (decision_ts 超 5min 窗口)
# [来源标注] [DD-001:MD:M-B04 类设计 #2 + ADR-006]


# ---------------------------------------------------------------------------
# 函数注释 — check_and_queue
# ---------------------------------------------------------------------------
# [函数名] check_and_queue
# [职责] 危险工具调用前置审批检查的核心实现
# [关联接口契约] IC-005
# [参数说明]
#   ws:       UUID  必填  workspace_id
#   mcp:      UUID  必填  mcp_id
#   tool:     str   必填  工具名（≤64）
#   args:     dict  必填  工具参数（序列化后 ≤16KB）
#   trace_id: str   必填  上游 trace 链路
# [返回值]
#   类型: Decision (enum: allowed | pending | denied)
#   描述: 决策结果对象 + queue_id（pending 时返）
#   特殊值: 任何异常→走 pending（fail-safe）
# [错误码]
#   APPROVAL_DB_UNAVAILABLE 503  PG 不可用     保守 pending + WARN 日志
#   APPROVAL_HASH_MISMATCH  500  hash 不一致   告警 ERROR + 走 pending
# [前置条件] Redis 可达（不可达则跳 cache 直查 PG）；PG 可达（否则 fail-safe pending）
# [后置条件]
#   - 命中 allowlist：直返 allowed（无 DB 写）
#   - 未命中：INSERT inbox_queue (pending) + publish approval.requested
# [并发安全]
#   - cache 层 atomic GET
#   - DB 写: PG SELECT FOR UPDATE on inbox_queue + UNIQUE 约束
#   - 幂等键 (ws, mcp, tool, args_hash) 防止重复入队
# [幂等性] 是；同一组 (ws, mcp, tool, args) 永远返回同一 queue_id（30 天有效期）
# [性能约束] P95 ≤ 200ms (cache hit) / P95 ≤ 500ms (DB 直查)
# [示例]
#   decision = await service.check_and_queue(ws_id, mcp_id, "fs.write", {"path": "/tmp/x"}, trace_id)
#   # decision = Decision(status=allowed | pending(queue_id=uuid) | denied)
# [来源标注] [DD-001:IC-005 + MD:M-B04 函数签名 #1 + AR洞察-3]


# ---------------------------------------------------------------------------
# 函数注释 — decide
# ---------------------------------------------------------------------------
# [函数名] decide
# [职责] 审批人对 pending 项做决策的核心实现
# [关联接口契约] IC-006
# [参数说明]
#   queue_id:     UUID         必填  inbox_queue.id
#   decision:     Decision     必填  enum {allow, deny}
#   custom_args:  dict | None  可选  覆盖原参数（如审批人手动改 path）
#   decider:      UUID         必填  审批人 user_id (U-04)
#   decision_ts:  int          必填  防重放时间戳（毫秒），5min 窗口
#   nonce:        str          必填  防重放 nonce（Redis SETNX）
#   trace_id:     str          必填
# [返回值]
#   类型: DecisionResult
#   描述: {decision_id: UUID, applied_at: ISO8601}
#   特殊值: 幂等场景返回历史 decision_id（不重新生成）
# [错误码]
#   APPROVAL_NOT_FOUND          404  queue_id 不存在
#   APPROVAL_PERMISSION_DENIED  403  decider 非 ws 审批人
#   APPROVAL_DUPLICATE          409  已决策（返回上次结果，状态码 409 而非 200，明示幂等命中）
#   APPROVAL_REPLAY             409  decision_ts 超 5min 窗口 或 nonce 已用
# [前置条件]
#   - decider ∈ workspace.admins（M-D01.workspace_admins 表查询）
#   - queue_id 状态 = pending（FOR UPDATE 行锁）
# [后置条件]
#   - INSERT inbox_decision (append-only, 不可变)
#   - UPSERT allowlist_30d (同 ws+mcp+tool+args_hash)
#   - Redis SETEX allowlist:{hash} 30d
#   - publish approval.decided
# [并发安全]
#   - PG row-lock (SELECT FOR UPDATE on inbox_queue)
#   - UNIQUE(queue_id, decision_hash) 防重（[AR洞察-3]）
#   - Redis SETNX nonce 防重放
# [幂等性] 是；append-only 永久；重复请求查询并返回上次 decision_id
# [性能约束] P95 ≤ 300ms
# [示例]
#   result = await service.decide(
#       queue_id=q, decision=Decision.allow, custom_args=None,
#       decider=user_id, decision_ts=now_ms, nonce="...", trace_id=tid)
# [来源标注] [DD-001:IC-006 + MD:M-B04 函数签名 #2 + SEC-005 + AR洞察-3]


# ---------------------------------------------------------------------------
# 函数注释 — timeout_scan
# ---------------------------------------------------------------------------
# [函数名] timeout_scan
# [职责] 周期扫描 pending 超时项，标记为 timeout 状态
# [关联接口契约] 内部接口（由 scanner.py arq 任务驱动）
# [参数说明]
#   now_ts: int 必填  当前时间戳（毫秒）；由调度器注入便于测试
# [返回值]
#   类型: int
#   描述: 本次标记为 timeout 的记录数量
# [错误码]
#   DBUnavailable → 重试 max 3 + 告警 WARN（不抛出，避免任务失败堆积）
# [前置条件] Leader Election 通过（与 M-A04 协调；同一时刻仅一个实例扫描）
# [后置条件]
#   - UPDATE inbox_queue SET status='timeout' WHERE status='pending' AND created_at < now - 60s
#   - publish approval.timeout (per row)
# [并发安全] 必须 Leader-only；普通实例调用应 noop 或抛 NotLeaderError
# [幂等性] 是；重复扫描已 timeout 项 UPDATE 0 行（WHERE 子句过滤）
# [性能约束] 单次扫描 ≤ 5s；批量 LIMIT 1000
# [来源标注] [DD-001:MD:M-B04 子模块"queue"+ APPROVAL_TIMEOUT 错误码 + DD-M-B04 推断: 拆分到 scanner.py 由 arq 驱动]


# ---------------------------------------------------------------------------
# 模块洞察 [DD-M-B04 推断]
# ---------------------------------------------------------------------------
# 洞察1 (异常处理未标注): MD 中 DBUnavailable 与 HashMismatch 均要求"走 pending"，
#   但未指定是否 publish approval.requested。本框架统一：fail-safe pending 同样发布事件，
#   以便审计链路完整；DD-S 实现时需确保事件 payload 标注 fail_safe=true 字段以便监控区分。
# 洞察2 (幂等性未标注): IC-006 错误码 APPROVAL_DUPLICATE 返回 409 但要求"幂等返回上次结果"，
#   语义上 409 与"成功幂等"略有冲突；本框架建议响应体明示 {duplicate: true, original_decision_id: ...}
#   供客户端识别，避免误判为失败。
