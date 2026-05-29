# StructuredContext — 分层上下文设计（⚠️ 已否决）

> **2026-05-23 【已否决】** — DOC-17 否定了全量替换方案。v4 改用 `AgentRequest` 新增 3 个可选增强字段替代 6 层 StructuredContext。实现参考 `PRD_AgentHub_v4_统一方案.md` §四。
>
> 6 层分层思想保留为长期参考，不作为当前实现依据。
>
> 版本：v1.0 | 日期：2026-05-23 | 基于 DOC-15 + adapter_interface_spec.md v0.2

---

## 一、问题

API 模式和 CLI 模式所需的上下文数据相同（身份、对话历史、工具、记忆），但当前散落在 `AgentRequest` 的多个字段 + `memory` 子结构中，CLI 模式只取最后一条用户消息，其余全部丢弃。每加一种新上下文（skills、group peers）就要改接口。

## 二、设计

将上下文收敛为显式的 **6 层结构体**，ChatService 负责填充，适配器只负责格式化。

```
┌─────────────────────────────────────────────────┐
│  StructuredContext   （L3 组装完成，整体传入适配器） │
│                                                  │
│  ┌─ identity ──────── 身份与角色 ──────────────┐ │
│  ├─ conversation ──── 对话历史 ────────────────┤ │
│  ├─ capabilities ──── 工具 + 技能 ─────────────┤ │
│  ├─ memory ────────── L2/L3/L4 记忆 ──────────┤ │
│  ├─ project ───────── 项目上下文 ──────────────┤ │
│  └─ params ────────── 调用参数 ────────────────┤ │
│                                                  │
│  每层独立 ownership（谁填）、独立修改、独立格式化   │
│  API 拆为 SDK 参数，CLI 拼为文本字符串             │
└─────────────────────────────────────────────────┘
```

## 三、各层定义

```python
from pydantic import BaseModel


# ===== 1. 身份层 =====
# ownership: AgentService.get_identity(agent_id, group_id)
# 数据源: Agent 实体 + Group 实体

class PeerInfo(BaseModel):
    name: str                                # "BackendAgent"
    role: str                                # "后端开发专家"
    capabilities: list[str] = []             # ["python", "fastapi"]

class IdentityContext(BaseModel):
    agent_name: str                          # "FrontendAgent"
    agent_role: str                          # "前端开发专家"
    system_prompt: str | None = None         # Agent 自定义 system_prompt
    group_name: str | None = None            # 私聊为 None
    group_role: str = "member"               # "member" / "coordinator"
    coordinator_name: str | None = None      # 协调者标识
    peers: list[PeerInfo] = []               # 群聊时填充


# ===== 2. 对话层 =====
# ownership: ChatService
# 数据源: L1 Redis 滑动窗口 + pinned + 当前消息

class MessageRecord(BaseModel):
    role: str                                # user / assistant / system
    content: str
    sender_name: str | None = None           # 群聊时 Agent 名
    mentions: list[str] | None = None        # @了谁

class ConversationContext(BaseModel):
    recent_messages: list[MessageRecord]     # 最近 N 条（<=20）
    pinned_messages: list[MessageRecord] = [] # Pin 的消息
    current_user_message: str                # 本轮用户输入


# ===== 3. 能力层 =====
# ownership: ToolRegistry + SkillRegistry
# 数据源: 域3 Tool Registry / 域2 Skill Registry

class ToolDefinition(BaseModel):
    name: str                                # "memory_retrieve"
    description: str                         # "检索会话上下文记忆..."
    parameters_schema: dict[str, Any]        # JSON Schema
    category: str                            # "memory" / "git" / "preview"
    requires_approval: bool = False

class SkillDefinition(BaseModel):
    name: str                                # "code-review"
    description: str                         # "审查代码变更..."
    trigger_keywords: list[str] = []         # ["code review", "审查代码"]

class CapabilityContext(BaseModel):
    tools: list[ToolDefinition] = []
    skills: list[SkillDefinition] = []


# ===== 4. 记忆层 =====
# ownership: MemoryContextBuilder (域3)
# 数据源: L2 PG 摘要 / L3 docs/.agenthub/ / L4 pgvector

class MemoryContext(BaseModel):
    l1_working: list[dict] = []              # Redis 滑动窗口
    l2_summary: str | None = None            # 超长历史压缩摘要
    l3_specs: str | None = None              # docs/.agenthub/ 项目上下文
    l4_rag: str | None = None                # pgvector Top-K


# ===== 5. 项目层 =====
# ownership: ProjectContext (域3)
# 数据源: docs/.agenthub/ 目录

class ProjectContext(BaseModel):
    workspace_dir: str                       # Agent 工作空间路径
    specs: str | None = None                 # 项目规格摘要
    rules: list[str] = []                    # 生效的规则摘要


# ===== 6. 调用参数 =====
# ownership: Agent.settings
# 数据源: Agent 实体 settings 字段

class CallParams(BaseModel):
    max_tokens: int = 16000
    temperature: float = 0.7
    thinking_enabled: bool = False
    thinking_budget: int = 4000
    timeout: int = 300                       # CLI 模式超时（秒）


# ===== 组装 =====

class StructuredContext(BaseModel):
    request_id: str                          # 全链路追踪
    session_id: UUID
    identity: IdentityContext
    conversation: ConversationContext
    capabilities: CapabilityContext = CapabilityContext()
    memory: MemoryContext = MemoryContext()
    project: ProjectContext | None = None
    params: CallParams = CallParams()
```

