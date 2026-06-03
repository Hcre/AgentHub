"""M-C02 K4 Analyzer - Rule_ShellInject shell 注入规则.

[文件路径] src/agenthub/infrastructure/k4/rules/shell_inject.py
[文件职责] 检测 os.system / os.popen 等 shell 命令注入
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + FS-011
[功能描述]
  功能1: 匹配 os.system / os.popen / os.exec* 调用
  功能2: 配合 subprocess shell=True 二次校验
[输入输出]
  输入: ast.Call
  输出: MatchResult | None
[依赖关系]
  依赖文件: base.py
  被依赖文件: rules/__init__.py
[代码风格] 遵循 CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[作者] DD-M-C02-20260603
[来源标注] [DD-M推断:依据 CWE-78 OS 命令注入]
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from agenthub.infrastructure.k4.rules.base import SEVERITY_HIGH, Rule

if TYPE_CHECKING:
    from agenthub.infrastructure.k4.analyzer import MatchResult


class Rule_ShellInject(Rule):
    """os.system / os.popen shell 注入检测.

    [类名] Rule_ShellInject
    [职责] 检测 shell 命令注入
    [属性]
      属性1: name "ShellInject"
      属性2: severity 90
    [方法列表]
      方法1: match(node) -> MatchResult | None
    [来源标注] [DD-M推断:依据 CWE-78]
    """

    name: str = "ShellInject"
    severity: int = SEVERITY_HIGH

    def match(self, node: ast.AST) -> MatchResult | None:
        """匹配 os.system / os.popen 调用.

        [函数名] match
        [参数说明]
          参数1: node ast.AST 必填
        [返回值]
          类型: MatchResult | None
        [来源标注] [DD-M推断:依据 CWE-78]
        """
        # 业务代码占位
        raise NotImplementedError
