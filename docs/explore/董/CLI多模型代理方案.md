# CLI 多模型代理方案

> 版本：v1.1 | 日期：2026-05-23 | 分支：feature/domain2/cli-custom-model
> 参考：cc-haha-multi-model-analysis.md
> v1.1: proxy 注册改为 FastAPI DI + lifespan；Runtime api_key 参数清理；风险表补充

---

## 一、问题定义

Claude Code CLI 启动子进程时，`ANTHROPIC_BASE_URL` 默认指向 `https://api.anthropic.com`，只能调用 Anthropic 官方模型。需要让 CLI 能使用 DeepSeek、GPT、Qwen、Kimi 等第三方模型。

### 约束

- **不改 CLI 源码**。CLI 是 Anthropic 的二进制/npm 包，不能也不该改。
- **不丢失 CLI 能力**。工具执行、会话管理、权限控制、Skills/MCP 等 CLI Harness 功能必须完整保留。
- **每 Agent 独立配置**。不同 Agent 可使用不同 Provider、不同模型。

---

## 二、方案：内置代理（统一路径）

### 2.1 为什么不直连

即使 DeepSeek/Kimi/GLM 提供了 Anthropic 兼容端点，也不应该让 CLI 直连。原因两条：

**鉴权机制不兼容**。CLI 只认 `ANTHROPIC_API_KEY`，会把它作为 `x-api-key` header 发送。但第三方 Anthropic 兼容端点的鉴权方式不统一：

| Provider | 鉴权 header | CLI 直连可行？ |
|----------|------------|--------------|
| Anthropic 官方 | `x-api-key: sk-ant-xxx` | 是 |
| DeepSeek | Bearer Token / 自定义 | **未知，待验证** |
| Kimi | Bearer Token / 自定义 | **未知，待验证** |
| 智谱 GLM | Bearer Token / 自定义 | **未知，待验证** |

直连假设 CLI 和 Provider 之间的 auth 协议天然匹配——这个前提不可靠。

**扩展性**。如果未来要接 GPT/Qwen（OpenAI Chat 格式），直连根本不可能，必须走代理+协议转换。与其维护两条 code path，不如一开始就统一过代理。

### 2.2 核心思路

```
Claude Code CLI (子进程)
    │  ANTHROPIC_BASE_URL = http://127.0.0.1:8000/proxy/agents/{agent_id}
    │  ANTHROPIC_API_KEY = "agenthub-proxy"  (占位)
    │  ANTHROPIC_MODEL = "deepseek-v4-pro"
    ▼
AgentHub Proxy (/proxy/agents/{agent_id}/v1/messages)
    │  1. 从路径提取 agent_id → 查数据库获取 Agent 配置
    │  2. 解密 agent.api_key_encrypted → 真实 API Key
    │  3. 鉴权适配：按 Provider 类型选择正确的 auth header
    │     - Anthropic 兼容 → x-api-key: {real_key}
    │     - OpenAI 兼容  → Authorization: Bearer {real_key}（需协议转换）
    │  4. 拼接 agent.base_url + request.path_suffix → 目标 URL
    │  5. 流式转发请求和响应
    ▼
第三方 API
```

**代理做三件事**：鉴权适配、URL 路由、流式转发。三者都是字节级操作，不解析请求/响应体。

对于 Anthropic 兼容的 Provider，代理是透明反向代理——请求体和响应体原样传递，只替换 auth header。对于 OpenAI Chat 格式的 Provider，协议转换模块后续按需叠加。

### 2.3 与 cc-haha 对比

| 维度 | cc-haha | AgentHub |
|------|---------|----------|
| 代理位置 | 独立 Bun 进程 | FastAPI 进程内，无需额外服务 |
| Agent 识别 | `ANTHROPIC_AUTH_TOKEN` 映射 providerId | URL 路径 `{agent_id}`，无需自定义 header |
| 鉴权适配 | 代理内部映射 | 代理内部适配（统一入口） |
| 协议转换 | 内置 Anthropic ↔ OpenAI | pass-through 优先，转换按需叠加 |
| Provider 管理 | 桌面端本地 providers.json | 数据库 Agent 表（`base_url` + `api_key_encrypted` 现成字段） |
| 会话隔离 | runtimeOverrides Map | 每 Agent 独立 CLI 子进程 |
| 模型槽位 | haiku/sonnet/opus 四槽位 | 单一 `model` 字段（可后续扩展） |

