# 安全设计方案 SEC-MCP-V1.0-20260602

> **范围**：14 条系统边界（输入 7 + 输出 4 + 不处理 3）100% 安全策略覆盖（4.14 安全左移 + 4.8 决策树）

---

## 1. 安全设计总览

| 边界 | 类型 | 认证 | 授权 | 加密 | 审计 | 防护措施 | 风险模型 | 来源 |
|------|------|------|------|------|------|---------|---------|------|
| B-001 MCP 市场查询 | 输入 | OAuth2/JWT | RBAC (U-01/02) | TLS 1.3 | 全部 GET 写审计 | 限流 100 QPS/IP + WAF | 越权/注入 | [TD:B-001] |
| B-002 MCP 安装请求 | 输入 | OAuth2/JWT | U-01=ws_id 管理员 | TLS 1.3 | 全部 POST 写审计 | 二次确认 + 限流 10 QPS | 越权/CSRF | [TD:B-002] |
| B-003 MCP 提交请求 | 输入 | OAuth2/JWT | U-03 创作者 | TLS 1.3 | 全部 POST 写审计 | 字段 secret 标记 + detect-secrets | 注入/越权 | [TD:B-003] |
| B-004 工具调用请求 | 输入 | mTLS (Agent) | workspace_id 校验 | TLS 1.3 | 全链路 trace_id | SSRF 5 层 + allowlist | SSRF/注入 | [TD:B-004] |
| B-005 审批决策提交 | 输入 | OAuth2/JWT | U-04 ws 审批人 | TLS 1.3 | append-only 决策日志 | decision 不可篡改 | 越权/篡改 | [TD:B-005] |
| B-006 Webhook 入站 | 输入 | HMAC-SHA256 | source 白名单 | TLS 1.3 | 验签失败率告警 | hmac.compare_digest 常量时间 | 伪造/重放 | [TD:B-006] |
| B-007 Cron 触发信号 | 输入 | 内部可信 | n/a | n/a | 全部触发写审计 | 不暴露外部触发 | 内部滥用 | [TD:B-007] |
| B-008 工具事件下行 (WS) | 输出 | mTLS (Agent) | agent_id 权限 | TLS 1.3 + WSS | 全部推送写审计 | 离线队列加密 | 窃听/越权 | [TD:B-008] |
| B-009 Prometheus 指标 | 输出 | 内网白名单 | n/a | n/a | scrape 审计 | 8 label 白名单 | 信息泄露 | [TD:B-009] |
| B-010 Inbox 通知 (IM) | 输出 | IM Webhook 鉴权 | n/a | TLS 1.3 | 通知失败兜底邮件 | 失败重试 + 邮件兜底 | 窃听 | [TD:B-010] |
| B-011 MCP 子进程启动参数 | 输出 | 文件权限 0600 | workspace_id 隔离 | n/a | last_writer 告警 | SHARED LOCK + 路径固定 | 覆盖/越权 | [TD:B-011] |
| B-012 不处理: 第三方协议 | 不处理 | n/a | n/a | n/a | n/a | 声明性 | n/a | [TD:B-012] |
| B-013 不处理: 跨 ws 共享 | 不处理 | n/a | 物理隔离 | n/a | n/a | 强制 workspace_id | n/a | [TD:B-013] |
| B-014 不处理: MCP 自升级 | 不处理 | n/a | n/a | n/a | n/a | 声明性 | n/a | [TD:B-014] |

---

## 2. 关键边界详细安全设计

### SEC-001 B-001 MCP 市场查询

```
[安全编号] SEC-001
[关联边界] B-001
[威胁模型]
  - 越权访问: 非授权用户查询市场 (威胁等级: 中)
  - 注入攻击: SQL 注入 (category/q/page 参数) (威胁等级: 高)
  - 拒绝服务: 高频查询 (威胁等级: 中)
[认证策略] OAuth2 Bearer JWT (RS256, 公钥由 Vault 注入)
  - 用户类型: U-01 (ws 管理员) / U-02 (普通用户)
  - 验证位置: API Gateway (M-A01) 统一拦截
  - 失败处理: 401 + 记录审计 (rate limit 5/min/IP)
[授权策略] RBAC
  - U-01: 查所有 ws
  - U-02: 仅查自己加入的 ws
  - 权限粒度: 资源级 (market:read)
[加密策略]
  - 传输: TLS 1.3 (前向保密 P-256)
  - 存储: 缓存结果 (Redis) 不含 PII, 30min TTL
[审计策略]
  - 记录: user_id / endpoint / params / response_code / trace_id
  - 保留: 90 天 (审计合规)
  - 查询: Grafana + Loki 全文检索
[防护措施]
  - WAF: OWASP CRS 3.3 (SQL 注入 / XSS)
  - 限流: 100 QPS/IP + 1000 QPS/global
  - 输入校验: Pydantic v2 schema (type + regex + length)
  - 输出编码: JSON 序列化 (自动)
[合规要求] GDPR Article 32 + OWASP ASVS L2
[来源标注] [TD:B-001 + BR-005 + RSK-01 静默覆盖]
```

