# 数据结构设计 DS-MCP-V1.0-20260602

> 30 个数据存储结构（19 PG 表组 + 7 Redis 键模式 + 4 其他存储），对应 30 DE / 5 MVIEW
> 来源 [AR:TS-NNN]；表名小写复数；FK 命名 {table}_id；所有变更走 Alembic

---

## 一、PostgreSQL（TS-010 + TS-008 SQLAlchemy 2 + TS-009 asyncpg）

### DS-001 mcp_servers（市场目录）

```
[结构编号] DS-001
[关联技术选型] TS-010 PostgreSQL 15.4
[存储类型] 关系型数据库
[存储名称] mcp_servers
[字段定义]
  id            UUID         PK    NOT NULL  default gen_random_uuid()
  name          VARCHAR(128) UNIQUE NOT NULL
  description   TEXT                NULL
  version       VARCHAR(32)         NOT NULL
  category      VARCHAR(64)         NOT NULL  INDEX
  tags          TEXT[]              NOT NULL  GIN INDEX
  manifest_json JSONB               NOT NULL
  owner_id      UUID                NOT NULL  INDEX FK→users(id)
  status        VARCHAR(16)         NOT NULL  default 'draft' (draft/published/deprecated)
  created_at    TIMESTAMPTZ         NOT NULL  default now()
  updated_at    TIMESTAMPTZ         NOT NULL  default now()
[主键] id
[唯一索引] name
[外键] owner_id → users.id
[GIN 索引] tags
[约束] CHECK (status IN ('draft','published','deprecated'))
[数据量预估] 初始 200 / 增长 50/月 / 峰值 10K
[分片] 无（单表足够）
[来源] [AR:TS-010 + DE-001 mcp_server]
```

### DS-002 mcp_installations

```
[字段]
  id          UUID PK
  mcp_id      UUID NOT NULL FK→mcp_servers(id) INDEX
  workspace_id UUID NOT NULL INDEX
  installer_id UUID NOT NULL
  installed_at TIMESTAMPTZ default now()
  status       VARCHAR(16) NOT NULL  -- active/uninstalled
[唯一索引] (mcp_id, workspace_id) UNIQUE
[来源] [AR:DE-002]
```

### DS-003 workspaces

```
[字段]
  id          UUID PK
  name        VARCHAR(128) UNIQUE NOT NULL
  admins      UUID[] NOT NULL
  created_at  TIMESTAMPTZ default now()
[来源] [AR:DE-003]
```

### DS-004 process_pool（进程池状态）

```
[字段]
  pid           BIGINT PK
  mcp_id        UUID NOT NULL FK→mcp_servers(id)
  workspace_id  UUID NOT NULL INDEX
  state         VARCHAR(16) NOT NULL  -- idle/spawning/running/recycling/recycled/zombie
  spawned_at    TIMESTAMPTZ NOT NULL
  last_health   TIMESTAMPTZ
  fail_count    SMALLINT default 0
  rss_bytes     BIGINT
  fd_count      INTEGER
[唯一索引] (workspace_id, mcp_id) WHERE state IN ('running','idle')
[索引] (workspace_id, state)
[约束] CHECK (state IN ('idle','spawning','running','recycling','recycled','zombie'))
[数据量] 峰值 6,400 行（100 ws × 64）
[来源] [AR:DE-004 + AC:AG-006]
```

### DS-005 health_history

```
[字段]
  id          BIGSERIAL PK
  pid         BIGINT NOT NULL INDEX
  check_at    TIMESTAMPTZ NOT NULL INDEX
  success     BOOLEAN NOT NULL
  latency_ms  INTEGER
  err_msg     TEXT
[分区] 按月分区（按 check_at）
[保留] 90 天
[来源] [AR:DE-005]
```

### DS-006 user_bindings

```
[字段]
  id          UUID PK
  user_id     UUID NOT NULL INDEX
  mcp_id      UUID NOT NULL
  workspace_id UUID NOT NULL
  mapping     JSONB
[唯一索引] (user_id, mcp_id, workspace_id)
[来源] [AR:DE-006]
```

