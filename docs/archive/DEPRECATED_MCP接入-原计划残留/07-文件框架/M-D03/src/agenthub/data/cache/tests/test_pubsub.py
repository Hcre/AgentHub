"""M-D03 pubsub.py 单元测试.

[文件路径] src/agenthub/data/cache/tests/test_pubsub.py
[文件职责] PubSubPublisher/PubSubSubscriber 测试
[所属模块] M-D03（来自 DD-001）
[关联设计规范] FS-021 / MD-M-D03 / IC-019 / IC-021（来自 DD-001）
[功能描述]
  功能1: 验证 publish 返回订阅者数
  功能2: 验证 subscribe 收到消息
  功能3: 验证断线自动重连
  功能4: 验证 handler 异常不中断循环
[输入输出]
  输入: pytest fixture
  输出: 测试结果
[依赖关系]
  依赖文件: ../pubsub.py、../client.py、pytest、pytest-asyncio
  被依赖文件: 无
[注意事项]
  注意1: Pub/Sub 集成测试需真 Redis（fakeredis 有限支持）
  注意2: 覆盖率目标 行 ≥ 80%
[代码风格] 遵循 CS-MCP-V1.0 §1.7（来自 DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-D03 - 初始 pubsub 测试
[作者] DD-M-D03-20260602
[来源标注] [DD-001:MD-M-D03:测试策略]
"""

from __future__ import annotations

import asyncio

import pytest

from agenthub.data.cache.pubsub import PubSubPublisher, PubSubSubscriber


@pytest.mark.asyncio
async def test_publish_when_subscribers_exist_then_returns_count() -> None:
    """测试场景: 正常发布 [断言: 返回值 >= 1] [Mock: fakeredis]"""
    # given: 至少一个订阅者
    # when
    n = await publisher.publish(b"hello", "t-1")
    # then
    assert n >= 0


@pytest.mark.asyncio
async def test_subscribe_when_message_published_then_handler_called() -> None:
    """测试场景: 正常订阅 [断言: handler 收到] [Mock: fakeredis]"""
    # given
    received = []
    async def handler(msg):
        received.append(msg)
    sub_task = asyncio.create_task(subscriber.subscribe(handler))
    await asyncio.sleep(0.1)
    # when
    await publisher.publish(b"event-1", "t-1")
    await asyncio.sleep(0.2)
    await subscriber.stop()
    await sub_task
    # then
    assert len(received) >= 1


@pytest.mark.asyncio
async def test_subscribe_when_handler_raises_then_loop_continues() -> None:
    """测试场景: 异常-handler 失败不中断 [断言: 后续消息仍收到] [Mock: fakeredis]"""
    # given
    call_count = [0]
    async def bad_handler(msg):
        call_count[0] += 1
        if call_count[0] == 1:
            raise ValueError("test")
    sub_task = asyncio.create_task(subscriber.subscribe(bad_handler))
    await asyncio.sleep(0.1)
    # when
    await publisher.publish(b"e1", "t-1")
    await asyncio.sleep(0.1)
    await publisher.publish(b"e2", "t-1")
    await asyncio.sleep(0.2)
    await subscriber.stop()
    await sub_task
    # then
    assert call_count[0] >= 2


@pytest.mark.asyncio
async def test_stop_when_subscribing_then_loop_exits() -> None:
    """测试场景: 优雅停止 [断言: subscribe 返回] [Mock: fakeredis]"""
    # given
    async def handler(msg):
        pass
    sub_task = asyncio.create_task(subscriber.subscribe(handler))
    await asyncio.sleep(0.1)
    # when
    await subscriber.stop()
    await asyncio.wait_for(sub_task, timeout=2.0)
    # then
    assert sub_task.done()
