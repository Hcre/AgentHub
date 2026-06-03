"""M-A01 RateLimiter — 令牌桶（per-IP / per-user / per-ws）.

[文件路径] src/agenthub/access/api_gateway/middleware/ratelimit.py
[文件职责] 基于 Redis 的令牌桶限流；三维度（IP / user / workspace）独立桶
[所属模块] M-A01 Web API Gateway
[关联设计规范] FS-001 / MD:M-A01 类设计 RateLimiter / IC-001 错误码 RATE_LIMIT_EXCEEDED
[功能描述]
  功能1: 从 request 提取 IP / user_id（jwt_claims.sub）/ ws_id（header / query）
  功能2: 三维度独立 check（命中任一即拒绝），使用 Redis Lua 脚本保证原子性
  功能3: 命中限流 → 429 + RATE_LIMIT_EXCEEDED + Retry-After 头
  功能4: 后台协程定时 refill（基于桶 capacity + qps 配置）
[输入输出]
  输入: starlette.Request（client.host / state.jwt_claims / headers["X-Workspace-Id"]）
  输出: 透传或 429 JSONResponse
[依赖关系]
  依赖文件: agenthub.data.cache.client (M-D03 跨模块，仅消费 RedisClusterClient 接口)
            agenthub.core.config (RateLimitConfig)
  被依赖文件: ../app.py (register_middleware)
[注意事项]
  注意1: 必须在 AuthMiddleware 之后注册——只对鉴权成功的请求计入 user/ws 桶，避免被刷流
  注意2: Redis 不可用时降级到 "fail-open"（仅记 WARN 日志），不阻塞业务（[DD-001:MD 异常处理]）
  注意3: 令牌桶 key 必须含 hash tag {workspace_id}，保证 Redis cluster 同 slot
  注意4: Lua 脚本必须使用 EVALSHA + script load 预加载，避免每请求传 script
[代码风格] 遵循 CS-MCP-V1.0 §1 + §1.8 异步约束
[创建日期] 2026-06-03
[修改历史] 2026-06-03: DD-M-A01 - 初版
[作者] DD-M-A01-20260603
[来源标注] [DD-001:FS-001 + MD:M-A01 + IC-001]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response


# ============================================================================
# [类] RateLimiter
# ----------------------------------------------------------------------------
# [职责] 令牌桶限流中间件
# [关联设计规范] MD:M-A01 类设计第 3 项 "RateLimiter - 令牌桶"
# [属性]
#   redis_client: RedisClusterClient    - M-D03 跨模块依赖（仅接口）
#   buckets: dict[str, BucketConfig]    - 三维度桶配置（IP/user/ws）
#   lua_sha: str                        - 预加载的 Lua 脚本 SHA
# [方法列表]
#   __init__(app, redis_client, buckets) → None
#   __call__(request, call_next) → Response
#   check(key: str, qps: int) → bool    - 公开：原子扣 token，返回是否通过
#   refill() → None                     - 后台协程：定时补充令牌（仅当未启用懒补时）
# [状态机] 无（桶状态在 Redis 中）
# [异常处理]
#   RateLimitError → 429 + RATE_LIMIT_EXCEEDED + Retry-After
#   RedisDown → fail-open + WARN 日志
# [来源标注] [DD-001:MD M-A01 + IC-001 错误码]
# ============================================================================
class RateLimiter:
    """Multi-dimensional token-bucket limiter backed by Redis cluster."""

    # [函数] __call__
    # [职责] 中间件入口；三维度 check 后决定透传或 429
    # [参数说明]
    #   request: Request 必填
    #   call_next: 下游
    # [返回值] Response
    # [错误码] RATE_LIMIT_EXCEEDED 429
    # [并发安全] 是；Redis Lua 脚本提供原子性
    # [性能约束] P95 ≤ 5ms（Redis 单 RTT）
    # [来源标注] [DD-001:IC-001 时序图第 3 步 check_rate]
    async def __call__(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Check three buckets atomically; reject with 429 on miss."""
        ...


# ============================================================================
# [函数] check_rate
# [职责] 单一桶原子扣 token；公开供 WebSocket 网关复用（[DD-M-A01推断:依据 M-A02 也需限流]）
# [关联接口契约] 内部接口（IC-022 in-proc 约束）
# [参数说明]
#   key: str 必填 - Redis 桶 key（含 {hash_tag}）
#   qps: int 必填 - 桶容量上限（每秒 token 数）
#   redis_client: object 必填 - RedisClusterClient 实例
# [返回值]
#   类型: bool
#   描述: True 通过；False 限流命中
# [错误码] 无（Redis 异常上抛由调用方决定 fail-open/closed）
# [前置条件] Lua 脚本已通过 SCRIPT LOAD 注册
# [后置条件] Redis 桶 count 已更新；过期时间已设置
# [并发安全] 是（Lua 原子）
# [幂等性] 否（每次调用扣减一次）
# [性能约束] < 5ms
# [来源标注] [DD-001:MD M-A01 函数签名 check_rate]
# ============================================================================
async def check_rate(key: str, qps: int, redis_client: object) -> bool:
    """Atomically consume one token from the given bucket.

    Args:
        key: Redis key for the bucket; must contain `{hash_tag}`.
        qps: Bucket capacity (tokens per second).
        redis_client: RedisClusterClient instance (M-D03 interface).

    Returns:
        True if a token was consumed; False if the bucket is empty.

    Raises:
        ConnectionError: Caller decides fail-open vs fail-closed.
    """
    ...
