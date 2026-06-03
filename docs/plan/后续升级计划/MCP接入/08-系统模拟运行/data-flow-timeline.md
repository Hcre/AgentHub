# 数据流时间线 — 围绕 "tool_call_response 事件" 主角

> 主角：本端到端场景中 1 条 `tool_call_response` 事件（payload 含 fetch_url 工具的 HTTP 响应）。
> 起点：MCP 用户 Alice 的 CLI 命令
> 终点：审计行、IM 端 UI、统计聚合、告警扫描、缓存层
> 对照 SA-001 DD-MCP-V1.0-20260602 数据字典（DE-008 / DE-009 / DE-005 / DE-001 / DE-014 等）。

---

## 0. 主角对象元数据

| 字段 | 值 |
|---|---|
| event_id | `ev-77f3a1b8-...` |
| call_id | `cl-0f3a1b8c-...` |
| trace_id | `tr-0f3a1b8c-...` |
| agent_id | `7c1b2d3e-...-a1` |
| binding_id | `bd-12cd...` |
| mcp_id | `mcp-3a4b5c-...` (filesystem-type MCP: `fetch_url`) |
| tool_name | `fetch_url`（14 字符 < 64 字符上限，BR:R-006） |
| args_hash | `8c4a1b2c...`（SHA256(sorted_json({"url":"https://example.com/spec","max_bytes":4096}))）|
| event_type | `request` → `response` → `progress`(N/A) |
| payload_size | 4096 bytes（base64 后 ~5462 bytes） |
| 整链路延迟 | 1.50 s（拍 1~17） |

---

## 1. 时间线（12 个时间锚点）

### 锚点 ① T+0.00 — 用户命令进入

- **对象形态**：CLI 进程内存中字符串
- **数据**：
  ```
  $ agenthub mcp run --agent-id 7c1b... --instance-id 9d8e... --tool fetch_url \
                    --args '{"url":"https://example.com/spec","max_bytes":4096}'
  ```
- **模块归属**：CLI 客户端（不在 22 模块内，但与 M-A01 对齐）
- **数据结构**：HTTP/1.1 POST `/v1/mcp/tool_call`，Content-Type: application/json
- **落盘**：`~/.agenthub/cli/req.log`（append-only，附 trace_id）

### 锚点 ② T+0.04 — 鉴权后 ctx

- **对象形态**：FastAPI Request → Depends(auth) → ctx
- **数据**：
  ```python
  ctx = {
      "user_id": "usr-alice-...",
      "ws_id": "ws-7e...",
      "roles": ["R-03"],
      "trace_id": "tr-0f3a1b8c-...",
      "request_id": "req-...",
  }
  ```
- **模块归属**：M-A01 `WebAPIGateway.dispatch`（FC-M-A01 §auth middleware）
- **数据结构**：`AuthContext` Pydantic v2 model
- **落盘**：仅在 ctx（不持久化），但 ctx 字段会写入 DE-008 / DE-009 行的 caller_id 等

### 锚点 ③ T+0.08 — 命中 binding

- **对象形态**：DE-006 行（`agent_mcp_bindings`）
- **数据**：
  ```
  binding_id=bd-12cd..., agent_id=7c1b..., instance_id=9d8e..., 
  tools_subset=["fetch_url", "read_file", ...], status=active
  ```
- **模块归属**：M-B03 `BindingEngine.list_bindings` → M-D03 Redis `bind:{agent_id}` 命中 → M-D01 PG 兜底
- **数据结构**：DE-006 字段全集（DD-MCP §DE-006）
- **落盘**：PG `agent_mcp_bindings` + Redis 缓存（5min TTL）

### 锚点 ④ T+0.12 — Allowlist 命中

- **对象形态**：DE-020 行（`mcp_inbox_allowlist`）+ Redis 缓存
- **数据**：
  ```
  user_id=usr-alice, mcp_id=mcp-3a..., tool_name=fetch_url,
  args_hash=8c4a1b2c..., approved_at=2026-05-20T..., expires_at=2026-06-19T...
  ```
- **模块归属**：M-B04 `ApprovalEngine.check_allowlist`
- **数据结构**：DE-020（DD-MCP §DE-020）unique(user, mcp, tool, args_hash)
- **落盘**：PG + Redis TTL 30d（BR:R-028）
- **副作用**：无（命中即放行）

### 锚点 ⑤ T+0.18 — WS 帧 request 事件

