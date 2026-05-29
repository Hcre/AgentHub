# Claude Adapter 详细设计

> 版本：v1.2 | 日期：2026-05-22 | 基于 adapter_interface_spec.md v0.2 + 架构设计文档

## 与 adapter_interface_spec.md 的差异说明

| spec v0.1 | 本设计 / 代码实际 | 原因 |
|-----------|------------------|------|
| `send_message()` | `stream()` | 更准确地表达流式语义，已在 protocol.py 冻结 |
| `agent_id` property | 移除 | Agent 标识在 `domain/entities/agent.py` 管理，不属于适配器职责 |
| `capabilities` property | 移除 | 同上，能力标签是实体属性 |
| `health_check()` | 移除 | 通过基础设施层健康检查实现（`/health` endpoint） |
| `get_supported_tools()` | 移除 | 由 ToolRegistry（M3）管理 |
| 新增 `chat_structured()` | spec 无 | 协调者任务分解需要非流式结构化输出 |

spec v0.2 已同步更新。

---

## 一、定位与双轨架构

AgentHub 与外部 AI 系统的通信存在两种本质不同的模式，不应强行统一到同一抽象中：

| | LLMAdapter（API 模式） | AgentRuntime（CLI 模式） |
|---|---|---|
| 本质 | 一次 LLM 调用的管道 | 完整 Agent 会话的运行时 |
| 谁管 tool loop | AgentHub（ChatService + ToolScheduler） | CLI 自身（自带 tool use） |
| 谁管会话状态 | AgentHub（L1 Redis + L2 摘要） | CLI 自身（`--resume`、session） |
| 流式输出 | SDK stream（结构化事件） | stdout 逐行解析（JSON Lines） |
| Harness | AgentHub 自建或引入 Agent SDK | CLI 自带，零成本 |

```
L3 Application (ChatService / CoordinatorService)
    │
    │  统一消费 AsyncIterator[StreamEvent]
    ▼
L2 Domain — 接口定义
    ├── UnifiedAgent (ABC)           ← 顶层抽象
    │   ├── LLMAdapter (ABC)         ← API 模式：AgentHub 控制 tool loop
    │   └── AgentRuntime (ABC)       ← CLI 模式：运行时自控 tool loop
    ▲
    │  依赖倒置
L1 Infrastructure — 实现
    ├── LLMAdapter 实现
    │   ├── ClaudeAdapter            (Anthropic API)        ✅ 已实现
    │   ├── OpenAICompatAdapter      (DeepSeek/Groq/vLLM)  [未来扩展]
    │   └── MockAdapter              (本地假数据)            ✅ 已实现
    │
    └── AgentRuntime 实现
        ├── ClaudeCodeRuntime        (claude CLI)           ← 当前优先
        ├── CodexRuntime             (codex CLI)            [未来扩展]
        └── TraeRuntime              (trae CLI)             [未来扩展]
```

### 为什么分两轨

CLI 工具（Claude Code / Codex / Trae）不是"LLM 的 HTTP 代理"，它们是**自带 Harness 的完整 Agent 运行时**：
- 自己管理 tool 调用（文件编辑、bash、MCP）
- 自己管理会话记忆（`--resume`）
- 自己处理审批（permission 机制）

如果用 `--print` 把 CLI 降格为一次性 LLM 调用，等于丢弃了免费的 Harness 设施，然后在 AgentHub 侧花大量人力重建。

**当前优先级**：CLI Runtime 先行（Harness 零成本）→ API 接口保留（未来扩展）。

---

## 二、职责边界

### LLMAdapter 职责（API 模式）

| 职责 | 说明 |
|------|------|
| 接收 `AgentRequest`，组装 prompt + messages | 将 MemoryContext L1-L4 注入 system_prompt |
| 调用 LLM API | 唯一的外部通信出口 |
| 流式产出 `StreamEvent` | 逐事件 yield，不缓冲 |
| 重试退避 | 网络波动/限流时指数退避，最多 3 次 |
| 错误标准化 | 所有异常包装为 `StreamEvent(type=ERROR)` |

**LLMAdapter 不负责**：Tool 执行、Tool 循环编排、审批流程、记忆获取、会话管理、任务分解。这些由 L3 ChatService / L2 Harness 负责。

### AgentRuntime 职责（CLI 模式）

| 职责 | 说明 |
|------|------|
| 接收任务指令，启动 CLI 进程 | `claude --resume` / `codex` / `trae` |
| 管理进程生命周期 | spawn、communicate、timeout、kill |
| 解析 stdout → `StreamEvent` | JSON Lines 格式逐行映射 |
| 转发 HITL 审批请求 | CLI 请求权限时 → `REQUEST_APPROVAL` 事件 |
| 进程级错误处理 | 崩溃 / 超时 → `StreamEvent(type=ERROR)` |

