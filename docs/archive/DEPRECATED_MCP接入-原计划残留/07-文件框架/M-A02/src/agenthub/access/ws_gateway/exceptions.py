"""WS Event Gateway 域异常 (M-A02).

[文件路径] src/agenthub/access/ws_gateway/exceptions.py
[文件职责] 定义 WS 网关域异常（AuthError / ACLError / RedisConnError / PushFailedError）
[所属模块] M-A02
[关联设计规范] MD-M-A02 §异常处理
[功能描述]
  功能1: AuthError - 鉴权失败，对应 WS 关闭码 4401
  功能2: ACLError - 越权订阅，对应 WS 关闭码 1008
  功能3: RedisConnectionError - Redis 不可用，触发内存兜底 + 告警
  功能4: PushFailedError - 推送失败，触发离线队列兜底
[输入输出]
  输入: 异常触发上下文（client_id, topic, reason）
  输出: raise，由 socketio / handler 捕获后决定关闭码或重试
[依赖关系]
  依赖文件: agenthub.core.exceptions (AgentHubError 基类)
  被依赖文件: handlers/*, server.py, offline_queue.py, subscription_store.py
[注意事项]
  注意1: 所有异常继承 AgentHubError，统一日志与告警通道
  注意2: AuthError / ACLError 关闭码固定（4401/1008），勿改动（IC-002 契约）
  注意3: RedisConnectionError 抛出后上层应捕获并降级到内存 dict
[代码风格] 遵循CS-MCP §1.6 异常处理规范
[创建日期] 2026-06-02
[作者] DD-M-A02
[来源标注] [DD-001:MD-M-A02 §异常处理 + IC-002 错误码]
"""

from __future__ import annotations

from agenthub.core.exceptions import AgentHubError


class AuthError(AgentHubError):
    """鉴权失败异常 → WS 关闭码 4401.

    [类名] AuthError
    [职责] 标识 JWT 校验失败或 token 过期
    [关联设计规范] IC-002 错误码 4401
    [属性]
      client_id: str | None 关联客户端 ID（便于审计）
    [来源标注] [DD-001:IC-002 4401 认证失败]
    """

    def __init__(self, message: str, *, client_id: str | None = None) -> None:
        """[函数名] __init__
        [职责] 构造 AuthError
        [参数说明]
          message: str 必填 错误描述
          client_id: str 可选 客户端标识
        [错误码] 4401
        [来源标注] [DD-001:IC-002 4401]
        """
        super().__init__(message, code="4401", client_id=client_id)


class ACLError(AgentHubError):
    """越权订阅异常 → WS 关闭码 1008.

    [类名] ACLError
    [职责] 标识 agent 无权订阅指定 topic
    [关联设计规范] IC-002 错误码 1008
    [属性]
      client_id: str | None
      topic: str 越权 topic
    [来源标注] [DD-001:IC-002 1008 越权订阅]
    """

    def __init__(self, message: str, *, client_id: str | None = None, topic: str = "") -> None:
        """[函数名] __init__
        [职责] 构造 ACLError
        [参数说明]
          message: str 必填
          client_id: str 可选
          topic: str 必填（被拒绝的 topic）
        [错误码] 1008
        [来源标注] [DD-001:IC-002 1008]
        """
        super().__init__(message, code="1008", client_id=client_id, topic=topic)


class RedisConnectionError(AgentHubError):
    """Redis 不可用异常 → 切换内存兜底 + 告警.

    [类名] RedisConnectionError
    [职责] 标识 Redis Stream / Hash 操作失败
    [关联设计规范] MD-M-A02 §异常处理
    [异常处理]
      上层捕获后应降级到内存 dict，并发出 WARN 日志与告警
    [来源标注] [DD-001:MD-M-A02 §异常处理]
    """

    def __init__(self, message: str, *, operation: str = "") -> None:
        """[函数名] __init__
        [职责] 构造 RedisConnectionError
        [参数说明]
          message: str 必填
          operation: str 可选（如 "xadd"/"hset"）
        [来源标注] [DD-001:MD-M-A02 §异常处理]
        """
        super().__init__(message, code="REDIS_CONN_FAILED", operation=operation)


class PushFailedError(AgentHubError):
    """WS 推送失败异常 → 触发离线队列兜底.

    [类名] PushFailedError
    [职责] 标识 emit/send 给客户端失败（连接已断但未感知）
    [关联设计规范] MD-M-A02 §异常处理
    [来源标注] [DD-001:MD-M-A02 §异常处理]
    """

    def __init__(self, message: str, *, client_id: str = "", event_type: str = "") -> None:
        """[函数名] __init__
        [职责] 构造 PushFailedError
        [参数说明]
          message: str 必填
          client_id: str 必填
          event_type: str 必填
        [来源标注] [DD-001:MD-M-A02 §异常处理]
        """
        super().__init__(message, code="PUSH_FAILED", client_id=client_id, event_type=event_type)
