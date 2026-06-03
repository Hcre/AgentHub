"""M-C02 K4 Analyzer - Rule_WeakHash 弱哈希算法规则.

[文件路径] src/agenthub/infrastructure/k4/rules/weak_hash.py
[文件职责] 检测 md5 / sha1 等弱哈希算法
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + FS-011
[代码风格] 遵循 CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[作者] DD-M-C02-20260603
[来源标注] [DD-M推断:依据 NIST 弱哈希禁用清单]
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from agenthub.infrastructure.k4.rules.base import SEVERITY_MEDIUM, Rule

if TYPE_CHECKING:
    from agenthub.infrastructure.k4.analyzer import MatchResult


class Rule_WeakHash(Rule):
    """弱哈希算法检测.

    [类名] Rule_WeakHash
    [职责] 检测 hashlib.md5 / hashlib.sha1 等
    [属性]
      属性1: name "WeakHash"
      属性2: severity 50
    [方法列表]
      方法1: match(node) -> MatchResult | None
    [来源标注] [DD-M推断:依据 NIST 弱哈希清单]
    """

    name: str = "WeakHash"
    severity: int = SEVERITY_MEDIUM

    def match(self, node: ast.AST) -> MatchResult | None:
        """匹配 hashlib.md5/sha1 调用.

        [函数名] match
        [参数说明]
          参数1: node ast.AST 必填
        [返回值]
          类型: MatchResult | None
        [来源标注] [DD-M推断:依据 NIST 弱哈希清单]
        """
        # 业务代码占位
        raise NotImplementedError
