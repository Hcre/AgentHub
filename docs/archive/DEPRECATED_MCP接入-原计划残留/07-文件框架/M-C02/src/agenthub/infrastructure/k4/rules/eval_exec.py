"""M-C02 K4 Analyzer - Rule_EvalExec eval/exec 动态执行规则.

[文件路径] src/agenthub/infrastructure/k4/rules/eval_exec.py
[文件职责] 检测 eval/exec/compile 等动态代码执行
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + FS-011
[功能描述]
  功能1: 匹配内置 eval/exec/compile 调用
  功能2: 高严重度（90）—— 代码注入风险
[输入输出]
  输入: ast.Call 节点
  输出: MatchResult 或 None
[依赖关系]
  依赖文件: base.py
  被依赖文件: rules/__init__.py
[注意事项]
  注意1: 不区分 builtins 与本地重命名（属性访问同样识别）
  注意2: literal eval 不豁免（仍建议 ast.literal_eval）
[代码风格] 遵循 CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[作者] DD-M-C02-20260603
[来源标注] [DD-M推断:依据 eval/exec 注入防护]
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from agenthub.infrastructure.k4.rules.base import SEVERITY_HIGH, Rule

if TYPE_CHECKING:
    from agenthub.infrastructure.k4.analyzer import MatchResult


class Rule_EvalExec(Rule):
    """eval/exec 动态执行检测.

    [类名] Rule_EvalExec
    [职责] 检测动态代码执行
    [关联设计规范] MD-MCP-V1.0#M-C02
    [属性]
      属性1: name "EvalExec"
      属性2: severity 90
    [方法列表]
      方法1: match(node) -> MatchResult | None
    [状态机] 无
    [异常处理] 不抛异常
    [来源标注] [DD-M推断:依据 CWE-94 代码注入]
    """

    name: str = "EvalExec"
    severity: int = SEVERITY_HIGH

    def match(self, node: ast.AST) -> MatchResult | None:
        """匹配 eval/exec/compile 调用.

        [函数名] match
        [参数说明]
          参数1: node ast.AST 必填
        [返回值]
          类型: MatchResult | None
        [来源标注] [DD-M推断:依据 CWE-94]
        """
        # 业务代码占位
        raise NotImplementedError
