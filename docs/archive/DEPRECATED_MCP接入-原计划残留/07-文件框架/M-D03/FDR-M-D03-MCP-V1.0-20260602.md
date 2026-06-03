# 框架决策记录 FDR-M-D03-MCP-V1.0-20260602

> M-D03 重大框架决策记录
> 来源标注 100%，影响范围限定 M-D03

---

## FDR-D03-001 Flyweight 单例实现策略

```
[决策编号] FDR-D03-001
[决策标题] RedisClusterClient 用类方法 + 类变量实现 Flyweight 单例
[决策状态] 已接受
[决策内容] 使用 cls._instance + @classmethod get_instance(settings) 实现线程/协程安全的 Flyweight 单例
[决策理由] 
  1. redis-py async cluster 客户端连接池开销大（~50MB/实例）
  2. 全进程共享一个连接池可显著降低资源消耗
  3. 类方法实现简单，DD-S 编码风险低
[拒绝的替代方案] 
  方案A: 使用第三方单例库（如 singleton-decorator） → 拒绝理由：增加依赖；与项目最小依赖原则冲突
  方案B: 模块级变量直接持有实例 → 拒绝理由：测试时无法重置；不支持 settings 注入
[影响范围] M-D03/client.py / __init__.py
[相关FDR] 无
[来源标注] [DD-001:MD-M-D03:设计模式 Flyweight + CS §1.5 导入规范]
```

---

## FDR-D03-002 CacheProxy 泛型化 vs 具体化

```
[决策编号] FDR-D03-002
[决策标题] CacheProxy 采用 Generic[T] 泛型实现
[决策状态] 已接受
[决策内容] 使用 typing.Generic[T] + TypeVar T 实现类型安全缓存代理
[决策理由]
  1. 同一代理类支持多种业务类型（MCPServerDTO / AllowlistEntry / DnsResult 等）
  2. 泛型版本不损失类型提示（mypy strict 通过）
  3. 调用方可通过 type parameter 显式声明缓存值类型
[拒绝的替代方案]
  方案A: 每种类型一个具体类 → 拒绝理由：违反 DRY；模块膨胀
  方案B: 退化为 Any 类型 → 拒绝理由：违反 CS §1.3（myypy 严格禁用 Any）
[影响范围] M-D03/proxy.py + M-B01/M-B04/M-C04 调用方
[相关FDR] 无
[来源标注] [DD-001:MD-M-D03:CacheProxy 类 + CS §1.3 + AR洞察-3 类型安全]
```

---

## FDR-D03-003 Stream vs Pub/Sub 分流策略

```
[决策编号] FDR-D03-003
[决策标题] 关键事件用 Stream（含 Consumer Group + DLQ），非关键事件用 Pub/Sub
[决策状态] 已接受
[决策内容] stream.py 负责持久化关键事件（24h）；pubsub.py 负责实时非关键事件
[决策理由]
  1. Stream 自带 XACK 至少一次投递 + DLQ 容错
  2. Pub/Sub 极低延迟（<50ms）适合实时但不可靠
  3. 二者结合既保证关键事件不丢，又保证实时事件快速
[拒绝的替代方案]
  方案A: 全部用 Stream → 拒绝理由：实时事件延迟高；资源占用大
  方案B: 全部用 Pub/Sub → 拒绝理由：关键事件可能丢失（违反 M-B04 审批不丢要求）
[影响范围] M-D03/stream.py + pubsub.py + M-EV01 调用方
[相关FDR] 无
[来源标注] [DD-001:MD-M-D03:stream/pubsub + AR洞察-1 关键 topic 用 Stream + DDR-002]
```

---

## FDR-D03-004 Key 强制含 {hash_tag} 校验

```
[决策编号] FDR-D03-004
[决策标题] 在 client 层强制 key 含 {workspace_id} 哈希标签
[决策状态] 已接受
[决策内容] RedisClusterClient._validate_key 静态方法在写入前校验，缺标签抛 ValueError
[决策理由]
  1. Redis cluster 同 slot 才能多键操作；缺标签会导致 cluster 性能退化
  2. 提前校验避免线上运行时错误
  3. 强制规范提升代码可读性
[拒绝的替代方案]
  方案A: 不校验依赖调用方自觉 → 拒绝理由：违反 fail-fast 原则
  方案B: 用文档说明 → 拒绝理由：无强制力；DD-S 编码时易遗漏
[影响范围] M-D03/client.py + 所有调用方
[相关FDR] 无
[来源标注] [DD-001:IC-019:入参约束 + AR洞察-6 集群 hash tag]
```

---

## FDR-D03-005 测试 Mock 策略：fakeredis + 真 cluster 集成

```
[决策编号] FDR-D03-005
[决策标题] 单元测试用 fakeredis；Stream DLQ/Pub-Sub 集成测试用 testcontainers 真 Redis
[决策状态] 已接受
[决策内容] test_client.py / test_proxy.py 用 fakeredis；test_stream.py / test_pubsub.py 用 testcontainers Redis
[决策理由]
  1. fakeredis 支持 90% KV/Pub/Sub 场景；速度快
  2. Stream Consumer Group + DLQ 是边缘场景，fakeredis 行为不全
  3. 真集群集成测试在 CI 中用 testcontainers 启动 3 master 节点
[拒绝的替代方案]
  方案A: 全部用真 Redis → 拒绝理由：CI 时间翻倍；开发反馈慢
  方案B: 全部用 fakeredis → 拒绝理由：DLQ/Stream 行为未覆盖
[影响范围] M-D03/tests/ + CI 配置
[相关FDR] 无
[来源标注] [DD-001:MD-M-D03:测试策略 25 用例 + CS §1.7 测试规范]
```

---

[决策总数] 5（FDR-D03-001 ~ FDR-D03-005）
[已接受] 5 / 5
[已拒绝] 0
[来源标注覆盖率] 100%
