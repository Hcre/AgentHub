# AgentHub PRD v4.0 — 统一方案

> v3 与 ADR-01 冲突裁决后合并 | 2026-05-23
> 变更摘要：记忆注入改为每次注入、适配器命名统一为 AgentRuntime、Skills 文件系统+Registry 共存、Celery 砍掉

---

## 实施进度速览（增量附录 · 2026-06-07）

> 段落定位：本文档为 v4.0 冻结版，2026-05-23 后所有新增落地均通过 ADR + worklog 沉淀（不回头改 v4.0 原文）。本段补充当前实施进度快照，便于答辩前对账。

| 维度 | v4.0 规划 | 当前状态（2026-06-07） | 证据 |
|------|---------|---------------------|------|
| **M1 环境+验证** | 脚手架 + SDK ClaudeAdapter + PG/Redis | ✅ 完成 | STATUS 董/袁/黎均无此行 |
| **M2 单聊 MVP** | SDK + CLI 双模式、Agent 卡片创建、Skills 选择、1v1 私聊、SessionStore | ✅ 完成 | ADR-01/02、 `docs/specs/04-commands` §私聊契约、PR #16 合并 |
| **M3 群聊+协调者** | 群组创建、Coordinator 分解、@mention 路由、`asyncio.gather` 并发、Loop Guard | ✅ 完成 | 群聊全栈实现、CLI 多模型代理、前端群聊 |
| **M4 产物预览** | DiffCard、PreviewCard、Pin 上下文、L2 摘要压缩 | ✅ 主体完成；Inbox 视觉 M4 TODO | `docs/deliverables/integration-verify-report.md` 5/6 PASS（A/B/C/D/F）；E Inbox 视觉 downscope（ADR-0010）|
| **M5 打磨** | Demo 视频、UI 细节、端到端测试 | 🚧 进行中（roadmap §8 P0 收尾冲刺） | `docs/plan/开发清单_roadmap.md` §8 必修 P0（6 项：3 已落实 / 1 部分 / 2 关键缺口） |
| **MCP 扩展（后续）** | 不在 v4.0 范围 | ✅ F1+F2 已并入 main；P3/P4 接力（ADR-09 cron 兜底） | `docs/reports/收束报告-MCP-F1.md` + F2；MCP P3 F3 创建 6/6-6/8 排期 |
| **桌面 App 转向** | 不在 v4.0 范围 | 🚧 规格冻结中（PR-01 2 人 Review 待答） | ADR-0007 Tauri 2 + M2 瘦客户端 + GitHub Releases；`docs/specs/06-desktop-app_桌面App规格.md` |
| **技术债** | v4.0 未盘点 | 7 项（roadmap §8 + STATUS 技术债段）| P0-3 multipart / P0-4 Pin UI / P0-5 复制代码文案 / 套件测试隔离 / etc. |

**关键里程碑统计**（2026-05-22 → 2026-06-07）：

- **代码量**：`src/backend/app/` 5 层洋葱 + `src/frontend/src/` React 19 + Vite + Tailwind 4（具体行数见 `docs/CODE-MAP_代码地图.md`）
- **git 提交**：「🚧 黎：merge 39 commits」+ 后续多人增量（实际数字见 `git log --oneline | wc -l`）
- **测试**：MCP 专项 19/19 + 集成验证 5/6 PASS + 既有套件偶发 flaky（fakeredis 单例，已立 NB）
- **ADR**：10 份（0001 CLI 优先 / 0002 长驻 CLI / 0003~0006 MCP 系列 / 0007 Tauri / 0008~0010 自决+P2+downscope）
- **收束报告**：`docs/reports/收束报告-MCP-F1.md`（140 行）+ `收束报告-MCP-F2.md` 双线签核闭合
- **worklog**：3 人 × 每日 1-2 份（详见 `worklogs/{黎,董,袁}/`）

**v4.0 文档状态**：本文档是历史冻结版，**不回头改 v4.0 原文**。所有变更通过 ADR + worklog 沉淀。本「实施进度速览」段是附录式增量，符合 PR-09「改架构先改 spec → 再实现」红线（v4.0 架构本身未改，仅在末尾加进度对账）。

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

## AI 协作沉淀（增量附录 · 2026-06-07）

> 段落定位：本段是 v4.0 PRD 落地的「过程资产」对账——不重复 spec 内容，只记录实现过程中沉淀的 AI 协作方法论、规范、工具链。详细 AI 协作流程与产物见 [`docs/deliverables/AI协作开发记录.md`](../deliverables/AI协作开发记录.md)。

### 1. 团队与角色（3 + 1 协作模型）

AgentHub 由 3 位人类开发者 + 1 位 Claude Agent 共同完成，遵循「Opus 开发 + DeepSeek 审查 + 人决策」：

- **董**（yii.d）——协调者 + 域 2 DRI：记忆系统、CLI 多模型代理、群聊编排
- **黎**（oldmanpushbike）——全栈 + 域 3 DRI：OpenCode 集成、桌面 App 选型
- **袁**（xiangbianpangde）——规范架构 + MCP DRI：模板重构、MCP F1/F2、集成验证
- **Claude Agent**（Opus）——架构师 + 开发者：TDD 自检、代码生成、文档生成（git identity 自动归「袁」目录）

