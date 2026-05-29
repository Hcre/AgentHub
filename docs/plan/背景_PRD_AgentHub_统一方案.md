# AgentHub PRD v4.0 — 统一方案

> v3 与 ADR-01 冲突裁决后合并 | 2026-05-23
> 变更摘要：记忆注入改为每次注入、适配器命名统一为 AgentRuntime、Skills 文件系统+Registry 共存、Celery 砍掉

---

## 一、产品定义

IM 聊天式多 Agent 协作平台。用户创建 Agent（选系统 + 配模型 + 设 System Prompt / Skills）、拉群、像飞书一样 @Agent 下达任务。复杂 coding 任务走 CLI 子进程模式（完整工具生态），Coordinator 分解走 SDK 模式（轻量结构化输出）。代码 Diff、网页预览在聊天流中内联展示。

### 核心决策（v3 → v4 变更标记）

| 决策 | v4 | v3 | 变更 |
|------|-----|-----|------|
| Agent 接入 | SDK + CLI 双模式 | 同 | — |
| CLI 适配器 | `ClaudeCodeRuntime(AgentRuntime)` | `ClaudeCLIAdapter(UnifiedAgent)` | **改名 + 基类抽象** |
| 记忆注入 | **每次调用注入** `StructuredContext` | 仅首次写入 `CLAUDE.md` | **以 ADR-01 为准** |
| Skills | 文件系统 + SkillRegistry **共存** | 仅文件系统 | **合并** |
| 多 Agent 编排 | Coordinator 分解 + `asyncio.gather` | 同（砍掉 Celery） | — |
| 记忆系统 | L1 滑动窗口 + L2 摘要 | 同 | — |
| Session 管理 | SessionStore(Redis) + 双路径历史 | 未涉及 | **补入 ADR-01 方案** |

### 与 ADR-01 的冲突裁决

| 冲突项 | 裁决 | 理由 |
|--------|------|------|
| 记忆注入策略 | **每次注入**（ADR-01） | 群聊场景需要动态上下文（新成员、新摘要、RAG），仅首次写入不够 |
| 适配器命名/基类 | **ClaudeCodeRuntime + AgentRuntime**（ADR-01） | 可扩展，接 Codex/Trae 不复制代码 |
| Skills 管理 | **共存**（文件系统 + SkillRegistry） | 静态 skills 走文件，动态 skills 走 Registry |

---

## 二、最终架构