- **对象形态**：WebSocket 帧 JSON
- **数据**：
  ```json
  {
    "event_type": "tool_call_request",
    "call_id": "cl-0f3a1b8c-...",
    "agent_id": "7c1b...",
    "binding_id": "bd-12cd...",
    "tool": "fetch_url",
    "args": {"url":"https://example.com/spec","max_bytes":4096},
    "trace_id": "tr-0f3a1b8c-...",
    "issued_at": "2026-06-02T10:30:00.180Z"
  }
  ```
- **模块归属**：M-A02 `WSEventGateway.publish`（FC-M-A02）
- **数据结构**：DE-008 部分字段
- **落盘**：M-D01 PG `tool_call_events`（event_id=ev-77..., event_type=request, ack_at=NULL）

### 锚点 ⑥ T+0.22 — 事件总线分发

- **对象形态**：M-EV01 Redis Streams 消息
- **数据**：
  ```
  stream: mcp.tool_call.event
  payload: { event_id, call_id, type=request, ... }
  consumers: 编排 (M-B03) / 审计 (M-D02) / 告警 (M-D02/B04)
  ```
- **模块归属**：M-EV01 `EventBus.publish`
- **数据结构**：DE-008 + 自定义 envelope {retry_count, first_published_at}
- **落盘**：Redis Streams + PG DE-008
- **副作用**：3 个订阅者各自 ack 一次（ack_at 落 DE-008）

### 锚点 ⑦ T+0.28 — 进程池 LRU 命中

- **对象形态**：DE-002-ish 内存对象（ProcessPoolSlot）
- **数据**：
  ```
  runtime_type=claude_code, agent_id=7c1b..., pid=8421, state=idle→running,
  spawned_at=2026-05-30T..., last_used=2026-06-02T09:00:00Z, rss_mb=128
  ```
- **模块归属**：M-B02 `ProcessPool.get_or_spawn`
- **数据结构**：M-B02_pool_models.py: ProcessPoolSlot
- **落盘**：Redis `pool:{runtime}:slots` + PG row-lock
- **副作用**：slot.state 状态机迁移（`M-B02_pool_lifecycle.py`）

### 锚点 ⑧ T+0.40 — SandboxResult

- **对象形态**：M-C01 内存对象
- **数据**：
  ```python
  SandboxResult(
    status="success", exit_code=0,
    stdout_b64="<4096 bytes base64>",
    stderr="",
    rss_peak_mb=84, duration_ms=720,
    sandbox_backend="linux_cgroup_v2",
    killed_reason=None,
    cgroup_slice="mcp_sandbox/cl-0f3a1b8c..."
  )
  ```
- **模块归属**：M-C01 `SandboxRunner.run` → `LinuxCgroupBackend.run`（FC-M-C01 §API-200）
- **数据结构**：`SandboxResult` Pydantic v2 model
- **落盘**：仅内存（cgroup_slice 立即清理）
- **副作用**：M-C01 → 编排 → 准备 response 事件

### 锚点 ⑨ T+1.25 — WS 帧 response 事件

- **对象形态**：WebSocket 帧 JSON
- **数据**：
  ```json
  {
    "event_type": "tool_call_response",
    "call_id": "cl-0f3a1b8c-...",
    "agent_id": "7c1b...",
    "binding_id": "bd-12cd...",
    "result": {
      "status_code": 200,
      "body_b64": "PGgxPi4uLjwvaDE+...",
      "truncated": false
    },
    "duration_ms": 720,
    "trace_id": "tr-0f3a1b8c-..."
  }
  ```
- **模块归属**：M-A02 `WSEventGateway.publish`
- **数据结构**：DE-008
- **落盘**：PG DE-008（event_id=ev-78... 同一 call_id，event_type=response，ack_at=T+1.30）

### 锚点 ⑩ T+1.30 — 审计行（不可变）

- **对象形态**：DE-009 行（`tool_call_audit_log`）
- **数据**：
  ```
  log_id=au-55321..., caller_id=usr-alice, binding_id=bd-12cd...,
  mcp_id=mcp-3a..., tool_name=fetch_url, args_hash=8c4a1b2c...,
  result_code=200, duration_ms=720, trace_id=tr-0f3a1b8c...,
  event_id=ev-77f3a1b8... (unique), created_at=2026-06-02T10:30:01.300Z
  ```
- **模块归属**：M-D02 `AuditSink.write`
- **数据结构**：DE-009 字段全集（DD-MCP §DE-009，INSERT ONLY）
- **落盘**：PG `tool_call_audit_log`（GRANT INSERT, REVOKE UPDATE, DELETE）
- **副作用**：90 天热存 → S3 归档（NF-07）

