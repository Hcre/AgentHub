"""M-B03 Binding Engine 领域异常.

[文件路径] src/agenthub/application/binding/exceptions.py
[文件职责] 定义 Binding Engine 业务异常（继承 core.exceptions 基类）
[所属模块] M-B03
[关联设计规范] EX-MCP-V1.0-20260602#EX-011 + SEC:SEC-011
[功能描述]
  功能1: BindingConflictError (409) 重复绑定
  功能2: ConfigLockTimeoutError (503) fcntl 锁竞争
  功能3: PathTraversalError (400) 路径遍历检测
  功能4: MappingValidationError (422) mapping 校验失败
[输入输出]
  输入: 异常参数
  输出: AgentHubError 子类
[依赖关系]
  依赖文件: agenthub.core.exceptions
  被依赖文件: agenthub.application.binding.services / strategies / generators / controllers
[注意事项]
  注意1: 所有异常必须继承 AgentHubError（统一响应格式）
  注意2: code / http_status 必须在类级常量定义
  注意3: 不允许吞异常（ruff E722 检查）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B03 - 初版异常
[作者] DD-M-B03-20260603
[来源标注] [DD-001:EX-011 + MD-MCP-V1.0-20260602#M-B03]
"""
from __future__ import annotations

from agenthub.core.exceptions import AgentHubError, BusinessError, SecurityError


class BindingConflictError(BusinessError):
    """绑定冲突（已存在）.

    [类名] BindingConflictError
    [职责] 表示 (ws_id, mcp_id) 已绑定
    [关联设计规范] EX-MCP-V1.0-20260602#EX-011 + MD-MCP-V1.0-20260602#M-B03
    [属性]
      属性1: code str = "BINDING_CONFLICT"
      属性2: http_status int = 409
    [来源标注] [DD-001:EX-011]
    """

    code: str = "BINDING_CONFLICT"
    http_status: int = 409


class ConfigLockTimeoutError(AgentHubError):
    """mcp-config 文件锁竞争超时.

    [类名] ConfigLockTimeoutError
    [职责] 表示 fcntl 锁等待超时（含重试 1 次后）
    [关联设计规范] EX-MCP-V1.0-20260602#EX-011 + SEC:SEC-011
    [属性]
      属性1: code str = "CONFIG_LOCK_TIMEOUT"
      属性2: http_status int = 503
    [来源标注] [DD-001:EX-011 + SEC:SEC-011]
    """

    code: str = "CONFIG_LOCK_TIMEOUT"
    http_status: int = 503


class PathTraversalError(SecurityError):
    """路径遍历检测命中.

    [类名] PathTraversalError
    [职责] 表示 mapping 含 .. / 绝对路径 / NUL
    [关联设计规范] SEC:SEC-011 + TD:BR-001~004
    [属性]
      属性1: code str = "PATH_TRAVERSAL"
      属性2: http_status int = 400
    [来源标注] [DD-001:SEC:SEC-011]
    """

    code: str = "PATH_TRAVERSAL"
    http_status: int = 400


class MappingValidationError(BusinessError):
    """mapping 校验失败.

    [类名] MappingValidationError
    [职责] 表示 mapping 结构非法
    [关联设计规范] MD-MCP-V1.0-20260602#M-B03
    [属性]
      属性1: code str = "MAPPING_VALIDATION_FAILED"
      属性2: http_status int = 422
    [来源标注] [DD-M推断:与 EX-011 区分的轻量校验异常]
    """

    code: str = "MAPPING_VALIDATION_FAILED"
    http_status: int = 422


__all__ = [
    "BindingConflictError",
    "ConfigLockTimeoutError",
    "PathTraversalError",
    "MappingValidationError",
]
