# TA-MCP-V1.0-20260602（修订版）— MCP 接入技术栈

> **版本**：V1.0-rev（2026-06-03 重写）
> **修订依据**：可行性清单 I-04（技术栈漂移：Poetry/gRPC/Vault/OTel/K8s 全非现有栈）
> **上一版**：Poetry monorepo + gRPC protobuf + Vault + OpenTelemetry + Kubernetes
> **本文档**：MCP 接入的**真实技术栈**对齐说明
> **单一权威入口**：[`../../README-REVISION.md`](../../README-REVISION.md)

---

## 0. 修订要点

| 类别 | 上一版 | **修订版** | 依据 |
|------|--------|-----------|------|
| Python 依赖管理 | Poetry + `pyproject.toml` | 现有 `requirements.txt` + `pyproject.toml`（pip） | I-04 |
| 进程间通信 | gRPC + protobuf | **沿用 HTTP/JSON + WebSocket** | I-04；AP-01~07 |
| 密钥/配置 | Vault transit | **环境变量 + 现有 `core/config.py`** | I-04 |
| 日志 | structlog | **沿用项目既有 logger** | I-04 |
| 可观测 | OpenTelemetry SDK | **trace_id 贯穿 + 既有日志** | PRD B-11 明确不做 OTel；I-07 |
| 部署 | Kubernetes（base/overlays） | **沿用 `src/docker/docker-compose.yml`** | I-04 |
| ORM | SQLAlchemy | **沿用 SQLAlchemy** | ✅ 保留 |
| 迁移 | 全新 alembic env | **续在现有 alembic 链（0006+）** | CR-03；I-10 |
| 消息总线 | 自建 eventbus | **Redis pub/sub（既有）+ WS 通道（既有）** | I-04 |
| 容器沙箱 | macos_sandbox + windows_jobobj + linux_cgroup + iptables + ipset + cgroup v2 | **单 Docker 容器 + compose 资源限额** | I-05；I-06 |
| Web 框架 | FastAPI | **沿用 FastAPI** | ✅ 保留 |
| 前端 | React + TypeScript | **沿用 React + TS + Zustand** | ✅ 保留 |

---

## 1. 真实技术栈（与现有 `src/backend/app/` 对齐）

### 1.1 后端

```
Python 3.11+
├── Web: FastAPI + Uvicorn（既有）
├── 数据: Pydantic v2（既有）
├── ORM: SQLAlchemy 2.x（既有）
├── 迁移: Alembic（既有；本期 0006+）
├── DB: PostgreSQL 15+（既有，docker compose）
├── 缓存: Redis 7+（既有）
├── 异步: asyncio（既有）
├── 日志: 项目既有 logger（沿用）
├── 配置: 环境变量 + Pydantic Settings（沿用 core/config.py）
├── 鉴权: JWT（既有，AP-04）
├── 测试: pytest + httpx + respx（既有）
├── Lint: ruff + mypy（既有）
└── 进程: 现有 AgentRuntime(ABC)（domain/llm/protocol.py）+ CLI Adapter（infrastructure/llm/{claude_code,opencode,pi_agent}_runtime）
```

### 1.2 前端

```
React 18 + TypeScript 5
├── 状态: Zustand（既有）
├── UI: 项目既有 ui 组件库（Button/Card/Tabs/Dialog/...）
├── HTTP: fetch（既有，沿用 api/ 目录）
├── 路由: react-router v6（**本期新增**）
├── 样式: Tailwind（既有）
├── 图标: lucide-react（既有）
├── 测试: 项目既有模式（manual E2E）
├── Lint: eslint（既有）
└── 类型检查: tsc strict mode（既有）
```

### 1.3 部署

```
Docker Compose（src/docker/docker-compose.yml）
├── backend（既有）
├── frontend（既有）
├── postgres（既有）
├── redis（既有）
├── mcp-sandbox（**本期新增**，单 Docker 容器 + resources.limits）
└── nginx（既有）
```

---

## 2. 删除的栈（不再使用）

| 类别 | 上一版 | 删除原因 |
|------|--------|----------|
| Poetry | 包管理 | 与现有 `requirements.txt` 冲突 |
| monorepo（`agenthub/`） | 多服务统一仓 | 不存在且与真实代码树冲突 |
| gRPC + protobuf | 进程间通信 | 现有栈只有 HTTP/JSON + WS |
| Vault | 密钥 | 现有用环境变量 + docker secrets 足够 |
| structlog | 日志 | 与项目既有 logger 冲突 |
| OpenTelemetry SDK | 可观测 | PRD B-11 明确不做 |
| Kubernetes | 部署 | 开发/演示在 Docker Desktop |
| iptables / ipset / cgroup v2 | 网络隔离 | 本机 Windows 11 跑不起来 |
| macos_sandbox / windows_jobobj / linux_cgroup | OS 沙箱 | 多 OS 沙箱矩阵不必要 |
| 自建 eventbus | 消息总线 | 既有 Redis + WS 足够 |
| Saga 模式 | 分布式事务 | 与 MCP 正交；本期不引 |

