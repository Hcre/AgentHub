"""M-B03 Binding Engine 策略测试.

[文件路径] src/agenthub/application/binding/tests/test_strategies.py
[文件职责] 单元测试 BindingStrategy 的两个实现
[所属模块] M-B03
[关联设计规范] CS-MCP-V1.0-20260602 §1.7 + TD:BR-001~004
[测试场景]
  - test_default_transform_when_called_then_normalize_keys
  - test_default_default_mapping_when_called_then_empty
  - test_custom_transform_when_safe_then_returns_mapping
  - test_custom_transform_when_path_traversal_then_raises: key 含 ..
  - test_custom_transform_when_absolute_path_then_raises: key 含 /
  - test_custom_transform_when_too_long_then_value_error
[来源标注] [DD-M推断:基于 MD-MCP#M-B03 + SEC:SEC-011]
[创建日期] 2026-06-03
[作者] DD-M-B03-20260603
"""
from __future__ import annotations

import pytest

from agenthub.application.binding.exceptions import PathTraversalError
from agenthub.application.binding.strategies import (
    CustomMappingStrategy,
    DefaultMappingStrategy,
)


def test_default_transform_when_called_then_normalize_keys():
    s = DefaultMappingStrategy()
    out = s.transform({"alpha": "http://x"})
    # M-C08 transform: 6→8 hex
    assert all(len(k) >= 6 for k in out.keys())


def test_default_default_mapping_when_called_then_empty():
    s = DefaultMappingStrategy()
    assert s.default_mapping() == {}


def test_custom_transform_when_safe_then_returns_mapping():
    s = CustomMappingStrategy()
    out = s.transform({"alpha": "http://x"})
    assert "alpha" not in out  # normalized


def test_custom_transform_when_path_traversal_then_raises():
    s = CustomMappingStrategy()
    with pytest.raises(PathTraversalError):
        s.transform({"../etc": "x"})


def test_custom_transform_when_absolute_path_then_raises():
    s = CustomMappingStrategy()
    with pytest.raises(PathTraversalError):
        s.transform({"/abs": "x"})


def test_custom_transform_when_nul_then_raises():
    s = CustomMappingStrategy()
    with pytest.raises(PathTraversalError):
        s.transform({"a\x00b": "x"})


def test_custom_transform_when_too_long_then_value_error():
    s = CustomMappingStrategy()
    with pytest.raises(ValueError):
        s.transform({"a" * 200: "x"})
