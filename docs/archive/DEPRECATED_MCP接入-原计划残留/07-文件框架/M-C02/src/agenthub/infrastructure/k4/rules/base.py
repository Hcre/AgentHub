"""M-C02 K4 Analyzer - Rule 策略抽象基类.

[文件路径] src/agenthub/infrastructure/k4/rules/base.py
[文件职责] 定义 Rule 抽象策略接口与 RuleRegistry 注册表
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + FS-011 + DP-MCP-V1.0#Strategy
[功能描述]
  功能1: 定义 Rule ABC 策略接口（match + name + version + severity）
  功能2: 定义 RuleRegistry 注册表（线程安全 + 迭代稳定）
  功能3: 定义 SEVERITY_* 常量（高/中/低）
[输入输出]
  输入: AST 节点（Call/Name/Assign 等）
  输出: MatchResult 或 None
[依赖关系]
  依赖文件: 无（仅依赖 ast 标准库）
  被依赖文件: rules/*.py（12 个具体规则）+ analyzer.py
[注意事项]
  注意1: 规则无状态，所有数据从 AST 派生，禁止访问全局状态
  注意2: 规则实现禁止 IO（不允许读文件/网络）
  注意3: 严重度 0-100，定义见 SEVERITY_HIGH/MEDIUM/LOW
[代码风格] 遵循 CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C02 - 初始版本
[作者] DD-M-C02-20260603
[来源标注] [DD-001:MD-MCP-V1.0#M-C02 + DP-MCP-V1.0#Strategy]
"""
from __future__ import annotations

import abc
import ast
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from agenthub.infrastructure.k4.analyzer import MatchResult

# 严重度常量
SEVERITY_HIGH: int = 80
SEVERITY_MEDIUM: int = 50
SEVERITY_LOW: int = 20


class Rule(abc.ABC):
    """K4 规则抽象基类（Strategy 接口）.

    [类名] Rule
    [职责] 定义单条规则的 match 接口
    [关联设计规范] MD-MCP-V1.0#M-C02
    [属性]
      属性1: name str 规则名（子类必填）
      属性2: version str 规则版本（默认 "1.0"）
      属性3: severity int 默认严重度（0-100）
    [方法列表]
      方法1: match(node: ast.AST) -> MatchResult | None
    [状态机] 无
    [异常处理]
      异常1: 不抛业务异常（match 失败返回 None）
    [来源标注] [DD-001:MD-MCP-V1.0#M-C02 + DP-MCP-V1.0#Strategy]
    """

    name: str = "BaseRule"
    version: str = "1.0"
    severity: int = SEVERITY_MEDIUM

    @abc.abstractmethod
    def match(self, node: ast.AST) -> MatchResult | None:
        """对单 AST 节点执行匹配.

        [函数名] match
        [职责] 判断节点是否命中当前规则
        [参数说明]
          参数1: node ast.AST 必填
        [返回值]
          类型: MatchResult | None
          特殊值: None = 未命中
        [并发安全] 规则无状态
        [幂等性] 是；同 node → 同结果
        [来源标注] [DD-001:MD-MCP-V1.0#M-C02]
        """
        raise NotImplementedError

    def matches(self, tree: ast.AST) -> list[MatchResult]:
        """对整棵 AST 树执行规则匹配（遍历所有节点）.

        [函数名] matches
        [职责] 遍历 ast.walk 并逐节点调用 match
        [参数说明]
          参数1: tree ast.AST 必填
        [返回值]
          类型: list[MatchResult]
        [来源标注] [DD-M推断:依据 Strategy 模式遍历语义]
        """
        # 业务代码占位
        raise NotImplementedError


class RuleRegistry:
    """规则注册表（线程安全）.

    [类名] RuleRegistry
    [职责] 管理 12 类规则的注册与迭代
    [关联设计规范] MD-MCP-V1.0#M-C02
    [属性]
      属性1: _rules dict[str, Rule] 规则字典
      属性2: _lock threading.RLock 线程锁
    [方法列表]
      方法1: register(rule: Rule) -> None
      方法2: all() -> tuple[Rule, ...]
      方法3: get(name: str) -> Rule | None
    [状态机] 无
    [异常处理]
      异常1: DuplicateRuleError - name 重复
    [来源标注] [DD-M推断:依据 Strategy + Registry 模式]
    """

    def __init__(self) -> None:
        """初始化注册表.

        [函数名] __init__
        [来源标注] [DD-M推断:依据线程安全注册表]
        """
        self._rules: dict[str, Rule] = {}
        self._lock: threading.RLock = threading.RLock()

    def register(self, rule: Rule) -> None:
        """注册单条规则.

        [函数名] register
        [职责] 注册并防重
        [参数说明]
          参数1: rule Rule 必填
        [错误码]
          错误码1: DuplicateRuleError - name 重复
        [并发安全] RLock
        [来源标注] [DD-M推断:依据 Registry 模式]
        """
        # 业务代码占位
        raise NotImplementedError

    def all(self) -> tuple[Rule, ...]:
        """返回所有规则（按注册顺序）.

        [函数名] all
        [职责] 迭代注册表
        [返回值]
          类型: tuple[Rule, ...]
        [来源标注] [DD-M推断:依据 Strategy 模式]
        """
        # 业务代码占位
        raise NotImplementedError

    def get(self, name: str) -> Rule | None:
        """按 name 查询规则.

        [函数名] get
        [职责] 单点查询
        [参数说明]
          参数1: name str 必填
        [返回值]
          类型: Rule | None
        [来源标注] [DD-M推断:依据 Registry 模式]
        """
        # 业务代码占位
        raise NotImplementedError
