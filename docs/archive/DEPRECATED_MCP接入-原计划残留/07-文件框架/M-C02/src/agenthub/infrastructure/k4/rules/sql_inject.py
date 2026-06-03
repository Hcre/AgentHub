"""M-C02 K4 Analyzer - Rule_SQLInject SQL 注入规则.

[文件路径] src/agenthub/infrastructure/k4/rules/sql_inject.py
[文件职责] 检测字符串拼接或 %-format 构造的 SQL
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + FS-011
[代码风格] 遵循 CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[作者] DD-M-C02-20260603
[来源标注] [DD-M推断:依据 CWE-89 SQL 注入]
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from agenthub.infrastructure.k4.rules.base import SEVERITY_HIGH, Rule

if TYPE_CHECKING:
    from agenthub.infrastructure.k4.analyzer import MatchResult


class Rule_SQLInject(Rule):
    """SQL 字符串拼接检测.

    [类名] Rule_SQLInject
    [职责] 检测 execute()/executemany() 中字符串拼接 SQL
    [属性]
      属性1: name "SQLInject"
      属性2: severity 80
    [方法列表]
      方法1: match(node) -> MatchResult | None
    [来源标注] [DD-M推断:依据 CWE-89]
    """

    name: str = "SQLInject"
    severity: int = SEVERITY_HIGH

    def match(self, node: ast.AST) -> MatchResult | None:
        """匹配字符串拼接作为 execute() 参数.

        [函数名] match
        [参数说明]
          参数1: node ast.AST 必填
        [返回值]
          类型: MatchResult | None
        [来源标注] [DD-M推断:依据 CWE-89]
        """
        # 业务代码占位
        raise NotImplementedError