**协作心法**：Claude 不自审自己的代码——TDD 是自检（保证「按预期运行」），DeepSeek 是独立审查关卡（发现「视角盲区」）。

### 2. 协作流程（自上而下、可追溯、可视化）

`CLAUDE.md`（冷启动）→ `docs/conventions/`（01-10 规范）→ `docs/specs/`（BDD 契约）→ `worklogs/{人名}/`（每功能点一份）→ `STATUS.md`（进度数据源）→ `dashboard.html`（物理可观测层）。

**关键设计**：
- **CLAUDE.md 冷启动契约**：从 `git config user.name` 自动判断「你是谁」，加载对应 worklog 目录、当前进度、阻塞项
- **conventions 红线速查表**：AR-01 5 层洋葱 / CR-12 禁同步阻塞 / PR-02 feature 分支 / AP-02 错误信封 / T-01 独立测试 / D-05 文档命名
- **worklogs 「给下一位的交接」段**：每份末尾固定段，让接手的人 2 小时内能继续
- **STATUS → dashboard**：`scripts/check_worklog.py` 校验 STATUS 与 git log 一致；dashboard 暖色 Claude 风（焦糖色 + Songti SC 衬线）渲染进度图

### 3. ADR 索引（10 份架构决策记录）

| # | 标题 | 关键决策 |
|---|------|---------|
| [0001](../decisions/0001-cli-first-pivot.md) | **CLI 优先** | API 95h+ 自建 Harness 不可行 → CLI 模式（Claude Code 自带 tool/state/Permission）<300 行 + SessionStore（Redis 7d TTL） |
| [0002](../decisions/0002-phase1-long-running-cli.md) | **Phase 1 长驻 CLI** | spawn+EOF 短驻 → stdin 持久监听 + stream-json 长驻 |
| [0003](../decisions/0003-mcp-url-prefix-and-ap05-deferral.md) | **MCP URL = `/api/mcp`** | 对齐现状（全库无 `/v1/`），AP-05 暂缓进 NB-02；记忆 MCP 协议端 mount 移到 `/api/mcp-memory` |
| [0004](../decisions/0004-mcp-f1-landing-and-installer-seam.md) | **MCP F1 二次对账** | 计划写「FK→workspaces」实无该表 → 裸 UUID stand-in；安装=结构校验探针（422 拦截） |
| [0005](../decisions/0005-mcp-attach-request-carried.md) | **attach = 请求携带** | `AgentRequest.mcp_servers` 逐调用带 config（避免池化跨 agent 串号） |
| [0006](../decisions/0006-mcp-injection-per-runtime-isolated-channel.md) | **MCP 注入逐调用隔离通道** | claude_code `--mcp-config <tmp>` / opencode `OPENCODE_CONFIG=<tmp>`；pi_agent deferred |
| [0007](../decisions/0007-tauri-desktop-pivot.md) | **Tauri 2 桌面 App 转向** | Tauri 2 + 瘦客户端（M2）+ GitHub Releases；3-5MB vs Electron 100MB+ |
| [0008](../decisions/0008-self-governance-authorization.md) | **owner 自决授权** | 用户明早未到岗期间 owner 自主判断（不可删用户文件 / 不可 force push main） |
| [0009](../decisions/0009-p2-handoff-cron.md) | **P2 兜底 cron** | 2026-06-07 10:00 用户未报备 → cron 自动启动 P2 接力 |
| [0010](../decisions/0010-integration-verify-downscope-e.md) | **集成验证 E downscope** | Inbox 视觉 M4 TODO（不在 P0 范围）→ 5/6 PASS override_accept |

**方法论固化**（ADR-04/06 沉淀）：凡「N 个组件都能做 X」必须逐个打开验证 X 在每个组件里可行——避免 R11「opencode 也能注入 MCP」未经实测断言。ADR-06 据此实测发现 opencode 的 `OPENCODE_CONFIG` env 才是逐调用隔离通道（不是写全局），R11 的「写全局会串号」根因不成立 → opencode 拉回本期。

### 4. 收束节点 4 阶段方法论（强制流程）

```
收束节点 = 质量闸门（每 3 个功能点或版本变更触发）
阶段1 整理 ──→ 阶段2 测试 ──→ 阶段3 审计 ──→ 阶段4 验证
 代码/文件    全量+集成+回归   AI+人双线    BDD+用户故事
```

| 阶段 | 关键动作 | 产出 |
|------|---------|------|
| **1 整理** | ruff 清未用 import / 删注释代码 / `worklogs/` 齐全 / 过时文档归档 / **回顾 worklog 关键决策 → 提升 ADR** | 整理报告段 |
| **2 测试** | 全量单测 + 集成 + 跨模块回归 + 手工探索 3-5 条核心用户流程 + 性能基准对比 | 测试矩阵段 |
| **3 审计** | **AI 线**：AR-01/02/06 + CR-01-12 + PR-01-09 + AP-01-07 + T-01-06 + 图谱缺陷 = 全量模式扫描<br>**人线**：AI 标记项复核 + 业务逻辑合理性 + 设计意图偏离 + PR/CR 抽查<br>**双线合入**：🔴 红线必修 / 🟡 中风险接受须 ADR | AI 审计 + 人签核 |
| **4 验证** | BDD 场景逐条回演 + 可视化产出重新生成（Playwright 截图对比）+ 回到 `背景.md` 验证方向未偏 + 技术债盘点 | 效果验证报告段 |

