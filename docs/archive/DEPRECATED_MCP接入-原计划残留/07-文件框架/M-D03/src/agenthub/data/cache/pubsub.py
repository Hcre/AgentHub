"""Redis Pub/Sub 封装（非关键事件）.

[文件路径] src/agenthub/data/cache/pubsub.py
[文件职责] 提供 Pub/Sub 消息发布/订阅
[所属模块] M-D03（来自 DD-001）
[关联设计规范] FS-021 / MD-M-D03 / IC-019（来自 DD-001）
[功能描述]
  功能1: PubSubPublisher 封装 PUBLISH
  功能2: PubSubSubscriber 封装 SUBSCRIBE + 自动重连
  功能3: 不持久化（Pub/Sub 特性），仅实时转发
[输入输出]
  输入: 业务事件 dict
  输出: 实时推送到订阅者
[依赖关系]
  依赖文件: ./client.py、agenthub.core.logging
  被依赖文件:
    - M-A02 ws_gateway/bus_listener.py: 事件转 WS
    - M-EV01 eventbus/bus.py: 非关键事件转发
[注意事项]
  注意1: Pub/Sub 不可靠（断连期间消息丢失），关键事件必须用 Stream
  注意2: 订阅者必须实现自动重连 + 重新订阅
  注意3: 单 channel 订阅者数量建议 < 1000（性能）
  注意4: Handler 异常不应中断消费循环（best-effort）
[代码风格] 遵循 CS-MCP-V1.0 §1（来自 DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-D03 - 初始 Pub/Sub 框架
[作者] DD-M-D03-20260602
[来源标注] [DD-001:FS-021 / MD-M-D03 / IC-019 + IC-020]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

import structlog

from agenthub.core.exceptions import AgentHubError

if TYPE_CHECKING:
    from agenthub.data.cache.client import RedisClusterClient

log = structlog.get_logger(__name__)


class PubSubPublisher:
    """Pub/Sub 发布者.

    [类名] PubSubPublisher
    [职责] 封装 PUBLISH
    [关联设计规范] MD-M-D03（来自 DD-001）
    [属性]
      属性1: client RedisClusterClient  底层客户端
      属性2: channel str                 channel 名
    [方法列表]
      方法1: publish(message, trace_id) → int
    [状态机] 无
    [异常处理]
      异常1: ClusterDownError
    [来源标注] [DD-001:MD-M-D03 + IC-020]
    """

    def __init__(self, client: RedisClusterClient, channel: str) -> None:
        """构造发布者.

        [函数名] __init__
        [职责] 绑定 channel
        [参数说明]
          参数1: client RedisClusterClient 必填
          参数2: channel str 必填
        [返回值]
          类型: None
        [错误码]
          错误码1: ValueError - channel 非法
        [前置条件] 无
        [后置条件] 可发布
        [并发安全] 协程安全
        [幂等性] 是
        [性能约束] < 1ms
        [来源标注] [DD-001:MD-M-D03]
        """
        ...

    async def publish(self, message: bytes, trace_id: str) -> int:
        """发布 Pub/Sub 消息.

        [函数名] publish
        [职责] PUBLISH channel message
        [关联接口契约] IC-019.pubsub.publish（来自 DD-001）
        [参数说明]
          参数1: message bytes 必填 序列化后的消息
          参数2: trace_id str 必填 追踪 ID
        [返回值]
          类型: int
          描述: 订阅者数量
        [错误码]
          错误码1: ClusterDownError
        [前置条件] 无
        [后置条件] 订阅者异步收到
        [并发安全] 协程安全
        [幂等性] 否
        [性能约束] 投递 < 50ms
        [来源标注] [DD-001:IC-019 + IC-020]
        """
        ...


class PubSubSubscriber:
    """Pub/Sub 订阅者.

    [类名] PubSubSubscriber
    [职责] 封装 SUBSCRIBE + 自动重连
    [关联设计规范] MD-M-D03（来自 DD-001）
    [属性]
      属性1: client RedisClusterClient  底层客户端
      属性2: channel str                 channel 名
      属性3: _running bool               运行状态
    [方法列表]
      方法1: subscribe(handler) → None - 阻塞订阅循环
      方法2: stop() → None - 停止
    [状态机]
      状态1: Idle → subscribe → Subscribed → disconnect → Reconnecting → Subscribed
      状态2: Subscribed → stop → Stopped
    [异常处理]
      异常1: ClusterDownError - 自动重连
      异常2: HandlerException - log + 继续（不中断）
    [来源标注] [DD-001:MD-M-D03 + IC-021 + AR洞察-1]
    """

    def __init__(self, client: RedisClusterClient, channel: str) -> None:
        """构造订阅者.

        [函数名] __init__
        [职责] 绑定 channel
        [参数说明]
          参数1: client RedisClusterClient 必填
          参数2: channel str 必填
        [返回值]
          类型: None
        [错误码]
          错误码1: ValueError - channel 非法
        [前置条件] 无
        [后置条件] 需调用 subscribe
        [并发安全] 协程安全
        [幂等性] 是
        [性能约束] < 1ms
        [来源标注] [DD-001:MD-M-D03]
        """
        ...

    async def subscribe(
        self,
        handler: Callable[[bytes], Awaitable[None]],
    ) -> None:
        """阻塞订阅循环.

        [函数名] subscribe
        [职责] SUBSCRIBE + 自动重连 + handler 调用
        [关联接口契约] IC-021.bus.subscribe（来自 DD-001）
        [参数说明]
          参数1: handler Callable[[bytes], Awaitable[None]] 必填
        [返回值]
          类型: None（持续运行直到 stop）
        [错误码]
          错误码1: ClusterDownError - 重连循环
        [前置条件] 应用启动时调用
        [后置条件] 持续运行
        [并发安全] 协程安全
        [幂等性] 否
        [性能约束] handler 无超时（best-effort）
        [来源标注] [DD-001:IC-021 + MD-M-D03:状态机]
        """
        ...

    async def stop(self) -> None:
        """停止订阅.

        [函数名] stop
        [职责] 设置 _running=False，下次循环退出
        [参数说明] 无
        [返回值]
          类型: None
        [错误码] 无
        [前置条件] 无
        [后置条件] subscribe 循环退出
        [并发安全] 协程安全
        [幂等性] 是
        [性能约束] < 1s
        [来源标注] [DD-M推断:优雅停止]
        """
        ...