```
┌─────────────────────────────────────────────────────────────────┐
│  L5  Presentation（React + TypeScript）                          │
│  ChatView / AgentCreate / TaskBoard / GroupChat                  │
│  Stores: chatStore / agentStore / groupStore / taskStore          │
└──────────────────────────────┬────────────────────────────────────┘
                               │ WS + REST
┌──────────────────────────────┴────────────────────────────────────┐
│  L4  API Gateway（FastAPI）                                        │
│  /api/agents  /api/groups  /api/sessions  /api/tasks  /ws/sessions│
└──────────────────────────────┬────────────────────────────────────┘
                               │ Command / StructuredContext
┌──────────────────────────────┴────────────────────────────────────┐
│  L3  Application                                                  │
│  AgentService / GroupService / ChatService / CoordinatorService   │
│  ContextBuilder: 组装 AgentRequest（基础字段 + CLI 增强字段）      │
│  SessionStore(Redis): 维护 AgentHub session ↔ CLI session 映射    │
└──────────────────────────────┬────────────────────────────────────┘
                               │ Domain Object
┌──────────────────────────────┴────────────────────────────────────┐
│  L2  Domain                                                       │
│  Agent / Group / Session / Message / Task (聚合根)                 │
│  TaskFSM (8状态) / Coordinator / Harness / LoopGuard              │
│  UnifiedAgent = LLMAdapter | AgentRuntime                         │
│  AgentRequest + CLI 增强字段 / StreamEvent (8 种)                  │
└──────────┬────────────────────────────────────────────────────────┘
           │ Repository / Adapter Interface
┌──────────┴────────────────────────────────────────────────────────┐
│  L1  Infrastructure                                                │
│                                                                     │
│  PG (6表)      Redis            LLM 双轨                            │
│                · sliding window  ┌── LLMAdapter (API) ──────────┐  │
│                · session store   │ ClaudeAdapter                  │  │
│                · pub/sub         │ → Anthropic Messages API       │  │
│                                  └────────────────────────────────┘  │
│                                  ┌── AgentRuntime (CLI) ─────────┐  │
│                                  │ ClaudeCodeRuntime              │  │
│                                  │ · per-agent 独立 env vars       │  │
│                                  │ · per-agent 独立 work dir       │  │
│                                  │ · --resume 维持长对话           │  │
│                                  │ · .claude/skills/ 文件落地      │  │
│                                  │ · StructuredContext 每轮注入    │  │
│                                  └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 表：6 表（同 v3）

| 表 | 说明 |
|----|------|
| `agents` | 核心。`capability_tags TEXT[]`，`skills TEXT[]`，`agent_system`，`settings JSONB` |
| `groups` | 核心 |
| `group_members` | 核心 |
| `sessions` | 核心。`summary TEXT` 存长对话摘要 |
| `messages` | 核心 |
| `tasks` | 核心。`status` 替代 task_events 表 |

---

## 三、双轨适配器（v4 统一命名）

### 3.1 类层级

```
UnifiedAgent (ABC)
    ├── LLMAdapter (ABC)          ← API 模式：AgentHub 自建 Harness
    │   ├── ClaudeAdapter          (Anthropic API — 已实现)
    │   └── OpenAICompatAdapter   (未来)
    │
    └── AgentRuntime (ABC)        ← CLI 模式：复用 CLI 自带 Harness
        ├── ClaudeCodeRuntime      (Claude Code CLI — P0 当前)
        ├── CodexRuntime           (未来)
        └── TraeRuntime            (未来)
```

### 3.2 两种模式定位

| | LLMAdapter (API) | AgentRuntime (CLI) |
|------|------|------|
| **适用场景** | Coordinator 结构化分解、简单问答 | 复杂 coding（读写文件、git、bash） |
| **工具能力** | 仅 function calling | CLI 内置 55+ 工具 + MCP + Skills |
| **Tool loop** | AgentHub 编排 | CLI 内部完成 |
| **状态管理** | 无状态，每次调用全量传 | 有状态，`--resume` sqlite 持久化 |
| **Coordinator** | ✅ 用此模式（`chat_structured`） | ❌ 不支持结构化输出 |

### 3.3 单机多 Agent 不同配置

```python
# Agent "前端专家" → DeepSeek
Agent "FrontendExpert":
  env: {
    ANTHROPIC_API_KEY=sk-deepseek-xxx,
    ANTHROPIC_BASE_URL=http://localhost:3457/v1,
    ANTHROPIC_MODEL=deepseek-v3,
  }
  work_dir: /tmp/agenthub/sessions/{agent_id}/

# Agent "后端专家" → Claude Sonnet
Agent "BackendExpert":
  env: {
    ANTHROPIC_API_KEY=sk-ant-xxx,
    ANTHROPIC_MODEL=claude-sonnet-4-20250514,
  }
  work_dir: /tmp/agenthub/sessions/{agent_id}/

# Agent "代码审查员" → Qwen（LiteLLM 中转）
Agent "Reviewer":
  env: {
    ANTHROPIC_API_KEY=sk-qwen-xxx,
    ANTHROPIC_BASE_URL=http://localhost:3457/v1,
    ANTHROPIC_MODEL=qwen-max,
  }
  work_dir: /tmp/agenthub/sessions/{agent_id}/
```

每个 CLI 子进程独立 env vars、独立 work_dir，完全隔离。

### 3.4 接口签名

```python
# domain/llm/protocol.py

