"""SQLAlchemy ORM 模型聚合入口 - M-D01.

[文件路径] src/agenthub/data/metadata/models/__init__.py
[文件职责] 聚合 19 PG 表 ORM 模型公共导出，提供 SQLAlchemy declarative Base 统一入口
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:FS-019 + DS-001~DS-019 + MD:M-D01]
[功能描述]
  功能1: 重新导出所有模型类，形成 `from agenthub.data.metadata.models import MCPServer, ProcessPool, ...` 单点入口
  功能2: 暴露 declarative Base（在 base.py 定义），供 Alembic env.py 收集所有 metadata
  功能3: 通过单文件导入触发 SQLAlchemy 关系映射注册（避免懒加载时未导入模型导致 NoForeignKeysError）
[输入输出]
  输入: 调用方 import
  输出: 35 SQLAlchemy ORM 类 + Base
[依赖关系]
  依赖文件: ./base.py, ./mcp_server.py, ./mcp_installation.py, ./workspace.py, ./process_pool.py,
            ./health_history.py, ./user_binding.py, ./cron_job.py, ./cron_run_log.py,
            ./inbox_queue.py, ./inbox_decision.py, ./allowlist_30d.py, ./mcp_submission.py,
            ./mcp_submission_history.py, ./ws_subscription.py, ./k4_rule_set.py,
            ./k4_test_corpus.py, ./acl_rule.py, ./secret_ref.py, ./mcp_migration_history.py
  被依赖文件: ../repositories/*.py, migrations/env.py
[注意事项]
  注意1: 必须显式导入所有模型类，否则 Alembic autogenerate 会遗漏（[DD-M推断:依据=Alembic 工作原理]）
  注意2: 严禁在模型 __init__ 中执行 DDL 操作；DDL 走 Alembic 迁移
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:FS-019 + DS-001~DS-019]
"""

# [DD-M推断:依据=SQLAlchemy 2.0 declarative_base 集中导出模式]
# DD-S 阶段需补充: from .base import Base / from .mcp_server import MCPServer / ...
__all__: list[str] = []
