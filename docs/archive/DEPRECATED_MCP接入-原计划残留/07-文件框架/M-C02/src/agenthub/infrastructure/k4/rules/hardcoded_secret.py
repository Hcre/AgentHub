"""M-C02 K4 Analyzer - Rule_HardcodedSecret 硬编码密钥规则.

[文件路径] src/agenthub/infrastructure/k4/rules/hardcoded_secret.py
[文件职责] 检测源码中硬编码的 API key/token/password
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + FS-011
[代码风格] 遵循 CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[作者] DD-M-C02-20260603
[来源标注] [DD-M推断:依据 detect-secrets 模式]
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from agenthub.infrastructure.k4.rules.base import SEVERITY_HIGH, Rule

if TYPE_CHECKING:
    from agenthub.infrastructure.k4.analyzer import MatchResult


class Rule_HardcodedSecret(Rule):
    """硬编码密钥检测.

    [类名] Rule_HardcodedSecret
    [职责] 检测源码中疑似密钥的长字符串字面量
    [属性]
      属性1: name "HardcodedSecret"
      属性2: severity 80
    [方法列表]
      方法1: match(node) -> MatchResult | None
    [来源标注] [DD-M推断:依据 detect-secrets 模式]
    """

    name: str = "HardcodedSecret"
    severity: int = SEVERITY_HIGH

    def match(self, node: ast.AST) -> MatchResult | None:
        """匹配高熵字符串字面量赋值.

        [函数名] match
        [参数说明]
          参数1: node ast.AST 必填
        [返回值]
          类型: MatchResult | None
        [来源标注] [DD-M推断:依据 detect-secrets]
        """
        # 业务代码占位
        raise NotImplementedError
