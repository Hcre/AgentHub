# M-EV01 接口注释清单 API-M-EV01-MCP-V1.0-20260603

> 覆盖 IC-020 (bus.publish) / IC-021 (bus.subscribe)
> [DD-001:IC-020 + IC-021]

---

## IC-020 bus.publish → bus.py::EventBus.publish

```
[接口编号] IC-020
[关联契约] IC-020（来自DD-001）
[实现文件] src/agenthub/eventbus/bus.py
[函数签名注释]
  async def publish(
      topic: str,                              # 主题枚举
      payload: dict[str, object],              # 事件载荷（schema 校验）
      trace_id: str,                           # 全链路追踪 ID
      mode: Literal["pubsub","stream"] = "pubsub"  # 关键 topic 强制 stream
  ) -> str
[参数说明] 详见 bus.py 中 publish() docstring
[返回值] message_id: str（Stream=XADD ID；Pub/Sub=ack count）
[错误码] BUS_SCHEMA_VIOLATION(400) / BUS_REDIS_DOWN(503)
[并发安全] fan-out 由 Redis 保证
[幂等性] Pub/Sub 否；Stream 是
[性能约束] 投递 P95 ≤ 50ms
[来源标注] [DD-001:IC-020 + AR洞察-1 + DDR-002]
```

## IC-021 bus.subscribe → bus.py::EventBus.subscribe

```
[接口编号] IC-021
[关联契约] IC-021（来自DD-001）
[实现文件] src/agenthub/eventbus/bus.py（委托 stream_consumer.StreamConsumer）
[函数签名注释]
  async def subscribe(
      topic: str,                              # 主题
      handler: Callable[[dict], Awaitable[None]],  # 必须幂等
      mode: Literal["pubsub","stream"] = "pubsub",
      consumer_group: str | None = None        # stream 模式必填
  ) -> UUID
[参数说明] 详见 bus.py 中 subscribe() docstring
[返回值] subscription_id: UUID
[错误码] BUS_HANDLER_EXCEPTION(→DLQ) / BUS_DISCONNECT(→重连)
[并发安全] consumer group 分布式安全
[幂等性] handler 必须幂等（消费方责任）
[性能约束] handler ≤ 30s（超 → DLQ）
[来源标注] [DD-001:IC-021]
```

## IC-020 内嵌错误码（领域异常）
- EventBusSchemaViolationError: 400 BUS_SCHEMA_VIOLATION
- EventBusRedisDownError: 503 BUS_REDIS_DOWN

[来源标注] [DD-001:IC-020 + IC-021 + MD-MCP-V1.0-M-EV01]
