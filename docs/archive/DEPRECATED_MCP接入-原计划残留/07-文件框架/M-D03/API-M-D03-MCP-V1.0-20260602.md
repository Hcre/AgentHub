# 接口注释清单 API-M-D03-MCP-V1.0-20260602

> M-D03 接口契约实现清单（基于 IC-019 Cache & Queue）
> 所有 API 注释 100% 来源于 DD-001 IC-019

---

## API-D03-001 client.get

```
[接口编号] API-D03-001
[关联契约] IC-019.cache.get（来自 DD-001）
[实现文件] src/agenthub/data/cache/client.py → RedisClusterClient.get
[函数签名注释]
  ```python
  async def get(self, key: str) -> bytes | None:
      """读取 KV.

      Args:
          key: 缓存键（含 {workspace_id} 哈希标签）

      Returns:
          键存在返回 value；不存在返回 None

      Raises:
          ClusterDownError: 集群不可用

      Example:
          >>> value = await client.get("cache:user:{ws-1}:123")
          b"..."
      """
  ```
[参数说明] key 必填；含 {workspace_id} 哈希标签保证同 slot
[返回值说明] bytes | None
[错误码说明] REDIS_CLUSTER_DOWN 503（[IC-019]）
[来源标注] [DD-001:IC-019 + MD-M-D03:函数签名]
```

---

## API-D03-002 client.setex

```
[接口编号] API-D03-002
[关联契约] IC-019.cache.set（来自 DD-001）
[实现文件] src/agenthub/data/cache/client.py → RedisClusterClient.setex
[函数签名注释]
  ```python
  async def setex(
      self,
      key: str,
      value: bytes,
      ttl_sec: int,
  ) -> None:
      """写入 KV 并设置 TTL.

      Args:
          key: 缓存键
          value: 序列化后的值
          ttl_sec: 过期时间（秒），范围 (0, 30*86400]

      Raises:
          ClusterDownError: 集群不可用
          ValueError: ttl_sec 非法
      """
  ```
[参数说明] key/value/ttl_sec 必填
[返回值说明] None
[错误码说明] REDIS_CLUSTER_DOWN 503；ttl_sec 非法 400
[来源标注] [DD-001:IC-019 + MD-M-D03:函数签名]
```

---

## API-D03-003 client.delete

```
[接口编号] API-D03-003
[关联契约] IC-019（来自 DD-001）
[实现文件] src/agenthub/data/cache/client.py → RedisClusterClient.delete
[函数签名注释]
  ```python
  async def delete(self, key: str) -> int:
      """删除 KV.

      Args:
          key: 缓存键
      Returns:
          删除的键数量（0/1）
      Raises:
          ClusterDownError: 集群不可用
      """
  ```
[参数说明] key 必填
[返回值说明] int
[错误码说明] REDIS_CLUSTER_DOWN 503
[来源标注] [DD-001:IC-019]
```

---

## API-D03-004 client.xadd

```
[接口编号] API-D03-004
[关联契约] IC-019.queue.xadd（来自 DD-001）
[实现文件] src/agenthub/data/cache/client.py → RedisClusterClient.xadd
[函数签名注释]
  ```python
  async def xadd(self, stream: str, fields: dict[str, bytes]) -> str:
      """Stream 追加消息.

      Args:
          stream: stream 名称（含 {workspace_id} 哈希标签）
          fields: 消息字段
      Returns:
          消息 ID（ms-seq 形式）
      Raises:
          ClusterDownError: 集群不可用
      """
  ```
[参数说明] stream/fields 必填
[返回值说明] str
[错误码说明] REDIS_CLUSTER_DOWN 503
[来源标注] [DD-001:IC-019 + MD-M-D03:stream]
```

---

## API-D03-005 client.publish

```
[接口编号] API-D03-005
[关联契约] IC-019.pubsub.publish（来自 DD-001）
[实现文件] src/agenthub/data/cache/client.py → RedisClusterClient.publish
[函数签名注释]
  ```python
  async def publish(self, channel: str, message: bytes) -> int:
      """Pub/Sub 发布.

      Args:
          channel: channel 名称
          message: 序列化后的消息
      Returns:
          收到消息的订阅者数
      Raises:
          ClusterDownError: 集群不可用
      """
  ```
[参数说明] channel/message 必填
[返回值说明] int
[错误码说明] REDIS_CLUSTER_DOWN 503
[来源标注] [DD-001:IC-019 + MD-M-D03:pubsub]
```

---

## API-D03-006 proxy.get

```
[接口编号] API-D03-006
[关联契约] IC-019.cache.get（来自 DD-001，泛型版）
[实现文件] src/agenthub/data/cache/proxy.py → CacheProxy.get
[函数签名注释]
  ```python
  async def get(self, key: str) -> T | None:
      """读取缓存值.

      Args:
          key: 业务 key（不含 prefix）
      Returns:
          命中返回 T；未命中或 sentinel 返回 None
      Raises:
          AgentHubError: 反序列化失败
      """
  ```
[参数说明] key 必填
[返回值说明] T | None
[错误码说明] 反序列化失败包装为 AgentHubError
[来源标注] [DD-001:IC-019 + MD-M-D03:CacheProxy 类]
```