**AgentRuntime 不负责**：Tool 执行（CLI 自己做）、Tool 循环编排（CLI 自己做）、prompt 拼装（CLI 有自己的 context 管理）。

**核心原则**：LLMAdapter 是"输入→LLM→流式输出"的无状态管道；AgentRuntime 是"委托任务→转发事件"的有状态进程管理器。

---

## 三、输入：AgentRequest

```python
class AgentRequest(BaseModel):
    request_id: str                    # UUID，全链路追踪
    session_id: UUID                   # 会话 ID
    messages: list[dict]               # [{"role": "user/assistant", "content": "..."}]
    system_prompt: str | None          # Agent 自定义 system_prompt
    memory: MemoryContext | None       # L1-L4 记忆上下文
    available_tools: list[str]         # 本会话可用的 Tool 名称列表
    max_tokens: int = 16000
    temperature: float = 0.7

class MemoryContext(BaseModel):
    l1_working: list[dict]             # Redis 滑动窗口最近 20 条
    l2_summary: str | None             # 超长历史摘要
    l3_specs: str | None               # .agenthub/ 项目上下文
    l4_rag: str | None                 # pgvector Top-K 检索
```

**谁构造 AgentRequest**：L3 ChatService（私聊）或 CoordinatorService（群聊分解）

**数据来源**：
- `messages`：ChatService 从 `L1MemoryStore.get_window()` 取最近 20 条
- `memory`：MemoryContextBuilder（域3）打包 L1-L4 记忆
- `system_prompt`：Agent 实体的 `system_prompt` 字段
- `available_tools`：ToolRegistry 按 Agent 能力过滤后的工具列表

---

## 四、输出：StreamEvent（8 种类型）

```python
class StreamEventType(StrEnum):
    TEXT = "text"                           # 普通文本 token
    THINKING = "thinking"                   # 扩展思考过程
    TOOL_CALL = "tool_call"                 # Agent 请求调用工具
    TOOL_RESULT = "tool_result"             # 工具执行结果（由 ToolScheduler 产生）
    REQUEST_APPROVAL = "request_approval"   # 危险操作请求审批（由 Harness 产生）
    TASK_PLAN = "task_plan"                 # 协调者任务分解 JSON
    ERROR = "error"                         # 错误事件
    DONE = "done"                           # 流结束

class StreamEvent(BaseModel):
    type: StreamEventType
    seq: int                               # 事件序号
    content: str | None                    # text/thinking/error 文本
    tool_call: ToolCall | None             # tool_call 时填充
    tool_result: ToolResult | None         # tool_result 时填充
    task_plan: dict | None                 # task_plan 时填充
    metadata: dict[str, Any]               # token_usage, model, latency_ms
```

**适配器产出的事件**：TEXT / THINKING / TOOL_CALL / ERROR / DONE

**上层产出的事件**（非适配器）：TOOL_RESULT（ToolScheduler）、REQUEST_APPROVAL（Harness）、TASK_PLAN（CoordinatorService）

---

## 五、输出流向

```
ClaudeAdapter.stream(AgentRequest)
  │
  │  AsyncIterator[StreamEvent] 逐事件 yield
  ▼
L3 ChatService.send_and_stream()    ← 消费者 #1（私聊/群聊）
  │
  │  yield event（透传）
  ▼
L4 WebSocket Handler                 ← 消费者 #2（序列化为 WS Frame）
  │
  │  WS Push
  ▼
L5 前端 useWebSocket                 ← 消费者 #3（渲染）
  │
  ├─ TEXT       → StreamingText 逐字打印
  ├─ THINKING   → 灰色展开面板
  ├─ TOOL_CALL  → "Agent 正在执行 {tool_name}..."
  ├─ TOOL_RESULT→ 工具执行结果展示
  ├─ ERROR      → Toast 错误提示
  └─ DONE       → token 计量条更新
```

调用链完整路径：
```
用户发消息 → WS → ChatService
  → MemoryContextBuilder.build()      # 域3 打包记忆
  → AgentRequest(...)                 # 构造请求
  → llm.stream(request)               # ← 适配器入口
    → Anthropic API                   # 外部调用
    → yield TEXT/THINKING/TOOL_CALL   # 流式产出
  → yield event                       # ChatService 透传
→ WS push → 前端渲染                  # 最终呈现
```

