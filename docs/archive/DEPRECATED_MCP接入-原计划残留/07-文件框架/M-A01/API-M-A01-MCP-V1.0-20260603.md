# 接口注释清单 API-M-A01-MCP-V1.0-20260603

[模块编号] M-A01
[关联契约] IC-001 (gateway.handle)
[Agent] DD-M-A01

---

## API-001 gateway.handle ←→ IC-001

[接口编号] API-001
[关联契约] IC-001
[实现文件] src/agenthub/access/api_gateway/app.py + controllers/_router.py + middleware/*
[函数签名注释]

```python
class GatewayApp:
    """FastAPI gateway implementing IC-001.

    Implements:
        - JWT auth (RS256, 5min skew) via middleware/auth.py
        - Token-bucket rate limiting (per-IP/user/ws) via middleware/ratelimit.py
        - Trace id injection via middleware/trace.py
        - Prometheus metrics via middleware/metrics.py
        - Path-based adapter routing to M-B01~M-B05 via controllers/_router.py
    """

async def verify_jwt(
    token: str,                      # IC-001 Authorization Bearer 必填
    jwks: object,                    # 预加载 JWKS（5min TTL by caller）
    issuer: str,                     # IC-001 SEC-001 iss 白名单校验
    audience: str,                   # IC-001 aud="api"
    skew_sec: int = 300,             # IC-001 5min skew
) -> JWTClaims:
    """Verify RS256 JWT per IC-001.

    Returns:
        JWTClaims: {sub, iss, aud, exp, iat, scope, workspace_id}

    Raises:
        AuthError: → 401 + AUTH_FAILED (IC-001)
    """

async def check_rate(
    key: str,                        # 形如 "ratelimit:ip:{ws}:1.2.3.4"
    qps: int,                        # 桶容量
    redis_client: object,            # M-D03 接口
) -> bool:
    """Atomic Lua-based token bucket consumption.

    Returns:
        True 通过 / False 触发 RATE_LIMIT_EXCEEDED → 429 + Retry-After (IC-001)
    """

def inject_trace(request: Request) -> str:
    """Extract/generate trace_id per IC-001 X-Trace-ID 入参定义.

    Returns:
        32-char UUID v4 hex 或客户端值（≤ 64 字符）
    """
```

[参数说明] 见 IC-001 入参定义；本模块严格遵循
[返回值说明] IC-001 出参 envelope {code,message,trace_id,data,timestamp}
[错误码说明]
- AUTH_FAILED 401     ← middleware/auth.py
- RATE_LIMIT_EXCEEDED 429 ← middleware/ratelimit.py
- UPSTREAM_TIMEOUT 504 ← controllers/_router.py (asyncio.TimeoutError 适配)
[幂等性] 取决于下游 HTTP 方法；GET 是；POST/PUT/DELETE 由下游处理
[性能约束] P95 ≤ 200ms（IC-001）

[来源标注] [DD-001:IC-001 + MD:M-A01 + CS §1.3]
