# Adapter Interface Specification — UnifiedAgent & Tool Protocol

> 域 2 ↔ 域 3 接口契约文档，W1 前半冻结。
> **域 2 负责**：UnifiedAgent 抽象 + Claude/Codex Adapter + Tool 调度框架。
> **域 3 负责**：实现本域 Tool（Diff/Deploy/Git/Memory），挂载到 Tool Registry。

---

## 1. 架构定位

```
┌──────────────────────────────────────────────────────┐
│  Domain 1 (Chat)                                     │
│  send_message() → AsyncIterator[StreamEvent]         │
│  只依赖 UnifiedAgent 抽象，不感知实现                  │
└────────────────────────┬─────────────────────────────┘
                         │
┌────────────────────────┴─────────────────────────────┐
│  Domain 2 (Orchestration) — 本文档范围                │
│                                                      │
│  UnifiedAgent (ABC)                                  │
│    ├── ClaudeAdapter    → claude CLI                 │
│    ├── CodexAdapter     → codex CLI                  │
│    └── LiteLLMGateway   → unified API                │
│                                                      │
│  ToolScheduler                                       │
│    → 接收 StreamEvent(tool_call)                     │
│    → ToolRegistry.lookup(tool_name)                  │
│    → if requires_approval: HITL.prompt()             │
│    → tool.execute(**params)                          │
│    → 回传 StreamEvent(tool_result) 给 Agent           │
└────────────────────────┬─────────────────────────────┘
                         │
┌────────────────────────┴─────────────────────────────┐
│  Domain 3 (Toolchain) — 实现 Tool                     │
│                                                      │
│  ToolRegistry.register(DiffTool())                   │
│  ToolRegistry.register(DeployTool())                 │
│  ToolRegistry.register(GitTool())                    │
│  ToolRegistry.register(MemoryTool())                 │
│  ...                                                 │
└──────────────────────────────────────────────────────┘
```

---

## 2. UnifiedAgent 接口

### 2.1 请求模型

```python
from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class MemoryContext(BaseModel):
    """域 3 记忆系统打包，注入到每次 Agent 调用"""
    l1_working: list[dict]           # Redis 滑动窗口最近 20 条消息
    l2_summary: Optional[str] = None # 超长历史的摘要
    l3_specs: Optional[str] = None   # .agenthub/ 中项目上下文
    l4_rag: Optional[str] = None     # pgvector Top-K 检索结果

class AgentRequest(BaseModel):
    request_id: str                  # UUID，全链路追踪
    session_id: UUID
    messages: list[dict]             # [{"role": "user/assistant", "content": "..."}]
    system_prompt: Optional[str] = None
    memory: Optional[MemoryContext] = None
    available_tools: list[str] = []  # 本会话可用的 Tool 名称列表
    max_tokens: int = 16000
    temperature: float = 0.7
```

### 2.2 响应模型：StreamEvent

```python
from enum import StrEnum
from typing import Any

class StreamEventType(StrEnum):
    TEXT = "text"               # 文本 token
    THINKING = "thinking"       # 扩展思考 token（展示但不可操作）
    TOOL_CALL = "tool_call"     # Agent 请求调用工具 → ToolScheduler 处理
    TOOL_RESULT = "tool_result" # 工具返回结果 → 回传给 Agent 继续推理
    REQUEST_APPROVAL = "request_approval"  # Agent 请求人工审批
    TASK_PLAN = "task_plan"     # Coordinator 产出的任务分解 JSON
    ERROR = "error"             # 错误事件
    DONE = "done"               # 流结束

class ToolCall(BaseModel):
    call_id: str                # 本次 tool_use 的唯一 ID
    name: str                   # Tool 名称
    arguments: dict[str, Any]   # 参数 JSON

class ToolResult(BaseModel):
    call_id: str                # 对应 ToolCall 的 call_id
    success: bool
    content: Optional[str] = None  # 成功时的返回内容
    error: Optional[str] = None    # 失败时的错误信息
    artifact: Optional[str] = None # 产物 URL/路径（Diff URL, Preview URL, Deploy URL）

class StreamEvent(BaseModel):
    type: StreamEventType
    seq: int                    # 事件序号
    content: Optional[str] = None           # text/thinking/error 内容
    tool_call: Optional[ToolCall] = None    # tool_call 时填充
    tool_result: Optional[ToolResult] = None # tool_result 时填充
    task_plan: Optional[dict] = None        # task_plan 时填充
    metadata: dict[str, Any] = {}           # token_usage, model, latency_ms 等
```