---

## 六、适配模式总览

### 6.1 当前实现

| 轨道 | 模式 | 配置值 | 实现类 | 状态 |
|------|------|--------|--------|------|
| — | Mock | `mock` | `MockAdapter` | ✅ 可用 |
| API | Anthropic | `anthropic_api` | `ClaudeAdapter` | ✅ 可用 |
| CLI | Claude Code | `claude_code` | `ClaudeCodeRuntime` | ← **当前优先实现** |

工厂 `build_adapter()` 按 `LLM_ADAPTER_MODE` 配置选择实现。API Key 缺失时自动降级为 Mock。

### 6.2 未来 API 扩展规划

#### 多模型接入路线

```
方案一：直接 SDK 接入（逐个对接）
  OpenAICompatAdapter → DeepSeek / Groq / Together / vLLM
  GeminiAdapter       → Google AI
  优点：最大控制力，无中间层
  缺点：每个 provider 一个实现，维护成本随数量增长

方案二：Agent SDK 作为 Harness 层
  OpenAI Agents SDK   → 任何 OpenAI-compatible 模型（含 DeepSeek）
  Pydantic AI         → Claude / OpenAI / Gemini / DeepSeek
  优点：Harness（tool loop + HITL）免费获得，无需自建
  缺点：引入框架依赖

方案三：协议适配（LiteLLM）
  LiteLLM proxy       → 100+ 模型统一接口
  优点：通用性最强，可实现负载均衡 + 自动降级
  缺点：多一个运行组件，调试链路变长
```

#### Agent SDK 兼容性矩阵

| SDK | Claude | OpenAI-compat (DeepSeek等) | Gemini | 多模型切换 |
|-----|--------|---------------------------|--------|-----------|
| **Claude Agent SDK** | ✅ | ❌ 不支持 | ❌ | ❌ 仅 Anthropic |
| **OpenAI Agents SDK** | ❌ 原生不支持 | ✅ | ❌ | ✅ 任何 OpenAI-compat |
| **Pydantic AI** | ✅ | ✅ | ✅ | ✅ 运行时切换 |
| **LiteLLM** | ✅ | ✅ | ✅ | ✅ 代理层统一 |

> **推荐路线**：短期用 `OpenAICompatAdapter` 直接对接 DeepSeek（最简单）；
> 中期引入 Pydantic AI 或 OpenAI Agents SDK 获得 Harness 能力；
> 长期按需加 LiteLLM 做负载均衡。

#### 决策约束

- Claude Agent SDK **不支持非 Anthropic 模型**，排除作为通用 Harness
- OpenAI Agents SDK 可用于 DeepSeek/Groq 等 OpenAI-compatible 模型
- Pydantic AI 覆盖面最广但需评估与现有 Pydantic v2 栈的集成成本
- 任何方案均不影响 CLI Runtime 轨道（两轨独立演进）

### 6.3 未来 CLI 扩展

| CLI 工具 | 运行时 | 优先级 | 备注 |
|----------|--------|--------|------|
| Claude Code | `ClaudeCodeRuntime` | P0 当前 | `claude --resume` + JSON stdout |
| Codex | `CodexRuntime` | P2 | OpenAI CLI，类似模式 |
| Trae | `TraeRuntime` | P3 | 需评估 CLI 接口成熟度 |

---

## 七、anthropic_api 模式实现

### 7.1 调用流程 ✅ 已实现

```
ClaudeAdapter.stream(request: AgentRequest) → AsyncIterator[StreamEvent]:
  │
  ├─ 1. _build_system_prompt(request)           ✅ 已实现
  │      合并: request.system_prompt
  │           + request.memory.l3_specs         (Project Context)
  │           + request.memory.l2_summary       (Conversation Summary)
  │           + request.memory.l4_rag           (Relevant Knowledge)
  │      → 单一 system 字符串
  │
  ├─ 2. _build_tool_definitions(available_tools) [M3 待实现: 需 ToolRegistry]
  │      当前: 无 registry 时返回空列表
  │      目标: 从 ToolRegistry 查询完整 JSON Schema
  │
  ├─ 3. _stream_with_retry(kwargs)               ✅ 已实现
  │      调用 AsyncAnthropic.messages.stream(**kwargs)
  │      逐事件映射: Anthropic event → StreamEvent (5 种: TEXT/THINKING/TOOL_CALL/ERROR/DONE)
  │      指数退避重试: 1s → 2s → 4s，最多 3 次
  │
  └─ 4. 异常 → StreamEvent(type=ERROR)           ✅ 已实现
```

