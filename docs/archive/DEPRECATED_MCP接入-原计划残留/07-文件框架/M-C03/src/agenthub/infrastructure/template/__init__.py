"""M-C03 Template Engine package.

[文件路径] src/agenthub/infrastructure/template/__init__.py
[文件职责] Template Engine 模块初始化与公共接口导出
[所属模块] M-C03（来自DD-001）
[关联设计规范] FS-012 / MD-MCP-V1.0-20260602.md#M-C03 / IC-010
[功能描述]
  功能1: 导出 TemplateConfig (Value Object) 与 TemplateMerger (纯函数容器) 公共符号
  功能2: 暴露 merge / validate 顶层函数便于调用方直接使用
  功能3: 暴露 __all__ 白名单以约束 from package import * 的范围
[输入输出]
  输入: 无（仅在被 import 时生效）
  输出: 暴露符号：TemplateConfig / TemplateMerger / merge / validate / TemplateValidationError / DepthLimitError
[依赖关系]
  依赖文件: agenthub.infrastructure.template.merger / agenthub.infrastructure.template.schema
  被依赖文件: M-C03 外部调用方（如 M-B05 提交前模板预处理）
[注意事项]
  注意1: 本模块为纯函数 in-proc 模块，禁止被发布为 RPC；调用方应同步 @in_process_only 装饰
  注意2: 任何对 merger / schema 内部状态的访问都应通过本 __init__ 暴露的公共符号
  注意3: __all__ 必须显式声明，遵循 ruff F401 规则
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1（Python 风格指南）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-12 - 初版文件框架注释（M-C03 详细设计）
[作者] DD-M-12-20260602
[来源标注] [DD-001:FS-012/MD-MCP-V1.0-20260602.md#M-C03/IC-010]
"""

# 仅暴露公共 Value Object、纯函数容器与领域异常；不导出内部 helper
from agenthub.infrastructure.template.merger import TemplateMerger
from agenthub.infrastructure.template.schema import (
    DepthLimitError,
    TemplateConfig,
    TemplateValidationError,
    ValidationResult,
    merge,
    validate,
)

__all__: list[str] = [
    "DepthLimitError",
    "TemplateConfig",
    "TemplateMerger",
    "TemplateValidationError",
    "ValidationResult",
    "merge",
    "validate",
]
