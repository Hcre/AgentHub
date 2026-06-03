"""M-C03 Template Engine schema module.

[文件路径] src/agenthub/infrastructure/template/schema.py
[文件职责] TemplateConfig Value Object + schema 校验（pydantic 不可变模型）
[所属模块] M-C03（来自DD-001）
[关联设计规范] FS-012 / MD-MCP-V1.0-20260602.md#M-C03 / IC-010
[功能描述]
  功能1: 定义 TemplateConfig（frozen=True）Value Object，承载 base / override / 合并策略
  功能2: 定义 ValidationResult / ValidationErrorItem 数据类
  功能3: 定义领域异常 TemplateValidationError / DepthLimitError
  功能4: 提供顶层 validate 函数调用 jsonschema Draft 2020-12
[输入输出]
  输入: TemplateConfig 实例 / 任意 dict + JSON Schema
  输出: ValidationResult / 抛出 TemplateValidationError / DepthLimitError
[依赖关系]
  依赖文件: agenthub.core.exceptions（领域异常基类 AgentHubError）
  被依赖文件: agenthub.infrastructure.template.merger / agenthub.infrastructure.template.__init__
[注意事项]
  注意1: TemplateConfig 不可变（frozen=True），任何变更需通过 model_dump + 新建实例
  注意2: 校验失败统一抛 TemplateValidationError，错误细节由 errors 列表承载
  注意3: 递归深度校验由 merger 层负责；本层仅做 schema 字段校验
  注意4: JSON Schema 须遵循 Draft 2020-12（[CS-MCP-V1.0-20260602 §7]）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-12 - 初版文件框架注释（M-C03 详细设计）
[作者] DD-M-12-20260602
[来源标注] [DD-001:FS-012/MD-MCP-V1.0-20260602.md#M-C03 + DD-M推断:Value Object 设计]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from agenthub.core.exceptions import AgentHubError  # type: ignore[import-not-found]

if TYPE_CHECKING:
    from collections.abc import Mapping


# 允许的 list 合并策略集合（[CS 1.1 常量命名 UPPER_SNAKE_CASE]）
ALLOWED_LIST_MERGE_STRATEGIES: Final[frozenset[str]] = frozenset({"override", "concat", "unique_concat"})

# 递归深度上下界
MIN_MAX_DEPTH: Final[int] = 1
MAX_MAX_DEPTH: Final[int] = 50
DEFAULT_MAX_DEPTH_VALUE: Final[int] = 10


class TemplateValidationError(AgentHubError):
    """模板 schema 校验失败.

    [类名] TemplateValidationError
    [职责] 携带 ValidationResult 的领域异常
    [关联设计规范] MD-MCP-V1.0-20260602.md#M-C03
    [属性]
      属性1: errors list[ValidationErrorItem] 详细错误列表
    [方法列表]
      方法1: to_code() -> str - 返回 TEMPLATE_SCHEMA_VIOLATION 错误码
    [状态机] 无
    [异常处理]
      异常1: 本异常由 validate 抛出，调用方应捕获并转译为 IC-010 错误码
    [来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-C03 + DD-M推断:领域异常继承 AgentHubError]
    """

    def __init__(self, errors: list[ValidationErrorItem]) -> None:
        """初始化 TemplateValidationError.

        [函数名] __init__
        [职责] 构造异常对象
        [参数说明]
          参数1: errors list[ValidationErrorItem] 必填 错误详情
        [返回值] None
        [错误码] 无
        [来源标注] [DD-M推断:基于 AgentHubError 约定]
        """
        super().__init__("template schema violation")
        self.errors: list[ValidationErrorItem] = errors

    def to_code(self) -> str:
        """转换为 IC-010 错误码.

        [函数名] to_code
        [职责] 返回 IC-010 错误码常量
        [参数说明] 无
        [返回值] str "TEMPLATE_SCHEMA_VIOLATION"
        [错误码] 无
        [来源标注] [DD-001:IC-010]
        """
        return "TEMPLATE_SCHEMA_VIOLATION"


class DepthLimitError(AgentHubError):
    """递归深度超限（循环引用）.

    [类名] DepthLimitError
    [职责] 当 merger 递归深度超过 max_depth 时抛出
    [关联设计规范] MD-MCP-V1.0-20260602.md#M-C03
    [属性]
      属性1: max_depth int 触发本次异常的深度上限
      属性2: path str 触发循环的路径（点号分隔）
    [方法列表]
      方法1: to_code() -> str - 返回 TEMPLATE_CIRCULAR_REF 错误码
    [状态机] 无
    [异常处理]
      异常1: 本异常由 merger.merge 抛出
    [来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-C03 + IC-010]
    """

    def __init__(self, max_depth: int, path: str) -> None:
        """初始化 DepthLimitError.

        [函数名] __init__
        [职责] 构造异常对象
        [参数说明]
          参数1: max_depth int 必填 触发上限
          参数2: path str 必填 触发路径
        [返回值] None
        [错误码] 无
        [来源标注] [DD-M推断:基于 AgentHubError 约定]
        """
        super().__init__(f"depth > {max_depth} at {path}")
        self.max_depth: int = max_depth
        self.path: str = path

    def to_code(self) -> str:
        """转换为 IC-010 错误码.

        [函数名] to_code
        [职责] 返回 TEMPLATE_CIRCULAR_REF
        [参数说明] 无
        [返回值] str "TEMPLATE_CIRCULAR_REF"
        [错误码] 无
        [来源标注] [DD-001:IC-010]
        """
        return "TEMPLATE_CIRCULAR_REF"


class TemplateConfig(BaseModel):
    """模板配置 Value Object（frozen=True，不可变）.

    [类名] TemplateConfig
    [职责] 不可变配置：base / override / 合并策略 / 递归深度
    [关联设计规范] MD-MCP-V1.0-20260602.md#M-C03
    [属性]
      属性1: base dict[str, object] 必填 基底
      属性2: override dict[str, object] 必填 覆盖层
      属性3: max_depth int 默认 10 递归深度上限
      属性4: list_merge_strategy str 默认 "override" ∈ ALLOWED_LIST_MERGE_STRATEGIES
    [方法列表]
      方法1: to_merged() -> dict - 便捷调用 merger.merge
      方法2: with_override(extra) -> TemplateConfig - 返回新实例（frozen 不能 in-place 修改）
    [状态机] 无（不可变）
    [异常处理]
      异常1: ValueError - list_merge_strategy 非法
      异常2: ValueError - max_depth 越界
    [来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-C03 + DD-M推断:frozen + ConfigDict 实践]
    """

    model_config: ConfigDict = ConfigDict(frozen=True, extra="forbid")

    base: dict[str, object] = Field(default_factory=dict)
    override: dict[str, object] = Field(default_factory=dict)
    max_depth: int = Field(default=DEFAULT_MAX_DEPTH_VALUE, ge=MIN_MAX_DEPTH, le=MAX_MAX_DEPTH)
    list_merge_strategy: str = Field(default="override")

    def __post_init_post_parse__(self) -> None:  # pragma: no cover - pydantic 入口
        """pydantic 字段校验后置钩子（占位说明）.

        [函数名] __post_init_post_parse__
        [职责] 进一步校验 list_merge_strategy ∈ 白名单
        [参数说明] 无
        [返回值] None
        [错误码] 无（失败时由 pydantic 抛 ValidationError）
        [来源标注] [DD-M推断:强化 list_merge_strategy 白名单校验]
        """
        # 业务实现由开发工程师在 DD-S 之后填充；此处仅注释
        return None

    def to_merged(self) -> dict[str, object]:
        """便捷：基于自身配置执行 merge.

        [函数名] to_merged
        [职责] 等价于 TemplateMerger.merge(self.base, self.override, ...)
        [参数说明] 无
        [返回值] dict[str, object] 合并结果
        [错误码] 见 TemplateMerger.merge
        [前置条件] base / override 可 JSON 序列化
        [后置条件] 无副作用（in-proc 纯函数）
        [并发安全] 纯函数线程安全
        [幂等性] 是
        [性能约束] < 5ms
        [来源标注] [DD-M推断:Value Object 自身便捷方法]
        """
        # 业务实现由开发工程师在 DD-S 之后填充；此处仅注释
        raise NotImplementedError("M-C03 TemplateConfig.to_merged 业务代码待开发工程师实现")

    def with_override(self, extra: dict[str, object]) -> TemplateConfig:
        """返回带额外 override 的新 TemplateConfig（frozen 不能 in-place 修改）.

        [函数名] with_override
        [职责] 在 override 之上叠加 extra 并返回新实例
        [参数说明]
          参数1: extra dict[str, object] 必填 要叠加的覆盖
                 校验规则: 键集合需为现有 override 的子集或无冲突新键
        [返回值] TemplateConfig 新实例
        [错误码] 无
        [前置条件] extra 可 JSON 序列化
        [后置条件] 不修改 self
        [并发安全] 纯函数线程安全
        [幂等性] 是（同 extra → 同新实例）
        [来源标注] [DD-M推断:frozen 模型的不可变更新范式]
        """
        # 业务实现由开发工程师在 DD-S 之后填充；此处仅注释
        raise NotImplementedError("M-C03 TemplateConfig.with_override 业务代码待开发工程师实现")


class ValidationErrorItem(BaseModel):
    """单条 schema 校验错误项.

    [类名] ValidationErrorItem
    [职责] 标准化 schema 校验错误结构
    [关联设计规范] MD-MCP-V1.0-20260602.md#M-C03
    [属性]
      属性1: path str 出错路径（点号分隔）
      属性2: message str 错误描述
      属性3: schema_path str 触发该错误的 schema 节点路径
    [方法列表]
      方法1: 无（纯数据载体）
    [状态机] 无
    [异常处理] 无
    [来源标注] [DD-M推断:对 jsonschema ValidationError 标准化包装]
    """

    model_config: ConfigDict = ConfigDict(frozen=True, extra="forbid")

    path: str
    message: str
    schema_path: str = ""


class ValidationResult(BaseModel):
    """schema 校验结果.

    [类名] ValidationResult
    [职责] 承载 valid 标志与错误列表
    [关联设计规范] MD-MCP-V1.0-20260602.md#M-C03
    [属性]
      属性1: valid bool 是否通过
      属性2: errors list[ValidationErrorItem] 错误列表（valid=True 时为空）
    [方法列表]
      方法1: raise_if_invalid() -> None - 失败时抛 TemplateValidationError
    [状态机] 无
    [异常处理]
      异常1: TemplateValidationError - 当 valid=False 且 raise_if_invalid 被调用
    [来源标注] [DD-M推断:领域结果对象]
    """

    model_config: ConfigDict = ConfigDict(frozen=True, extra="forbid")

    valid: bool
    errors: list[ValidationErrorItem] = Field(default_factory=list)

    def raise_if_invalid(self) -> None:
        """失败时抛 TemplateValidationError.

        [函数名] raise_if_invalid
        [职责] 校验失败的便捷抛出
        [参数说明] 无
        [返回值] None
        [错误码] 抛出后转化为 TEMPLATE_SCHEMA_VIOLATION（IC-010）
        [前置条件] 无
        [后置条件] valid=True 时无副作用
        [并发安全] 线程安全
        [幂等性] 是
        [来源标注] [DD-M推断:领域结果对象的便捷方法]
        """
        # 业务实现由开发工程师在 DD-S 之后填充；此处仅注释
        if not self.valid:
            raise TemplateValidationError(self.errors)
        return None


def validate(
    merged: Mapping[str, object],
    schema: Mapping[str, object],
) -> ValidationResult:
    """对合并结果做 schema 校验（JSON Schema Draft 2020-12）.

    [函数名] validate
    [职责] 顶层 schema 校验入口
    [关联接口契约] IC-010
    [参数说明]
      参数1: merged Mapping[str, object] 必填 合并后结果
      参数2: schema Mapping[str, object] 必填 JSON Schema (Draft 2020-12)
    [返回值] ValidationResult
    [错误码]
      错误码1: TEMPLATE_SCHEMA_VIOLATION 422 详见 ValidationResult.errors（IC-010）
    [前置条件] schema 满足 JSON Schema 2020-12
    [后置条件] 无副作用
    [并发安全] 纯函数线程安全
    [幂等性] 是
    [性能约束] < 5ms（[IC-010:性能约束]）
    [示例]
      ```
      r = validate({"a": 1}, {"type": "object", "required": ["a"]})
      assert r.valid is True
      ```
    [来源标注] [DD-001:IC-010 + CS-MCP-V1.0-20260602 §7 JSON Schema]
    """
    # 业务实现由开发工程师在 DD-S 之后填充；此处仅注释
    raise NotImplementedError("M-C03 schema.validate 业务代码待开发工程师实现")


__all__: list[str] = [
    "ALLOWED_LIST_MERGE_STRATEGIES",
    "DEFAULT_MAX_DEPTH_VALUE",
    "DepthLimitError",
    "MAX_MAX_DEPTH",
    "MIN_MAX_DEPTH",
    "TemplateConfig",
    "TemplateValidationError",
    "ValidationErrorItem",
    "ValidationResult",
    "validate",
]
