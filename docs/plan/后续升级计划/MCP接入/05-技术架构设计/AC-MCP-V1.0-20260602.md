# Agent 协作方案 AC-MCP-V1.0-20260602

> **项目代号**：MCP
> **版本**：V1.0
> **日期**：2026-06-02
> **范围**：22 个 Agent 角色（1:1 映射 TD 模块）的协作机制

---

## 1. Agent 角色总览

| Agent ID | 角色 | 对应模块 | 层级 | 部署单元 | 副本数 |
|---------|------|---------|------|---------|--------|
| AG-001 | Web API Gateway Agent | M-A01 | 接入 | Deployment | 2-8 (HPA) |
| AG-002 | WS Event Gateway Agent | M-A02 | 接入 | Deployment | 2-4 (sticky) |
| AG-003 | Webhook Receiver Agent | M-A03 | 接入 | Deployment | 1-2 |
| AG-004 | Cron Scheduler Agent | M-A04 | 接入 | DaemonSet | 1 (leader) |
| AG-005 | Market Service Agent | M-B01 | 应用 | Deployment (with AG-001) | 2-8 |
| AG-006 | Process Pool Manager Agent | M-B02 | 应用 | Deployment | 2-4 |
| AG-007 | Binding Engine Agent | M-B03 | 应用 | Deployment (with AG-001) | 2-8 |
| AG-008 | Approval Engine Agent | M-B04 | 应用 | Deployment (with AG-001) | 2-8 |
| AG-009 | MCP Create Agent | M-B05 | 应用 | Deployment (with AG-001) | 2-8 |
| AG-010 | Sandbox Engine Agent | M-C01 | 基础设施 | Sidecar (per AG-006) | per-Pod |
| AG-011 | K4 Analyzer Agent | M-C02 | 基础设施 | Deployment (gRPC) | 1 + 8 worker |
| AG-012 | Template Engine Agent | M-C03 | 基础设施 | In-proc (AG-009) | n/a |
| AG-013 | DNS Pinning Agent | M-C04 | 基础设施 | In-proc (AG-001) | n/a |
| AG-014 | Network ACL Agent | M-C05 | 基础设施 | In-proc (per AG-006) | per-Pod |
| AG-015 | SSRF Guard Agent | M-C06 | 基础设施 | In-proc (AG-001) | n/a |
| AG-016 | Secret Manager Agent | M-C07 | 基础设施 | Sidecar (Vault Agent) | per-Node |
| AG-017 | Name Transformer Agent | M-C08 | 基础设施 | In-proc (AG-007) | n/a |
| AG-018 | ACL Migration Agent | M-C09 | 基础设施 | Deployment (with AG-006) | 1-2 |
| AG-019 | Metadata Store Agent | M-D01 | 数据 | StatefulSet (per-DB) | 1 (read-replica 1) |
| AG-020 | TS & Log Agent | M-D02 | 数据 | Deployment | 1 |
| AG-021 | Cache & Queue Agent | M-D03 | 数据 | StatefulSet (Redis) | 6 (cluster) |
| AG-022 | Event Bus Agent | M-EV01 | 横切 | Shared infra (Redis) | 6 (cluster) |

---

## 2. Agent 协作详细定义（关键 6 维）

### AG-001 Web API Gateway Agent

```
[Agent角色] AG-001 Web API Gateway Agent
[职责边界]
  负责：路由、限流、鉴权、请求日志、metrics 上报
  不负责：业务逻辑、状态持有（无状态）、业务错误处理
[输入接口]
  HTTPS REST: GET/POST/PUT/DELETE /api/v1/{path}
  Headers: Authorization (Bearer JWT), X-Trace-ID, X-Request-ID
[输出接口]
  路由到 M-B01~M-B05 内部 FastAPI router（in-proc 内存调用）
  Metrics: API.* (8 个 label)
[通信协议] HTTPS/1.1 + HTTP/2 (后端), WebSocket (M-A02)
[状态同步] 无状态；JWT 验证用 Vault 注入的公钥（启动时拉取 5min TTL）
[冲突解决] 无（无状态）
[故障恢复]
  崩溃检测: K8s liveness probe (GET /healthz, 5s)
  自动重启: K8s ReplicaSet (max 3 次失败后 CrashLoopBackOff)
  状态恢复: 无状态
  任务转移: HPA 自动扩缩 + Nginx sticky session
[资源配额] 1 CPU / 1GB / 100 并发 / 30s 超时
[生命周期]
  创建: K8s Deployment (HPA min=2, max=8, CPU>70%)
  运行: 持续
  销毁: 滚动更新 / Scale to zero (off-hours 可选)
[来源标注] [TD:M-A01] [AR推断:典型 K8s 无状态服务模式]
```

