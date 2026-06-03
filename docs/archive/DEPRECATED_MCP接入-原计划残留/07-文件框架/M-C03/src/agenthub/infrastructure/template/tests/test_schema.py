"""M-C03 Template Engine schema tests.

[文件路径] src/agenthub/infrastructure/template/tests/test_schema.py
[文件职责] TemplateConfig / ValidationResult / 领域异常单元测试
[所属模块] M-C03（来自DD-001）
[关联设计规范] FS-012 / MD-MCP-V1.0-20260602.md#M-C03 / IC-010 / CS §1.7
[功能描述]
  功能1: 覆盖 Value Object 不可变性 / schema 校验成功与失败 / 异常抛出
[输入输出]
  输入: 测试函数（无 IO，函数式）
  输出: pytest 报告
[依赖关系]
  依赖文件: pytest / agenthub.infrastructure.template.schema
  被依赖文件: 无
[注意事项]
  注意1: 全部为纯函数测试
  注意2: 命名遵循 CS §1.7
  注意3: AAA 模式
  注意4: 覆盖率目标 ≥ 95%
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.7
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-12 - 初版测试文件注释
[作者] DD-M-12-20260602
[来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-C03 + DD-M推断:Value Object 测试集]
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from agenthub.infrastructure.template.schema import (
    ALLOWED_LIST_MERGE_STRATEGIES,
    DepthLimitError,
    MAX_MAX_DEPTH,
    MIN_MAX_DEPTH,
    TemplateConfig,
    TemplateValidationError,
    ValidationErrorItem,
    ValidationResult,
    validate,
)


# ----- 正常场景 ------------------------------------------------------------

# [测试场景1: TemplateConfig 默认值] [断言: 默认 max_depth=10, list_merge_strategy="override"] [Mock: 无]
def test_template_config_when_default_then_expected_defaults() -> None:
    """[测试场景] 默认配置.
    [断言] TemplateConfig().max_depth == 10
    [Mock] 无
    [来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-C03]
    """
    # given
    cfg = TemplateConfig()
    # when
    # then
    assert cfg.max_depth == 10
    assert cfg.list_merge_strategy == "override"
    assert cfg.base == {}
    assert cfg.override == {}


# [测试场景2: TemplateConfig 不可变] [断言: 修改属性抛 ValidationError] [Mock: 无]
def test_template_config_when_frozen_then_mutation_raises() -> None:
    """[测试场景] frozen 模型不可变.
    [断言] 赋值 base 抛 ValidationError（Pydantic frozen）
    [Mock] 无
    [来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-C03 frozen=True]
    """
    # given
    cfg = TemplateConfig(base={"a": 1})
    # when / then
    with pytest.raises((PydanticValidationError, AttributeError, ValueError)):
        cfg.base = {"b": 2}  # type: ignore[misc]


# [测试场景3: with_override 返回新实例] [断言: 返回新 TemplateConfig 且不修改原实例] [Mock: 无]
def test_template_config_with_override_when_called_then_new_instance() -> None:
    """[测试场景] 不可变更新.
    [断言] 新 cfg.override 含原值 ∪ extra；原 cfg 不变
    [Mock] 无
    [来源标注] [DD-M推断:frozen 模型的不可变更新范式]
    """
    # given
    cfg = TemplateConfig(base={"a": 1}, override={"b": 2})
    # when
    new_cfg = cfg.with_override({"c": 3})
    # then
    assert new_cfg is not cfg
    assert "c" in new_cfg.override
    assert "c" not in cfg.override


# [测试场景4: validate 成功] [断言: valid=True, errors=[] ] [Mock: 无]
def test_validate_when_schema_match_then_valid_true(sample_schema: dict[str, object]) -> None:
    """[测试场景] 校验通过.
    [断言] result.valid is True 且 errors 为空
    [Mock] 无
    [来源标注] [DD-001:IC-010 + CS §7 JSON Schema 2020-12]
    """
    # given
    data = {"name": "ok", "nested": {"a": 1}}
    # when
    result = validate(data, sample_schema)
    # then
    assert result.valid is True
    assert result.errors == []


# [测试场景5: validate 失败] [断言: valid=False, errors 非空] [Mock: 无]
def test_validate_when_missing_required_then_valid_false(sample_schema: dict[str, object]) -> None:
    """[测试场景] 校验失败.
    [断言] result.valid is False 且 errors 非空
    [Mock] 无
    [来源标注] [DD-001:IC-010 错误码 TEMPLATE_SCHEMA_VIOLATION]
    """
    # given
    data = {"nested": {"a": 1}}  # 缺 name
    # when
    result = validate(data, sample_schema)
    # then
    assert result.valid is False
    assert len(result.errors) > 0


# [测试场景6: raise_if_invalid 抛出] [断言: 失败时抛 TemplateValidationError] [Mock: 无]
def test_validation_result_raise_if_invalid_when_invalid_then_raises() -> None:
    """[测试场景] 失败抛出.
    [断言] 抛 TemplateValidationError，errors 字段被填充
    [Mock] 无
    [来源标注] [DD-M推断:领域异常]
    """
    # given
    err = ValidationErrorItem(path="$.name", message="required", schema_path="#/required")
    result = ValidationResult(valid=False, errors=[err])
    # when / then
    with pytest.raises(TemplateValidationError) as exc_info:
        result.raise_if_invalid()
    assert exc_info.value.errors == [err]


# [测试场景7: raise_if_invalid 通过不抛] [断言: 有效时无副作用] [Mock: 无]
def test_validation_result_raise_if_invalid_when_valid_then_no_op() -> None:
    """[测试场景] 通过不抛.
    [断言] 调用 raise_if_invalid 不抛
    [Mock] 无
    [来源标注] [DD-M推断:happy path]
    """
    # given
    result = ValidationResult(valid=True)
    # when / then
    result.raise_if_invalid()  # 不应抛


# [测试场景8: TemplateValidationError.to_code] [断言: 返回 "TEMPLATE_SCHEMA_VIOLATION"] [Mock: 无]
def test_template_validation_error_to_code() -> None:
    """[测试场景] 错误码映射.
    [断言] to_code() == "TEMPLATE_SCHEMA_VIOLATION"
    [Mock] 无
    [来源标注] [DD-001:IC-010 错误码]
    """
    # given
    exc = TemplateValidationError(errors=[])
    # when
    code = exc.to_code()
    # then
    assert code == "TEMPLATE_SCHEMA_VIOLATION"


# [测试场景9: DepthLimitError.to_code] [断言: 返回 "TEMPLATE_CIRCULAR_REF"] [Mock: 无]
def test_depth_limit_error_to_code() -> None:
    """[测试场景] 错误码映射.
    [断言] to_code() == "TEMPLATE_CIRCULAR_REF"
    [Mock] 无
    [来源标注] [DD-001:IC-010 错误码]
    """
    # given
    exc = DepthLimitError(max_depth=10, path="$.nested")
    # when
    code = exc.to_code()
    # then
    assert code == "TEMPLATE_CIRCULAR_REF"


# [测试场景10: ALLOWED_LIST_MERGE_STRATEGIES] [断言: 集合含 override/concat/unique_concat] [Mock: 无]
def test_allowed_strategies_contains_expected() -> None:
    """[测试场景] 白名单.
    [断言] ALLOWED_LIST_MERGE_STRATEGIES == {"override","concat","unique_concat"}
    [Mock] 无
    [来源标注] [DD-M推断:白名单校验]
    """
    # given
    # when
    # then
    assert ALLOWED_LIST_MERGE_STRATEGIES == frozenset({"override", "concat", "unique_concat"})


# [测试场景11: 边界 max_depth] [断言: MIN/MAX 常量值正确] [Mock: 无]
def test_depth_constants() -> None:
    """[测试场景] 常量边界.
    [断言] MIN_MAX_DEPTH == 1, MAX_MAX_DEPTH == 50
    [Mock] 无
    [来源标注] [DD-M推断:边界常量]
    """
    # given
    # when
    # then
    assert MIN_MAX_DEPTH == 1
    assert MAX_MAX_DEPTH == 50


# [测试场景12: max_depth 越界] [断言: 越界抛 PydanticValidationError] [Mock: 无]
def test_template_config_when_max_depth_out_of_range_then_validation_error() -> None:
    """[测试场景] 越界.
    [断言] max_depth=100 抛 ValidationError
    [Mock] 无
    [来源标注] [DD-M推断:边界]
    """
    # given
    # when / then
    with pytest.raises(PydanticValidationError):
        TemplateConfig(max_depth=100)


# [测试场景13: list_merge_strategy 非法] [断言: 非法策略抛 ValidationError 或 ValueError] [Mock: 无]
def test_template_config_when_invalid_list_strategy_then_validation_error() -> None:
    """[测试场景] 非法策略.
    [断言] list_merge_strategy="bogus" 抛 ValidationError 或 ValueError
    [Mock] 无
    [来源标注] [DD-M推断:白名单校验]
    """
    # given
    # when / then
    with pytest.raises((PydanticValidationError, ValueError)):
        TemplateConfig(list_merge_strategy="bogus")
