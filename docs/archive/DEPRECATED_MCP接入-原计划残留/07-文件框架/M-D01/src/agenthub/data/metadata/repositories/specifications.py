"""Specification 模式基类与查询规约 - M-D01.

[文件路径] src/agenthub/data/metadata/repositories/specifications.py
[文件职责] 定义 Specification[T] 泛型基类与可组合的领域查询规约，避免业务方拼接 SQLAlchemy filter
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:MD:M-D01 + 设计模式: Specification]
[功能描述]
  功能1: Specification[T] 抛弃 ad-hoc kwargs filter，将查询条件封装为可命名/可测试的对象
  功能2: 支持 AndSpecification / OrSpecification / NotSpecification 组合
  功能3: 提供具体规约: PendingInboxByWorkspaceSpec / ExpiredInboxSpec / ActiveProcessByWorkspaceSpec /
         PublishedMCPSpec / Allowlist30dActiveSpec / 等
  功能4: 通过 to_clause(model_class) → ColumnElement 翻译为 SQLAlchemy 表达式
[输入输出]
  输入: 业务层组合规约对象 → 传入 Repository.list_by_spec
  输出: SQLAlchemy where 子句
[依赖关系]
  依赖文件: 第三方 sqlalchemy + ../models/*.py
  被依赖文件: ./base.py, ./approval_repos.py, ./pool_repos.py 等
[注意事项]
  注意1: Specification 必须是 Value Object（不可变 + __eq__/__hash__），便于缓存与单元测试
  注意2: 严禁在 Specification 内执行 IO；纯 ColumnElement 翻译
  注意3: 复杂规约（如 JSONB 子段匹配）必须封装为独立 Spec 类，禁止 lambda（[DD-M推断:依据=可读性 + IDE 跳转]）
[代码风格] 遵循 [DD-001:CS-MCP §1.9 @pure 装饰]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:MD:M-D01 设计模式 Specification + DD-M推断:依据=避免业务层 SQLAlchemy 耦合]
"""

# ============================================================
# [类名] Specification[T]
# [职责] 规约模式抽象基类
# [属性] 无
# [方法列表]
#   to_clause(model_class: type[T]) → ColumnElement - 翻译为 SQLAlchemy where 子句
#   __and__(other: Specification[T]) → AndSpecification[T] - 组合
#   __or__(other: Specification[T]) → OrSpecification[T] - 组合
#   __invert__() → NotSpecification[T] - 组合
# [来源标注] [DD-001:MD:M-D01]
# ============================================================

# ============================================================
# [类名] PendingInboxByWorkspaceSpec
# [职责] 查询 workspace 下所有 status='pending' 的 InboxQueue
# [属性] workspace_id: UUID
# [关联模型] InboxQueue
# [来源标注] [DD-001:DS-009 + MD:M-B04]
# ============================================================

# ============================================================
# [类名] ExpiredInboxSpec
# [职责] 查询 status='pending' 且 expires_at < now() 的 InboxQueue（timeout_scan 用）
# [属性] now_ts: datetime
# [关联模型] InboxQueue
# [来源标注] [DD-001:DS-009 + IC-005 timeout_scan]
# ============================================================

# ============================================================
# [类名] ActiveProcessByWorkspaceSpec
# [职责] 查询 workspace 下 state IN ('running','idle','spawning') 的 ProcessPool 行
# [属性] workspace_id: UUID
# [关联模型] ProcessPool
# [来源标注] [DD-001:DS-004 + MD:M-B02]
# ============================================================

# ============================================================
# [类名] PublishedMCPSpec
# [职责] 查询 status='published' 的 MCPServer（市场列表用）
# [属性] category: str | None / tags: list[str] | None
# [关联模型] MCPServer
# [来源标注] [DD-001:DS-001 + MD:M-B01]
# ============================================================

# ============================================================
# [类名] Allowlist30dActiveSpec
# [职责] 查询 expires_at > now() 的 Allowlist30d
# [属性] workspace_id / mcp_id / tool / args_hash
# [来源标注] [DD-001:DS-011 + ADR-006]
# ============================================================
