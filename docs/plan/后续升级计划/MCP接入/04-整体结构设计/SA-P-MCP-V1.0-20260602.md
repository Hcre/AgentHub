# 系统架构图-物理视图 SA-P-MCP-V1.0-20260602

> **项目代号**：MCP
> **版本**：V1.0
> **日期**：2026-06-02
> **角色**：TD-001 顶层设计师
> **范围**：运行时组件、进程、线程、服务实例、通信协议

---

## 1. 运行时组件清单

| 组件 | 类型 | 进程模型 | 协议 | 来源 |
|------|------|---------|------|------|
| APIGateway | 服务实例(Nginx/Kong) | 多 worker | HTTPS/HTTP/WS | [TD推断:典型接入层] |
| AgentHub-Core | 服务实例(FastAPI/uvicorn) | 4-8 worker + Gunicorn | HTTP/WS | [SA:BP-001~017] |
| WS-Gateway | 服务实例(python-socketio/aiohttp) | 4 worker | WebSocket | [SA:BP-010] |
| Inbox-Notifier | 后台 worker(arq/celery) | 2-4 worker | 内部事件 | [SA:BP-020] |
| Cron-Scheduler | 守护进程(APScheduler) | 1 进程多 job | 内部事件 | [SA:BP-008/020/023/024] |
| Webhook-Listener | 服务实例(独立端口) | 1 worker | HTTPS | [SA:BP-017] |
| Runtime Adapter | 库/适配器（in-process） | per-Agent | 进程间 stdio/JSON-RPC | [SA:BP-009/010] |
| Process-Manager | 库（in-process + os.fork） | per-Core worker | 进程生命周期 | [SA:BP-002/004/005] |
| Sandbox-Executor | 库（in-process） | 临时子进程 | 进程间 stdio | [SA:BP-011] |
| K4-Analyzer | 库/独立服务（gRPC） | 池化 | gRPC | [SA:BP-015] |
| DNS-Pinning-Resolver | 库（in-process） | 共享解析器 | DNS/UDP | [SA:BP-013] |
| SSRF-Guard | 库（in-process） | — | — | [SA:BP-013/BR-010] |
| Secret-Manager-Client | 库（in-process） | — | HTTPS (Vault/KMS) | [SA:BR-014] |
| Name-Transformer | 库（in-process 纯函数） | — | — | [SA:BP-008] |
| Metrics-Exporter | sidecar (Prometheus) | 1 进程 | HTTP scrape | [SA:BR-031] |
| Log-Shipper | sidecar (Vector/Promtail) | 1 进程 | HTTP/UDP | [SA:BR-030] |
| mcp-proxy | 独立进程(sparfenyuk/mcp-proxy) | per-Runtime | Streamable HTTP+SSE | [SA:BR-034] |
| MCP Server (3 Runtime) | 独立子进程 | per-install | stdio / Streamable HTTP | [SA:BP-002] |

## 2. 进程交互时序（关键路径）

### 2.1 一键安装路径（BP-002）

```
User → APIGateway → AgentHub-Core(Worker)
  ↓
  鉴权 → 查 mcp_servers → 查 process_pool
  ↓
  Process-Manager.fork_subprocess() → mcp-proxy → MCP Server(child)
  ↓
  写 process_pool / mcp_installations
  ↓
  WS-Gateway 订阅 → 返回结果
```

### 2.2 危险工具调用路径（BP-019）

```
Agent → Runtime Adapter → AgentHub-Core(Worker)
  ↓
  SSRF-Guard (Streamable HTTP case)
  ↓
  Name-Transformer.transform(tool_name, args)
  ↓
  Allowlist check (Redis 缓存)
  ↓ 未命中
  写 inbox_queue → publish approval.requested
  ↓
  WS-Gateway → 前端 Inbox UI
  ↓
  U-04 决策 → publish approval.decided
  ↓
  Inbox-Notifier → 调用 MCP / 写入 allowlist (Redis + DB)
```

### 2.3 健康检查与回收路径（BP-005 + BP-004 + BP-023）

```
Cron-Scheduler (30s :00) → Process-Manager.healthcheck_all
  ↓
  per process: tools/list RPC with 5s timeout
  ↓
  fail_count++ → publish process.health_changed
  ↓
  WS-Gateway → 前端 (red banner)

Cron-Scheduler (30s :15/:45) → Process-Manager.idle_scan
  ↓
  SIGTERM → 5s grace → SIGKILL → 写 metrics
  ↓
  publish process.recycled
```

## 3. 关键进程数量与容量

| 资源 | 单 workspace 容量 | 全平台 (假设 100 ws) | 来源 |
|------|------------------|---------------------|------|
| MCP 进程 | 64 | 6,400 | [SA:BR-005/S-037] |
| Sandbox 临时子进程 | 短时 < 5 | < 50 (并发限制) | [SA:BR-012] |
| K4 分析 worker | pool size 8 | 8 + 弹性 | [TD推断:BP-015 性能] |
| DB 连接 | pool size 20/worker | 100~200 | [TD推断:标准配置] |
| Redis 连接 | pool size 10/worker | 50 | [TD推断] |
| mcp-proxy | per-MCP per-Runtime | 6,400 | [SA:BR-034] |
| WS 长连接 | per-UI client | 假设 500 | [TD推断] |

```
[TD洞察-4] 物理瓶颈预判：
  ① 全平台 6,400 个 MCP 子进程需 16GB/workspace 推荐 → 总计 ≥ 1.6TB 内存需求
     这是 V1.0 不可能达成单 host 部署的——必须明确"分 workspace 部署 + 共享 DB"
  ② mcp-proxy 6,400 个进程在主 host 上有 fd 上限风险 → 需 ulimit -n 提升
  ③ WS-Gateway 单实例 4 worker 难以承载 6,400 个进程的事件流 → 需多实例 + sticky session
```

---

**物理视图文档结束。**
