"""SecretRef ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/secret_ref.py
[文件职责] 映射 PG 表 secret_refs（Vault secret 元数据 / 仅引用不存值）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-018 + DE-025 + TDR-010 + MD:M-C07]
[功能描述]
  功能1: 定义 SecretRef 类
  功能2: 字段 id / name (UNIQUE) / workspace_id / rotated_at / next_rotation
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/secret_ref.py
[注意事项]
  注意1: 严禁存储 secret 明文！本表仅记录 Vault path 后缀（name）+ 轮换时间
  注意2: 实际 secret 在 Vault KV v2 路径 `secret/data/agenthub/{name}`（DS-030）
  注意3: 90d 轮换由 Cron 触发 M-C07.rotate
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2 + SEC]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-018 + TDR-010]
"""

# ============================================================
# [类名] SecretRef
# [职责] 映射 secret_refs 表（Vault 元数据引用）
# [属性] id / name (UNIQUE VARCHAR(128)) / workspace_id / rotated_at / next_rotation
# [来源标注] [DD-001:DS-018]
# ============================================================