---

## 三、核心架构

### 3.1 组件关系

```
┌──────────────────────────────────────────────────────────┐
│  L3 ChatService                                          │
│  调用 build_adapter_for_agent(agent)                     │
│  → ClaudeCodeRuntime.stream(request)                     │
└───────────────────────────┬──────────────────────────────┘
                            │ 启动子进程
                            ▼
┌──────────────────────────────────────────────────────────┐
│  L1 ClaudeCodeRuntime (修改：_build_env 指向代理)         │
│                                                          │
│  ANTHROPIC_BASE_URL  = {proxy_base}/agents/{agent_id}    │
│  ANTHROPIC_API_KEY   = "agenthub-proxy"                  │
│  ANTHROPIC_MODEL     = agent.model                       │
│                                                          │
│  _build_cmd / _run_cli / _parse_line: 不变               │
└───────────────────────────┬──────────────────────────────┘
                            │ HTTP POST /proxy/agents/{id}/v1/messages
                            ▼
┌──────────────────────────────────────────────────────────┐
│  L4 ProxyRouter (新增)                                   │
│                                                          │
│  request → parse agent_id                                │
│       → agent_repo.get_by_id() → Agent 配置              │
│       → decrypt(api_key) → 真实 key                      │
│       → 鉴权适配（选择正确的 auth header）                │
│       → 拼接 target_url                                  │
│       → httpx 流式转发                                    │
│       → StreamingResponse 原样返回                        │
└───────────────────────────┬──────────────────────────────┘
                            │ 真实 auth header + 原样 body
                            ▼
┌──────────────────────────────────────────────────────────┐
│  第三方 API                                              │
│  DeepSeek: https://api.deepseek.com/anthropic            │
│  Kimi:     https://api.moonshot.cn/anthropic             │
│  智谱:     https://open.bigmodel.cn/api/anthropic        │
│  Ollama:   http://localhost:11434/v1                     │
│  GPT/Qwen: 需协议转换（后续）                              │
└──────────────────────────────────────────────────────────┘
```

### 3.2 请求数据流

```
1. 用户发送消息 → ChatService 选择 Agent → ClaudeCodeRuntime.stream()
2. Runtime 启动 `claude` CLI 子进程，env 中 ANTHROPIC_BASE_URL 指向本地代理
3. CLI 向 http://127.0.0.1:8000/proxy/agents/{agent_id}/v1/messages 发请求
4. ProxyRouter:
   a. 路径提取 agent_id
   b. 查数据库获取 Agent
   c. 解密 api_key_encrypted
   d. 鉴权适配：根据 Provider 类型选择 auth header
   e. 拼接目标 URL（agent.base_url + 剥离代理前缀后的 path）
   f. httpx 流式转发
5. 第三方 API 返回响应 → Proxy 流式透明回传给 CLI
6. CLI 解析响应 → 执行工具调用 → 产出 stream-json 事件
7. Runtime 解析 stdout → StreamEvent → ChatService
```

### 3.3 鉴权适配策略

代理的核心职责之一：解耦 CLI 的 auth 方式与 Provider 的 auth 方式。

```
CLI 请求
  headers: { "x-api-key": "agenthub-proxy" }   ← 占位
                    ↓
ProxyHandler
  real_key = decrypt(agent.api_key_encrypted)
  if provider 是 Anthropic 兼容:
      → headers["x-api-key"] = real_key         ← 替换占位
  if provider 是 OpenAI 兼容:
      → headers["authorization"] = f"Bearer {real_key}"  ← 换 auth 方式（需协议转换）
                    ↓
第三方 API
  x-api-key: sk-real-key 或 Authorization: Bearer sk-real-key
```

当前阶段所有 Provider 使用 `x-api-key` 直通。OpenAI 兼容 Provider 的 Bearer token 适配与协议转换同时实现。