**核心原则 4 条**（项目红线）：

1. **先收束再前进**——收束是「不做完不能走」，不是「建议做完」
2. **AI + 人双线**——AI 模式匹配 / 人理解上下文，互补不替代
3. **效果验证 ≠ 功能测试**——BDD 100% 通过不代表用户体验好
4. **产物必须落盘**——`docs/reports/收束报告-vX.Y.md` + Git tag `vX.Y`，后续的人能翻历史

**真实案例**（MCP F1）：MCP「市场 + 安装」5 端点（commit `3c0027c`..`f59a45a`）→ 收束-1 双线签核闭合（AI 线无 🔴 红线 + 人线袁签核通过）→ Git tag `mcp-f1` 打在 `9d7cdf2` → 并入 main。完整报告：[`docs/reports/收束报告-MCP-F1.md`](../reports/收束报告-MCP-F1.md)（140 行）。

**反面案例**（plan_bcf9945c 集成验证）：Inbox 视觉收 3 重 gap（backend TODO + frontend mock + 无 nav）→ 4 次 retry 失败 → owner **不盲目第 5 次 retry**，而是**降级验证层级**（visual → API+code）并主动记 known gap → ADR-0010 立方法论「下次遇到 P0 范围外的项不再硬 retry」。

### 5. 工具链映射

| 场景 | 工具 / Skill |
|------|------------|
| 冷启动 | `CLAUDE.md`（自动加载） + `git config user.name`（身份识别） |
| 任务定位 | `docs/conventions/CLAUDE-规范导航.md` + `meta/FILE_GRAPH.md`（文件归类权威） |
| 规范扫描 | `scripts/check_docs.py`（命名校） + `scripts/check_worklog.py`（worklog 校） + `scripts/check_branch.py`（分支名校） |
| 代码审计 | `scripts/verify.bat`（ruff + pytest cov + tsc + eslint） + `skills/code-review/`（按 conventions 01-08 红线） |
| 收束 | `docs/reports/收束报告-*.md` + `docs/templates/收束报告模板.md` + `docs/templates/AI审计报告模板.md` |
| 可视化 | `dashboard.html`（解析 STATUS） + `.understand-anything/graph.html`（图谱） + `.codegraph/graph.json`（节点/边/缺陷） |
| 协作沟通 | `worklogs/{人名}/YYYY-MM-DD_*.md`（每功能点） + `worklogs/decisions/NNNN-*.md`（ADR） |
| 收束关闭 | `git tag vX.Y` + `STATUS.md` 收束行 + `dashboard.html` 刷新 |

### 6. 沉淀的可复用方法论

- **CLI 优先决策树**（ADR-01）：判断自建 Harness vs 复用现有 CLI → 工时差距 95h+ vs <300 行 → 选 CLI
- **MCP URL/AP 对齐现状**（ADR-03）：单点改规范 vs 改全库 → 现状是「全库无 `/v1/`」→ 单点对齐 + 规范暂缓（进 NB）
- **二次对账 schema↔代码**（ADR-04）：计划阶段必查「引用表/依赖/协议/类型真实存在」→ 漏掉会导致迁移失败/测试全红
- **attach 请求携带**（ADR-05）：运行时有状态 vs 请求携带 → 池化/共享 runtime 跨 agent 串号 → 选请求携带
- **逐调用隔离通道**（ADR-06）：全局配置 mutation vs 逐调用 flag/env → 跨调用串号风险 → 选逐调用
- **降级验证层级**（ADR-0010）：某项不在 P0 范围时 → 降级验证层级（visual → API+code） + 主动记 known gap，比无脑 retry 5/6 次更高效

### 7. 与交付物的对应

| 交付物（题目要求） | 落地产物 |
|------------------|---------|
| 1. 产品设计文档 + 技术文档飞书文档 | 本文档 + [`docs/deliverables/AI协作开发记录.md`](../deliverables/AI协作开发记录.md) |
| 2. 可运行 Demo github仓库地址 | `oldmanpushbike/agenthub`（feature 分支并入 main） |
| 3. AI 协作开发记录 | [`docs/deliverables/AI协作开发记录.md`](../deliverables/AI协作开发记录.md)（团队介绍 + 工作流 + ADR 索引 + worklogs 模板 + 收束 4 阶段 + dashboard/F1 截图引用） |
| 4. 3-10 分钟 Demo 视频 | 视频脚本（roadmap §8.4 Demo 3min） |

---

*版本: v4.0 | 日期: 2026-05-23 | 变更: v3 与 ADR-01 冲突裁决合并*
*附录增量: 2026-06-07 — 顶部「实施进度速览」+ 末尾「AI 协作沉淀」（不回头改 v4.0 原文，符合 PR-09）*
