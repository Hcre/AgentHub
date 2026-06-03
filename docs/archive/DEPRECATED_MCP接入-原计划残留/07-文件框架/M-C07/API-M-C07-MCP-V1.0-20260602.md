# M-C07 Secret Manager 接口注释清单 API-M-C07-MCP-V1.0-20260602

> [模块编号] M-C07  [接口契约] IC-014 (IC-MCP-V1.0)
> [关联规范] MD-M-C07 / IC-014 / CS-MCP-V1.0 §1

---

## API-M-C07-001  VaultClient.get

```
[接口编号] API-M-C07-001
[关联契约] IC-014（Secret.get）
[实现文件] src/agenthub/infrastructure/secret/vault_client.py
[函数签名注释]
  async def get(self, name: str) -> bytes
[参数说明]
  参数1: name str 必填 secret 路径 "secret/data/agenthub/{name}"
[返回值说明]
  类型: bytes
  描述: secret 明文
  特殊值: 缓存命中时不再回源
[错误码说明]
  错误码1: VAULT_SEALED 503 含义: Vault 未 unseal 触发条件: 启动期或续期失败
  错误码2: VAULT_PERMISSION_DENIED 403 含义: 策略不足 触发条件: token policy 不覆盖 path
  错误码3: VAULT_RATE_LIMIT 429 含义: 限流命中 触发条件: 调用方需按指数退避
[并发安全] 协程安全；缓存层使用 asyncio.Lock
[幂等性] 是（GET 语义）
[性能约束] P95 ≤ 100ms（命中缓存 ≤ 5ms）
[来源标注] [DD-001:IC-014/MD-M-C07]
```

## API-M-C07-002  VaultClient.put

```
[接口编号] API-M-C07-002
[关联契约] IC-014（写入端约定；IC 仅描述读取，写入由本模块定义）
[实现文件] src/agenthub/infrastructure/secret/vault_client.py
[函数签名注释]
  async def put(self, name: str, value: bytes) -> None
[参数说明]
  参数1: name str 必填 secret 路径
  参数2: value bytes 必填 secret 内容（最大 1MB）
[返回值说明]
  类型: None
  描述: 写入成功；缓存失效
[错误码说明]
  错误码1: VAULT_PERMISSION_DENIED 403
  错误码2: VAULT_RATE_LIMIT 429
  错误码3: VAULT_INVALID_PAYLOAD 400（value 超限或非 bytes）
[并发安全] 协程安全
[幂等性] 否（每次 put 产生新 version）
[性能约束] P95 ≤ 200ms
[来源标注] [DD-001:MD-M-C07 + DD-M推断: 写后失效语义]
```

## API-M-C07-003  VaultClient.encrypt

```
[接口编号] API-M-C07-003
[关联契约] IC-014（高层 API，跨模块统一入口）
[实现文件] src/agenthub/infrastructure/secret/vault_client.py
[函数签名注释]
  async def encrypt(self, plaintext: bytes) -> bytes
[参数说明]
  参数1: plaintext bytes 必填 明文（最大 1MB）
[返回值说明]
  类型: bytes
  描述: vault:v1:... 格式密文
[错误码说明]
  错误码1: VAULT_PERMISSION_DENIED 403
  错误码2: VAULT_INVALID_PLAINTEXT 400
  错误码3: VAULT_RATE_LIMIT 429
[并发安全] 协程安全
[幂等性] 否
[性能约束] P95 ≤ 50ms
[来源标注] [DD-001:MD-M-C07/IC-014]
```

## API-M-C07-004  VaultClient.decrypt

```
[接口编号] API-M-C07-004
[关联契约] IC-014
[实现文件] src/agenthub/infrastructure/secret/vault_client.py
[函数签名注释]
  async def decrypt(self, ciphertext: bytes) -> bytes
[参数说明]
  参数1: ciphertext bytes 必填 vault 格式密文
[返回值说明]
  类型: bytes
  描述: 解密后的明文（不进入缓存，遵循 TDR-010）
[错误码说明]
  错误码1: VAULT_PERMISSION_DENIED 403
  错误码2: VAULT_INVALID_CIPHERTEXT 400
  错误码3: VAULT_RATE_LIMIT 429
[并发安全] 协程安全
[幂等性] 是
[性能约束] P95 ≤ 50ms
[来源标注] [DD-001:MD-M-C07/IC-014]
```

## API-M-C07-005  TokenManager.get_dynamic_token

```
[接口编号] API-M-C07-005
[关联契约] IC-014（内部 token 取用，对外不直接可见）
[实现文件] src/agenthub/infrastructure/secret/token_manager.py
[函数签名注释]
  async def get_dynamic_token(self) -> str
[参数说明] 无
[返回值说明]
  类型: str
  描述: 动态 token 字符串
  特殊值: 即将过期时阻塞等待续期
[错误码说明]
  错误码1: VaultSealed 续期失败
  错误码2: TokenManagerStopped stop() 已调用
[并发安全] 协程安全（_lock 串行化续期）
[幂等性] 是（TTL 内返回相同 token）
[性能约束] < 10ms（命中缓存）
[来源标注] [DD-001:MD-M-C07/IC-014]
```

## API-M-C07-006  SecretCache.get/put/invalidate

```
[接口编号] API-M-C07-006
[关联契约] IC-014（缓存层，私有于 M-C07）
[实现文件] src/agenthub/infrastructure/secret/cache.py
[函数签名注释]
  async def get(self, key: str) -> bytes | None
  async def put(self, key: str, value: bytes, ttl_sec: int | None = None) -> None
  async def invalidate(self, key: str) -> None
[参数说明]
  参数1: key str 必填
  参数2: value bytes 必填
  参数3: ttl_sec int | None 可选 默认 30s
[返回值说明]
  类型: bytes | None
[错误码说明]
  错误码1: ValueError key 非法（防路径穿越）
[并发安全] 协程安全（_lock 串行）
[幂等性] 是
[性能约束] < 1ms
[来源标注] [DD-001:MD-M-C07 + DD-M推断: TTL=30s 来源 TDR-010]
```

## API-M-C07-007  Transit.encrypt/decrypt

```
[接口编号] API-M-C07-007
[关联契约] IC-014
[实现文件] src/agenthub/infrastructure/secret/transit.py
[函数签名注释]
  async def encrypt(self, plaintext: bytes, key_name: str | None = None) -> bytes
  async def decrypt(self, ciphertext: bytes) -> bytes
[参数说明]
  参数1: plaintext bytes 必填
  参数2: ciphertext bytes 必填
  参数3: key_name str | None 可选 默认 "agenthub"
[返回值说明]
  类型: bytes
[错误码说明]
  错误码1: VAULT_PERMISSION_DENIED
  错误码2: VAULT_INVALID_CIPHERTEXT
  错误码3: VAULT_RATE_LIMIT
[并发安全] 协程安全
[幂等性] decrypt 是 / encrypt 否
[性能约束] P95 ≤ 50ms
[来源标注] [DD-001:MD-M-C07/IC-014]
```

**接口覆盖统计**: IC-014 全部 3 个错误码（VAULT_SEALED / VAULT_PERMISSION_DENIED / VAULT_RATE_LIMIT）已映射至 7 个 API 注释；D4 = 100%。