class AgentRequest(BaseModel):
    """统一请求结构体。私聊仅需基础字段，群聊/M3 渐进启用 CLI 增强字段。

    CLI 增强字段为预格式化文本块，ChatService/ContextBuilder 负责语义组装，
    适配器只负责按目标协议拼接（CLI）或拆解（API），不感知语义。
    """
    # === 基础字段 ===
    request_id: str
    session_id: UUID
    messages: list[dict]               # [{"role": "user/assistant", "content": "..."}]
    system_prompt: str | None = None
    memory: MemoryContext | None = None
    available_tools: list[str] = []
    max_tokens: int = 16000
    temperature: float = 0.7

    # === CLI 增强字段（全部可选，默认 None） ===
    identity_prompt: str | None = None     # ChatService 组装身份描述文本块
    capability_prompt: str | None = None   # ChatService 组装工具+技能文本块
    peer_context: str | None = None        # ChatService 组装其他 Agent 消息文本块


class UnifiedAgent(ABC):
    """所有 Agent 适配器的统一接口。调用方只依赖此抽象。"""

    @abstractmethod
    def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        """流式执行，逐事件 yield。签名不变，AgentRequest 渐进扩展。"""
        ...

    @abstractmethod
    async def chat_structured(self, prompt: str) -> dict:
        """非流式结构化调用（Coordinator 分解用）。"""
        ...


class LLMAdapter(UnifiedAgent, ABC):
    """API 模式基类：无状态 HTTP/SDK 调用。AgentHub 自建 Harness。"""
    pass


class AgentRuntime(UnifiedAgent, ABC):
    """CLI 模式基类：有状态子进程管理。复用 CLI 自带 Harness。

    额外生命周期方法：
    - kill(session_id): 优雅终止子进程
    - send_decision(session_id, decision): HITL 审批决策回写 stdin
    """

    @abstractmethod
    async def kill(self, session_id: UUID) -> None: ...

    @abstractmethod
    async def send_decision(self, session_id: UUID, decision: str) -> None: ...
```

**适配器消费方式：**

```python
# API 模式：拆解为 SDK 参数
class ClaudeAdapter(LLMAdapter):
    def _to_api_kwargs(self, request: AgentRequest) -> dict:
        system = request.system_prompt or ""
        if request.identity_prompt:
            system = request.identity_prompt + "\n\n" + system
        if request.memory and request.memory.l2_summary:
            system += f"\n\n## 对话摘要\n{request.memory.l2_summary}"
        return {
            "model": self._model,
            "max_tokens": request.max_tokens,
            "system": system,
            "messages": request.messages,
        }

# CLI 模式：拼接为文本字符串
class ClaudeCodeRuntime(AgentRuntime):
    def _to_cli_prompt(self, request: AgentRequest) -> str:
        parts = [p for p in (
            request.identity_prompt,
            request.capability_prompt,
            request.peer_context,
        ) if p]
        parts.append(request.messages[-1]["content"])
        return "\n\n".join(parts)
```

**ChatService 调用（不变）：**

```python
# 私聊：仅基础字段
request = AgentRequest(
    request_id=str(uuid.uuid4()),
    session_id=session_id,
    messages=window,
    identity_prompt=identity_prompt,  # M2 新增
)
async for event in llm.stream(request):
    yield event

