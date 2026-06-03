"""M-A01 TraceMiddleware — trace_id 注入 + OpenTelemetry span.

[文件路径] src/agenthub/access/api_gateway/middleware/trace.py
[文件职责] 提取/生成 X-Trace-ID，启动 OTel span，写入 request.state.trace_id
[所属模块] M-A01 Web API Gateway
[关联设计规范] FS-001 / MD:M-A01 类设计 TraceMiddleware / IC-001 入参 X-Trace-ID
[功能描述]
  功能1: 优先使用客户端传入的 X-Trace-ID；缺失或非 UUID v4 则本地生成
  功能2: 注入到 request.state.trace_id；写入 OTel current span 的 attribute
  功能3: 响应头回写 X-Trace-ID 便于客户端关联
  功能4: 配合 structlog contextvars 实现跨协程日志关联
[输入输出]
  输入: starlette.Request.headers["X-Trace-ID"]（可选）
  输出: 透传 + 响应头 X-Trace-ID
[依赖关系]
  依赖文件: agenthub.core.tracing (OTel SDK)
            agenthub.core.logging (structlog contextvars)
  被依赖文件: ../app.py (最外层中间件)
[注意事项]
  注意1: 必须是中间件链最外层（最先进入），否则 trace_id 未注入时日志会缺失关联
  注意2: 生成 UUID v4 使用 stdlib uuid.uuid4()，避免引入随机性密码学库
  注意3: 长度上限 64 字符（防御性），超长截断 + WARN
[代码风格] 遵循 CS-MCP-V1.0 §1
[创建日期] 2026-06-03
[修改历史] 2026-06-03: DD-M-A01 - 初版
[作者] DD-M-A01-20260603
[来源标注] [DD-001:FS-001 + MD:M-A01 + IC-001 入参 X-Trace-ID]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response


# ============================================================================
# [类] TraceMiddleware
# ----------------------------------------------------------------------------
# [职责] trace_id 注入与 OTel span 启动
# [关联设计规范] MD:M-A01 类设计第 4 项
# [属性] 无（无状态）
# [方法列表]
#   __init__(app) → None
#   __call__(request, call_next) → Response
# [状态机] 无
# [异常处理] 无（即使 OTel 失败也不阻塞请求；记 WARN）
# [来源标注] [DD-001:MD M-A01]
# ============================================================================
class TraceMiddleware:
    """Trace id injection and OpenTelemetry span middleware."""

    async def __call__(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Inject trace_id and start OTel span."""
        ...


# ============================================================================
# [函数] inject_trace
# [职责] 解析/生成 trace_id 并写入 request.state
# [关联接口契约] IC-001 入参 X-Trace-ID 可选
# [参数说明]
#   request: Request 必填
# [返回值]
#   类型: str
#   描述: 32 字符 UUID v4 hex 或客户端传入值（≤ 64 字符）
# [错误码] 无
# [前置条件] 无
# [后置条件] request.state.trace_id 已设置
# [并发安全] 是
# [幂等性] 否（同请求重复调用会覆盖；但实际只调用一次）
# [性能约束] < 0.1ms
# [来源标注] [DD-001:MD M-A01 函数签名 inject_trace]
# ============================================================================
def inject_trace(request: Request) -> str:
    """Extract or generate trace_id and persist to request.state.

    Args:
        request: Starlette Request.

    Returns:
        Trace id string (UUID v4 hex by default).
    """
    ...
