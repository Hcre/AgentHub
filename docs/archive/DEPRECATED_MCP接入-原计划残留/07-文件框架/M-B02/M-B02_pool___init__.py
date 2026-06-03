"""M-B02 Process Pool Manager 模块初始化文件.

[文件路径] src/agenthub/application/pool/__init__.py
[文件职责] 模块初始化，导出公共接口供 FastAPI 路由层调用
[所属模块] M-B02
[关联设计规范] FS-006 / MD-MCP-V1.0-20260602
[功能描述]
  功能1: 导出 ProcessPool 单例与 PoolController 路由
  功能2: 统一暴露 spawn / healthcheck_all / recycle_idle / evict_lru 公共方法
  功能3: 暴露领域异常（PoolFullError / SpawnFailedError）
[输入输出]
  输入: 无（仅做符号导出）
  输出: 公共符号 (ProcessPool, PoolController, PoolFullError, SpawnFailedError)
[依赖关系]
  依赖文件: agenthub.application.pool.controllers, agenthub.application.pool.pool, agenthub.application.pool.exceptions
  被依赖文件: agenthub.access.api_gateway（被 M-A01 路由层 import）
[注意事项]
  注意1: 禁止在此处实现业务逻辑（仅符号聚合）
  注意2: ProcessPool 必须在 import 时立即初始化单例（DD-001 Singleton 模式约束）
  注意3: 模块导入顺序应避开循环依赖：先导出再实例化
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1 Python 风格指南
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B02 - 初始版本
[作者] DD-M-B02-20260603
[来源标注] [DD-001:FS-006 + MD-MCP-M-B02]
"""
from agenthub.application.pool.controllers import PoolController
from agenthub.application.pool.exceptions import PoolFullError, SpawnFailedError
from agenthub.application.pool.pool import ProcessPool

__all__ = [
    "ProcessPool",
    "PoolController",
    "PoolFullError",
    "SpawnFailedError",
]
