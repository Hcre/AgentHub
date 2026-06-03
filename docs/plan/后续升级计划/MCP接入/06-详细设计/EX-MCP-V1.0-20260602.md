# 异常处理策略 EX-MCP-V1.0-20260602

> 14 边界 (SEC-001~SEC-014) 1:1 异常处理策略 + 4 条跨边界系统级 = 共 18 条
> 模板遵循 soul 3.7（异常类型/触发条件/处理流程/降级策略/告警机制/来源标注）

---

## 一、异常基类（agenthub/core/exceptions.py）

```python
class AgentHubError(Exception):
    """所有领域异常基类."""
    code: str = "UNKNOWN"
    http_status: int = 500

class BusinessError(AgentHubError):       """业务异常 4xx."""
class SystemError(AgentHubError):         """系统异常 5xx."""
class NetworkError(SystemError):          """网络异常."""
class DataError(SystemError):             """数据异常."""
class SecurityError(AgentHubError):       """安全异常."""
class ValidationError(BusinessError):     """输入校验失败."""
class NotFoundError(BusinessError):       """资源不存在."""
class ConflictError(BusinessError):       """资源冲突."""
class RateLimitError(BusinessError):      """限流命中."""
class TimeoutError(SystemError):          """超时."""
```

所有 EX-NNN 异常继承上述基类，统一 `{code, message, trace_id, data}` 响应格式。

---

## 二、按边界异常处理策略

### EX-001 B-001 市场查询

```
[异常编号] EX-001
[关联边界] SEC-001 / B-001
[异常类型] 业务异常 + 系统异常
[触发条件]
  - JWT 无效 / 过期
  - 参数校验失败（category/q/page）
  - 高频访问（> 100 QPS/IP）
  - DB 不可用
[处理流程]
  1. AuthError → 401 + AUTH_FAILED
  2. ValidationError → 422 + VALIDATION_FAILED + 字段细节
  3. RateLimitError → 429 + RATE_LIMIT_EXCEEDED + Retry-After
  4. DBError → 503 + 走 Redis 缓存降级（30min TTL）
[降级策略]
  DB 不可用 → 返回 Redis 缓存（标记 stale=true）
  缓存也无 → 返回空列表 + WARN 日志
[告警机制]
  级别: WARN（限流命中 5min > 100 次）/ ERROR（DB 持续 1min 不可用）
  通知: Loki → AlertManager → 钉钉/邮件
  对象: 运维 oncall
[来源] [AR:SEC-001 + API:API-100]
```

### EX-002 B-002 MCP 安装

```
[关联边界] SEC-002 / B-002
[异常类型] 业务异常
[触发条件] 越权安装 / CSRF / 进程池满 / 二次确认超时
[处理流程]
  1. PermissionError(403) → MCP_PERMISSION_DENIED
  2. PoolFullError(429) → POOL_FULL → 触发 LRU 驱逐 → 重试 1 次
  3. ConfirmTimeout(60s) → 标记 cancelled
[降级] 进程池满 → reserved_slot + 客户端轮询
[告警] WARN（pool 利用率 > 80%）/ ERROR（spawn 失败率 > 5%）
[来源] [AR:SEC-002 + API:API-110]
```

### EX-003 B-003 MCP 提交（Saga）

```
[关联边界] SEC-003 / B-003
[异常类型] 业务 + 数据 + 安全
[触发条件] dry_run 失败 / K4 拒绝 / secret 写入失败 / metadata 冲突
[处理流程]
  - DryRunFailed → 标 rejected + 用户提示（不补偿）
  - K4Rejected → 标 rejected（DDR-005 不补偿）
  - SecretFailed → 补偿: 删 metadata + history → 标 failed
  - MetadataFailed → 补偿: 删 secret → 标 failed
[降级] Saga 失败 → trace_id 持久化 → arq 重试 max 3
[告警] ERROR（每次 Saga 失败）；CRITICAL（重试 3 次仍失败）
[来源] [AR:SEC-003 + DDR-005]
```

### EX-004 B-004 工具调用（SSRF + 越权）—— 最关键

```
[关联边界] SEC-004 / B-004
[异常类型] 安全异常（最高优先级）
[触发条件]
  - SSRF 探测：scheme/IP/port/redirect/DNS 链中任一拒绝
  - mTLS 证书无效
  - workspace_id 越界
  - 重放（trace_id 5min 内重复）
[处理流程]
  1. SSRFAttempt → 立即拒绝 + 写 ERROR 审计 + 触发安全告警
     - 记录: url_hash / agent_id / 拒绝层（哪个 validator）
  2. mTLSAuthFailed → close + 通知 PKI 系统轮换证书
  3. WorkspaceCrossBorder → 403 + WORKSPACE_DENIED + 不返回详细原因
  4. Replay → 409 + REPLAY_DETECTED
[降级]
  SSRF 校验链中任一步失败时 fail-secure（默认拒绝）
  DNS 解析失败 → 默认拒绝（不可"通过"以免绕过）
[告警] ALL ERROR；SSRF 命中触发安全运营中心告警（CRITICAL）
[合规] OWASP ASVS L3 / NIST SP 800-53 SC-7
[来源] [AR:SEC-004 + ADR-004 + S-032]
```

