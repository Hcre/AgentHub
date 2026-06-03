"""Workspace ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/workspace.py
[文件职责] 映射 PG 表 workspaces，承载工作区元数据
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-003 + DE-003 + FS-019]
[功能描述]
  功能1: 定义 Workspace 类
  功能2: 字段 id / name / admins / created_at
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/workspace.py
[注意事项]
  注意1: admins 为 UUID[]，校验在应用层进行（非 FK）；如需 FK 需引入 workspace_admins 连接表
  注意2: name UNIQUE，重命名需走 Alembic 迁移并校验冲突
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-003 + DE-003]
"""

# ============================================================
# [类名] Workspace
# [职责] 映射 workspaces 表
# [属性] id / name (UNIQUE) / admins (UUID[]) / created_at
# [异常处理] IntegrityError on duplicate name
# [来源标注] [DD-001:DS-003]
# ============================================================
