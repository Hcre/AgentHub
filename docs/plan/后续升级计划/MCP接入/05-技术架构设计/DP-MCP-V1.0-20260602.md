# 部署架构图 DP-MCP-V1.0-20260602

> **范围**：22 模块的部署映射 + 启动顺序 + 健康检查 + 监控告警
> **拓扑**：K8s 1.28+ 集群（2 host 起步 → 100 workspace 多 host）

---

## 1. 环境定义

| 环境 | 用途 | 资源 | 部署方式 |
|------|------|------|---------|
| local | 开发者本地 | Docker Compose，单机 | docker compose up |
| dev | 集成测试 | K8s minikube，2 节点 | helm install --values dev.yaml |
| staging | 预生产 | K8s 1.28，3 节点 | ArgoCD GitOps |
| prod | 生产 | K8s 1.28，N 节点（HPA） | ArgoCD GitOps + canary |

---

## 2. 部署组件映射

| 部署组件 | 对应模块 | 运行环境 | 资源配置 | 配置管理 | 依赖 | 启动顺序 | 健康检查 | 监控告警 | 来源 |
|---------|---------|---------|---------|---------|------|---------|---------|---------|------|
| DP-001 postgres-primary | M-D01 | StatefulSet | 4 CPU / 16GB / 100GB SSD | ConfigMap + Vault | — | 1 | pg_isready | prom postgres_up | [TD:M-D01] |
| DP-002 postgres-replica | M-D01 | StatefulSet | 4 CPU / 16GB / 100GB SSD | 同步主库 | DP-001 | 2 | pg_isready | replica_lag < 5s | [TD:M-D01] |
| DP-003 pgbouncer | M-D01 | Deployment | 1 CPU / 512MB | ConfigMap | DP-001/002 | 3 | TCP 6432 | 连接数 < 200 | [TD:M-D01] |
| DP-004 redis-master | M-D03/M-EV01 | StatefulSet (cluster) | 2 CPU / 4GB / 10GB | ConfigMap | — | 1 | redis-cli ping | redis_up, keyspace_hits | [TD:M-D03/EV01] |
| DP-005 redis-replica | M-D03 | StatefulSet (cluster) | 2 CPU / 4GB / 10GB | 同步主 | DP-004 | 2 | redis-cli ping | replica_lag < 1s | [TD:M-D03] |
| DP-006 vault | M-C07 | StatefulSet (HA 3 实例) | 1 CPU / 1GB / 10GB | ConfigMap (auto-unseal) | — | 1 | vault status | vault_sealed=false | [TD:M-C07] |
| DP-007 vault-agent | M-C07 | DaemonSet | 0.2 CPU / 256MB | ConfigMap (annotations) | DP-006 | 4 | HTTP 8200 | token_renewal_ok | [TD:M-C07] |
| DP-008 agenthub-core | M-A01/M-B01~M-B05 | Deployment (HPA 2-8) | 1 CPU / 1GB / replica | ConfigMap + Vault (动态) | DP-001~006 | 5 | GET /healthz 5s | API QPS, error_rate, p95_latency | [TD:M-A01] |
| DP-009 ws-gateway | M-A02 | Deployment (HPA 2-4) | 1 CPU / 2GB / replica | ConfigMap + Vault | DP-004 | 5 | WS ping/pong 30s | ws_connections, msg_rate | [TD:M-A02] |
| DP-010 webhook-listener | M-A03 | Deployment | 0.5 CPU / 512MB | ConfigMap + Vault (webhook secrets) | DP-001/004/006 | 5 | POST /healthz | webhook_recv_rate, sig_fail_count | [TD:M-A03] |
| DP-011 cron-scheduler | M-A04 | DaemonSet (1 leader) | 0.5 CPU / 512MB | ConfigMap | DP-001/004 | 5 | GET /healthz | cron_jobs_run, leader_is_active | [TD:M-A04] |
| DP-012 k4-analyzer | M-C02 | Deployment (1 + 8 worker subprocess) | 4 CPU / 8GB | ConfigMap + Vault (corpus) | DP-001/003 | 5 | gRPC health | k4_analyze_latency, pool_busy | [TD:M-C02] |
| DP-013 nginx | 接入层 | Deployment (2-4) | 1 CPU / 512MB | ConfigMap (sticky) | DP-008~011 | 6 | GET /healthz | upstream_health, req_rate | [AR推断:典型反代] |
| DP-014 prometheus | M-D02 | StatefulSet (2 实例) | 2 CPU / 4GB / 50GB | ConfigMap (scrape config) | DP-008~012 | 7 | GET /-/healthy | prom_targets_up, tsdb_compression | [TD:M-D02] |
| DP-015 grafana | M-D02 | Deployment | 0.5 CPU / 512MB | ConfigMap + Vault (datasource) | DP-014/DP-016 | 7 | GET /api/health | grafana_up | [TD:M-D02] |
| DP-016 loki | M-D02 | StatefulSet (3 节点) | 2 CPU / 4GB / 50GB | ConfigMap | DP-001/DP-017 | 7 | GET /ready | loki_up, ingester_streams | [TD:M-D02] |
| DP-017 promtail | M-D02 | DaemonSet | 0.2 CPU / 128MB | ConfigMap (file paths) | DP-016 | 6 | GET /ready | log_send_rate | [TD:M-D02] |
| DP-018 jaeger-collector | M-D02 | Deployment | 1 CPU / 1GB | ConfigMap (OTLP) | DP-014 | 7 | GET / | jaeger_up | [AR推断] |
| DP-019 jaeger-query | M-D02 | Deployment | 0.5 CPU / 512MB | ConfigMap | DP-018 | 8 | GET / | jaeger_query_latency | [AR推断] |
| DP-020 alertmanager | M-D02 | Deployment (2 实例) | 0.5 CPU / 512MB | ConfigMap (routes) | DP-014 | 7 | GET /-/healthy | alertmanager_active | [AR推断] |
| DP-021 mcp-proxy | 桥接层 (per-MCP) | 独立进程（per Core） | 0.1 CPU / 50MB | 命令行参数 | mcp-server 子进程 | 子进程级 | 进程存在性 | mcp_proxy_alive | [调研:S-027] |
| DP-022 mcp-server (子进程) | per-install | 独立子进程 | 0.1-1 CPU / 50-256MB | mcp-config 文件 | DP-021 mcp-proxy | 子进程级 | tools/list RPC | tool_call_p95, health | [TD:M-B02] |

