# EXP-01: Pi Agent 接入分析

> 日期: 2026-05-27 | 状态: 进行中
> 目标: 将 Pi Agent (earendil-works/pi) 接入 AgentHub 双轨架构

---

## 1. Pi Agent 概览

| 维度 | 详情 |
|------|------|
| 项目 | github.com/earendil-works/pi |
| 类型 | Node.js/TypeScript 交互式 Coding Agent CLI |
| 架构 | Monorepo: pi-coding-agent / pi-agent-core / pi-ai / pi-tui |
| 运行方式 | CLI (`pi`), 从源码构建 (`npm run build`) |
| License | MIT |
| 最新版本 | v0.75.5 (2026-05-23) |

**核心能力**: 多 Provider (Anthropic/OpenAI/Google) 统一 LLM API，自带工具执行 Harness（read/bash/edit/write/grep/find/ls），会话持久化，RPC 模式支持程序化集成。

---

## 2. 与 Claude CLI 对比

| 维度 | Claude CLI | Pi Agent |
|------|-----------|----------|
| 语言 | Rust/Python | TypeScript |
| Provider | 仅 Anthropic | Anthropic/OpenAI/Google |
| 工具集 | 内置 + MCP | 内置 7 件套 + Extension |
| 输出模式 | `--output-format stream-json` | `--mode json` / `--mode rpc` |
| 会话 | `--session-id` / `--resume` | `--session <path\|id>` / `-c` / `--no-session` |
| 权限 | `--permission-mode` | 无内置权限模式（RPC 下由客户端控制） |
| 最大轮次 | `--max-turns` | 无 `--max-turns`（需通过 abort 命令控制） |
| 程序化集成 | stdin prompt → stdout JSON stream | stdin JSONL commands → stdout JSONL events |
| 子进程控制 | stdin EOF 结束 | `abort` 命令 |
| System Prompt | `--system-prompt` | `--system-prompt` / `--append-system-prompt` |
| 模型选择 | `--model` 或 `ANTHROPIC_MODEL` | `--model` / `--provider` |
| API Key | `ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY` 等，或 `--api-key` |

**关键差异**:

1. **RPC 模式是双向协议** — 不像 Claude CLI 单向 stdin→stdout，Pi 的 RPC 模式支持运行时命令（abort、steer、get_state 等），更灵活
2. **无 max-turns** — 需要 AgentHub 侧通过 timeout 或发送 abort 命令来控制
3. **无 permission-mode** — Pi 在 RPC 模式下由调用方（AgentHub）控制权限
4. **多 Provider** — 一个 CLI 支持多 LLM 后端，AgentHub 的 Provider 枚举可以充分利用

---

## 3. RPC 模式协议分析

### 3.1 启动命令

```bash
pi --mode rpc [--provider <name>] [--model <pattern>] [--no-session] [--session <id>]
   [--session-dir <path>] [--system-prompt <text>] [--thinking <level>]
   [--tools <list>] [--no-builtin-tools] [--no-tools]
   [--extension <source>] [--skill <path>]
```

### 3.2 JSONL 协议

**传输**: stdin/stdout JSONL, LF (`\n`) 分隔。

**Commands (stdin)**:

```json
// 核心
{"type": "prompt", "message": "Hello!", "images": []}     // 发送用户消息
{"type": "abort"}                                           // 终止当前操作
{"type": "new_session", "parentSession": "/path"}           // 新建会话
{"type": "switch_session", "sessionFile": "/path"}          // 切换会话

// 状态查询
{"type": "get_state"}    // → {model, thinkingLevel, isStreaming, sessionId, ...}
{"type": "get_messages"} // → 所有消息

// 模型 & 思考
{"type": "set_model", "provider": "anthropic", "modelId": "claude-sonnet-4-20250514"}
{"type": "set_thinking_level", "level": "off|minimal|low|medium|high|xhigh"}
{"type": "cycle_model"}

// Bash 执行
{"type": "bash", "command": "ls -la"}  // → {output, exitCode, cancelled}

// 会话管理
{"type": "compact"}                    // 手动压缩
{"type": "get_session_stats"}          // Token 使用统计
{"type": "export_html", "outputPath": "/path"}
```

**Events (stdout)**:

