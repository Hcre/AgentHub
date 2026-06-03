"""UserBinding ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/user_binding.py
[文件职责] 映射 PG 表 user_bindings（用户 × MCP × workspace 三元绑定）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-006 + DE-006 + MD:M-B03]
[功能描述]
  功能1: 定义 UserBinding 类
  功能2: 字段 id / user_id / mcp_id / workspace_id / mapping (JSONB)
  功能3: 唯一索引 (user_id, mcp_id, workspace_id)
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/user_binding.py
[注意事项]
  注意1: mapping 字段存储绑定策略（DefaultMapping / CustomMapping）的具体映射 dict
  注意2: 删除绑定时同步触发 M-B03 撤销 mcp-config 文件，事务一致性由 UnitOfWork 保证（[DD-M推断:依据=单事务多操作避免文件残留]）
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-006 + DE-006]
"""

# ============================================================
# [类名] UserBinding
# [职责] 映射 user_bindings 表
# [属性] id (UUID PK) / user_id (INDEX) / mcp_id / workspace_id / mapping (JSONB)
# [唯一索引] (user_id, mcp_id, workspace_id)
# [来源标注] [DD-001:DS-006]
# ============================================================
