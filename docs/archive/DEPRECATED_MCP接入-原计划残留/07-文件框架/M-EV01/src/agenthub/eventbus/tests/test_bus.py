"""M-EV01 EventBus 单元测试（28 用例骨架）.

[文件路径] src/agenthub/eventbus/tests/test_bus.py
[文件职责] EventBus publish/subscribe 单测（含 Pub/Sub + Stream 双模式）
[所属模块] M-EV01
[关联设计规范] CS-§1.7 / MD-MCP-V1.0-M-EV01（用例数 28）
[创建日期] 2026-06-03
[作者] DD-M-EV01-20260603
[来源标注] [DD-001:CS-§1.7 + MD-MCP-V1.0-M-EV01]
"""

# === 测试场景注释（28 用例）===
#
# [测试场景1: publish_pubsub_normal]
#   - 断言: redis.publish 被调用 + 返回 ack count
#   - Mock: fakeredis
# [测试场景2: publish_stream_normal]
#   - 断言: redis.xadd 返回 ID + Stream TTL 正确
#   - Mock: fakeredis stream
# [测试场景3: publish_schema_violation]
#   - 断言: 抛 EventBusSchemaViolationError
#   - Mock: 无
# [测试场景4: publish_redis_down]
#   - 断言: 抛 EventBusRedisDownError
#   - Mock: redis cluster 模拟 cluster_down
# [测试场景5: publish_critical_topic_force_stream]
#   - 断言: 即使 mode=pubsub，关键 topic 实际走 XADD
#   - Mock: fakeredis stream
# [测试场景6: subscribe_pubsub_normal]
#   - 断言: handler 被调用 + payload 正确
#   - Mock: fakeredis pubsub
# [测试场景7: subscribe_stream_with_group]
#   - 断言: XREADGROUP 调用 + handler 执行 + XACK
#   - Mock: fakeredis stream + consumer group
# [测试场景8: subscribe_handler_exception_to_dlq]
#   - 断言: 消息进入 <topic>.dlq stream
#   - Mock: fakeredis stream
# [测试场景9: subscribe_handler_timeout_to_dlq]
#   - 断言: 30s 超时转 DLQ
#   - Mock: handler 永久 sleep
# [测试场景10: subscribe_redis_disconnect_reconnect]
#   - 断言: 自动重连 + 从 last_delivered_id 恢复
#   - Mock: fakeredis 模拟断连
# [测试场景11~28: 边界 / 并发 / 异常 / Schema 版本等]
#   - 覆盖 MD 用例数 28（含双模式）