---

## 3. 本期新增依赖（pip + npm）

### 3.1 Python（`requirements.txt` 追加）

- `pydantic[email]>=2.0`（既有）
- `httpx>=0.27`（既有）
- `docker>=7.0`（**新增**，dry-run 沙箱用 Docker SDK 启停单容器）
- 其它：沿用既有

### 3.2 Node（`package.json` 追加）

- `react-router-dom@^6`（**新增**，注册 3 个新路由 + 1 个 Tab）
- 其它：沿用既有

### 3.3 不引

- ❌ OpenTelemetry / opentelemetry-*
- ❌ grpcio / protobuf
- ❌ hvac（Vault client）
- ❌ structlog
- ❌ poetry
- ❌ kubernetes client
- ❌ saga / 分布式事务库

---

## 4. 进程模型

| 进程 | 来源 | 本期 |
|------|------|------|
| backend (FastAPI) | docker compose | 既有 |
| frontend (Vite) | docker compose | 既有 |
| postgres | docker compose | 既有 |
| redis | docker compose | 既有 |
| **mcp-sandbox** | docker compose | **本期新增**：单 Docker 容器，按需启动（仅 F-021 dry-run 时），CPU=1, MEM=512MB, network=none |
| nginx | docker compose | 既有 |
| claude_code runtime | 由 backend spawn（既有） | 既有 + attach_mcp 扩展 |
| opencode runtime | 由 backend spawn（既有） | 既有 + attach_mcp 扩展 |
| pi_agent runtime | 由 backend spawn（既有） | 既有 + attach_mcp 扩展 |

> **没有独立的 MCP server 进程**。MCP server 由 Runtime 通过 stdio/sse/http 协议**调用**（不是后端常驻进程）。

---

## 5. 存储与命名

| 资源 | 命名 | 备注 |
|------|------|------|
| 库表 | `mcp_servers` / `workspace_mcp_installations` / `agent_mcp_bindings` / `mcp_tool_call_logs` | §十 + E-01 口径统一 |
| 缓存键 | `mcp:list:{workspace_id}` / `mcp:detail:{mcp_id}` / `mcp:bindings:{agent_id}` | 沿用既有 Redis 风格 |
| WS 通道 | 既有 `chat:{conversation_id}` + 既有 `toolcall:{agent_id}` | 复用 |
| trace_id | 既有格式（`trace-` + 16hex） | 不引 OTel，沿用 trace_id 字符串贯穿 |

---

## 6. 性能与 SLO（沿用 PRD §1.3）

| 指标 | 目标 | 测量 |
|------|------|------|
| S-01 详情页 LCP | ≤ 1.5s P95 | 前端性能监控 |
| S-02 工具调用端到端 | ≤ 800ms P95（stdio） | trace_id 贯穿日志 |
| S-04 上线 30 天 MCP 数 | ≥ 20（官方 ≥ 5） | 平台计数 |
| S-05 WS 投递成功率 | ≥ 99.5% | WS 心跳 |
| S-06 安装失败率 | ≤ 1% | 安装日志 |
| S-07 schema 校验覆盖率 | 100% | 单测 |

> S-03（dry-run 误报率 ≤ 2%）下期再校准（沙箱矩阵版才适用）。

---

## 7. 安全（本期最小化）

| 项 | 本期 | 下期 |
|----|------|------|
| 输入校验 | Pydantic（既有） | — |
| 鉴权 | JWT（既有） | — |
| 速率限制 | 沿用既有 | — |
| dry-run 隔离 | 单 Docker 容器 + `network: none`（E-03） | 多 OS 沙箱矩阵 |
| SSRF guard | — | NB-02 |
| DNS pinning | — | NB-02 |
| K4 扫描 | — | NB-02 |
| Vault secret | — | NB-02 |
| ACL Saga | — | NB-02 |
| OpenTelemetry | **不做**（B-11） | 维持不做 |
| 审计日志 | 异步落盘 + 90 天查询 | — |

---

## 8. 与既有代码的对齐检查

| 项 | 状态 | 备注 |
|----|------|------|
| 后端栈与 `src/backend/app/` 一致 | ✅ | FastAPI + Pydantic + SQLAlchemy + alembic |
| 前端栈与 `src/frontend/src/` 一致 | ✅ | React + TS + Zustand + Tailwind |
| 部署与 `src/docker/` 一致 | ✅ | docker compose |
| 进程模型与既有 Runtime 一致 | ✅ | 不另起运行时 |
| 日志/配置/鉴权/迁移 与既有同源 | ✅ | 全部沿用 |

---

*本 TA-MCP 是 MCP 接入**技术栈**唯一权威。所有依赖引入与此项冲突的，应回退到本文档。落地清单见 `FS-MCP-V1.0-20260602.md` §3。*
