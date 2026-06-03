"""OfflineQueue - 离线事件缓冲 (M-A02).

[文件路径] src/agenthub/access/ws_gateway/offline_queue.py
[文件职责] Redis Stream 离线缓冲：push / pull by client_id
[所属模块] M-A02
[关联设计规范] MD-M-A02 §类设计 OfflineQueue / IC-002 §时序图 断线回放
[功能描述]
  功能1: push - 客户端不在线时事件入 Redis Stream
  功能2: pull - 拉取某 client 截止 since_id 之后的所有事件
  功能3: replay_missed - 客户端重连后回放离线事件
[输入输出]
  输入: client_id, event, last_id
  输出: 事件列表 / 回放数量
[依赖关系]
  依赖文件: M-D03 Stream API（XADD/XREAD）
  被依赖文件: handlers/subscribe.py, bus_listener.py
[注意事项]
  注意1: Stream 容量上限 1000/客户端，超限 → 告警 + 截断最旧
  注意2: replay_missed 拉取时按 id 顺序重放（保证同 topic 顺序）
  注意3: Stream 24h 过期（IC-002 投递有效期）
[代码风格] 遵循CS-MCP §1
[创建日期] 2026-06-02
[作者] DD-M-A02
[来源标注] [DD-001:MD-M-A02 类设计 OfflineQueue + IC-002]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agenthub.core.logging import get_logger

if TYPE_CHECKING:
    from agenthub.access.ws_gateway.models import EventEnvelope
    from agenthub.data.cache.client import RedisClusterClient

log = get_logger(__name__)

MAX_STREAM_LEN = 1000  # 每客户端最多缓冲事件数
STREAM_TTL_SEC = 86400  # 24h


class OfflineQueue:
    """Redis Stream 离线事件队列.

    [类名] OfflineQueue
    [职责] 暂存推送失败/客户端离线时的事件，Redis Stream 实现
    [关联设计规范] MD-M-A02 / IC-002
    [属性]
      redis: RedisClusterClient
    [方法列表]
      push(client_id, event) -> bool 是否入队
      pull(client_id, last_id) -> list[EventEnvelope]
      replay_missed(client_id, since) -> int 回放数量
    [异常处理]
      RedisConnectionError → 内存 dict 兜底 + 告警
    [来源标注] [DD-001:MD-M-A02 类设计 OfflineQueue]
    """

    def __init__(self, redis: "RedisClusterClient") -> None:
        """[函数名] __init__
        [职责] 构造 OfflineQueue
        [参数说明]
          redis: RedisClusterClient 必填
        [来源标注] [DD-001:MD-M-A02 类设计]
        """
        ...

    async def push(self, client_id: str, event: "EventEnvelope") -> bool:
        """[函数名] push
        [职责] 客户端离线/推送失败时入队
        [关联接口契约] IC-002 push_event
        [参数说明]
          client_id: str 必填
          event: EventEnvelope 必填
        [返回值]
          类型: bool
          描述: True=入队成功；False=超出容量截断
        [错误码]
          PushFailedError - 推送 + 入队双重失败时上抛
        [后置条件] Redis Stream 新增一项（带 message_id）
        [并发安全] 安全
        [性能约束] XADD < 5ms
        [来源标注] [DD-001:MD-M-A02 push_event + IC-002]
        """
        ...

    async def pull(self, client_id: str, last_id: str = "0-0") -> list["EventEnvelope"]:
        """[函数名] pull
        [职责] 从 last_id 之后拉取客户端的所有事件
        [参数说明]
          client_id: str 必填
          last_id: str 默认 "0-0" Redis Stream 起始 ID
        [返回值]
          类型: list[EventEnvelope]
          描述: 事件列表（按 id 升序）
        [性能约束] XREAD < 10ms / 100 events
        [来源标注] [DD-001:MD-M-A02 pull]
        """
        ...

    async def replay_missed(self, client_id: str, since: str) -> int:
        """[函数名] replay_missed
        [职责] 客户端重连后回放 since 之后的所有离线事件
        [关联接口契约] IC-002 replay_missed + 时序图 断线回放
        [参数说明]
          client_id: str 必填
          since: str 必填 Redis Stream ID
        [返回值]
          类型: int
          描述: 实际回放数量
        [后置条件] 事件经 WSServer.emit 投递给客户端
        [幂等性] 重复调用同 since 返回 0
        [性能约束] 100 事件 < 50ms
        [来源标注] [DD-001:MD-M-A02 replay_missed + IC-002]
        """
        ...
