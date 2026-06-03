"""M-A01 MetricsMiddleware — Prometheus 指标上报.

[文件路径] src/agenthub/access/api_gateway/middleware/metrics.py
[文件职责] 记录 HTTP 请求计数 / 延迟直方图 / 状态码分布
[所属模块] M-A01 Web API Gateway
[关联设计规范] FS-001 / MD:M-A01 子模块 middleware/ metrics 上报
[功能描述]
  功能1: 在请求开始时记录起始时间
  功能2: 在响应返回前记录 endpoint / method / status / latency_ms
  功能3: 通过 MetricsRegistry（M-D02 跨模块接口）注册的 counter/histogram 上报
  功能4: 暴露 /metrics 端点（白名单路径，跳过 Auth / RateLimit）
[输入输出]
  输入: starlette.Request
  输出: 透传 + Prometheus 指标累加
[依赖关系]
  依赖文件: agenthub.data.ts_log.metrics (M-D02 跨模块，仅消费 MetricsRegistry 接口)
  被依赖文件: ../app.py
[注意事项]
  注意1: 高基数 label（如 path 含 UUID）会导致 Prom 内存暴涨——必须做 path 模板化（/v1/pool/{id} → /v1/pool/:id）
  注意2: latency 单位 ms（histogram buckets: 5/10/25/50/100/250/500/1000/2500/5000）
  注意3: /metrics 端点的指标采集本身不应再上报指标，避免递归
[代码风格] 遵循 CS-MCP-V1.0 §1
[创建日期] 2026-06-03
[修改历史] 2026-06-03: DD-M-A01 - 初版
[作者] DD-M-A01-20260603
[来源标注] [DD-001:FS-001 + MD:M-A01]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response


# ============================================================================
# [类] MetricsMiddleware
# ----------------------------------------------------------------------------
# [职责] 请求级 Prometheus 指标上报
# [关联设计规范] MD:M-A01 + IC-018 metrics.expose
# [属性]
#   request_counter: Counter   - http_requests_total{method,endpoint,status}
#   latency_hist: Histogram    - http_request_duration_ms{method,endpoint}
# [方法列表]
#   __init__(app, registry) → None
#   __call__(request, call_next) → Response
# [状态机] 无
# [异常处理] Prom 上报失败仅记 WARN，绝不影响业务
# [来源标注] [DD-001:MD M-A01 + IC-018]
# ============================================================================
class MetricsMiddleware:
    """Prometheus metrics middleware (counter + histogram)."""

    async def __call__(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Record latency and status into Prometheus metrics."""
        ...


# ============================================================================
# [函数] _normalize_endpoint
# [职责] 将 path 模板化以降低 Prometheus 基数
# [参数说明]
#   path: str 必填 - request.url.path
# [返回值]
#   类型: str
#   描述: 形如 "/v1/pool/:id" 而非 "/v1/pool/<uuid>"
# [并发安全] 是（纯函数）
# [幂等性] 是
# [性能约束] < 0.05ms
# [来源标注] [DD-M-A01推断:依据 高基数 label 导致 Prom 内存暴涨的最佳实践]
# ============================================================================
def _normalize_endpoint(path: str) -> str:
    """Reduce label cardinality by replacing UUIDs with `:id`.

    Args:
        path: Raw request path.

    Returns:
        Templated path safe for Prometheus labels.
    """
    ...
