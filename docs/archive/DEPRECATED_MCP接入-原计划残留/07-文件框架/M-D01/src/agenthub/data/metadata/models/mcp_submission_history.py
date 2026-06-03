"""MCPSubmissionHistory ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/mcp_submission_history.py
[文件职责] 映射 PG 表 mcp_submission_history（append-only Saga 步骤日志）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-013 + DE-022 + DD洞察-5]
[功能描述]
  功能1: 定义 MCPSubmissionHistory 类，继承 AppendOnlyMixin
  功能2: 字段 id (BIGSERIAL) / submission_id (FK) / step / status / payload (JSONB) / occurred_at
  功能3: 5 步骤: dry_run / k4 / secret / metadata / history
[依赖关系]
  依赖文件: ./base.py (AppendOnlyMixin)
  被依赖文件: ../repositories/mcp_submission_history.py
[注意事项]
  注意1: 严禁 UPDATE / DELETE（ORM + PG trigger）
  注意2: status: started / done / failed / compensated
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-013 + DE-022 + DD洞察-5]
"""

# ============================================================
# [类名] MCPSubmissionHistory
# [职责] 映射 mcp_submission_history append-only 表
# [属性] id (BIGSERIAL PK) / submission_id (FK) / step / status / payload (JSONB) / occurred_at
# [异常处理] AppendOnlyViolation on UPDATE/DELETE
# [来源标注] [DD-001:DS-013]
# ============================================================
