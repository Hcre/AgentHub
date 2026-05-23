---
name: test-claude-adapter
description: E2E test the Claude Code adapter — start backend, create agent/session, chat via WebSocket. Use after modifying claude_code_runtime.py or factory.py.
---

# test-claude-adapter: Claude 适配器端到端测试

> 验证 ClaudeCodeRuntime 全链路：API → ChatService → CLI subprocess → stream-json 解析 → WS 推送

## 前提

- PostgreSQL + Redis 已启动（localhost 默认端口）
- `claude` CLI 可用（`which claude`）
- 本机 Claude Code 已认证（`claude --print "test"` 能正常响应）

## 执行步骤

### 1. 启动后端

```bash
cd /home/huishuohuademao/workspace/AgentHub/.worktrees/claude-adapter/backend
/home/huishuohuademao/workspace/AgentHub/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. 创建 Agent + Session

```bash
AGENT_ID=$(curl -s -X POST http://127.0.0.1:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{"name":"ClaudeTest","avatar":"🤖","role":"开发助手","agent_system":"claude_code","provider":"anthropic"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Agent: $AGENT_ID"

SESSION_ID=$(curl -s -X POST http://127.0.0.1:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"private\",\"agent_id\":\"$AGENT_ID\",\"title\":\"test\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Session: $SESSION_ID"
```

### 3. WebSocket 多轮对话测试

```bash
cd /home/huishuohuademao/workspace/AgentHub/.worktrees/claude-adapter/backend
/home/huishuohuademao/workspace/AgentHub/backend/.venv/bin/python scripts/manual_test_claude.py
```

### 4. 前端 UI 测试（可选）

```bash
cd /home/huishuohuademao/workspace/AgentHub/frontend
npm run dev
```

浏览器打开 `http://localhost:5173`，进入刚创建的 session 发送消息。

## 验证点

| # | 验证项 | 预期 |
|---|--------|------|
| 1 | Agent 创建返回 201 | `agent_system: "claude_code"` 在响应中 |
| 2 | Session 创建返回 201 | type=private，关联 agent_id |
| 3 | WS 发送消息后收到流式响应 | text 事件逐字推送 |
| 4 | 第一轮发送后收到 DONE | cost > 0，duration_ms > 0 |
| 5 | 第二轮 `--resume` 恢复上下文 | Agent 记住第一轮的内容 |
| 6 | 后端日志有 `request_id=... session=...` | 确认日志输出 |
| 7 | tool_use 事件映射为 TOOL_CALL | 前端可见工具调用 |
| 8 | tool_result is_error 映射正确 | 权限阻断 → permission_denials |

## 常见问题

### Internal Server Error on create agent

缺少 DB 列，运行：

```bash
/home/huishuohuademao/workspace/AgentHub/backend/.venv/bin/python -c "
import asyncio, sys
sys.path.insert(0, '/home/huishuohuademao/workspace/AgentHub/.worktrees/claude-adapter/backend')
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def main():
    e = create_async_engine('postgresql+asyncpg://agenthub:agenthub_dev_pwd@localhost:5432/agenthub')
    async with e.begin() as conn:
        await conn.execute(text(\"ALTER TABLE agents ADD COLUMN IF NOT EXISTS agent_system VARCHAR(32) DEFAULT 'mock' NOT NULL\"))
        await conn.execute(text('ALTER TABLE agents ADD COLUMN IF NOT EXISTS base_url VARCHAR(512)'))
    print('OK')
    await e.dispose()
asyncio.run(main())
"
```

### Nonce must be between 8 and 128 bytes

Agent 创建时未传 api_key，factory 对空字符串调了 decrypt_secret。已在 factory.py 修复（空值时跳过解密）。

### CLI 未安装或未认证

```bash
which claude && claude --print "hi" --max-turns 1
```
