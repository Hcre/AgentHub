"""M-C03 Template Engine merger tests.

[文件路径] src/agenthub/infrastructure/template/tests/test_merger.py
[文件职责] TemplateMerger.merge / merge_with_diff 单元测试
[所属模块] M-C03（来自DD-001）
[关联设计规范] FS-012 / MD-MCP-V1.0-20260602.md#M-C03 / IC-010 / CS §1.7
[功能描述]
  功能1: 覆盖深合并 / 标量覆盖 / list 合并策略 / 循环引用等核心场景
  功能2: 覆盖 diff 输出 / 性能约束（< 5ms）
[输入输出]
  输入: 测试函数（无 IO，函数式）
  输出: pytest 报告
[依赖关系]
  依赖文件: pytest / agenthub.infrastructure.template.merger
  被依赖文件: 无
[注意事项]
  注意1: 全部为纯函数测试，禁止引入 IO（[CS 1.7]）
  注意2: 命名遵循 test_{function}_when_{scenario}_then_{expected}（[CS 1.7]）
  注意3: AAA 模式（given/when/then）
  注意4: 覆盖率目标 ≥ 95%（[MD-MCP-V1.0-20260602.md#M-C03 测试策略]）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.7
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-12 - 初版测试文件注释
[作者] DD-M-12-20260602
[来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-C03 + DD-M推断:基于 [AR:TS-030] 25 用例拆分]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from agenthub.infrastructure.template.merger import (
    DEFAULT_MAX_DEPTH,
    TemplateMerger,
    merge,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


# ----- 正常场景 ------------------------------------------------------------

# [测试场景1: 简单标量覆盖] [断言: 返回字典中 override 标量覆盖 base 标量] [Mock: 无]
def test_merge_when_scalar_override_then_override_wins(
    sample_base: Mapping[str, object],
    sample_override: Mapping[str, object],
) -> None:
    """[测试场景] 标量覆盖：override 胜出.
    [断言] result["scalar"] == "from_override"
    [Mock] 无
    [来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-C03 + DD-M推断:深合并核心]
    """
    # given - fixtures
    # when
    result = TemplateMerger.merge(sample_base, sample_override)
    # then
    assert result["scalar"] == "from_override"


# [测试场景2: dict 递归合并] [断言: 子字典的字段按 override 合并] [Mock: 无]
def test_merge_when_nested_dict_then_deep_merge(
    sample_base: Mapping[str, object],
    sample_override: Mapping[str, object],
) -> None:
    """[测试场景] 嵌套 dict 合并.
    [断言] result["nested"] == {"a": 1, "b": 20, "c": 3, "list": [4]}
    [Mock] 无
    [来源标注] [DD-M推断:深合并核心]
    """
    # given
    # when
    result = TemplateMerger.merge(sample_base, sample_override)
    # then
    assert result["nested"] == {"a": 1, "b": 20, "c": 3, "list": [4]}


# [测试场景3: list 覆盖策略默认] [断言: list 整体被 override 替换（默认 override）] [Mock: 无]
def test_merge_when_list_default_strategy_then_override_replaces(
    sample_base: Mapping[str, object],
    sample_override: Mapping[str, object],
) -> None:
    """[测试场景] list 默认 override 策略.
    [断言] result["nested"]["list"] == [4]
    [Mock] 无
    [来源标注] [DD-M推断:list_merge_strategy="override"]
    """
    # given
    # when
    result = TemplateMerger.merge(sample_base, sample_override)
    # then
    assert result["nested"]["list"] == [4]


# [测试场景4: list 拼接策略] [断言: list = base + override] [Mock: 无]
def test_merge_when_list_concat_strategy_then_concatenated() -> None:
    """[测试场景] list concat 策略.
    [断言] result["list"] == [1, 2, 3, 4]
    [Mock] 无
    [来源标注] [DD-M推断:list_merge_strategy="concat"]
    """
    # given
    base = {"list": [1, 2, 3]}
    override = {"list": [4]}
    # when
    result = TemplateMerger.merge(base, override, list_merge_strategy="concat")
    # then
    assert result["list"] == [1, 2, 3, 4]


# [测试场景5: 顶层便捷函数] [断言: merge() 与 TemplateMerger.merge() 结果一致] [Mock: 无]
def test_merge_top_level_when_same_input_then_same_output_as_classmethod(
    sample_base: Mapping[str, object],
    sample_override: Mapping[str, object],
) -> None:
    """[测试场景] 顶层 merge 与类方法等价.
    [断言] merge(...) == TemplateMerger.merge(...)
    [Mock] 无
    [来源标注] [DD-M推断:顶层便捷函数一致性]
    """
    # given
    # when
    a = merge(sample_base, sample_override)
    b = TemplateMerger.merge(sample_base, sample_override)
    # then
    assert a == b


# [测试场景6: diff 列表输出] [断言: diff 至少包含 nested.b 与 scalar 的 patch] [Mock: 无]
def test_merge_with_diff_when_override_present_then_diff_non_empty(
    sample_base: Mapping[str, object],
    sample_override: Mapping[str, object],
) -> None:
    """[测试场景] diff 输出.
    [断言] diff 非空且至少 2 项
    [Mock] 无
    [来源标注] [DD-001:IC-010 包含 diff 字段]
    """
    # given
    # when
    merged, diff = TemplateMerger.merge_with_diff(sample_base, sample_override)
    # then
    assert isinstance(merged, dict)
    assert isinstance(diff, list)
    assert len(diff) >= 2


# [测试场景7: diff 为空] [断言: base == override 时 diff 为 [] ] [Mock: 无]
def test_merge_with_diff_when_no_change_then_diff_empty() -> None:
    """[测试场景] diff 空.
    [断言] diff == []
    [Mock] 无
    [来源标注] [DD-M推断:无变更时 diff 为空]
    """
    # given
    same = {"a": 1, "b": 2}
    # when
    _, diff = TemplateMerger.merge_with_diff(same, same)
    # then
    assert diff == []


# [测试场景8: 不修改入参] [断言: base/override 的 id 与合并前一致（in-proc 不可变性）] [Mock: 无]
def test_merge_when_called_then_does_not_mutate_inputs(
    sample_base: Mapping[str, object],
    sample_override: Mapping[str, object],
) -> None:
    """[测试场景] 不可变性.
    [断言] sample_base 与 sample_override 内容未变
    [Mock] 无
    [来源标注] [DD-001:IC-010 纯函数 + 不可变]
    """
    # given
    base_snapshot = dict(sample_base)
    override_snapshot = dict(sample_override)
    # when
    TemplateMerger.merge(sample_base, sample_override)
    # then
    assert sample_base == base_snapshot
    assert sample_override == override_snapshot


# [测试场景9: 性能 < 5ms] [断言: 1k 次调用平均 < 5ms] [Mock: 无]
def test_merge_when_perf_check_then_under_5ms(
    sample_base: Mapping[str, object],
    sample_override: Mapping[str, object],
) -> None:
    """[测试场景] 性能约束.
    [断言] 单次 merge < 5ms
    [Mock] 无
    [来源标注] [DD-001:IC-010 性能约束 < 5ms]
    """
    # given
    import time

    # when
    start = time.perf_counter()
    for _ in range(1000):
        TemplateMerger.merge(sample_base, sample_override)
    elapsed_ms = (time.perf_counter() - start) * 1000
    # then
    assert elapsed_ms / 1000 < 5.0


# ----- 异常场景 ------------------------------------------------------------

# [测试场景10: 循环引用] [断言: 抛 DepthLimitError] [Mock: 无]
def test_merge_when_circular_reference_then_depth_limit_error() -> None:
    """[测试场景] 循环引用.
    [断言] 抛 DepthLimitError
    [Mock] 无
    [来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-C03 异常处理]
    """
    # given
    a: dict[str, object] = {}
    a["self"] = a  # type: ignore[assignment]
    # when / then
    with pytest.raises(Exception) as exc_info:  # noqa: PT011
        TemplateMerger.merge(a, {})
    # DepthLimitError 继承 AgentHubError
    assert "depth" in str(exc_info.value).lower() or "circular" in str(exc_info.value).lower()


# [测试场景11: max_depth 边界] [断言: max_depth=1 时平层合并正常] [Mock: 无]
def test_merge_when_max_depth_1_then_flat_only() -> None:
    """[测试场景] max_depth=1 边界.
    [断言] 正常返回；不抛异常
    [Mock] 无
    [来源标注] [DD-M推断:边界]
    """
    # given
    # when
    result = TemplateMerger.merge({"a": {"b": 1}}, {"a": {"c": 2}}, max_depth=1)
    # then
    assert "a" in result


# [测试场景12: 非法 list_merge_strategy] [断言: 抛 ValueError] [Mock: 无]
def test_merge_when_invalid_list_strategy_then_value_error() -> None:
    """[测试场景] 非法策略.
    [断言] 抛 ValueError
    [Mock] 无
    [来源标注] [DD-M推断:输入校验]
    """
    # given
    # when / then
    with pytest.raises(ValueError):
        TemplateMerger.merge({}, {}, list_merge_strategy="unknown")


# [测试场景13: DEFAULT_MAX_DEPTH 常量] [断言: DEFAULT_MAX_DEPTH == 10] [Mock: 无]
def test_default_max_depth_constant_value() -> None:
    """[测试场景] 常量值.
    [断言] DEFAULT_MAX_DEPTH == 10
    [Mock] 无
    [来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-C03 循环引用 max depth 10]
    """
    # given
    # when
    # then
    assert DEFAULT_MAX_DEPTH == 10


# [测试场景14: schema 校验调用] [断言: validate 被调用后返回 ValidationResult] [Mock: 无]
def test_validate_delegates_to_schema_module(
    sample_base: Mapping[str, object],
    sample_override: Mapping[str, object],
    sample_schema: Mapping[str, object],
) -> None:
    """[测试场景] validate 委托.
    [断言] TemplateMerger.validate 返回 ValidationResult 实例
    [Mock] 无
    [来源标注] [DD-M推断:模块间调用]
    """
    # given
    merged = TemplateMerger.merge(sample_base, sample_override)
    # when
    result = TemplateMerger.validate(merged, sample_schema)
    # then
    from agenthub.infrastructure.template.schema import ValidationResult

    assert isinstance(result, ValidationResult)