# 群聊（M3）：加上 peer_context + capability_prompt
request = AgentRequest(
    ...,
    identity_prompt=identity_prompt,
    capability_prompt=capability_prompt,
    peer_context=peer_context,
)
```

---

## 四、上下文注入（v4 关键变更）

### 4.1 变更：从「注入一次」到「每次注入」

v3 策略是首次 session 创建时写入 `CLAUDE.md`，之后不再干预。v4 改为通过 `StructuredContext` 每轮完整拼接，理由见 ADR-01 §5.2。

### 4.2 AgentRequest 增强字段

v4 不采用 DOC-16 的 StructuredContext 全量替换方案（该方案已被 DOC-17 否定）。改为在现有 `AgentRequest` 上新增 3 个可选文本字段，ChatService 负责组装为预格式化文本块，适配器只做拼接/拆解。

```python
class AgentRequest(BaseModel):
    # === 基础字段（所有模式必需，已有，不变） ===
    request_id: str
    session_id: UUID
    messages: list[dict]
    system_prompt: str | None = None
    memory: MemoryContext | None = None
    available_tools: list[str] = []
    max_tokens: int = 16000
    temperature: float = 0.7

    # === CLI 增强字段（M2 私聊 → M3 群聊渐进启用，全部可选，默认空） ===
    identity_prompt: str | None = None     # 身份描述文本块
    capability_prompt: str | None = None   # 工具+技能描述文本块
    peer_context: str | None = None        # 其他 Agent 消息文本块（群聊）
```

**为什么是 3 个 `str | None` 而不是 6 层 StructuredContext：**
- M2 私聊只需 `identity_prompt`，其余字段空——6 层结构体会产生大量空壳
- 新字段全有默认值，现有代码零破坏——ChatService、适配器、测试都不需要改
- M3 群聊按需加 `peer_context` + `capability_prompt`，M4 记忆增强时字段可从 `str` 升级为结构化子类型
- ChatService 负责语义组装，适配器只管文本拼接——职责边界清晰

**各字段数据源与组装者：**

| 字段 | 组装者 | 数据源 | 启用阶段 |
|------|--------|--------|---------|
| `identity_prompt` | `ContextBuilder` | Agent 实体 + Group 上下文 | M2 私聊 |
| `capability_prompt` | `ContextBuilder` | ToolRegistry + SkillRegistry | M3 群聊 |
| `peer_context` | `ContextBuilder` | 群聊其他 Agent 最近消息 | M3 群聊 |

### 4.3 CLI 模式格式化

```python
# ClaudeCodeRuntime
def _to_cli_prompt(self, request: AgentRequest) -> str:
    sections = []

    # 身份层：Agent 角色 + 群组上下文
    if request.identity_prompt:
        sections.append(request.identity_prompt)

    # 能力层：工具 + Skills 文本描述
    if request.capability_prompt:
        sections.append(request.capability_prompt)

    # 群聊上下文：其他 Agent 消息
    if request.peer_context:
        sections.append(request.peer_context)

    # 记忆层：L2 摘要
    if request.memory and request.memory.l2_summary:
        sections.append(f"## 对话摘要\n{request.memory.l2_summary}")

    # 当前用户消息（取 messages 最后一条）
    user_content = request.messages[-1]["content"] if request.messages else ""
    sections.append(user_content)

    return "\n\n".join(filter(None, sections))
```

### 4.4 记忆分工

```
AgentHub 记忆系统（每次注入到 AgentRequest）
  L1 Redis 滑动窗口 (最近 20 条) → messages 字段
  L2 PG 摘要 (长对话压缩)       → memory.l2_summary
  L3 .agenthub/ 项目上下文       → memory.l3_specs
  L4 pgvector RAG (M4)          → memory.l4_rag

Claude Code CLI 内部（进程内自动管理）
  对话历史 (messages[] 数组)
  CLAUDE.md（系统级上下文，首次创建 + 每次可被 AgentHub 覆盖）
  Skills 文件 (.claude/skills/)
  JSONL session 文件 (--resume 恢复)
