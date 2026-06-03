# 文件框架结构 FF-M-A01-MCP-V1.0-20260603

[模块编号] M-A01
[模块名称] Web API Gateway
[负责 Agent] DD-M-A01
[设计模式] Adapter + Chain of Responsibility + Decorator
[模块边界] 仅 src/agenthub/access/api_gateway/ 内（跨模块文件数 = 0）

## 文件框架（13 个代码文件 + 5 个管理文档）

```
src/agenthub/access/api_gateway/
├── __init__.py                       ← 包入口；导出 GatewayApp / get_app  [来源:FS-001]
├── app.py                            ← GatewayApp(FastAPI) 工厂 + lifespan  [来源:FS-001+MD:M-A01+IC-001]
│   ├─ class GatewayApp               ← [来源:MD:M-A01 类设计 #1]
│   └─ def get_app() → FastAPI        ← 模块级单例工厂
├── controllers/
│   ├── __init__.py                   ← 导出 api_router
│   └── _router.py                    ← APIRouter 适配 M-B01~M-B05  [来源:MD:M-A01 Adapter]
│       └─ def wrap_response          ← IC-001 出参 envelope
├── middleware/                       ← Chain of Responsibility 链 [来源:MD:M-A01]
│   ├── __init__.py
│   ├── auth.py                       ← AuthMiddleware (JWT+JWKS 5min)  [来源:MD:M-A01 #2 + IC-001]
│   │   ├─ class AuthMiddleware
│   │   └─ async def verify_jwt       ← MD 函数签名 #1
│   ├── ratelimit.py                  ← RateLimiter (令牌桶三维度)  [来源:MD:M-A01 #3 + IC-001]
│   │   ├─ class RateLimiter
│   │   └─ async def check_rate       ← MD 函数签名 #2
│   ├── trace.py                      ← TraceMiddleware (trace_id+OTel)  [来源:MD:M-A01 #4]
│   │   ├─ class TraceMiddleware
│   │   └─ def inject_trace           ← MD 函数签名 #3
│   └── metrics.py                    ← MetricsMiddleware (Prom 上报)
│       ├─ class MetricsMiddleware
│       └─ def _normalize_endpoint    ← [DD-M-A01推断:Prom 高基数防御]
├── schemas/
│   └── __init__.py                   ← JWTClaims/UnifiedResponse/ErrorResponse
└── tests/
    ├── __init__.py
    ├── test_auth.py                  ← 8 场景（覆盖率 ≥ 90%）
    ├── test_ratelimit.py             ← 10 场景（覆盖率 ≥ 85%）
    └── test_trace.py                 ← 8 场景（覆盖率 ≥ 85%）
```

## 文件间依赖关系（无循环）

```
app.py ──┬──> controllers/_router.py ──> schemas/
         ├──> middleware/auth.py     ──> schemas/, [跨模块仅消费 M-C07.VaultClient 接口]
         ├──> middleware/ratelimit.py──> [跨模块仅消费 M-D03.RedisClusterClient 接口]
         ├──> middleware/trace.py    ──> core.tracing, core.logging
         └──> middleware/metrics.py  ──> [跨模块仅消费 M-D02.MetricsRegistry 接口]

tests/test_*.py ──> 各被测中间件 + fakeredis + AsyncMock
```

**跨模块策略合规**：所有跨模块依赖仅消费接口（IC-014 / IC-019 / IC-018），不 import 其他模块内部实现；模块边界守护策略 16 已落实（R28 红线）。

## 模块测试用例统计（对齐 MD:M-A01 测试策略）
- 单元: auth(8) + ratelimit(10) + trace(8) = 26
- 核心 12 / 边界 8 / 异常 6（与 MD 26 用例分配吻合）
- Mock: fakeredis / pytest-mock / OTel InMemorySpanExporter
- 行覆盖率目标: auth ≥ 90% / ratelimit ≥ 85% / trace ≥ 85%（与 MD ≥85%/分支≥75% 对齐）

[来源标注] [DD-001:FS-001 + MD:M-A01 + IC-001 + CS-§1]
[作者] DD-M-A01-20260603
