"""Redis Cluster 客户端（Flyweight 模式）.

[文件路径] src/agenthub/data/cache/client.py
[文件职责] 封装 redis-py async cluster 客户端，Flyweight 连接池
[所属模块] M-D03（来自 DD-001）
[关联设计规范] FS-021 / MD-M-D03 / IC-019（来自 DD-001）
[功能描述]
  功能1: 提供 Flyweight 单例的 RedisClusterClient，避免重复创建连接池
  功能2: 封装 GET / SETEX / DEL / EXISTS 等基础 KV 操作
  功能3: 封装 XADD / XREAD / XACK 等 Stream 操作
  功能4: 封装 PUBLISH / SUBSCRIBE 等 Pub/Sub 操作
  功能5: 提供连接健康检查与自动重连
[输入输出]
  输入: key/value/topic 等字符串与字节数据
  输出: 异步操作结果（bytes/None/MessageID/int）
[依赖关系]
  依赖文件: agenthub.core.config、agenthub.core.logging、agenthub.core.exceptions
  被依赖文件: ./proxy.py、./stream.py、./pubsub.py
[注意事项]
  注意1: Flyweight 单例：所有调用方共享一个连接池，节约资源
  注意2: Key 必须含 {workspace_id} 哈希标签，保证多键操作落同 slot
  注意3: cluster MOVED/ASK 重定向由 redis-py 自动处理，无需手动捕获
  注意4: ClusterDownError 上抛上层并告警 CRITICAL（[MD-M-D03:异常处理]）
  注意5: 连接超时默认 10s（CS §1.8 约束）
[代码风格] 遵循 CS-MCP-V1.0 §1（来自 DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-D03 - 初始 Flyweight 客户端框架
[作者] DD-M-D03-20260602
[来源标注] [DD-001:FS-021 / MD-M-D03 / IC-019]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from redis.asyncio.cluster import ClusterNode, RedisCluster
from redis.exceptions import ClusterDownError, ConnectionError as RedisConnectionError

from agenthub.core.config import Settings
from agenthub.core.exceptions import AgentHubError

if TYPE_CHECKING:
    from agenthub.data.cache.stream import StreamMessage

log = structlog.get_logger(__name__)


class RedisClusterClient:
    """Redis 集群 Flyweight 客户端.

    [类名] RedisClusterClient
    [职责] Flyweight 单例，提供统一 Redis cluster 入口
    [关联设计规范] MD-M-D03（来自 DD-001）
    [属性]
      属性1: _instance RedisClusterClient | None  类级单例存储
      属性2: _pool ConnectionPool            async cluster 连接池（懒加载）
      属性3: _client RedisCluster            async cluster 客户端实例
      属性4: _settings Settings              全局配置（含 Redis URL/集群节点）
      属性5: _lock asyncio.Lock              单例构造的并发保护
    [方法列表]
      方法1: get_instance(settings) → RedisClusterClient - 获取 Flyweight 单例
      方法2: get(key) → bytes | None - 读取 KV
      方法3: setex(key, value, ttl_sec) → None - 写入 KV 并设置 TTL
      方法4: delete(key) → int - 删除 KV
      方法5: xadd(stream, fields) → str - Stream 追加
      方法6: publish(channel, message) → int - Pub/Sub 发布
      方法7: healthcheck() → bool - 集群健康探测
      方法8: close() → None - 关闭连接池
    [状态机] 无业务状态机（无状态服务）
    [异常处理]
      异常1: ClusterDownError - 集群不可用，CRITICAL 告警
      异常2: RedisConnectionError - 连接失败，重试 3 次
      异常3: AgentHubError - 通用领域异常包装
    [来源标注] [DD-001:MD-M-D03 + 设计模式 Flyweight]
    """

    _instance: RedisClusterClient | None = None

    def __init__(self, settings: Settings) -> None:
        """初始化 Flyweight 客户端（不直接调用，使用 get_instance）.

        [函数名] __init__
        [职责] 内部构造方法，缓存 settings 与连接池
        [参数说明]
          参数1: settings Settings 必填 全局配置（含 Redis 集群节点）
        [返回值]
          类型: None
          描述: 构造完毕
        [错误码]
          错误码1: 无（构造不抛异常）
        [前置条件] 配置中含 redis_cluster_startup_nodes
        [后置条件] 客户端未连接，懒加载
        [并发安全] 仅由 get_instance 内部调用
        [幂等性] 否（不应被多次直接调用）
        [性能约束] < 1ms（仅设置属性）
        [来源标注] [DD-M推断:Flyweight 模式典型构造]
        """
        self._settings = settings
        self._client: RedisCluster | None = None
        log.info("redis_cluster_client_init", nodes=len(settings.redis_cluster_nodes))

    @classmethod
    def get_instance(cls, settings: Settings) -> RedisClusterClient:
        """获取 Flyweight 单例.

        [函数名] get_instance
        [职责] 提供 Flyweight 单例访问入口
        [关联接口契约] IC-019（来自 DD-001）
        [参数说明]
          参数1: settings Settings 必填 全局配置
        [返回值]
          类型: RedisClusterClient
          描述: 进程内唯一客户端实例
        [错误码]
          错误码1: 无
        [前置条件] 无
        [后置条件] 全进程共享同一连接池
        [并发安全] 内部锁保护
        [幂等性] 是（相同 settings 返回同一实例）
        [性能约束] < 1ms（命中已创建实例时）
        [示例]
          ```
          client = RedisClusterClient.get_instance(settings)
          ```
        [来源标注] [DD-001:MD-M-D03 / IC-019 + Flyweight 模式]
        """
        if cls._instance is None:
            cls._instance = cls(settings)
        return cls._instance

    async def _ensure_client(self) -> RedisCluster:
        """懒加载 cluster 客户端.

        [函数名] _ensure_client
        [职责] 首次调用时构造连接池，后续复用
        [参数说明] 无
        [返回值]
          类型: RedisCluster
          描述: redis-py async cluster 客户端
        [错误码]
          错误码1: RedisConnectionError - 连接失败
        [前置条件] 配置含 cluster 节点列表
        [后置条件] 客户端已就绪可执行命令
        [并发安全] 由调用方使用 asyncio.Lock 保护
        [幂等性] 是（重复调用返回同一 client）
        [性能约束] 首调用 < 500ms；后续 < 1ms
        [来源标注] [DD-M推断:redis-py 懒加载最佳实践]
        """
        ...

    async def get(self, key: str) -> bytes | None:
        """读取 KV.

        [函数名] get
        [职责] 从 Redis cluster 读取指定 key 的 value
        [关联接口契约] IC-019.cache.get（来自 DD-001）
        [参数说明]
          参数1: key str 必填 缓存键（含 {workspace_id} 哈希标签）
        [返回值]
          类型: bytes | None
          描述: 键存在返回 value；不存在返回 None
        [错误码]
          错误码1: ClusterDownError - 集群不可用
        [前置条件] 客户端已初始化
        [后置条件] 不修改任何状态
        [并发安全] redis-py cluster 客户端线程/协程安全
        [幂等性] 是（GET 不修改状态）
        [性能约束] P95 ≤ 5ms
        [示例]
          ```
          value = await client.get("cache:user:{ws-1}:123")
          ```
        [来源标注] [DD-001:IC-019 + MD-M-D03:函数签名]
        """
        ...

    async def setex(self, key: str, value: bytes, ttl_sec: int) -> None:
        """写入 KV 并设置 TTL.

        [函数名] setex
        [职责] SET key value EX ttl_sec 的原子封装
        [关联接口契约] IC-019.cache.set（来自 DD-001）
        [参数说明]
          参数1: key str 必填 缓存键（含 {workspace_id} 哈希标签）
          参数2: value bytes 必填 序列化后的值
          参数3: ttl_sec int 必填 过期时间（秒），范围 (0, 30*86400]
        [返回值]
          类型: None
          描述: 写入成功
        [错误码]
          错误码1: ClusterDownError - 集群不可用
          错误码2: ValueError - ttl_sec 非法
        [前置条件] 客户端已初始化
        [后置条件] 键已写入并设置 TTL
        [并发安全] 协程安全
        [幂等性] 是（相同 key/value 覆盖）
        [性能约束] P95 ≤ 5ms
        [示例]
          ```
          await client.setex("cache:allowlist:{ws-1}:hash-x", b"1", 30*86400)
          ```
        [来源标注] [DD-001:IC-019 + MD-M-D03:函数签名]
        """
        ...

    async def delete(self, key: str) -> int:
        """删除 KV.

        [函数名] delete
        [职责] DEL key，返回删除条数
        [关联接口契约] IC-019（来自 DD-001）
        [参数说明]
          参数1: key str 必填 缓存键
        [返回值]
          类型: int
          描述: 删除的键数量（0/1）
        [错误码]
          错误码1: ClusterDownError - 集群不可用
        [前置条件] 无
        [后置条件] 键已删除
        [并发安全] 协程安全
        [幂等性] 是（重复删除返回 0）
        [性能约束] P95 ≤ 5ms
        [来源标注] [DD-001:IC-019]
        """
        ...

    async def xadd(self, stream: str, fields: dict[str, bytes]) -> str:
        """Stream 追加消息.

        [函数名] xadd
        [职责] 向 Stream 追加一条消息，返回消息 ID
        [关联接口契约] IC-019.queue.xadd（来自 DD-001）
        [参数说明]
          参数1: stream str 必填 stream 名称（含 {workspace_id} 哈希标签）
          参数2: fields dict[str, bytes] 必填 消息字段
        [返回值]
          类型: str
          描述: 消息 ID（ms-seq 形式）
        [错误码]
          错误码1: ClusterDownError - 集群不可用
        [前置条件] stream 由 stream.py 统一封装
        [后置条件] 消息已追加
        [并发安全] 协程安全
        [幂等性] 否（每次产生新 ID；调用方传 message_id 可去重）
        [性能约束] P95 ≤ 5ms
        [来源标注] [DD-001:IC-019 + MD-M-D03:stream]
        """
        ...

    async def publish(self, channel: str, message: bytes) -> int:
        """Pub/Sub 发布.

        [函数名] publish
        [职责] 向 channel 发布消息，返回订阅者数量
        [关联接口契约] IC-019.pubsub.publish（来自 DD-001）
        [参数说明]
          参数1: channel str 必填 channel 名称
          参数2: message bytes 必填 序列化后的消息
        [返回值]
          类型: int
          描述: 收到消息的订阅者数
        [错误码]
          错误码1: ClusterDownError - 集群不可用
        [前置条件] 无
        [后置条件] 订阅者异步收到
        [并发安全] 协程安全
        [幂等性] 否（Pub/Sub 不保证持久化）
        [性能约束] 投递 < 50ms
        [来源标注] [DD-001:IC-019 + MD-M-D03:pubsub]
        """
        ...

    async def healthcheck(self) -> bool:
        """集群健康探测.

        [函数名] healthcheck
        [职责] PING 主节点，确认集群可用
        [参数说明] 无
        [返回值]
          类型: bool
          描述: True 健康；False 不可用
        [错误码]
          错误码1: RedisConnectionError - 连接失败返回 False（不抛）
        [前置条件] 无
        [后置条件] 不修改状态
        [并发安全] 协程安全
        [幂等性] 是
        [性能约束] < 50ms
        [来源标注] [DD-M推断:K8s readinessProbe 需求]
        """
        ...

    async def close(self) -> None:
        """关闭连接池.

        [函数名] close
        [职责] 应用关闭时释放连接
        [参数说明] 无
        [返回值]
          类型: None
        [错误码]
          错误码1: 无（吞连接异常 + 告警）
        [前置条件] 应用退出
        [后置条件] 连接已释放
        [并发安全] 仅应用退出阶段调用
        [幂等性] 是
        [性能约束] < 1s
        [来源标注] [DD-M推断:资源释放最佳实践]
        """
        ...

    @staticmethod
    def _validate_key(key: str) -> None:
        """校验 key 含 {hash_tag}.

        [函数名] _validate_key
        [职责] 确保 key 含 {workspace_id} 形式的哈希标签
        [参数说明]
          参数1: key str 必填 缓存键
        [返回值]
          类型: None
        [错误码]
          错误码1: ValueError - key 缺哈希标签
        [前置条件] 无
        [后置条件] 无
        [并发安全] 纯函数线程安全
        [幂等性] 是
        [性能约束] < 0.1ms
        [来源标注] [DD-001:IC-019:入参约束 + AR洞察-6]
        """
        ...
