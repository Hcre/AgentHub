"""MCPMigrationHistory ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/mcp_migration_history.py
[文件职责] 映射 PG 表 mcp_migration_history（append-only ACL 迁移 Saga 记录）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-019 + DE-026 + DD洞察-5 + MD:M-C09]
[功能描述]
  功能1: 定义 MCPMigrationHistory 类，继承 AppendOnlyMixin
  功能2: 字段 id (BIGSERIAL) / workspace_id / snapshot_hash (CHAR(64)) / status / applied_count / occurred_at
[依赖关系]
  依赖文件: ./base.py (AppendOnlyMixin)
  被依赖文件: ../repositories/mcp_migration_history.py
[注意事项]
  注意1: 严禁 UPDATE / DELETE
  注意2: status: committed / rolled
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-019 + DE-026]
"""

# ============================================================
# [类名] MCPMigrationHistory
# [职责] 映射 mcp_migration_history append-only 表
# [属性] id (BIGSERIAL) / workspace_id / snapshot_hash / status / applied_count / occurred_at
# [来源标注] [DD-001:DS-019]
# ============================================================