```

**关键原则**：
- AgentHub 管理"跨会话"状态，**每轮注入**最新值
- CLI 自己管理"对话内"状态
- Skills 文件在 Agent 创建时写入，后续 AgentHub 可增量更新
- 两个系统通过文件系统（Skills）和 prompt 文本文本交换信息

---

## 五、Skills：文件系统 + Registry 共存

| 渠道 | 适用于 | 机制 |
|------|--------|------|
| **文件系统** `.claude/skills/` | 静态 Skills（代码规范、框架指南、设计系统） | Agent 创建时复制 `.md` 文件到 workspace |
| **SkillRegistry**（AgentHub） | 动态 Skills（运行时注册、跨 Agent 共享、统计） | `CapabilityContext.skills` 每轮拼入 prompt |

不互斥：
- 静态 Skill 走文件系统（CLI 自动加载，零 AgentHub 干预）
- AgentHub 维护 SkillRegistry 做展示和选择
- 两者通过 skill name 对齐（文件名为 `{name}.md`，registry 中 key 为 name）

---

## 六、Session 管理（ADR-01 方案）

### 6.1 SessionStore（Redis）

```
Redis key:
  cli_session:{session_id}    → {session_id, agent_id, workspace_dir, created_at, updated_at}
  cli_sessions:{agent_id}     → 反向索引集合

TTL: 7 天，每次对话刷新
首次创建 register()，后续 touch()，删除 remove()
```

### 6.2 消息历史双路径

| 端点 | 数据源 | 用途 |
|------|--------|------|
| `GET /api/sessions/{id}/messages` | AgentHub PG | 快速列表 |
| `GET /api/sessions/{id}/history` | CLI `~/.claude/sessions/{id}/transcript.jsonl` | 完整回放（含 tool_call/thinking） |

### 6.3 Session 生命周期

```
首条消息 → --session-id UUID-A（新建）→ SessionStore.register()
后续消息 → --resume UUID-A（恢复）→ SessionStore.touch()
WS 断开  → 延迟 30s kill，30s 内重连复用同一进程
删除 Session → SessionStore.remove() + 清理 CLI 文件（或靠 7 天 TTL）
```

---

## 七、完整流程 Walkthrough

### 流程零：环境准备

```
docker compose up -d postgres redis
make dev
# 浏览器 http://localhost:5173
```

### 流程一：创建 Agent（卡片式配置）

用户填写 Agent 卡片：名称、系统(Claude Code)、Provider(DeepSeek/Anthropic/Zhipu)、Model、API Key、System Prompt、Skills 多选、权限模式。

后端处理：
1. 校验 name 唯一性
2. AES-256-GCM 加密 API Key
3. 创建 Agent 聚合根
4. 如果 `agent_system == "claude_code"`：
   - 创建 work_dir: `/tmp/agenthub/sessions/{agent_id}/`
   - 复制选中的 skill 文件到 `.claude/skills/`
   - 写入初始 `CLAUDE.md`（含 system_prompt）
5. 持久化到 agents 表
6. 发布 AgentCreated 事件

### 流程二：创建群聊（自动生成 Coordinator）

```python
# GroupService.create()
# 1. 创建 Group(id=g1, name="全栈开发组")
# 2. 自动创建 Coordinator Agent（AgentSystem.ANTHROPIC_API，用 SDK 模式做结构化分解）
# 3. 初始成员 + Coordinator 加入 group_members
# 4. 发布 GroupCreated + AgentCreated(coordinator)
```

Coordinator 固定用 SDK 模式（`chat_structured` 需要结构化输出，CLI 不支持）。

### 流程三：群聊实际对话

1. 用户发送消息
2. ChatService 持久化 + 写 L1
3. 意图检测 → 任务意图 → 触发 Coordinator
4. Coordinator（SDK 模式，轻量）调用 `chat_structured()` → 分解为子任务 JSON
5. Harness 校验（环检测 + Worker 路由）
6. `asyncio.gather` 并发执行各子任务
7. 每个子任务：选 CLI/SDK adapter → `stream(StructuredContext)` → WS 实时推送
8. 前端渲染：协调者任务卡片 + 多 Worker 流式输出

### 流程四：记忆系统工作

每次 `ChatService.send_and_stream()`：
1. `ContextBuilder.build(session_id)` 组装 `AgentRequest`（基础字段 + CLI 增强字段）
2. 传入 `ClaudeCodeRuntime.stream(request)` 或 `ClaudeAdapter.stream(request)`
3. CLI 模式：`_to_cli_prompt(request)` 拼接增强字段 + 当前消息 → 传入 `-p`
4. API 模式：`_to_api_kwargs(request)` 拆解为 `{system, messages, tools, params}`

v4 区别：**每次调用都注入最新记忆**，不只在首次。

### 流程五：Loop Guard

```python
class LoopGuard:
    def __init__(self, max_consecutive_agent_messages=5):
        self.max_consecutive = max_consecutive

    def check(self, recent_messages: list[Message]) -> bool:
        agent_count = 0
        for msg in reversed(recent_messages):
            if msg.role == "assistant" and msg.mentions:
                agent_count += 1
            else:
                break
        if agent_count >= self.max_consecutive:
            return False
        return True
