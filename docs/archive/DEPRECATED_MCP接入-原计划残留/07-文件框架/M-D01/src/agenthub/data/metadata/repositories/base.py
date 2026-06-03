"""BaseRepository[T] 泛型基类 - M-D01.

[文件路径] src/agenthub/data/metadata/repositories/base.py
[文件职责] 定义 Repository 模式的泛型基类，所有具体 Repository 继承
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:MD:M-D01 + IC-017 + FS-019 + 设计模式: Repository + UnitOfWork + Specification]
[功能描述]
  功能1: 提供 BaseRepository[T: Base] 泛型，封装通用 CRUD 方法
  功能2: 接受 AsyncSession 构造，绑定到 UnitOfWork 的事务上下文
  功能3: 支持 Specification 模式查询（list_by_spec）
  功能4: 提供 select_for_update 行锁原语，供并发场景使用（如 inbox_queue 决策）
  功能5: 自动重试 Deadlock（指数退避 100ms/200ms/400ms，max 3）
[输入输出]
  输入: AsyncSession（由 UnitOfWork 注入）/ 实体对象 / Specification
  输出: 实体实例 / 实体列表 / 主键 UUID
[依赖关系]
  依赖文件: ../models/base.py (Base), ./specifications.py
  被依赖文件: ./market_repos.py, ./pool_repos.py, ./approval_repos.py,
              ./submission_repos.py, ./system_repos.py
[注意事项]
  注意1: 严禁在 Repository 内 commit / rollback；事务由 UnitOfWork 统一管理（[设计模式约束: Repository 只负责数据访问]）
  注意2: select_for_update 必须在 async with UnitOfWork: 上下文内调用（外部裸 session 调用会泄露事务边界）
  注意3: Deadlock 重试逻辑需识别 PG SQLSTATE 40P01；其他 IntegrityError 不重试
  注意4: 所有方法 100% async，禁止阻塞 IO（[CS-MCP §1.8]）
  注意5: 类型注解必须 strict（mypy disallow_untyped_defs），泛型 T 须 bound=Base
[代码风格] 遵循 [DD-001:CS-MCP §1.3 类型注解 + §1.8 异步]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:MD:M-D01 + IC-017 + DD-M推断:依据=Repository 模式约束 commit 由 UoW 统一]
"""

# ============================================================
# [类名] BaseRepository[T]
# [职责] Repository 模式泛型基类，封装 CRUD + Specification 查询
# [关联设计规范] [DD-001:MD:M-D01 + IC-017]
# [属性]
#   _session: AsyncSession - 由 UnitOfWork 注入
#   _model_class: type[T] - 子类指定的 ORM 类
# [方法列表]
#   __init__(session: AsyncSession, model_class: type[T]) → None - 构造
#   async get(id: UUID) → T | None - 主键查询；P95 ≤ 50ms（IC-017）
#   async list(filter: dict | None = None, limit: int = 100, offset: int = 0) → list[T] - 列表查询
#   async list_by_spec(spec: Specification[T], limit: int = 100, offset: int = 0) → list[T] - 规约查询
#   async add(entity: T) → UUID - 插入；返回主键
#   async update(entity: T) → None - 更新；append-only 模型 raise AppendOnlyViolation
#   async delete(id: UUID) → None - 删除；append-only 模型 raise AppendOnlyViolation
#   async select_for_update(id: UUID) → T | None - 行锁查询（SELECT ... FOR UPDATE）
#   async count(spec: Specification[T] | None = None) → int - 计数
# [状态机] 无
# [异常处理]
#   IntegrityError → DBIntegrityError（领域异常）；含 UNIQUE / FK / CHECK 子类
#   DeadlockError (SQLSTATE 40P01) → 自动重试 max 3（100/200/400ms）；超限上抛 DBDeadlockExhausted
#   AppendOnlyViolation → 直接上抛，禁止重试
#   OperationalError → 上抛 DBUnavailable（503）；由调用方决定降级
# [来源标注] [DD-001:IC-017 + MD:M-D01]
# ============================================================

# ============================================================
# [函数名] _retry_on_deadlock
# [职责] 装饰器：捕获 PG Deadlock 并指数退避重试 max 3 次
# [关联接口契约] [IC-017 错误码 DB_DEADLOCK]
# [参数说明]
#   func: Callable - 被装饰的 async 方法
#   max_retries: int = 3 - 最大重试次数
#   base_delay_ms: int = 100 - 起始退避（100ms → 200ms → 400ms）
# [返回值]
#   类型: Callable[..., Awaitable[T]]
#   描述: 装饰后的方法
# [错误码] DB_DEADLOCK 503（超限上抛 DBDeadlockExhausted）
# [前置条件] 必须在 async 上下文使用
# [后置条件] 成功返回原结果；失败上抛包装异常
# [并发安全] 是
# [幂等性] 否（重试期间副作用累加 → 必须在事务内，依赖 PG ROLLBACK ON ERROR）
# [性能约束] 单次重试最大额外延迟 = 100+200+400 = 700ms
# [来源标注] [DD-001:IC-017 + DD-M推断:依据=PG SQLSTATE 40P01 自动重试模式]
# ============================================================
