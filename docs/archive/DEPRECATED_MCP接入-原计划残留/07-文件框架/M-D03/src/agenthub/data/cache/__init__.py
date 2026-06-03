"""Cache & Queue 模块入口（M-D03）.

[文件路径] src/agenthub/data/cache/__init__.py
[文件职责] M-D03 模块初始化，导出公共接口
[所属模块] M-D03（来自 DD-001）
[关联设计规范] FS-021 / MD-M-D03 / IC-019（来自 DD-001）
[功能描述]
  功能1: 导出 RedisClusterClient (Flyweight) 连接池客户端
  功能2: 导出 CacheProxy[T] 泛型缓存代理
  功能3: 导出 StreamPublisher / StreamConsumer（关键事件）
  功能4: 导出 PubSubPublisher / PubSubSubscriber（非关键事件）
[输入输出]
  输入: 来自上层模块（M-B01/M-B04/M-C04/M-A02 等）的缓存/队列调用
  输出: Redis cluster 的 KV/Stream/Pub/Sub 操作结果
[依赖关系]
  依赖文件: ./client.py、./proxy.py、./stream.py、./pubsub.py
  被依赖文件:
    - M-B01 market/services.py: 通过 CacheProxy 缓存 MCPServerRepository
    - M-B04 approval/allowlist.py: 通过 CacheProxy 缓存 allowlist
    - M-C04 dns_pinning/cache.py: 通过 CacheProxy 缓存 DNS 结果
    - M-A02 ws_gateway/offline_queue.py: 通过 Stream 写入离线消息
    - M-EV01 eventbus/bus.py: 通过 PubSub/Stream 转发事件
[注意事项]
  注意1: 模块边界硬约束：本文件仅 M-D03 使用，禁止被其他模块直接 import 内部子模块
  注意2: 公共导出严格控制，避免破坏 Flyweight 单例属性
  注意3: 所有异步接口需通过 redis-py async API 暴露
  注意4: Key 命名必须包含 {workspace_id} 哈希标签以确保 cluster 同 slot
[代码风格] 遵循 CS-MCP-V1.0 §1（来自 DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-D03 - 初始模块入口文件
[作者] DD-M-D03-20260602
[来源标注] [DD-001:FS-021 / MD-M-D03]
"""

from __future__ import annotations

from agenthub.data.cache.client import RedisClusterClient
from agenthub.data.cache.proxy import CacheProxy
from agenthub.data.cache.pubsub import PubSubPublisher, PubSubSubscriber
from agenthub.data.cache.stream import StreamConsumer, StreamPublisher

__all__ = [
    "RedisClusterClient",
    "CacheProxy",
    "StreamPublisher",
    "StreamConsumer",
    "PubSubPublisher",
    "PubSubSubscriber",
]
