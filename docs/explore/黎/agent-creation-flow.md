# Agent 创建与路由机制

## Agent 类型与适配器

创建 Agent 时选择 `agent_system`，后端 `factory.py` 根据类型路由到不同适配器：

| agent_system | 适配器 | 原理 | 文件访问 | 适用场景 |
|-------------|--------|------|:---:|------|
| `claude_code` | ClaudeCodeRuntime | `create_subprocess_exec("claude", cwd=workspace)` | ✅ | 需要读写本地文件 |
| `pi_agent` | ClaudeAdapter | Anthropic SDK → HTTP POST `base_url/v1/messages` | ❌ | 纯文本对话、DeepSeek |
| `mock` | MockAdapter | 本地假回复 | ❌ | 测试/演示 |

## 创建流程

```
前端 CreateAgentModal
  Step 1: 选模板 + 名称 + system_prompt + skills
  Step 2: 选运行依赖 (claude_code / pi_agent / mock)
          + Provider 配置（从 apiKeyStore 选或手动填）
          → provider, model, api_key, base_url
  Step 3: 创建 → POST /api/agents → 连通性测试(WS ping)
```

## pi_agent 为什么用 ClaudeAdapter 而不是 Pi CLI

| 方式 | 结果 |
|------|------|
| Pi CLI 子进程 | ❌ 401 — `create_subprocess_exec` 在 Windows 下 env var 传递有问题 |
| Pi CLI 手动测试 | ✅ 能用 — `ANTHROPIC_BASE_URL=... pi --mode rpc` |
| ClaudeAdapter | ✅ 能用 — 直接 HTTP，不经过子进程 |

结论：Windows 下 `asyncio.create_subprocess_exec` 传给子进程的环境变量不可靠。API 模式（ClaudeAdapter）绕过了这个问题。

## claude_code 为什么能工作

`ClaudeCodeRuntime` 也用 `create_subprocess_exec`，但：
1. 用 `shutil.which("claude")` 找完整路径
2. `--permission-mode bypassPermissions` 跳过权限弹窗
3. `cwd=workspace` 让 Agent 锁定在工作目录
4. `ANTHROPIC_BASE_URL` 指向 AgentHub proxy → proxy 过滤 system 消息 → 转发 DeepSeek

## 当前配置要点

| 配置项 | 值 | 说明 |
|--------|-----|------|
| 数据库 | Docker PG (`localhost:5432`) | 或 SQLite(`agenthub.db`) |
| Redis | Docker Redis (`localhost:6379`) | 或 fakeredis（内存模拟） |
| 后端端口 | 9001 | 8000 被 Docker 端口转发占用 |
| 前端端口 | 5173 | Vite dev server |
| 前端代理 | `/api` → `localhost:9001` | vite.config.ts |

## 已知问题

1. **SQLite UUID 损坏** — `Uuid` 类型在 SQLite 下存读不一致，用 PostgreSQL 规避
2. **端口 8000 冲突** — Docker Desktop 端口转发占用，改 9001
3. **启动脚本端口耦合** — `start.bat` 和 `vite.config.ts` 都硬编码端口，换环境要改多处
4. **pi_agent 无文件系统** — ClaudeAdapter 是纯 API 调用，无法读写文件
