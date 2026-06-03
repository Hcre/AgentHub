"""Metadata Store package - M-D01.

[文件路径] src/agenthub/data/metadata/__init__.py
[文件职责] M-D01 包入口，导出 ORM 模型 / Repository / UnitOfWork 公共 API
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:FS-019 + MD:M-D01]
[功能描述]
  功能1: 暴露 35 SQLAlchemy 模型（来自 DS-001~DS-019 19 PG 表组）的公共类符号
  功能2: 暴露 BaseRepository / 30 具体 Repository 公共构造器
  功能3: 暴露 UnitOfWork 上下文管理器，作为唯一事务边界出口
[输入输出]
  输入: 调用方 import (M-B01 / M-B02 / M-B03 / M-B04 / M-B05 / M-A04 / M-EV01 等)
  输出: 公共类 / 工厂 / 上下文管理器
[依赖关系]
  依赖文件: ./models/__init__.py, ./repositories/__init__.py, ./unit_of_work.py
  被依赖文件: 跨模块通过 `from agenthub.data.metadata import UnitOfWork, MCPServerRepository, ...` 调用
[注意事项]
  注意1: 仅导出"公共"符号；带下划线前缀的内部实现禁止重新导出
  注意2: 严禁在此文件中放置业务逻辑或 IO 调用（包导入应保持轻量、纯导入）
  注意3: 与 SQLAlchemy 的 MetaData 全局对象同名易冲突，调用方需用 `from sqlalchemy import MetaData as SAMetadata` 别名（[DD洞察-6]）
[代码风格] 遵循 [DD-001:CS-MCP §1]（Python 3.11 / 4 空格 / 100 列 / Google Docstring）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:FS-019 + MD:M-D01 + CS-MCP §1.5 导入规范]
"""

# [DD-M推断:依据=Python 包公共 API 显式 __all__ 列表，便于 mypy / IDE 静态分析]
# __all__ 将由 DD-S（结构设计师）根据 models / repositories / unit_of_work 实际符号填充
__all__: list[str] = []