```
agent_start → turn_start → message_start → message_update* → message_end
  → [tool_execution_start → tool_execution_update* → tool_execution_end]*
  → turn_end → agent_end
```

**message_update delta 类型**:
- `text_delta` → TEXT event
- `thinking_delta` → THINKING event
- `toolcall_start` / `toolcall_delta` / `toolcall_end` → TOOL_CALL event
- `done` / `error` → DONE event

### 3.3 与 Claude CLI stream-json 的映射关系

| Pi RPC Event | Claude CLI event | → StreamEvent |
|-------------|-----------------|---------------|
| `message_update.text_delta` | `assistant.content[text]` | TEXT |
| `message_update.thinking_delta` | `assistant.content[thinking]` | THINKING |
| `message_update.toolcall_end` | `assistant.content[tool_use]` | TOOL_CALL |
| `tool_execution_start/end` | `user.content[tool_result]` | TOOL_RESULT |
| `agent_end` | `result` | DONE |
| error in message | `result.is_error` | ERROR |

---

## 4. 接入方案

### 4.1 架构决策: AgentRuntime（非 LLMAdapter）

Pi 自带工具执行循环、会话记忆、权限控制 → `AgentRuntime` 子类。

### 4.2 实现路径

```
D:\AgentHub\repo\backend\app\
├── domain\enums.py              → + PI_AGENT = "pi_agent"
├── infrastructure\llm\
│   ├── pi_agent_runtime.py      → 新建 PiAgentRuntime(AgentRuntime)
│   └── factory.py               → + elif system == AgentSystem.PI_AGENT
```

### 4.3 PiAgentRuntime 设计

```python
class PiAgentRuntime(AgentRuntime):
    """
    Pi Agent CLI 运行时（--mode rpc 模式）。
    
    通过 `pi --mode rpc` 启动子进程，JSONL 双向协议。
    - stdin:  发送 JSON commands (prompt/abort/get_state)
    - stdout: 解析 JSONL events → StreamEvent
    - 会话: --session <session_id> 或 --no-session
    """

    async def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        # 1. 启动子进程: pi --mode rpc --no-session ...
        # 2. 发送 prompt command: {"type":"prompt","message":"..."}
        # 3. 循环读取 stdout JSONL → 解析为 StreamEvent
        # 4. agent_end 时结束流

    async def stop(self) -> None:
        # 发送 abort command: {"type":"abort"}
```

### 4.4 关键设计问题

1. **会话策略**: Pi 使用 `--session <path>` 而非 `--session-id`。需要将 AgentHub session UUID 映射为文件路径，或使用 `--no-session` + AgentHub 自己的记忆系统投喂历史。

2. **超时控制**: Pi 无 `--max-turns`。AgentHub 侧通过 `_timeout` 超时 + 发送 `abort` 命令来控制。

3. **权限模式**: Pi 无内置 approval 流程。工具执行的审批由 RPC 客户端的 `extension_ui_request` dialog 事件实现。初期可默认允许所有工具（Pi 在 RPC 模式下本身不会阻塞）。

4. **多 Provider**: Pi 的 `--provider` + `--model` 可直接复用 AgentHub 的 `agent.provider` + `agent.model` 字段。

5. **API Key 注入**: Pi 读取标准环境变量 (`ANTHROPIC_API_KEY` 等)，或通过 `--api-key` 参数。AgentHub 解密 agent 的 api_key 后通过环境变量注入。

---

## 5. Event 映射表

```python
# Pi message_update.assistantMessageEvent.type → StreamEventType
_EVENT_MAP = {
    "text_start":      None,           # 跳过
    "text_delta":      StreamEventType.TEXT,
    "text_end":        None,           # 跳过
    "thinking_start":  None,
    "thinking_delta":  StreamEventType.THINKING,
    "thinking_end":    None,
    "toolcall_start":  None,
    "toolcall_delta":  None,
    "toolcall_end":    StreamEventType.TOOL_CALL,
    "done":            StreamEventType.DONE,
    "error":           StreamEventType.ERROR,
}
```

## 6. 下一步

- [ ] 完成 Pi 仓库 clone，验证 CLI 可运行
- [ ] 实现 PiAgentRuntime
- [ ] 工厂注册
- [ ] 端到端测试（私聊 + 群聊）
- [ ] Pi Agent 的 AgentHub proxy 适配（多 Provider API key 注入）
