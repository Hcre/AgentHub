# OpenCode 集成问题记录

## 当前状态 (2026-05-31)

**仍未完全调通。** 已修复 7 个 bug，push 到 main。待验证。

### 已修复 (7ad2abc → f9ad8a5)

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 1 | opencode 静默卡死 | `create_subprocess_exec` 没设 `stdin=DEVNULL`，继承父进程 stdin 等待输入 | 加 `stdin=asyncio.subprocess.DEVNULL` |
| 2 | opencode 找不到配置 | Windows 无 `HOME` 环境变量，opencode Unix 风格读 `$HOME/.config` | `env["HOME"] = USERPROFILE` |
| 3 | `.format()` KeyError | Python `.format()` 与 opencode.jsonc 的 `{` 冲突 | 改用 `.replace("{api_key}", key)` |
| 4 | `--dir` 触发 agent 流水线卡死 | opencode 带 `--dir` 进入完整 coding agent 模式，分析项目卡住 | 去掉 `--dir`，用 cwd 替代 |
| 5 | `--session` 报 Session not found | 首次调用就带 `--session`，session 还没创建 | 首次不加，从 stdout 捕获 sessionID 后复用 |
| 6 | npm 全局路径找不到 | `shutil.which` 在 Windows 不查 npm 全局目录 | 改用 `_resolve_binary`(Windows fallback) |
| 7 | base_url env var 名错误 | PiAgentRuntime 对 deepseek 设了 `ANTHROPIC_BASE_URL` | 改为 provider-aware: anthropic→ANTHROPIC_BASE_URL, 其他→OPENAI_BASE_URL |
| 8 | AgentResponse 丢 settings | `from_domain()` 漏了 `settings` 字段 | 添加 `settings=a.settings` |
| 9 | Step 2 关闭按钮无响应 | `reset()` 未重置 `wsBrowserOpen`，残留 Portal 遮罩 | 添加 `setWsBrowserOpen(false)` |

### 验证矩阵

| 项目 | 状态 |
|------|:---:|
| 终端 `opencode run "你好"` | ✅ |
| `POST /api/providers/ping` (opencode) | ✅ 3827ms |
| opencode.jsonc 动态覆写 | ✅ |
| AgentHub WebSocket 对话 | ❌ 待验证 |

### 架构决策

- **OpenCode 多轮对话**: 首次 spawn 无 `--session`，从 stdout 捕获 sessionID，后续复用
- **Key 注入**: 每次 spawn 前 `_write_provider_config()` 覆写 `~/.config/opencode/opencode.jsonc`
- **模型**: 默认 `deepseek/deepseek-v4-flash`，`--pure` 跳过项目分析
