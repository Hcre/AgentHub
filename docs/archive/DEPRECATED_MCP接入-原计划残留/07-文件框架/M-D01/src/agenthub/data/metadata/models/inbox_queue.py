"""InboxQueue ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/inbox_queue.py
[文件职责] 映射 PG 表 inbox_queue（审批待办队列）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-009 + DE-027 + ADR-006 + MD:M-B04]
[功能描述]
  功能1: 定义 InboxQueue 类
  功能2: 字段 id / workspace_id / mcp_id / tool / args_hash (CHAR(64)) / status / submitter_id / submitted_at / expires_at
  功能3: 部分唯一索引 (workspace_id, mcp_id, tool, args_hash) WHERE status='pending'，避免同参数重复入队
  功能4: 状态机 pending → allowed | denied | timeout（CHECK 约束）
  功能5: 索引 (expires_at) WHERE status='pending'，便于 timeout_scan
[输入输出]
  输入: M-B04 ApprovalService.check_and_queue
  输出: 待审批 inbox 行
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/inbox_queue.py, ../repositories/specifications.py
[注意事项]
  注意1: args_hash 必须为 SHA256（64 字符 hex），与 ADR-006 全局规约一致
  注意2: SELECT FOR UPDATE on inbox_queue 由 Repository 层提供，并发决策必须串行化（[IC-006 并发安全]）
  注意3: expires_at = submitted_at + 60s，由应用层填充（避免 DB now() 与应用时钟漂移）
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-009 + DE-027 + ADR-006 + IC-005/IC-006]
"""

# ============================================================
# [类名] InboxQueue
# [职责] 映射 inbox_queue 表，审批待办的核心载体
# [属性]
#   id: Mapped[UUID] - PK
#   workspace_id / mcp_id: Mapped[UUID]
#   tool: Mapped[str] - VARCHAR(128) NOT NULL（最长 ≤ 64 由 IC-005 校验）
#   args_hash: Mapped[str] - CHAR(64) NOT NULL（SHA256 hex）
#   status: Mapped[str] - VARCHAR(16) CHECK IN (pending/allowed/denied/timeout)
#   submitter_id: Mapped[UUID]
#   submitted_at: Mapped[datetime]
#   expires_at: Mapped[datetime]
# [状态机] pending → (allowed | denied | timeout) [单向]
# [异常处理]
#   IntegrityError: 同参数已有 pending（partial UNIQUE 触发）→ 返回上次 queue_id（幂等）
# [来源标注] [DD-001:DS-009 + IC-005]
# ============================================================
