"""agenthub.data.ts_log - TS & Log 模块（M-D02）.

本包提供：
  - Prometheus 指标注册与暴露（/metrics 端点）
  - structlog 结构化日志配置（JSON Lines → Promtail → Loki）
  - OpenTelemetry trace_id 注入辅助

设计模式: Observer + Pub/Sub（Prom 拉模式 + Loki 推模式）。
[DD-001:MD-MCP M-D02 + FS-MCP FS-020]
"""
from agenthub.data.ts_log.metrics import MetricsRegistry, get_counter, get_gauge, get_histogram
from agenthub.data.ts_log.log_config import LogConfig, configure_logging, get_logger

__all__ = [
    "MetricsRegistry",
    "get_counter",
    "get_gauge",
    "get_histogram",
    "LogConfig",
    "configure_logging",
    "get_logger",
]