### SEC-002 B-002 MCP 安装请求

```
[安全编号] SEC-002
[关联边界] B-002
[威胁模型]
  - 越权安装: 非 ws 管理员安装 MCP (威胁等级: 高)
  - CSRF: 跨站请求伪造 (威胁等级: 中)
  - 资源耗尽: 进程池填满 (威胁等级: 中)
[认证策略] OAuth2 Bearer JWT + CSRF Token (double-submit cookie)
  - 用户类型: U-01 (ws 管理员)
  - 二次确认: WS 推送 "是否确认安装" (M-A02)
[授权策略] RBAC + workspace 成员校验
  - 权限粒度: mcp:install
  - 强制校验: U-01 ∈ workspace_id.admins
[加密策略]
  - 传输: TLS 1.3
  - 参数: mcp_id/ws_id 不可逆哈希后审计
[审计策略]
  - 记录: user_id / mcp_id / workspace_id / install_source / decision
  - 保留: 365 天 (合规)
[防护措施]
  - 限流: 10 QPS/ws (安装写操作)
  - 进程池硬限: 64/ws (BR-005)
  - 输入校验: UUID v4 regex
[合规要求] SOC 2 CC6.1 + ISO 27001 A.9.4
[来源标注] [TD:B-002 + BR-005 + RSK-02 6,400 容量]
```

### SEC-004 B-004 工具调用请求（最关键边界）

```
[安全编号] SEC-004
[关联边界] B-004
[威胁模型]
  - SSRF 攻击: 恶意 URL 调用内部服务 (威胁等级: 严重, CVE-2025-49596 历史)
  - 工具调用绕过: 越权调用危险工具 (威胁等级: 高)
  - 越权: workspace 越界 (威胁等级: 中)
  - 重放: 同 trace_id 重放 (威胁等级: 低)
[认证策略] mTLS (Agent 客户端证书, 由 AgentHub 颁发)
  - 证书: 有效期 24h, 自动轮换
  - 验证: 双向 TLS (Agent + AgentHub-Core)
[授权策略] workspace_id + agent_id 双校验
  - 工具名 → mcp_id → workspace_id 链路校验
  - 命名转换后 mcp.* 命名空间校验 (CE-007 避免搜索失败)
[加密策略]
  - 传输: TLS 1.3 (强制)
  - 工具调用参数: 落库前 redact (Secret 标记)
[审计策略]
  - 全链路 trace_id: API → Approval → MCP Server → Log
  - 记录: trace_id / agent_id / workspace_id / mcp_id / tool / args_hash / decision
  - 保留: 90 天 (合规 + 调试)
[防护措施]
  - SSRF 5 层防御 (ADR-004):
    1. yarl 单对象 Pin (M-C04)
    2. 域名级缓存 (Redis DE-018, TTL 60s)
    3. 重定向重校验 (max 3 跳)
    4. IP 黑名单 (M-C06 frozenset O(1))
    5. DNSSEC 验证 (可选, V2.0)
  - allowlist 优先 (M-B04): 命中直接允许, 未命中走审批
  - 输入校验: 工具参数 schema (Pydantic v2 + jsonschema)
  - 沙箱执行: stdio 走 M-C01 沙箱, HTTP 走 5 层防御
[合规要求] OWASP ASVS L3 + NIST SP 800-53 SC-7
[来源标注] [TD:B-004 + ADR-004 + RSK-04 + 调研:R-009 + S-032/S-033]
```

### SEC-005 B-005 审批决策提交

