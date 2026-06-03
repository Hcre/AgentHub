# 结构风险清单 SR-MCP-V1.0-20260602

> **范围**：8 条结构风险（每条含缓解+监控），含 SA 反例 CE-* 全部映射

| 风险编号 | 风险描述 | 影响模块 | 影响范围 | 缓解策略 | 监控指标 | 来源 |
|---------|---------|---------|---------|---------|---------|------|
| RSK-01 | mcp_proxy 6 项已知缺陷 (RSK-10) | M-B05/M-A01 | BP-009/010 全部调用首次失败 | DD 实施 6 项 workaround：session 重试/keepalive ping/TTL 清理/serverInfo 包装/wrapped stdio/端点文档化 | mcp_tool_first_call_error_rate < 1% | [SA:CE-012] |
| RSK-02 | 进程池 6,400 子进程 fd/内存爆炸 | M-B02 | V1.0 100 workspace 部署不可行 | ulimit -n 提至 65535；workspace Pool CRD；DB 分片 (50 ws/分片) | process_pool.active_count, host.fd_used | [TD推断:物理视图容量推导] |
| RSK-03 | K4 反引号/$()/curl|sh 漏检 (RSK-08) | M-C02 | BP-015 危险工具绕过 | 规则集追加 3 类模式；CE-014 回归测试 | k4.false_negative_rate (高危样本漏检率) | [SA:CE-014] |
| RSK-04 | SSRF 跨对象 Pinning 失效 (S-052) | M-C04/M-C06 | BP-013 重定向被绕过 | 跨对象持久化 first_pinned_ip；重定向前以首解析 IP 为基准 | dns_pinning.recheck_fail_count | [SA:CE-004] |
| RSK-05 | Cron + healthcheck 同相位抢占 | M-A04/M-B02 | BP-005 排队 5s+ | 错开 15s 相位：healthcheck :00，idle_scan :15/:45 | scheduler.phase_overlap_count=0 | [SA:CE-002] |
| RSK-06 | allowlist hash ensure_ascii 偏差 | M-B04 | BP-019/021 中文参数命中失效 | 提取公共函数 compute_args_hash；显式 ensure_ascii=False | allowlist.hit_rate (中文 ws 单独统计) | [SA:CE-006] |
| RSK-07 | 32 工具全量加载上下文爆炸 | M-B03 | BP-007 绑定接近上限时工具搜索失败 | V2.1 按需加载（M-B06 metadata-only） | claude_code.tool_search_latency | [SA:CE-007] |
| RSK-08 | mcp-config Bug #2946 静默覆盖 | M-B03 | BP-009 多 Runtime 配置被覆盖 | L4 单一源；SHARED LOCK；运维文档禁手动编辑 | config_file.last_writer_collision_count | [SA:调研 S-023/S-024] |
| RSK-09 | WSL2 cgroup 控制器不全 | M-C01 | BP-011 沙箱在 WSL2 失效 | .wslconfig 前置文档；setrlimit 降级路径 | sandbox.backend_used{backend=setrlimit} 占比 | [SA:调研 RSK-09] |
| RSK-10 | Inbox 长时间不可用批量误拒 | M-B04 | BP-019/020 Inbox 宕机 5min+ 大量误判 | EX-035 改进：Inbox 恢复后 1min 缓冲期不触发硬超时 | inbox.batch_rejected_after_recovery | [SA:CE-011] |
