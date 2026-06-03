# 接口技术规范 API-MCP-V1.0-20260602

> **范围**：28 个接口契约（IF-001~IF-401 全部覆盖）的技术实现规范
> **规范统一**：协议/序列化/认证/限流/版本/错误处理

---

## 1. 接口总览

| 接口编号 | 协议 | 序列化 | 关联契约 | 鉴权 | 限流 | 版本策略 | 性能要求 |
|---------|------|--------|---------|------|------|---------|---------|
| API-001 | REST/JSON | JSON UTF-8 | IF-001 (M-A01 handle) | OAuth2/JWT | 100 QPS/IP | URL /v1 | P95 ≤ 200ms |
| API-010 | WebSocket | JSON Lines | IF-010~012 (M-A02 WS) | mTLS (Agent) | 500 连接/实例 | subprotocol v1 | P95 ≤ 50ms |
| API-020 | REST/JSON | JSON UTF-8 | IF-020 (M-A03 Webhook) | HMAC-SHA256 | 1000 QPS/source | URL /v1 | P95 ≤ 100ms |
| API-030 | in-proc | n/a | IF-030 (M-A04 Cron) | 内网 | n/a | n/a | 调度粒度 1s |
| API-100 | REST/JSON | JSON UTF-8 | IF-100~103 (M-B01 Market) | OAuth2/JWT | 100 QPS | URL /v1 | P95 ≤ 200ms |
| API-110 | REST/JSON | JSON UTF-8 | IF-110~114 (M-B02 Pool) | OAuth2/JWT | 10 QPS | URL /v1 | P95 ≤ 1.2s |
| API-120 | REST/JSON | JSON UTF-8 | IF-120~123 (M-B03 Binding) | OAuth2/JWT | 50 QPS | URL /v1 | P95 ≤ 300ms |
| API-130 | REST/JSON | JSON UTF-8 | IF-130~132 (M-B04 Approval) | OAuth2/JWT (U-01/U-04) | 100 QPS | URL /v1 | P95 ≤ 200ms |
| API-140 | REST/JSON | JSON UTF-8 | IF-140~143 (M-B05 Create) | OAuth2/JWT (U-03) | 5 QPS (写) | URL /v1 | P95 ≤ 5s |
| API-200 | REST/JSON | JSON UTF-8 | IF-200 (M-C01 Sandbox) | 内部 mTLS | 5 并发 | URL /v1 | P95 ≤ 30s |
| API-210 | gRPC | Protobuf | IF-210~211 (M-C02 K4) | mTLS | 8 worker pool | proto v1 | P95 ≤ 10s |
| API-220 | REST/JSON | JSON UTF-8 | IF-220~222 (M-C03 Template) | OAuth2/JWT | 10 QPS | URL /v1 | P95 ≤ 5s |
| API-230 | in-proc | n/a | IF-230~231 (M-C04 DNS) | n/a | n/a | n/a | < 50ms |
| API-240 | REST/JSON | JSON UTF-8 | IF-240~241 (M-C05 ACL) | OAuth2/JWT (admin) | 5 QPS | URL /v1 | P95 ≤ 1s |
| API-250 | in-proc | n/a | IF-250 (M-C06 SSRF) | n/a | n/a | n/a | < 50ms |
| API-260 | Vault API | JSON | IF-260~262 (M-C07 Secret) | Vault Token | 100 QPS | Vault v1 | P95 ≤ 100ms |
| API-270 | in-proc | n/a | IF-270 (M-C08 Name) | n/a | n/a | n/a | < 1ms |
| API-280 | REST/JSON | JSON UTF-8 | IF-280 (M-C09 Migration) | OAuth2/JWT (admin) | 1 QPS | URL /v1 | P95 ≤ 30s |
| API-300 | SQL | n/a | IF-300 (M-D01 DAO) | mTLS (内部) | 200 连接池 | n/a | P95 ≤ 50ms |
| API-310 | Prom HTTP | text | IF-310~312 (M-D02) | 内网白名单 | n/a | Prom v1 | scrape 15s |
| API-320 | Redis | RESP | IF-320~321 (M-D03) | Redis AUTH | 1000 QPS | Redis 7 | P95 ≤ 5ms |
| API-400 | Redis Pub/Sub | RESP | IF-400~401 (M-EV01 Bus) | Redis AUTH | 1000 msg/s | n/a | 投递 < 50ms |

---

## 2. 关键接口详细规范

### API-130 Approval.check_and_queue