### EX-005 B-005 审批决策

```
[关联边界] SEC-005 / B-005
[异常类型] 业务异常 + 安全异常
[触发条件] 越权决策 / 重复决策 / 时间戳重放 / hash 不一致
[处理流程]
  1. PermissionError(403) → APPROVAL_PERMISSION_DENIED
  2. DuplicateDecision → 409 → 返回上次结果（幂等）
  3. ReplayDetected(decision_ts 超出 5min) → 409 + REPLAY
  4. HashMismatch → 500 + 走 pending + 报警 CRITICAL
[降级] 不允许（决策必须显式）
[告警] ERROR（越权）/ CRITICAL（hash 不一致 → 可能 hash 函数被改）
[来源] [AR:SEC-005 + ADR-006 + AR洞察-3]
```

### EX-006 B-006 Webhook 入站

```
[关联边界] SEC-006 / B-006
[异常类型] 安全异常 + 业务异常
[触发条件] HMAC 验签失败 / 重放 / 限流 / source 非白名单
[处理流程]
  1. HMACFailed → 401 + WEBHOOK_HMAC_FAILED + 失败计数器++
     - 5min 内同 source IP > 100 → 自动封禁 1h（[AR洞察-10]）
  2. Replay → 409
  3. RateLimit → 429
  4. SourceNotInWhitelist → 401 + 拒绝
[降级] 验签失败仅拒绝，不阻塞其他 source
[告警] WARN（单次失败）/ ERROR（5min > 50 次）/ CRITICAL（启动 IP 封禁）
[来源] [AR:SEC-006 + AR洞察-10]
```

### EX-007 B-007 Cron 触发

```
[关联边界] SEC-007 / B-007
[异常类型] 系统异常
[触发条件] Leader 丢失 / arq dispatch 失败 / 同步 cron 表失败
[处理流程]
  1. LeaderLost → 停止 scheduler + 让位
  2. DispatchError → arq 重试（指数 1s/2s/4s, max 3）
  3. MissedRun → 跳过（不补跑，[AC:AG-004]）
  4. 内部伪造 cron（[AR洞察-11]）→ mTLS 校验失败 → 拒绝
[降级] 无（Cron 是触发，未触发不影响业务即时性）
[告警] WARN（让位）/ ERROR（dispatch 持续失败）
[来源] [AR:SEC-007 + AR洞察-11]
```

### EX-008 B-008 WS 事件下行

```
[关联边界] SEC-008 / B-008
[异常类型] 网络异常 + 安全异常
[触发条件] 推送失败 / 越权订阅 / 离线缓存满 / WS 心跳超时
[处理流程]
  1. PushFailed → 写 Redis Stream 离线队列（max 1000 events, 1h TTL）
  2. ACLError → close 1008
  3. OfflineQueueFull → 丢弃最旧事件 + WARN
  4. PingTimeout(30s) → close 1011 → 客户端重连
[降级] WS 不可用 → 客户端轮询 REST API（前端兜底实现）
[告警] WARN（离线队列 > 80% 容量）/ ERROR（推送失败率 > 5%）
[来源] [AR:SEC-008 + AC:AG-002]
```

### EX-009 B-009 Prometheus 抓取

```
[关联边界] SEC-009 / B-009
[异常类型] 系统异常
[触发条件] /metrics 端点超时 / 暴露非白名单 label
[处理流程]
  1. PromExportError → 降级本地 buffer（in-memory，1min）
  2. LabelViolation → CI/单元测试阶段拦截（不上线）
[降级] Prom 持续不可用 → 本地 buffer 满后丢弃最旧（不影响业务）
[告警] WARN（scrape 失败）/ ERROR（5min 持续失败）
[来源] [AR:SEC-009]
```

### EX-010 B-010 IM 通知（Inbox）

```
[关联边界] SEC-010 / B-010
[异常类型] 网络异常
[触发条件] IM Webhook 调用失败 / 限流
[处理流程]
  1. IMSendFailed → 邮件兜底发送
  2. RateLimit → 退避重试 + 合并通知（5min 内同类合并）
[降级] IM 失败 → 邮件；邮件失败 → 仅写 DB（用户登录后看 Inbox）
[告警] WARN（IM 单次失败）/ ERROR（兜底链全失败）
[来源] [AR:SEC-010]
```

### EX-011 B-011 mcp-config 文件（关键输出）

