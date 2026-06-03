"""CronJob ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/cron_job.py
[文件职责] 映射 PG 表 cron_jobs（APScheduler 任务定义）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-007 + DE-007 + MD:M-A04]
[功能描述]
  功能1: 定义 CronJob 类
  功能2: 字段 name (PK VARCHAR(64)) / cron_expr / enabled / last_run / next_run / fail_count
  功能3: next_run 索引用于 Scheduler 高效拉取就绪任务
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/cron_job.py
[注意事项]
  注意1: name 为业务主键（非 UUID），便于人工运维查询
  注意2: cron_expr 校验由应用层完成（croniter 库）；DB 仅存储原文
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-007 + DE-007]
"""

# ============================================================
# [类名] CronJob
# [职责] 映射 cron_jobs 表
# [属性] name (PK) / cron_expr / enabled / last_run / next_run (INDEX) / fail_count
# [来源标注] [DD-001:DS-007]
# ============================================================
