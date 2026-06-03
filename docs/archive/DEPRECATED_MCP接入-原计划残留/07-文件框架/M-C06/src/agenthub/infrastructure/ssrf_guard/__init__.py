"""SSRF Guard 包初始化.

[文件路径] src/agenthub/infrastructure/ssrf_guard/__init__.py
[文件职责] M-C06 包初始化，导出 SSRFChain 公共入口与异常类型
[所属模块] M-C06（来自 DD-001）
[关联设计规范] FS-015 / MD-MCP-V1.0-20260602.md#M-C06
[功能描述]
  功能1: 导出 SSRFChain 类（chain.check 公共 API）
  功能2: 导出 CheckResult 数据类（pass/block + reason）
  功能3: 导出 SSRFAttempt 异常（被 M-B05 / M-C02 捕获）
[输入输出]
  输入: 无（包初始化）
  输出: 符号: SSRFChain, CheckResult, SSRFAttempt, SSRFCheckError
[依赖关系]
  依赖文件: ./chain.py, ./validators/base.py, ./blacklist.py
  被依赖文件: M-B05 MCP Create (IC-007) / M-C02 K4 Analyzer (IC-009) / 上层调用方
[注意事项]
  注意1: 任何跨模块调用（如 M-C04 DNS Pinning）必须通过 type-only import 或延迟导入
  注意2: 包初始化无副作用；黑名单加载在首次 SSRFChain.check() 触发
[代码风格] 遵循 CS-001（来自 DD-001）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-15 - 初始版本
[作者] DD-M-15-20260603
[来源标注] [DD-001:FS-015 + MD-M-C06 + IC-013]
"""
from __future__ import annotations

from agenthub.infrastructure.ssrf_guard.chain import SSRFChain
from agenthub.infrastructure.ssrf_guard.exceptions import (
    SSRFAttempt,
    SSRFCheckError,
)
from agenthub.infrastructure.ssrf_guard.validators.base import CheckResult

__all__: list[str] = [
    "SSRFChain",
    "CheckResult",
    "SSRFAttempt",
    "SSRFCheckError",
]
