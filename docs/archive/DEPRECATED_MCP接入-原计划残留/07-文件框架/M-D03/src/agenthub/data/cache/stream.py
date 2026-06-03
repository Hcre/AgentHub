"""Redis Stream 封装（关键事件）.

[文件路径] src/agenthub/data/cache/stream.py
[文件职责] 提供 Stream 消息发布/消费/Consumer Group 支持
[所属模块] M-D03（来自 DD-001）
[关联设计规范] FS-021 / MD-M-D03 / IC-019（来自 DD-001）
[功能描述]
  功能1: StreamPublisher 封装 XADD + MAXLEN 截断
  功能2: StreamConsumer 封装 XREADGROUP + XACK
  功能3: Consumer Group 自动创建与维护
  功能4: Dead-letter 处理（handler 异常消息转 DLQ stream）
[输入输出]
  输入: 业务事件 dict（必含 trace_id/timestamp/payload）
  输出: 异步消息 ID；消费后 ack
[依赖关系]
  依赖文件: ./client.py、agenthub.core.logging
  被依赖文件:
    - M-A02 ws_gateway/offline_queue.py: 离线消息
    - M-EV01 eventbus/stream_consumer.py: 关键事件 Stream 模式
[注意事项]
  注意1: MAXLEN 截断使用 ~ 近似值，节约 CPU
  注意2: Consumer name 必须唯一（建议用 hostname-pid）
  注意3: XACK 仅在 handler 成功后调用
  注意4: Handler 异常 → 消息转 DLQ stream（24h 保留）
  注意5: Stream name 含 {workspace_id} 哈希标签
[代码风格] 遵循 CS-MCP-V1.0 §1（来自 DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-D03 - 初始 Stream 框架
[作者] DD-M-D03-20260602
[来源标注] [DD-001:FS-021 / MD-M-D03 / IC-019 + AR洞察-1]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

import structlog

from agenthub.core.exceptions import AgentHubError

if TYPE_CHECKING:
    from agenthub.data.cache.client import RedisClusterClient

log = structlog.get_logger(__name__)


class StreamMessage:
    """Stream 消息值对象.

    [类名] StreamMessage
    [职责] 表示一条 Stream 消息
    [关联设计规范] MD-M-D03（来自 DD-001）
    [属性]
      属性1: message_id str  XADD 返回的 ID（ms-seq）
      属性2: stream str      源 stream 名
      属性3: fields dict[str, bytes]  消息字段
    [方法列表]
      方法1: decode() → dict[str, str] - 解码所有字段
    [状态机] 无
    [异常处理] 无
    [来源标注] [DD-M推断:Stream 消息包装]
    """

    def __init__(self, message_id: str, stream: str, fields: dict[str, bytes]) -> None:
        """构造消息值对象.

        [函数名] __init__
        [职责] 包装 Stream 原始消息
        [参数说明]
          参数1: message_id str 必填
          参数2: stream str 必填
          参数3: fields dict[str, bytes] 必填
        [返回值]
          类型: None
        [错误码] 无
        [前置条件] 无
        [后置条件] 无
        [并发安全] 值对象不可变
        [幂等性] 是
        [性能约束] < 0.1ms
        [来源标注] [DD-M推断:Value Object 模式]
        """
        ...

    def decode(self) -> dict[str, str]:
        """解码所有字段为 str.

        [函数名] decode
        [职责] bytes → str 解码
        [参数说明] 无
        [返回值]
          类型: dict[str, str]
          描述: 解码后字段
        [错误码] 无
        [前置条件] 无
        [后置条件] 无
        [并发安全] 纯函数
        [幂等性] 是
        [性能约束] < 1ms
        [来源标注] [DD-M推断:便捷工具]
        """
        ...


class StreamPublisher:
    """Stream 发布者.

    [类名] StreamPublisher
    [职责] 封装 XADD + MAXLEN
    [关联设计规范] MD-M-D03（来自 DD-001）
    [属性]
      属性1: client RedisClusterClient  底层客户端
      属性2: stream str                 stream 名
      属性3: maxlen int                 近似最大长度
    [方法列表]
      方法1: publish(fields, trace_id) → str - 发布消息
    [状态机] 无
    [异常处理]
      异常1: ClusterDownError
    [来源标注] [DD-001:MD-M-D03 + IC-019]
    """

    def __init__(self, client: RedisClusterClient, stream: str, maxlen: int = 100_000) -> None:
        """构造发布者.

        [函数名] __init__
        [职责] 绑定 stream + 截断长度
        [参数说明]
          参数1: client RedisClusterClient 必填
          参数2: stream str 必填（含 {workspace_id} 哈希标签）
          参数3: maxlen int 可选 默认 100_000
        [返回值]
          类型: None
        [错误码]
          错误码1: ValueError - stream 缺哈希标签
        [前置条件] 无
        [后置条件] 可发布
        [并发安全] 协程安全
        [幂等性] 是
        [性能约束] < 1ms
        [来源标注] [DD-001:MD-M-D03]
        """
        ...

    async def publish(self, fields: dict[str, bytes], trace_id: str) -> str:
        """发布 Stream 消息.

        [函数名] publish
        [职责] XADD stream MAXLEN ~ maxlen * fields
        [关联接口契约] IC-019.queue.xadd（来自 DD-001）
        [参数说明]
          参数1: fields dict[str, bytes] 必填 消息字段
          参数2: trace_id str 必填 追踪 ID（自动注入）
        [返回值]
          类型: str
          描述: 消息 ID
        [错误码]
          错误码1: ClusterDownError
        [前置条件] 无
        [后置条件] 消息已追加
        [并发安全] 协程安全
        [幂等性] 否
        [性能约束] P95 ≤ 5ms
        [来源标注] [DD-001:IC-019]
        """
        ...


class StreamConsumer:
    """Stream 消费者（Consumer Group）.

    [类名] StreamConsumer
    [职责] 封装 XREADGROUP + XACK
    [关联设计规范] MD-M-D03（来自 DD-001）
    [属性]
      属性1: client RedisClusterClient  底层客户端
      属性2: stream str                 stream 名
      属性3: group str                  consumer group
      属性4: consumer str               consumer 唯一名
      属性5: dlq_stream str             dead-letter stream
    [方法列表]
      方法1: ensure_group() → None - 创建 group（已存在则忽略）
      方法2: consume(handler) → None - 阻塞消费循环
      方法3: ack(message_id) → None - 确认
    [状态机]
      状态1: Idle → start → Consuming → stop → Idle
    [异常处理]
      异常1: HandlerException - 消息转 DLQ + ack
    [来源标注] [DD-001:MD-M-D03 + IC-021 + AR洞察-1]
    """

    def __init__(
        self,
        client: RedisClusterClient,
        stream: str,
        group: str,
        consumer: str,
        dlq_stream: str,
    ) -> None:
        """构造消费者.

        [函数名] __init__
        [职责] 绑定 stream / group / consumer
        [参数说明]
          参数1: client RedisClusterClient 必填
          参数2: stream str 必填
          参数3: group str 必填 consumer group
          参数4: consumer str 必填 唯一 consumer 名
          参数5: dlq_stream str 必填 dead-letter stream
        [返回值]
          类型: None
        [错误码]
          错误码1: ValueError - 参数校验失败
        [前置条件] 无
        [后置条件] 需调用 ensure_group
        [并发安全] 协程安全
        [幂等性] 是
        [性能约束] < 1ms
        [来源标注] [DD-001:MD-M-D03 + IC-021]
        """
        ...

    async def ensure_group(self) -> None:
        """创建 consumer group.

        [函数名] ensure_group
        [职责] XGROUP CREATE（已存在 BUSYGROUP 则忽略）
        [参数说明] 无
        [返回值]
          类型: None
        [错误码]
          错误码1: ClusterDownError
        [前置条件] 应用启动时调用
        [后置条件] group 就绪
        [并发安全] 启动时单次调用
        [幂等性] 是
        [性能约束] < 50ms
        [来源标注] [DD-001:MD-M-D03]
        """
        ...

    async def consume(
        self,
        handler: Callable[[StreamMessage], Awaitable[None]],
        block_ms: int = 5000,
        batch: int = 16,
    ) -> None:
        """阻塞消费循环.

        [函数名] consume
        [职责] XREADGROUP + handler + XACK/DLQ
        [关联接口契约] IC-021.bus.subscribe（来自 DD-001）
        [参数说明]
          参数1: handler Callable[[StreamMessage], Awaitable[None]] 必填
          参数2: block_ms int 可选 默认 5000
          参数3: batch int 可选 默认 16
        [返回值]
          类型: None（持续运行直到 stop）
        [错误码]
          错误码1: ClusterDownError - 暂停 + 告警
        [前置条件] ensure_group 已调用
        [后置条件] 持续运行
        [并发安全] 协程安全
        [幂等性] 否（持续消费）
        [性能约束] 单 handler < 30s；超则 DLQ
        [来源标注] [DD-001:IC-021 + MD-M-D03:测试策略]
        """
        ...

    async def ack(self, message_id: str) -> None:
        """确认消息.

        [函数名] ack
        [职责] XACK stream group message_id
        [参数说明]
          参数1: message_id str 必填
        [返回值]
          类型: None
        [错误码]
          错误码1: ClusterDownError
        [前置条件] consume 中调用
        [后置条件] 消息从 pending 移除
        [并发安全] 协程安全
        [幂等性] 是
        [性能约束] < 5ms
        [来源标注] [DD-001:MD-M-D03]
        """
        ...
