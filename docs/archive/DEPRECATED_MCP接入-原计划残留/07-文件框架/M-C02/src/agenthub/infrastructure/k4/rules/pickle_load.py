"""M-C02 K4 Analyzer - Rule_PickleLoad 反序列化规则.

[文件路径] src/agenthub/infrastructure/k4/rules/pickle_load.py
[文件职责] 检测 pickle.load/loads 不安全反序列化
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + FS-011
[功能描述]
  功能1: 匹配调用 pickle.load/loads/pickle.loads
  功能2: 高严重度（90）—— RCE 风险
  功能3: 修复建议：使用 json 或限制白名单
[输入输出]
  输入: ast.Call 节点
  输出: MatchResult 或 None
[依赖关系]
  依赖文件: base.py
  被依赖文件: rules/__init__.py
[注意事项]
  注意1: 仅匹配函数名 pickle.load/loads，不限定 import 方式
  注意2: cPickle 与 _pickle 同样识别（Python 2/3 兼容）
[代码风格] 遵循 CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C02 - 初始版本
[作者] DD-M-C02-20260603
[来源标注] [DD-M推断:依据 OWASP A8:2021 Insecure Deserialization]
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from agenthub.infrastructure.k4.rules.base import SEVERITY_HIGH, Rule

if TYPE_CHECKING:
    from agenthub.infrastructure.k4.analyzer import MatchResult


class Rule_PickleLoad(Rule):
    """pickle.load/loads 不安全反序列化检测.

    [类名] Rule_PickleLoad
    [职责] 检测 pickle 反序列化调用
    [关联设计规范] MD-MCP-V1.0#M-C02
    [属性]
      属性1: name "PickleLoad"
      属性2: severity 90
    [方法列表]
      方法1: match(node) -> MatchResult | None
    [状态机] 无
    [异常处理] 不抛异常
    [来源标注] [DD-M推断:依据 OWASP 不安全反序列化]
    """

    name: str = "PickleLoad"
    severity: int = SEVERITY_HIGH

    def match(self, node: ast.AST) -> MatchResult | None:
        """匹配 pickle.load/loads 调用.

        [函数名] match
        [职责] 命中后返回 MatchResult
        [参数说明]
          参数1: node ast.AST 必填
        [返回值]
          类型: MatchResult | None
        [来源标注] [DD-M推断:依据 Rule ABC]
        """
        # 业务代码占位
        raise NotImplementedError
