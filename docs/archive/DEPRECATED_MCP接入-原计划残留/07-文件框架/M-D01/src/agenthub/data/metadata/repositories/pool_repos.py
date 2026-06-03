"""Pool 域 Repository 集合 - M-D01.

[文件路径] src/agenthub/data/metadata/repositories/pool_repos.py
[文件职责] 聚合 ProcessPool / HealthHistory 2 个 Repository（进程池相关）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-004/005 + IC-004 + MD:M-B02 + AC:AG-006]
[功能描述]
  功能1: ProcessPoolRepository - 进程池状态行 CRUD + 行锁原语
  功能2: HealthHistoryRepository - 健康检查历史（分区表）批量写入
[依赖关系]
  依赖文件: ./base.py, ../models/process_pool.py, ../models/health_history.py, ./specifications.py
  被依赖文件: ../unit_of_work.py, M-B02 services
[注意事项]
  注意1: spawn 路径必须 select_for_update 锁定 workspace 槽位（[DD洞察-1] + IC-004 并发安全）
  注意2: health_history 高频写入，提供 add_batch 接口；走 COPY 而非逐行 INSERT
[代码风格] 遵循 [DD-001:CS-MCP §1 + IC-017]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-004/005 + MD:M-B02 + DD洞察-1]
"""

# ============================================================
# [类名] ProcessPoolRepository
# [职责] process_pool 表 CRUD + workspace 槽位锁
# [继承] BaseRepository[ProcessPool]
# [方法列表]
#   async get_by_pid(pid: int) → ProcessPool | None
#   async list_by_workspace(workspace_id: UUID, states: list[str] | None = None) → list[ProcessPool]
#   async count_active_by_workspace(workspace_id: UUID) → int - spawn 前检查槽位（< 64）
#   async lock_workspace_slot(workspace_id: UUID) → None - SELECT 1 FROM process_pool WHERE workspace_id=$1 FOR UPDATE（[DD洞察-1] PG 行锁）
#   async add(entity: ProcessPool) → UUID
#   async transition_state(pid: int, from_state: str, to_state: str) → bool - 原子状态机迁移（CAS 风格）
#   async list_idle_over(grace_sec: int) → list[ProcessPool] - 回收候选
#   async list_zombie() → list[ProcessPool] - fail_count ≥ 3
# [关联接口契约] IC-004 pool.spawn
# [来源标注] [DD-001:DS-004 + IC-004 + MD:M-B02]
# ============================================================

# ============================================================
# [类名] HealthHistoryRepository
# [职责] health_history 分区表批量写入
# [继承] BaseRepository[HealthHistory]
# [方法列表]
#   async add_batch(records: list[HealthHistory]) → int - 批量插入（COPY）；返回插入行数
#   async list_recent_by_pid(pid: int, limit: int = 100) → list[HealthHistory]
#   async cleanup_partition_older_than(days: int = 90) → None - 调用 PG DROP PARTITION（运维方法）
# [性能约束] add_batch P95 ≤ 100ms / 1000 行
# [来源标注] [DD-001:DS-005]
# ============================================================