### DS-007 cron_jobs

```
[字段]
  name        VARCHAR(64) PK
  cron_expr   VARCHAR(64) NOT NULL
  enabled     BOOLEAN default true
  last_run    TIMESTAMPTZ
  next_run    TIMESTAMPTZ INDEX
  fail_count  SMALLINT default 0
[来源] [AR:DE-007]
```

### DS-008 cron_run_log

```
[字段]
  id          BIGSERIAL PK
  job_name    VARCHAR(64) NOT NULL INDEX
  triggered_at TIMESTAMPTZ NOT NULL INDEX
  finished_at  TIMESTAMPTZ
  status       VARCHAR(16)  -- success/failed
  err_msg      TEXT
[分区] 按月
[来源] [AR:DE-008]
```

### DS-009 inbox_queue（审批队列）

```
[字段]
  id              UUID PK default gen_random_uuid()
  workspace_id    UUID NOT NULL INDEX
  mcp_id          UUID NOT NULL
  tool            VARCHAR(128) NOT NULL
  args_hash       CHAR(64) NOT NULL  -- SHA256
  status          VARCHAR(16) NOT NULL  -- pending/allowed/denied/timeout
  submitter_id    UUID NOT NULL
  submitted_at    TIMESTAMPTZ default now()
  expires_at      TIMESTAMPTZ NOT NULL  -- 60s 后
[唯一索引] (workspace_id, mcp_id, tool, args_hash) WHERE status='pending'
[索引] (expires_at) WHERE status='pending'
[约束] CHECK (status IN ('pending','allowed','denied','timeout'))
[来源] [AR:DE-027 + ADR-006]
```

### DS-010 inbox_decision（append-only）

```
[字段]
  id              UUID PK
  queue_id        UUID NOT NULL UNIQUE FK→inbox_queue(id)
  decision        VARCHAR(16) NOT NULL  -- allow/deny
  decision_hash   CHAR(64) NOT NULL  -- 哈希链
  prev_hash       CHAR(64)
  custom_args     JSONB  -- Vault Transit 加密
  decider_id      UUID NOT NULL
  decided_at      TIMESTAMPTZ default now()
  nonce           VARCHAR(32) NOT NULL
[唯一索引] (queue_id, decision_hash) UNIQUE
[禁止] UPDATE / DELETE（DB trigger 强制）
[来源] [AR:DE-028 + SEC-005 + AR洞察-3]
```

### DS-011 allowlist_30d

```
[字段]
  id              UUID PK
  workspace_id    UUID NOT NULL
  mcp_id          UUID NOT NULL
  tool            VARCHAR(128) NOT NULL
  args_hash       CHAR(64) NOT NULL
  granted_at      TIMESTAMPTZ NOT NULL
  expires_at      TIMESTAMPTZ NOT NULL  -- granted_at + 30d
[唯一索引] (workspace_id, mcp_id, tool, args_hash) UNIQUE
[索引] (expires_at)
[来源] [AR:DE-029 + ADR-006]
```

### DS-012 mcp_submission

```
[字段]
  id              UUID PK
  mcp_id          UUID NOT NULL
  version         VARCHAR(32) NOT NULL
  manifest_json   JSONB NOT NULL
  status          VARCHAR(16) NOT NULL  -- queued/running/done/failed/rejected
  k4_score        SMALLINT
  k4_tags         TEXT[]
  trace_id        UUID NOT NULL INDEX
  submitted_by    UUID NOT NULL
  submitted_at    TIMESTAMPTZ default now()
[唯一索引] (mcp_id, version) UNIQUE
[索引] (status), (trace_id)
[来源] [AR:DE-017]
```

### DS-013 mcp_submission_history（append-only）

```
[字段]
  id              BIGSERIAL PK
  submission_id   UUID NOT NULL FK→mcp_submission(id)
  step            VARCHAR(32)  -- dry_run/k4/secret/metadata/history
  status          VARCHAR(16)  -- started/done/failed/compensated
  payload         JSONB
  occurred_at     TIMESTAMPTZ default now()
[禁止] UPDATE / DELETE
[来源] [AR:DE-022]
```

