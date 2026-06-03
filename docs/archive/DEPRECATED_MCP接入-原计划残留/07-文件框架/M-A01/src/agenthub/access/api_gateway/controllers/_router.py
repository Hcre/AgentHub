"""M-A01 统一路由分发器 — Adapter 模式适配上游 M-B0x.

[文件路径] src/agenthub/access/api_gateway/controllers/_router.py
[文件职责] 定义 APIRouter，将 HTTPS 请求按 path 适配/转发到 M-B01~M-B05
[所属模块] M-A01 Web API Gateway
[关联设计规范] FS-001 / MD:M-A01 设计模式 Adapter / IC-001
[功能描述]
  功能1: 声明 /v1/market/*  → M-B01 controllers (Market Service)
  功能2: 声明 /v1/pool/*    → M-B02 controllers (Process Pool)
  功能3: 声明 /v1/binding/* → M-B03 controllers (Binding Engine)
  功能4: 声明 /v1/approval/* → M-B04 controllers (Approval Engine)
  功能5: 声明 /v1/mcp/*     → M-B05 controllers (MCP Create)
  功能6: 统一响应包装 {code, message, trace_id, data, timestamp}（IC-001 出参契约）
[输入输出]
  输入: starlette.Request（path / method / body / headers）
  输出: starlette.Response（JSON 包装格式见 IC-001）
[依赖关系]
  依赖文件: ../schemas/__init__.py（Pydantic 请求/响应模型）
            ../middleware/auth.py 注入的 request.state.jwt_claims
            ../middleware/trace.py 注入的 request.state.trace_id
  被依赖文件: ../app.py（通过 register_routes 挂载）
[注意事项]
  注意1: 本文件只做适配/转发，不实现业务逻辑（[D7 模块边界守护]：禁止在此实现 M-B0x 业务）
  注意2: 上游 Service 必须通过 Depends() 注入，禁止直接 import M-B0x 内部类（[DD-001:CS §1.5 禁止跨层 import]）
  注意3: 文件名带下划线前缀表示内部组件，外部仅消费 controllers.api_router
[代码风格] 遵循 CS-MCP-V1.0 §1
[创建日期] 2026-06-03
[修改历史] 2026-06-03: DD-M-A01 - 初版
[作者] DD-M-A01-20260603
[来源标注] [DD-001:FS-001 + MD:M-A01 设计模式 Adapter + IC-001]
"""

from __future__ import annotations

# ============================================================================
# [模块级常量] ROUTE_PREFIX_MAP
# ----------------------------------------------------------------------------
# [职责] path 前缀 → 上游模块映射（仅文档化用途，运行时由 include_router 实现）
# [类型] dict[str, str]
# [来源标注] [DD-001:MD M-A01 子模块拆分 routing/]
# ============================================================================
# ROUTE_PREFIX_MAP: dict[str, str] = {
#     "/v1/market":   "M-B01",
#     "/v1/pool":     "M-B02",
#     "/v1/binding":  "M-B03",
#     "/v1/approval": "M-B04",
#     "/v1/mcp":      "M-B05",
# }


# ============================================================================
# [模块级符号] api_router
# ----------------------------------------------------------------------------
# [职责] fastapi.APIRouter 实例，挂载所有 /v1/* 子路由
# [类型] fastapi.APIRouter
# [使用] from agenthub.access.api_gateway.controllers import api_router
#        app.include_router(api_router)
# [来源标注] [DD-001:FS-001]
# ============================================================================
# api_router = APIRouter(prefix="/v1", default_response_class=ORJSONResponse)


# ============================================================================
# [函数] wrap_response
# [职责] 将上游 Service 的领域对象包装为 IC-001 统一响应格式
# [关联接口契约] IC-001 出参定义 {code, message, trace_id, data, timestamp}
# [参数说明]
#   data: object 必填 - 上游业务返回的领域对象（pydantic / dict / list）
#   trace_id: str 必填 - 从 request.state.trace_id 取
#   code: int 可选 = 0 - 业务码（0 = 成功）
#   message: str 可选 = "ok"
# [返回值]
#   类型: dict[str, object]
#   描述: 形如 {"code":0,"message":"ok","trace_id":"...","data":{...},"timestamp":1717372800}
# [错误码] 无（纯函数）
# [前置条件] data 可被 jsonable_encoder 序列化
# [后置条件] 不修改输入
# [并发安全] 是（无共享状态）
# [幂等性] 是；same input → same output
# [性能约束] < 1ms
# [示例]
#   wrapped = wrap_response({"id": "x"}, trace_id="t-1")
# [来源标注] [DD-001:IC-001 出参定义]
# ============================================================================
def wrap_response(
    data: object,
    trace_id: str,
    code: int = 0,
    message: str = "ok",
) -> dict[str, object]:
    """Wrap domain payload into IC-001 unified envelope.

    Args:
        data: Domain object returned by upstream service.
        trace_id: Trace identifier injected by TraceMiddleware.
        code: Business code; 0 means success.
        message: Human-readable status.

    Returns:
        Dict matching IC-001 response schema.
    """
    ...
