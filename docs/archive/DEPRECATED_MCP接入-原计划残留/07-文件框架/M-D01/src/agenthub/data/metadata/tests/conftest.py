"""共享测试 fixture - M-D01.

[文件路径] src/agenthub/data/metadata/tests/conftest.py
[文件职责] 提供 testcontainers PG / Alembic 自动迁移 / 测试 UoW 等共享 fixture
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:CS-MCP §1.7 + MD:M-D01 测试策略]
[功能描述]
  功能1: pg_container fixture - 启动 testcontainers PostgreSQL 15
  功能2: engine fixture - 基于容器 DSN 创建 AsyncEngine
  功能3: alembic_apply fixture - 自动跑 Alembic upgrade head
  功能4: uow fixture - 每测试函数独立 UnitOfWork 实例（事务隔离）
  功能5: sample_workspace / sample_mcp / sample_inbox 等 factory fixture
[依赖关系] 第三方 pytest / pytest-asyncio / testcontainers / alembic
[注意事项]
  注意1: fixture scope=function 强制每测试独立事务；scope=session 仅用于 PG 容器
  注意2: 测试结束后必须 await engine.dispose() 释放连接
[代码风格] 遵循 [DD-001:CS-MCP §1.7]
[创建日期] 2026-06-03
[作者] DD-M-D01-20260603
[来源标注] [DD-001:CS-MCP §1.7 + MD:M-D01 + DD-M推断:依据=testcontainers + Alembic 自动迁移]
"""

# ============================================================
# [测试 fixture 1: pg_container] [scope: session] [Mock: 无（真 PG 容器）]
# 启动 testcontainers PG 15；测试会话结束时 stop
# ============================================================

# ============================================================
# [测试 fixture 2: engine] [scope: session] [依赖: pg_container]
# 从容器 DSN 创建 AsyncEngine（asyncpg）；session 结束 dispose
# ============================================================

# ============================================================
# [测试 fixture 3: alembic_apply] [scope: session] [依赖: engine]
# 调用 alembic upgrade head；保证 schema 与 ORM 一致
# ============================================================

# ============================================================
# [测试 fixture 4: uow] [scope: function] [依赖: engine, alembic_apply]
# 构造 UnitOfWork；每测试函数结束 rollback 隔离数据
# ============================================================
