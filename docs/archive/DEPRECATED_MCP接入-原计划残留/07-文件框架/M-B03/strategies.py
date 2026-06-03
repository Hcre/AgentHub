"""M-B03 Binding Engine 绑定策略（Strategy 模式）.

[文件路径] src/agenthub/application/binding/strategies.py
[文件职责] 提供 BindingStrategy 抽象 + Default / Custom 两种实现
[所属模块] M-B03
[关联设计规范] MD-MCP-V1.0-20260602#M-B03 / TD:BR-001~004 / ADR-007
[功能描述]
  功能1: BindingStrategy 抽象接口定义 transform() 与 default_mapping()
  功能2: DefaultMappingStrategy 默认 1:1 映射 + 内嵌 M-C08 命名转换
  功能3: CustomMappingStrategy 自定义 alias 映射（含路径遍历检测）
[输入输出]
  输入: mapping dict / name str
  输出: transformed dict / str
[依赖关系]
  依赖文件: agenthub.infrastructure.naming.transformer（内嵌 M-C08）、
            agenthub.application.binding.exceptions
  被依赖文件: agenthub.application.binding.services
[注意事项]
  注意1: Strategy 必须是无状态 pure function 容器（soul 4.8 约束）
  注意2: CustomMappingStrategy 必须拒绝路径遍历（.. / 绝对路径 / NUL 字节）
  注意3: 命名转换统一使用 M-C08 NameTransformer（6→8 hex，碰撞自动升位）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B03 - 初版策略层
[作者] DD-M-B03-20260603
[来源标注] [DD-001:FS-007 + MD-MCP-V1.0-20260602#M-B03 + TD:BR-001~004]
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from agenthub.application.binding.exceptions import PathTraversalError
from agenthub.core.logging import get_logger
from agenthub.infrastructure.naming.transformer import NameTransformer

if TYPE_CHECKING:
    from agenthub.application.binding.schemas import Mapping

log = get_logger(__name__)


class BindingStrategy(ABC):
    """绑定策略抽象基类.

    [类名] BindingStrategy
    [职责] 定义名称映射转换的抽象接口
    [关联设计规范] MD-MCP-V1.0-20260602#M-B03
    [属性] (无状态)
    [方法列表]
      方法1: transform(mapping) -> Mapping - 转换 mapping
      方法2: default_mapping() -> Mapping - 生成默认 mapping
    [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03]
    """

    @abstractmethod
    def transform(self, mapping: "Mapping") -> "Mapping":
        """转换 mapping.

        [函数名] transform
        [职责] 抽象方法：将用户提供的 mapping 转换为最终 mcp-config 写入的 mapping
        [参数说明]
          参数1: mapping Mapping 必填 用户原始 mapping
        [返回值]
          类型: Mapping
          描述: 转换后的 mapping
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03]
        """
        raise NotImplementedError

    @abstractmethod
    def default_mapping(self) -> "Mapping":
        """生成默认 mapping.

        [函数名] default_mapping
        [职责] 抽象方法：当用户未提供 mapping 时返回默认映射
        [返回值]
          类型: Mapping
          描述: 默认 mapping
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03]
        """
        raise NotImplementedError


class DefaultMappingStrategy(BindingStrategy):
    """默认 1:1 映射策略.

    [类名] DefaultMappingStrategy
    [职责] 不做 alias 转换，仅做命名规范化（6→8 hex）
    [关联设计规范] MD-MCP-V1.0-20260602#M-B03 + ADR-007
    [属性] (无)
    [方法列表]
      方法1: transform(mapping) -> Mapping - 对每个 key 跑 M-C08 NameTransformer
      方法2: default_mapping() -> Mapping - 返回空 dict
    [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03]
    """

    def __init__(self) -> None:
        self._transformer = NameTransformer()

    def transform(self, mapping: "Mapping") -> "Mapping":
        """1:1 + 命名规范化.

        [函数名] transform
        [职责] 对 mapping 的 key 走 M-C08 6→8 hex 转换
        [参数说明]
          参数1: mapping Mapping 必填
        [返回值]
          类型: Mapping
          描述: 转换后 mapping
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03 + ADR-007]
        """
        # [DD-M推断:仅规范化 key；value 保持原样（用户已指定 server URL）]
        result: dict[str, str] = {}
        for key, value in mapping.items():
            normalized_key = self._transformer.transform(key)
            result[normalized_key] = value
        return result

    def default_mapping(self) -> "Mapping":
        """返回空 dict（1:1 不需别名）.

        [函数名] default_mapping
        [职责] 提供默认空 mapping
        [返回值]
          类型: Mapping
          描述: 空 dict
        [来源标注] [DD-M推断:基于 ADR-005 单一源]
        """
        return {}


class CustomMappingStrategy(BindingStrategy):
    """自定义 alias 映射策略.

    [类名] CustomMappingStrategy
    [职责] 支持用户自定义 alias + 路径遍历检测
    [关联设计规范] MD-MCP-V1.0-20260602#M-B03 + TD:BR-001~004
    [属性] (无)
    [方法列表]
      方法1: transform(mapping) -> Mapping - 校验 + 规范化
      方法2: default_mapping() -> Mapping - 返回空 dict
    [异常处理]
      异常1: PathTraversalError - 检测到 .. / 绝对路径 / NUL 字节
    [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03]
    """

    _FORBIDDEN_CHARS = ("..", "/", "\\", "\x00")
    _MAX_KEY_LEN = 128
    _MAX_VALUE_LEN = 512

    def __init__(self) -> None:
        self._transformer = NameTransformer()

    def transform(self, mapping: "Mapping") -> "Mapping":
        """校验 + 规范化.

        [函数名] transform
        [职责] 检测路径遍历 + 长度限制 + 命名规范化
        [参数说明]
          参数1: mapping Mapping 必填 用户自定义 alias
        [返回值]
          类型: Mapping
          描述: 安全映射
        [错误码]
          错误码1: PATH_TRAVERSAL 400 - 检测到 .. 或 / 或 NUL
          错误码2: MAPPING_TOO_LONG 400 - 键/值超长
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03 + SEC:SEC-011]
        """
        result: dict[str, str] = {}
        for key, value in mapping.items():
            self._validate_key(key)
            self._validate_value(value)
            normalized_key = self._transformer.transform(key)
            result[normalized_key] = value
        return result

    def default_mapping(self) -> "Mapping":
        """返回空 dict.

        [函数名] default_mapping
        [职责] 提供默认空 mapping
        [来源标注] [DD-M推断:与 DefaultMappingStrategy 行为一致]
        """
        return {}

    @classmethod
    def _validate_key(cls, key: str) -> None:
        """校验 key 安全性.

        [函数名] _validate_key
        [职责] 检测路径遍历字符
        [参数说明]
          参数1: key str 必填
        [异常处理]
          异常1: PathTraversalError - 含 .. / / / \\ / NUL
          异常2: ValueError - key 超长
        [来源标注] [DD-001:SEC:SEC-011 + TD:BR-001~004]
        """
        if len(key) > cls._MAX_KEY_LEN:
            raise ValueError(f"mapping key too long: {len(key)} > {cls._MAX_KEY_LEN}")
        for forbidden in cls._FORBIDDEN_CHARS:
            if forbidden in key:
                raise PathTraversalError(f"forbidden pattern in mapping key: {forbidden!r}")

    @classmethod
    def _validate_value(cls, value: str) -> None:
        """校验 value 安全性.

        [函数名] _validate_value
        [职责] 检测路径遍历 + 长度
        [参数说明]
          参数1: value str 必填
        [异常处理]
          异常1: PathTraversalError
          异常2: ValueError
        [来源标注] [DD-001:SEC:SEC-011]
        """
        if len(value) > cls._MAX_VALUE_LEN:
            raise ValueError(f"mapping value too long: {len(value)} > {cls._MAX_VALUE_LEN}")
        for forbidden in cls._FORBIDDEN_CHARS:
            if forbidden in value:
                raise PathTraversalError(f"forbidden pattern in mapping value: {forbidden!r}")


__all__ = [
    "BindingStrategy",
    "DefaultMappingStrategy",
    "CustomMappingStrategy",
]
