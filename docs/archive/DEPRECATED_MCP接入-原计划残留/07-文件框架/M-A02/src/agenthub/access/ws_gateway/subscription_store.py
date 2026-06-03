"""SubscriptionStore - 订阅持久化 (M-A02).

[文件路径] src/agenthub/access/ws_gateway/subscription_store.py
[文件职责] 订阅关系持久化（PG DE-013 主存 + Redis hash 加速查询）
[所属模块] M-A02
[关联设计规范] MD-M-A02 §类设计 SubscriptionStore / IC-002
[功能描述]
  功能1: add - 持久化 (client_id, topic) 关系
  功能2: remove - 退订清理
  功能3: list_topics - 查某 client 的所有 topic
  功能4: list_subscribers - 查某 topic 的所有 client
[输入输出]
  输入: client_id, topic
  输出: 持久化结果 / 查询列表
[依赖关系]
  依赖文件: M-D01 Repository（PG DE-013）、M-D03 Redis client
  被依赖文件: handlers/subscribe.py, bus_listener.py
[注意事项]
  注意1: PG 写失败应回滚 Redis 写入（防数据不一致）
  注意2: Redis hash 仅作缓存，主存为 PG
  注意3: list_subscribers 性能 ≤ 5ms（Redis hash O(1) + 反查）
[代码风格] 遵循CS-MCP §1
[创建日期] 2026-06-02
[作者] DD-M-A02
[来源标注] [DD-001:MD-M-A02 类设计 SubscriptionStore]
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from agenthub.core.logging import get_logger

if TYPE_CHECKING:
    from agenthub.data.cache.client import RedisClusterClient
    from agenthub.data.metadata.repositories.subscription_repo import SubscriptionRepository

log = get_logger(__name__)


class SubscriptionStore:
    """订阅持久化（PG + Redis hash 双写）.

    [类名] SubscriptionStore
    [职责] 管理 client ↔ topic 订阅关系，双写 PG/Redis
    [关联设计规范] MD-M-A02 / IC-002
    [属性]
      pg: SubscriptionRepository PG Repository（DE-013 表）
      redis: RedisClusterClient Redis hash 缓存
    [方法列表]
      add(client_id, topic) -> None
      remove(client_id, topic) -> None
      list_topics(client_id) -> list[str]
      list_subscribers(topic) -> list[str]
    [异常处理]
      PG 写失败 → 上抛 + 清理 Redis；Redis 失败 → 内存 dict 兜底 + 告警
    [来源标注] [DD-001:MD-M-A02 类设计 SubscriptionStore]
    """

    def __init__(self, pg: "SubscriptionRepository", redis: "RedisClusterClient") -> None:
        """[函数名] __init__
        [职责] 构造 SubscriptionStore
        [参数说明]
          pg: SubscriptionRepository 必填
          redis: RedisClusterClient 必填
        [来源标注] [DD-001:MD-M-A02 类设计]
        """
        ...

    async def add(self, client_id: str, topic: str, agent_id: UUID) -> None:
        """[函数名] add
        [职责] 持久化 (client_id, topic, agent_id) 订阅关系
        [参数说明]
          client_id: str 必填 socketio sid
          topic: str 必填 事件 topic
          agent_id: UUID 必填 订阅者
        [前置条件] 客户端已认证（connect 通过）
        [后置条件] PG/Redis 双写成功
        [并发安全] 同一 (client, topic) 重复 add 幂等
        [幂等性] 是
        [性能约束] P95 ≤ 10ms
        [来源标注] [DD-001:MD-M-A02 add]
        """
        ...

    async def remove(self, client_id: str, topic: str) -> None:
        """[函数名] remove
        [职责] 退订清理
        [参数说明]
          client_id: str 必填
          topic: str 必填
        [幂等性] 是
        [来源标注] [DD-001:MD-M-A02 remove]
        """
        ...

    async def list_topics(self, client_id: str) -> list[str]:
        """[函数名] list_topics
        [职责] 查询某 client 订阅的所有 topic
        [参数说明]
          client_id: str 必填
        [返回值]
          类型: list[str]
          描述: topic 列表
        [性能约束] P95 ≤ 5ms（Redis 缓存）
        [来源标注] [DD-001:MD-M-A02 list_topics]
        """
        ...

    async def list_subscribers(self, topic: str) -> list[str]:
        """[函数名] list_subscribers
        [职责] 查询某 topic 的所有订阅者 client_id
        [参数说明]
          topic: str 必填
        [返回值]
          类型: list[str]
          描述: client_id 列表
        [性能约束] P95 ≤ 5ms（Redis 缓存）
        [来源标注] [DD-001:MD-M-A02 list_topics 反向]
        """
        ...
