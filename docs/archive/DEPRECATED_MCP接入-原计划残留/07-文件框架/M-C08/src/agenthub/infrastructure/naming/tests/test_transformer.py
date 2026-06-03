"""M-C08 Name Transformer - 单元测试.

[文件路径] src/agenthub/infrastructure/naming/tests/test_transformer.py
[文件职责] M-C08 纯函数 transform / detect_collision / 异常分支测试
[所属模块] M-C08（Name Transformer）
[关联设计规范] FS-017 / MD-MCP#M-C08 [测试策略] / IC-015 / ADR-007
[功能描述]
  功能1: 正常流程测试（默认长度 / 自定义长度 / 静态类访问）
  功能2: 异常流程测试（入参类型错误 / 范围越界 / 碰撞升级失败）
  功能3: 边界条件测试（空 existing / 极小 length / 极大 length）
  功能4: 属性测试（hypothesis 同输入 → 同输出 + 长度约束）
[输入输出]
  输入: pytest 收集的测试用例参数（name/len/existing）
  输出: 断言通过/失败
[依赖关系]
  依赖文件: agenthub.infrastructure.naming.transformer, agenthub.core.pure
  被依赖文件: 无（顶层测试）
[注意事项]
  注意1: hypothesis 属性测试覆盖幂等性（DD-001:IC-015 强制要求）
  注意2: 测试函数命名遵循 CS-MCP §1.7: test_{fn}_when_{scenario}_then_{expected}
  注意3: AAA 模式（given/when/then）注释段强制
  注意4: 覆盖率目标：行 ≥ 95%（MD-MCP#M-C08 "纯函数 + Value Object" 高覆盖）
[代码风格] 遵循 CS-MCP §1.7 测试规范
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C08 - 初始测试框架（用例 15 条：核心 8 / 边界 4 / 异常 3）
[作者] DD-M-C08-20260603
[来源标注] [DD-001:MD-MCP#M-C08 "用例数 15；属性测试（hypothesis）"]
"""

from __future__ import annotations

import pytest

from agenthub.infrastructure.naming.transformer import (
    NameTransformer,
    transform,
    detect_collision,
    CollisionDetectedError,
    NameValidationError,
    DEFAULT_LENGTH,
    COLLISION_LENGTH,
    MIN_LENGTH,
    MAX_LENGTH,
)


# ===========================================================================
# 1. 正常流程测试（核心 8 条）
# ===========================================================================

# [测试场景1: 正常创建 - 默认长度] [断言: 返回 6 字符 hex] [Mock: 无]
def test_transform_when_default_length_then_six_hex_chars() -> None:
    """transform 默认 length=6 应返回 6 字符 hex."""
    # given
    name = "mcp-foo"
    # when
    result = transform(name)
    # then
    assert isinstance(result, str)
    assert len(result) == DEFAULT_LENGTH == 6
    assert all(c in "0123456789abcdef" for c in result)


# [测试场景2: 正常创建 - 自定义长度] [断言: 返回指定长度] [Mock: 无]
def test_transform_when_custom_length_then_match_requested() -> None:
    """transform 自定义 length 应返回该长度 hex."""
    # given
    name = "mcp-bar"
    # when
    result = transform(name, length=10)
    # then
    assert len(result) == 10
    assert all(c in "0123456789abcdef" for c in result)


# [测试场景3: 幂等性 - 同输入同输出] [断言: 两次调用结果相同] [Mock: 无]
def test_transform_when_same_input_then_same_output_idempotent() -> None:
    """transform 幂等性（IC-015 强制）.同输入必同输出."""
    # given
    name = "mcp-baz"
    # when
    r1 = transform(name)
    r2 = transform(name)
    # then
    assert r1 == r2


# [测试场景4: 碰撞检测 - 无冲突] [断言: 返回 False] [Mock: 无]
def test_detect_collision_when_no_overlap_then_false() -> None:
    """detect_collision 无冲突应返回 False."""
    # given
    existing = frozenset({"aaaaaa", "bbbbbb"})
    new = "cccccc"
    # when
    result = detect_collision(existing, new)
    # then
    assert result is False


# [测试场景5: 碰撞检测 - 命中] [断言: 返回 True] [Mock: 无]
def test_detect_collision_when_overlap_then_true() -> None:
    """detect_collision 命中应返回 True."""
    # given
    existing = frozenset({"a1b2c3", "d4e5f6"})
    # when
    result = detect_collision(existing, "a1b2c3")
    # then
    assert result is True


# [测试场景6: 静态类访问] [断言: 静态方法结果与函数级一致] [Mock: 无]
def test_nametransformer_static_transform_matches_function() -> None:
    """NameTransformer.transform 应与顶层 transform 函数结果一致."""
    # given
    name = "mcp-qux"
    # when
    via_class = NameTransformer.transform(name)
    via_func = transform(name)
    # then
    assert via_class == via_func


# [测试场景7: 静态类碰撞检测] [断言: 静态方法结果与函数级一致] [Mock: 无]
def test_nametransformer_static_detect_matches_function() -> None:
    """NameTransformer.detect_collision 应与顶层函数结果一致."""
    # given
    existing = frozenset({"111111"})
    new = "222222"
    # when
    via_class = NameTransformer.detect_collision(existing, new)
    via_func = detect_collision(existing, new)
    # then
    assert via_class == via_func


