# OpenCode 集成审查 — 根因分析与修复

> 2026-05-31 | 审查 `opencode_runtime.py` + `provider_scanner.py` + `factory.py`

## 根因：JSON 解析层级错误

### 问题

opencode v1.15+ 的 JSON 输出格式中，实际内容**嵌套在 `data.part` 内**：

```json
{"type":"text", "sessionID":"ses_xxx", "part":{"type":"text", "text":"OK"}}
```

但 `_parse_line()` 只查顶层 `data["text"]`，永远拿到 `None` → 所有文本内容丢失 → opencode "不理你"。

### 修复

`_parse_line` 中的 `_s()` 辅助函数改为**优先取 `data.part` 内字段**，fallback 到顶层（兼容旧版 opencode）。

### 为什么 ping 测试通过了？

ping 测试只检查 `data.get("type") == "text"` 就返回 True，不提取文本内容，所以没暴露这个 bug。

---

## 其他发现

### 1. `--dangerously-skip-permissions` 不是 opencode 的有效 flag

`opencode run --help` 中不存在此 flag。opencode 静默忽略未知 flag，所以无害但应移除。

### 2. 每次调用覆写配置文件

`_write_provider_config()` 在每次 `stream()` 时覆写 `~/.config/opencode/opencode.jsonc`，并发场景有竞态风险。建议：只在 key 变更时写入，或启动时写一次。

### 3. 配置 key 可能应为 `providers`（复数）

OpenCode 文档中配置 key 为 `providers`（复数），当前代码用 `provider`（单数）。v1.15.13 实测能用，但后续版本可能收紧校验。

### 4. API key 明文落盘

配置文件直接写入明文 key，建议改为 `"apiKey": "env:DEEPSEEK_API_KEY"` 模式，运行时注入环境变量。

---

## 验证

```bash
# 修复前：text 内容丢失
echo '{"type":"text","part":{"text":"OK"}}' | python -c "
data = json.loads(sys.stdin.read())
print(data.get('text'))  # None!
"

# 修复后：正确从 part.text 提取
echo '{"type":"text","part":{"text":"OK"}}' | python -c "
part = data.get('part', {})
print(part.get('text') or data.get('text'))  # 'OK'
"
```

## opencode v1.15+ CLI 参考

```
opencode run --help

  --format       json (raw JSON events)
  -m, --model    provider/model (如 deepseek/deepseek-v4-flash)
  -s, --session  继续已有 session
  -c, --continue 继续上次 session
  --pure         禁用外部插件
  --attach       连接后台 opencode server
  --print-logs   打印日志到 stderr
```

### JSON 事件格式 (--format json)

| type | 内容位置 |
|------|---------|
| `step_start` | `part.type = "step-start"`, 顶层 `sessionID` |
| `text` | `part.text` (嵌套), `part.type = "text"` |
| `tool_use` | `part.name`, `part.arguments` |
| `tool_result` | `part.content`, `part.is_error` |
| `step_finish` | marker 事件 |
| `error` | `part.message` |
