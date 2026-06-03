"""M-C08 Name Transformer - 纯函数名空间转换器.

[文件路径] src/agenthub/infrastructure/naming/transformer.py
[文件职责] 6→8 字符 hex 命名转换与碰撞检测（升位）
[所属模块] M-C08（Name Transformer，来自 DD-001）
[关联设计规范] FS-017 / MD-MCP#M-C08 / IC-015 / API-270 / ADR-007 / BR-001~004
[功能描述]
  功能1: transform() —— 将原始 mcp 名称做 SHA256 → 截前 N 位 hex 的纯函数
  功能2: detect_collision() —— 检测新名是否与已存在集合冲突
  功能3: NameTransformer 静态类 —— 集中暴露上述两个静态方法
[输入输出]
  输入: 原始 mcp 名称（str），长度参数（int，可选），已存在名集合（frozenset[str]，可选）
  输出: 转换后的 hex 名称（str）或碰撞检测布尔值（bool）
[依赖关系]
  依赖文件: 仅依赖标准库 hashlib；零三方依赖
  被依赖文件: M-B03 Binding Engine（strategies.py / services.py）通过 NameTransformer 调用
[注意事项]
  注意1: 本模块为纯函数，禁止引入 IO/网络/全局可变状态（CI grep @pure 函数体检查）
  注意2: length 参数范围 [MIN_LENGTH=4, MAX_LENGTH=64]，超出抛 ValueError
  注意3: 碰撞自动升位由调用方决策；本模块仅提供 detect_collision 判定
  注意4: 必须用 @pure 装饰器 + @in_process_only 装饰器，避免被误发布为远程服务
  注意5: thread-safe（无状态）；frozen frozenset 共享即可
[代码风格] 遵循 CS-MCP §1 Python 风格指南 + §1.9 纯函数装饰器约束
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C08 - 初始文件框架（含完整注释，无业务代码）
[作者] DD-M-C08-20260603
[来源标注] [DD-001:FS-017/MD-MCP#M-C08/IC-015/API-270/ADR-007]
"""

from __future__ import annotations

import hashlib
from typing import Final

from agenthub.core.pure import pure, in_process_only  # [DD-001:CS-MCP §1.9]


# ---------------------------------------------------------------------------
# 常量定义（遵循 CS-MCP §1.1 UPPER_SNAKE_CASE）
# ---------------------------------------------------------------------------
NAMING_NAMESPACE_PREFIX: Final[str] = "mcp_"
"""MCP 命名空间前缀（保留，便于未来扩展多命名空间隔离）.

[来源标注] [DD-M推断:依据 M-B03 BR-001 mcp_ 前缀约定]
"""

DEFAULT_LENGTH: Final[int] = 6
"""默认输出长度：6 字符 hex（16^6 ≈ 16.7M 空间）.

[来源标注] [DD-001:MD-MCP#M-C08/IC-015 length 默认值]
"""

COLLISION_LENGTH: Final[int] = 8
"""碰撞升级长度：8 字符 hex（16^8 ≈ 4.3B 空间）.

[来源标注] [DD-001:MD-MCP#M-C08 "6→8 字符 hex 升级" / ADR-007]
"""

MIN_LENGTH: Final[int] = 4
"""最小允许长度（防御性下限，hashlib 截断安全）.

[来源标注] [DD-M推断:依据 hex 至少 4 字符可避免命名空间过密]
"""

MAX_LENGTH: Final[int] = 64
"""最大允许长度（防御性上限，hashlib SHA256 hex 总长）.

[来源标注] [DD-M推断:依据 hashlib.sha256.hexdigest() 返回 64 字符]
"""


# ---------------------------------------------------------------------------
# 异常类型（遵循 CS-MCP §1.6 自定义异常基类继承规范）
# ---------------------------------------------------------------------------
class NameTransformerError(Exception):
    """Name Transformer 模块异常基类.

    [类名] NameTransformerError
    [职责] M-C08 模块异常统一基类
    [关联设计规范] MD-MCP#M-C08
    [来源标注] [DD-001:CS-MCP §1.6 异常基类]
    """


class NameValidationError(NameTransformerError, ValueError):
    """输入参数非法.

    [类名] NameValidationError
    [职责] 报告入参校验失败（name 非 str/空串、length 越界）
    [关联设计规范] MD-MCP#M-C08 [异常处理]
    [异常处理]
      异常1: NameValidationError - name 为空或非字符串 / length 越界 [MIN, MAX]
    [来源标注] [DD-M推断:依据 IC-015 "无；输入校验异常上抛 ValueError"]
    """


class CollisionDetectedError(NameTransformerError):
    """碰撞自动升级失败（已达 MAX_LENGTH 仍冲突）.

    [类名] CollisionDetectedError
    [职责] 报告碰撞升级到最大长度后仍冲突
    [关联设计规范] MD-MCP#M-C08 [异常处理] / ADR-007
    [异常处理]
      异常1: CollisionDetectedError - 升位至 MAX_LENGTH 仍冲突（理论 16^64 空间）
    [来源标注] [DD-001:MD-MCP#M-C08 "CollisionDetected → 升 8 字符（ADR-007）"]
    """


