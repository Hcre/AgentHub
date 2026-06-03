"""M-C02 K4 Analyzer - Rule_DeserializeUntrusted 不受信反序列化规则.

[文件路径] src/agenthub/infrastructure/k4/rules/deserialize_untrusted.py
[文件职责] 检测 marshal/shelve/dill 等非受信反序列化
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + FS-011
[代码风格] 遵循 CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[作者] DD-M-C02-20260603
[来源标注] [DD-M推断:依据非受信反序列化风险]
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from agenthub.infrastructure.k4.rules.base import SEVERITY_HIGH, Rule

if TYPE_CHECKING:
    from agenthub.infrastructure.k4.analyzer import MatchResult


class Rule_DeserializeUntrusted(Rule):
    """非受信反序列化检测（marshal/shelve/dill）.

    [类名] Rule_DeserializeUntrusted
    [职责] 检测 marshal/shelve/dill 等反序列化
    [属性]
      属性1: name "DeserializeUntrusted"
      属性2: severity 85
    [方法列表]
      方法1: match(node) -> MatchResult | None
    [来源标注] [DD-M推断:依据非受信反序列化]
    """

    name: str = "DeserializeUntrusted"
    severity: int = SEVERITY_HIGH

    def match(self, node: ast.AST) -> MatchResult | None:
        """匹配 marshal.load/shelve.open/dill.load 调用.

        [函数名] match
        [参数说明]
          参数1: node ast.AST 必填
        [返回值]
          类型: MatchResult | None
        [来源标注] [DD-M推断:依据非受信反序列化]
        """
        # 业务代码占位
        raise NotImplementedError
