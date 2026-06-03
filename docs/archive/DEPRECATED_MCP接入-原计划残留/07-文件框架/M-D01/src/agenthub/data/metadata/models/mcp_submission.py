"""MCPSubmission ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/mcp_submission.py
[文件职责] 映射 PG 表 mcp_submission（创作者提交的 Saga 入口记录）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-012 + DE-017 + MD:M-B05]
[功能描述]
  功能1: 定义 MCPSubmission 类
  功能2: 字段 id / mcp_id / version / manifest_json / status / k4_score / k4_tags / trace_id / submitted_by / submitted_at
  功能3: 唯一索引 (mcp_id, version) 实现 Saga 幂等
  功能4: status enum: queued / running / done / failed / rejected
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/mcp_submission.py
[注意事项]
  注意1: K4 失败时 status='rejected' 而非 'failed'（DDR-005 + DD洞察-3）
  注意2: trace_id 索引便于按提交链路追溯
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-012 + DE-017 + DDR-005]
"""

# ============================================================
# [类名] MCPSubmission
# [职责] 映射 mcp_submission 表
# [属性]
#   id / mcp_id / version / manifest_json (JSONB) / status / k4_score (SMALLINT) / k4_tags (TEXT[]) / trace_id (INDEX) / submitted_by / submitted_at
# [唯一索引] (mcp_id, version)
# [状态机] queued → running → (done | failed | rejected)
# [来源标注] [DD-001:DS-012]
# ============================================================
