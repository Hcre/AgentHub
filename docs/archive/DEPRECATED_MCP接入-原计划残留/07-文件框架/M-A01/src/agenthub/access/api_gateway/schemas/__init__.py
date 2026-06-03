"""M-A01 schemas — Pydantic 请求/响应模型.

[文件路径] src/agenthub/access/api_gateway/schemas/__init__.py
[文件职责] 定义 IC-001 入参/出参 + JWTClaims + 通用错误响应模型
[所属模块] M-A01 Web API Gateway
[关联设计规范] FS-001 / IC-001 入出参定义
[功能描述]
  功能1: JWTClaims - 解码后的 JWT 载荷（sub/iat/exp/iss/aud/scope）
  功能2: UnifiedResponse[T] - IC-001 统一出参 {code,message,trace_id,data,timestamp}
  功能3: ErrorResponse - 错误响应（继承自 UnifiedResponse，data=None）
  功能4: RateLimitBucketConfig - 三维度桶配置（IP / user / ws）
[输入输出] 仅类型定义，无运行时 IO
[依赖关系]
  依赖文件: 无业务文件依赖（仅 pydantic / typing）
  被依赖文件: ../middleware/auth.py / ../middleware/ratelimit.py / ../controllers/_router.py
[注意事项]
  注意1: 所有响应模型必须 frozen=True（不可变；契合 IC-001 出参语义）
  注意2: 时间戳统一 epoch ms（int），避免时区歧义
  注意3: 错误响应的 code 字段使用 IC-001 错误码字符串而非整数（AUTH_FAILED / RATE_LIMIT_EXCEEDED ...）
[代码风格] 遵循 CS-MCP-V1.0 §1.3 强制类型注解
[创建日期] 2026-06-03
[修改历史] 2026-06-03: DD-M-A01 - 初版
[作者] DD-M-A01-20260603
[来源标注] [DD-001:FS-001 + IC-001 出参定义]
"""

from __future__ import annotations

# ============================================================================
# [类] JWTClaims
# ----------------------------------------------------------------------------
# [职责] JWT 解码后的载荷 Value Object
# [关联设计规范] IC-001 入参 Authorization + MD:M-A01 函数签名 verify_jwt
# [属性]
#   sub: str           - 用户/服务标识（必填）
#   iss: str           - 颁发者（校验白名单）
#   aud: str           - 受众（"api"）
#   exp: int           - 过期 epoch sec
#   iat: int           - 签发 epoch sec
#   scope: list[str]   - 授权域（如 ["mcp:read","mcp:write"]）
#   workspace_id: str | None - 所属 workspace（可选）
# [来源标注] [DD-001:IC-001 + RFC 7519]
# ============================================================================
# class JWTClaims(BaseModel):  # frozen=True
#     ...


# ============================================================================
# [类] UnifiedResponse (Generic[T])
# ----------------------------------------------------------------------------
# [职责] IC-001 统一出参 envelope
# [属性]
#   code: int           - 业务码（0 = 成功）
#   message: str        - 简短消息
#   trace_id: str       - 链路 id
#   data: T | None      - 业务数据
#   timestamp: int      - epoch ms
# [来源标注] [DD-001:IC-001 出参定义]
# ============================================================================
# class UnifiedResponse(BaseModel, Generic[T]):
#     ...


# ============================================================================
# [类] ErrorResponse
# ----------------------------------------------------------------------------
# [职责] 错误专用响应
# [属性] 同 UnifiedResponse + code 使用 IC-001 错误码字符串映射 + data=None
# [来源标注] [DD-001:IC-001 错误码定义]
# ============================================================================
# class ErrorResponse(BaseModel):
#     ...


__all__: list[str] = [
    # "JWTClaims",
    # "UnifiedResponse",
    # "ErrorResponse",
    # "RateLimitBucketConfig",
]
