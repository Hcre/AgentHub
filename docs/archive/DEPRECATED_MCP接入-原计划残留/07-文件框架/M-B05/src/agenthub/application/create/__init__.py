"""
[文件路径] src/agenthub/application/create/__init__.py
[文件职责] M-B05 MCP Create 模块初始化，导出公共 Saga 接口
[所属模块] M-B05
[关联设计规范] MD-MCP-V1.0-20260602 #M-B05 + FS-MCP-V1.0-20260602 #FS-009 + IC-MCP-V1.0-20260602 #IC-007
[功能描述]
  功能1: 导出 CreateController / SagaOrchestrator / SagaStep 等公共类
  功能2: 暴露模块版本号与导出白名单
[输入输出]
  输入: 无
  输出: 公共符号（CreateController / SagaOrchestrator / SagaStep / SubmitForm / SagaResult）
[依赖关系]
  依赖文件: agenthub.application.create.controllers / orchestrator / steps / compensator
  被依赖文件: agenthub.access.api_gateway（M-A01 路由分发到 CreateController）
[注意事项]
  注意1: 仅导出公共符号；内部 Step 子类建议从 steps 包显式导入
  注意2: 本模块为应用层（Layer 2），禁止依赖 access 层（[FS-MCP §0]）
[代码风格] 遵循CS-MCP-V1.0-20260602（4空格、Google docstring、PEP 484 类型注解）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B05 - 初始创建文件框架
[作者] DD-M-B05-20260603
[来源标注] [DD-001:FS-MCP/FS-009 + MD-MCP/M-B05]
"""
# 注释占位：模块初始化与公共符号导出
# 实施时由 DD-S 填充：
# from agenthub.application.create.controllers import CreateController
# from agenthub.application.create.orchestrator import SagaOrchestrator, SagaStep
# from agenthub.application.create.schemas import SubmitForm, SagaResult, SagaContext
#
# __all__ = [
#     "CreateController",
#     "SagaOrchestrator",
#     "SagaStep",
#     "SubmitForm",
#     "SagaResult",
#     "SagaContext",
#     "MODULE_VERSION",
# ]
# MODULE_VERSION = "1.0.0"