---

## 四、详细设计

### 4.1 代理端点 `api/routers/proxy.py`

```python
# 新增文件: backend/app/api/routers/proxy.py

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.infrastructure.llm.proxy.handler import ProxyHandler
from app.infrastructure.repositories import PostgresAgentRepository

router = APIRouter(prefix="/proxy", tags=["proxy"])


@router.api_route(
    "/agents/{agent_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
async def proxy_request(
    agent_id: str,
    path: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    client: httpx.AsyncClient = request.app.state.client
    handler = ProxyHandler(PostgresAgentRepository(db))
    return await handler.handle(agent_id, path, request, client)
```

- `{path:path}` 通配捕获所有子路径（`v1/messages` 及其他端点）
- 复用项目已有的 `get_db` 依赖注入，不引入全局变量
- httpx client 从 `app.state.client` 获取（lifespan 管理生命周期）
- ProxyHandler 无状态，每次请求创建成本可忽略

### 4.2 ProxyHandler `infrastructure/llm/proxy/handler.py`

```python
import httpx
from fastapi import Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from app.core.security import decrypt_secret

_HOP_BY_HOP_HEADERS = {
    "host", "connection", "transfer-encoding", "te", "trailer",
    "upgrade", "proxy-authorization", "proxy-authenticate",
}


class ProxyHandler:
    """无状态处理器，client 由 lifespan 注入，每次请求由路由层传入。"""

    def __init__(self, agent_repo):
        self._agent_repo = agent_repo

    async def handle(
        self, agent_id: str, path: str, request: Request, client: httpx.AsyncClient
    ) -> Response:
        # 1. 查 Agent
        agent = await self._agent_repo.get_by_id(agent_id)
        if not agent:
            return JSONResponse({"error": "agent not found"}, status_code=404)

        # 2. 解密 API Key
        real_key = decrypt_secret(agent.api_key_encrypted)
        if not real_key:
            return JSONResponse({"error": "agent has no api_key"}, status_code=400)

        # 3. 拼接目标 URL
        target_url = f"{agent.base_url.rstrip('/')}/{path}"

        # 4. 构建转发 headers
        forward_headers = {}
        for name, value in request.headers.items():
            if name.lower() not in _HOP_BY_HOP_HEADERS:
                forward_headers[name] = value
        forward_headers["x-api-key"] = real_key

        # 5. 流式转发（复用 lifespan 管理的连接池）
        body = await request.body()
        upstream = await client.send(
            client.build_request(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                content=body,
            ),
            stream=True,
        )

        response_headers = {
            k: v for k, v in upstream.headers.items()
            if k.lower() not in _HOP_BY_HOP_HEADERS
        }
        return StreamingResponse(
            upstream.aiter_raw(),
            status_code=upstream.status_code,
            headers=response_headers,
        )
```

**要点**：
- `aiter_raw()` 字节级透明转发，不解析请求/响应体
- 过滤 hop-by-hop headers
- `client` 由路由层从 `request.app.state.client` 获取后传入，复用连接池，lifespan 负责生命周期
- 不依赖 `api_format` 字段——当前阶段统一 `x-api-key` 鉴权

### 4.3 Runtime 修改 `claude_code_runtime.py`

**唯一改动**——`_build_env()` 指向本地代理而非 `agent.base_url`：

```python
# === 修改后：_build_env 始终走代理 ===
def _build_env(self) -> dict[str, str]:
    env = os.environ.copy()
    env["ANTHROPIC_API_KEY"] = "agenthub-proxy"  # 占位，真实 key 由代理注入
    if self._model:
        env["ANTHROPIC_MODEL"] = self._model
    env["ANTHROPIC_BASE_URL"] = self._proxy_url   # http://127.0.0.1:8000/proxy/agents/{id}
    return env
```

`__init__` 新增 `agent_id`、`proxy_base`。`api_key`/`base_url` **保留**（供未来直接模式切换），但 `_build_env` 不再使用：

