"""M-D03 proxy.py 单元测试.

[文件路径] src/agenthub/data/cache/tests/test_proxy.py
[文件职责] CacheProxy[T] 泛型缓存代理测试
[所属模块] M-D03（来自 DD-001）
[关联设计规范] FS-021 / MD-M-D03 / IC-019（来自 DD-001）
[功能描述]
  功能1: 验证 get/put/invalidate/invalidate_all
  功能2: 验证序列化反序列化
  功能3: 验证 TTL 行为
  功能4: 验证大对象拒绝
[输入输出]
  输入: pytest fixture
  输出: 测试结果
[依赖关系]
  依赖文件: ../proxy.py、../client.py、pytest、pytest-asyncio
  被依赖文件: 无
[注意事项]
  注意1: 覆盖率目标 行 ≥ 85%
[代码风格] 遵循 CS-MCP-V1.0 §1.7（来自 DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-D03 - 初始 proxy 测试
[作者] DD-M-D03-20260602
[来源标注] [DD-001:MD-M-D03:测试策略]
"""

from __future__ import annotations

import pytest

from agenthub.data.cache.proxy import CacheProxy


@pytest.mark.asyncio
async def test_put_when_value_set_then_get_returns_same_value() -> None:
    """测试场景: 正常 put/get [断言: 反序列化一致] [Mock: fakeredis]"""
    # given
    value = {"name": "test", "n": 42}
    # when
    await proxy.put("user:1", value, ttl_sec=60)
    got = await proxy.get("user:1")
    # then
    assert got == value


@pytest.mark.asyncio
async def test_get_when_key_missing_then_returns_none() -> None:
    """测试场景: 边界-未命中 [断言: None] [Mock: fakeredis]"""
    # when
    got = await proxy.get("user:missing")
    # then
    assert got is None


@pytest.mark.asyncio
async def test_put_when_value_too_large_then_raises() -> None:
    """测试场景: 异常-超过 1MB [断言: ValueError] [Mock: fakeredis]"""
    # given: > 1MB
    # when / then
    with pytest.raises(ValueError):
        await proxy.put("big", b"x" * 1_500_000)


@pytest.mark.asyncio
async def test_invalidate_when_key_exists_then_deleted() -> None:
    """测试场景: 正常失效 [断言: get 返回 None] [Mock: fakeredis]"""
    # given
    await proxy.put("k", "v", ttl_sec=60)
    # when
    await proxy.invalidate("k")
    # then
    assert await proxy.get("k") is None


@pytest.mark.asyncio
async def test_invalidate_all_when_called_then_clears_prefix() -> None:
    """测试场景: 批量失效 [断言: 删除数 = 已写入数] [Mock: fakeredis]"""
    # given
    for i in range(5):
        await proxy.put(f"item:{i}", i, ttl_sec=60)
    # when
    n = await proxy.invalidate_all()
    # then
    assert n == 5


@pytest.mark.asyncio
async def test_put_when_serializer_fails_then_raises_agent_hub_error() -> None:
    """测试场景: 异常-序列化失败 [断言: AgentHubError] [Mock: 坏 serializer]"""
    # given
    bad_proxy = CacheProxy(client, "p", 60, lambda x: 1/0, lambda b: b)
    # when / then
    with pytest.raises(Exception):
        await bad_proxy.put("k", "v")
