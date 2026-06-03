"""M-B03 Binding Engine 模块初始化文件.

[文件路径] src/agenthub/application/binding/__init__.py
[文件职责] 导出 Binding Engine 公共接口，初始化模块日志
[所属模块] M-B03
[关联设计规范] FS-MCP-V1.0-20260602#FS-007 / MD-MCP-V1.0-20260602#M-B03
[功能描述]
  功能1: 导出 BindingController / BindingService / BindingStrategy / ConfigGenerator
  功能2: 集中暴露模块级 DTO 契约 (BindForm / BindingResult / Mapping)
  功能3: 暴露领域异常 (BindingConflictError / ConfigLockTimeoutError)
[输入输出]
  输入: 无（模块加载期）
  输出: 公共符号包，供 API Gateway (M-A01) 路由挂载
[依赖关系]
  依赖文件: agenthub.application.binding.controllers、agenthub.application.binding.services、
            agenthub.application.binding.strategies、agenthub.application.binding.generators
  被依赖文件: agenthub.access.api_gateway（M-A01 在 router 注册时导入）
[注意事项]
  注意1: 禁止在此处执行任何 IO（DB / 文件系统 / fcntl）— 仅做符号聚合
  注意2: 严禁循环导入到下层业务模块，import 必须自上而下（controllers → services → strategies/generators）
  注意3: ConfigGenerator 是 L4 单一源（ADR-005），所有 mcp-config 文件生成必经此入口
  注意4: BindingEngine 通过 in-proc 调用 M-B02 pool.spawn（IC-004），禁止远程调用
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1（Python 风格）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B03 - 初版模块入口
[作者] DD-M-B03-20260603
[来源标注] [DD-001:FS-007 + MD-MCP-V1.0-20260602#M-B03]
"""
from __future__ import annotations

from agenthub.application.binding.controllers import BindingController
from agenthub.application.binding.exceptions import (
    BindingConflictError,
    ConfigLockTimeoutError,
)
from agenthub.application.binding.generators import ConfigGenerator
from agenthub.application.binding.schemas import (
    BindForm,
    BindingResult,
    Mapping,
)
from agenthub.application.binding.services import BindingService
from agenthub.application.binding.strategies import (
    BindingStrategy,
    CustomMappingStrategy,
    DefaultMappingStrategy,
)

__all__: list[str] = [
    # 控制器
    "BindingController",
    # 服务
    "BindingService",
    # 策略
    "BindingStrategy",
    "DefaultMappingStrategy",
    "CustomMappingStrategy",
    # 生成器
    "ConfigGenerator",
    # DTO
    "BindForm",
    "BindingResult",
    "Mapping",
    # 异常
    "BindingConflictError",
    "ConfigLockTimeoutError",
]
