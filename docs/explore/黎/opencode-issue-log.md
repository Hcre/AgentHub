# OpenCode 集成问题记录

## 当前状态

**Ping 测试通过，真实对话不通。**

### 已确认可以工作
- 终端直接运行 `opencode run` ✅ (2026-05-31 验证)
- `POST /api/providers/ping` opencode ✅ (3827ms)
- opencode.jsonc 配置正确 ✅
- AgentHub → OpenCodeRuntime → spawn opencode → `step_start` 事件 ✅
- `_write_provider_config` 写入正确 JSON ✅

### 不通的地方
- 通过 AgentHub 创建 OpenCode Agent → 发消息 → 无响应
- 前端显示 `⚠️` 错误

### 已修复的问题
1. `--dir` 参数触发完整 agent 流水线 → 已去掉
2. `--session` 找不到已存在 session → 已去掉（首次不用）
3. `.format()` 与 JSON 花括号冲突 → 改用 `.replace()`
4. Windows 缺少 `HOME` 环境变量 → 已补 `env["HOME"] = USERPROFILE`
5. `apiKey: "{env:DEEPSEEK_API_KEY}"` 不支持 → 改为硬编码 + 动态覆写
6. `shutil.which` 找不到 npm 全局路径 → 改用 `_resolve_binary`

### 待排查
- 为什么 E2E 测试 `adapter.stream()` 能捕获 `step_start`，但实际对话无响应
- ChatService → ContextBuilder → AgentRequest 链路是否正确传递 system_prompt
- WebSocket 事件流是否正确转发
