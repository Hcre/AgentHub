# 接口注释清单 API-M-D02-MCP-V1.0-20260603

> M-D02 对应 IC-018 metrics.expose / logs.emit
> 实现文件: src/agenthub/data/ts_log/metrics.py, log_config.py, tracing.py

---

## API-D02-001 metrics.expose

```
[接口编号] API-D02-001
[关联契约] IC-018（[DD-001]）
[实现文件] src/agenthub/data/ts_log/metrics.py
[函数签名注释]
  def get_counter(name: str, labels: list[str]) -> prometheus_client.Counter:
      """
      获取或创建 Counter 指标.

      Args:
          name: 指标名（snake_case，必须以 agenthub_ 开头）
          labels: label 列表（基数必须可控，禁 trace_id/request_id）

      Returns:
          prometheus_client.Counter 实例（线程安全）

      Raises:
          ValueError: name 命名不合规

      Example:
          >>> c = get_counter("agenthub_request_total", ["endpoint", "status"])
          >>> c.labels(endpoint="/mcp", status="200").inc()
      """
[参数说明]
  参数1: name str 必填 指标名
  参数2: labels list[str] 必填 label 列表
[返回值说明] 类型: Counter
[错误码说明] PROM_DUPLICATED (prom client 内置) / PROM_EXPORT_FAILED
[来源标注] [DD-001:IC-018 / MD-MCP M-D02]
```

## API-D02-002 logs.emit

```
[接口编号] API-D02-002
[关联契约] IC-018
[实现文件] src/agenthub/data/ts_log/log_config.py
[函数签名注释]
  def get_logger(name: str) -> structlog.stdlib.BoundLogger:
      """
      获取带 trace_id 上下文的 structlog logger.

      Args:
          name: 通常传 __name__

      Returns:
          BoundLogger（可 .bind(req_id=...) / .info(event, **kw)）

      Example:
          >>> log = get_logger(__name__)
          >>> log.info("user_login", user_id=str(uid), trace_id=...)
      """
[参数说明] 参数1: name str 必填
[返回值说明] 类型: structlog.stdlib.BoundLogger
[错误码说明] 无（logging 失败不抛，转交 stdlib root logger）
[来源标注] [DD-001:IC-018]
```

## API-D02-003 configure_logging

```
[接口编号] API-D02-003
[关联契约] IC-018
[实现文件] src/agenthub/data/ts_log/log_config.py
[函数签名注释]
  def configure_logging(settings: Settings) -> None:
      """
      启动时初始化 structlog（进程入口调用一次）.

      Args:
          settings: 全局 Settings（log_level / service_name / env）

      Raises:
          ValueError: log_level 非法
      """
[参数说明] 参数1: settings Settings 必填
[返回值说明] None
[来源标注] [DD-001:IC-018 / MD-MCP M-D02 LogConfig]
```

## API-D02-004 trace.get_current

```
[接口编号] API-D02-004
[关联契约] IC-018（trace_id 上下文）
[实现文件] src/agenthub/data/ts_log/tracing.py
[函数签名注释]
  def get_current_trace_id() -> str | None:
      """
      获取当前协程上下文的 trace_id（UUID v4）.

      Returns:
          trace_id 字符串；无 OTel 上下文时返回 None
      """
[来源标注] [DD-M推断:MD-MCP M-D02 tracing 子模块]
```

---

[来源标注] [DD-001:IC-018] 全覆盖