### 锚点 ⑪ T+1.40 — 1h 聚合行

- **对象形态**：Redis SortedSet 成员
- **数据**：
  ```
  key: mcp:usage:{mcp_id}:1h
  member: bucket:2026-06-02T10:00 / score: 调用次数 +1, p95_latency=720, success_rate=1.0
  ```
- **模块归属**：M-D03 `Cache.update_aggregate`
- **数据结构**：DE-028-ish 聚合（实际上 PG `mcp_usage_stats` 持久化聚合行）
- **落盘**：Redis TTL 1h + PG rollup job 每 5min
- **副作用**：详情页"数据"tab 实时刷新（F-028 P95 ≤ 5min 延迟）

### 锚点 ⑫ T+1.45 — 告警扫描结果（不触发）

- **对象形态**：M-D02 内存评估
- **数据**：
  ```
  metric: error_rate_5min
  threshold: 30%
  observed: 0.0% (1/1 success)
  decision: skip
  ```
- **模块归属**：M-D02 `AlertEngine.evaluate`（DE-014 rules）
- **数据结构**：DE-015 评估结果
- **落盘**：无（未触发）
- **副作用**：无

---

## 2. 数据结构对齐表（与 SA-001 DD-MCP 数据字典）

| 锚点 | 涉及 DE 实体 | 字段数 | 是否落 PG | 是否落 Redis | 是否审计 |
|---|---|---|---|---|---|
| ① | — | — | ❌ | ❌ | ❌ |
| ② | DE-008（部分） | 5 | ❌ | ❌ | ❌ |
| ③ | DE-006 | 7 | ✅ | ✅ | ❌ |
| ④ | DE-020 | 7 | ✅ | ✅ TTL 30d | ❌ |
| ⑤ | DE-008 | 9 | ✅ | ❌ | ✅（待⑩） |
| ⑥ | DE-008 + envelope | 11 | ✅ | ✅ Streams | ✅ |
| ⑦ | M-B02 内部 | 6 | ✅（PG row-lock） | ✅ | ❌ |
| ⑧ | M-C01 内部 | 8 | ❌ | ❌ | ❌ |
| ⑨ | DE-008 | 9 | ✅ | ❌ | ✅ |
| ⑩ | DE-009 | 11 | ✅ INSERT ONLY | ❌ | ✅ 本行 |
| ⑪ | DE-028-ish | 4 | ✅ rollup | ✅ TTL 1h | ❌ |
| ⑫ | DE-014 评估 | 5 | ❌ | ❌ | ❌ |

**统计**：1 条主链调用穿过了 9 个 PG 表（DE-001/003/005/006/008/009/011/013/020/028）+ 4 类 Redis 结构（KV/Stream/PubSub/SortedSet）+ 1 条事件总线 topic。审计行 1 条（DE-009）。

---

## 3. 一致性与可追溯性

- **trace_id 贯通**：12 个锚点全部携带 `trace_id=tr-0f3a1b8c-...`，可在 Loki 日志中 grep 单次调用全链路（NF-09 100%）
- **event_id 唯一**：DE-008 用 event_id 唯一索引防重复（[反例 CE-013 修复]），DE-009 `unique(event_id)` 保证审计不双写
- **args_hash 稳定**：DE-009 args_hash = DE-020 args_hash = SHA256(sorted_json(args))（[调研 S-030]），便于 allowlist ↔ 审计对账
- **created_at 单调**：12 锚点 created_at 单调递增，T+0.00 → T+1.45（无回拨）

---

## 4. 与 SA-001 数据字典的偏差

| 锚点 | 偏差 | 是否阻塞 | 备注 |
|---|---|---|---|
| ⑦ | M-B02 slot 内存结构无独立 DE（用 DE-002-ish 自定义类） | ❌ | DD-M §M-B02 已说明为"内存池"，不进 PG（高频热数据） |
| ⑪ | 1h 聚合未在 EX/BR 覆盖 | ❌ | 已隐含在 F-028，需 V1.4 PRD 收口 |
| ⑫ | 告警评估结果无持久化 | ❌ | 仅触发时落 DE-015，skip 时不落（设计正确，避免噪声） |

**结论**：1 条主链调用完整走通 9 个 DE + 4 类 Redis + 1 个 topic；trace_id / event_id / args_hash 三个关联键在 12 个锚点间稳定贯通，零数据孤岛。
