# 文件框架结构 FF-M-D03-MCP-V1.0-20260602

> 模块：M-D03 Cache & Queue
> 设计模式：Cache Proxy + Flyweight
> 文件路径：产出物/07-文件框架/M-D03/

---

```
[模块编号] M-D03
[模块名称] Cache & Queue
[关联设计规范] FS-021 / MD-M-D03 / IC-019（来自 DD-001）
[设计模式] Cache Proxy + Flyweight（来自 DD-001）
[技术栈] TS-012 Redis 7.2 cluster（来自 DD-001）

[文件框架]
  src/agenthub/data/cache/
    __init__.py                  ← [职责：模块初始化，导出公共接口]
      - 导出 RedisClusterClient / CacheProxy / Stream* / PubSub*
    client.py                    ← [职责：Redis Cluster Flyweight 客户端]
      - [类注释: RedisClusterClient (Flyweight)]
        - [函数注释: get_instance / get / setex / delete / xadd / publish / healthcheck / close]
        - [静态方法注释: _validate_key]
    proxy.py                     ← [职责：类型安全缓存代理 CacheProxy[T]]
      - [类注释: CacheProxy (Generic[T])]
        - [函数注释: get / put / invalidate / invalidate_all]
        - [静态方法注释: _build_key]
    stream.py                    ← [职责：Stream 关键事件发布/消费]
      - [类注释: StreamMessage (值对象)]
      - [类注释: StreamPublisher]
      - [类注释: StreamConsumer (Consumer Group + DLQ)]
        - [函数注释: ensure_group / consume / ack]
    pubsub.py                    ← [职责：Pub/Sub 非关键事件]
      - [类注释: PubSubPublisher]
      - [类注释: PubSubSubscriber (自动重连)]
        - [函数注释: subscribe / stop]
    tests/
      __init__.py                ← [职责：测试包入口]
      test_client.py             ← [职责：RedisClusterClient 测试]
        - [测试场景1: 单例 get_instance - 断言同对象]
        - [测试场景2: 正常 GET - 断言返回 bytes]
        - [测试场景3: 边界-未命中 - 断言 None]
        - [测试场景4: 正常 SETEX - 断言 TTL 范围可读]
        - [测试场景5: 异常-非法 TTL - 断言 ValueError]
        - [测试场景6: 异常-集群故障 - 断言 ClusterDownError 透传]
        - [测试场景7: 健康检查 - 断言 True]
        - [测试场景8: 异常-key 缺哈希标签 - 断言 ValueError]
      test_proxy.py              ← [职责：CacheProxy 测试]
        - [测试场景1: 正常 put/get - 断言反序列化一致]
        - [测试场景2: 边界-未命中 - 断言 None]
        - [测试场景3: 异常-超过 1MB - 断言 ValueError]
        - [测试场景4: 正常失效 - 断言 get 返回 None]
        - [测试场景5: 批量失效 - 断言删除数 = 已写入数]
        - [测试场景6: 异常-序列化失败 - 断言 AgentHubError]
      test_stream.py             ← [职责：Stream 测试]
        - [测试场景1: 正常发布 - 断言 ID 非空]
        - [测试场景2: 首次创建 group - 断言无异常]
        - [测试场景3: 重复创建 group - 断言幂等]
        - [测试场景4: 正常消费 - 断言 handler 收到]
        - [测试场景5: 异常-handler 失败 - 断言消息进 DLQ]
      test_pubsub.py             ← [职责：Pub/Sub 测试]
        - [测试场景1: 正常发布 - 断言返回订阅者数]
        - [测试场景2: 正常订阅 - 断言 handler 收到]
        - [测试场景3: 异常-handler 失败不中断 - 断言后续消息仍收到]
        - [测试场景4: 优雅停止 - 断言 subscribe 返回]

[文件间依赖关系]
  __init__.py → client.py / proxy.py / stream.py / pubsub.py
  proxy.py → client.py
  stream.py → client.py
  pubsub.py → client.py
  tests/test_*.py → __init__.py / *.py
  无循环依赖 ✓

[跨模块依赖声明（仅声明，不实现）]
  被依赖方:
    - M-B01 market/decorators.py: 通过 CacheProxy 缓存 MCPServerRepository
    - M-B04 approval/allowlist.py: 通过 CacheProxy 缓存 allowlist
    - M-C04 dns_pinning/cache.py: 通过 CacheProxy 缓存 DNS 结果
    - M-A02 ws_gateway/offline_queue.py: 通过 Stream 写入离线消息
    - M-EV01 eventbus/bus.py: 通过 PubSub/Stream 转发事件
  依赖方向: 单向上层 → 下层 M-D03（不反向依赖）
  实际 import 由 DD-S 阶段在对应模块文件中实现（不在 M-D03 内）

[命名合规]
  包名: cache（小写无下划线）✓
  模块文件: snake_case（client.py / proxy.py / stream.py / pubsub.py）✓
  类名: PascalCase（RedisClusterClient / CacheProxy / StreamPublisher 等）✓
  函数/变量: snake_case（get_instance / _validate_key）✓
  常量: UPPER_SNAKE_CASE（预留）✓
  私有: _leading_underscore（_client / _settings / _lock）✓
  测试: test_{feature}.py（test_client.py / test_proxy.py 等）✓

[来源标注] [DD-001:FS-021 / MD-M-D03 / IC-019 + 设计模式 Cache Proxy + Flyweight]
```