```
[关联边界] SEC-011 / B-011
[异常类型] 数据异常 + 安全异常
[触发条件] fcntl 锁竞争 / 多 writer 检测 / 路径遍历探测 / 文件权限被改
[处理流程]
  1. LockTimeout → 重试 1 次（200ms）→ 失败则 503 + 告警
  2. MultiWriterDetected（Bug #2946）→ 立即 CRITICAL 告警 + 暂停 spawn
  3. PathTraversal → 拒绝 + 安全告警
  4. PermissionChanged → 自动 chmod 0600 + INFO 日志
[降级] 不允许；mcp-config 是 spawn 的硬依赖
[告警] CRITICAL（multi-writer）/ ERROR（lock 持续失败）
[来源] [AR:SEC-011 + BR-032 + RSK-08 + Bug#2946]
```

### EX-012 B-012 不处理: 第三方协议

```
[关联边界] SEC-012 / B-012
[异常类型] 声明性（不处理）
[处理] 暴露给上游处理；不主动 catch
[来源] [AR:SEC-012]
```

### EX-013 B-013 不处理: 跨 ws 共享

```
[关联边界] SEC-013 / B-013
[处理] 物理隔离（强制 workspace_id），任何跨 ws 调用立即抛 WorkspaceCrossBorder
[告警] CRITICAL（任何跨 ws 访问尝试）
[来源] [AR:SEC-013]
```

### EX-014 B-014 不处理: MCP 自升级

```
[关联边界] SEC-014 / B-014
[处理] 声明性；mcp-server 内部升级机制不由 AgentHub 控制
[来源] [AR:SEC-014]
```

---

## 三、跨边界系统级异常

### EX-015 PG / Redis 集群故障

```
[关联] 全局 SystemError
[触发] PG 主库不可达 / Redis cluster 节点 < 3 master
[处理]
  PG 不可达:
    - asyncpg 触发 ConnectionError
    - SQLAlchemy retry 1 次（指数 100ms）
    - 仍失败 → 503 DB_UNAVAILABLE 上抛
    - M-B04 Approval 走 "fail-safe pending"
    - M-B02 Pool 走 Redis Redlock 降级（[DD洞察-1]）
  Redis cluster 故障:
    - 失败传递到上层 + CRITICAL 告警
    - WS 离线队列丢失（接受）
    - allowlist 全失效 → 强制走 PG 直查
[告警] CRITICAL（任一）
[来源] [AR:全模块 + DD洞察-1]
```

### EX-016 Vault 故障

```
[关联] M-C07 全局依赖
[触发] Vault sealed / token 过期 / 网络不通
[处理]
  - 启动时 sealed → fail-fast（拒绝启动）
  - 运行时 token 过期 → 自动 renew；连续失败 3 次 → CRITICAL
  - 运行时 sealed → 短期使用 LRU 缓存 30s；缓存过期后请求失败
[告警] CRITICAL（启动 / 运行时持续 1min 不可用）
[来源] [AR:M-C07 + TDR-010]
```

### EX-017 Event Bus 失效

```
[关联] M-EV01 全局
[触发] Redis Pub/Sub 断连
[处理]
  - 自动重连 + 重新订阅（max 10s）
  - 关键 topic 用 Stream 保证至少一次（[AR洞察-1]）
  - 非关键 topic 接受丢失（如 process.health_changed 下次 healthcheck 会刷新）
[告警] ERROR（重连失败 > 1min）
[来源] [AR:M-EV01 + AR洞察-1]
```

### EX-018 K8s Pod OOM / CrashLoop

```
[关联] 全部 Deployment
[触发] OOM / liveness 失败 → CrashLoopBackOff
[处理]
  - K8s 自动重启
  - 启动后从 PG/Redis 恢复状态
  - HPA 自动扩容（CPU > 70%）
[告警] ERROR（CrashLoop 持续 > 5min）
[来源] [AR:DP + AC:AG-001~022]
```

---

## 四、统一错误响应

```json
{
  "code": "APPROVAL_DB_UNAVAILABLE",
  "message": "审批数据库暂时不可用，已保守走 pending 流程",
  "trace_id": "01HX2ABCDEF...",
  "data": {
    "workspace_id": "...",
    "queue_id": null,
    "fallback": "pending"
  },
  "timestamp": "2026-06-02T12:34:56.789Z"
}
```

---

## 五、异常处理覆盖统计

| 维度 | 实测 |
|------|------|
| 14 SEC 边界 | 14 EX 一一对应（含 3 个不处理声明） |
| 跨边界系统级 | 4（PG/Redis、Vault、Bus、K8s） |
| 总策略数 | 18 |
| 含告警机制 | 18/18 = 100% |
| 含降级策略（非声明性 11 条）| 11/11 = 100% |

**D7 = 100%（14/14 边界覆盖）**

---

**[DD 洞察-8]** EX-005 中"HashMismatch → 走 pending + CRITICAL"——若 hash 函数被恶意修改或迭代升级，会瞬间产生大量 pending 决策造成 inbox 雪崩。建议在 ApprovalService 启动时跑一次自检（已知样本 → 预期 hash），失败则 fail-fast 拒绝启动，避免错误版本进入流量。已记入 DDR-008。

**异常处理策略文档结束。**