```
[接口编号] API-130
[关联接口契约] IF-130
[协议类型] REST/JSON over HTTPS
[序列化格式] JSON (UTF-8)
[认证方式] OAuth2 Bearer JWT (U-01 用户)
[限流策略] 100 QPS/workspace + 1000 QPS/global (令牌桶)
[版本策略] URL Path /api/v1/approvals/check
[兼容性矩阵]
  | 版本 | v1.0 | v1.1 | v2.0 |
  | v1.0 | -    | 向后兼容（新增 enum allowed/pending/denied） | 不兼容 |
  | v1.1 | 兼容 | -    | 不兼容（破坏：移除 allowed enum） |
  升级路径: v1.0→v1.1 自动 / v1.1→v2.0 需双写过渡期（DB schema 改造）
[错误处理]
  错误码规范:
    APPROVAL_DB_UNAVAILABLE (503) - DB 不可用，保守走 pending
    APPROVAL_HASH_MISMATCH (500) - hash 算法不一致，报警+走 pending
    APPROVAL_TIMEOUT (408) - 审批超时，客户端重试
  重试策略: 指数退避 1s/2s/4s, max 3 次, 不可重试 4xx
  降级策略: DB 不可用 → 全部 pending (deny by default fail-safe)
[性能要求] P95 ≤ 200ms（allowlist 命中）；P95 ≤ 500ms（DB 直查）
[来源标注] [TD:IF-130 + ADR-006 compute_args_hash + RSK-06]
```

### API-110 Pool.spawn

```
[接口编号] API-110
[关联接口契约] IF-110
[协议类型] REST/JSON over HTTPS（外部触发）+ in-proc asyncio（内部触发）
[序列化格式] JSON
[认证方式] OAuth2 Bearer JWT (U-01)
[限流策略] 10 QPS/workspace + 64/workspace 硬限 (BR-005)
[版本策略] URL Path /api/v1/pool/spawn
[兼容性矩阵]
  | 版本 | v1.0 | v2.0 |
  | v1.0 | -    | 不兼容（新增 reserved_slot 参数） |
  升级路径: v1.0→v2.0 需双写（先 nullable 字段，6 个月后废弃）
[错误处理]
  错误码:
    POOL_FULL (429) - 进程池满，触发 IF-113 驱逐
    POOL_SPAWN_FAILED (500) - fork 失败，报警
    POOL_RESERVED (202) - 仅预留槽位未启动，客户端轮询
  重试策略: POOL_FULL 触发自动 LRU 驱逐后重试 1 次；其他不重试
  降级策略: spawn 失败 → reserved slot + 5s 后客户端轮询
[性能要求] P95 ≤ 1.2s（含冷启动）；spawn 流程详见 PC-04
[来源标注] [TD:IF-110 + RSK-02 6,400 容量 + ADR-002 workspace 隔离]
```

### API-010 WS Event Gateway

```
[接口编号] API-010
[关联接口契约] IF-010~012
[协议类型] WebSocket (RFC 6455) over WSS (TLS 1.3)
[序列化格式] JSON Lines (一行一事件)
[认证方式] mTLS (Agent 客户端) + JWT (Web UI)
[限流策略] 500 长连接/实例 + 100 消息/秒/连接
[版本策略] subprotocol: mcp.v1（header Sec-WebSocket-Protocol）
[兼容性矩阵]
  | 协议版本 | mcp.v1 | mcp.v2 |
  | mcp.v1   | -      | 兼容（新增可选字段） |
  | mcp.v2   | 兼容    | -      |
  升级路径: mcp.v1→mcp.v2 灰度（5%→50%→100%）
[消息格式]
  客户端发送:
    {"action":"subscribe","agent_id":"...","topics":["mcp.*"]}
    {"action":"unsubscribe","topics":["mcp.rollback_done"]}
    {"action":"ping"}
  服务端推送:
    {"event_type":"mcp.running","payload":{...},"trace_id":"...","emitted_at":"..."}
[错误处理]
  错误码: 1008 (policy violation) / 1011 (server error) / 4401 (auth failed)
  重连策略: 客户端指数退避 1s/2s/4s/8s/30s (max)
  离线缓存: Redis Stream key=ws:{client_id} (max 1000 events, 1h TTL)
[性能要求] P95 ≤ 50ms 推送延迟；mcp.* 事件 50ms 内投递
[来源标注] [TD:IF-010~012 + R-006 stdio 200ms / HTTP 500ms 分级]
```

### API-210 K4 Analyze (gRPC)

