# 性能优化方案 PO-MCP-V1.0-20260602

> **范围**：8 项 PC 性能指标全覆盖，每项含瓶颈分析 + 优化策略 + 实施步骤 + 验证方法 + 回滚策略

---

## 1. 性能指标总览

| 性能指标 | 目标 | 瓶颈模块 | 优化策略 | 验证方法 | 回滚策略 |
|---------|------|---------|---------|---------|---------|
| PO-01 进程池容量 | 64/ws, 6,400 全平台 | M-B02 | workspace 隔离 + HPA + ulimit 提升 | 64 并发 healthcheck 压测 | 缩减 workspace 数 |
| PO-02 stdio 工具调用延迟 | P95 ≤ 800ms | M-A02 | ring buffer + L4 config 缓存 + asyncio pipe | 1000 QPS tool_call 压测 | 关闭 ring buffer |
| PO-03 HTTP 工具调用延迟 | P95 ≤ 1500ms | M-C04/M-A02 | DNS Pinning + Redis 缓存 (命中率>90%) | 跨区 HTTP 压测 | 关闭 DNS 缓存 |
| PO-04 冷启动延迟 | P95 ≤ 1.2s | M-B02 | manifest_cache + 30s 预热 + 预占槽位 | 冷启动 vs 热调用对比 | 关闭预热 |
| PO-05 SSRF 检测 | < 50ms/请求 | M-C06 | frozenset O(1) + yarl 单对象 Pin | 1000 QPS SSRF check 压测 | 关闭 yarl Pin（降级） |
| PO-06 K4 静态分析 | < 10s/MCP | M-C02 | 规则集预加载 + 8 worker pool | 200 样本 FPR 校准时延 | 同步单进程分析 |
| PO-07 沙箱 dry-run | < 30s/MCP | M-C01 | cgroup v2 + DB 限制 5 并发 | 5 并发沙箱 P95 | 串行执行 |
| PO-08 DB 并发 | 100-200 连接 | M-D01 | PGBouncer + 读副本 + MVIEW | 200 连接 tps 压测 | 关闭 PGBouncer |

---

## 2. 详细优化策略

### PO-01 进程池容量 64/workspace

```
[性能指标] PO-01
[当前容量] 32 进程/workspace (V0 经验值)
[目标容量] 64 进程/workspace (BR-005)
[扩容倍数] 2x
[瓶颈分析]
  - OS 文件描述符: 默认 1024 → 64 进程 × 8 fd = 512 (临界)
  - 内存: 64 进程 × 256MB = 16GB/workspace
  - 进程创建: fork + mcp-proxy 启动 ~800ms (冷启动)
  - DB 连接: 64 进程 × 2 连接 = 128 (DB 200 上限 64%)
[优化策略]
  1. ulimit -n 提升至 65535 (容器级别)
  2. 内存预分配: cgroup memory.max = 16GB
  3. 进程池预占: 启动时预创建 16 个槽位 (warm pool)
  4. 增量扩容: 超出预占后按需 spawn
  5. workspace CRD: K8s Custom Resource 控制
[实施步骤]
  步骤1: 修改 Dockerfile CMD ["sh", "-c", "ulimit -n 65535 && gunicorn ..."]
  步骤2: 配置 K8s pod.spec.securityContext.sysctls: fs.file-max=65535
  步骤3: 实现 warm pool (16 slots pre-spawn)
  步骤4: 部署 workspace CRD + controller
  步骤5: 灰度 5%→25%→100%
[验证方法]
  - 压测: 1000 并发 spawn 请求, 测量 P95 spawn latency
  - 监控: host.fd_used, process_pool.active_count, host.memory_used
  - 指标: spawn P95 < 1.2s, fd < 50000, memory < 14GB
[回滚策略]
  - 缩减 workspace 数（K8s namespace 删除）
  - 调整 ulimit 至 32768
  - 关闭 warm pool（冷启动）
[来源标注] [TD:PC-进程池 + RSK-02 + ADR-002 workspace 隔离]
```

### PO-02 stdio 工具调用延迟 P95 ≤ 800ms