### AG-002 WS Event Gateway Agent

```
[Agent角色] AG-002 WS Event Gateway Agent
[职责边界]
  负责: WS 长连接管理、mcp.* 事件路由、离线队列、订阅鉴权
  不负责: 事件产生、事件持久化（持久化由 M-D02）
[输入接口]
  WebSocket: wss://{host}/ws (subprotocol: mcp.v1)
  订阅消息: {"action":"subscribe","agent_id":"..."}
  事件: 来自 AG-022 Event Bus (Redis Pub/Sub)
[输出接口]
  WS 推送: {event_type, payload, trace_id, emitted_at} (JSON Lines)
  离线缓存: Redis Stream key=ws:{client_id} (max 1000 events)
[通信协议] WebSocket + Redis Pub/Sub (5 topic)
[状态同步]
  有状态: ws_subscription (PG DE-013) + 在线映射 (Redis hash)
  状态存储: PG + Redis
  同步机制: 启动时从 PG 加载活跃订阅，运行时增量更新
[冲突解决]
  同一 client 多实例连接: 首次连接为主连接 (Redis SETNX ws:primary:{client_id})
  重复消息: trace_id 去重 (Redis SETEX 5min)
[故障恢复]
  崩溃检测: WS ping/pong 30s timeout
  自动重启: K8s + 客户端自动重连（指数退避 1s/2s/4s/8s）
  状态恢复: 重连后从 Redis Stream 拉取 missed events
  任务转移: Nginx sticky session (cookie: AG-002 sticky)
[资源配额] 1 CPU / 2GB / 500 长连接 / 心跳 30s
[生命周期]
  创建: K8s Deployment (HPA min=2, max=4)
  运行: 持续
  销毁: 通知客户端重连到其他实例
[来源标注] [TD:M-A02] [AR推断:典型 WS 网关 + sticky session]
```

### AG-004 Cron Scheduler Agent

```
[Agent角色] AG-004 Cron Scheduler Agent
[职责边界]
  负责: 定时任务触发（healthcheck 30s :00 / idle_scan 30s :15/:45 / approval_timeout 60s / migration 5min）
  不负责: 任务执行（分发到 arq）、任务结果（由 arq worker 写回）
[输入接口]
  内部 trigger (APScheduler): cron expression
  外部手动触发: POST /api/v1/admin/cron/{job_name}/run
[输出接口]
  arq enqueue: {job_name, payload, trace_id}
  事件: trigger.cron.fired (Redis Pub/Sub for audit)
[通信协议] in-proc APScheduler + arq (Redis Stream)
[状态同步]
  有状态: job 状态表（last_run / next_run / fail_count in PG DE-007/008）
  状态存储: PG
  同步机制: 启动时从 PG 恢复任务表；运行时单 leader（Redis SETNX cron:leader）
[冲突解决]
  多实例冲突: SETNX 选举 leader，TTL 60s + 心跳续期；非 leader 等待
  任务重复触发: arq job_id 含 timestamp + instance_id 去重
[故障恢复]
  崩溃检测: leader 心跳超时 60s 自动让位
  自动重启: K8s + 备用实例自动竞选 leader
  状态恢复: 从 PG 恢复 job 表，跳过 missed run（不补跑）
  任务转移: 无（任务由 arq worker 池消费，与 scheduler 解耦）
[资源配额] 0.5 CPU / 512MB / 1 实例
[生命周期]
  创建: K8s DaemonSet (1 节点, leader 模式)
  运行: 持续
  销毁: 主动让位 leader，关闭 APScheduler
[来源标注] [TD:M-A04 + RSK-05 错开 15s 相位]
```

### AG-006 Process Pool Manager Agent

