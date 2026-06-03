"""M-B03 Binding Engine 测试包入口.

[文件路径] src/agenthub/application/binding/tests/__init__.py
[文件职责] 标记 tests 为 Python 包，集中导出 conftest fixtures
[所属模块] M-B03
[关联设计规范] CS-MCP-V1.0-20260602 §1.7
[功能描述]
  功能1: 暴露 conftest 中的共享 fixture（in-memory repo / fake pool / tmp config dir）
[来源标注] [DD-M推断:典型 pytest 包布局]
[创建日期] 2026-06-03
[作者] DD-M-B03-20260603
"""
from __future__ import annotations
