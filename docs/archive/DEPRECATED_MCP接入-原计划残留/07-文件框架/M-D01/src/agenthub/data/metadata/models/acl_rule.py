"""ACLRule ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/acl_rule.py
[文件职责] 映射 PG 表 acl_rules（workspace 级网络 ACL 规则）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-017 + DE-024 + MD:M-C05]
[功能描述]
  功能1: 定义 ACLRule 类
  功能2: 字段 id / workspace_id / rule_type / cidr (PG CIDR 类型) / port / protocol / rule_hash (UNIQUE)
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/acl_rule.py
[注意事项]
  注意1: cidr 使用 PG 原生 CIDR 类型（非 VARCHAR），便于 << 子网包含运算
  注意2: rule_hash UNIQUE 实现幂等 apply（[IC-012 幂等性]）
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-017 + DE-024 + IC-012]
"""

# ============================================================
# [类名] ACLRule
# [职责] 映射 acl_rules 表
# [属性] id / workspace_id / rule_type (allow|deny) / cidr (CIDR) / port / protocol / rule_hash (UNIQUE)
# [来源标注] [DD-001:DS-017]
# ============================================================