---

## API-D03-007 proxy.put

```
[接口编号] API-D03-007
[关联契约] IC-019.cache.set（来自 DD-001，泛型版）
[实现文件] src/agenthub/data/cache/proxy.py → CacheProxy.put
[函数签名注释]
  ```python
  async def put(
      self,
      key: str,
      value: T,
      ttl_sec: int | None = None,
  ) -> None:
      """写入缓存值.

      Args:
          key: 业务 key
          value: 待缓存值
          ttl_sec: 覆盖默认 TTL
      Raises:
          AgentHubError: 序列化失败
          ValueError: 序列化结果 > 1MB
      """
  ```
[参数说明] key/value 必填；ttl_sec 可选
[返回值说明] None
[错误码说明] 序列化失败 / 1MB 限制
[来源标注] [DD-001:IC-019 + MD-M-D03:CacheProxy 类]
```

---

## API-D03-008 stream.publish

```
[接口编号] API-D03-008
[关联契约] IC-019.queue.xadd + IC-020.bus.publish（来自 DD-001，Stream 版）
[实现文件] src/agenthub/data/cache/stream.py → StreamPublisher.publish
[函数签名注释]
  ```python
  async def publish(
      self,
      fields: dict[str, bytes],
      trace_id: str,
  ) -> str:
      """发布 Stream 消息.

      Args:
          fields: 消息字段
          trace_id: 追踪 ID（自动注入）
      Returns:
          消息 ID
      Raises:
          ClusterDownError: 集群不可用
      """
  ```
[参数说明] fields/trace_id 必填
[返回值说明] str
[错误码说明] REDIS_CLUSTER_DOWN 503
[来源标注] [DD-001:IC-019 + IC-020 + AR洞察-1]
```

---

## API-D03-009 stream.consume

```
[接口编号] API-D03-009
[关联契约] IC-021.bus.subscribe（来自 DD-001，Stream 模式）
[实现文件] src/agenthub/data/cache/stream.py → StreamConsumer.consume
[函数签名注释]
  ```python
  async def consume(
      self,
      handler: Callable[[StreamMessage], Awaitable[None]],
      block_ms: int = 5000,
      batch: int = 16,
  ) -> None:
      """阻塞消费循环.

      Args:
          handler: 消息处理函数
          block_ms: 阻塞时间
          batch: 批量大小
      Note:
          持续运行直到 stop；handler 异常 → 消息转 DLQ
      Raises:
          ClusterDownError: 暂停 + 告警
      """
  ```
[参数说明] handler 必填；block_ms/batch 可选
[返回值说明] None（持续运行）
[错误码说明] REDIS_CLUSTER_DOWN 503
[来源标注] [DD-001:IC-021 + MD-M-D03:stream/状态机]
```

---

## API-D03-010 pubsub.publish

```
[接口编号] API-D03-010
[关联契约] IC-019.pubsub.publish + IC-020.bus.publish（来自 DD-001）
[实现文件] src/agenthub/data/cache/pubsub.py → PubSubPublisher.publish
[函数签名注释]
  ```python
  async def publish(self, message: bytes, trace_id: str) -> int:
      """发布 Pub/Sub 消息.

      Args:
          message: 序列化后的消息
          trace_id: 追踪 ID
      Returns:
          订阅者数量
      Raises:
          ClusterDownError: 集群不可用
      """
  ```
[参数说明] message/trace_id 必填
[返回值说明] int
[错误码说明] REDIS_CLUSTER_DOWN 503
[来源标注] [DD-001:IC-019 + IC-020]
```

---

## API-D03-011 pubsub.subscribe

```
[接口编号] API-D03-011
[关联契约] IC-021.bus.subscribe（来自 DD-001，Pub/Sub 模式）
[实现文件] src/agenthub/data/cache/pubsub.py → PubSubSubscriber.subscribe
[函数签名注释]
  ```python
  async def subscribe(
      self,
      handler: Callable[[bytes], Awaitable[None]],
  ) -> None:
      """阻塞订阅循环.

      Args:
          handler: 消息处理函数
      Note:
          持续运行直到 stop；handler 异常不中断（log + 继续）
      Raises:
          ClusterDownError: 重连循环
      """
  ```
[参数说明] handler 必填
[返回值说明] None（持续运行）
[错误码说明] REDIS_CLUSTER_DOWN 503
[来源标注] [DD-001:IC-021 + MD-M-D03:pubsub/状态机]
```

---

[接口总数] 11（API-D03-001 ~ API-D03-011）
[契约覆盖] IC-019（11 个函数均对应）✓
[来源标注] [DD-001:IC-019 + IC-020 + IC-021 + MD-M-D03]
