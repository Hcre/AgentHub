"""M-B04 Approval Engine 模块初始化.

[文件路径] src/agenthub/application/approval/__init__.py
[文件职责] 模块初始化，对外导出 Approval 模块的公共接口
[所属模块] M-B04
[关联设计规范] FS-008 / MD:M-B04
[功能描述]
  功能1: 显式导出 ApprovalService（业务编排入口）
  功能2: 显式导出 ArgsHasher（系统级公共哈希，ADR-006 单一来源）
  功能3: 导出领域异常类，便于上层 import
[输入输出]
  输入: 无（Python 包初始化）
  输出: 公共符号集（__all__）
[依赖关系]
  依赖文件: services / hasher / exceptions / schemas
  被依赖文件: agenthub.access.api_gateway / agenthub.application.create / 其他需要审批检查的上层模块
[注意事项]
  注意1: 禁止在此处执行 IO 副作用（仅声明导出）
  注意2: ArgsHasher 是全系统统一哈希函数（ADR-006），必须从本包导出，禁止其他模块重复实现
[代码风格] 遵循 CS §1.1 (PascalCase 类) / §1.5 (导入分段)
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B04 - 初始框架（仅注释，无业务实现）
[作者] DD-M-B04-20260603
[来源标注] [DD-001:FS-008 + ADR-006]
"""

from __future__ import annotations

# [DD-M-B04 推断: 显式 __all__ 可避免 from approval import * 误导出内部符号]
# 由 DD-S 在骨架阶段补充实际 import 语句
__all__: list[str] = [
    "ApprovalService",       # services.ApprovalService
    "ArgsHasher",            # hasher.ArgsHasher
    "AllowlistCache",        # allowlist.AllowlistCache
    "ApprovalError",         # exceptions.ApprovalError (基类)
    "ApprovalDBUnavailable", # exceptions
    "ApprovalHashMismatch",  # exceptions
    "ApprovalDuplicate",     # exceptions
    "ApprovalNotFound",      # exceptions
    "ApprovalPermissionDenied",
    "ApprovalReplay",
    "Decision",              # schemas.Decision (enum)
    "CheckRequest",          # schemas
    "DecideRequest",         # schemas
]
