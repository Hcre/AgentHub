# 系统边界定义 BD-MCP-V1.0-20260602

> **项目代号**：MCP
> **版本**：V1.0
> **日期**：2026-06-02
> **角色**：TD-001 顶层设计师
> **范围**：14 条系统边界（输入 7 + 输出 4 + 不处理 3）

---

## 1. 输入边界

### B-001 MCP 市场查询请求

```
[边界编号] B-001
[边界类型] 输入边界
[边界描述] 用户（U-01/U-02）通过 Web 前端查询 MCP 市场；REST GET 请求携带 category/q/page 参数
[关联模块] M-A01 → M-B01
[数据格式] HTTPS REST + JSON: {category: string, q: string, page: int}
[安全要求] TLS 1.3 + 鉴权（U-01/U-02）+ 限流 100 QPS/IP
[来源标注] [SA:BP-001]
```

### B-002 MCP 安装请求

```
[边界编号] B-002
[边界类型] 输入边界
[边界描述] 用户（U-01）在 MCP 详情页点击"安装到当前 workspace"；POST 请求携带 mcp_id/ws_id
[关联模块] M-A01 → M-B01 → M-B02
[数据格式] HTTPS REST + JSON: {mcp_id: UUID, workspace_id: UUID}
[安全要求] 鉴权（U-01 是 ws_id 管理员）+ WS gateway 二次确认
[来源标注] [SA:BP-002 + BR-005]
```

### B-003 MCP 提交请求

```
[边界编号] B-003
[边界类型] 输入边界
[边界描述] 创作者（U-03）通过"创建 MCP"表单提交；含 stdio/Streamable HTTP 两种类型
[关联模块] M-A01 → M-B05
[数据格式] HTTPS REST + multipart (含 secret 标记) / JSON (HTTP 类型)
[安全要求] 鉴权（U-03 创作者角色）+ 字段级 secret 标记 + CI detect-secrets 兜底
[来源标注] [SA:BP-012/013 + BR-014]
```

### B-004 工具调用请求

```
[边界编号] B-004
[边界类型] 输入边界
[边界描述] Agent（U-01 间接触发）调用 MCP 工具；通过 Runtime Adapter → AgentHub 内部 API
[关联模块] M-A01 → M-B04 (审批) → M-B05
[数据格式] 内部 JSON-RPC 2.0 + mcp.* 命名空间（[SA:AP-01~07]）
[安全要求] trace_id 全链路 + SSRF-Guard (Streamable HTTP) + allowlist 命中优先
[来源标注] [SA:BP-019/021 + BR-021/029]
```

### B-005 审批决策提交

```
[边界编号] B-005
[边界类型] 输入边界
[边界描述] 审批人（U-04）通过 Inbox 提交 4 选项决策（通过本次/永久通过/拒绝/自定义）
[关联模块] M-A01 → M-B04
[数据格式] HTTPS REST + JSON: {queue_id, decision, custom_args?}
[安全要求] 鉴权（U-04 workspace 审批人）+ decision 不可篡改（append-only）
[来源标注] [SA:BP-019 + BR-023]
```

### B-006 Webhook 入站

```
[边界编号] B-006
[边界类型] 输入边界
[边界描述] GitHub/GitLab/Bitbucket 推送 release 事件至 /webhook/{source}/release
[关联模块] M-A03 → M-C03 → M-C07
[数据格式] HTTPS + JSON payload + X-Hub-Signature-256 (GitHub) / X-Gitlab-Token / 等
[安全要求] HMAC-SHA256 验签 + hmac.compare_digest（常量时间）+ 失败率超阈值报警
[来源标注] [SA:BP-017 + BR-017/018 + CE-010]
```

### B-007 Cron 触发信号

