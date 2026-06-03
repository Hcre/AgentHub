# 数据流向图 DF-MCP-V1.0-20260602

> **范围**：30 个 DE 的正常+异常流向（[灵魂 R21] 100% 覆盖）

## 数据实体流向矩阵

| DE | 产生模块 | 正常流转 | 异常流转 | 消费模块 | 存储 | 一致性 | 来源 |
|----|---------|---------|---------|---------|------|--------|------|
| DE-001 mcp_server | M-B05 (BP-012/013/014/016) | 创建→M-B01 列表→M-B02 安装→M-B03 绑定→M-B04 审批 | 创建失败→M-B05 回滚+报警；SSRF→M-C06 拒绝 | M-B01/M-B02/M-B03/M-B04 | PG | 强一致 | [SA:DE-001] |
| DE-002 mcp_template | M-C03 (BP-014/017/024) | 模板定义→M-C03 升级→M-B05 应用→workspace 通知 | webhook 验签失败→M-C07 报警+丢弃 | M-C03/M-B05 | PG | 强一致 | [SA:DE-002] |
| DE-003 mcp_installation | M-B02 (BP-002) | 安装→M-B02 启动→WS 推 running→M-B01 展示 | 启动失败→status=install_failed→M-D02 报警 | M-B01/M-B02 | PG | 最终一致(100ms) | [SA:DE-003] |
| DE-004 process_pool | M-B02 (BP-002) | spawn→healthcheck 周期→idle 回收→evict | SIGKILL 失败→zombie→M-D02 报警+OS 介入 | M-B01/M-B02/M-A04 | PG+内存 | 强一致 | [SA:DE-004] |
| DE-005 workspace | (沿用) | U-01 触发→M-B02 鉴权 | — | M-B01/M-B02/M-B04 | PG | 强一致 | [SA:DE-005] |
| DE-006 mcp_log | M-B02 (BP-003) | ring buffer→M-D02 Loki；tail 查询→M-B01 返回 | 覆盖→提示+切外部收集 | M-B01/M-D02 | Loki+内存 | 异步批写(5s) | [SA:DE-006] |
| DE-007 metrics_counter | 全部模块 | 8 个 Prom 指标→M-D02 Prom | label 超白名单→M-D02 丢弃+告警 | M-D02/M-A04 | Prom | 最终一致(5s) | [SA:DE-007] |
| DE-008 health_history | M-B02 (BP-005) | healthcheck→记录→M-D02 展示 | timeout→M-D02 报警+fail_count+1 | M-B02/M-D02 | PG | 最终一致(30s) | [SA:DE-008] |
| DE-009 mcp_binding | M-B03 (BP-007) | bind→M-C08 转换→写入→M-B03 重新生成 config | 32 满→M-B03 拒绝；进程重启竞态→M-B03 等待 5s | M-B03/M-B05 | PG | 强一致 | [SA:DE-009] |
| DE-010 agent | (沿用) | U-01 触发→M-B03 鉴权 | — | M-B03 | PG | 强一致 | [SA:DE-010] |
| DE-011 mcp_config_file | M-B03 (BP-009) | 生成→SHARED LOCK→写 /tmp→Runtime Adapter 读取 | 锁等待超时→重试 3 次→报警 | M-B03/M-B05 | PG+文件 | 强一致(顺序) | [SA:DE-011] |
| DE-012 ws_event | M-B02/M-B03/M-B04 | 产生→M-A02 路由→前端订阅 | 客户端离线→Redis 队列→重连批量下发 | M-A02 | PG+Redis | 最终一致(50ms) | [SA:DE-012] |
| DE-013 ws_subscription | M-A02 (BP-010) | 客户端连接→M-A02 注册→心跳维护 | 心跳超时→status=expired | M-A02 | PG | 强一致 | [SA:DE-013] |
| DE-014 sandbox_session | M-C01 (BP-011) | 启动→执行→捕获→销毁 | 沙箱逃逸→M-C01 强制 kill+报警+1h 锁定 | M-C01/M-D02 | PG | 强一致 | [SA:DE-014] |
| DE-015 cgroup_config | M-C01 (BP-011) | 平台检测→cgroup v2 创建→限制→销毁 | cgroup 不可用→setrlimit 降级+报警 | M-C01 | PG | 强一致 | [SA:DE-015] |
| DE-016 secret_reference | M-C07 (BP-012) | 写入→M-C07 加密→M-B05 引用 | 泄露检测命中→M-C07 强制 redact+提示 | M-B05/M-C07 | Vault | 强一致 | [SA:DE-016] |
| DE-017 mcp_submission | M-B05 (BP-012/016) | 提交→K4 评分→写库→M-B05 审核 | K4 超时→unknown+人工审核 | M-B05/M-C02 | PG | 强一致 | [SA:DE-017] |
| DE-018 dns_pinning_cache | M-C04 (BP-013) | 解析→写缓存(TTL 60s)→重定向前读 | TTL 过期→M-C04 重解析；rebind→M-C06 拒绝 | M-C04/M-C06 | PG+Redis | 强一致 | [SA:DE-018] |
| DE-019 mcp_migration_notice | M-C03 (BP-014/024) | 触发→workspace 通知→倒计时 30d | 主动升级→status=cancelled | M-C03/M-C09 | PG | 强一致 | [SA:DE-019] |
| DE-020 k4_rule_set | M-C02 (BP-015) | 加载→11+1 类规则→M-C02 评分 | 误判率>15%→回滚+报警 | M-C02 | PG | 强一致 | [SA:DE-020] |
| DE-021 k4_test_corpus | M-C02 (BP-015) | 200 样本→M-C02 校准 | 样本不足→M-C02 拒绝校准 | M-C02 | PG | 强一致 | [SA:DE-021] |
| DE-022 mcp_submission_history | M-B05 (BP-016) | 提交后快照→M-B05 回滚读取 | 启动失败→自动回滚到 vN+1 | M-B05 | PG | 强一致 | [SA:DE-022] |
| DE-023 webhook_event | M-A03 (BP-017) | 接收→验签→M-C03 处理 | 验签失败→401+报警；拉取失败→3 次重试 | M-A03/M-C03 | PG | 最终一致(异步) | [SA:DE-023] |
| DE-024 config_override | M-C03 (BP-017) | 写入→深度合并→M-C03 应用 | 合并冲突→标量覆盖 | M-C03 | PG | 强一致 | [SA:DE-024] |
| DE-025 network_acl | M-C05 (BP-018) | 写入→iptables/Docker 网络→容器附加 | 权限不足→报警；通配符→拒绝 | M-C05 | PG | 强一致 | [SA:DE-025] |
| DE-026 docker_network | M-C05 (BP-018) | 创建→127.0.0.11 DNS→容器附加 | Docker 不可用→主机级 iptables 降级+报警 | M-C05 | PG | 强一致 | [SA:DE-026] |
| DE-027 inbox_queue | M-B04 (BP-019/020) | 写入→软提醒(10min)→硬超时(30min) | IM 失败→邮件兜底；DB 不可用→保守 pending | M-B04/M-A04 | PG | 最终一致 | [SA:DE-027] |
| DE-028 inbox_decision | M-B04 (BP-019/020) | 决策→M-B04 执行→append-only 保留 | auto_rejected→客户端收 APPROVAL_TIMEOUT | M-B04 | PG | 强一致(append) | [SA:DE-028] |
| DE-029 allowlist_30d | M-B04 (BP-019/021) | 决策→写 DB+Redis 缓存→30d 过期清理 | DB 不可用→保守不命中→走审批 | M-B04/M-D03 | PG+Redis | 最终一致(500ms) | [SA:DE-029] |
| DE-030 mcp_migration_history | M-C09 (BP-024) | 执行→结果→append-only 保留 | 启动失败→回滚+failed+人工修复 | M-C09 | PG | 强一致 | [SA:DE-030] |

**验证**：30/30 DE 完整正常+异常流向 ✓；无数据孤岛（每个 DE 均有产生和消费节点）✓