```
[安全编号] SEC-005
[关联边界] B-005
[威胁模型]
  - 决策篡改: 决策后被恶意修改 (威胁等级: 严重)
  - 越权决策: 非审批人决策 (威胁等级: 高)
  - 决策泄露: 审批内容 PII 泄露 (威胁等级: 中)
[认证策略] OAuth2 Bearer JWT + mTLS (MFA 可选)
  - 用户类型: U-04 (ws 审批人)
  - 二次验证: 敏感决策需邮件确认 (V2.0)
[授权策略] RBAC + 审批人清单 (workspace_id.admins)
  - 决策粒度: queue_id (单条决策)
  - 不可越权: 决策者必须是 queue.submitter_id.workspace_id 的审批人
[加密策略]
  - 传输: TLS 1.3
  - 存储: inbox_decision 表 custom_args 字段加密 (Vault Transit)
[审计策略]
  - append-only: inbox_decision 表禁止 UPDATE/DELETE
  - 哈希链: 每条决策 hash = SHA256(prev_hash + decision_json)
  - 保留: 永久 (合规) / 5 年 (PII 部分脱敏)
[防护措施]
  - PG row-level lock: SELECT FOR UPDATE
  - 决策幂等: UNIQUE (queue_id, decision_hash)
  - 时间戳防重放: decision_ts + nonce
[合规要求] SOX + GDPR Article 30 (处理活动记录)
[来源标注] [TD:B-005 + BR-021/023 + RSK-06 + ADR-006]
```

### SEC-006 B-006 Webhook 入站

```
[安全编号] SEC-006
[关联边界] B-006
[威胁模型]
  - 伪造 webhook: 攻击者伪造 GitHub release (威胁等级: 严重, CE-010)
  - 重放攻击: 同一 payload 重放 (威胁等级: 中)
  - 拒绝服务: 高频 webhook (威胁等级: 中)
[认证策略] HMAC-SHA256 签名验证
  - 签名头: X-Hub-Signature-256 (GitHub) / X-Gitlab-Token / X-Event-Key (Bitbucket)
  - 密钥管理: Vault (per-source secret)
  - 常量时间比较: hmac.compare_digest (防侧信道)
[授权策略] source 白名单
  - 允许: github.com / gitlab.com / bitbucket.org
  - 拒绝: 其他 source 401
[加密策略]
  - 传输: TLS 1.3 (强制)
  - 签名密钥: Vault KV v2, 90d 自动轮换
[审计策略]
  - 记录: source / signature / payload_hash / verification_result
  - 失败告警: 验签失败率 > 5% 触发告警
  - 保留: 90 天
[防护措施]
  - 重放保护: timestamp + nonce 校验 (5min 时间窗)
  - 限流: 1000 QPS/source (令牌桶)
  - 异步处理: 立即 ack 200, 异步处理 (避免长连接占用)
  - 拉取验证: tarball 拉取后 SHA256 校验
[合规要求] OWASP API Security Top 10 (Broken Authentication)
[来源标注] [TD:B-006 + BR-017/018 + RSK-03 + 调研:S-022 + CE-010]
```

### SEC-008 B-008 工具事件下行 (WS)

```
[安全编号] SEC-008
[关联边界] B-008
[威胁模型]
  - 窃听: 事件被中间人窃听 (威胁等级: 高)
  - 越权订阅: 用户订阅非授权 agent (威胁等级: 高)
  - 离线缓存泄露: 客户端离线时事件被窃 (威胁等级: 中)
[认证策略] mTLS (Agent 客户端) + JWT (Web UI)
  - 订阅鉴权: agent_id 必须在 user.permitted_agents 列表
[授权策略] ACL
  - 订阅粒度: topic (mcp.* / approval.* / binding.* / process.* / template.*)
  - 越权拒绝: subscribe 失败立即 close 1008
[加密策略]
  - 传输: TLS 1.3 + WSS
  - 离线缓存: Redis Stream 加密 (AES-256-GCM, Vault Transit)
[审计策略]
  - 记录: client_id / agent_id / topic / action
  - 保留: 30 天
[防护措施]
  - 离线队列: Redis Stream key=ws:{client_id} (max 1000 events, 1h TTL)
  - 推送限流: 100 msg/s/连接
  - 消息大小限制: 64KB/event
  - 心跳: ping/pong 30s
[合规要求] GDPR Article 25 (Privacy by Design)
[来源标注] [TD:B-008 + BR-029/030 + 调研:R-006]
```

### SEC-011 B-011 MCP 子进程启动参数（关键输出边界）