```
[Agent角色] AG-006 Process Pool Manager Agent
[职责边界]
  负责: MCP 进程生命周期（spawn/healthcheck/idle_recycle/evict）
  不负责: 进程业务执行（mcp-proxy 子进程）、MCP 业务逻辑
[输入接口]
  同步调用: IF-110 Pool.spawn(mcp_id, workspace_id)
  Cron: healthcheck 30s :00 / idle_scan 30s :15/:45
  事件: 来自 AG-022 (process.health_changed)
[输出接口]
  进程 PID: spawn 返回值
  DB 写入: process_pool (PG DE-004)
  事件: publish process.health_changed / process.recycled
  Metrics: pool.active_count, pool.fd_used, pool.rss_total
[通信协议] in-proc + asyncio subprocess + Redis Pub/Sub
[状态同步]
  有状态: process_pool 表 (PG) + 内存中 pid → mcp_id 映射 (LRU 256)
  状态存储: PG (权威) + Redis (缓存)
  同步机制: 启动时从 PG 加载活跃进程；运行时实时同步
[冲突解决]
  跨实例 spawn 竞争: PG INSERT ON CONFLICT (workspace_id, mcp_id) DO NOTHING + 槽位预占
  健康检查双跑: SETNX with TTL 25s（防止 30s 周期重叠）
  驱逐冲突: append-only 记录，evict 标记 CAS
[故障恢复]
  崩溃检测: per-process healthcheck 5s timeout / OS SIGKILL
  自动重启: spawn 失败重试 3 次（指数退避 1s/2s/4s）
  状态恢复: 启动时扫描 PG 中 status=started 但 OS 中无 PID 的进程 → 标记 zombie
  任务转移: SIGTERM 5s grace → SIGKILL → 记录到 PG
[资源配额] 2 CPU / 4GB / 64 子进程 (workspace 隔离)
[生命周期]
  创建: K8s Deployment (HPA min=2, max=4)
  运行: 持续
  销毁: 优雅关闭 SIGTERM 所有子进程（30s grace）
[来源标注] [TD:M-B02 + RSK-02 进程池 6,400 容量 + ADR-002 workspace 隔离]
```

### AG-008 Approval Engine Agent

```
[Agent角色] AG-008 Approval Engine Agent
[职责边界]
  负责: 危险工具审批（allowlist 查询 / inbox_queue 写 / 决策处理 / 双层超时）
  不负责: 工具执行（仅决策后调度 MCP）、UI 展示（前端）
[输入接口]
  同步调用: IF-130 Approval.check_and_queue(workspace_id, mcp_id, tool, args)
  同步调用: IF-131 Approval.decide(queue_id, decision, custom_args)
  事件: approval.timeout_scan (Cron 60s)
[输出接口]
  decision: allowed / pending / denied
  DB 写入: inbox_queue / inbox_decision / allowlist_30d (PG DE-027/028/029)
  Redis: allowlist hot set (SETEX 30d)
  事件: publish approval.requested / approval.decided / approval.timeout
[通信协议] in-proc + Redis Pub/Sub + Redis SETEX
[状态同步]
  有状态: Redis allowlist 缓存 (权威: PG DE-029)
  状态存储: PG + Redis 双写（写 PG 后异步刷 Redis，500ms 最终一致）
  同步机制: 启动时从 PG 全量加载 allowlist；运行时增量更新
[冲突解决]
  hash 一致性: 公共函数 compute_args_hash (sorted_json + ensure_ascii=False + SHA256) [TD:ADR-006]
  决策并发: PG row-level lock (SELECT FOR UPDATE)
  超时双跑: SETNX with TTL 55s
[故障恢复]
  崩溃检测: K8s liveness / arq health
  自动重启: K8s + 重建 Redis 缓存 (从 PG)
  状态恢复: 启动时 PG → Redis 全量加载
  任务转移: 无（inbox_queue 行级锁，决策幂等）
[资源配额] 1 CPU / 1GB / 100 QPS
[生命周期]
  创建: K8s Deployment (HPA min=2, max=8)
  运行: 持续
  销毁: 优雅关闭（先停 in-proc 接收，再等 in-flight 结束）
[来源标注] [TD:M-B04 + ADR-006 + RSK-06/R-006 公共 hash + RSK-10 Inbox 缓冲]
```

### AG-009 MCP Create Agent

