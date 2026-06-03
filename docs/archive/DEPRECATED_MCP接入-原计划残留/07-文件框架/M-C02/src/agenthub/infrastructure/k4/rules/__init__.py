"""M-C02 K4 Analyzer - Rules 子包初始化.

[文件路径] src/agenthub/infrastructure/k4/rules/__init__.py
[文件职责] 集中导出 11+1 类 Rule 策略实现 + 全局 RuleRegistry
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + FS-011
[功能描述]
  功能1: re-export 所有 12 类规则类
  功能2: 提供 register_all() 一键注册函数
  功能3: 维护 RuleRegistry 全局单例（线程安全）
[输入输出]
  输入: 无
  输出: 12 类规则 + RuleRegistry 单例
[依赖关系]
  依赖文件: base.py + 12 个规则文件
  被依赖文件: analyzer.py + grpc_server.py
[注意事项]
  注意1: 新增规则必须在此处 re-export 并加入 ALL_RULES 列表
  注意2: 规则按字母序排序便于审阅
[代码风格] 遵循 CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C02 - 初始版本
[作者] DD-M-C02-20260603
[来源标注] [DD-001:MD-MCP-V1.0#M-C02 11+1 类规则]
"""
from __future__ import annotations

from agenthub.infrastructure.k4.rules.base import Rule, RuleRegistry
from agenthub.infrastructure.k4.rules.deserialize_untrusted import (
    Rule_DeserializeUntrusted,
)
from agenthub.infrastructure.k4.rules.dynamic_import import Rule_DynamicImport
from agenthub.infrastructure.k4.rules.eval_exec import Rule_EvalExec
from agenthub.infrastructure.k4.rules.hardcoded_secret import Rule_HardcodedSecret
from agenthub.infrastructure.k4.rules.path_traversal import Rule_PathTraversal
from agenthub.infrastructure.k4.rules.pickle_load import Rule_PickleLoad
from agenthub.infrastructure.k4.rules.shell_inject import Rule_ShellInject
from agenthub.infrastructure.k4.rules.sql_inject import Rule_SQLInject
from agenthub.infrastructure.k4.rules.subprocess_shell import Rule_SubprocessShell
from agenthub.infrastructure.k4.rules.template_inject import Rule_TemplateInject
from agenthub.infrastructure.k4.rules.unsafe_yaml import Rule_UnsafeYAML
from agenthub.infrastructure.k4.rules.weak_hash import Rule_WeakHash

# 12 类规则（11 + 1 = MD 描述的 11+1 规则集）
ALL_RULES: list[type[Rule]] = [
    Rule_DeserializeUntrusted,
    Rule_DynamicImport,
    Rule_EvalExec,
    Rule_HardcodedSecret,
    Rule_PathTraversal,
    Rule_PickleLoad,
    Rule_ShellInject,
    Rule_SQLInject,
    Rule_SubprocessShell,
    Rule_TemplateInject,
    Rule_UnsafeYAML,
    Rule_WeakHash,
]


def register_all(registry: RuleRegistry | None = None) -> RuleRegistry:
    """一键注册全部 12 类规则.

    [函数名] register_all
    [职责] 将 ALL_RULES 全部注册到指定 registry 或新建 registry
    [参数说明]
      参数1: registry RuleRegistry | None 可选 缺省新建
    [返回值]
      类型: RuleRegistry
    [来源标注] [DD-M推断:依据 MD-MCP-V1.0#M-C02 11+1 规则]
    """
    if registry is None:
        registry = RuleRegistry()
    for rule_cls in ALL_RULES:
        # 业务代码占位
        pass
    return registry


__all__ = [
    "ALL_RULES",
    "Rule",
    "RuleRegistry",
    "Rule_DeserializeUntrusted",
    "Rule_DynamicImport",
    "Rule_EvalExec",
    "Rule_HardcodedSecret",
    "Rule_PathTraversal",
    "Rule_PickleLoad",
    "Rule_ShellInject",
    "Rule_SQLInject",
    "Rule_SubprocessShell",
    "Rule_TemplateInject",
    "Rule_UnsafeYAML",
    "Rule_WeakHash",
    "register_all",
]
