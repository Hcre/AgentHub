# 系统架构图-数据视图 SA-DA-MCP-V1.0-20260602

> **项目代号**：MCP
> **版本**：V1.0
> **日期**：2026-06-02
> **角色**：TD-001 顶层设计师
> **范围**：数据存储、缓存、消息队列、数据流转

---

## 1. 存储介质映射

| 存储 | 类型 | 存储对象 | 容量估计 | 来源 |
|------|------|---------|---------|------|
| PostgreSQL (主) | RDBMS | DE-001~030 全部结构化数据 | < 100GB (V1.0) | [SA:DD 全部] |
| Redis (主) | KV/缓存 | allowlist_30d hot set / dns_pinning_cache / ws_event offline queue | < 4GB | [SA:DE-018/029] |
| Prometheus | 时序 | metrics_counter 8 个指标 | < 50GB (30d retention) | [SA:DE-007/BR-031] |
| Loki | 日志 | mcp_log / structlog | < 100GB (30d) | [SA:DE-006/BR-030] |
| 文件系统 (/tmp) | 临时 | mcp_config_file mcp-{agent_id}.json | < 10MB | [SA:DE-011/BR-032] |
| 文件系统 (long-term) | 归档 | submission_history manifest_snapshot | < 5GB | [SA:DE-022] |
| 内存 (process) | 运行时 | ring buffer (200 行) / in-process state | — | [SA:BP-003/S-047] |
| 内存 (mcp-proxy) | session | 桥接 session TTL 5min | — | [SA:BR-034/RSK-10] |

## 2. 数据分区与索引

| 表 | 分区键 | 关键索引 | 来源 |
|-----|--------|---------|------|
| mcp_server (DE-001) | — | UNIQUE(name, slug), GIN(manifest) | [SA:DD SA洞察] |
| mcp_installation (DE-003) | workspace_id | (workspace_id, status) | [SA:DD] |
| process_pool (DE-004) | workspace_id | (workspace_id, status) 复合 | [SA:DD] |
| mcp_log (DE-006) | mcp_id + timestamp | (mcp_id, timestamp DESC) | [TD推断:按 mcp 查日志] |
| mcp_binding (DE-009) | agent_id | UNIQUE(agent_id, mcp_id) WHERE status=active (部分) | [SA:DD] |
| inbox_queue (DE-027) | status | (status, created_at) | [SA:BP-020 cron 扫描] |
| allowlist_30d (DE-029) | workspace_id + expires_at | (workspace_id, mcp_id, tool_name, args_hash) UNIQUE, (expires_at) | [SA:DD] |
| dns_pinning_cache (DE-018) | expires_at | (mcp_id), (expires_at) TTL 清理 | [SA:DD] |
| metrics_counter (DE-007) | recorded_at | (mcp_id, recorded_at) | [TD推断:时序] |
| sandbox_session (DE-014) | started_at | (started_at) 短期保留 | [TD推断:沙箱] |

## 3. 数据流概览图

```
                       写入                              读取
[M-B01 市场服务]  ─┐                            ┌─→ [M-A01 Web API] → User
                   ├─→ PostgreSQL ──────────────┤
[M-B02 进程池]    ─┤  (主, 30 表)              ├─→ [M-A02 WS 网关] → Frontend
                   │                            │
[M-B03 绑定引擎]  ─┤                            ├─→ [M-B04 审批引擎]
                   │                            │
[M-B05 MCP 创建]  ─┤                            └─→ [M-D02 时序与日志]
                   │
                   │                  ┌─────→ Redis (allowlist / dns / ws queue)
                   │                  │           │
                   │                  │           └→ [M-B02/M-B03/M-B04] 命中查询
                   │                  │
                   └─→ mcp-config file (/tmp/agenthub/mcp-{agent_id}.json)
                                  │
                                  └→ Runtime Adapter → MCP Server 子进程
                                                          │
                                                          └→ [M-D02] ring buffer → Loki
```

## 4. 跨存储数据一致性

| 场景 | 一致性 | 策略 | 来源 |
|------|--------|------|------|
| mcp_installation 与 process_pool 同步 | 最终一致 (≤ 100ms) | 事务后 publish process_pool.changed | [TD推断:典型最终一致] |
| allowlist 写入 DB + Redis | 最终一致 (≤ 500ms) | 写 DB 成功 → 写 Redis（失败则后台补偿） | [SA:BR-021] |
| dns_pinning_cache 写 DB + yarl in-proc | 写穿 (write-through) | 同事务提交 | [SA:BR-011] |
| mcp_config_file 文件 + DB metadata | 强一致 (顺序写) | 先写文件再写 DB（失败则告警） | [SA:BR-032] |
| mcp_log ring buffer + Loki | 异步批写 (5s flush) | ring buffer → file → log-shipper → Loki | [TD推断:BR-030] |
| 模板迁移 mcp_servers 状态切换 | 强一致 | 单事务 | [SA:BP-024] |

## 5. 数据生命周期

| 数据 | 保留期 | 归档策略 | 来源 |
|------|--------|---------|------|
| mcp_log | 30d (Loki) | 30d 后转冷存储 | [TD推断:BR-030] |
| metrics_counter | 30d (Prom) | 7d 降采样 → 1y 冷存 | [TD推断:BR-031] |
| mcp_submission_history | 永久（已废弃版本也保留） | — | [SA:DE-022] |
| inbox_decision | 永久（合规审计） | — | [SA:DE-028] |
| sandbox_session | 7d | 7d 后删除 | [TD推断:BR-012 沙箱临时] |
| dns_pinning_cache | TTL 60s | cron 清理 | [SA:DE-018] |
| allowlist_30d | granted_at + 30d | 到期 cron 删除 | [SA:DE-029/BR-020] |
| ws_event offline queue | 5min | 重连后批量下发 + 清理 | [SA:BP-010] |

```
[TD洞察-6] 数据孤岛检测 — 所有 DE 均有产生与消费节点：
  - DE-018 dns_pinning_cache: 产生 M-B05(BP-013)，消费 M-B05(BP-013 重定向) — ✓
  - DE-029 allowlist_30d: 产生 M-B04(BP-019)，消费 M-B04(BP-021) — ✓
  - DE-013 ws_subscription: 产生 M-A02(BP-010)，消费 M-A02(BP-010) — ✓
  - DE-007 metrics_counter: 产生各模块，消费 M-D02 — ✓
  - DE-022 mcp_submission_history: 产生 M-B05(BP-016)，消费 M-B05(BP-016) — ✓
  结论: 无数据孤岛 [灵魂 R8 通过]
```

---

**数据视图文档结束。**