```

---

## 八、里程碑计划

| 里程碑 | 时间 | 核心交付 |
|--------|------|---------|
| **M1** 环境+验证 | 5/20-22 (已完成) | 脚手架 + SDK ClaudeAdapter + PG/Redis |
| **M2** 单聊 MVP | 5/23-27 (当前) | SDK + CLI 双模式，Agent 卡片式创建，Skills 选择，1v1 私聊，StructuredContext 组装，SessionStore |
| **M3** 群聊+协调者 | 5/28-6/1 | 群组创建、Coordinator 分解、@mention 路由、asyncio.gather 并发、Loop Guard |
| **M4** 产物预览 | 6/2-5 | DiffCard、PreviewCard、Pin 上下文、L2 摘要压缩 |
| **M5** 打磨 | 6/6-9 | Demo 视频、UI 细节、端到端测试 |
| **M6** 提交 | 6/10 | 仓库整理 |

---

## 九、需要新增/修改的文件

### 新增

```
src/backend/app/infrastructure/llm/runtimes/
  _base.py                    # AgentRuntime 基类（子进程管理）
  claude_code.py              # ClaudeCodeRuntime
src/backend/app/infrastructure/cache/session_store.py    # SessionStore (Redis)
src/backend/app/application/services/coordinator_service.py
src/backend/app/application/services/context_builder.py  # StructuredContext 组装

src/frontend/src/components/agent/AgentCreateForm.tsx
src/frontend/src/components/chat/GroupChatView.tsx
src/frontend/src/components/chat/TaskPlanCard.tsx
```

### 修改

```
src/backend/app/domain/llm/protocol.py       # +LLMAdapter +AgentRuntime ABC
src/backend/app/infrastructure/llm/factory.py # +claude_code 分支
src/backend/app/application/services/chat_service.py  # StructuredContext 组装 + mode 感知
src/backend/app/domain/task_engine/harness.py         # asyncio.gather + LoopGuard
```

### 可删除

```
src/backend/app/infrastructure/queue/        # Celery 相关
```

---

## 十、相关文档

| 文档 | 内容 |
|------|------|
| `ADR-01-cli-first-pivot.md` | 架构决策记录：API→CLI 重心转移 + Session 管理方案 |
| `DOC-15-claude-adapter-design.md` v1.2 | 双轨架构详细设计 |
| `DOC-17-context-injection-problem.md` | CLI 模式上下文注入问题分析 |
| `PRD_AgentHub_v3_完整流程方案.md` | v3 版本（被本版本取代） |
| `架构设计_分层与数据流.md` | §2.0 StructuredContext + §2.1 双轨架构 |

> `DOC-16-structured-context-design.md` 的全量替换方案已被 DOC-17 否定，v4 采用 `AgentRequest` 增强字段方案。DOC-16 的 6 层分层思路保留为长期参考，当前不作为实现依据。

---

*版本: v4.0 | 日期: 2026-05-23 | 变更: v3 与 ADR-01 冲突裁决合并*
