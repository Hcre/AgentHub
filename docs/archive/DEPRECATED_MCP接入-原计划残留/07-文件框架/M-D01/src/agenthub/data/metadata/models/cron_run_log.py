"""CronRunLog ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/cron_run_log.py
[文件职责] 映射 PG 表 cron_run_log（按月分区，每次 Cron 触发日志）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-008 + DE-008 + MD:M-A04]
[功能描述]
  功能1: 定义 CronRunLog 类
  功能2: 字段 id (BIGSERIAL) / job_name / triggered_at / finished_at / status / err_msg
  功能3: 按月分区，便于运维查阅与定期清理
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/cron_run_log.py
[注意事项]
  注意1: status 仅 'success' / 'failed'
  注意2: err_msg 长度无限制（TEXT），需注意防御异常 stack trace 泄漏（[DD-M推断:依据=审计日志脱敏]）
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-008 + DE-008]
"""

# ============================================================
# [类名] CronRunLog
# [职责] 映射 cron_run_log 分区表
# [属性] id (BIGSERIAL PK) / job_name (INDEX) / triggered_at (INDEX) / finished_at / status / err_msg
# [分区] 按月
# [来源标注] [DD-001:DS-008]
# ============================================================
