"""Submission 域 Repository 集合 - M-D01.

[文件路径] src/agenthub/data/metadata/repositories/submission_repos.py
[文件职责] 聚合 MCPSubmission / MCPSubmissionHistory / WSSubscription 3 个 Repository
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-012/013/014 + IC-007 + MD:M-B05/M-A02]
[功能描述]
  功能1: MCPSubmissionRepository - Saga 入口记录 CRUD
  功能2: MCPSubmissionHistoryRepository - append-only Saga 步骤日志
  功能3: WSSubscriptionRepository - WebSocket 订阅持久化 + topic 反查
[依赖关系]
  依赖文件: ./base.py, ../models/mcp_submission.py, ../models/mcp_submission_history.py,
            ../models/ws_subscription.py, ./specifications.py
  被依赖文件: ../unit_of_work.py, M-B05 orchestrator, M-A02 server
[注意事项]
  注意1: MCPSubmissionHistory append-only；任何 update/delete 上抛 AppendOnlyViolation
  注意2: K4 失败由调用方设 status='rejected'，Repository 仅持久化（业务约束 DDR-005 在 services 层校验）
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-012/013/014 + IC-007 + DDR-005]
"""

# ============================================================
# [类名] MCPSubmissionRepository
# [职责] mcp_submission 表 CRUD
# [继承] BaseRepository[MCPSubmission]
# [方法列表]
#   async get_by_mcp_and_version(mcp_id: UUID, version: str) → MCPSubmission | None - 幂等查询
#   async get_by_trace(trace_id: UUID) → MCPSubmission | None
#   async add(entity: MCPSubmission) → UUID
#   async update_status(id: UUID, status: str, k4_score: int | None = None, k4_tags: list[str] | None = None) → None
# [关联接口契约] IC-007 mcp.submit
# [来源标注] [DD-001:DS-012 + IC-007]
# ============================================================

# ============================================================
# [类名] MCPSubmissionHistoryRepository
# [职责] mcp_submission_history append-only 写入
# [继承] BaseRepository[MCPSubmissionHistory]
# [方法列表]
#   async append(submission_id: UUID, step: str, status: str, payload: dict) → int - 返回 BIGSERIAL id
#   async list_by_submission(submission_id: UUID) → list[MCPSubmissionHistory] - 步骤追溯
#   update/delete → raise AppendOnlyViolation
# [来源标注] [DD-001:DS-013]
# ============================================================

# ============================================================
# [类名] WSSubscriptionRepository
# [职责] ws_subscription 表 CRUD + topic 反查
# [继承] BaseRepository[WSSubscription]
# [方法列表]
#   async add(entity: WSSubscription) → UUID
#   async list_by_topic(topic: str) → list[WSSubscription] - GIN 索引反查订阅者
#   async deactivate_by_client(client_id: str) → int - 软删
# [来源标注] [DD-001:DS-014 + MD:M-A02]
# ============================================================