## 四、组装流程

```
ChatService.send_and_stream()
  │
  ├─ 1. 持久化用户消息 + 写 L1
  │
  ├─ 2. 组装 StructuredContext
  │     │
  │     ├─ identity = self._agent_svc.get_identity(agent_id, session)
  │     │
  │     ├─ conversation = self._build_conversation(session, cmd)
  │     │     ├─ recent_messages ← L1 MemoryStore.get_window()
  │     │     ├─ pinned_messages ← MessageRepo.get_pinned(session_id)
  │     │     └─ current_user_message ← cmd.content
  │     │
  │     ├─ capabilities = self._tool_registry.get_for_agent(agent_id)
  │     │                 + self._skill_registry.get_for_group(group_id)
  │     │
  │     ├─ memory = self._memory_builder.build(session_id, intent_hint)
  │     │
  │     ├─ project = self._project_ctx.get_for_agent(agent_id)
  │     │
  │     └─ params = self._agent_svc.get_params(agent_id)
  │
  └─ 3. UnifiedAgent.stream(StructuredContext)
```

## 五、适配器消费

### API 模式：拆解为 Anthropic SDK 参数

```python
# ClaudeAdapter
def _to_api_kwargs(self, ctx: StructuredContext) -> dict:
    system = self._format_system_prompt(ctx)
    messages = self._format_messages(ctx)
    tools = self._format_tool_schemas(ctx)
    return {
        "model": self._model,
        "max_tokens": ctx.params.max_tokens,
        "temperature": ctx.params.temperature,
        "system": system,
        "messages": messages,
        "tools": tools,
    }

def _format_system_prompt(self, ctx: StructuredContext) -> str:
    parts = [ctx.identity.system_prompt or ""]
    if ctx.memory.l2_summary:
        parts.append(f"## 对话摘要\n{ctx.memory.l2_summary}")
    if ctx.memory.l4_rag:
        parts.append(f"## 相关知识\n{ctx.memory.l4_rag}")
    # tools / skills 以 function calling 方式透出，不放入 system prompt
    return "\n\n".join(filter(None, parts))

def _format_messages(self, ctx: StructuredContext) -> list[dict]:
    conv = ctx.conversation
    return [
        {"role": m.role, "content": m.content}
        for m in conv.recent_messages
    ]
```

### CLI 模式：拼接为纯文本