```
[边界编号] B-007
[边界类型] 输入边界
[边界描述] APScheduler 内部触发器，无外部输入；周期 30s（健康/扫描）/ 60s（DNS pinning 清理）/ 5min（allowlist 过期）
[关联模块] M-A04 → M-B02/M-B04/M-C04/M-C09
[数据格式] 内部事件
[安全要求] 内部可信；不暴露外部触发入口
[来源标注] [SA:BP-004/005/020/023/024 + DE-018 TTL + DE-029 过期]
```

## 2. 输出边界

### B-008 工具事件下行（WS）

```
[边界编号] B-008
[边界类型] 输出边界
[边界描述] 工具调用/结果事件经 WS 网关推送到前端订阅客户端；事件 schema 遵循 mcp.* 命名空间
[关联模块] M-A02 → 前端
[数据格式] WebSocket + JSON Lines: {event_type, payload, trace_id, emitted_at}
[安全要求] TLS 1.3 + 订阅鉴权（agent_id 权限）+ 离线队列加密 (Redis at-rest)
[来源标注] [SA:BP-010 + BR-029/030 + EX-018/019]
```

### B-009 Prometheus 指标

```
[边界编号] B-009
[边界类型] 输出边界
[边界描述] 8 个 Prometheus 指标通过 /metrics 端点暴露给 Prom server
[关联模块] M-D02 → Prometheus server
[数据格式] Prometheus text format: metric_name{label=value} value timestamp
[安全要求] 仅内网访问；8 个 label 集白名单（runtime ∈ {claude_code, opencode, pi_agent}）防基数爆炸
[来源标注] [SA:BR-031 + CE-017]
```

### B-010 Inbox 通知（IM）

```
[边界编号] B-010
[边界类型] 输出边界
[边界描述] 软提醒（10min 触发）通过 IM（Slack/Teams/钉钉）通知 U-04
[关联模块] M-B04 → 外部 IM
[数据格式] IM Webhook JSON: {text, mentions, actions}
[安全要求] IM Webhook 鉴权 + 失败邮件兜底
[来源标注] [SA:BP-020 + EX-036]
```

### B-011 MCP 子进程启动参数

```
[边界编号] B-011
[边界类型] 输出边界
[边界描述] mcp-config 文件写入 /tmp/agenthub/mcp-{agent_id}.json 后，Runtime Adapter 启动子进程注入 --mcp-config={path}
[关联模块] M-B03 → Runtime Adapter → MCP Server 子进程
[数据格式] 文件 + 命令行参数
[安全要求] 文件权限 0600（仅当前用户）+ 路径固定 + L4 单一源防覆盖
[来源标注] [SA:BP-009 + BR-032 + EX-016/017 + CE-012]
```

## 3. 不处理边界

### B-012 不处理：第三方 MCP 协议扩展

```
[边界编号] B-012
[边界类型] 不处理边界
[边界描述] 仅支持 MCP 标准协议（tools/list, tools/call 等）；不处理第三方私有扩展协议
[关联模块] — (架构层显式声明)
[数据格式] — 
[安全要求] — 
[来源标注] [SA:BP-005 + EX-011 协议不兼容时 unhealthy 标记]
```

### B-013 不处理：跨 workspace 共享进程池

```
[边界编号] B-013
[边界类型] 不处理边界
[边界描述] 进程池严格按 workspace 隔离；不提供跨 workspace 共享/借调机制
[关联模块] M-B02
[数据格式] —
[安全要求] 物理隔离 + workspace_id 是强制隔离键
[来源标注] [SA:BR-005 64/workspace + DE-004.workspace_id FK]
```

### B-014 不处理：MCP Server 自升级

```
[边界编号] B-014
[边界类型] 不处理边界
[边界描述] MCP Server 进程内的自动升级机制不在 AgentHub 职责内；AgentHub 仅管理外部版本回滚
[关联模块] M-B05 (BP-016)
[数据格式] —
[安全要求] —
[来源标注] [SA:BP-016 范围限定 + CE-015 5s 宽限]
```

---

**系统边界定义文档结束。**