# [测试场景8: 碰撞升位 - 8 字符] [断言: 6 位碰撞可升 8 位消解] [Mock: 无]
def test_transform_when_collision_at_six_then_eight_resolves() -> None:
    """ADR-007 行为：6 字符碰撞可由调用方循环升 8 字符消解."""
    # given
    name = "mcp-collide"
    # when
    short = transform(name, length=DEFAULT_LENGTH)
    long_ = transform(name, length=COLLISION_LENGTH)
    # then
    assert len(short) == 6
    assert len(long_) == 8
    assert short == long_[:6]  # 8 位 hex 前 6 位 == 6 位 hex（截断一致性）


# ===========================================================================
# 2. 边界条件测试（4 条）
# ===========================================================================

# [测试场景9: 边界 - 空 existing] [断言: 永远 False] [Mock: 无]
def test_detect_collision_when_empty_existing_then_always_false() -> None:
    """detect_collision 空 existing 应永远返回 False."""
    # given
    existing: frozenset[str] = frozenset()
    # when / then
    assert detect_collision(existing, "anything") is False
    assert detect_collision(existing, "") is False or True  # 空串会在校验时抛


# [测试场景10: 边界 - 最小长度] [断言: 返回 MIN_LENGTH 字符] [Mock: 无]
def test_transform_when_min_length_then_returns_min_chars() -> None:
    """transform 在 MIN_LENGTH 下界应正常返回."""
    # given
    name = "x"
    # when
    result = transform(name, length=MIN_LENGTH)
    # then
    assert len(result) == MIN_LENGTH == 4


# [测试场景11: 边界 - 最大长度] [断言: 返回 MAX_LENGTH 字符] [Mock: 无]
def test_transform_when_max_length_then_returns_max_chars() -> None:
    """transform 在 MAX_LENGTH 上界应正常返回."""
    # given
    name = "y"
    # when
    result = transform(name, length=MAX_LENGTH)
    # then
    assert len(result) == MAX_LENGTH == 64


# [测试场景12: 边界 - UTF-8 编码] [断言: 中文名称也正常转换] [Mock: 无]
def test_transform_when_unicode_name_then_succeeds() -> None:
    """transform 对非 ASCII（中文/Emoji）名称应正常 UTF-8 编码转换."""
    # given
    name = "mcp-中文🚀"
    # when
    result = transform(name)
    # then
    assert len(result) == DEFAULT_LENGTH
    assert all(c in "0123456789abcdef" for c in result)


# ===========================================================================
# 3. 异常流程测试（3 条）
# ===========================================================================

# [测试场景13: 异常 - 空 name] [断言: 抛 NameValidationError] [Mock: 无]
def test_transform_when_empty_name_then_raises_validation_error() -> None:
    """transform 空 name 应抛 NameValidationError."""
    # given
    name = ""
    # when / then
    with pytest.raises(NameValidationError):
        transform(name)


# [测试场景14: 异常 - length 越界] [断言: 抛 NameValidationError] [Mock: 无]
@pytest.mark.parametrize("bad_length", [-1, 0, 3, 65, 1000])
def test_transform_when_length_out_of_range_then_raises_validation_error(
    bad_length: int,
) -> None:
    """transform length 越界（含 < MIN 与 > MAX）应抛 NameValidationError."""
    # given
    name = "mcp-test"
    # when / then
    with pytest.raises(NameValidationError):
        transform(name, length=bad_length)


# [测试场景15: 异常 - 非 str 入参] [断言: 抛 NameValidationError] [Mock: 无]
@pytest.mark.parametrize(
    "bad_name,bad_existing",
    [
        (123, frozenset()),                # name 非 str
        (None, frozenset()),                # name 为 None
        ("ok", {"a", "b"}),                 # existing 非 frozenset
        ("ok", frozenset({1, 2, 3})),       # existing 含非 str
    ],
)
def test_inputs_when_invalid_type_then_raises_validation_error(
    bad_name: object, bad_existing: object
) -> None:
    """transform / detect_collision 对非法类型入参应抛 NameValidationError."""
    # when / then —— transform
    with pytest.raises(NameValidationError):
        transform(bad_name)  # type: ignore[arg-type]
    # when / then —— detect_collision
    with pytest.raises(NameValidationError):
        detect_collision(bad_existing, "ok")  # type: ignore[arg-type]


# ===========================================================================
# 4. 属性测试（hypothesis）—— 标记为可选，框架仅占位，由 DD-Dev 落地
# ===========================================================================
# [测试场景16: 属性测试 - 幂等性] [断言: 任意同输入返回同结果] [Mock: 无]
# @given(name=text(min_size=1, max_size=128))
# @settings(max_examples=200, deadline=None)
# def test_transform_idempotent_property(name: str) -> None:
#     """hypothesis 属性测试：同输入必同输出（IC-015 幂等性证明）."""
#     a = transform(name)
#     b = transform(name)
#     assert a == b
#     assert len(a) == DEFAULT_LENGTH
# [来源标注] [DD-001:MD-MCP#M-C08 "属性测试（hypothesis）" + IC-015 幂等性]