### 7.2 Anthropic 事件映射表 ✅ 已实现

| Anthropic 事件 | StreamEvent |
|---------------|-------------|
| `content_block_delta.text_delta.text` | `TEXT(seq, content=delta)` |
| `content_block_start.content_block.thinking` | （开始收集） |
| `content_block_delta.thinking_delta.thinking` | `THINKING(seq, content=delta)` |
| `content_block_start.content_block.tool_use` | （开始收集 name + input_json） |
| `content_block_delta.input_json_delta.partial_json` | （累积 JSON 片段） |
| `content_block_stop` (tool_use) | `TOOL_CALL(seq, tool_call=ToolCall(...))` |
| `message_delta.usage` | 暂存到 metadata |
| 流结束 | `DONE(seq, metadata={token_usage, model, stop_reason})` |

### 7.3 关键参数 ✅ 已实现

```python
kwargs = {
    "model": self._model,               # 从 config.default_model 注入
    "max_tokens": request.max_tokens,    # 默认 16000 (config.max_tokens)
    "temperature": request.temperature,  # 默认 0.7
    "system": system_prompt,             # _build_system_prompt() 组装
    "messages": messages,                # 用户/助手消息历史
    "tools": tool_definitions,           # [M3 待实现] 当前为空列表
}
```

### 7.4 THINKING 控制 [M2 待实现: 需 Agent settings 扩展]

```python
# 目标实现（需要 Agent 实体新增 thinking_enabled / thinking_budget 字段）
if agent_settings.thinking_enabled:
    kwargs["thinking"] = {
        "type": "enabled",
        "budget_tokens": agent_settings.thinking_budget or 4000,
    }
```

当前状态：THINKING 事件**解析**已实现（收到 thinking_delta 会产出 `StreamEvent(THINKING)`），但**触发**机制待 Agent settings 扩展后接入。默认不启用扩展思考。

---

## 八、CLI Runtime 模式设计 ← 当前优先实现

### 8.0 设计原则

CLI 工具自带完整 Harness（tool 执行、会话管理、权限控制）。AgentRuntime 的职责是**进程管理 + 事件转发**，不重复实现 Harness 逻辑。

### 8.1 ClaudeCodeRuntime 架构

```
ClaudeCodeRuntime
  │
  ├── 进程管理
  │   ├─ spawn: claude --print --output-format=stream-json --verbose
  │   ├─ resume: claude --resume --session-id {id} (跨调用保持会话)
  │   └─ kill: 超时/取消时优雅终止
  │
  ├── stdout 解析 (JSON Lines)
  │   ├─ {"type":"assistant","content":[{"type":"text","text":"..."}]}  → TEXT
  │   ├─ {"type":"assistant","content":[{"type":"tool_use",...}]}       → TOOL_CALL (仅通知)
  │   ├─ {"type":"result","result":"...","duration_ms":...}            → DONE
  │   └─ 其他/异常行                                                    → ERROR
  │
  └── HITL 桥接
      └─ CLI 的 permission 请求 → REQUEST_APPROVAL → 用户决策 → stdin 回写
```

### 8.2 两种调用模式

| 模式 | 命令 | 适用场景 | 会话状态 |
|------|------|---------|----------|
| **one-shot** | `claude --print -p "..." --output-format stream-json` | 简单问答、无需 tool | 无状态 |
| **session** | `claude --resume --session-id {uuid} --output-format stream-json` | 多轮对话、工具调用 | CLI 内部维护 |

私聊场景默认用 session 模式（利用 CLI 原生会话记忆）；
协调者分解子任务时用 one-shot 模式（每个子任务独立执行）。

### 8.3 ChatService 消费 Runtime 的方式

```python
# CLI Runtime 模式：委托整个任务，只转发事件
async for event in runtime.run(task):
    if event.type == REQUEST_APPROVAL:
        # CLI 请求执行危险操作 → 转发给前端 HITL
        decision = await hitl_service.prompt(event)
        await runtime.send_decision(decision)
    yield event   # 透传给 WS → 前端
```

与 API 模式的关键区别：**ChatService 不管 tool loop**，CLI 自己决定何时调用工具、何时结束。

### 8.4 与 LLMAdapter 的对比

| 维度 | LLMAdapter (API) | AgentRuntime (CLI) |
|------|-------------------|---------------------|
| Tool loop | AgentHub 管理（M3 待建） | CLI 自管（零成本） |
| 会话记忆 | AgentHub L1/L2 | CLI `--resume` |
| Harness | 需自建或引入 Agent SDK | CLI 自带 |
| HITL 粒度 | tool_call 级别精确拦截 | CLI permission 级别 |
| 多模型支持 | 按 provider 扩展 | 按 CLI 工具扩展 |
| 适用阶段 | 未来扩展 | **当前优先** |

