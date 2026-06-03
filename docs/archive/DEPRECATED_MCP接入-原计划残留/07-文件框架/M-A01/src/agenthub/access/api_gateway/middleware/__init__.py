"""M-A01 middleware subpackage.

[文件路径] src/agenthub/access/api_gateway/middleware/__init__.py
[文件职责] middleware 子包初始化；导出四个中间件类
[所属模块] M-A01 Web API Gateway
[关联设计规范] FS-001 / MD:M-A01 设计模式 Chain of Responsibility
[依赖关系]
  依赖文件: auth.py / ratelimit.py / trace.py / metrics.py
  被依赖文件: ../app.py
[代码风格] 遵循 CS-MCP-V1.0 §1
[创建日期] 2026-06-03
[修改历史] 2026-06-03: DD-M-A01 - 初版
[作者] DD-M-A01-20260603
[来源标注] [DD-001:FS-001 + MD:M-A01]
"""

from __future__ import annotations

__all__: list[str] = [
    # "AuthMiddleware",      # 由 auth.py 提供
    # "RateLimiter",         # 由 ratelimit.py 提供
    # "TraceMiddleware",     # 由 trace.py 提供
    # "MetricsMiddleware",   # 由 metrics.py 提供
]
