# 接口注释清单 API-M-B04-MCP-V1.0-20260603

> 模块 M-B04 Approval Engine 暴露的 API 接口注释清单
> 来源: [DD-001:IC-005 + IC-006 + API-130 + API-131]

---

## API-130 approval.check_and_queue

| 项 | 值 |
|----|----|
| 接口编号 | API-130 |
| 关联契约 | IC-005 |
| 实现文件 | `controllers.py::check` → `services.py::check_and_queue` |
| HTTP 方法 | POST |
| 路径 | /approvals/check |

### 函数签名注释

```python
async def check(
    body: CheckRequest,          # workspace_id/mcp_id/tool/args
    ctx: UserCtx = Depends(...)  # JWT 解析后的用户上下文
) -> CheckResponse:              # decision/queue_id/trace_id/timestamp/fail_safe
    """危险工具调用前置审批检查 (IC-005).

    Args:
        body: 检查请求。tool 长度 ≤ 64；args 序列化 ≤ 16KB。
        ctx:  当前用户上下文（M-A01 JWT 中间件注入）。

    Returns:
        CheckResponse:
            - decision=ALLOWED  → 命中 30d allowlist
            - decision=PENDING  → 入队等待 U-04 审批，含 queue_id
            - decision=DENIED   → 显式黑名单（保留扩展）
            - fail_safe=True    → PG/Redis 双不可达时的保守 pending（监控可见）

    Raises:
        ApprovalDBUnavailable: PG 不可达且无 cache 命中（503，fail-safe 仍走 pending）
        ApprovalHashMismatch:  internal hash 不一致（500，理论上不应在 check 路径出现）

    Example:
        >>> POST /approvals/check
        ... {"workspace_id":"...","mcp_id":"...","tool":"fs.write","args":{"path":"/x"}}
        ... → 200 {"decision":"pending","queue_id":"...","trace_id":"...","timestamp":"..."}
    """
```

[来源标注] [DD-001:IC-005]

---

## API-131 approval.decide

| 项 | 值 |
|----|----|
| 接口编号 | API-131 |
| 关联契约 | IC-006 |
| 实现文件 | `controllers.py::decide` → `services.py::decide` |
| HTTP 方法 | POST |
| 路径 | /approvals/{queue_id}/decide |

### 函数签名注释

```python
async def decide(
    queue_id: UUID,                  # 路径参数
    body: DecideRequest,             # decision/custom_args/decider/decision_ts/nonce
    ctx: UserCtx = Depends(...)
) -> DecideResponse:                 # decision_id/applied_at/trace_id/duplicate/original_decision_id
    """审批人对 pending 项做决策 (IC-006).

    Args:
        queue_id: inbox_queue.id
        body: 决策请求。decision ∈ {allow,deny}；decision_ts 5min 窗口；nonce 防重放。
        ctx:  审批人上下文（必须 ∈ workspace.admins）。

    Returns:
        DecideResponse:
            - duplicate=False → 新决策，decision_id 新生成
            - duplicate=True  → 幂等命中，original_decision_id 返回历史结果

    Raises:
        ApprovalNotFound:         404  queue_id 不存在
        ApprovalPermissionDenied: 403  decider 非 ws 审批人
        ApprovalDuplicate:        409  幂等命中（UNIQUE(queue_id,decision_hash) 冲突）
        ApprovalReplay:           409  decision_ts 超 5min 窗口 或 nonce 已用
        ApprovalHashMismatch:     500  inbox_queue.args_hash 与重算不符（告警 + 拒绝）
        ApprovalDBUnavailable:    503  PG 不可达
    """
```

[来源标注] [DD-001:IC-006 + SEC-005 + AR洞察-3]

---

## API-130/2 approval.query (扩展，供 408 后客户端轮询)

| 项 | 值 |
|----|----|
| 接口编号 | API-130/2 (扩展) |
| 关联契约 | IC-005 (APPROVAL_TIMEOUT 错误码场景) |
| 实现文件 | `controllers.py::query` |
| HTTP 方法 | GET |
| 路径 | /approvals/{queue_id} |

```python
async def query(queue_id: UUID, ctx: UserCtx = Depends(...)) -> QueueStatus:
    """查询 queue 当前状态（轮询）.

    Returns:
        QueueStatus: status ∈ {pending|allowed|denied|timeout}, decided_at?, decider?

    Raises:
        ApprovalNotFound: 404
    """
```

[来源标注] [DD-M-B04 推断: IC-005 408 错误码语义要求客户端轮询]

---

## 接口契约覆盖度

| 接口契约 | API 注释 | 状态 |
|---------|---------|------|
| IC-005  | API-130 + API-130/2 | ✓ 完整 |
| IC-006  | API-131 | ✓ 完整 |

**D4 = 100%（2/2 关联契约全覆盖）**
