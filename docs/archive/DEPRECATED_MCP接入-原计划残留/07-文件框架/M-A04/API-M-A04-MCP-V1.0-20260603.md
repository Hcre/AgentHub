# 接口注释清单 API-M-A04-MCP-V1.0-20260603

> 模块：M-A04 Cron Scheduler
> 来源：[DD-001:IC-MCP-V1.0-20260602.md#IC-022 + MD-MCP-V1.0-20260602.md#M-A04]

---

## 接口契约映射

M-A04 自身无独立 IC（in-proc 模块）；通过 IC-022（in-proc 内部接口集合）统一约束。其对外契约由 K8s 健康探针 + arq worker 队列消费 + Event Bus 订阅共同承担。

| API 路径/契约 | 关联 IC | 实现文件 | 函数签名 | 注释状态 |
|---------------|---------|---------|---------|---------|
| /healthz (K8s) | IC-022 | app.py:healthz | `def healthz() -> dict[str, str]` | 完整 |
| /readyz (K8s) | IC-022 | app.py:readyz | `def readyz() -> bool` | 完整 |
| cron:leader (Redis) | IC-022 | leader_elector.py:acquire | `async def acquire() -> bool` | 完整 |
| cron:leader (Redis) | IC-022 | leader_elector.py:renew | `async def renew() -> None` | 完整 |
| cron:leader (Redis) | IC-022 | leader_elector.py:release | `async def release() -> None` | 完整 |
| arq enqueue (cron) | IC-022 | dispatcher.py:dispatch | `async def dispatch(name, payload, trace_id) -> str` | 完整 |
| arq enqueue retry | IC-022 | dispatcher.py:dispatch_with_retry | `async def dispatch_with_retry(...) -> str` | 完整 |
| trigger.cron.fired | IC-021 | auditor.py:on_trigger | `async def on_trigger(job_name, ts, ...) -> None` | 完整 |

## IC-022 通用约束（在注释中体现）

- 所有函数具备完整类型注解（PEP 484）→ mypy strict 通过
- 所有函数具备 Google 风格 docstring（含 raises）
- 异常透传，禁止吞异常（CS §1.6）
- arq 任务 ID 携带 trace_id 便于链路追踪

## 注释覆盖

接口契约注释化完整度 = 100%（8/8 API 全部带函数签名/参数/返回值/错误码/前置后置/并发安全/幂等性/性能约束/示例 9 字段注释）