```python
def __init__(
    self,
    *,
    model: str = "",
    agent_id: str = "",       # 新增：构造代理 URL
    proxy_base: str = "",     # 新增：代理前缀
    permission_mode: str = _DEFAULT_PERMISSION_MODE,
    max_turns: int = _DEFAULT_MAX_TURNS,
    timeout: int = _DEFAULT_TIMEOUT,
) -> None:
    self._model = model
    self._proxy_url = f"{proxy_base.rstrip('/')}/agents/{agent_id}" if agent_id else ""
    self._permission_mode = permission_mode
    self._max_turns = max_turns
    self._timeout = timeout
    self._process: asyncio.subprocess.Process | None = None
```

**移除** `api_key` 和 `base_url` 构造参数——代理模式下它们是死代码。Factory 也不再传递这两个值给 Runtime。如果未来需要支持直连/代理双模式，通过 `proxy_base` 为空判断即可。

### 4.4 Factory 修改 `factory.py`

```python
if system == AgentSystem.CLAUDE_CODE:
    from app.infrastructure.llm.claude_code_runtime import ClaudeCodeRuntime

    s = agent.settings or {}

    return ClaudeCodeRuntime(
        model=agent.model,
        agent_id=str(agent.id),
        proxy_base=settings.proxy_base_url,
        permission_mode=s.get("permission_mode", "acceptEdits"),
        max_turns=s.get("max_turns", 10),
        timeout=s.get("cli_timeout", settings.claude_cli_timeout),
    )
```

- 不再传 `api_key`、`base_url`——代理模式下 Runtime 不直接使用这两个值
- 全局 `build_adapter()` 中 `claude_cli` 分支同样更新

### 4.5 配置新增 `config.py`

```python
# 新增一行
proxy_base_url: str = "http://127.0.0.1:8000"
```

### 4.6 启动注册 `main.py`

```python
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api.routers import proxy


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：创建复用的 httpx 连接池
    client = httpx.AsyncClient(timeout=300.0)
    app.state.client = client
    yield
    # 关闭：释放连接池
    await client.aclose()


app = FastAPI(lifespan=lifespan, ...)
app.include_router(proxy.router)
```

- httpx client 生命周期与 app 绑定，正确释放资源
- proxy router 通过 `request.app.state.client` 获取客户端
- 无需额外的 `init_proxy()` 或全局变量

### 4.7 Agent 实体与数据库

**无需变更**。现有字段已满足需求：

| 字段 | 用途 | 示例 |
|------|------|------|
| `id` | 构造代理 URL `{proxy}/agents/{id}` | uuid |
| `model` | 设置 `ANTHROPIC_MODEL` | `deepseek-v4-pro` |
| `base_url` | 代理转发的目标 API 地址 | `https://api.deepseek.com/anthropic` |
| `api_key_encrypted` | 代理解密后注入 auth header | `sk-xxxxx` |

### 4.8 改动文件清单

```
新增 (3):
  backend/app/api/routers/proxy.py
  backend/app/infrastructure/llm/proxy/__init__.py
  backend/app/infrastructure/llm/proxy/handler.py

修改 (4):
  backend/app/infrastructure/llm/claude_code_runtime.py  (_build_env + __init__ 清理死代码)
  backend/app/infrastructure/llm/factory.py              (传入 agent_id, proxy_base)
  backend/app/core/config.py                             (+proxy_base_url)
  backend/app/main.py                                    (lifespan + app.include_router)
```

**总改动量约 130 行（含新增文件）。**

---

## 五、后续扩展：协议转换

当需要接入 GPT、Qwen 等不提供 Anthropic 兼容端点的 Provider 时，在 proxy 模块下叠加协议转换层。

### 5.1 Agent 扩展

agent.settings JSON 新增 `api_format` 字段：

```json
{
  "api_format": "anthropic",
  "model_slots": {
    "haiku": null,
    "sonnet": "deepseek-v4-pro",
    "opus": null
  }
}
```

- `"anthropic"`（默认）→ pass-through，不改请求/响应体
- `"openai_chat"` → 请求/响应做 Anthropic ↔ OpenAI 格式转换

### 5.2 新增模块结构