# ---------------------------------------------------------------------------
# 核心纯函数
# ---------------------------------------------------------------------------
@pure
@in_process_only
def transform(name: str, length: int = DEFAULT_LENGTH) -> str:
    """名称 6→8 字符 hex 转换（碰撞自动升位由调用方循环处理）.

    [函数名] transform
    [职责] SHA256(name) → 截前 N 位 hex
    [关联接口契约] IC-015 / API-270
    [参数说明]
      参数1: name str 必填 原始 mcp 名称 校验规则: 非空字符串，已 strip
      参数2: length int 可选=DEFAULT_LENGTH(6) 输出长度 校验规则: [MIN_LENGTH, MAX_LENGTH]
    [返回值]
      类型: str
      描述: 长度 == length 的小写 hex 串
      特殊值: name="" 时抛 NameValidationError
    [错误码]
      错误码1: NameValidationError - 入参非法（类型/范围）
    [前置条件] 调用方需在调用前 strip 空白（避免 " mcp-x" vs "mcp-x" 视为不同）
    [后置条件] 不修改任何外部状态；同输入必返回同输出
    [并发安全] 纯函数线程安全
    [幂等性] 是；same input → same output；永久；返回相同 hex
    [性能约束] < 1ms（IC-015 性能约束）
    [来源标注] [DD-001:IC-015/API-270/MD-MCP#M-C08 + CS-MCP §1.9 @pure 约束]

    Example:
        >>> transform("mcp-foo")
        'a1b2c3'   # 6 字符 hex 示例
    """
    # ---- 入参校验 ----
    if not isinstance(name, str):
        raise NameValidationError(f"name must be str, got {type(name).__name__}")
    if not name:
        raise NameValidationError("name must be non-empty string")
    if not isinstance(length, int) or isinstance(length, bool):
        raise NameValidationError(f"length must be int, got {type(length).__name__}")
    if length < MIN_LENGTH or length > MAX_LENGTH:
        raise NameValidationError(
            f"length must be in [{MIN_LENGTH}, {MAX_LENGTH}], got {length}"
        )

    # ---- 纯计算：SHA256 → 截前 N 位 hex（小写） ----
    digest: str = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return digest[:length]


@pure
@in_process_only
def detect_collision(existing: frozenset[str], new: str) -> bool:
    """碰撞检测 —— 判定 new 是否与 existing 集合冲突.

    [函数名] detect_collision
    [职责] 判定转换后名称是否已被占用
    [关联接口契约] IC-015 / API-270
    [参数说明]
      参数1: existing frozenset[str] 必填 已存在名称集合 校验规则: 元素均为 str
      参数2: new str 必填 待检测的新名称 校验规则: 非空
    [返回值]
      类型: bool
      描述: True 表示 new ∈ existing（碰撞），False 表示无冲突
      特殊值: 空 existing 永远返回 False
    [错误码]
      错误码1: NameValidationError - existing 元素含非 str
    [前置条件] 调用方持有现有已分配名集合（典型来源：PG mcp_naming 表 + 内存缓存）
    [后置条件] 不修改 existing（frozenset 不可变）
    [并发安全] 纯函数线程安全（依赖 frozenset 不可变）
    [幂等性] 是；same (existing, new) → same result
    [性能约束] O(len(existing))，< 1ms（IC-015 性能约束）
    [来源标注] [DD-001:IC-015/MD-MCP#M-C08 detect_collision 签名]

    Example:
        >>> detect_collision(frozenset({"a1b2c3", "d4e5f6"}), "a1b2c3")
        True
    """
    if not isinstance(existing, frozenset):
        raise NameValidationError("existing must be frozenset[str]")
    if not isinstance(new, str):
        raise NameValidationError(f"new must be str, got {type(new).__name__}")
    if not new:
        raise NameValidationError("new must be non-empty string")
    return new in existing


# ---------------------------------------------------------------------------
# 静态类容器（命名空间聚合；非业务类，仅为 API 易用性）
# ---------------------------------------------------------------------------
class NameTransformer:
    """Name Transformer 静态类容器 —— 纯函数命名空间.

    [类名] NameTransformer
    [职责] 集中暴露 transform / detect_collision 静态方法（API 易用）
    [关联设计规范] MD-MCP#M-C08 "NameTransformer - 纯函数容器"
    [属性]
      属性1: 无实例属性（静态类，禁实例化）
    [方法列表]
      方法1: transform(name, length=6) → str - SHA256 截位转换
      方法2: detect_collision(existing, new) → bool - 碰撞检测
    [状态机] 无
    [异常处理]
      异常1: NameValidationError - 入参校验失败（透传自纯函数）
      异常2: CollisionDetectedError - 升位失败（由调用方决定是否捕获）
    [来源标注] [DD-001:MD-MCP#M-C08 "NameTransformer - 纯函数容器 - {} - @staticmethod transform / detect_collision"]

    本类不持有任何状态；其存在仅为：
      1) 与 MD-MCP#M-C08 类设计一一对应（降低 DD-S 骨架搭建认知负担）
      2) 提供"模块门面"式静态方法访问（避免调用方频繁 import 函数名）
    """

    __slots__ = ()  # 禁止实例属性，强制纯静态语义

    @staticmethod
    @pure
    @in_process_only
    def transform(name: str, length: int = DEFAULT_LENGTH) -> str:
        """静态方法包装 —— 见 transform() 函数级注释.

        [来源标注] [DD-001:MD-MCP#M-C08 @staticmethod transform]
        """
        return transform(name, length)

    @staticmethod
    @pure
    @in_process_only
    def detect_collision(existing: frozenset[str], new: str) -> bool:
        """静态方法包装 —— 见 detect_collision() 函数级注释.

        [来源标注] [DD-001:MD-MCP#M-C08 @staticmethod detect_collision]
        """
        return detect_collision(existing, new)
