"""M-B02 Process Pool Manager 测试包初始化.

[文件路径] src/agenthub/application/pool/tests/__init__.py
[文件职责] 测试包初始化，导出共享 fixtures
[所属模块] M-B02
[关联设计规范] FS-006 / MD-MCP-V1.0-20260602
[功能描述]
  功能1: 共享 fixture 注册（mock pool / mock spawner / fakeredis / asyncpg）
  功能2: 测试工具（构造 Process / 状态机驱动）
[输入输出]
  输入: 无
  输出: 测试共享 fixtures
[依赖关系]
  依赖文件: pytest / pytest-asyncio / fakeredis
  被依赖文件: 所有 test_*.py
[注意事项]
  注意1: 严禁在此处实现业务逻辑
  注意2: 所有 mock 必须显式（不依赖 patch 隐式行为）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.7 测试规范
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B02 - 初始版本
[作者] DD-M-B02-20260603
[来源标注] [DD-001:FS-006 + MD-MCP-M-B02]
"""
from __future__ import annotations

import pytest

__all__: list[str] = []
