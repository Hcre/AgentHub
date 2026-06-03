"""HealthHistory ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/health_history.py
[文件职责] 映射 PG 表 health_history（按月分区，进程健康检查历史，保留 90 天）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-005 + DE-005]
[功能描述]
  功能1: 定义 HealthHistory 类，id 为 BIGSERIAL
  功能2: 字段 id / pid / check_at / success / latency_ms / err_msg
  功能3: 按月分区（按 check_at）+ 90 天保留策略（清理 Cron 由 M-A04 调度）
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/health_history.py
[注意事项]
  注意1: 分区表 Alembic 迁移需手写（autogenerate 不支持），首批迁移由本模块负责
  注意2: 写入路径要求高吞吐，Repository.add 应支持批量 COPY（[DD-M推断:依据=每个进程 30s/次 健康检查]）
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-005 + DE-005]
"""

# ============================================================
# [类名] HealthHistory
# [职责] 映射 health_history 分区表
# [属性] id (BIGSERIAL PK) / pid (INDEX) / check_at (INDEX) / success / latency_ms / err_msg
# [分区] 按月（PARTITION BY RANGE (check_at)）
# [保留] 90 天（Cron 触发 DROP PARTITION）
# [来源标注] [DD-001:DS-005]
# ============================================================
