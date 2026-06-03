# 系统架构图-部署视图 SA-D-MCP-V1.0-20260602

> **项目代号**：MCP
> **版本**：V1.0
> **日期**：2026-06-02
> **角色**：TD-001 顶层设计师
> **范围**：开发/测试/生产三环境部署拓扑

---

## 1. 部署单元清单

| 单元 | 镜像/包 | 实例数(单 workspace) | 资源请求 | 资源限制 | 来源 |
|------|---------|---------------------|---------|---------|------|
| apigateway | nginx:1.27-alpine | 1 | 0.5 CPU / 256MB | 2 CPU / 1GB | [TD推断:标准网关] |
| agenthub-core | agenthub:v1.0 | 2-4 | 2 CPU / 4GB | 8 CPU / 16GB | [SA:BR-005/S-037 推荐 16GB] |
| ws-gateway | agenthub-ws:v1.0 | 2-4 | 1 CPU / 1GB | 4 CPU / 4GB | [TD推断:WS 连接] |
| webhook-listener | agenthub-webhook:v1.0 | 1 | 0.5 CPU / 512MB | 1 CPU / 1GB | [SA:BP-017] |
| cron-scheduler | agenthub-cron:v1.0 | 1 | 0.25 CPU / 256MB | 1 CPU / 512MB | [SA:BP-004/005/020/023/024] |
| inbox-notifier | agenthub-notifier:v1.0 | 1-2 | 0.5 CPU / 512MB | 2 CPU / 1GB | [SA:BP-020] |
| k4-analyzer | agenthub-k4:v1.0 | 1 (pool size 8 in-proc) | 1 CPU / 2GB | 4 CPU / 8GB | [SA:BP-015] |
| postgresql | postgres:16-alpine | 1 主 + 1 备 | 2 CPU / 8GB | 8 CPU / 32GB | [TD推断:30 表/290 字段] |
| redis | redis:7-alpine | 1 主 + 1 从 | 0.5 CPU / 1GB | 2 CPU / 4GB | [TD推断:allowlist+pinning 缓存] |
| prometheus | prom/prometheus | 1 | 0.5 CPU / 1GB | 2 CPU / 4GB | [SA:BR-031] |
| loki | grafana/loki | 1 | 0.5 CPU / 1GB | 2 CPU / 4GB | [SA:BR-030] |
| mcp 子进程 (sandbox) | 临时 | < 5 并发 | — | 256MB/1 CPU | [SA:BR-012] |
| mcp 子进程 (业务) | per install | 0~64/workspace | — | 256MB/1 CPU | [SA:BR-005] |
| mcp-proxy | sparfenyuk/mcp-proxy:0.5 | per-MCP | — | 128MB | [SA:BR-034] |

## 2. 生产部署拓扑（单 workspace 视角）

```
                         ┌─────────────────────────────┐
                         │   Load Balancer / TLS       │
                         │   (Cloud LB / Nginx)        │
                         └─────────────┬───────────────┘
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            │                          │                          │
   ┌────────▼────────┐      ┌─────────▼────────┐       ┌────────▼────────┐
   │  APIGateway     │      │  APIGateway      │       │  APIGateway     │
   │  (nginx)        │      │  (nginx)         │       │  (nginx)        │
   └────────┬────────┘      └─────────┬────────┘       └────────┬────────┘
            │                          │                          │
   ┌────────▼────────┐      ┌─────────▼────────┐       ┌────────▼────────┐
   │  agenthub-core  │      │  agenthub-core   │  ...  │  agenthub-core  │
   │  worker 1       │      │  worker 2        │       │  worker N       │
   │  (FastAPI)      │      │  (FastAPI)       │       │  (FastAPI)      │
   └─┬────┬──────┬───┘      └─┬────┬──────┬────┘       └─┬────┬──────┬───┘
     │    │      │             │    │      │               │    │      │
     │    │      └──── ws-gateway pool ─────────────────────┘    │      │
     │    │                                                        │      │
     │    └──── cron-scheduler (1) ───── inbox-notifier (1) ─────┘      │
     │                                                                  │
     │    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
     │    │ postgres-main│    │ redis-main   │    │ k4-analyzer  │      │
     │    │ (主)         │    │ (主)         │    │              │      │
     │    └──────┬───────┘    └──────┬───────┘    └──────────────┘      │
     │           │                   │                                  │
     │    ┌──────▼───────┐    ┌──────▼───────┐                           │
     │    │ postgres-    │    │ redis-       │                           │
     │    │ replica (备) │    │ replica (从) │                           │
     │    └──────────────┘    └──────────────┘                           │
     │                                                                  │
     │  ┌──────────────────────────────────────────────────────────┐    │
     │  │  sidecar: prometheus-exporter + log-shipper (per pod)    │    │
     │  └──────────────────────────────────────────────────────────┘    │
     │                                                                  │
     │  ┌──────────────────────────────────────────────────────────┐    │
     │  │  sandbox executor (per pod, cgroup v2)                   │    │
     │  │  + mcp-proxy per installed MCP                           │    │
     │  │  + MCP child processes (0~64)                            │    │
     │  └──────────────────────────────────────────────────────────┘    │
     └──────────────────────────────────────────────────────────────────┘
```

## 3. 环境差异

| 资源 | 开发 | 测试 | 生产 |
|------|------|------|------|
| 进程池容量 | 8 | 16 | 64 |
| 实例数 | 1 (all-in-one) | 2 (主从) | 4+ |
| K4 误判率阈值 | 0.30 (宽松) | 0.15 (标准) | 0.15 (标准) |
| Secret Manager | 本地 .env | Vault dev | Vault HA |
| 监控告警 | 关闭 | 部分开启 | 全量开启 |

## 4. 跨 workspace 部署约束

```
[TD洞察-5] 部署约束 — 单 workspace 进程池 64 (16GB 推荐) 意味着：
  ① 每个 workspace 独立 agenthub-core Pod/VM（共享 DB 即可），不混部
  ② 若需动态扩 workspace 数 → 需 Kubernetes HPA + workspace Pool CRD
  ③ 共享 DB 带来跨 workspace 资源争抢风险 — 建议每 50 个 workspace 独立 DB 分片
  来源标注: [TD推断:基于 S-037/BR-005 容量约束推导]
```

---

**部署视图文档结束。**
