"""Allowlist30d ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/allowlist_30d.py
[文件职责] 映射 PG 表 allowlist_30d（30 天许可缓存，与 Redis allowlist:{ws_id} 双写）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-011 + DE-029 + ADR-006 + AR洞察-3]
[功能描述]
  功能1: 定义 Allowlist30d 类
  功能2: 字段 id / workspace_id / mcp_id / tool / args_hash / granted_at / expires_at
  功能3: 唯一索引 (workspace_id, mcp_id, tool, args_hash) 防止重复 granted
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/allowlist_30d.py
[注意事项]
  注意1: PG 写后 500ms 异步刷 Redis（[AR洞察-3]）由 M-B04 协调，本模块不负责
  注意2: 过期清理由 Cron 定时 DELETE WHERE expires_at < now()，避免索引膨胀
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-011 + ADR-006]
"""

# ============================================================
# [类名] Allowlist30d
# [职责] 映射 allowlist_30d 表
# [属性] id / workspace_id / mcp_id / tool / args_hash / granted_at / expires_at
# [来源标注] [DD-001:DS-011]
# ============================================================
