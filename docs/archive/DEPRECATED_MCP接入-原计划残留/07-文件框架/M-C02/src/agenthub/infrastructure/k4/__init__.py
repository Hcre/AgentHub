"""M-C02 K4 Analyzer 模块初始化文件.

[文件路径] src/agenthub/infrastructure/k4/__init__.py
[文件职责] K4 Analyzer 模块入口，导出公共类与接口符号
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + FS-011 + IC-009
[功能描述]
  功能1: 暴露 ASTAnalyzer、K4Servicer、CorpusCalibrator 等公共类
  功能2: 暴露 Rule 策略集合（11+1 类）便于外部注册自定义规则
  功能3: 集中管理规则集版本常量
[输入输出]
  输入: 无（模块级常量与符号导出）
  输出: 对外可见的类、函数、版本常量
[依赖关系]
  依赖文件: analyzer.py / grpc_server.py / corpus.py / rules/*.py
  被依赖文件: M-B05(application/create) / M-A01(access/api_gateway) / DD-S(结构设计师)
[注意事项]
  注意1: 严禁在 __init__ 引入 gRPC stub（k4_pb2_grpc）以避免 protobuf 缺失时阻塞导入
  注意2: 公共符号必须显式 __all__ 声明，避免污染命名空间
  注意3: 任何新增 Rule 子类必须在此处 re-export 并写入 RULE_REGISTRY
[代码风格] 遵循 CS-MCP-V1.0-20260602（Python Google Docstring + mypy strict）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C02 - 初始版本，导出 K4 模块公共符号
[作者] DD-M-C02-20260603
[来源标注] [DD-001:MD-MCP-V1.0#M-C02 + FS-011 + IC-009]
"""
from __future__ import annotations

from agenthub.infrastructure.k4.analyzer import (
    ASTAnalyzer,
    MatchResult,
    ScoreResult,
)
from agenthub.infrastructure.k4.corpus import (
    CalibrationReport,
    CorpusCalibrator,
)
from agenthub.infrastructure.k4.grpc_server import K4Servicer
from agenthub.infrastructure.k4.rules.base import Rule, RuleRegistry

# 模块级常量：K4 规则集版本与 Worker Pool 大小
RULE_SET_VERSION: str = "v1.0.0"
WORKER_POOL_SIZE: int = 8
QUEUE_MAX_SIZE: int = 100
ANALYZE_TIMEOUT_SEC: int = 10
MANIFEST_MAX_BYTES: int = 1 * 1024 * 1024  # 1MB

__all__ = [
    "ASTAnalyzer",
    "CalibrationReport",
    "CorpusCalibrator",
    "K4Servicer",
    "MANIFEST_MAX_BYTES",
    "MatchResult",
    "RULE_SET_VERSION",
    "Rule",
    "RuleRegistry",
    "ScoreResult",
    "WORKER_POOL_SIZE",
    "ANALYZE_TIMEOUT_SEC",
    "QUEUE_MAX_SIZE",
]
