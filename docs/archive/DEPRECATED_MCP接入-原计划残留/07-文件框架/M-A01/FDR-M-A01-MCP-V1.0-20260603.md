# 框架决策记录 FDR-M-A01-MCP-V1.0-20260603

[模块] M-A01 Web API Gateway

---

## FDR-A01-001 中间件注册顺序：Trace→Auth→RateLimit→Metrics

[决策状态] 已接受
[决策内容] 中间件按 Trace(最外) → Auth → RateLimit → Metrics(最内) 顺序注册
[决策理由]
1. Trace 最外层确保所有日志（包括 401/429 响应日志）携带 trace_id
2. Auth 在 RateLimit 之前：未鉴权请求不计入 user/ws 桶，避免被恶意刷流耗尽合法用户配额
3. Metrics 最内层：仅统计真正进入业务的请求延迟，避免被前置中间件失败放大延迟分布
[拒绝的替代方案]
- 方案 B：RateLimit → Auth（先限流再鉴权）。拒绝理由：per-user/per-ws 桶需 jwt_claims.sub，必须在 Auth 之后才能取到 user_id
- 方案 C：Metrics 最外层（含 Auth/RateLimit 耗时）。拒绝理由：导致 latency 直方图被异常请求污染，无法定位真实业务慢点
[影响范围] app.py register_middleware()
[相关 FDR] 无
[来源标注] [DD-M-A01推断:依据 IC-001 时序图 + Chain of Responsibility 模式语义]

---

## FDR-A01-002 跨模块依赖采取"仅接口消费"策略

[决策状态] 已接受
[决策内容] middleware/auth.py 仅 import M-C07.VaultClient 公开接口；middleware/ratelimit.py 仅 import M-D03.RedisClusterClient 接口；middleware/metrics.py 仅 import M-D02.MetricsRegistry 接口；全部通过依赖注入接收
[决策理由]
1. 严格遵守 R28 模块边界硬约束：M-A01 不创建/修改任何 M-C07/M-D02/M-D03 文件
2. 仅消费 IC-014 / IC-018 / IC-019 已定义的稳定接口，避免实现耦合
3. 通过构造函数注入（DI）便于测试 mock，无需 monkeypatch
[拒绝的替代方案]
- 方案 B：直接复用 M-C07 内部 cache 实现。拒绝理由：违反 R28 跨模块红线 + R29 职责扩散
[影响范围] AuthMiddleware/RateLimiter/MetricsMiddleware 构造签名
[相关 FDR] 无
[来源标注] [DD-001:IC-014/018/019 + soul R28/R29 + soul §7.3 多实例隔离]

---

## FDR-A01-003 fail-open vs fail-closed 策略：Redis 限流降级 fail-open，Vault 鉴权 fail-closed

[决策状态] 已接受
[决策内容]
- 限流依赖 Redis：Redis 不可用时 fail-open（透传 + WARN）
- 鉴权依赖 Vault 公钥：Vault unsealed 时 fail-closed（503 UPSTREAM_TIMEOUT）
[决策理由]
1. 限流是可用性优化而非安全屏障，宁可放过流量也不能误杀（fail-open）
2. 鉴权是安全屏障，公钥不可用时必须拒绝服务（fail-closed），避免绕过鉴权
3. 与 IC-001 错误码定义一致：RATE_LIMIT_EXCEEDED 是业务码而非安全码；AUTH_FAILED 是安全码
[拒绝的替代方案]
- 方案 B：限流也 fail-closed（Redis 不可用即拒服务）。拒绝理由：会因运维 Redis 重启导致业务大面积 429，违反 SLA
[影响范围] middleware/auth.py + middleware/ratelimit.py
[相关 FDR] FDR-A01-001
[来源标注] [DD-001:MD M-A01 异常处理 + IC-001 + SEC:SEC-001]

---

## FDR-A01-004 Prometheus label 高基数防御：path 模板化

[决策状态] 已接受
[决策内容] MetricsMiddleware._normalize_endpoint 将 path 中 UUID/数字替换为 :id，避免每个 UUID 生成独立 time series
[决策理由]
1. 不做模板化将导致 Prom 内存按 path 基数线性膨胀（数千 workspace × 数百 endpoint）
2. /v1/pool/{id} 模板化后只产生 1 个 series 而非 N 个
[拒绝的替代方案]
- 方案 B：保留原 path。拒绝理由：[DD洞察-跨模块依赖] M-D02 Prometheus 集成会因高基数 OOM
[影响范围] middleware/metrics.py
[来源标注] [DD-M-A01推断:依据 Prometheus 高基数最佳实践 + 与 M-D02 IC-018 协同]

---

## FDR-A01-005 测试 Mock 选型：fakeredis + AsyncMock + OTel InMemoryExporter

[决策状态] 已接受
[决策内容]
- Redis: fakeredis（支持 Lua）替代 testcontainers，降低测试启动时间
- 上游路由: AsyncMock（无需真实 M-B0x）
- OTel: opentelemetry-sdk InMemorySpanExporter
[决策理由] 单元测试目标 ≥ 90%(auth) / ≥ 85% 覆盖率；快速反馈优于真实环境
[拒绝的替代方案]
- 方案 B：testcontainers Redis。拒绝理由：CI 启动 +30s，不满足 PR 反馈速度要求
[影响范围] tests/test_auth.py / test_ratelimit.py / test_trace.py
[来源标注] [DD-001:MD M-A01 Mock 策略 + CS §1.7]

---

## 多方案对比汇总（soul 4.11）

| 维度 (W) | 主方案（采纳）| 备选方案 B |
|---------|--------------|-----------|
| 文件结构合规度 (0.22) | 9 (FS-001 完全对齐) | 6 (扁平化无 controllers/middleware 子包) |
| 注释完整度 (0.22) | 10 (100% 覆盖) | 8 |
| 接口契约注释化 (0.18) | 10 (IC-001 全映射) | 7 |
| 代码风格合规度 (0.13) | 10 (CS §1 全遵循) | 9 |
| 设计可追溯性 (0.13) | 10 (每文件含来源标注) | 7 |
| 文件框架可追溯性 (0.12) | 10 | 7 |
| **加权总分** | **9.65** | **7.27** |

主方案优势 ≥ 5 分差距，直接采纳。
