# 多 Agent 自动接入方案

> 借鉴 [Open Design](https://github.com/nexu-io/open-design) 和 [Multica](https://github.com/multica-ai/multica) 的设计模式，解决 AgentHub 当前手动创建 Agent、耦合运行时选择的问题。

---

## 当前问题

AgentHub 现在的 Agent 创建流程：

```
前端 CreateAgentModal
  Step 1: 选模板 + 名称 + system_prompt + skills
  Step 2: 选运行依赖 (claude_code / pi_agent / mock)
          + Provider 配置（provider, model, api_key, base_url）
  Step 3: 创建 → POST /api/agents
```

**三个耦合点：**

1. **创建 Agent 必须理解运行时实现** — 用户需要知道 `claude_code`（子进程）和 `pi_agent`（HTTP API）的区别
2. **每个 Agent 绑定死一个 adapter** — `agent_system` 字段写死在 DB，换运行时要重建 Agent
3. **新增 Agent 类型要改多处** — `factory.py` 加分支、前端加选项、DB 加枚举

---

## 两个参考项目的核心模式

### Open Design：PATH 扫描 + 适配器多路复用

```
┌──────────────────────────────────────────────────┐
│                  Local Daemon                     │
│                                                   │
│  PATH-scan (16 CLIs):                             │
│    claude, codex, gemini, cursor-agent,           │
│    copilot, qwen, opencode, devin,                │
│    hermes, kimi, kiro-cli, pi, ...                │
│                                                   │
│  Adapter per CLI:                                 │
│    claude-stream-json    → Claude Code            │
│    json-event-stream     → Codex/Gemini/OpenCode  │
│    acp-json-rpc          → Devin/Hermes/Kimi      │
│    pi-rpc                → Pi                     │
│    plain                 → Qwen/DeepSeek          │
│                                                   │
│  BYOK proxy (无 CLI 时的兜底):                     │
│    /api/proxy/{anthropic,openai,...}/stream       │
│    → 用户只需提供 baseUrl + apiKey + model         │
└──────────────────────────────────────────────────┘
```

**关键设计决策：**
- **检测不做安装** — daemon 只发现已有 CLI，不安装不配置
- **每个 CLI 一个 adapter** — 只处理 transport + 事件流解析
- **统一输出格式** — 所有 adapter 输出归一化到相同的 chat stream
- **无 CLI 时退化为 API 代理** — 同一个 pipeline，只是跳过 spawn

### Multica：Runtime 抽象 + Backend 接口

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│  Next.js UI  │ ←→  │  Go Server      │ ←→  │  Local Daemon│
│  (管理层)     │     │  (路由/调度层)    │     │  (执行层)     │
└──────────────┘     └─────────────────┘     └──────────────┘
                            │                        │
                      PostgreSQL              exec.Command
                      (任务状态机)              (agent CLI)
```

**核心抽象 — Backend 接口（`server/pkg/agent/agent.go`）：**

```go
type Backend interface {
    Execute(ctx context.Context, prompt string, opts ExecOptions) (*Session, error)
}

type Session struct {
    Messages <-chan Message   // 流式输出
    Result   <-chan Result    // 最终结果
}
```

**11 个实现**，每个是一个 Go 文件：
`claude.go`, `codex.go` (33KB 最复杂), `cursor.go`, `gemini.go`, `copilot.go`, `opencode.go`, `openclaw.go`, `hermes.go`, `pi.go`, `kimi.go`, `kiro.go`

**关键设计决策：**
- **新增 Agent = 一个 Go 文件** — 不需要改协议、DB 迁移、UI
- **控制面不执行** — Multica 是控制面，委托给第三方 CLI
- **vendor-neutral** — 用户保留自己的 API key 和订阅
- **崩溃安全** — `PinTaskSession()` 中途持久化 session_id，崩溃后可恢复
- **DB 级任务抢占** — `FOR UPDATE SKIP LOCKED` 避免多 daemon 抢同一任务

### 两个项目的共性模式

| 模式 | Open Design | Multica |
|------|------------|---------|
| **检测方式** | PATH 扫描 16 个 CLI | `exec.LookPath` 探测已知二进制 |
| **适配器** | 每个 CLI 一个 stream parser | 每个 CLI 一个 `Backend` 实现 |
| **运行时抽象** | Daemon 管理 spawn | Runtime 注册到 workspace |
| **Provider 管理** | `.od/media-config.json` (BYOK) | 用户自己的 CLI 认证 |
| **兜底方案** | BYOK API proxy | — |
| **新增 Agent 成本** | 1 个 adapter 文件 | 1 个 Go 文件 |

---

## 方案设计：AgentHub 多 Agent 自动接入

### 目标架构

```
当前:
  Create Agent → 手动选择 agent_system → 手动填 provider/key/model → 创建

目标:
  启动 AgentHub → 自动扫描可用 Provider → 管理 key 即可 → 一键创建 Agent
```

### 核心改动：引入 Provider 层

```
                    ┌──────────────┐
                    │    Agent     │  ← 身份层：name, system_prompt, skills
                    │  (profile)   │
                    └──────┬───────┘
                           │ 引用 (agent.provider_id)
                    ┌──────▼───────┐
                    │   Provider   │  ← 执行层：CLI 工具 + 认证配置
                    │  (execution) │
                    └──────┬───────┘
                           │ 自动检测
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        Claude Code    codex CLI    Gemini CLI   ...
        (自动发现)      (自动发现)     (自动发现)
```

**Agent 只管"我是谁"（身份），Provider 只管"怎么跑"（执行）。**

### 数据模型变更

```python
# 新模型：Provider（自动检测 + 用户配置）
class Provider(Base):
    __tablename__ = "providers"
    id: UUID
    name: str              # "claude_code", "codex", "gemini", ...
    display_name: str      # "Claude Code", "OpenAI Codex CLI", ...
    type: ProviderType     # "cli" | "api_proxy"
    executable_path: str   # 自动检测到的二进制路径
    version: str           # --version 检测到的版本
    status: str            # "available" | "unavailable" | "configured"
    config: JSON           # {"api_key": "...", "base_url": "...", "model": "..."}
    detected_at: datetime
    last_health_check: datetime

# Agent 简化 — 移除 agent_system，改为引用 Provider
class Agent(Base):
    __tablename__ = "agents"
    id: UUID
    name: str
    system_prompt: str
    skills: list[Skill]
    provider_id: FK[Provider]   # ← 改为引用 Provider
    model_override: str | None  # ← 可选覆盖 model
    # 不再有 agent_system 字段
```

### 1. Provider Scanner（借鉴 Multica 的 config.go + Open Design 的 PATH 扫描）

```python
# provider_scanner.py

KNOWN_CLIS: list[ProviderDef] = [
    ProviderDef(
        name="claude_code",
        display_name="Claude Code",
        binary="claude",
        adapter="claude_code_runtime",      # 对应现有 ClaudeCodeRuntime
        input_format="stream-json",          # 借鉴 Open Design 的协议声明
        version_flag="--version",
        min_version=None,
    ),
    ProviderDef(
        name="codex",
        display_name="OpenAI Codex CLI",
        binary="codex",
        adapter="codex_runtime",             # 新增 adapter
        input_format="json-rpc",             # Codex 用 JSON-RPC 2.0（借鉴 Multica）
        version_flag="--version",
        min_version="0.16.0",
    ),
    ProviderDef(
        name="gemini",
        display_name="Google Gemini CLI",
        binary="gemini",
        adapter="gemini_runtime",
        input_format="json-event-stream",
        version_flag="--version",
    ),
    ProviderDef(
        name="cursor_agent",
        display_name="Cursor Agent",
        binary="cursor-agent",
        adapter="cursor_runtime",
        input_format="json-event-stream",
        version_flag="--version",
    ),
    ProviderDef(
        name="pi_agent",
        display_name="Pi Agent",
        binary="pi",
        adapter="pi_adapter",                # 对应现有 ClaudeAdapter
        input_format="pi-rpc",
        version_flag="--version",
        env_overrides={                      # 借鉴 Multica 的 MULTICA_<PROVIDER>_PATH
            "ANTHROPIC_BASE_URL": "PI_BASE_URL",
            "ANTHROPIC_API_KEY": "PI_API_KEY",
        },
    ),
    # ... 更多 CLI
]


async def scan_providers(db: AsyncSession) -> list[Provider]:
    """启动时扫描 PATH，自动发现可用 CLI。

    借鉴 Multica:
    - exec.LookPath 探测已知二进制
    - DetectVersion() 版本检查
    - CheckMinVersion() 版本门控

    借鉴 Open Design:
    - 只检测不安装
    - 检测到的 CLI 自动成为候选
    """
    discovered = []
    for defn in KNOWN_CLIS:
        path = shutil.which(defn.binary)
        if not path:
            continue

        version = await detect_version(path, defn.version_flag)
        if not check_min_version(version, defn.min_version):
            logger.warning(f"{defn.name} version {version} < {defn.min_version}")
            continue

        provider = await upsert_provider(
            db, defn,
            executable_path=path,
            version=version,
            status="available",
        )
        discovered.append(provider)

    return discovered
```

### 2. Adapter 注册表（借鉴 Multica 的 Backend 接口 + Open Design 的 per-CLI adapter）

```python
# adapter_registry.py

from typing import Protocol


class AgentAdapter(Protocol):
    """统一 Backend 接口 — 借鉴 Multica 的 Backend interface"""

    async def execute(
        self,
        prompt: str,
        workspace: Path,
        config: ProviderConfig,  # api_key, base_url, model
    ) -> AsyncIterator[AgentMessage]:
        ...


# 注册表 — 新增 Agent 只需注册一个 adapter
ADAPTER_REGISTRY: dict[str, AgentAdapter] = {
    "claude_code": ClaudeCodeRuntime(),    # 现有，子进程 spawn
    "codex": CodexRuntime(),               # 新增：spawn codex + JSON-RPC parser
    "pi_agent": ClaudeAdapter(),           # 现有，HTTP API
    "gemini": GeminiRuntime(),             # 新增：spawn gemini + event stream parser
    "cursor": CursorRuntime(),             # 新增
    "api_proxy": BYOKProxyAdapter(),       # 兜底：直接 HTTP API（借鉴 Open Design BYOK）
}


def get_adapter(provider_type: str) -> AgentAdapter:
    return ADAPTER_REGISTRY[provider_type]
```

**新增 Agent 类型的成本降到：1 个 adapter 文件 + 1 行注册。**

### 3. 启动时的完整流程

```
AgentHub 启动
  │
  ├─1. ProviderScanner.scan_providers()
  │     ├─ shutil.which("claude")     → /usr/bin/claude  ✓
  │     ├─ shutil.which("codex")      → /usr/bin/codex   ✓
  │     ├─ shutil.which("gemini")     → None             ✗
  │     ├─ shutil.which("cursor-agent") → None           ✗
  │     └─ shutil.which("pi")         → /usr/local/bin/pi ✓
  │
  ├─2. DB upsert → providers 表同步
  │     providers:
  │       ├─ id=1, name="claude_code", status="available"
  │       ├─ id=2, name="codex",       status="available"
  │       └─ id=3, name="pi_agent",    status="available"
  │
  ├─3. 健康检查（定期，借鉴 Multica heartbeatLoop 15s）
  │     ├─ 检查 CLI 是否仍可用
  │     ├─ 更新 last_health_check
  │     └─ 标记不可用的为 "unavailable"
  │
  └─4. API 暴露：GET /api/providers
        → 前端自动展示可用 Provider 列表
```

### 4. 简化后的 Agent 创建流程

```
前端 CreateAgentModal（改进后）:
  Step 1: 选模板 + 名称 + system_prompt + skills
  Step 2: 选 Provider（从 GET /api/providers 自动获取列表，不再是手动填 agent_system）
          → 展示：Claude Code ✓ / Codex ✓ / Pi ✓（灰色：Gemini 未安装）
  Step 3: 配置 Provider 的 API Key（如需要）
          → Provider 级别的 key，可被多个 Agent 共享
  Step 4: 创建 → POST /api/agents {provider_id, name, system_prompt, skills}
```

**用户不再需要理解 `claude_code` vs `pi_agent` vs `mock` 的区别，只需要从自动检测到的可用 Provider 中选择。**

### 5. Key 管理解耦（借鉴 Open Design 的 `.od/media-config.json`）

```python
# provider_key_store.py

# 借鉴 Open Design: 配置文件存储，gitignored
# 借鉴 Multica: vendor-neutral，用户保留自己的 key

class ProviderKeyStore:
    """Provider 级别的 key 管理，多个 Agent 共享"""

    def __init__(self, storage_path: Path):
        self.path = storage_path  # 如 .agenthub/provider-keys.json (gitignored)

    def set_key(self, provider_id: str, api_key: str, base_url: str | None = None):
        ...

    def get_config(self, provider_id: str) -> ProviderConfig:
        ...

    def list_configured(self) -> list[ProviderSummary]:
        """返回已配置 key 的 Provider 列表，供 Agent 选择"""
        ...
```

**一个 Provider 配一次 key，多个 Agent 共用。** 不再每个 Agent 单独填 key。

### 6. API 设计

```
GET    /api/providers              → 列出所有自动检测到的 Provider
POST   /api/providers/scan         → 手动触发重新扫描
PUT    /api/providers/{id}/config  → 配置 Provider 的 api_key/base_url
GET    /api/providers/{id}/health  → Provider 健康检查

POST   /api/agents                 → 创建 Agent（body 含 provider_id，不再含 agent_system）
GET    /api/agents                 → 列出 Agent（含 provider 信息）
PUT    /api/agents/{id}/provider   → 更换 Agent 的 Provider
```

---

## 实施路线

### Phase 1：Provider 基础设施（最小可行）

1. 创建 `providers` 表
2. 实现 `ProviderScanner`（PATH 扫描 `claude` 和 `pi` 两个已知 CLI）
3. 暴露 `GET /api/providers`
4. 前端展示自动检测结果

### Phase 2：解耦 Agent → Provider

1. Agent 表加 `provider_id` 外键（保留 `agent_system` 兼容）
2. 创建 Agent 时使用 `provider_id` 而非 `agent_system`
3. `factory.py` 改为查 `ADAPTER_REGISTRY[provider.type]`

### Phase 3：扩展 Provider 种类

1. 新增 Codex、Gemini、Cursor 的 Provider 定义
2. 实现对应的 adapter（参考 Multica 各 CLI 的 `exec.Command` + stream parser 模式）
3. 加入版本门控（`--version` 检测 + `min_version` 检查）

### Phase 4：Key 管理独立

1. Provider 级别的 key store（`.agenthub/provider-keys.json`）
2. Agent 创建时自动引用 Provider 的 key
3. Key 轮换、过期检测

---

## 关键设计原则（来自两个参考项目）

| 原则 | 来源 | 实践 |
|------|------|------|
| **只检测不安装** | Open Design, Multica | Provider 只发现已有 CLI，不尝试安装 |
| **一个 adapter 一个文件** | Multica | 新增 Agent 类型 = 1 个 Python 文件 + 1 行注册 |
| **控制面与执行面分离** | Multica | AgentHub 是控制面，CLI 是执行面 |
| **KEY 与 Agent 解耦** | Open Design | Provider 级别配 key，Agent 级别选 Provider |
| **兜底 API 代理** | Open Design | 无 CLI 时退化为直接 HTTP API 调用 |
| **版本门控** | Multica | 阻止过旧的 CLI 注册 |
| **崩溃安全** | Multica | 借鉴 PinTaskSession 中途持久化思路 |
| **vendor-neutral** | Multica | 用户保留自己的 API key 和订阅 |

---

## 与现有代码的对接点

| 现有模块 | 改动 |
|----------|------|
| `factory.py` | 从 `agent_system` switch 改为 `ADAPTER_REGISTRY[provider.type]` 查表 |
| `ClaudeCodeRuntime` | 注册为 `claude_code` adapter，增加 stream parser 抽象 |
| `ClaudeAdapter` | 注册为 `pi_agent` adapter，同时作为 BYOK proxy 的兜底 |
| `MockAdapter` | 注册为 `mock` adapter（测试用，不参与自动检测） |
| `CreateAgentModal` | Step 2 改为自动展示 `GET /api/providers` 结果 |
| `apiKeyStore` (前端) | 改为 Provider 级别的 key 管理 |
| DB migration | 新增 `providers` 表，Agent 表加 `provider_id` |
