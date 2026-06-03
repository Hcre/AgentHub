"""M-C02 K4 Analyzer - Rule_TemplateInject 模板注入规则.

[文件路径] src/agenthub/infrastructure/k4/rules/template_inject.py
[文件职责] 检测 jinja2/Mako 模板未关闭自动转义
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + FS-011
[代码风格] 遵循 CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[作者] DD-M-C02-20260603
[来源标注] [DD-M推断:依据 jinja2/Mako SSTI]
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from agenthub.infrastructure.k4.rules.base import SEVERITY_MEDIUM, Rule

if TYPE_CHECKING:
    from agenthub.infrastructure.k4.analyzer import MatchResult


class Rule_TemplateInject(Rule):
    """SSTI 模板注入检测.

    [类名] Rule_TemplateInject
    [职责] 检测 jinja2.Environment(autoescape=False) / Mako Template
    [属性]
      属性1: name "TemplateInject"
      属性2: severity 60
    [方法列表]
      方法1: match(node) -> MatchResult | None
    [来源标注] [DD-M推断:依据 jinja2 SSTI]
    """

    name: str = "TemplateInject"
    severity: int = SEVERITY_MEDIUM

    def match(self, node: ast.AST) -> MatchResult | None:
        """匹配 autoescape=False 的 jinja2 Environment.

        [函数名] match
        [参数说明]
          参数1: node ast.AST 必填
        [返回值]
          类型: MatchResult | None
        [来源标注] [DD-M推断:依据 jinja2 SSTI]
        """
        # 业务代码占位
        raise NotImplementedError