### DS-014 ws_subscription

```
[字段]
  id          UUID PK
  client_id   VARCHAR(64) NOT NULL INDEX
  agent_id    UUID NOT NULL
  topics      TEXT[] NOT NULL  -- GIN
  active      BOOLEAN default true
  subscribed_at TIMESTAMPTZ default now()
[来源] [AR:DE-013]
```

### DS-015 k4_rule_set

```
[字段]
  id              UUID PK
  version         VARCHAR(16) UNIQUE NOT NULL
  rules_json      JSONB NOT NULL
  status          VARCHAR(16)  -- active/deprecated
  created_at      TIMESTAMPTZ
[来源] [AR:DE-020]
```

### DS-016 k4_test_corpus

```
[字段]
  id              UUID PK
  rule_set_id     UUID FK→k4_rule_set(id)
  sample_count    INTEGER NOT NULL  -- 200
  fpr             NUMERIC(5,4)  -- false positive rate
  calibrated_at   TIMESTAMPTZ
[来源] [AR:DE-021]
```

### DS-017 acl_rules

```
[字段]
  id              UUID PK
  workspace_id    UUID NOT NULL
  rule_type       VARCHAR(16)  -- allow/deny
  cidr            CIDR NOT NULL
  port            INTEGER
  protocol        VARCHAR(8)
  rule_hash       CHAR(64) UNIQUE
[来源] [AR:DE-024]
```

### DS-018 secret_refs

```
[字段]
  id              UUID PK
  name            VARCHAR(128) UNIQUE NOT NULL  -- vault path 后缀
  workspace_id    UUID NOT NULL
  rotated_at      TIMESTAMPTZ
  next_rotation   TIMESTAMPTZ  -- + 90d
[注] 实际 secret 在 Vault，DB 仅存元数据
[来源] [AR:DE-025 + TDR-010]
```

### DS-019 mcp_migration_history（append-only）

```
[字段]
  id              BIGSERIAL PK
  workspace_id    UUID NOT NULL
  snapshot_hash   CHAR(64) NOT NULL
  status          VARCHAR(16)  -- committed/rolled
  applied_count   INTEGER
  occurred_at     TIMESTAMPTZ default now()
[禁止] UPDATE / DELETE
[来源] [AR:DE-026]
```

---

## 二、Redis 7.2 cluster（TS-012）

### DS-020 allowlist:{ws_id}

```
[结构编号] DS-020
[存储类型] Redis Hash (cluster, 哈希标签 {ws_id})
[键模式] allowlist:{workspace_id}
[值类型] HSET tool:args_hash → "1"
[TTL] 30 天（SETEX）
[一致性] PG 写后 500ms 异步刷 Redis（[AR洞察-3]）
[内存预估] 100 ws × 1000 tools × 64B = ~6MB
[来源] [AR:TS-012 + ADR-006]
```

### DS-021 dns:{hostname}

```
[键模式] dns:{hostname}
[值] {ip, pinned_at}
[TTL] 60s
[一致性] in-proc 先查；miss → aiodns → 写缓存
[来源] [AR:DE-018 + RSK-04]
```

### DS-022 ws:{client_id}（离线队列）

```
[键模式] ws:{client_id}
[类型] Redis Stream
[XADD] event_type/payload/trace_id
[MAXLEN] 1000 events
[TTL] 1 小时
[消费] 客户端重连后 XREAD 自 last_id
[来源] [AR:DE-014 + SEC-008]
```

### DS-023 submit:{trace_id}

```
[键模式] submit:{trace_id}
[类型] Redis Hash
[字段] step / status / progress
[TTL] 1 小时
[来源] [AR:DE-022 + AC:AG-009]
```

### DS-024 cron:leader

```
[键模式] cron:leader
[类型] String (SETNX)
[值] instance_id
[TTL] 60s（心跳续期）
[来源] [AR:AC:AG-004]
```

