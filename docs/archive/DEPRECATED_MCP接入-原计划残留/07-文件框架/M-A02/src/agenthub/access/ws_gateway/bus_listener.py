"""BusListener - Event Bus → WS 转推 (M-A02).

[文件路径] src/agenthub/access/ws_gateway/bus_listener.py
[文件职责] 订阅 M-EV01 Event Bus 全部 topic，按订阅关系转推 WS 客户端（Observer 模式）
[所属模块] M-A02
[关联设计规范] MD-M-A02 §类设计 BusListener / IC-002 §时序图 EventBus → WSGateway
[功能描述]
  功能1: subscribe_all_topics - 启动时订阅全部 topic（5 类：approval/template/process/mcp/binding）
  功能2: on_event - Event Bus 回调，按 topic 查订阅者并 push
  功能3: _dispatch - 内部调度：emit + 失败兜底 OfflineQueue
[输入输出]
  输入: Event Bus payload（topic, payload, trace_id）
  输出: WS 推送或 OfflineQueue 入队
[依赖关系]
  依赖文件: M-EV01 bus.subscribe, subscription_store, offline_queue, server.emit
  被依赖文件: server.py（启动时注册）
[注意事项]
  注意1: on_event 内部 try/except 必须 catch 推送失败并兜底入队
  注意2: 同 trace_id 5min 内去重（IC-002 幂等性）
  注意3: 关键 topic（process/mcp）使用 Stream 模式，其余 Pub/Sub
[代码风格] 遵循CS-MCP §1
[创建日期] 2026-06-02
[作者] DD-M-A02
[来源标注] [DD-001:MD-M-A02 类设计 BusListener + IC-002]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

from agenthub.core.logging import get_logger

if TYPE_CHECKING:
    from agenthub.access.ws_gateway.offline_queue import OfflineQueue
    from agenthub.access.ws_gateway.server import WSServer
    from agenthub.access.ws_gateway.subscription_store import SubscriptionStore
    from agenthub.eventbus.bus import EventBus

log = get_logger(__name__)

ALL_TOPICS = ["approval.*", "template.*", "process.*", "mcp.*", "binding.*"]


class BusListener:
    """Event Bus 监听器（Observer 模式）.

    [类名] BusListener
    [职责] 订阅 M-EV01 Event Bus 全部 topic，按订阅关系转推 WS
    [关联设计规范] MD-M-A02 / IC-002
    [属性]
      sio: WSServer
      bus: EventBus
      store: SubscriptionStore
      queue: OfflineQueue
      idempotency_cache: dict[str, float]  # trace_id → expire_ts
    [方法列表]
      subscribe_all_topics() -> None
      on_event(topic, payload) -> None
      _dispatch(event) -> None
    [状态机]
      Idle → Subscribed → Consuming → Disconnected → Reconnecting → Subscribed
    [异常处理]
      推送失败 → OfflineQueue.push 兜底
      BusException → 重连（见 M-EV01）
    [来源标注] [DD-001:MD-M-A02 类设计 BusListener]
    """

    def __init__(
        self,
        sio: "WSServer",
        bus: "EventBus",
        store: "SubscriptionStore",
        queue: "OfflineQueue",
    ) -> None:
        """[函数名] __init__
        [职责] 构造 BusListener
        [参数说明]
          sio: WSServer 必填
          bus: EventBus 必填
          store: SubscriptionStore 必填
          queue: OfflineQueue 必填
        [来源标注] [DD-001:MD-M-A02 类设计]
        """
        ...

    async def subscribe_all_topics(self) -> None:
        """[函数名] subscribe_all_topics
        [职责] 启动时订阅全部 topic
        [后置条件] bus 上对 5 大类 topic 注册 handler
        [并发安全] 启动期单次调用
        [来源标注] [DD-001:MD-M-A02 subscribe_all_topics]
        """
        ...

    async def on_event(self, topic: str, payload: dict) -> None:
        """[函数名] on_event
        [职责] Event Bus 事件回调，查询订阅者并推送
        [关联接口契约] IC-002 EventBus → WSGateway: event
        [参数说明]
          topic: str 必填
          payload: dict 必填（含 trace_id / emitted_at）
        [后置条件] WSServer.emit 推送给所有订阅 client
        [幂等性] trace_id 5min 内去重
        [性能约束] 推送 P95 ≤ 50ms
        [来源标注] [DD-001:MD-M-A02 on_event + IC-002]
        """
        ...

    async def _dispatch(self, event: dict) -> None:
        """[函数名] _dispatch
        [职责] 内部调度：emit + 失败兜底入队
        [参数说明]
          event: dict 必填 EventEnvelope.to_dict()
        [异常处理] emit 失败 → OfflineQueue.push
        [来源标注] [DD-001:MD-M-A02 on_event 内部]
        """
        ...

    def _is_duplicate(self, trace_id: str) -> bool:
        """[函数名] _is_duplicate
        [职责] 幂等性去重
        [参数说明]
          trace_id: str 必填
        [返回值]
          类型: bool
          描述: True=已处理过；False=新事件
        [来源标注] [DD-001:IC-002 幂等性 5min]
        """
        ...