### 2.3 抽象接口

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator

class UnifiedAgent(ABC):
    """所有 Agent 适配器的统一接口"""

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """唯一标识，如 'claude-sonnet-4'"""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> list[str]:
        """能力标签，如 ['python', 'fastapi', 'react', 'postgresql']"""
        ...

    @abstractmethod
    async def send_message(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        """核心接口：发送消息，返回流式事件"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """检查 Agent 是否可用"""
        ...

    @abstractmethod
    async def get_supported_tools(self) -> list[str]:
        """返回本 Agent 支持的 Tool 名称列表"""
        ...
```

---

## 3. Tool 协议

### 3.1 基类定义

```python
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any, Optional

class Permission(StrEnum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"

class ToolCategory(StrEnum):
    FILESYSTEM = "filesystem"
    GIT = "git"
    PREVIEW = "preview"
    DEPLOY = "deploy"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"

class ToolDefinition(BaseModel):
    """Tool 元数据，用于：Agent 的 function calling schema 生成 + ToolRegistry 索引"""
    name: str
    description: str                        # LLM 理解用
    parameters: dict[str, Any]              # JSON Schema 格式
    category: ToolCategory
    permissions: list[Permission]           # 权限声明
    requires_approval: bool                 # True → Harness 拦截走 HITL
    max_timeout_seconds: int = 30

class BaseTool(ABC):
    """域 3 实现的所有 Tool 必须继承此类"""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """返回 Tool 元数据"""
        ...

    @abstractmethod
    async def execute(self, call_id: str, arguments: dict[str, Any], session_id: UUID) -> ToolResult:
        """执行工具调用。call_id 用于关联 ToolCall，session_id 用于上下文"""
        ...

    async def pre_execute(self, arguments: dict[str, Any]) -> None:
        """执行前校验，默认无操作。子类可覆盖做参数校验"""
        pass

    async def post_execute(self, result: ToolResult) -> ToolResult:
        """执行后处理，默认透传。子类可覆盖做结果格式化"""
        return result
```

### 3.2 Tool 完整调用链路

```
Agent 输出 tool_use 块
  → ClaudeAdapter 解析 → StreamEvent(tool_call)
  → Harness.ToolScheduler.receive(tool_call)
  → tool = ToolRegistry.lookup(tool_call.name)
  → if tool.requires_approval:
       emit StreamEvent(request_approval) → HITL 弹窗
       await user_decision  # 阻塞等待
       if rejected: return ToolResult(success=False, error="User rejected")
  → await tool.execute(tool_call.call_id, tool_call.arguments, session_id)
  → result = ToolResult(...)
  → emit StreamEvent(tool_result)
  → ClaudeAdapter.send(result) → Agent 继续推理
```

### 3.3 错误处理规范

```python
# Tool 执行中的错误统一包装，严禁裸抛异常

class ToolError:
    TIMEOUT = "TIMEOUT"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    GIT_CONFLICT = "GIT_CONFLICT"
    DEPLOY_FAILED = "DEPLOY_FAILED"
    MEMORY_UNAVAILABLE = "MEMORY_UNAVAILABLE"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN = "UNKNOWN"

# 错误一律通过 ToolResult 返回，不抛异常：
# ToolResult(success=False, error=ToolError.INVALID_ARGUMENTS, content="path 参数不能为空")
```

---

## 4. 域 3 需要实现的 Tool 清单

### 4.1 一览

| # | Tool | Category | requires_approval | Phase |
|---|------|----------|--------------------|-------|
| 3.1 | `memory_retrieve` | memory | false | P1 W2 |
| 3.2 | `memory_save` | memory | false | P1 W2 |
| 3.3 | `git_diff` | git | false | P2 W4 |
| 3.4 | `git_commit` | git | **true** | P2 W4 |
| 3.5 | `diff_preview` | preview | false | P3 W5 |
| 3.6 | `web_preview` | preview | false | P3 W5 |
| 3.7 | `deploy` | deploy | **true** | P3 W5-6 |
| 3.8 | `knowledge_search` | knowledge | false | P3 W6 |
| 3.9 | `knowledge_index` | knowledge | false | P3 W6 |

### 4.2 逐个定义

#### 4.2.1 `memory_retrieve`

```python
ToolDefinition(
    name="memory_retrieve",
    description="检索当前会话的上下文记忆，返回最近的对话消息和摘要",
    parameters={
        "type": "object",
        "properties": {
            "session_id":  {"type": "string", "description": "会话 ID"},
            "limit":       {"type": "integer", "default": 20, "minimum": 1, "maximum": 50},
            "memory_type": {"type": "string", "enum": ["working", "summary", "both"], "default": "working"},
        },
        "required": ["session_id"]
    },
    category=ToolCategory.MEMORY,
    permissions=[Permission.READ],
    requires_approval=False,
    max_timeout_seconds=5,
)

# ToolResult 示例
# 成功: ToolResult(success=True, content=json.dumps(messages_list), artifact=None)
# 失败: ToolResult(success=False, content=None, error="MEMORY_UNAVAILABLE")
```

#### 4.2.2 `memory_save`

```python
ToolDefinition(
    name="memory_save",
    description="将重要信息写入跨会话持久记忆，供后续会话检索",
    parameters={
        "type": "object",
        "properties": {
            "content":   {"type": "string", "description": "要保存的内容"},
            "category":  {"type": "string", "enum": ["fact", "decision", "pattern", "preference"]},
            "tags":      {"type": "array", "items": {"type": "string"}, "default": []},
            "importance":{"type": "integer", "minimum": 1, "maximum": 5, "default": 3},
        },
        "required": ["content", "category"]
    },
    category=ToolCategory.MEMORY,
    permissions=[Permission.WRITE],
    requires_approval=False,
    max_timeout_seconds=5,
)
```

#### 4.2.3 `git_diff`

```python
ToolDefinition(
    name="git_diff",
    description="查看当前项目的 Git 变更，返回 unified diff 格式。参数为空时显示所有未暂存变更",
    parameters={
        "type": "object",
        "properties": {
            "paths":    {"type": "array", "items": {"type": "string"}, "description": "要查看的文件路径列表"},
            "staged":   {"type": "boolean", "default": False},
            "base_ref": {"type": "string", "description": "对比基准 ref，如 'HEAD~1' 或 'main'"},
        },
        "required": []
    },
    category=ToolCategory.GIT,
    permissions=[Permission.READ],
    requires_approval=False,
    max_timeout_seconds=10,
)
```

#### 4.2.4 `git_commit`

```python
ToolDefinition(
    name="git_commit",
    description="提交代码变更到 Git。操作不可逆，需要人工审批",
    parameters={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "commit message"},
            "paths":   {"type": "array", "items": {"type": "string"}, "description": "要提交的文件路径"},
        },
        "required": ["message"]
    },
    category=ToolCategory.GIT,
    permissions=[Permission.WRITE],
    requires_approval=True,         # HITL 审批
    max_timeout_seconds=15,
)
```

#### 4.2.5 `diff_preview`

```python
ToolDefinition(
    name="diff_preview",
    description="生成代码变更的可视化 Diff 预览卡片。传入 unified diff 内容，返回预览 URL",
    parameters={
        "type": "object",
        "properties": {
            "diff_content": {"type": "string", "description": "unified diff 文本"},
            "title":        {"type": "string", "description": "Diff 卡片标题"},
        },
        "required": ["diff_content"]
    },
    category=ToolCategory.PREVIEW,
    permissions=[Permission.WRITE],
    requires_approval=False,
    max_timeout_seconds=10,
)

# ToolResult 示例
# 成功: ToolResult(success=True, content="Diff preview ready", 
#                  artifact="/api/preview/diff/{diff_id}")
# 失败: ToolResult(success=False, error="INVALID_ARGUMENTS", content="diff_content 为空")
```

#### 4.2.6 `web_preview`

```python
ToolDefinition(
    name="web_preview",
    description="启动开发服务器并返回网页预览 URL，在聊天窗口 iframe 中展示",
    parameters={
        "type": "object",
        "properties": {
            "project_path": {"type": "string", "description": "项目根路径"},
            "port":         {"type": "integer", "default": 5173},
            "command":      {"type": "string", "description": "启动命令，如 'npm run dev'"},
        },
        "required": ["project_path"]
    },
    category=ToolCategory.PREVIEW,
    permissions=[Permission.EXECUTE],
    requires_approval=False,
    max_timeout_seconds=30,
)

# ToolResult 示例
# 成功: ToolResult(success=True, content="Dev server started on port 5173",
#                  artifact="https://preview.agenthub.local/api/preview/web/{id}")
# 失败: ToolResult(success=False, error="NETWORK_ERROR", content="端口 5173 被占用")
```

#### 4.2.7 `deploy`

```python
ToolDefinition(
    name="deploy",
    description="一键部署到生产环境。操作不可逆，需要人工审批",
    parameters={
        "type": "object",
        "properties": {
            "build_cmd":    {"type": "string", "description": "构建命令"},
            "deploy_target":{"type": "string", "enum": ["docker", "vercel", "github_pages"], "default": "docker"},
            "env_vars":     {"type": "object", "additionalProperties": {"type": "string"}, "default": {}},
        },
        "required": []
    },
    category=ToolCategory.DEPLOY,
    permissions=[Permission.EXECUTE, Permission.NETWORK],
    requires_approval=True,         # HITL 审批
    max_timeout_seconds=300,
)

# ToolResult 示例
# 成功: ToolResult(success=True, content="Deploy successful",
#                  artifact="https://agenthub-t7h3s.ondigitalocean.app")
# 失败: ToolResult(success=False, error="DEPLOY_FAILED", content="Docker build failed: ...")
```

#### 4.2.8 `knowledge_search`

```python
ToolDefinition(
    name="knowledge_search",
    description="搜索项目知识库，返回相关文档和代码片段。用于搜索编码规范、架构文档等",
    parameters={
        "type": "object",
        "properties": {
            "query":   {"type": "string", "description": "自然语言搜索查询"},
            "top_k":   {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
            "sources": {"type": "array", "items": {"type": "string", "enum": ["rag", "living_specs", "all"]},
                        "default": ["all"]},
        },
        "required": ["query"]
    },
    category=ToolCategory.KNOWLEDGE,
    permissions=[Permission.READ],
    requires_approval=False,
    max_timeout_seconds=10,
)
```

#### 4.2.9 `knowledge_index`

```python
ToolDefinition(
    name="knowledge_index",
    description="将文档或代码片段索引到知识库，供后续语义搜索",
    parameters={
        "type": "object",
        "properties": {
            "content":  {"type": "string", "description": "要索引的文本内容"},
            "source":   {"type": "string", "description": "来源标识，如文件路径或 URL"},
            "metadata": {"type": "object", "default": {}},
        },
        "required": ["content", "source"]
    },
    category=ToolCategory.KNOWLEDGE,
    permissions=[Permission.WRITE],
    requires_approval=False,
    max_timeout_seconds=10,
)
```

---

## 5. MemoryContext 注入流程

域 3 的 L1-L4 记忆通过 `MemoryContext` 注入到 `AgentRequest` 中，域 2 的 Adapter 负责组装为 prompt。

```
每次 Agent 调用前：
  1. Harness 调用 MemoryContextBuilder
  2. MemoryContextBuilder → L1: Redis 滑动窗口取最近 20 条
  3. MemoryContextBuilder → L2: 超过阈值时查 PG 摘要
  4. MemoryContextBuilder → L3: 读 .agenthub/ 项目上下文
  5. MemoryContextBuilder → L4: 按当前意图做 pgvector Top-K
  6. 组装为 MemoryContext → 传入 AgentRequest
  7. Adapter.inject_memory(request) → 拼到 system_prompt
```

```python
# 域 3 暴露的 MemoryContextBuilder 接口
class MemoryContextBuilder:
    async def build(self, session_id: UUID, intent_hint: str = "") -> MemoryContext:
        return MemoryContext(
            l1_working=await self._get_working_memory(session_id),
            l2_summary=await self._get_summary(session_id),
            l3_specs=await self._get_living_specs(session_id),
            l4_rag=await self._rag_search(session_id, intent_hint),
        )
```

---

## 6. 域 2 提供给域 3 的回调

```python
class CallbackEvents(StrEnum):
    TOOL_EXEC_START = "tool.exec.start"       # {tool_name, arguments}
    TOOL_EXEC_DONE = "tool.exec.done"         # {tool_name, duration_ms, success}
    TOOL_EXEC_FAILED = "tool.exec.failed"     # {tool_name, error}
    TOOL_APPROVAL_REQUIRED = "tool.approval.required"  # {tool_name}
    TOOL_APPROVAL_GRANTED = "tool.approval.granted"    # {tool_name}
    TOOL_APPROVAL_REJECTED = "tool.approval.rejected"  # {tool_name}
    DEPLOY_PROGRESS = "deploy.progress"       # {stage, progress, message}
```

域 3 通过订阅 `TOOL_EXEC_*` 事件，在自己的 UI 卡片（DiffCard / DeployCard）展示实时状态，无需域 2 关心 UI 细节。

---

## 7. 验收清单（域 2 ↔ 域 3 联调）

| # | 测试场景 | 预期结果 |
|---|---------|---------|
| 1 | Agent 调用 `memory_retrieve` | 返回最近 20 条消息，延迟 < 5ms |
| 2 | Agent 调用 `memory_save` | 写入 pgvector，下次检索可召回 |
| 3 | Agent 调用 `git_diff` | 返回 unified diff 文本 |
| 4 | Agent 调用 `git_commit` | 触发 HITL 弹窗，用户确认后提交成功 |
| 5 | Agent 调用 `diff_preview` | artifact 返回有效预览 URL，卡片渲染正确 |
| 6 | Agent 调用 `web_preview` | Dev Server 启动，iframe 可访问 |
| 7 | Agent 调用 `deploy` | 触发审批 → Docker build → 返回生产 URL |
| 8 | Agent 调用 `knowledge_search` | 返回 Top-K 结果，包含 source 和分数 |
| 9 | Tool 超时 | 返回 TIMEOUT 错误，不阻塞 Agent 后续推理 |
| 10 | HITL 拒绝 `git_commit` | 返回 PERMISSION_DENIED，Agent 收到错误继续推理 |

---

## 8. 版本管理

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.1 | 2026-05-21 | 初稿：UnifiedAgent + Tool 协议 + 9 个 Tool 定义 + MemoryContext + 验收清单 |

**下一步**：域 3 审查本协议后，域 2 在 `backend/app/adapters/base.py` 落地 `UnifiedAgent` 和 `BaseTool` 抽象类，域 3 在 `backend/app/tools/` 下实现本域 Tool。