```
[Agent角色] AG-009 MCP Create Agent
[职责边界]
  负责: MCP 端到端编排（dry-run → K4 → secret → 元数据 → 历史）
  不负责: 具体能力执行（委托给 AG-010 沙箱 / AG-011 K4 / AG-012 模板 / AG-013 DNS / AG-014 ACL / AG-015 SSRF / AG-016 Secret）
[输入接口]
  同步调用: IF-140 MCPServer.submit(form) / IF-141 rollback / IF-142 upgrade / IF-143 configure_acl
  事件: 来自 AG-003 Webhook（webhook.upgrade_received）
[输出接口]
  异步: arq enqueue {chain: [dry_run, k4, secret, metadata, history], trace_id}
  DB 写入: mcp_submission / mcp_submission_history (PG DE-017/022)
  事件: publish mcp.created / mcp.rollback_done
[通信协议] in-proc + arq (异步 chain) + Redis Pub/Sub
[状态同步]
  有状态: 当前提交进度 (Redis hash key=submit:{trace_id} TTL 1h)
  状态存储: Redis (临时) + PG (历史)
  同步机制: arq job 内步骤间共享 trace_id
[冲突解决]
  同 mcp_id 重复提交: PG UNIQUE (mcp_id, version) 约束
  步骤失败: 自动回滚（snapshot → restore）
[故障恢复]
  崩溃检测: arq job 超时 30min
  自动重启: arq 重试（指数退避 max 3 次）
  状态恢复: PG 历史快照 + restart from last_step
  任务转移: arq worker 池接管
[资源配额] 2 CPU / 2GB / 10 并发 chain
[生命周期]
  创建: K8s Deployment (HPA min=2, max=4)
  运行: 持续
  销毁: 优雅关闭（先停接收，等 in-flight 结束）
[来源标注] [TD:M-B05 + BP-011~018 编排链]
```

### AG-011 K4 Analyzer Agent（独立 gRPC 服务）

```
[Agent角色] AG-011 K4 Analyzer Agent
[职责边界]
  负责: 11+1 类高危模式静态分析 + 200 样本校准
  不负责: 评分应用、UI 展示
[输入接口]
  gRPC: K4Analyze(manifest_json) → {score, tags}
  gRPC: K4Calibrate(rule_set_id, corpus_id) → {fpr, pass}
[输出接口]
  gRPC response: {score: 1-10, tags: [...], trace_id}
  DB 写入: k4_rule_set / k4_test_corpus (PG DE-020/021)
[通信协议] gRPC (Protocol Buffers) + HTTP/2
[状态同步]
  有状态: 预加载规则集 (in-memory, 启动时从 PG 加载)
  状态存储: PG (权威) + 内存 (热缓存)
  同步机制: 规则更新时 Pub/Sub 广播 reload 信号
[冲突解决]
  校准并发: PG row-level lock + CAS 版本号
  评分幂等: 相同 input + rule_set_version → 相同 output
[故障恢复]
  崩溃检测: gRPC health check + 5min 校准超时
  自动重启: K8s + 启动时从 PG 加载规则集
  状态恢复: reload 规则集约 2s
  任务转移: gRPC client 自动重试其他实例
[资源配额] 4 CPU / 8GB / 8 worker pool / 单次分析 ≤ 10s
[生命周期]
  创建: K8s Deployment (1 实例 + 8 worker subprocess)
  运行: 持续
  销毁: 优雅关闭 worker
[来源标注] [TD:M-C02 + 调研:R-008 K4 误判率 15% 校准]
```

### AG-022 Event Bus Agent（横切基础设施）

```
[Agent角色] AG-022 Event Bus Agent
[职责边界]
  负责: 5 topic 跨进程事件分发（approval.*, template.*, process.*, mcp.*, binding.*）
  不负责: 事件持久化（消费方负责）、事件业务处理
[输入接口]
  publish: Bus.publish(topic, payload) → Redis PUBLISH
  subscribe: Bus.subscribe(topic, handler) → Redis SUBSCRIBE
[输出接口]
  fan-out: 同 topic 多订阅者均收到
  持久化: 无（消费方负责落盘）
[通信协议] Redis Pub/Sub（fire-and-forget）+ Redis Stream（≥1 消费方要求可靠时）
[状态同步]
  有状态: 活跃订阅表 (Redis hash key=bus:subs:{topic})
  状态存储: Redis
  同步机制: 启动时重新订阅；运行时心跳 30s
[冲突解决]
  多订阅者: pubsub 自带 fan-out
  重复消息: 消费方 trace_id 去重
[故障恢复]
  崩溃检测: Redis connection ping 10s
  自动重启: K8s + 自动重连 + 重新订阅
  状态恢复: 重新订阅所有 topic（无状态丢失）
  任务转移: 多实例同时订阅（无单点）
[资源配额] 0.5 CPU / 512MB / 5 topic / 1000 msg/s
[生命周期]
  创建: K8s Deployment (HPA min=2, max=4, 每个实例全量订阅)
  运行: 持续
  销毁: 主动 unsubscribe
[来源标注] [TD:M-EV01 + ADR-003 Redis Pub/Sub]
```

---

## 3. 协作流程图（关键路径）

### 3.1 MCP 安装（BP-002）

