"""M-C02 K4 Analyzer - Rule_SubprocessShell subprocess shell=True 规则.

[文件路径] src/agenthub/infrastructure/k4/rules/subprocess_shell.py
[文件职责] 检测 subprocess 调用中 shell=True 危险用法
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + FS-011
[功能描述]
  功能1: 匹配 subprocess.Popen/call/run/check_call 中 shell=True
  功能2: 强制推荐 list 形式参数
[输入输出]
  输入: ast.Call
  输出: MatchResult | None
[依赖关系]
  依赖文件: base.py
  被依赖文件: rules/__init__.py
[代码风格] 遵循 CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[作者] DD-M-C02-20260603
[来源标注] [DD-M推断:依据 subprocess shell 注入]
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from agenthub.infrastructure.k4.rules.base import SEVERITY_HIGH, Rule

if TYPE_CHECKING:
    from agenthub.infrastructure.k4.analyzer import MatchResult


class Rule_SubprocessShell(Rule):
    """subprocess shell=True 检测.

    [类名] Rule_SubprocessShell
    [职责] 检测 shell=True 用法
    [属性]
      属性1: name "SubprocessShell"
      属性2: severity 85
    [方法列表]
      方法1: match(node) -> MatchResult | None
    [来源标注] [DD-M推断:依据 subprocess 最佳实践]
    """

    name: str = "SubprocessShell"
    severity: int = SEVERITY_HIGH

    def match(self, node: ast.AST) -> MatchResult | None:
        """匹配 subprocess 调用中 shell=True 关键字.

        [函数名] match
        [参数说明]
          参数1: node ast.AST 必填
        [返回值]
          类型: MatchResult | None
        [来源标注] [DD-M推断:依据 subprocess 最佳实践]
        """
        # 业务代码占位
        raise NotImplementedError