---

## 3. 启动顺序

```
阶段 0（基础设施）
  1. DP-001 postgres-primary, DP-002 replica, DP-003 pgbouncer
  2. DP-004~005 redis cluster, DP-006 vault (3 实例 HA)
  3. DP-007 vault-agent（注入 secret 到所有 Pod）

阶段 1（数据层就绪）
  4. DP-014~020 可观测性（Prom/Grafana/Loki/Jaeger/Alertmanager）
  5. DP-017 promtail（开始采集日志）

阶段 2（应用层就绪）
  6. DP-008 agenthub-core, DP-009 ws-gateway, DP-010 webhook-listener
  7. DP-011 cron-scheduler（leader 选举）
  8. DP-012 k4-analyzer
  9. DP-013 nginx（等所有 upstream 健康）

阶段 3（运行时）
  10. DP-021~022 mcp-proxy + mcp-server 子进程（按需 spawn）
  11. 前端静态资源（CDN）
  12. 验证：GET /healthz (200) + WS ping (200) + cron jobs (≥1 run)
```

**启动总时间预估**：约 90s（基础设施 30s + 应用 30s + 验证 30s）

---

## 4. 关键部署模式

### 4.1 Workspace 隔离

- **多 workspace 部署**：每个 workspace = 1 K8s namespace
- **资源隔离**：ResourceQuota per namespace（CPU 64 cores / Memory 256GB / Pod 100）
- **网络隔离**：NetworkPolicy 默认 deny，显式 allow agenthub-core → 各自 DB schema
- **DB 隔离**：PG schema-per-workspace（共享 DB 实例，逻辑隔离）；V2.0+ 可选物理 DB-per-workspace
- **进程隔离**：mcp-server 子进程 per-workspace，独立 cgroup

