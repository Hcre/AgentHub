"""WSSubscription ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/ws_subscription.py
[文件职责] 映射 PG 表 ws_subscription（WebSocket 订阅持久化）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-014 + DE-013 + MD:M-A02]
[功能描述]
  功能1: 定义 WSSubscription 类
  功能2: 字段 id / client_id / agent_id / topics (TEXT[] GIN) / active / subscribed_at
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/ws_subscription.py
[注意事项]
  注意1: topics 使用 GIN 索引支持按 topic 反查订阅者
  注意2: M-A02 在 connect 时写入，disconnect 时设 active=false（软删）
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-014 + DE-013]
"""

# ============================================================
# [类名] WSSubscription
# [职责] 映射 ws_subscription 表
# [属性] id / client_id (INDEX) / agent_id / topics (TEXT[] GIN) / active / subscribed_at
# [来源标注] [DD-001:DS-014]
# ============================================================