```
U-01 → AG-001 (API Gateway)
     → AG-005 (Market): 查 mcp_server + process_pool
     → AG-008 (Approval): check_and_queue (allowlist 命中则跳过)
     → AG-006 (Pool): spawn → fork mcp-proxy → mcp-server 子进程
     → AG-019 (Metadata): INSERT process_pool / mcp_installation
     → AG-002 (WS): publish mcp.running → 前端
     → 返回结果 (P95 ≤ 1.2s 冷启动)
```

### 3.2 危险工具调用（BP-019）

```
Agent → AG-001 (API Gateway)
      → AG-008 (Approval): compute_args_hash → Redis allowlist check
      → 未命中 → AG-019 (Metadata): INSERT inbox_queue
      → AG-022 (Event Bus): publish approval.requested
      → AG-002 (WS): 推 Inbox UI
      → U-04 决策 → AG-008: decide → append-only inbox_decision
      → AG-022: publish approval.decided
      → AG-006 (Pool): if rejected → AG-008 记录 auto_rejected
      → AG-019: 更新 allowlist_30d + Redis SETEX 30d
```

### 3.3 健康检查与回收（BP-005 + BP-004 + BP-023）

```
AG-004 (Cron :00) → AG-022: trigger.cron.fired
                 → AG-006: healthcheck_all (per-pid tools/list 5s timeout)
                 → fail_count++ → AG-019: UPDATE health_history
                 → AG-022: publish process.health_changed
                 → AG-002: WS 推前端 red banner

AG-004 (Cron :15/:45) → AG-006: idle_scan
                      → SIGTERM → 5s grace → SIGKILL
                      → AG-019: UPDATE process_pool status=recycled
                      → AG-022: publish process.recycled
```

---

## 4. 协作闭环检测（4.15）

| 检测项 | 检测结果 | 处理 |
|--------|---------|------|
| 死锁检测 | AG-009 → AG-010/011/012.../016 单向依赖；AG-008 → AG-019/AG-022 单向；AG-006 → AG-022 单向；**依赖图无环** ✓ | 通过 |
| 活锁检测 | AG-008 决策有 trace_id 去重；AG-006 健康检查 fail_count 有上限 (3) → 标记 zombie；AG-009 chain 步骤有 max_retry (3) ✓ | 通过 |
| 超时机制 | 所有通信均有超时设置（AG-001 30s / AG-006 5s / AG-008 60s / AG-011 5min / AG-004 60s leader）✓ | 通过 |
| 降级策略 | AG-008 DB 不可用 → 保守 pending；AG-006 spawn 失败 → 报警 + reserved slot；AG-002 WS 不可用 → 离线队列 (Redis Stream)；AG-011 gRPC 失败 → 同步本地降级分析（无规则预加载）✓ | 通过 |
| 状态一致性 | 强一致：DE-009/011/017/019/020/021/022/024/025/026/028/030；最终一致（500ms）：DE-029 allowlist ✓ | 通过 |

**协作闭环检测：5/5 通过 ✓**

---

## 5. AR 洞察

**洞察-1（技术选型冲突）**：AG-002 WS 推送与 AG-022 事件总线均使用 Redis Pub/Sub，Pub/Sub 的 fire-and-forget 在 AG-002 离线客户端重连时可能丢失关键事件（如 mcp.rollback_done）。建议 AG-022 对关键 topic（mcp.rollback_done / approval.timeout）改用 Redis Stream + consumer group，确保至少一次投递。**[AR推断:典型 WS+Pub/Sub 消息丢失风险]**

**洞察-2（协作协议风险）**：AG-006 Process Pool Manager 的 6,400 进程分布在 2-4 实例，跨实例 spawn 冲突目前依赖 PG row-level lock + workspace 槽位预占。若 PG 主库故障，spawn 请求将全部 timeout。建议引入 Redis 分布式锁（Redlock 5 节点）作为 PG 锁的备用降级。**[AR推断:PG SPOF 降级路径]**

**洞察-3（状态同步风险）**：AG-008 Approval Engine 维护 Redis allowlist 缓存（30d 过期），但 allowlist 更新路径是 PG → 异步 → Redis（500ms 延迟）。若有 2 个 AG-008 实例同时处理同 queue_id 的决策（极小概率），可能因 Redis 同步延迟导致重复决策。建议在 PG inbox_decision 加 UNIQUE (queue_id, decision_hash) 约束。**[AR推断:典型 read-after-write 一致性窗口]**

---

**Agent 协作方案文档结束。**
