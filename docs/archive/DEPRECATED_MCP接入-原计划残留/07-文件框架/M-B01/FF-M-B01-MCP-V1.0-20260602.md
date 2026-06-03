# M-B01 Market Service 文件框架结构

> 文件框架结构 FF-M-B01-MCP-V1.0-20260602
> 负责模块：M-B01 Market Service
> 来源：[DD-001:FS-005/MD-MCP#M-B01]

---

## 文件框架

```
src/agenthub/application/market/
├── __init__.py                 ← 模块入口；导出公共符号（MarketController/Service/Repository/Cached/Schemas）
├── controllers.py              ← FastAPI router + MarketController 类；处理 HTTP 边界
├── services.py                 ← MarketService 业务编排（list_servers/get_detail/search）
├── repositories.py             ← MCPServerRepository 基础仓储（继承 M-D01 BaseRepository 范型）
├── decorators.py               ← CachedMCPServerRepository 缓存代理（TTL 30min）
├── schemas.py                  ← Pydantic DTO（ListFilter/Page/MCPServerDTO/MCPServerDetail）
└── tests/
    ├── __init__.py
    └── test_market.py          ← 20 用例（单元 + 集成 + 控制器 HTTP）
```

## 文件职责与依赖关系

| 文件路径 | 职责 | 依赖（被本文件 import） | 被依赖（import 本文件） |
|---------|------|----------------------|----------------------|
| `__init__.py` | 模块符号聚合 | 同包 5 个模块 | M-A01（include_router 时） |
| `controllers.py` | HTTP 路由 + 异常包装 | services / schemas / core.exceptions | __init__ / M-A01 |
| `services.py` | 业务编排、缓存路径选择 | repositories / decorators / schemas / core.logging | controllers |
| `repositories.py` | SQLAlchemy 异步查询 | schemas / data.metadata.models（M-D01，跨模块） | services / decorators |
| `decorators.py` | 缓存代理（read-through + tombstone） | repositories / schemas / data.cache.client（M-D03，跨模块） | services |
| `schemas.py` | Pydantic 强类型 DTO | 仅 pydantic 标准库 | controllers / services / repositories / decorators |
| `tests/test_market.py` | 20 用例覆盖 | 同包 5 个模块 + pytest-asyncio + fakeredis | 无 |

## 依赖方向

```
controllers.py → services.py → repositories.py → (M-D01 ORM)
                       ↓
                       decorators.py → repositories.py
                                    ↓
                                    (M-D03 Redis)
```

严格三层；无反向依赖；无循环导入。

## 跨模块依赖声明（D7 守护）

| 目标模块 | 文件 | 原因 | 风险 |
|---------|------|------|------|
| M-D01 (data.metadata) | repositories.py | 复用 BaseRepository 范型 + mcp_servers ORM 模型 | 循环导入风险——已通过 TYPE_CHECKING 延迟导入缓解 |
| M-D03 (data.cache) | decorators.py | RedisClusterClient 读穿透 | 跨模块；事件失效由 M-EV01 订阅 mcp.created 触发 |
| M-A01 (access.api_gateway) | __init__.py | router include | 单向（不反向） |

## 命名合规

- 包名：`agenthub` / `application` / `market`（小写无下划线 ✓）
- 模块文件：`controllers.py` / `services.py` / `repositories.py` / `decorators.py` / `schemas.py`（snake_case ✓）
- 类名：`MarketController` / `MarketService` / `MCPServerRepository` / `CachedMCPServerRepository` / `ListFilter` / `MCPServerDTO` / `MCPServerDetail` / `Page`（PascalCase ✓）
- 函数/变量：`list_servers` / `get_detail` / `server_id` / `filter_payload`（snake_case ✓）
- 常量：`CACHE_TTL_SEC` / `CACHE_KEY_PREFIX` / `BLANK_TTL_SEC`（UPPER_SNAKE_CASE ✓）
- 测试文件：`test_market.py`；方法 `test_{function}_when_{scenario}_then_{expected}` ✓

## 来源标注

[DD-001:FS-005/MD-MCP#M-B01]
