"""M-EV01 StreamConsumer 关键 topic 消费者（含 dead-letter）.

[文件路径] src/agenthub/eventbus/stream_consumer.py
[文件职责] StreamConsumer 类：关键 topic 的 Redis Stream 消费者（consumer group + 至少一次）
[所属模块] M-EV01（来自DD-001）
[关联设计规范] FS-022 / MD-MCP-V1.0-M-EV01 / IC-021（来自DD-001）
[功能描述]
  功能1: 以 consumer group 方式消费 Stream topic（XREADGROUP）
  功能2: handler 异常自动转 dead-letter stream（避免阻塞组）
  功能3: 维护消费进度（XACK）+ 定期 XAUTOCLAIM 抢占僵尸消费者
  功能4: 自动重连 Redis + 从 last_delivered_id 恢复
[输入输出]
  输入:
    - redis: Redis cluster 客户端
    - topic: str（Stream 模式 topic）
    - consumer_group: str（必填，建议 "<service>-<env>" 格式）
    - consumer_name: str（建议本机 hostname/pod name）
    - handler: Callable[[dict], Awaitable[None]]
  输出:
    - consumed_count: int（消费成功数）
    - dead_letter_count: int（死信数）
[依赖关系]
  依赖文件:
    - agenthub.core.config（Settings）
    - agenthub.core.logging（结构化日志）
    - agenthub.eventbus.bus（EventBus，仅类型引用）
  被依赖文件:
    - agenthub.eventbus.bus（EventBus.subscribe 委托）
    - agenthub.application.pool.services（M-B02，process.spawned 消费者）
    - agenthub.application.approval.services（M-B04，approval.decided 消费者）
[注意事项]
  注意1: dead-letter stream 命名约定 "<original_topic>.dlq"（如 "approval.requested.dlq"）
  注意2: handler 超时 30s 标 dead-letter（必须 handler 内部含超时控制）
  注意3: XAUTOCLAIM 周期 60s，min_idle_time 300s（避免抢占正在处理的消息）
  注意4: Stream TTL 默认 24h（Redis Stream MAXLEN ~ N）
  注意5: consumer group 创建必须 MKSTREAM（group 不存在时自动建 stream）
  注意6: 关键 topic 列表来自 __init__.STREAM_TOPICS，禁止在 StreamConsumer 中硬编码
[代码风格] 遵循 CS-MCP-V1.0 §1
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-EV01 - 初始版本
[作者] DD-M-EV01-20260603
[来源标注] [DD-001:FS-022 + MD-MCP-V1.0-M-EV01 + AR洞察-1 + DDR-002]
"""

# === 仅注释框架（无业务代码）===