```
[性能指标] PO-02
[当前容量] P95 ~1.5s (V0 实测)
[目标容量] P95 ≤ 800ms
[瓶颈分析]
  - JSON 序列化: tool_call payload 约 2KB, 序列化 5ms
  - stdio pipe: 64 进程并发 pipe I/O, 上下文切换频繁
  - mcp-proxy 转发: 增加一跳 50-100ms
  - L4 config 重复读取: 每次 spawn 重新生成
[优化策略]
  1. ring buffer (memoryview): 进程间共享内存, 减少 pipe 序列化
  2. L4 config 内存缓存: spawn 时生成一次, 进程生命周期内复用
  3. asyncio.subprocess.PIPE + 8KB buffer size
  4. mcp-proxy 连接池: per-MCP 复用长连接
  5. P95 拆解: stdio 200ms (子进程) + 序列化 50ms + 网络 100ms
[实施步骤]
  步骤1: 引入 multiprocessing.shared_memory 替代 pipe
  步骤2: L4 config 缓存到 process_pool.config_cache (Redis hash)
  步骤3: 调优 asyncio subprocess buffer_size=8192
  步骤4: mcp-proxy 长连接 (per-MCP persistent)
  步骤5: 压测 1000 QPS, 验证 P95 < 800ms
[验证方法]
  - 压测: locust 1000 RPS 持续 5min
  - 监控: tool_call_p95, mcp_proxy_latency, ring_buffer_usage
  - 目标: P95 < 800ms, P99 < 1.2s, 错误率 < 0.1%
[回滚策略]
  - 关闭 ring buffer (回退到 pipe)
  - 关闭 mcp-proxy 长连接
  - L4 config 缓存失效 (强制重新生成)
[来源标注] [TD:PC-工具调用延迟 + R-006 stdio 200ms / HTTP 500ms]
```

### PO-03 HTTP 工具调用延迟 P95 ≤ 1500ms

```
[性能指标] PO-03
[当前容量] P95 ~2.5s (V0)
[目标容量] P95 ≤ 1500ms
[瓶颈分析]
  - DNS 解析: 每次调用 50-200ms (无缓存)
  - TCP 握手: 100-300ms (TLS 1.3 1-RTT)
  - 跨区域: 100-500ms 物理延迟
  - 重定向链: 多次重定向 500-1000ms
[优化策略]
  1. DNS Pinning: 首次解析后锁定 IP, 重用 60s (命中率 > 90%)
  2. HTTP 连接池: per-host keep-alive
  3. TLS session resumption: 减少 1-RTT
  4. 重定向预算: 最大 3 跳, 超出拒绝
  5. 区域亲和性: workspace pod 调度到同区域
[实施步骤]
  步骤1: 实现 M-C04 DNS Pinning (yarl 单对象 + Redis 缓存)
  步骤2: 引入 httpx.AsyncClient 复用 TCP 连接
  步骤3: 配置 TLS session tickets
  步骤4: 限制重定向 max_redirects=3
  步骤5: 配置 K8s topology constraints
[验证方法]
  - 压测: 1000 RPS 跨区 HTTP 调用
  - 监控: dns_pinning.hit_rate, http_connect_reuse_rate
  - 目标: P95 < 1500ms, DNS 命中率 > 90%
[回滚策略]
  - 关闭 DNS Pinning 缓存 (每次重解析)
  - 关闭 keep-alive (短连接)
[来源标注] [TD:PC-HTTP + RSK-04 跨对象 Pinning + ADR-004 5 层]
```

### PO-04 冷启动延迟 P95 ≤ 1.2s

