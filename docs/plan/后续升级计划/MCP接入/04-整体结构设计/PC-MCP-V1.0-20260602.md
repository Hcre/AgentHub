# 性能容量预判表 PC-MCP-V1.0-20260602

> **范围**：8 项性能指标（[灵魂 R17] PRD 非功能需求 100% 覆盖）

| 性能指标 | 预估规模 | 架构应对策略 | 瓶颈模块 | 扩展方式 | 基准测试建议 | 来源 |
|---------|---------|------------|---------|---------|------------|------|
| 进程池容量 | 64/workspace, 6400 全平台 | ulimit + workspace 隔离 + HPA | M-B02 | 增加 workspace Pod | 64 并发 healthcheck 100/500/1000 ws 延迟 | [SA:BR-005/S-037] |
| 工具调用延迟 stdio | P95 ≤ 800ms | ring buffer + 内存通信 + L4 config 缓存 | M-A02 | 水平扩展 WS gateway | 1000 QPS tool_call P95 分布 | [SA:BR-029/S-029] |
| 工具调用延迟 HTTP | P95 ≤ 1500ms | yarl Pinning + Redis 缓存 | M-C04/M-A02 | DNS 缓存命中率 > 90% | 跨区 HTTP 调用 P95 | [SA:BR-029] |
| 冷启动延迟 | P95 ≤ 1.2s | manifest_cache + manifest 预热 30s | M-B02 | 预占槽位 + LRU 预热 | 冷启动 vs 热调用 P95 对比 | [SA:BR-007/CE-013] |
| SSRF 检测 | < 50ms/请求 | IP 黑名单 O(1) 哈希 + yarl 单对象 Pin | M-C06 | 无状态可水平扩 | 1000 QPS SSRF check P95 | [SA:BR-010] |
| K4 静态分析 | < 10s/MCP | 规则集预加载 + 样本 1:1 校准 | M-C02 | gRPC 池化 (8 worker) | 200 样本 FPR 校准时延 | [SA:BR-019/EX-027] |
| 沙箱 dry-run | < 30s/MCP | cgroup v2 + 临时子进程 | M-C01 | 并发 5 (DB 连接限制) | 5 并发沙箱 P95 | [SA:BR-012/EX-021] |
| DB 并发 | 100-200 连接 | PostgreSQL 主备 + MVIEW + 索引 | M-D01 | 连接池 + 读副本分离 | 200 连接 tps 压测 | [TD推断:30 表/290 字段] |
| 进程数 → 内存 | 64×256MB=16GB/workspace | workspace 隔离 + 16GB 推荐 | M-B02/M-A01 | 多 host 部署 | 64 进程 RSS 分布 | [SA:S-037] |
| WS 并发连接 | 假设 500 | nginx sticky + 多实例 | M-A02 | 增加 ws-gateway 实例 | 500/1000 长连接 P95 | [TD推断] |
