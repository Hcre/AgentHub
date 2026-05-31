# CLI 自动扫描 + Provider 解析 + OpenCode 集成 + Step 2 重设计

> 日期: 2026-05-31 | 耗时: ~10h | 分支: feature/domain2/agent-workspace → main

## 做了什么

### 1. CLI 自动扫描 (PATH Scan)
- `provider_scanner.py`: 借鉴 Multica `exec.LookPath` + Open Design PATH 扫描，自动检测 pi/claude/opencode 等 6 个 CLI
- `_resolve_binary()`: Windows npm 全局目录 fallback
- `POST /api/providers` + `POST /api/providers/scan`: 扫描端点
- `POST /api/providers/ping`: 连通性预检端点，spawn CLI 发消息验证配置

### 2. Provider × CLI 配置矩阵
- `cliProviderMatrix.ts`: 前端查表，4 Provider × 3 CLI = 12 种组合
- ProviderKeyResolver 设计: 一套 key 通吃三种 CLI
- PiAgentRuntime provider 映射修正 (deepseek → deepseek, 不是 anthropic)

### 3. Step 2 重设计
- CLI 选择 → 自动扫描下拉 (不再是硬编码 RUNTIMES)
- 选保存配置 → 自动推导 base_url/协议/模型
- 工作目录输入 + WorkspaceBrowser 文件浏览
- 连通性预检放入 Step 3，创建前自动执行
- 进度指示 2/3

### 4. OpenCode 集成 (v1.15)
- `opencode_runtime.py`: 子进程适配器，`opencode run --format json --pure`
- 多轮对话: `--session` 首次自动捕获 sessionID
- Key 注入: 每次 spawn 前动态覆写 `~/.config/opencode/opencode.jsonc`
- `_write_provider_config()`: 写入 opencode 配置文件
- opencode.jsonc: DeepSeek provider + `@ai-sdk/openai-compatible`

### 5. Bug 修复 (9 个)
| # | 问题 | 修复 |
|---|------|------|
| 1 | opencode 静默卡死 | stdin=DEVNULL |
| 2 | opencode 找不到配置 | HOME 环境变量 |
| 3 | .format() KeyError | 改用 .replace() |
| 4 | --dir 触发 agent 流水线卡死 | 去掉 --dir，用 cwd |
| 5 | --session 报 Session not found | 首次不用 session |
| 6 | npm 全局路径找不到 | _resolve_binary fallback |
| 7 | PiAgentRuntime base_url env var 错误 | provider-aware 映射 |
| 8 | AgentResponse 丢 settings | from_domain 补字段 |
| 9 | Step 2 wsBrowserOpen 残留 | reset() 补重置 |

### 6. 其他
- API Key 管理简化 (仅 provider + key)
- 工作目录 end-to-end 管线 (Step2 → Agent → Session → Runtime)
- ChatView session 创建时自动加载 workspace_path
- 合并到 main (f9ad8a5)

## 关键决策

1. **OpenCode 配置注入方式**: 每次 spawn 前覆写 opencode.jsonc，不依赖 `{env:XXX}` (opencode 自定义 provider 不支持)
2. **多轮对话**: 用 opencode 原生 `--session` 而非传历史消息，保留 CLI 自带上下文管理
3. **默认模型**: deepseek-v4-flash (比 pro 快 2s，成本 ~$0.00005/次)
4. **Pi 身份**: agent_name 注入 system_prompt 前缀 (`你的名字是{name}。`)
5. **base_url 管理**: 每个 CLI 自己管，AgentHub 不硬编码端点
6. **OpenCode 仍未完全调通**: 待验证 stdin=DEVNULL 修复效果

## 待办

- [ ] 验证 OpenCode Agent 真实对话（不在 ping，在 WebSocket）
- [ ] OpenCode 自定义 provider 稳定性测试
- [ ] MiMo/MiniMax/Anthropic provider 真 key 测试
- [ ] WorkspaceBrowser ChatView 去重（两处实现）
- [ ] `_session_map` 过期清理机制
