"""structlog 结构化日志配置.

[文件路径] src/agenthub/data/ts_log/log_config.py
[文件职责] structlog 启动时初始化；JSON Lines → stdout → Promtail → Loki
[所属模块] M-D02（来自DD-001）
[关联设计规范] FS-020 / MD-MCP M-D02 / IC-018
[功能描述]
  功能1: 配置 structlog processor chain（merge_contextvars / JSONRenderer）
  功能2: 注入 trace_id 上下文变量（从 OpenTelemetry 提取）
  功能3: 提供 get_logger(name) 工厂方法
[输入输出]
  输入: Settings（log_level / log_format / service_name）
  输出: 配置完成的 stdlib logger
[依赖关系]
  依赖文件: agenthub.core.config（Settings）
  被依赖文件: 全模块（log = get_logger(__name__)）
[注意事项]
  注意1: configure_logging 启动时调用一次，幂等
  注意2: JSON Lines 格式保证 Loki 兼容（[DD-001:IC-018]）
  注意3: 线程安全（structlog 内部 Processor 链无共享可变状态）
  注意4: 自身日志级别为 INFO（[DD-001:MD-MCP M-D02]）
[代码风格] 遵循CS-MCP §1
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D02 - 初始框架
[作者] DD-M-D02-20260603
[来源标注] [DD-001:FS-020 / MD-MCP M-D02 / IC-018]
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from agenthub.core.config import Settings


class LogConfig:
    """[类名] LogConfig.

    [职责] structlog 配置数据类 + 启动初始化.
    [关联设计规范] MD-MCP M-D02（LogConfig 类设计）
    [属性]
      属性1: level str - 日志级别（DEBUG/INFO/WARNING/ERROR）
      属性2: json_format bool - True=JSON Lines；False=Console
      属性3: service_name str - 注入到所有 log event
      属性4: inject_trace_id bool - 是否自动注入 trace_id
    [方法列表]
      方法1: configure_logging(settings) - 启动时初始化（静态）
      方法2: get_logger(name) - 工厂方法（静态）
    [异常处理]
      异常1: 无（启动失败由 Settings 校验阶段捕获）
    [来源标注] [DD-001:MD-MCP M-D02]
    """

    def __init__(
        self,
        level: str = "INFO",
        json_format: bool = True,
        service_name: str = "agenthub",
        inject_trace_id: bool = True,
    ) -> None:
        """初始化 LogConfig."""
        self.level: str = level
        self.json_format: bool = json_format
        self.service_name: str = service_name
        self.inject_trace_id: bool = inject_trace_id


def configure_logging(settings: Settings) -> None:
    """[函数名] configure_logging.

    [职责] structlog 启动时初始化（进程入口调用一次）.
    [关联接口契约] IC-018（logs.emit）
    [参数说明]
      参数1: settings Settings 必填 全局配置
    [返回值] 类型: None
    [前置条件] Settings 已加载；进程启动阶段
    [后置条件] stdlib root logger 已配置；structlog Processor 链已绑定
    [并发安全] 启动期单次调用
    [幂等性] 重复调用会覆盖（设计意图）
    [性能约束] 启动期 < 50ms
    [来源标注] [DD-001:IC-018 / MD-MCP M-D02 LogConfig]
    """
    raise NotImplementedError


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """[函数名] get_logger.

    [职责] 工厂方法：获取带服务名/trace 上下文的 logger.
    [关联接口契约] IC-018（logs.emit）
    [参数说明]
      参数1: name str 必填 通常传 __name__
    [返回值] 类型: structlog.stdlib.BoundLogger
    [并发安全] structlog 线程安全
    [来源标注] [DD-001:IC-018 / CS-MCP §1.5 log = get_logger(__name__)]
    """
    raise NotImplementedError
