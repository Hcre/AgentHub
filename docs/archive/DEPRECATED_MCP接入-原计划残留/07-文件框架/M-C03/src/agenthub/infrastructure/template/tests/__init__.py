"""M-C03 Template Engine tests package.

[文件路径] src/agenthub/infrastructure/template/tests/__init__.py
[文件职责] 测试包初始化与公共 pytest fixture 声明
[所属模块] M-C03（来自DD-001）
[关联设计规范] FS-012 / CS-MCP-V1.0-20260602 §1.7
[功能描述]
  功能1: 标记 tests 目录为 Python 包，便于 pytest 收集
  功能2: 集中声明模块级 fixture，避免各测试文件重复
[输入输出]
  输入: 无
  输出: 暴露符号：sample_base / sample_override / sample_schema / frozen_mutation_guard
[依赖关系]
  依赖文件: pytest
  被依赖文件: tests/test_merger.py / tests/test_schema.py
[注意事项]
  注意1: 任何需要 IO 的 fixture 必须显式 mock（[CS 1.7]）
  注意2: fixtures 必须放 __init__.py 或 conftest.py，禁止散落各测试文件
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.7
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-12 - 初版文件框架注释
[作者] DD-M-12-20260602
[来源标注] [DD-M推断:pytest 集中 fixture 实践]
"""

from __future__ import annotations

import pytest

__all__: list[str] = [
    "frozen_mutation_guard",
    "sample_base",
    "sample_override",
    "sample_schema",
]


@pytest.fixture
def sample_base() -> dict[str, object]:
    """示例 base fixture.

    [职责] 提供合并测试用基底
    [来源标注] [DD-M推断:测试 fixture]
    """
    return {
        "name": "base",
        "nested": {"a": 1, "b": 2, "list": [1, 2, 3]},
        "scalar": "from_base",
    }


@pytest.fixture
def sample_override() -> dict[str, object]:
    """示例 override fixture.

    [职责] 提供合并测试用覆盖层
    [来源标注] [DD-M推断:测试 fixture]
    """
    return {
        "nested": {"b": 20, "c": 3, "list": [4]},
        "extra": "from_override",
        "scalar": "from_override",
    }


@pytest.fixture
def sample_schema() -> dict[str, object]:
    """示例 JSON Schema 2020-12 fixture.

    [职责] 提供校验测试用 schema
    [来源标注] [DD-M推断:测试 fixture]
    """
    return {
        "$id": "https://agenthub.local/schemas/template.v1.json",
        "type": "object",
        "required": ["name"],
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "nested": {"type": "object"},
            "scalar": {"type": "string"},
            "extra": {"type": "string"},
        },
    }


@pytest.fixture
def frozen_mutation_guard() -> None:
    """frozen 模型变异检测 fixture（占位说明）.

    [职责] 通过上下文标记提醒测试：TemplateConfig 不可 in-place 修改
    [来源标注] [DD-M推断:测试约束]
    """
    return None
