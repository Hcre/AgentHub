"""M-C03 Template Engine merger module.

[文件路径] src/agenthub/infrastructure/template/merger.py
[文件职责] 模板深合并 + 标量覆盖核心（基于 TS-030 jsondiff，纯函数 in-proc）
[所属模块] M-C03（来自DD-001）
[关联设计规范] FS-012 / MD-MCP-V1.0-20260602.md#M-C03 / IC-010
[功能描述]
  功能1: 提供 TemplateMerger 纯函数容器：merge / validate（[AR:TS-030 + AC:AG-012]）
  功能2: 实现深合并：递归合并 dict + list 拼接 + 标量覆盖规则
  功能3: 调用 jsondiff 生成 diff patch 列表，作为返回值的一部分
  功能4: 强制 in-proc：装饰器 @pure / @in_process_only 标记
[输入输出]
  输入: base (dict) / override (dict) / schema (dict)
  输出: merged (dict) / diff (list[Patch]) / ValidationResult
[依赖关系]
  依赖文件: agenthub.infrastructure.template.schema（类型 + 异常）
  被依赖文件: agenthub.infrastructure.template.__init__ / M-B05 等调用方
[注意事项]
  注意1: merge / validate 必须是纯函数：禁 IO/全局状态/网络/文件（[DD-001:DD洞察-2]）
  注意2: 标量覆盖规则遵循 jsondiff 默认行为：list 按索引覆盖；如需 list 拼接，使用 list_merge_strategy 参数
  注意3: max_depth 默认 10，触发循环引用时抛 DepthLimitError
  注意4: 性能约束 < 5ms（[IC-010:性能约束]），禁止在内部调用任何 IO 操作
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1 + §1.9 纯函数装饰器约束
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-12 - 初版文件框架注释（M-C03 详细设计）
[作者] DD-M-12-20260602
[来源标注] [DD-001:FS-012/MD-MCP-V1.0-20260602.md#M-C03/IC-010 + DD-001:DD洞察-2]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from agenthub.core.pure import in_process_only, pure  # type: ignore[import-not-found]
from agenthub.infrastructure.template.schema import (
    DepthLimitError,
    TemplateConfig,
    TemplateValidationError,
    ValidationResult,
    validate as _validate,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


# 模块级常量（CS 1.1 命名：UPPER_SNAKE_CASE）
DEFAULT_MAX_DEPTH: Final[int] = 10
DEFAULT_LIST_MERGE_STRATEGY: Final[str] = "override"  # "override" | "concat" | "unique_concat"


class TemplateMerger:
    """模板合并纯函数容器（Value Object 风格、无状态、无 IO）.

    [类名] TemplateMerger
    [职责] 集中承载 M-C03 的纯函数，强制 in-proc 调用
    [关联设计规范] MD-MCP-V1.0-20260602.md#M-C03
    [属性]
      属性1: MAX_DEPTH int 类常量 递归深度上限（防止循环引用）
      属性2: LIST_MERGE_STRATEGY str 类常量 list 默认合并策略
    [方法列表]
      方法1: merge(base, override, max_depth, list_merge_strategy) -> dict - 深合并入口
      方法2: merge_with_diff(base, override, ...) -> tuple[dict, list[Patch]] - 合并并返回 diff
      方法3: validate(merged, schema) -> ValidationResult - 调 schema.validate
    [状态机] 无（纯函数容器）
    [异常处理]
      异常1: TemplateValidationError - schema 校验失败（M-C03 子模块 validate/ 抛出）
      异常2: DepthLimitError - 递归深度 > 10，循环引用
    [来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-C03 + DD-M推断:Value Object 容器化]
    """

    MAX_DEPTH: Final[int] = DEFAULT_MAX_DEPTH
    LIST_MERGE_STRATEGY: Final[str] = DEFAULT_LIST_MERGE_STRATEGY

    @staticmethod
    @pure
    @in_process_only
    def merge(
        base: Mapping[str, object],
        override: Mapping[str, object],
        max_depth: int = DEFAULT_MAX_DEPTH,
        list_merge_strategy: str = DEFAULT_LIST_MERGE_STRATEGY,
    ) -> dict[str, object]:
        """深合并 base 与 override，返回新 dict（不修改入参）.

        [函数名] TemplateMerger.merge
        [职责] 深合并入口，标量覆盖 + dict 递归 + list 按策略合并
        [关联接口契约] IC-010
        [参数说明]
          参数1: base Mapping[str, object] 必填 模板基底；不可变入参
                 校验规则: 必须可 JSON 序列化；最大深度 10
          参数2: override Mapping[str, object] 必填 覆盖层
                 校验规则: 同 base
          参数3: max_depth int 可选 默认 10 递归深度上限
                 校验规则: 1 <= max_depth <= 50
          参数4: list_merge_strategy str 可选 默认 "override"
                 校验规则: ∈ {"override","concat","unique_concat"}
        [返回值]
          类型: dict[str, object]
          描述: 深合并后的新 dict（不修改入参）
          特殊值: 输入空 dict 时返回空 dict
        [错误码]
          错误码1: TEMPLATE_CIRCULAR_REF 422 递归深度超限（IC-010 错误码）
          错误码2: TEMPLATE_SCHEMA_VIOLATION 422 合并结果不合法 schema
        [前置条件] base / override 必须可 JSON 序列化
        [后置条件] 返回新 dict；入参对象未被修改
        [并发安全] 纯函数线程安全（无共享状态）
        [幂等性] 是；同输入永远返回同结果（[IC-010:幂等性]）
        [性能约束] < 5ms（[IC-010:性能约束]）
        [示例]
          ```
          result = TemplateMerger.merge({"a": 1}, {"b": 2})
          # -> {"a": 1, "b": 2}
          ```
        [来源标注] [DD-001:IC-010 + AR:TS-030]
        """
        # 业务实现由开发工程师在 DD-S 之后填充；此处仅注释
        raise NotImplementedError("M-C03 merge 业务代码待开发工程师实现")

    @staticmethod
    @pure
    @in_process_only
    def merge_with_diff(
        base: Mapping[str, object],
        override: Mapping[str, object],
        max_depth: int = DEFAULT_MAX_DEPTH,
        list_merge_strategy: str = DEFAULT_LIST_MERGE_STRATEGY,
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        """深合并并产出 diff patch 列表（jsondiff Patch 协议）.

        [函数名] TemplateMerger.merge_with_diff
        [职责] 合并 + 同时返回结构化 diff 便于审计与回放
        [关联接口契约] IC-010
        [参数说明]
          参数1: base Mapping[str, object] 必填 基底
          参数2: override Mapping[str, object] 必填 覆盖
          参数3: max_depth int 可选 默认 10
          参数4: list_merge_strategy str 可选 默认 "override"
        [返回值]
          类型: tuple[dict[str, object], list[dict[str, object]]]
          描述: (merged, diff) - diff 每项为 {"op": str, "path": str, "value": Any}
          特殊值: base == override 时 diff 为空列表
        [错误码]
          错误码1: TEMPLATE_CIRCULAR_REF 422
          错误码2: TEMPLATE_SCHEMA_VIOLATION 422
        [前置条件] 同 merge
        [后置条件] 返回新对象；diff 长度 > 0 当且仅当存在覆盖
        [并发安全] 纯函数线程安全
        [幂等性] 是
        [性能约束] < 5ms（[IC-010]）
        [来源标注] [DD-001:IC-010 + AR:TS-030]
        """
        # 业务实现由开发工程师在 DD-S 之后填充；此处仅注释
        raise NotImplementedError("M-C03 merge_with_diff 业务代码待开发工程师实现")

    @staticmethod
    @pure
    @in_process_only
    def validate(merged: Mapping[str, object], schema: Mapping[str, object]) -> ValidationResult:
        """对合并结果做 schema 校验（委托给 schema 模块的 validate）.

        [函数名] TemplateMerger.validate
        [职责] 统一入口：调用方使用 TemplateMerger.validate 而非直接 import schema.validate
        [关联接口契约] IC-010
        [参数说明]
          参数1: merged Mapping[str, object] 必填 合并后结果
                 校验规则: 必须可 JSON 序列化
          参数2: schema Mapping[str, object] 必填 JSON Schema (Draft 2020-12)
                 校验规则: 顶层必须为 dict；$id 必填
        [返回值]
          类型: ValidationResult
          描述: {valid: bool, errors: list[ValidationErrorItem]}
          特殊值: 校验通过时 errors 为空列表
        [错误码]
          错误码1: TEMPLATE_SCHEMA_VIOLATION 422 详见 ValidationResult.errors
        [前置条件] schema 满足 JSON Schema 2020-12
        [后置条件] 无副作用
        [并发安全] 纯函数线程安全
        [幂等性] 是
        [性能约束] < 5ms（与 merge 同等量级）
        [来源标注] [DD-001:IC-010 + AR:TS-030 + CS-MCP-V1.0-20260602 §7 JSON Schema]
        """
        # 业务实现由开发工程师在 DD-S 之后填充；此处仅注释
        return _validate(merged, schema)


# 顶层便捷函数（[DD-M推断:与 IC-010 函数签名 merge(base, override) 对齐]）
@pure
@in_process_only
def merge(
    base: Mapping[str, object],
    override: Mapping[str, object],
    max_depth: int = DEFAULT_MAX_DEPTH,
    list_merge_strategy: str = DEFAULT_LIST_MERGE_STRATEGY,
) -> dict[str, object]:
    """顶层 merge 函数（[IC-010] 顶层函数签名）.

    [函数名] merge
    [职责] 提供模块级便捷调用，语义等价于 TemplateMerger.merge
    [关联接口契约] IC-010
    [参数说明] 同 TemplateMerger.merge
    [返回值] 同 TemplateMerger.merge
    [错误码] 同 TemplateMerger.merge
    [前置条件] 同 TemplateMerger.merge
    [后置条件] 同 TemplateMerger.merge
    [并发安全] 纯函数线程安全
    [幂等性] 是；同输入 → 同输出（[IC-010:幂等性]）
    [性能约束] < 5ms（[IC-010:性能约束]）
    [示例]
      ```
      from agenthub.infrastructure.template import merge
      out = merge({"a": 1}, {"b": 2})
      ```
    [来源标注] [DD-001:IC-010 + DD-M推断:顶层便捷函数]
    """
    return TemplateMerger.merge(base, override, max_depth, list_merge_strategy)


@pure
@in_process_only
def validate(
    merged: Mapping[str, object],
    schema: Mapping[str, object],
) -> ValidationResult:
    """顶层 validate 函数（[IC-010] 顶层函数签名）.

    [函数名] validate
    [职责] 提供模块级便捷调用，语义等价于 TemplateMerger.validate
    [关联接口契约] IC-010
    [参数说明] 同 TemplateMerger.validate
    [返回值] 同 TemplateMerger.validate
    [错误码] 同 TemplateMerger.validate
    [前置条件] 同 TemplateMerger.validate
    [后置条件] 同 TemplateMerger.validate
    [并发安全] 纯函数线程安全
    [幂等性] 是
    [性能约束] < 5ms
    [来源标注] [DD-001:IC-010 + DD-M推断:顶层便捷函数]
    """
    return TemplateMerger.validate(merged, schema)


# 模块级不可变配置占位（[DD-M推断:为后续配置注入预留，例如支持不同 list 合并策略的 Profile]）
DEFAULT_TEMPLATE_PROFILE: Final[TemplateConfig] = TemplateConfig(
    base={},
    override={},
    max_depth=DEFAULT_MAX_DEPTH,
    list_merge_strategy=DEFAULT_LIST_MERGE_STRATEGY,
)


__all__: list[str] = [
    "DEFAULT_LIST_MERGE_STRATEGY",
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_TEMPLATE_PROFILE",
    "DepthLimitError",
    "TemplateConfig",
    "TemplateMerger",
    "TemplateValidationError",
    "ValidationResult",
    "merge",
    "validate",
]
