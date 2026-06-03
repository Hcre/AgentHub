"""M-C02 K4 Analyzer - Rule_PathTraversal 路径穿越规则.

[文件路径] src/agenthub/infrastructure/k4/rules/path_traversal.py
[文件职责] 检测 open()/Path() 中未校验的 ../ 路径
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + FS-011
[代码风格] 遵循 CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[作者] DD-M-C02-20260603
[来源标注] [DD-M推断:依据 CWE-22 路径穿越]
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from agenthub.infrastructure.k4.rules.base import SEVERITY_MEDIUM, Rule

if TYPE_CHECKING:
    from agenthub.infrastructure.k4.analyzer import MatchResult


class Rule_PathTraversal(Rule):
    """路径穿越检测.

    [类名] Rule_PathTraversal
    [职责] 检测 open()/Path() 中含 ../ 或 /etc/passwd 等危险路径
    [属性]
      属性1: name "PathTraversal"
      属性2: severity 60
    [方法列表]
      方法1: match(node) -> MatchResult | None
    [来源标注] [DD-M推断:依据 CWE-22]
    """

    name: str = "PathTraversal"
    severity: int = SEVERITY_MEDIUM

    def match(self, node: ast.AST) -> MatchResult | None:
        """匹配 open()/Path() 调用中含 ../ 的字符串字面量.

        [函数名] match
        [参数说明]
          参数1: node ast.AST 必填
        [返回值]
          类型: MatchResult | None
        [来源标注] [DD-M推断:依据 CWE-22]
        """
        # 业务代码占位
        raise NotImplementedError
