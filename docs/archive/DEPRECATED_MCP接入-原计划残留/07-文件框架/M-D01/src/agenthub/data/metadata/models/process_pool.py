"""ProcessPool ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/process_pool.py
[文件职责] 映射 PG 表 process_pool，记录 spawn 出的子进程状态
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-004 + DE-004 + AC:AG-006 + MD:M-B02 调用方]
[功能描述]
  功能1: 定义 ProcessPool 类，pid 为主键（BIGINT，OS 原生 pid）
  功能2: 字段 pid / mcp_id / workspace_id / state / spawned_at / last_health / fail_count / rss_bytes / fd_count
  功能3: 唯一索引 (workspace_id, mcp_id) WHERE state IN ('running','idle')，防止同 ws 内重复 spawn
  功能4: 状态机 idle / spawning / running / recycling / recycled / zombie（CHECK 约束）
[输入输出]
  输入: M-B02 ProcessPool.spawn → INSERT；healthcheck / recycle → UPDATE
  输出: spawn / recycle / evict 决策依据
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/process_pool.py
[注意事项]
  注意1: pid 为 BIGINT 主键（非 UUID），避免与 OS pid 不一致
  注意2: 部分唯一索引（partial unique）需 PG 特有语法 `WHERE state IN (...)`，Alembic 自动生成可能失败，需手写 op.execute()
  注意3: row-lock 由 Repository 层 SELECT FOR UPDATE 控制，避免并发 spawn 越限（[AR洞察-2] + [DD洞察-1]）
  注意4: state 流转通过 ORM event listener 校验合法性（[DD-M推断:依据=状态机不可越级跳转]）
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-004 + DE-004 + AC:AG-006 + DD洞察-1]
"""

# ============================================================
# [类名] ProcessPool
# [职责] 映射 process_pool 表，承载进程池运行时状态
# [属性]
#   pid: Mapped[int] - BIGINT PK
#   mcp_id / workspace_id: Mapped[UUID]
#   state: Mapped[str] - VARCHAR(16) CHECK
#   spawned_at: Mapped[datetime]
#   last_health: Mapped[datetime | None]
#   fail_count: Mapped[int] - SMALLINT default 0（上限 3 → zombie）
#   rss_bytes / fd_count: Mapped[int | None] - 健康检查回填
# [状态机]
#   idle → spawn_requested → spawning → running → idle (5min idle) → recycling → recycled
#   running → health_fail × 3 → zombie → recycled
#   spawning → spawn_fail → reserved_slot → retry → spawning（max 3）
# [异常处理]
#   IntegrityError: 同 ws + mcp 已 running/idle 触发 partial UNIQUE
#   CheckConstraintViolation: state 越界
# [来源标注] [DD-001:DS-004 + MD:M-B02]
# ============================================================
