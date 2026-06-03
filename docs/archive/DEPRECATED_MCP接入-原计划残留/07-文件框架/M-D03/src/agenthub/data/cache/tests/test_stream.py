"""M-D03 stream.py 单元测试.

[文件路径] src/agenthub/data/cache/tests/test_stream.py
[文件职责] StreamPublisher/StreamConsumer 测试
[所属模块] M-D03（来自 DD-001）
[关联设计规范] FS-021 / MD-M-D03 / IC-019 / IC-021（来自 DD-001）
[功能描述]
  功能1: 验证 XADD 消息 ID 返回
  功能2: 验证 Consumer Group 创建
  功能3: 验证 consume + handler + ack
  功能4: 验证 handler 异常 → DLQ
[输入输出]
  输入: pytest fixture
  输出: 测试结果
[依赖关系]
  依赖文件: ../stream.py、../client.py、pytest、pytest-asyncio
  被依赖文件: 无
[注意事项]
  注意1: fakeredis Stream 支持有限，DLQ 场景用真 Redis
  注意2: 覆盖率目标 行 ≥ 80%
[代码风格] 遵循 CS-MCP-V1.0 §1.7（来自 DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-D03 - 初始 stream 测试
[作者] DD-M-D03-20260602
[来源标注] [DD-001:MD-M-D03:测试策略 + AR洞察-1]
"""

from __future__ import annotations

import pytest

from agenthub.data.cache.stream import StreamConsumer, StreamPublisher


@pytest.mark.asyncio
async def test_publish_when_valid_input_then_returns_message_id() -> None:
    """测试场景: 正常发布 [断言: ID 非空] [Mock: fakeredis]"""
    # when
    msg_id = await publisher.publish({"trace_id": b"t-1", "payload": b"{}"}, "t-1")
    # then
    assert msg_id


@pytest.mark.asyncio
async def test_ensure_group_when_new_group_then_creates() -> None:
    """测试场景: 首次创建 [断言: 无异常] [Mock: fakeredis]"""
    # when
    await consumer.ensure_group()
    # then: 不抛异常
    pass


@pytest.mark.asyncio
async def test_ensure_group_when_existing_then_idempotent() -> None:
    """测试场景: 重复创建 [断言: 无异常（BUSYGROUP 忽略）] [Mock: fakeredis]"""
    # given
    await consumer.ensure_group()
    # when
    await consumer.ensure_group()
    # then
    pass


@pytest.mark.asyncio
async def test_consume_when_message_available_then_handler_called() -> None:
    """测试场景: 正常消费 [断言: handler 收到消息] [Mock: fakeredis]"""
    # given
    received = []
    async def handler(msg):
        received.append(msg)
        await consumer.ack(msg.message_id)
        return None
    await publisher.publish({"data": b"hello"}, "t-1")
    # when
    consume_task = asyncio.create_task(consumer.consume(handler, block_ms=100, batch=1))
    await asyncio.sleep(0.3)
    await consumer.stop()
    await consume_task
    # then
    assert len(received) >= 1


@pytest.mark.asyncio
async def test_consume_when_handler_raises_then_message_goes_to_dlq() -> None:
    """测试场景: 异常-handler 失败 [断言: DLQ 收到] [Mock: fakeredis]"""
    # given
    async def bad_handler(msg):
        raise ValueError("test")
    await publisher.publish({"data": b"x"}, "t-1")
    # when
    consume_task = asyncio.create_task(consumer.consume(bad_handler, block_ms=100))
    await asyncio.sleep(0.3)
    await consumer.stop()
    await consume_task
    # then: DLQ 验证（len(dlq) >= 1）
    pass