---

## 九、重试退避 ✅ 已实现

```python
from anthropic import RateLimitError, APIStatusError

RETRYABLE = (RateLimitError, APIStatusError)  # 429 + 5xx
MAX_RETRIES = 3
BASE_DELAY = 1.0  # 秒

async def _stream_with_retry(self, kwargs):
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with self._client.messages.stream(**kwargs) as stream:
                ...  # yield events
            return  # 成功
        except RETRYABLE:
            if attempt == MAX_RETRIES:
                raise
            await asyncio.sleep(BASE_DELAY * (2 ** attempt))  # 1s → 2s → 4s
```

**不可重试错误**（4xx 非 429）：直接包装为 `StreamEvent(type=ERROR)` → 不重试。

---

## 十、Tool Loop 编排（由上层实现）[M3 待实现]

适配器只做一次 LLM 调用的流式产出。Tool 循环由 L3 编排。当前 ChatService 为直通模式，不做 tool loop。目标实现：

```
ChatService.send_and_stream():
  │
  ├─ messages = [...]
  │
  └─ for turn in range(max_turns):          ← 最多 10 轮，防死循环
       │
       ├─ request = AgentRequest(messages=messages, ...)
       │
       ├─ async for event in llm.stream(request):
       │     if event.type == TOOL_CALL:
       │       tool_calls.append(event.tool_call)
       │     yield event                     ← 实时推 WS
       │
       ├─ if not tool_calls: break           ← LLM 没调工具，对话结束
       │
       └─ for tc in tool_calls:
            result = await tool_scheduler.execute(tc)   ← Harness 执行
            messages.append(tool_result_block(result))   ← 回注
            yield StreamEvent(type=TOOL_RESULT, ...)
```

---

## 十一、配置项

```python
# core/config.py 新增
claude_cli_timeout: int = 300        # CLI 子进程超时（秒）
max_tool_turns: int = 10             # Tool loop 最大轮次
max_tokens: int = 16000              # LLM 默认 max_tokens

# Agent settings（Agent 级别）
thinking_enabled: bool = False       # 是否启用扩展思考
thinking_budget: int = 4000          # 思考 token 预算
```

---

## 十二、文件结构

```
src/backend/app/domain/llm/
├── protocol.py             # UnifiedAgent + LLMAdapter + AgentRuntime ABC
└── __init__.py

src/backend/app/infrastructure/llm/
├── __init__.py
├── factory.py              # build_adapter() 工厂                        ✅
├── mock_adapter.py         # MockAdapter — 无 API Key 时使用              ✅
├── claude_adapter.py       # ClaudeAdapter (LLMAdapter) — Anthropic API   ✅
└── runtimes/
    ├── __init__.py
    ├── claude_code.py      # ClaudeCodeRuntime (AgentRuntime)             ← 当前优先
    ├── codex.py            # CodexRuntime                                 [未来]
    └── trae.py             # TraeRuntime                                  [未来]
```

> API 适配器和 CLI 运行时在文件系统上也物理分离，避免职责混淆。

---

## 十三、与现有接口的关系

| 已有定义 | 位置 | 本次变化 |
|---------|------|---------|
| `UnifiedAgent` ABC | `domain/llm/protocol.py` | 不变（W1 已冻结） |
| `AgentRequest` / `StreamEvent` | `domain/llm/protocol.py` | 不变 |
| `ClaudeAdapter` | `infrastructure/llm/claude_adapter.py` | ✅ 已重写：5 种事件 + memory 注入 + 重试退避 |
| `MockAdapter` | `infrastructure/llm/mock_adapter.py` | 不变 |
| `build_adapter()` | `infrastructure/llm/factory.py` | claude_cli 分支已有（fallback mock） |
| `adapter_interface_spec.md` | `docs/` | ✅ v0.2 已同步更新接口定义 |
| `config.py` | `core/config.py` | ✅ 新增 max_tokens / max_tool_turns / claude_cli_timeout |

---

## 十四、版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-05-22 | 初稿：单轨 adapter 设计 |
| v1.1 | 2026-05-22 | 审查裁决：加差异说明 + [待实现] 标记，实现 ClaudeAdapter |
| v1.2 | 2026-05-22 | 双轨架构：LLMAdapter(API) + AgentRuntime(CLI) 分离，API 扩展规划，CLI 优先实现 |
