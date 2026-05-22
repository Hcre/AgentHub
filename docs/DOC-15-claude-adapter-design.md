# Claude Adapter 详细设计

> 版本：v1.1 | 日期：2026-05-22 | 基于 adapter_interface_spec.md v0.2 + 架构设计文档

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

## 一、定位

Claude Adapter 是 L1 基础设施层组件，实现 L2 定义的 `UnifiedAgent` 抽象接口，是 AgentHub 与外部 LLM 之间的**唯一通信桥梁**。

```
L3 Application (ChatService / CoordinatorService)
    │ 调用 UnifiedAgent.stream(request)                    ← 只依赖抽象
    ▼
L2 Domain (UnifiedAgent ABC + AgentRequest/StreamEvent)     ← 接口定义
    ▲
    │ 实现 UnifiedAgent                                     ← 依赖倒置
L1 Infrastructure (ClaudeAdapter / ClaudeCliAdapter / MockAdapter)
    │ 调用 Anthropic SDK / CLI 子进程
    ▼
外部 LLM (Anthropic API / Claude Code CLI)
```

---

## 二、职责边界

### 适配器负责

| 职责 | 说明 |
|------|------|
| 接收 `AgentRequest`，组装 prompt + messages | 将 MemoryContext L1-L4 注入 system_prompt |
| 调用 LLM（Anthropic SDK 或 CLI 子进程） | 唯一的外部通信出口 |
| 流式产出 `StreamEvent` | 逐事件 yield，不缓冲 |
| 重试退避 | 网络波动/限流时指数退避，最多 3 次 |
| 错误标准化 | 所有异常包装为 `StreamEvent(type=ERROR)` |

### 适配器不负责

| 非职责 | 由谁负责 |
|--------|---------|
| Tool 执行 | L2 Harness / ToolScheduler |
| Tool 循环编排（多轮 tool_use） | L3 ChatService / CoordinatorService |
| 审批流程（HITL） | L3 InboxService + L2 Harness |
| 记忆获取（L1-L4 数据） | L3 MemoryContextBuilder（域3） |
| 会话管理 | L3 ChatService |
| 任务分解逻辑 | L2 CoordinatorService |

**核心原则**：适配器是纯粹的"输入→LLM→流式输出"管道，不包含任何业务逻辑。

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

## 六、三种适配模式

| 模式 | 配置值 | 实现类 | 通信方式 |
|------|--------|--------|---------|
| Mock | `mock` | `MockAdapter` | 本地生成假数据 |
| Anthropic API | `anthropic_api` | `ClaudeAdapter` | `AsyncAnthropic.messages.stream()` |
| Claude CLI | `claude_cli` | `ClaudeCliAdapter` | `subprocess.Popen("claude", ...)` |

工厂 `build_adapter()` 按 `LLM_ADAPTER_MODE` 配置选择实现。API Key 缺失时自动降级为 Mock。

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

## 八、claude_cli 模式实现 [M2 待实现]

> 当前 `factory.py` 中 `claude_cli` 分支 fallback 到 MockAdapter。`ClaudeCliAdapter` 文件尚未创建。

### 8.1 调用流程

```
ClaudeCliAdapter.stream(request: AgentRequest) → AsyncIterator[StreamEvent]:
  │
  ├─ 1. 检查 CLI 可用性: shutil.which("claude")
  │
  ├─ 2. 将 messages 写为临时 JSON → stdin
  │
  ├─ 3. spawn: claude --model {m} --max-tokens {t} --stream --input-format json
  │
  ├─ 4. 逐行读 stdout → 解析 → yield TEXT event
  │
  ├─ 5. stderr 非空 → yield ERROR event
  │
  ├─ 6. 进程退出 → yield DONE event
  │
  └─ 7. 超时: asyncio.wait_for(process.wait(), timeout=settings.claude_cli_timeout)
```

### 8.2 与 anthropic_api 的区别

| 特性 | anthropic_api | claude_cli |
|------|-------------|-----------|
| THINKING 事件 | 支持 | 不支持（CLI 不暴露） |
| TOOL_CALL 事件 | 支持 | 不支持（CLI 自己管理工具） |
| 需要 API Key | 是 | 否（由 CLI 配置管理） |
| 适用场景 | 生产环境 | 本地开发 |

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
backend/app/infrastructure/llm/
├── __init__.py
├── factory.py              # build_adapter() 工厂                    ✅
├── mock_adapter.py         # MockAdapter — 无 API Key 时使用          ✅
├── claude_adapter.py       # ClaudeAdapter — anthropic_api 模式       ✅ (含 _build_system_prompt / _build_tool_definitions)
└── claude_cli_adapter.py   # ClaudeCliAdapter — claude_cli 子进程模式  [M2 待创建]
```

> v1.0 原计划的 `_prompt_builder.py` 已内联到 `claude_adapter.py` 中作为模块级纯函数，不再单独拆文件。

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