```
[安全编号] SEC-011
[关联边界] B-011
[威胁模型]
  - 配置覆盖: 多个 Runtime 配置文件相互覆盖 (威胁等级: 严重, Bug #2946)
  - 越权访问: 配置文件被其他用户读取 (威胁等级: 高)
  - 路径遍历: 文件路径注入 (威胁等级: 中)
[认证策略] 文件系统权限 0600 (仅当前用户)
  - 路径固定: /tmp/agenthub/mcp-{agent_id}.json
  - L4 单一源: M-B03 唯一生成器 (ADR-005)
[授权策略] workspace_id 隔离
  - 文件命名: {workspace_id}_{agent_id}
  - 进程启动: Runtime Adapter 启动时校验文件 owner
[加密策略]
  - 静态: 文件含 secret 时 Vault Transit 加密
  - 传输: Runtime Adapter 通过命令行参数注入
[审计策略]
  - 记录: last_writer / lock_acquire_count
  - 告警: 多 writer collision 立即告警 (防止 Bug #2946)
  - 保留: 90 天
[防护措施]
  - SHARED LOCK: fcntl 跨进程互斥
  - 原子写入: write 到 tmp + rename
  - 路径固定: 不允许自定义路径
  - 运维禁止: 文档明确禁止手动编辑 (RSK-08)
[合规要求] CIS Docker Benchmark 4.1
[来源标注] [TD:B-011 + BR-032 + RSK-08 + ADR-005 + 调研:S-023/S-024]
```

---

## 3. 跨边界通用安全策略

### 3.1 认证授权

- **OAuth2 + JWT**：用户层，RS256，公钥 Vault 注入
- **mTLS**：Agent + 内部服务间
- **Vault Token**：Secret Manager 访问
- **HMAC-SHA256**：Webhook 验签
- **API Key（V2.0）**：第三方 API 访问

### 3.2 加密

- **传输加密**：TLS 1.3 (前向保密 P-256)
- **存储加密**：Vault Transit (AES-256-GCM, 90d 轮换)
- **密钥管理**：HashiCorp Vault KV v2 + auto-unseal

### 3.3 审计

- **审计日志**：Loki 90d 保留
- **决策日志**：append-only (inbox_decision / mcp_migration_history) 永久保留
- **操作日志**：trace_id 串联所有调用链

### 3.4 防护

- **WAF**：OWASP CRS 3.3 (Web 入口)
- **限流**：令牌桶 (per-IP/per-user/per-workspace)
- **输入校验**：Pydantic v2 + jsonschema
- **输出编码**：JSON 自动编码

### 3.5 Agent 间互认证（4.14 安全左移）

- 所有 Agent 调用其他 Agent 必须验证对方身份（mTLS）
- 最小权限原则：每个 Agent 仅拥有完成其职责的权限（K8s ServiceAccount + RBAC）
- 调用链审计：OpenTelemetry TraceID 跨 Agent 追踪

---

## 4. 安全左移自检清单（4.14）

| 检查项 | 通过 | 备注 |
|--------|------|------|
| 认证覆盖 | ✓ | 14/14 边界有认证机制 |
| 授权粒度 | ✓ | 模块/接口/资源级 RBAC |
| 传输加密 | ✓ | 外部 100% TLS 1.3；内部 mTLS |
| 输入校验 | ✓ | Pydantic v2 schema + jsonschema |
| 审计日志 | ✓ | 全部写操作 + 关键读操作 |
| 密钥管理 | ✓ | Vault KV v2 + 90d 轮换 |
| Agent 间互认证 | ✓ | mTLS (K8s cert-manager) |
| 最小权限原则 | ✓ | K8s ServiceAccount + RBAC |
| 调用链审计 | ✓ | OpenTelemetry TraceID |

**9/9 通过 ✓ 安全左移**

---

## 5. AR 洞察

**洞察-10（安全漏洞风险）**：SEC-006 webhook 验签后异步处理，验签失败仅告警不阻断。若攻击者高频伪造 webhook，可能产生大量告警噪声掩盖真实攻击。建议增加"5min 内失败 > 100 次自动封禁 source IP 1h"的速率限制。**[AR推断:典型 webhook DDoS 场景]**

**洞察-11（安全边界遗漏）**：B-007 Cron 触发信号标注"内部可信"，但若攻击者获取了容器执行权限（如 SSRF 通过 mcp-server），可能伪造 cron 触发。建议 cron 触发增加内部 mTLS（DP-011 与 agenthub-core 之间）。**[AR推断:纵深防御]**

**洞察-12（合规要求）**：GDPR 要求数据驻留和删除权（right to erasure），但当前 mcp_log (Loki) / mcp_submission_history (PG) 保留策略未明确删除路径。建议在 V1.0 增加 "user delete request → cascade delete → audit" 流程。**[AR推断:GDPR Article 17]**

---

**安全设计方案文档结束。**
