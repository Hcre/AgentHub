# 框架决策记录 FDR-M-A03-MCP-V1.0-20260603

> 负责模块：M-A03 Webhook Receiver
> 决策数：6
> 来源：[DD-M推断:基于 DD-001 规范 + 模块细化方案]

---

## FDR-A03-001 独立 ASGI 端口（与 M-A01 隔离）

| 项 | 内容 |
|----|------|
| 决策编号 | FDR-A03-001 |
| 决策标题 | WebhookApp 独立端口（不复用 M-A01 的 FastAPI app） |
| 决策状态 | 已接受 |
| 决策内容 | M-A03 启动独立 ASGI 实例，监听独立端口（如 :8081），与 M-A01（:8080）物理隔离 |
| 决策理由 | 1) M-A01 主网关需稳定运行，不应被 webhook 突发流量拖垮 2) 资源争抢会导致网关 504 3) 独立部署便于弹性扩缩容 |
| 拒绝的替代方案 | A) 共用 M-A01 app：增加 /webhook/* 路由；被拒因：1) 资源争抢风险；2) 鉴权重叠（JWT vs HMAC）；3) 故障域耦合 |
| 影响范围 | 部署拓扑：M-A03 独立 K8s Deployment / 独立 Service |
| 相关 FDR | - |
| 来源标注 | [DD-001:MD-M-A03 + FS-003] |

---

## FDR-A03-002 Chain of Responsibility 验签

| 项 | 内容 |
|----|------|
| 决策编号 | FDR-A03-002 |
| 决策标题 | 采用 Chain of Responsibility 组织 HMAC 验签链路 |
| 决策状态 | 已接受 |
| 决策内容 | 验签链：HMAC 验签（per-source）→ ReplayGuard → Enqueuer，每环独立可替换 |
| 决策理由 | 1) 3 个 source（GitHub/GitLab/Bitbucket）需差异化 header 解析；Strategy 不如 Chain 直观；2) Chain 便于未来新增 source（如 Gitee）；3) 易于单元测试 |
| 拒绝的替代方案 | A) Strategy 模式 + 工厂：被拒因：策略分发与链式校验语义不符；B) 单一巨型 if-else：被拒因：违反 OCP，难扩展 |
| 影响范围 | verifiers/base.py（ABC） + 3 子类 + app.py 编排 |
| 相关 FDR | - |
| 来源标注 | [DD-001:MD-M-A03 + DP:Chain of Responsibility] |

---

## FDR-A03-003 立即 200 ack（异步处理）

| 项 | 内容 |
|----|------|
| 决策编号 | FDR-A03-003 |
| 决策标题 | 验签+入队后立即返回 200 ack，处理逻辑下放 arq worker |
| 决策状态 | 已接受 |
| 决策内容 | WebhookApp.handle 仅做"接收→验签→重放检测→入队→ack"，业务处理由 arq worker 异步执行 |
| 决策理由 | 1) 上游 GitHub 等会在 10s 后超时（5s 通常），本地处理 P95 不应 > 100ms 2) 同步处理会绑定 worker 线程 3) 失败重试由 arq 调度，比 HTTP 客户端重试更可靠 |
| 拒绝的替代方案 | A) 同步处理 + 立即落库：被拒因：性能 + 重试成本；B) 异步但阻塞等待 worker：被拒因：违反 ack 即返回原则 |
| 影响范围 | app.py / enqueuer.py；下游 worker 任务（不在 M-A03 范围） |
| 相关 FDR | - |
| 来源标注 | [DD-001:IC-003 + MD-M-A03] |

---

## FDR-A03-004 5min 重放窗口 + SETNX nonce

| 项 | 内容 |
|----|------|
| 决策编号 | FDR-A03-004 |
| 决策标题 | ReplayGuard 用 timestamp + nonce 双因子，Redis SETNX 5min TTL |
| 决策状态 | 已接受 |
| 决策内容 | 1) 校验 |now - ts| ≤ 300s；2) SETNX nonce:{source}:{nonce}，TTL=300s；3) 命中已存在 nonce → ReplayDetected |
| 决策理由 | 1) timestamp 单一防重放受 NTP skew 影响；2) nonce 防"同 ts 重复发"；3) SETNX 原子去重；4) TTL 自动清理避免膨胀 |
| 拒绝的替代方案 | A) 仅 timestamp 滑动窗口：被拒因：网络重发可能同 ts；B) 数据库 UNIQUE：被拒因：性能不如 Redis；C) 滑动时间窗 with 持久化：被拒因：复杂度高、收益低 |
| 影响范围 | replay_guard.py；依赖 M-D03 Redis |
| 相关 FDR | - |
| 来源标注 | [DD-001:IC-003 + MD-M-A03] |

---

## FDR-A03-005 失败计数告警（5min>100 封 IP 1h）

| 项 | 内容 |
|----|------|
| 决策编号 | FDR-A03-005 |
| 决策标题 | HMACMismatchError 触发滑动窗口计数，超阈值自动封禁源 IP |
| 决策状态 | 已接受 |
| 决策内容 | 1) Redis 维护 `hmac_fail:{ip}` 滑动计数器（5min）2) 阈值 > 100 → IP 黑名单 1h 3) 告警 ERROR + 通知 oncall |
| 决策理由 | 1) 防爆破（GitHub webhook secret 泄露/社工）；2) 自动化响应减少人工介入；3) 与 AR 洞察-10 一致 |
| 拒绝的替代方案 | A) 仅日志告警不自动封：被拒因：被动响应慢；B) 全局 IP 封禁：被拒因：影响合法用户 |
| 影响范围 | app.py + M-D02 metrics + 运维 runbook |
| 相关 FDR | - |
| 来源标注 | [DD-001:MD-M-A03 + AR洞察-10] |

---

## FDR-A03-006 测试场景 26 条 = 3 source × 多场景

| 项 | 内容 |
|----|------|
| 决策编号 | FDR-A03-006 |
| 决策标题 | 测试覆盖：3 source × {正常/伪造/重放/超时} = 至少 12 场景 + 集成 8 + 单元 6 = 26 场景 |
| 决策状态 | 已接受 |
| 决策内容 | 1) test_app.py：8 场景（3 source + 边界）；2) test_verifiers.py：9 场景（3 source × 3 场景）；3) test_replay_guard.py：5 场景；4) test_enqueuer.py：4 场景 |
| 决策理由 | 1) MD-M-A03 要求 22 场景，含边界覆盖；2) 安全关键模块覆盖率 ≥ 90%；3) 3 source 必须独立测试防回归 |
| 拒绝的替代方案 | A) 仅端到端 22 场景：被拒因：故障定位粒度差；B) 参数化单文件：被拒因：违反测试职责分离 |
| 影响范围 | tests/* 全部 |
| 相关 FDR | - |
| 来源标注 | [DD-001:MD-M-A03] |

---

## 决策汇总

| FDR | 标题 | 状态 |
|-----|------|------|
| FDR-A03-001 | 独立 ASGI 端口 | 已接受 |
| FDR-A03-002 | Chain of Responsibility 验签 | 已接受 |
| FDR-A03-003 | 立即 200 ack | 已接受 |
| FDR-A03-004 | 5min 重放窗口 + SETNX | 已接受 |
| FDR-A03-005 | 失败计数自动封 IP | 已接受 |
| FDR-A03-006 | 26 测试场景 | 已接受 |

[来源标注] [DD-001:MD-M-A03 + IC-003 + FS-003 + AR洞察-10]
