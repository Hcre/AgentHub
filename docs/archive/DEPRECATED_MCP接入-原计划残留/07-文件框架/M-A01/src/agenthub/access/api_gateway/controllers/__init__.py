"""M-A01 controllers subpackage.

[文件路径] src/agenthub/access/api_gateway/controllers/__init__.py
[文件职责] controllers 子包初始化；暴露 api_router 给 app.py
[所属模块] M-A01 Web API Gateway
[关联设计规范] FS-001
[依赖关系]
  依赖文件: _router.py
  被依赖文件: ../app.py
[代码风格] 遵循 CS-MCP-V1.0 §1
[创建日期] 2026-06-03
[修改历史] 2026-06-03: DD-M-A01 - 初版
[作者] DD-M-A01-20260603
[来源标注] [DD-001:FS-001]
"""

from __future__ import annotations

__all__: list[str] = [
    # "api_router",  # 由 _router.py 提供
]
