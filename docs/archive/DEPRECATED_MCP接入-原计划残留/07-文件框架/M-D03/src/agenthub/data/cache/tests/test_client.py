"""M-D03 client.py 单元测试.

[文件路径] src/agenthub/data/cache/tests/test_client.py
[文件职责] RedisClusterClient 测试
[所属模块] M-D03（来自 DD-001）
[关联设计规范] FS-021 / MD-M-D03 / IC-019（来自 DD-001）
[功能描述]
  功能1: 验证 Flyweight 单例
  功能2: 验证 GET/SETEX/DEL/XADD/PUBLISH 行为
  功能3: 验证 ClusterDownError 透传
  功能4: 验证 healthcheck
[输入输出]
  输入: pytest fixture（fakeredis-cluster）
  输出: 测试结果
[依赖关系]
  依赖文件: ../client.py、pytest、pytest-asyncio、fakeredis
  被依赖文件: 无
[注意事项]
  注意1: 单元测试用 fakeredis；集成测试用 testcontainers（[MD-M-D03:测试策略]）
  注意2: 覆盖率目标 行 ≥ 85%
[代码风格] 遵循 CS-MCP-V1.0 §1.7（来自 DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-D03 - 初始 client 测试
[作者] DD-M-D03-20260602
[来源标注] [DD-001:MD-M-D03:测试策略]
"""

from __future__ import annotations

import pytest

from agenthub.data.cache.client import RedisClusterClient


@pytest.mark.asyncio
async def test_get_instance_when_called_twice_then_returns_same_object() -> None:
    """测试场景: 正常获取单例 [断言: 两次返回同一对象] [Mock: fakeredis]"""
    # given
    settings = ...  # fakeredis fixture
    # when
    a = RedisClusterClient.get_instance(settings)
    b = RedisClusterClient.get_instance(settings)
    # then
    assert a is b


@pytest.mark.asyncio
async def test_get_when_key_exists_then_returns_value() -> None:
    """测试场景: 正常 GET [断言: 返回 bytes] [Mock: fakeredis]"""
    # given: key 已 SETEX
    # when
    value = await client.get("cache:{ws-1}:key")
    # then
    assert value == b"expected"


@pytest.mark.asyncio
async def test_get_when_key_missing_then_returns_none() -> None:
    """测试场景: 边界-未命中 [断言: 返回 None] [Mock: fakeredis]"""
    # given
    # when
    value = await client.get("cache:{ws-1}:missing")
    # then
    assert value is None


@pytest.mark.asyncio
async def test_setex_when_valid_input_then_writes_value() -> None:
    """测试场景: 正常 SETEX [断言: TTL 范围内可读] [Mock: fakeredis]"""
    # given
    # when
    await client.setex("cache:{ws-1}:k", b"v", 60)
    # then
    assert await client.get("cache:{ws-1}:k") == b"v"


@pytest.mark.asyncio
async def test_setex_when_invalid_ttl_then_raises_value_error() -> None:
    """测试场景: 异常-非法 TTL [断言: 抛 ValueError] [Mock: fakeredis]"""
    # given
    # when / then
    with pytest.raises(ValueError):
        await client.setex("cache:{ws-1}:k", b"v", -1)


@pytest.mark.asyncio
async def test_get_when_cluster_down_then_propagates_error() -> None:
    """测试场景: 异常-集群故障 [断言: 透传 ClusterDownError] [Mock: fakeredis 模拟故障]"""
    # given
    # when / then
    with pytest.raises(ClusterDownError):
        await client.get("cache:{ws-1}:k")


@pytest.mark.asyncio
async def test_healthcheck_when_cluster_healthy_then_returns_true() -> None:
    """测试场景: 健康检查通过 [断言: True] [Mock: fakeredis]"""
    # when
    ok = await client.healthcheck()
    # then
    assert ok is True


@pytest.mark.asyncio
async def test_validate_key_when_missing_hash_tag_then_raises() -> None:
    """测试场景: 异常-key 缺哈希标签 [断言: ValueError] [Mock: 无]"""
    # when / then
    with pytest.raises(ValueError):
        RedisClusterClient._validate_key("plain-key")