```python
# ClaudeCodeRuntime
def _to_cli_prompt(self, ctx: StructuredContext) -> str:
    sections = []

    # 身份层
    sections.append(self._format_identity(ctx.identity))

    # 项目层
    if ctx.project:
        sections.append(self._format_project(ctx.project))

    # 记忆层（L3 specs / L2 summary / L4 rag）
    sections.append(self._format_memory(ctx.memory))

    # 能力层（文本描述，因为 CLI 不支持 function calling）
    if ctx.capabilities.tools or ctx.capabilities.skills:
        sections.append(self._format_capabilities(ctx.capabilities))

    # 对话层
    sections.append(self._format_conversation(ctx.conversation))

    return "\n\n".join(filter(None, sections))

def _format_identity(self, id_ctx: IdentityContext) -> str:
    lines = [
        f"## 你的身份",
        f"你是 {id_ctx.agent_name}，{id_ctx.agent_role}。",
    ]
    if id_ctx.group_name:
        lines.append(f"\n当前在「{id_ctx.group_name}」群聊中。你的角色是 **{id_ctx.group_role}**。")
        if id_ctx.peers:
            lines.append("其他成员：")
            for p in id_ctx.peers:
                caps = ", ".join(p.capabilities)
                lines.append(f"- **{p.name}**: {p.role}，擅长 [{caps}]")
        lines.append("\n行为规则：")
        lines.append("- 收到 @你的消息或分配给你的任务时，执行并回复")
        lines.append("- 收到 @All 消息时，根据自身能力判断是否响应")
        lines.append("- 其他 Agent 的对话不需要你响应，除非包含对你的 @")
    return "\n".join(lines)

def _format_conversation(self, conv: ConversationContext) -> str:
    lines = []
    if conv.pinned_messages:
        lines.append("## 长期上下文（已 Pin）")
        for m in conv.pinned_messages:
            sender = m.sender_name or m.role
            lines.append(f"**{sender}**: {m.content}")
        lines.append("")
    lines.append("## 对话历史")
    for m in conv.recent_messages:
        sender = m.sender_name or m.role
        mentions = ""
        if m.mentions:
            mentions = f" (@{' @'.join(m.mentions)})"
        lines.append(f"**{sender}**{mentions}: {m.content}")
    lines.append("")
    lines.append(f"## 当前消息\n{conv.current_user_message}")
    lines.append("\n请基于以上上下文，给出你的回复。")
    return "\n".join(lines)

def _format_capabilities(self, cap: CapabilityContext) -> str:
    lines = ["## 可用工具"]
    for t in cap.tools:
        safety = "[需审批] " if t.requires_approval else ""
        lines.append(f"- **{t.name}**: {safety}{t.description}")
    if cap.skills:
        lines.append("\n## 可用技能")
        for s in cap.skills:
            triggers = ", ".join(s.trigger_keywords)
            lines.append(f"- **{s.name}**: {s.description}（触发词: {triggers}）")
    return "\n".join(lines)
```

## 六、与 AgentRequest 的关系

`StructuredContext` 替代 `AgentRequest`——不是在其基础上包装，而是直接替换。

```
当前  → 统一接口拆分为 LLMAdapter / AgentRuntime 后废弃 AgentRequest

protocol.py 变更:
  - 删除 AgentRequest
  + 新增 StructuredContext + 各层子结构体
  - LLMAdapter.stream(request: AgentRequest)
  + LLMAdapter.stream(ctx: StructuredContext)
  - AgentRuntime.stream(request: AgentRequest)
  + AgentRuntime.stream(ctx: StructuredContext)
```

## 七、实施步骤

| # | 变更 | 范围 |
|---|------|------|
| 1 | `protocol.py` — 新增 `StructuredContext` + 6 层子结构体，替换 `AgentRequest` | domain |
| 2 | `chat_service.py` — 组装逻辑改为填充 `StructuredContext` 各层 | application |
| 3 | `claude_adapter.py` — 消费 `StructuredContext`，格式化逻辑不变 | infrastructure |
| 4 | `claude_code_runtime.py` — 从"只取最后一条"改为消费完整 `StructuredContext` | infrastructure |
| 5 | `mock_adapter.py` — 适配新接口 | infrastructure |
| 6 | 测试更新 | tests |

