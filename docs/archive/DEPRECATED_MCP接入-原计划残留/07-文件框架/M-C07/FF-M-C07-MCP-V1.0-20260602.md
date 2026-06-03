# M-C07 Secret Manager 文件框架结构 FF-M-C07-MCP-V1.0-20260602

> [模块编号] M-C07  [模块名称] Secret Manager  [设计模式] Proxy + Cache Proxy
> [关联规范] FS-016 (FS-MCP-V1.0) / MD-M-C07 (MD-MCP-V1.0) / IC-014 (IC-MCP-V1.0) / CS-MCP-V1.0 §1

---

## 1. 文件框架

```
M-C07/
└── src/agenthub/infrastructure/secret/
    ├── __init__.py              ← [职责: 公共接口导出与异常透传]
    ├── vault_client.py          ← [职责: VaultClient (Proxy 模式核心，封装 KV v2 + Transit)]
    │   ├── 类 VaultClient
    │   │   ├── 方法 async get(name) -> bytes           # 关联 IC-014
    │   │   ├── 方法 async put(name, value) -> None
    │   │   ├── 方法 async encrypt(plaintext) -> bytes  # 关联 IC-014
    │   │   ├── 方法 async decrypt(ciphertext) -> bytes # 关联 IC-014
    │   │   ├── 方法 async health() -> bool
    │   │   └── 方法 async aclose() -> None
    ├── token_manager.py         ← [职责: TokenManager (动态 token 获取 + 续期)]
    │   └── 类 TokenManager
    │       ├── 方法 async start() -> None
    │       ├── 方法 async stop() -> None
    │       ├── 方法 async get_dynamic_token() -> str
    │       ├── 方法 async renew() -> None
    │       └── 方法 _auto_renew_loop() -> None
    ├── transit.py               ← [职责: Transit (Vault Transit 加解密封装)]
    │   └── 类 Transit
    │       ├── 方法 async encrypt(plaintext, key_name=None) -> bytes
    │       ├── 方法 async decrypt(ciphertext) -> bytes
    │       └── 方法 async rotate_key(key_name=None) -> None
    ├── cache.py                 ← [职责: SecretCache (in-proc LRU 30s TTL)]
    │   └── 类 SecretCache
    │       ├── 方法 async get(key) -> bytes | None
    │       ├── 方法 async put(key, value, ttl_sec=None) -> None
    │       ├── 方法 async invalidate(key) -> None
    │       ├── 方法 async clear() -> None
    │       └── 方法 stats() -> dict
    └── tests/
        ├── __init__.py
        ├── test_vault_client.py  ← 6 个测试场景（见各文件头注释）
        ├── test_token_manager.py ← 5 个测试场景
        ├── test_transit.py       ← 4 个测试场景
        └── test_cache.py         ← 5 个测试场景
```

## 2. 文件间依赖关系

```
vault_client.py  →  token_manager.py  (依赖: 取用动态 token)
                 →  transit.py        (依赖: 加解密封装)
                 →  cache.py          (依赖: 30s LRU 缓存)
                 →  core.config       (Settings 注入 vault_addr)
                 →  core.logging      (structlog)

token_manager.py →  core.config / httpx (异步 HTTP)
transit.py       →  token_manager.py   (共享 token_provider)
cache.py         →  (无外部依赖, 纯标准库)
__init__.py      →  上述全部
tests/*          →  被测文件 + pytest + pytest-asyncio + httpx.MockTransport
```

无循环依赖；无跨模块文件引用（严格遵守 D7=100）。

## 3. 文件结构合规检查 (soul 4.7 五项)

| 检查项 | 通过 | 依据 |
|--------|------|------|
| 目录层级 ≥2 | ✓ | secret/ + tests/ = 3 层 |
| 文件命名合规 | ✓ | snake_case: vault_client.py / token_manager.py / transit.py / cache.py |
| 文件职责定义 | ✓ | 每个文件仅承担单一职责 |
| 依赖关系明确 | ✓ | 见 §2，无循环 |
| 符合最佳实践 | ✓ | FastAPI/Poetry 推荐布局；tests 与源码并列 |

合规度 = 高（5/5 通过）

## 4. 命名与版本

```
[版本标签] secret-v1.0-20260602
[分支命名] feature/M-C07-secret-manager
[提交信息] [feat] M-C07: 新增 Secret Manager 框架注释
```

[来源标注] [DD-001:FS-016/MD-M-C07/IC-014 + DD-M推断: 缓存容量 1024]