```
infrastructure/llm/proxy/
├── __init__.py
├── handler.py                    # 修改：根据 api_format 分流
├── transform/
│   ├── __init__.py
│   ├── anthropic_to_openai.py    # 请求转换: Anthropic Messages → OpenAI Chat
│   └── openai_to_anthropic.py    # 响应转换: OpenAI Chat SSE → Anthropic SSE
└── streaming/
    ├── __init__.py
    └── openai_stream.py          # 逐 chunk 解析 → Anthropic content_block 事件
```

### 5.3 ProxyHandler 分流逻辑

```python
async def handle(self, agent_id: str, path: str, request: Request) -> Response:
    agent = await self._agent_repo.get_by_id(agent_id)
    real_key = decrypt_secret(agent.api_key_encrypted)
    api_format = (agent.settings or {}).get("api_format", "anthropic")

    if api_format == "openai_chat":
        return await self._proxy_openai(agent, real_key, request)
    else:
        return await self._proxy_pass_through(agent, real_key, path, request)
```

### 5.4 当前不实现的原因

- 覆盖的 Provider 极少（只有 GPT 和 Qwen）
- Anthropic SSE（`content_block_start/delta/stop`）与 OpenAI SSE（`choices[0].delta`）的事件结构差异大，转换层的测试矩阵复杂
- ROI 低：DeepSeek/Kimi/GLM 的 Anthropic 兼容端点已覆盖主流需求

---

## 六、实施计划

### Phase 0：前置

- [ ] `config.py` 新增 `proxy_base_url`
- [ ] 创建 `infrastructure/llm/proxy/__init__.py`

### Phase 1：核心链路

- [ ] 创建 `infrastructure/llm/proxy/handler.py`
- [ ] 创建 `api/routers/proxy.py`
- [ ] 修改 `claude_code_runtime.py`（`__init__` + `_build_env`）
- [ ] 修改 `factory.py`（CLAUDE_CODE 分支）
- [ ] 在 `main.py` 注册 proxy router + init_proxy

### Phase 2：验证

- [ ] 创建 DeepSeek Agent（`base_url=https://api.deepseek.com/anthropic`, `model=deepseek-v4-pro`）
- [ ] 启动 AgentHub，发送消息，端到端验证代理转发链路
- [ ] 验证流式响应完整性（逐 chunk 确认没有截断）
- [ ] 验证错误场景：Agent 不存在 → 404、API Key 无效 → 上游错误透传、上游超时 → 502

### Phase 3（后续）：协议转换

- [ ] 选一个 OpenAI Chat 格式的 Provider 作为目标（建议 GPT-4o-mini，成本低）
- [ ] 实现 req/res SSE 转换模块
- [ ] Agent settings 新增 `api_format` 字段
- [ ] ProxyHandler 分流

---

## 七、风险与对策

| 风险 | 对策 |
|------|------|
| **代理是单点故障** — 代理进程挂掉，所有 CLI 调用中断 | 有意的设计取舍（统一路径换简单性）。代理运行在 FastAPI 进程内，与后端同生命周期。后端健康检查天然覆盖代理。 |
| **安全边界依赖 localhost** — `agenthub-proxy` 占位 key 不提供真实认证 | 代理绑 127.0.0.1，只有本机可达。生产环境通过反向代理（Nginx/Caddy）对外暴露时，`/proxy/` 路径不加入反向代理配置，确保外部不可达。 |
| 第三方 Provider 鉴权用 Bearer Token 而非 `x-api-key` | ProxyHandler 增加 auth header 选择逻辑，agent.settings 可选 `auth_header` 配置 |
| CLI 请求 `/v1/messages` 以外的端点 | `{path:path}` 通配捕获，原样转发 |
| 代理增加一跳延迟 | 同进程内 localhost 通信，延迟 <1ms |
| 生产环境 proxy 需要对外可达 | Docker Compose 内 `backend` hostname 即可；外部部署用反向代理域名 |
| 某些 Provider 的 Anthropic 实现不完整 | 代理不解析请求体，兼容性由 Provider 自身负责 |
