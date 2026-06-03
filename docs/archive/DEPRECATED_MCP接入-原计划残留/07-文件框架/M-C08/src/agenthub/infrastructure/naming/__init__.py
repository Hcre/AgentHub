"""M-C08 Name Transformer - 模块初始化.

本模块实现 M-B03 绑定引擎所需的核心名空间映射能力。
- transform(): 名称 6 字符 hex → 必要时升 8 字符 hex（碰撞时）
- detect_collision(): 碰撞检测（传入已存在集合）
设计模式：Pure Function（无 IO / 无状态 / 线程安全）。
依赖：Python 标准库 hashlib；零三方依赖。
[来源标注] [DD-001:FS-017/MD-MCP#M-C08/IC-015 + CS-MCP §1.9 @pure 装饰器]
"""

from agenthub.infrastructure.naming.transformer import (
    NameTransformer,
    transform,
    detect_collision,
    CollisionDetectedError,
    NameValidationError,
    NAMING_NAMESPACE_PREFIX,
    DEFAULT_LENGTH,
    COLLISION_LENGTH,
    MIN_LENGTH,
    MAX_LENGTH,
)

__all__ = [
    "NameTransformer",
    "transform",
    "detect_collision",
    "CollisionDetectedError",
    "NameValidationError",
    "NAMING_NAMESPACE_PREFIX",
    "DEFAULT_LENGTH",
    "COLLISION_LENGTH",
    "MIN_LENGTH",
    "MAX_LENGTH",
]
