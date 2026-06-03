"""K4RuleSet ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/k4_rule_set.py
[文件职责] 映射 PG 表 k4_rule_set（K4 11+1 类规则集版本管理）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-015 + DE-020 + MD:M-C02]
[功能描述]
  功能1: 定义 K4RuleSet 类
  功能2: 字段 id / version (UNIQUE) / rules_json (JSONB) / status / created_at
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/k4_rule_set.py
[注意事项]
  注意1: status: active / deprecated；同一时刻仅一个 active（应用层约束，DB 无 partial UNIQUE）
  注意2: 规则集升级走 Alembic data migration，避免 K4Analyzer 缓存与 DB 版本漂移
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-015 + DE-020]
"""

# ============================================================
# [类名] K4RuleSet
# [职责] 映射 k4_rule_set 表
# [属性] id / version (UNIQUE VARCHAR(16)) / rules_json (JSONB) / status / created_at
# [来源标注] [DD-001:DS-015]
# ============================================================