```
[性能指标] PO-04
[当前容量] P95 ~2.5s (V0)
[目标容量] P95 ≤ 1.2s
[瓶颈分析]
  - mcp-config 生成: 100ms
  - subprocess fork: 200ms
  - mcp-proxy 启动: 300ms
  - mcp-server 启动: 500ms (Node.js/Python 解释器)
  - tools/list RPC: 100ms
[优化策略]
  1. manifest_cache: 预编译/预加载 manifest, 启动前 30s 预热
  2. 预占槽位: 启动时预留 16 槽位 (warm pool)
  3. LRU 预热: 频繁使用的 mcp 优先 spawn
  4. mcp-server 镜像缓存: 宿主机层缓存 (overlay2)
  5. 启动并发: mcp-proxy + mcp-server 并行启动
[实施步骤]
  步骤1: 实现 manifest_cache (LRU + TTL 1h)
  步骤2: warm pool 16 槽位预创建
  步骤3: LRU 算法 (基于调用频次 + 最近使用)
  步骤4: 镜像层缓存 (Docker pull 优化)
  步骤5: 并行 subprocess.Popen (proxy + server)
[验证方法]
  - 压测: 1000 次冷启动 vs 热调用对比
  - 监控: spawn P95, warm_pool_hit_rate, manifest_cache_hit_rate
  - 目标: 冷启动 P95 < 1.2s, 热调用 P95 < 800ms
[回滚策略]
  - 关闭 warm pool (全冷启动)
  - 关闭 manifest_cache
  - 串行启动 mcp-proxy + mcp-server
[来源标注] [TD:PC-冷启动 + RSK-02 + 调研:R-005]
```

### PO-05 SSRF 检测 < 50ms/请求

```
[性能指标] PO-05
[当前容量] ~30ms (V0)
[目标容量] < 50ms
[瓶颈分析]
  - IP 黑名单查询: 列表遍历 O(n), 1000+ 条目
  - URL 解析: urllib.parse 多次调用 + CVE-2022-0391
  - DNS 解析: 同步阻塞
[优化策略]
  1. frozenset O(1): 私网/loopback/link-local 预计算
  2. yarl 单对象 Pin: 解析一次, 后续复用 (避免 urllib 多次解析)
  3. aiodns 异步解析: 与 HTTP 调用并行
  4. 缓存: 域名 → IP 缓存 TTL 60s (DE-018)
  5. IPv6 完整支持: 链路本地/ULA/IPv4-mapped 一次匹配
[实施步骤]
  步骤1: 预计算 frozenset (IPv4 私网/loopback/link-local + IPv6 链路本地/loopback/ULA/IPv4-mapped)
  步骤2: 引入 yarl.URL 替代 urllib.parse
  步骤3: aiodns 异步解析 (M-C04)
  步骤4: Redis 缓存 (DE-018)
  步骤5: 1000 QPS 压测
[验证方法]
  - 压测: 1000 QPS SSRF check
  - 监控: ssrf_check_latency_p95, blacklist_ip_match_count
  - 目标: P95 < 50ms, 100% 拦截已知 bypass (xip.io / hex / IPv6)
[回滚策略]
  - 关闭 yarl Pin (回退到 urllib)
  - 关闭缓存 (每次重解析)
[来源标注] [TD:PC-SSRF + ADR-004 + 调研:R-009 + S-032/S-033]
```

### PO-06 K4 静态分析 < 10s/MCP

```
[性能指标] PO-06
[当前容量] ~15s (V0)
[目标容量] < 10s
[瓶颈分析]
  - 11+1 类规则: AST 解析 200ms + 规则匹配 500ms × 12
  - 串行执行: 12 规则串行
  - 冷启动: 规则集每次从 PG 加载
[优化策略]
  1. 规则集预加载: 启动时从 PG 加载, 内存常驻
  2. 8 worker pool: 规则匹配并行
  3. ripgrep 加速: 大文件 (>1MB) 用 ripgrep 子进程预过滤
  4. 增量分析: 仅分析变更文件 (V2.0 引入)
  5. 缓存: 相同 manifest hash 复用结果
[实施步骤]
  步骤1: gRPC server + 8 worker subprocess (multiprocessing)
  步骤2: 启动时从 PG 加载 rule_set, 内存常驻
  步骤3: Pub/Sub 广播 reload 信号
  步骤4: ripgrep 预过滤 (manifest > 1MB)
  步骤5: 200 样本 FPR 校准时延验证
[验证方法]
  - 压测: 200 样本 FPR 校准
  - 监控: k4_analyze_latency_p95, worker_pool_busy
  - 目标: P95 < 10s, FPR < 15% (校准后)
[回滚策略]
  - 缩减 worker pool 至 4
  - 同步单进程分析（关闭并行）
  - 关闭 ripgrep 预过滤
[来源标注] [TD:PC-K4 + 调研:R-008 + 误判率校准]
```

