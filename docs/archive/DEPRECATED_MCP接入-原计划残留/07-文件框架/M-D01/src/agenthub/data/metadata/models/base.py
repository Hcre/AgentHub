"""SQLAlchemy declarative Base + 通用 mixin - M-D01.

[文件路径] src/agenthub/data/metadata/models/base.py
[文件职责] 定义 SQLAlchemy 2.0 DeclarativeBase 与 TimestampMixin / UUIDPrimaryKeyMixin 等通用基类
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:FS-019 + MD:M-D01 + CS-MCP §2 SQL 规范]
[功能描述]
  功能1: 提供 DeclarativeBase 子类 Base，作为 19 张 PG 表 ORM 共同父类
  功能2: 提供 UUIDPrimaryKeyMixin（id UUID PK default gen_random_uuid()），减少重复字段定义
  功能3: 提供 TimestampMixin（created_at / updated_at TIMESTAMPTZ default now()），统一时间戳列
  功能4: 提供 AppendOnlyMixin（拒绝 UPDATE / DELETE 的 ORM 校验钩子），用于 inbox_decision / mcp_submission_history / mcp_migration_history
[输入输出]
  输入: SQLAlchemy ORM 子类继承
  输出: Base.metadata（供 Alembic env.py 调用）/ Mixin 列
[依赖关系]
  依赖文件: 标准库 datetime / uuid + 第三方 sqlalchemy.orm
  被依赖文件: ./mcp_server.py, ./process_pool.py, ./inbox_queue.py 等全部 19 模型
[注意事项]
  注意1: DeclarativeBase 必须为类（非函数 declarative_base()），遵循 SQLAlchemy 2.0 新语法
  注意2: AppendOnlyMixin 须在 ORM event listener 中拦截 'before_update' / 'before_delete'，且在 PG 端配 trigger 双重防护（[AR洞察-3] + [DS-010/013/019]）
  注意3: 时间戳列使用 server_default=func.now()，避免应用时钟与 DB 时钟偏差
[代码风格] 遵循 [DD-001:CS-MCP §1.3 类型注解 / §2 SQL 规范]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:CS-MCP §2 + DS-010/013/019 + DD-M推断:依据=SQLAlchemy 2.0 DeclarativeBase 最佳实践]
"""

# ============================================================
# [类名] Base
# [职责] SQLAlchemy 2.0 DeclarativeBase 根基类，承载全局 metadata
# [关联设计规范] [DD-001:FS-019]
# [属性] metadata: SAMetadata - 全局 metadata（聚合 19 张表 schema）
# [方法列表] 由 SQLAlchemy 提供
# [状态机] 无
# [异常处理] 无（仅基类）
# [来源标注] [DD-001:CS-MCP §2 + DD-M推断:Alembic 单 metadata 模型]
# ============================================================
# class Base(DeclarativeBase): ...

# ============================================================
# [类名] UUIDPrimaryKeyMixin
# [职责] 提供 id: UUID 主键列，默认 gen_random_uuid()
# [关联设计规范] [DD-001:CS-MCP §2 主键统一为 UUID]
# [属性]
#   id: Mapped[UUID] - 主键 (server_default=text("gen_random_uuid()"))
# [方法列表] 无
# [来源标注] [DD-001:CS-MCP §2]
# ============================================================

# ============================================================
# [类名] TimestampMixin
# [职责] 提供 created_at / updated_at 时间戳列
# [关联设计规范] [DD-001:CS-MCP §2 时间戳规范]
# [属性]
#   created_at: Mapped[datetime] - TIMESTAMPTZ NOT NULL server_default=now()
#   updated_at: Mapped[datetime] - TIMESTAMPTZ NOT NULL server_default=now() onupdate=now()
# [方法列表] 无（声明式列）
# [来源标注] [DD-001:CS-MCP §2 + DS-001]
# ============================================================

# ============================================================
# [类名] AppendOnlyMixin
# [职责] 拒绝 UPDATE / DELETE 的 ORM 钩子（双重防护：DB trigger + ORM event）
# [关联设计规范] [DS-010 inbox_decision + DS-013 mcp_submission_history + DS-019 mcp_migration_history + DD洞察-5]
# [属性] 无
# [方法列表]
#   _reject_update(mapper, connection, target) → None - 触发 before_update 时 raise AppendOnlyViolation
#   _reject_delete(mapper, connection, target) → None - 触发 before_delete 时 raise AppendOnlyViolation
# [异常处理]
#   AppendOnlyViolation: 调用方尝试更新或删除受保护行时抛出 [DD-M推断:领域异常名]
# [来源标注] [DD-001:DS-010/013/019 + DD洞察-5]
# ============================================================
