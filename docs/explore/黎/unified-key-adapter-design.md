# 统一 Key 适配器设计

> 借鉴 [Open Design](https://github.com/nexu-io/open-design) 的 `RuntimeAgentDef.env` + BYOK proxy 和 [Multica](https://github.com/multica-ai/multica) 的 `Backend.Execute(ctx, prompt, opts)` 接口模式。

## 核心发现

Open Design 和 Multica 都**不在适配器层管理 key**。Key 通过环境变量注入，每个 CLI 读自己的标准 env var。适配器只管 spawn + parse，不管 key 格式。

```
Open Design:  RuntimeAgentDef.env: Record<string, string>  → spawn 时注入
Multica:     Config.Env: []string                           → exec.Command 时注入
```

## 问题定义

三种 CLI 对同一把 DeepSeek key 的接收方式完全不同：

| CLI | Key 传递方式 | 需要额外处理 |
|-----|------------|------------|
| **Claude CLI** | `ANTHROPIC_BASE_URL=proxy` + `ANTHROPIC_API_KEY=placeholder` | 走 AgentHub proxy 透传 |
| **Pi CLI** | `DEEPSEEK_API_KEY` env var | 无，pi CLI 内置 deepseek provider |
| **OpenCode** | `{env:DEEPSEEK_API_KEY}` in opencode.jsonc | 需要预写配置文件 |

## 设计方案：三层解耦

```
┌──────────────────────────────────────────────────────────────────┐
│                    AgentHub API Key Store                         │
│  { provider: "deepseek", api_key: "sk-xxx", model: "..." }      │
└──────────────────────────┬───────────────────────────────────────┘
                           │ 取 key
┌──────────────────────────▼───────────────────────────────────────┐
│                  ProviderKeyResolver (新增)                       │
│  输入: provider=deepseek, api_key=sk-xxx                         │
│  输出: { env: {"DEEPSEEK_API_KEY":"sk-xxx"},                     │
│          cli_args: ["--provider","deepseek"],                     │
│          config_files: None }                                     │
└──────────────────────────┬───────────────────────────────────────┘
                           │ 传给 CLI Adapter
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │ ClaudeCode   │  │ PiAgent      │  │ OpenCode     │
  │ Runtime      │  │ Runtime      │  │ Runtime      │
  │              │  │              │  │              │
  │ proxy 透传   │  │ CLI 原生     │  │ jsonc 配置   │
  │              │  │ provider     │  │ + env var    │
  └──────────────┘  └──────────────┘  └──────────────┘
```

### 第一层：AgentHub Key Store（已有）

用户在 AgentHub 前端存一份 key → 加密存储在 DB → 创建 Agent 时选择。

### 第二层：ProviderKeyResolver（新增）

```python
@dataclass
class ProviderEnv:
    """单个 CLI 需要的环境变量和配置"""
    env: dict[str, str]           # 环境变量
    cli_args: list[str]           # 附加 CLI 参数
    config_files: dict[str, str]  # 需要写入的配置文件 {路径: 内容}

@dataclass
class ProviderKeyResolver:
    """根据 provider 和 key，生成各个 CLI 需要的配置"""

    provider: str       # "deepseek" | "anthropic" | "openai"
    api_key: str        # 原始 API key
    proxy_base: str     # AgentHub proxy 地址（给 claude_code 用）
    agent_id: str

    def for_claude(self) -> ProviderEnv:
        """Claude CLI 走 proxy"""
        return ProviderEnv(
            env={
                "ANTHROPIC_BASE_URL": f"{self.proxy_base}/proxy/agents/{self.agent_id}",
            },
            cli_args=[],
            config_files={},
        )

    def for_pi(self) -> ProviderEnv:
        """Pi CLI 原生 provider → 用 provider 对应的 env var"""
        env_key = _PI_ENV_MAP[self.provider]  # deepseek → DEEPSEEK_API_KEY
        pi_provider = _PI_PROVIDER_MAP[self.provider]  # deepseek → deepseek
        return ProviderEnv(
            env={env_key: self.api_key},
            cli_args=["--provider", pi_provider],
            config_files={},
        )

    def for_opencode(self) -> ProviderEnv:
        """OpenCode 需要 env var + 预写 ~/.config/opencode/opencode.jsonc"""
        env_key = _OPENCODE_ENV_MAP[self.provider]
        return ProviderEnv(
            env={env_key: self.api_key},
            cli_args=[],
            config_files=self._build_opencode_config(),
        )
```

### 第三层：CLI Adapter（已有，改造）

每个 Runtime 的 `__init__` 接收 `ProviderEnv` 而不是分别接收 `api_key`, `base_url`, `proxy_base`：

```python
class PiAgentRuntime(AgentRuntime):
    def __init__(self, *, model: str, agent_id: str, provider_env: ProviderEnv, ...):
        self._env = provider_env.env
        self._extra_args = provider_env.cli_args
        # 不再需要 _PROVIDER_MAP, _PROVIDER_ENV_KEY 等硬编码

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update(self._env)
        return env
```

## 和 Open Design / Multica 的对照

| 概念 | Open Design | Multica | AgentHub 新设计 |
|------|------------|---------|---------------|
| **Key 存储** | `.od/media-config.json` (BYOK) | 用户自己的 CLI auth | AgentHub Key Store (加密 DB) |
| **Key 传递** | `RuntimeAgentDef.env` | `Config.Env` | `ProviderKeyResolver` → `ProviderEnv` |
| **适配器接口** | `buildArgs(prompt, images, dirs, options)` | `Backend.Execute(ctx, prompt, opts)` | `AgentRuntime.stream(request)` + `ProviderEnv` |
| **新增 CLI** | 1 个 `XXXAgentDef` + 1 个 parser | 1 个 Go 文件 | 1 个 Runtime 文件 + 1 行 resolver 注册 |
| **兜底方案** | BYOK proxy `/api/proxy/{provider}/stream` | — | `_build_api_fallback` → ClaudeAdapter |

## 实施计划

### Phase 1: ProviderKeyResolver

创建 `backend/app/infrastructure/llm/provider_key.py`：

```python
# provider → 各 CLI 的环境变量名
PI_ENV_MAP = {"deepseek": "DEEPSEEK_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
PI_PROVIDER_MAP = {"deepseek": "deepseek", "anthropic": "anthropic", "openai": "openai"}
OPENCODE_ENV_MAP = {"deepseek": "DEEPSEEK_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
```

### Phase 2: 改造三个 Runtime

- `ClaudeCodeRuntime.__init__` → 接收 `ProviderEnv` 替代 `proxy_base`
- `PiAgentRuntime.__init__` → 接收 `ProviderEnv` 替代 `provider/api_key/base_url`
- `OpenCodeRuntime.__init__` → 接收 `ProviderEnv` 替代 `provider/api_key`

### Phase 3: 统一 factory

```python
def build_adapter_for_agent(agent: Agent) -> UnifiedAgent:
    resolver = ProviderKeyResolver(
        provider=str(agent.provider.value),
        api_key=decrypt_secret(agent.api_key_encrypted),
        proxy_base=settings.proxy_base_url,
        agent_id=str(agent.id),
    )
    
    if system == AgentSystem.CLAUDE_CODE:
        return ClaudeCodeRuntime(model=agent.model, provider_env=resolver.for_claude())
    if system == AgentSystem.PI_AGENT:
        return PiAgentRuntime(model=agent.model, provider_env=resolver.for_pi())
    if system == AgentSystem.OPENCODE:
        return OpenCodeRuntime(model=agent.model, provider_env=resolver.for_opencode())
```

### Phase 4: 新增 CLI 的成本

只需要：
1. 在 `ProviderKeyResolver` 加一个 `for_xxx()` 方法
2. 写一个 `XxxRuntime` adapter
3. 在 factory 加一行路由

**不需要改 key store、前端、DB、或任何其他模块。**
