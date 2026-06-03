"""M-A01 AuthMiddleware — JWT 校验 + JWKS 缓存（5min TTL）.

[文件路径] src/agenthub/access/api_gateway/middleware/auth.py
[文件职责] 解析 Authorization: Bearer，验签 JWT（RS256），注入 request.state.jwt_claims
[所属模块] M-A01 Web API Gateway
[关联设计规范] FS-001 / MD:M-A01 类设计 AuthMiddleware / IC-001
[功能描述]
  功能1: 从 Authorization 头提取 Bearer token；缺失 / 格式非法 → 401 AUTH_FAILED
  功能2: 通过 M-C07 Secret Manager 拉取 Vault 公钥（JWKS），in-proc LRU 缓存 5min
  功能3: jose.jwt.decode 验签（RS256；允许 5min skew；校验 iss / aud / exp）
  功能4: 将 JWTClaims 注入 request.state.jwt_claims 供下游消费
  功能5: 鉴权失败统一返回 IC-001 错误格式 {code:"AUTH_FAILED", http=401}
[输入输出]
  输入: starlette.Request（headers["Authorization"]）
  输出: 透传（成功）或 401 JSONResponse（失败）
[依赖关系]
  依赖文件: ../schemas/__init__.py (JWTClaims pydantic 模型)
            agenthub.infrastructure.secret.vault_client (M-C07 跨模块接口，仅消费)
            agenthub.core.logging
  被依赖文件: ../app.py (register_middleware)
[注意事项]
  注意1: JWKS 缓存键 = "jwks:{issuer}"，TTL 5min；缓存失效时全局加锁刷新（避免雪崩）
  注意2: 公开路径白名单（/healthz / /metrics）必须在 Auth 前置短路返回，否则探针无法通过
  注意3: 禁止把 token 写入日志（[DD-001:CS §1.6 安全要求]），仅记录 token_hash
  注意4: 跨模块依赖：本文件 → M-C07（仅 import 公共接口，禁止 import M-C07 内部实现）
[代码风格] 遵循 CS-MCP-V1.0 §1 + §1.6 异常处理
[创建日期] 2026-06-03
[修改历史] 2026-06-03: DD-M-A01 - 初版
[作者] DD-M-A01-20260603
[来源标注] [DD-001:FS-001 + MD:M-A01 + IC-001 + SEC:SEC-001]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response


# ============================================================================
# [类] AuthMiddleware
# ----------------------------------------------------------------------------
# [职责] Starlette BaseHTTPMiddleware；JWT 校验入口
# [关联设计规范] MD:M-A01 类设计第 2 项 "AuthMiddleware - JWT 校验"
# [属性]
#   jwks_cache: dict[str, JWKSEntry] - issuer → 公钥集合，5min TTL
#   public_paths: frozenset[str]     - 白名单路径（健康检查/metrics）
#   secret_client: VaultClient       - M-C07 跨模块依赖（仅接口）
# [方法列表]
#   __init__(app, secret_client, public_paths) → None
#   __call__(request, call_next) → Response   - ASGI 中间件入口
#   _verify_jwt(token: str) → JWTClaims       - 私有：验签 + 解码
#   _get_jwks(issuer: str) → JWKSEntry        - 私有：缓存 / 拉取公钥
# [状态机] 无；JWKS 缓存项有自身 TTL
# [异常处理]
#   AuthError → 401 + AUTH_FAILED（不记 token，仅记 token_hash + reason）
#   VaultSealedError → 503 + UPSTREAM_TIMEOUT（公钥拉取失败时临时拒服务）
# [来源标注] [DD-001:MD M-A01 + IC-001 错误码]
# ============================================================================
class AuthMiddleware:
    """JWT verification middleware with 5-minute JWKS cache."""

    # [函数] __call__
    # [职责] ASGI 中间件入口，BaseHTTPMiddleware 协议
    # [关联接口契约] IC-001 入参定义 Authorization 必填
    # [参数说明]
    #   request: Request 必填 - Starlette 请求对象
    #   call_next: Callable[[Request], Awaitable[Response]] 必填 - 下游中间件链
    # [返回值] Response（401 错误响应或下游响应）
    # [错误码] AUTH_FAILED 401 / UPSTREAM_TIMEOUT 503
    # [前置条件] TraceMiddleware 已注入 trace_id（用于错误响应）
    # [后置条件] 成功时 request.state.jwt_claims 已设置
    # [并发安全] 是（每请求独立 state）
    # [幂等性] 是（同 token + 同公钥版本 → 同结果）
    # [性能约束] P95 ≤ 20ms（JWKS 缓存命中）；P95 ≤ 150ms（缓存未命中含 Vault 拉取）
    # [来源标注] [DD-001:IC-001 时序图第 2 步 verify_jwt]
    async def __call__(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Verify JWT and either inject claims or short-circuit with 401."""
        ...


# ============================================================================
# [函数] verify_jwt（模块级公开纯校验函数；IC-001 暴露的最小单元）
# [职责] 验签 JWT 并返回 JWTClaims（无 IO 缓存；JWKS 由调用方注入）
# [关联接口契约] IC-001 - 验签子步骤
# [参数说明]
#   token: str 必填 - Bearer token（裸字符串，不含 "Bearer " 前缀）
#   jwks: object 必填 - 已缓存的公钥集合（jose JWKS 对象）
#   issuer: str 必填 - 期望 issuer，用于校验 iss 声明
#   audience: str 必填 - 期望 audience
#   skew_sec: int 可选 = 300 - 允许的时间漂移
# [返回值]
#   类型: JWTClaims（pydantic Model）
#   描述: 解码后的载荷（sub / exp / iat / iss / aud / scope）
# [错误码]
#   AuthError - token 过期 / 签名无效 / iss/aud 不匹配
# [前置条件] jwks 已加载且未过期
# [后置条件] 不修改输入；不写日志（由调用方记录）
# [并发安全] 是（纯函数）
# [幂等性] 是
# [性能约束] < 10ms
# [示例]
#   claims = await verify_jwt(token, jwks, issuer="agenthub", audience="api")
# [来源标注] [DD-001:MD M-A01 函数签名 verify_jwt + CS §1.3]
# ============================================================================
async def verify_jwt(
    token: str,
    jwks: object,
    issuer: str,
    audience: str,
    skew_sec: int = 300,
) -> object:
    """Decode and verify a JWT against the supplied JWKS.

    Args:
        token: Raw bearer token without prefix.
        jwks: Pre-fetched JWKS object (5-min TTL cached by caller).
        issuer: Expected `iss` claim.
        audience: Expected `aud` claim.
        skew_sec: Allowed clock skew in seconds (default 300 per IC-001).

    Returns:
        JWTClaims pydantic model with decoded payload.

    Raises:
        AuthError: Token expired / signature invalid / iss-aud mismatch.
    """
    ...
