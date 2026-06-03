"""UnitOfWork - M-D01.

[文件路径] src/agenthub/data/metadata/unit_of_work.py
[文件职责] 定义 UnitOfWork（async context manager），承担事务边界与 Repository 工厂职责
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:MD:M-D01 + IC-017 + 设计模式: Repository + UnitOfWork]
[功能描述]
  功能1: 作为唯一事务边界出口；调用方 `async with UnitOfWork(engine) as uow:` 自动 commit / rollback
  功能2: 内部惰性构造 17 个 Repository 实例并暴露为属性（mcp_servers / process_pool / inbox_queue / ...）
  功能3: 与 PGBouncer 连接池协作（200 上限），async session 复用连接
  功能4: 异常发生时自动 rollback；正常退出时 commit；幂等（已 commit/rollback 后再调用为 no-op）
  功能5: 暴露 raw_session 仅供 Alembic / 极少数高级场景使用（[DD-M推断:依据=逃生舱口，但默认不推荐]）
[输入输出]
  输入: async_engine（由 core.config 创建）
  输出: UnitOfWork 实例 + Repository 集合
[依赖关系]
  依赖文件: 第三方 sqlalchemy.ext.asyncio + ./repositories/*.py
  被依赖文件: 跨模块所有数据访问入口（M-B01~M-B05, M-A02~M-A04, M-C05, M-C07, M-C09, M-EV01 等）
[注意事项]
  注意1: 严禁在同一 task 内嵌套 UnitOfWork（多事务嵌套语义不清晰，禁止 savepoint 套娃）
  注意2: 严禁在 UnitOfWork 外部直接 commit / rollback session；session 生命周期由 UoW 私有控制
  注意3: DeadlockError 重试由 BaseRepository 装饰器处理；UnitOfWork 仅捕获不在重试范围内的异常
  注意4: __aexit__ 中若 exc_type 非 None 且 commit 已发生（不应发生），需 raise RuntimeError 提示状态机违规
  注意5: 连接池耗尽时 acquire timeout 由 SQLAlchemy 抛 TimeoutError；UnitOfWork 包装为 DBUnavailable 503（[IC-017 错误码]）
  注意6: 必须在每个 async task 单独构造 UoW；禁止跨 task 共享（asyncio session not task-safe）
[代码风格] 遵循 [DD-001:CS-MCP §1.3 类型注解 + §1.8 异步 + §1.6 异常]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:MD:M-D01 + IC-017 + DD-M推断:依据=显式事务边界 + PGBouncer 兼容]
"""

# ============================================================
# [类名] UnitOfWork
# [职责] async context manager 事务边界 + Repository 工厂
# [关联设计规范] [DD-001:MD:M-D01 + IC-017]
# [属性]
#   _engine: AsyncEngine - 注入的引擎
#   _session: AsyncSession | None - 私有 session（在 __aenter__ 创建）
#   _state: enum["Open", "Committed", "RolledBack"] - 状态机
#   mcp_servers: MCPServerRepository - 惰性构造
#   mcp_installations: MCPInstallationRepository
#   workspaces: WorkspaceRepository
#   process_pool: ProcessPoolRepository
#   health_history: HealthHistoryRepository
#   user_bindings: UserBindingRepository
#   cron_jobs: CronJobRepository
#   cron_run_log: CronRunLogRepository
#   inbox_queue: InboxQueueRepository
#   inbox_decision: InboxDecisionRepository
#   allowlist_30d: Allowlist30dRepository
#   mcp_submission: MCPSubmissionRepository
#   mcp_submission_history: MCPSubmissionHistoryRepository
#   ws_subscription: WSSubscriptionRepository
#   k4_rule_set: K4RuleSetRepository
#   k4_test_corpus: K4TestCorpusRepository
#   acl_rules: ACLRuleRepository
#   secret_refs: SecretRefRepository
#   mcp_migration_history: MCPMigrationHistoryRepository
# [方法列表]
#   __init__(engine: AsyncEngine) → None
#   async __aenter__() → UnitOfWork - 创建 session；状态置 Open；返回 self
#   async __aexit__(exc_type, exc_val, exc_tb) → None - 异常 rollback；正常 commit；关闭 session
#   async commit() → None - 显式提交（一般无需手动调用）
#   async rollback() → None - 显式回滚
#   property raw_session → AsyncSession - 暴露给 Alembic 等高级场景（不推荐）
# [状态机]
#   Init → __aenter__ → Open → (commit | rollback | __aexit__) → (Committed | RolledBack)
#   Committed | RolledBack → 任何方法调用 → raise RuntimeError
# [异常处理]
#   OperationalError → 包装为 DBUnavailable(503) 上抛
#   TimeoutError（连接池）→ 包装为 DBUnavailable(503)
#   IntegrityError → 上抛领域异常（由调用方处理）
#   RuntimeError → 状态机违规（如重复 commit）
# [并发安全] 单 UoW 实例非线程安全；每 task 独立构造
# [来源标注] [DD-001:IC-017 + MD:M-D01]
# ============================================================

# ============================================================
# [函数名] create_engine_from_settings
# [职责] 工厂：从 Settings 创建 AsyncEngine（封装连接串、PGBouncer 选项）
# [关联接口契约] 无（in-proc 工具函数）
# [参数说明]
#   settings: Settings - 来自 core.config（PG DSN / pool_size / pool_pre_ping）
# [返回值]
#   类型: AsyncEngine
#   描述: 配置好的 asyncpg 引擎
# [错误码] 无（构造失败上抛 OperationalError）
# [前置条件] PG DSN 有效
# [后置条件] 应用关闭前调用 await engine.dispose()
# [并发安全] AsyncEngine 全局单例线程安全
# [幂等性] 是（同入参 → 同实例由调用方缓存）
# [性能约束] 启动一次性，无运行时调用
# [来源标注] [DD-001:TS-009/011 + DD-M推断:依据=PGBouncer pool_pre_ping=True 避免连接已断]
# ============================================================