### PO-07 沙箱 dry-run < 30s/MCP

```
[性能指标] PO-07
[当前容量] ~45s (V0)
[目标容量] < 30s
[瓶颈分析]
  - cgroup v2 创建: 500ms
  - 启动子进程: 200ms
  - 执行命令: 5-20s (用户命令)
  - 销毁: 200ms
  - DB 写入 audit: 100ms
[优化策略]
  1. cgroup v2 模板预创建: 复用模板而非每次创建
  2. 并发限制: 5 并发 (DB 连接限制 30)
  3. 超时强制: 30s 超时强制 kill
  4. 异步执行: 长命令转 arq 异步
  5. 平台自适应: Windows Docker + Linux cgroup + macOS sandbox-exec
[实施步骤]
  步骤1: cgroup v2 模板预创建 (cgroup.clone_children)
  步骤2: arq 任务分发, 5 并发信号量
  步骤3: 30s 强制 timeout (signal.SIGKILL)
  步骤4: Windows + macOS + Linux 三平台自适应
  步骤5: 5 并发沙箱 P95 压测
[验证方法]
  - 压测: 5 并发沙箱 P95
  - 监控: sandbox_run_latency, sandbox_timeout_count
  - 目标: P95 < 30s, 强制 kill 率 < 5%
[回滚策略]
  - 缩减并发至 2
  - 关闭 cgroup 模板复用
  - 增加超时至 60s
[来源标注] [TD:PC-沙箱 + 调研:R-003 + CVE-2025-53372]
```

### PO-08 DB 并发 100-200 连接

```
[性能指标] PO-08
[当前容量] 80 连接 (V0)
[目标容量] 100-200 连接
[瓶颈分析]
  - PG max_connections 默认 100
  - 应用连接池未优化: per-worker 20 × 8 = 160
  - 慢查询: 30 表无索引优化
[优化策略]
  1. PGBouncer transaction 模式: 减少物理连接
  2. 读副本: 分离读写
  3. MVIEW: 复杂查询物化视图
  4. 索引优化: 30 表核心查询索引
  5. 连接池: per-worker 20, PGBouncer 复用
[实施步骤]
  步骤1: 部署 PGBouncer (transaction mode, 100 pool_size)
  步骤2: PG 主备 + 读副本 (1 主 2 备)
  步骤3: 5 个 MVIEW (mcp_status / pool_status / approval_pending / log_recent / k4_stats)
  步骤4: 30 表核心查询索引审查
  步骤5: 200 连接 tps 压测
[验证方法]
  - 压测: pgbench 200 连接 tps
  - 监控: pg_stat_activity count, replica_lag
  - 目标: tps > 5000, replica_lag < 5s
[回滚策略]
  - 关闭 PGBouncer (直连 PG)
  - 关闭读副本
  - DROP MVIEW
[来源标注] [TD:PC-DB + RSK-09 cgroup 不可用降级]
```

---

## 3. 性能压测计划

### 3.1 压测工具

- **HTTP/REST**: locust 1.4+ + wrk 4.2
- **gRPC**: ghz 0.3+
- **WS**: websocket-bench 0.3+
- **DB**: pgbench 15 + sysbench 1.0
- **综合**: k6 0.45+ (可观测集成)

### 3.2 压测环境

- **staging 环境**：与生产同构（3 节点 K8s + 同等资源）
- **数据规模**：100 workspace + 200 user + 1000 mcp
- **持续时间**：稳态 30min + 峰值 5min

### 3.3 验收标准

| 指标 | 验收 | 监控告警阈值 |
|------|------|------------|
| API P95 延迟 | ≤ 200ms | > 500ms 警告 / > 1s 严重 |
| 错误率 | < 0.1% | > 1% 警告 / > 5% 严重 |
| 进程池 | 64/workspace | 满载 90% 警告 |
| DB 连接 | < 200 | > 180 警告 |
| CPU 利用率 | < 70% | > 80% 警告 / > 90% 严重 |
| 内存利用率 | < 80% | > 90% 警告 |

---

**性能优化方案文档结束。**