```
[接口编号] API-210
[关联接口契约] IF-210~211
[协议类型] gRPC over HTTP/2
[序列化格式] Protobuf 3
[认证方式] mTLS (内部服务间)
[限流策略] 8 worker pool + 队列 100 (背压返回 RESOURCE_EXHAUSTED)
[版本策略] proto package v1
[Proto 定义]
  syntax = "proto3";
  package agenthub.k4.v1;
  service K4Analyzer {
    rpc Analyze(AnalyzeRequest) returns (AnalyzeResponse);
    rpc Calibrate(CalibrateRequest) returns (CalibrateResponse);
  }
  message AnalyzeRequest { bytes manifest_json = 1; string rule_set_version = 2; string trace_id = 3; }
  message AnalyzeResponse { int32 score = 1; repeated string tags = 2; string rule_set_version = 3; }
[兼容性矩阵]
  | proto 版本 | v1 | v2 |
  | v1         | -  | 兼容（新增可选字段） |
  升级路径: v1→v2 通过 reserved 字段保护
[错误处理]
  gRPC codes: UNAVAILABLE (queue full) / DEADLINE_EXCEEDED (>10s) / INVALID_ARGUMENT
  重试策略: UNAVAILABLE 指数退避 1s/2s/4s max 3；DEADLINE_EXCEEDED 不重试
  降级策略: gRPC 不可用 → 同步本地降级分析（in-memory 规则集）
[性能要求] P95 ≤ 10s/MCP（200 样本校准时延分布）
[来源标注] [TD:IF-210 + 调研:R-008 K4 误判率校准]
```

### API-230 DNS Pinning Resolve

```
[接口编号] API-230
[关联接口契约] IF-230~231
[协议类型] in-proc (Python function call)
[序列化格式] n/a
[认证方式] n/a
[限流策略] n/a（无状态）
[版本策略] 函数签名稳定，破坏性变更需 deprecation 周期
[函数签名]
  def resolve(url: yarl.URL) -> str:  # 返回 pinned_ip
  def recheck_redirect(from_pin: str, to_url: yarl.URL) -> bool
[兼容性矩阵] 函数级版本，semver
[错误处理]
  异常: DNSResolveError, BlacklistIPError
  失败处理: 抛异常由调用方（M-B05）处理
[性能要求] < 50ms（含 Redis 缓存查询，命中率 > 90%）
[来源标注] [TD:IF-230 + ADR-004 5 层防御 + RSK-04 跨对象 Pinning]
```

### API-260 Secret Manager

```
[接口编号] API-260
[关联接口契约] IF-260~262
[协议类型] HTTPS REST to Vault
[序列化格式] JSON
[认证方式] Vault Token (启动时获取 root token → 短期 dynamic token)
[限流策略] 100 QPS/服务
[版本策略] Vault KV v2 engine path
[请求示例]
  PUT /v1/secret/data/agenthub/{name}
  Headers: X-Vault-Token: {dynamic_token}
  Body: {"data": {"value": "..."}}
[兼容性矩阵] Vault API v1，policy 版本控制
[错误处理]
  Vault 错误码: 403 (permission denied) / 503 (sealed) / 429 (rate limit)
  重试: 5xx 指数退避 1s/2s/4s max 3；4xx 不重试
  降级: Vault sealed → 启动失败 fail-fast
[性能要求] P95 ≤ 100ms
[来源标注] [TD:IF-260 + BR-014 + TDR-010 Transit 自动轮换 90d]
```

---

## 3. 通用规范

### 3.1 错误响应格式（统一）

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

### 3.2 兼容性策略

- **URL 版本**：所有 REST API 走 URL Path 版本（`/api/v1/...`），保留 2 个主版本
- **WS 协议版本**：通过 `Sec-WebSocket-Protocol: mcp.v1` 协商
- **gRPC proto 版本**：通过 `package agenthub.X.v1` 命名空间
- **DB schema 版本**：通过 Alembic 迁移文件，强制双写过渡期 6 个月

### 3.3 限流策略

| 维度 | 限流 |
|------|------|
| 用户级 | 100 QPS/IP（GET）/ 10 QPS/IP（写） |
| Workspace 级 | 1000 QPS 总和 |
| 关键 API | API-130 100 QPS/ws；API-110 10 QPS/ws；API-140 5 QPS (写) |
| Agent 内部 | mTLS 互信，无限流 |
| 内部服务间 | mTLS 互信，按需限流 |

### 3.4 性能要求总览（来源 [TD:PC]）

| 接口 | P95 性能要求 |
|------|------------|
| API-001 网关入口 | ≤ 200ms |
| API-110 Pool.spawn | ≤ 1.2s（含冷启动） |
| API-130 Approval.check | ≤ 200ms（allowlist 命中） |
| API-140 MCPServer.submit | ≤ 5s |
| API-200 Sandbox.run | ≤ 30s |
| API-210 K4.analyze | ≤ 10s |
| API-220 Template.upgrade | ≤ 5s (webhook 端到端) |
| API-230 DNS.resolve | ≤ 50ms |
| API-250 SSRF.check | ≤ 50ms |
| API-260 Secret.get | ≤ 100ms |

---

**接口技术规范文档结束。**