### DS-025 bus:{topic}（Pub/Sub）+ stream:{topic}（关键）

```
[键模式]
  bus:{topic}          - PUBSUB channel
  stream:{topic}       - XADD（关键 topic, [AR洞察-1]）
[关键 topic 列表] mcp.rollback_done / approval.timeout / mcp.created
[消费组] group=ws_gateway / group=auditor
[来源] [AR:API-400 + AR洞察-1]
```

### DS-026 ratelimit:{key}

```
[键模式] ratelimit:{user_id|ip|workspace_id}
[类型] Sorted Set（滑动窗口）或 String（令牌桶）
[TTL] 1 分钟
[来源] [AR:API-001 + DD推断:实现限流]
```

---

## 三、其他存储

### DS-027 mcp-config 文件

```
[结构编号] DS-027
[存储类型] 文件系统（tmpfs/local）
[路径] /tmp/agenthub/mcp-{agent_id}.json
[权限] 0600
[内容] {mcp_id, workspace_id, mapping, secrets_ref}
[并发] fcntl SHARED LOCK + 原子写入（tmp + rename）
[L4 单一源] M-B03 唯一生成器（ADR-005）
[来源] [AR:DE-011 + SEC-011]
```

### DS-028 Prometheus 指标命名

```
[结构编号] DS-028
[存储] Prometheus 2.48 TSDB
[命名规范] {namespace}_{subsystem}_{name}_{unit}
  示例:
    agenthub_pool_active_processes
    agenthub_approval_decision_latency_seconds
    agenthub_k4_analyze_duration_seconds
    agenthub_ssrf_block_total
[Label] workspace_id / mcp_id / status / endpoint（白名单 8 个，[SEC:SEC-009]）
[保留] 15 天本地 + 长期对象存储
[来源] [AR:TS-013 + DE-015]
```

### DS-029 Loki 日志 schema

```
[结构编号] DS-029
[存储] Loki 2.9
[Label] service / level / workspace_id / trace_id
[格式] JSON Lines（structlog）
  示例: {"ts":"2026-06-02T12:34:56.789Z","level":"INFO","service":"approval","trace_id":"...","msg":"decided","decision":"allow"}
[保留] 90 天热 + 365 天冷
[来源] [AR:TS-015 + DE-016]
```

### DS-030 Vault KV v2 路径

```
[结构编号] DS-030
[存储] HashiCorp Vault 1.15
[KV 路径] secret/data/agenthub/{name}
[Transit 路径] transit/encrypt/agenthub-key（90d 轮换）
[Policy] agenthub-app（read secret/data/agenthub/*; encrypt/decrypt transit/*）
[来源] [AR:TS-017 + TDR-010]
```

---

## 物化视图（5 MVIEW）

| MVIEW | 用途 | 刷新策略 |
|-------|------|---------|
| mv_pool_summary_per_ws | 每 ws 活跃进程数/RSS 总和 | 30s 增量 |
| mv_approval_throughput | 审批吞吐与平均延迟 | 1min |
| mv_mcp_install_count | MCP 安装统计 | 5min |
| mv_webhook_failure_rate | webhook 失败率（[AR洞察-10]） | 1min |
| mv_k4_score_distribution | K4 分数分布 | 1h |

---

## 数据结构覆盖统计

| 维度 | 实测 |
|------|------|
| PG 表（DE 映射） | 19 表 覆盖 30 DE / 35 表（部分合并） |
| Redis 键模式 | 7 |
| 其他存储 | 4（mcp-config / Prom / Loki / Vault） |
| MVIEW | 5 |
| 总 DS | 30 |
| 覆盖 30 DE | 100% |

**[DD 洞察-5]** DS-010 inbox_decision 与 DS-013 mcp_submission_history 均为 append-only，需统一通过 DB trigger 拒绝 UPDATE/DELETE，并提供运维"逻辑删除"接口（标记 redacted=true）以兼容 GDPR right to erasure（[AR洞察-12]）。

**数据结构设计文档结束。**