# from __future__ import annotations
#
# from typing import Awaitable, Callable
# import asyncio
# import time
#
# import structlog
# from redis.asyncio.cluster import RedisCluster
# from redis.exceptions import ResponseError
#
# from agenthub.core.config import Settings
# from agenthub.core.logging import get_logger
#
# log = get_logger(__name__)
#
# DEFAULT_DEAD_LETTER_SUFFIX = ".dlq"
# DEFAULT_HANDLER_TIMEOUT_SEC = 30
# DEFAULT_XAUTOCLAIM_INTERVAL_SEC = 60
# DEFAULT_MIN_IDLE_TIME_SEC = 300
# DEFAULT_STREAM_MAXLEN = 1_000_000
#
#
# class StreamConsumer:
#     """Stream 模式消费者（关键 topic 用）.
#
#     职责: 以 consumer group 方式消费 Stream topic，handler 失败转 dead-letter
#     关联设计规范: MD-MCP-V1.0-M-EV01
#
#     Attributes:
#         redis: Redis cluster 客户端
#         topic: 目标 topic（必须已注册）
#         group: consumer group 名
#         consumer: 当前消费者标识
#         handler: 事件处理函数
#         _running: 消费循环运行标志
#         _task: 消费协程
#
#     Methods:
#         start(): 启动消费循环
#         stop(): 优雅停止
#         consume_loop(): 主消费循环（XREADGROUP）
#        _handle_message(message): 单条消息处理
#        _move_to_dlq(message, reason): 转 dead-letter
#         reclaim_idle(): XAUTOCLAIM 抢占僵尸消费者
#
#     状态机:
#         Idle → start() → Subscribed
#         Subscribed → XREADGROUP → Consuming
#         Consuming → handler 异常 → DLQ + ack → Consuming
#         Consuming → Redis 断开 → Reconnecting → Subscribed
#         Subscribed → stop() → Idle
#
#     异常处理:
#         HandlerException: 转 dead-letter + ack
#         RedisDisconnect: 自动重连 + 从 last_delivered_id 恢复
#     """
#
#     def __init__(
#         self,
#         redis: RedisCluster,
#         topic: str,
#         consumer_group: str,
#         consumer_name: str,
#         handler: Callable[[dict[str, object]], Awaitable[None]],
#         settings: Settings,
#     ) -> None:
#         """
#         [函数名] __init__
#         [职责] StreamConsumer 初始化
#         [参数说明]
#           参数1: redis RedisCluster 必填 Redis cluster 异步客户端
#           参数2: topic str 必填 已注册的 Stream topic
#           参数3: consumer_group str 必填 consumer group 名称
#           参数4: consumer_name str 必填 本机消费者标识
#           参数5: handler Callable 必填 事件处理函数（必须幂等）
#           参数6: settings Settings 必填 配置
#         [前置条件] topic 已在 TopicRegistry 注册且 mode=stream
#         [后置条件] consumer group 已创建（MKSTREAM）
#         """
#         ...
#
#     async def start(self) -> None:
#         """
#         [函数名] start
#         [职责] 启动消费循环
#
#         [前置条件] consumer group 已存在
#         [后置条件] 后台 task 持续消费
#         [并发安全] 多次调用安全（幂等）
#         [错误码]
#           错误码1: BUS_DISCONNECT Redis 不可达 自动重连 + 重新订阅
#         """
#         ...
#
#     async def stop(self) -> None:
#         """
#         [函数名] stop
#         [职责] 优雅停止消费循环
#
#         [前置条件] start() 已调用
#         [后置条件] task 取消；in-flight 消息由其他 consumer 接管（XAUTOCLAIM）
#         """
#         ...
#
#     async def consume_loop(self) -> None:
#         """
#         [函数名] consume_loop
#         [职责] 主消费循环：XREADGROUP + handler 调用 + XACK
#
#         [错误码]
#           错误码1: BUS_DISCONNECT Redis 断开 重连 + 从 last_delivered_id 恢复
#         [性能约束] XREADGROUP block 5s；handler 顺序执行
#         """
#         ...
#
#     async def _handle_message(
#         self,
#         message_id: str,
#         fields: dict[str, str],
#     ) -> None:
#         """
#         [函数名] _handle_message
#         [职责] 单条消息处理（含超时与异常转 DLQ）
#
#         [参数说明]
#           参数1: message_id str 必填 Stream 消息 ID
#           参数2: fields dict 必填 消息字段（包含 trace_id/payload）
#
#         [错误码]
#           错误码1: BUS_HANDLER_TIMEOUT 30s handler 超时 转 DLQ
#           错误码2: BUS_HANDLER_EXCEPTION handler 抛异常 转 DLQ
#         [幂等性] handler 异常后 XACK；DLQ 由人工 / 定时任务处理
#         """
#         ...
#
#     async def _move_to_dlq(
#         self,
#         message_id: str,
#         fields: dict[str, str],
#         reason: str,
#     ) -> None:
#         """
#         [函数名] _move_to_dlq
#         [职责] 将失败消息写入 dead-letter stream
#
#         [参数说明]
#           参数1: message_id str 必填 原始消息 ID
#           参数2: fields dict 必填 原始消息字段
#           参数3: reason str 必填 失败原因（timeout/exception/...）
#         """
#         ...
#
#     async def reclaim_idle(self) -> int:
#         """
#         [函数名] reclaim_idle
#         [职责] XAUTOCLAIM 抢占 idle 超过 min_idle_time 的消息
#
#         [返回值]
#           类型: int
#           描述: 抢占的消息数
#         [性能约束] min_idle_time 300s；XAUTOCLAIM 周期 60s
#         """
#         ...
