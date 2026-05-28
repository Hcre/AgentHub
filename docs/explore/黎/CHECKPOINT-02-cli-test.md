# CHECKPOINT 02 — CLI 安装与集成测试

测试时间: 2026-05-27
Pi 版本: 0.74.2 (npm global)

## 测试结果

### 1. Pi CLI 安装: PASS
- 安装方式: `npm install -g --ignore-scripts @earendil-works/pi-coding-agent`
- 版本: 0.74.2 (npm registry, 对应 GitHub v0.75.5)
- `pi --help` 正常，支持 `--mode rpc` / `--session` / `--provider` / `--model` 等全部所需参数

### 2. RPC 模式验证: PASS
- `pi --mode rpc --no-session` 正常启动
- JSONL 协议: stdin 接收 `{"type":"prompt",...}`, stdout 输出 `{"type":"response",...}`
- 无 API key 时返回明确错误: `"No API key found for the selected model"`

### 3. Python 集成测试: PASS

```
Factory routing:    [PASS] PI_AGENT -> PiAgentRuntime
Subprocess start:   [PASS] pi subprocess spawned
Stop safety:        [PASS] stop() no-op when idle
RPC protocol:       [PASS] stdin prompt -> stdout response (JSONL)
Error handling:     [PASS] No API key -> ERROR event
```

### 4. PiAgentRuntime 改进
- 添加 `shutil.which("pi")` 自动查找 pi 二进制（兼容 Windows + Unix）
- Fallback 路径: npm 全局 → 本地 clone → bare "pi"
- `message_update.done` 已修复为 pass（不产生 DONE，防提前终止流）

## 待验证

- [ ] 带 API key 的完整 RPC 对话（需 `ANTHROPIC_API_KEY` 环境变量）
- [ ] 多 Provider 切换（OpenAI/Google）
- [ ] 会话恢复（`--session` 跨 turn 持久化）
- [ ] 后端服务全栈运行（需 PostgreSQL + Redis 基础设施）

## 结论

Pi Agent 适配器集成已就绪，核心代码路径可工作。完整功能需要：
1. 设置 `ANTHROPIC_API_KEY` 环境变量后运行 `python tests/test_pi_agent_e2e.py`
2. 启动 AgentHub 后端服务（PG + Redis + FastAPI + 前端）进行全栈验证