### 4.2 HPA 配置

| 组件 | min | max | 触发指标 | 冷却 |
|------|-----|-----|---------|------|
| DP-008 agenthub-core | 2 | 8 | CPU > 70% / RPS > 500 | 60s 扩 / 300s 缩 |
| DP-009 ws-gateway | 2 | 4 | 连接数 > 300/实例 | 60s 扩 / 300s 缩 |
| DP-012 k4-analyzer | 1 | 4 | queue depth > 50 | 120s 扩 / 600s 缩 |

### 4.3 持久化存储

- PG：StatefulSet volumeClaimTemplates（100GB SSD per Pod）
- Redis：StatefulSet（10GB SSD per Pod，appendonly yes）
- Loki：StatefulSet（50GB SSD per Pod，boltdb-shipper）
- Vault：StatefulSet（10GB SSD，HA 模式 auto-unseal via AWS KMS / GCP CKMS）

---

## 5. 健康检查 + 监控告警

### 5.1 健康检查端点

| 组件 | 端点 | 间隔 | 失败阈值 |
|------|------|------|---------|
| agenthub-core | GET /healthz (200) | 10s | 3 |
| ws-gateway | WS ping/pong (30s 内响应) | 30s | 2 |
| cron-scheduler | GET /healthz + 验证 leader | 30s | 2 |
| k4-analyzer | gRPC health (1.21) | 30s | 3 |
| postgres | pg_isready | 10s | 3 |
| redis | PING | 5s | 3 |
| vault | vault status | 10s | 3 |
| nginx | GET /healthz | 5s | 3 |

### 5.2 告警规则（关键 5 条）

```yaml
- alert: AgentHubCoreDown
  expr: up{job="agenthub-core"} == 0
  for: 2m
  labels: {severity: critical}
  annotations: {summary: "AgentHub Core 不可用"}

- alert: PostgresReplicaLag
  expr: pg_replication_lag_seconds > 5
  for: 5m
  labels: {severity: warning}

- alert: RedisClusterSlotsUnassigned
  expr: redis_cluster_slots_assigned < 16384
  for: 1m
  labels: {severity: critical}

- alert: WSConnectionsHigh
  expr: ws_active_connections > 400
  for: 5m
  labels: {severity: warning}

- alert: CronSchedulerNoLeader
  expr: cron_leader_is_active == 0
  for: 2m
  labels: {severity: critical}
```

---

## 6. AR 洞察

**洞察-7（部署复杂度）**：DP-008 agenthub-core 启动依赖 7 个组件（PG/Redis/Vault/Promtail/Jaeger/Nginx/health-check），启动顺序 5 在所有数据层就绪之后。建议在 Helm chart 中使用 `initContainers` + `readinessProbe` 串行化等待，避免启动竞态。**[AR推断:K8s 启动顺序最佳实践]**

**洞察-8（资源隔离风险）**：Workspace 隔离走 K8s namespace + ResourceQuota，但 mcp-server 子进程（DP-022）以宿主机进程运行，不受 K8s cgroup 限制。建议 V1.0 实施 Linux cgroup v2 per-workspace（systemd-run --user --scope）作为 K8s cgroup 的二级隔离。**[调研:RSK-02 + R-003]**

**洞察-9（依赖单点）**：DP-006 Vault 启动时依赖 auto-unseal（AWS KMS），若 KMS 不可用，Vault 启动失败 → 所有服务无法获取 secret。建议 V1.0 实施"transit 模式 + 静态密钥 fallback"双模式（KMS 不可用时用本地加密密钥）。**[AR推断:Vault 启动依赖降级]**

---

**部署架构图文档结束。**
