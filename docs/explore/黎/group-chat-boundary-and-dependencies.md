# 群聊功能：模块边界、依赖分析与接口契约

> 状态：探索讨论 | 日期：2026-05-25 | 参与：小明、Claude

## 一、背景

在实现「群组正常对话」之前，需要厘清以下问题：

1. 群组对话对多 Agent 任务编排、协调者、记忆、上下文、工具的依赖程度有多高？
2. 群组创建功能与群聊编排（M3）有哪些重合？
3. 消息同步、长期记忆、CLI 进程生命周期、Session 模型的边界在哪里？
4. 在记忆/工具/上下文尚未完整设计的情况下，如何不阻塞群聊开发？

---

## 二、群组对话的依赖分层

群聊功能不是单一开关，可以分层交付：

```
群组正常对话
│
├── L1: 消息广播（无 AI 回复）          依赖: 0 个新模块
│   └── 只改 _resolve_target_agent，消息落库 + WS 广播即可
│
├── L2: @Agent 直接路由                 依赖: L1 + @mention 解析 + Context
│   └── @前端专家 → 路由到该 Agent → 流式回复
│
├── L3: @协调者 任务分解                依赖: L2 + Coordinator + Harness
│   └── @协调者 "做登录页" → 拆成 N 个子任务
│
└── L4: 多 Agent 并行执行               依赖: L3 + Task FSM + DAG + Worker
    └── 子任务并行分派给多个 Agent 执行
```

**核心结论：L2（@Agent 路由）对 L3/L4（Coordinator/TaskEngine）的依赖为零。**

### 逐层模块依赖矩阵

| 模块 | L1 广播 | L2 @Agent | L3 @协调者 | L4 并行 |
|------|:------:|:---------:|:---------:|:------:|
| @mention 解析 | — | **需要** | 需要 | 需要 |
| L1 记忆（滑动窗口） | — | 需要 ✅ | 需要 | 需要 |
| 长期记忆 | — | 可选 | 建议 | 建议 |
| ContextBuilder | — | **需要** | 需要 | 需要 |
| Coordinator | — | — | **需要** | 需要 |
| Harness/DAG | — | — | 需要 | **需要** |
| Task FSM | — | — | — | **需要** |
| Worker 调度 | — | — | — | **需要** |
| 工具执行 | — | CLI 自带 | CLI 自带 | **需要** |

---

## 三、群组创建 vs 群聊编排 — 重合分析

### 重合部分

| 重合项 | 群组创建 | 群聊编排（M3） | 重合度 |
|--------|---------|---------------|--------|
| Group CRUD | `POST/GET /api/groups` + check-name | 2.12 完整 CRUD | **高** |
| 协调者自动创建 | `GroupService.create()` step 4 | 2.12 创建群组→协调者出现 | **完全重合** |
| 数据模型 | groups + group_members | 同一套表 | **完全重合** |
| GroupService | `group_service.py` | 同一个 L3 Service | **同一文件** |
| GroupRepository | 接口 + Postgres | 同一个 Repository | **同一文件** |

### 各自独立

| 群组创建独有 | 群聊编排独有 |
|-------------|-------------|
| CreateGroupModal UI | dispatch_mode=auto + @mention 路由 |
| LeftPanel「+」入口 | Coordinator Prompt + Few-shot 分解 |
| 名称实时校验 | Harness: TaskPlan 校验 + DAG 编译 |
| | Worker 并行执行 asyncio.gather |
| | Task FSM + Budget Controller |

### 结论

群组创建是群聊编排的前置子任务。创建群组做完后，编排直接在同一套 GroupService/Repository 上叠加，不复建。

---

## 四、三个核心问题与解决方案

### 4.1 消息同步 + 长期记忆 + 模块边界

#### 消息同步

群聊消息同步无需新设施，复用现有链路：

```
用户发消息 → WS → ChatService
  ├─ 持久化 PG messages 表
  ├─ 写 L1 Redis 滑动窗口（key: l1:{session_id}）
  ├─ 发布 MessageSent 事件
  └─ WS broadcast → 群内所有在线客户端
```

#### 长期记忆：AgentHub 管，不交给 CLI

| | CLI 管理 | AgentHub 管理 |
|---|---|---|
| 存储 | `~/.claude/sessions/` sqlite | PG + pgvector |
| 范围 | 单 Agent 单 session | 跨 Agent、跨 session、跨群组 |
| 能做什么 | --resume 恢复对话 | 语义搜索、RAG、共享记忆 |
| 群聊场景 | Agent A 不知道 B 记住了什么 | 统一记忆池 |

#### 模块边界设计

核心原则：**每个模块的输入/输出是数据结构，不是另一个模块的实例。**

```
┌──────────────────────────────────────────────────────┐
│                   GroupChatModule                     │
│                                                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────┐ │
│  │ Pipeline │   │  Router  │   │  ContextBuilder  │ │
│  │ 接收/持久 │──→│ 解析路由  │──→│ 组装 AgentRequest │ │
│  │ WS 广播  │   │ @/intent │   │ +memory+peer     │ │
│  └──────────┘   └──────────┘   └───────┬──────────┘ │
│                                        │             │
│  ┌──────────┐              ┌───────────▼──────────┐ │
│  │  Memory  │◀── 调用 ────│     Executor          │ │
│  │  Service │              │  adapter.stream()     │ │
│  │ 长期记忆  │              │  → StreamEvent 迭代器 │ │
│  └──────────┘              └───────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

**边界规则**：

| 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|
| Pipeline | 消息落库 + WS 广播 | `message` | 持久化确认 + 广播事件 |
| Router | 决定消息发给谁 | `(message, session)` | `List[TargetAgent]` |
| ContextBuilder | 给 Agent 准备什么上下文 | `ContextRequest`（纯数据） | `AgentRequest` |
| MemoryService | 长期记忆存取 | `remember() / recall()` | 记忆 CRUD |
| Executor | 调 CLI/API 执行 | `(agent, AgentRequest)` | `AsyncIterator[StreamEvent]` |

**变更隔离**：

| 未来变更 | 影响范围 |
|----------|---------|
| 记忆引擎切换（ILIKE→pgvector） | 只改 MemoryService |
| 路由策略升级（@mention→意图分类） | 只改 Router |
| 执行模式切换（CLI→API） | 只改 Executor |
| Prompt 模板变化 | 只改 ContextBuilder |
| 新增「@all 通知全体」 | 只改 Router（新返回类型） |

---

### 4.2 CLI 进程生命周期

#### 问题

文档设计中「每条消息 spawn 一次 CLI」带来：
- 冷启动延迟：CLI 加载 + sqlite 恢复 ≈ 1-3s
- 资源抖动：5 个 Agent 同时 spawn = 5 个进程同时初始化

#### 方案对比

**方案 A：进程池（keep-alive）**

```
Agent 进程池
├─ FrontendAgent: CLI 进程常驻，stdin/stdout 长连接
├─ BackendAgent:  CLI 进程常驻
└─ ReviewerAgent: CLI 进程常驻

空闲 5 分钟 → SIGTERM → 退出
新消息到达 → 检查池 → 命中复用，未命中 spawn
```

- 优点：零冷启动
- 障碍：CLI `--print` 是一次性执行模式，需验证是否支持多轮 stdin

**方案 B：--resume 预热**

每次 spawn 后不额外处理，下次 `--resume` 直接恢复 sqlite。

- 优点：实现简单，`--resume` 已就绪
- 问题：仍有进程启动开销（~0.5-1s），比纯冷启动快但非零

**方案 C：第一版只做 @mention 路由**

不搞讨论模式（并行通知全体），用户必须 @某人，一次只 spawn 一个 CLI。

- 优点：最简单，资源压力为零
- 问题：不支持「群内自由讨论」

#### 建议：分阶段

| 阶段 | 方案 | 目标 |
|------|------|------|
| V1 | 方案 C（@mention 路由，单 Agent spawn） | 验证路由和上下文链路 |
| V2 | 方案 B（--resume 预热）+ 讨论模式 | 扩展为多 Agent 并发 |
| V3 | 方案 A（进程池） | 实际瓶颈出现后再优化 |

进程池的关键障碍是 CLI `--print` 模式不支持持久化 stdin，需要验证 CLI 是否有 `--input-stream` 或交互模式。切换成本仅影响 Executor 模块。

---

### 4.3 Session 模型与边界

#### Session 归属：Agent 在群里的记忆属于谁？

::: example
FrontendAgent 在「全栈开发组」讨论过 React 状态管理
FrontendAgent 在「设计评审组」讨论过 UI 规范

这两个上下文的 CLI session 是同一个还是分开的？
:::

- **共用**：Agent 混淆两个群的讨论内容
- **分开**：session 数量 = 群组 × Agent，但上下文隔离清晰

**结论：分开。Agent 在不同群的上下文不该混淆。**

#### CLI Session Key 设计

```
私聊：{session_id}
群聊：{group_session_id}:{agent_id}
```

3 个群组 × 5 个 Agent = 15 个 CLI session，每个 ≈ 几百 KB sqlite。存储成本可忽略。

#### SessionManager 接口

```python
class SessionManager:
    """管理 AgentHub session ↔ CLI session 的映射。"""

    def cli_key(self, session_id: UUID, agent_id: UUID | None = None) -> str:
        """私聊: session_id  群聊: session_id:agent_id"""
        ...

    async def cleanup_agent(self, agent_id: UUID) -> None:
        """Agent 被删除 → 清理其所有 CLI session"""

    async def cleanup_group(self, group_id: UUID) -> None:
        """群组被删除 → 清理该群所有 Agent 的 CLI session"""
```

只有 SessionManager 知道 key 格式。Router/ContextBuilder/Executor 只知道「给我一个 key」，不关心格式。

---

## 五、接口契约：在不完整设计下推进群聊

当前三个模块的实际状态：

| 模块 | 文档里说的 | 代码里实际有 | Gap |
|------|-----------|-------------|-----|
| ContextBuilder | 独立类，组装 AgentRequest | 不存在，逻辑散落 ChatService | **无接口，无实现** |
| Memory | L1~L4 四级 | 只有 L1 滑动窗口 | **L2+ 无接口** |
| Tools | ToolRegistry | 注释写 `TODO(M3)` | **无接口，无实现** |
| AgentRequest | 含 peer_context 等字段 | 代码里无这些字段 | **协议不同步** |

对策：每个缺失模块只定义群聊需要的**最小接口** + **桩实现**。

```
群聊代码
  │
  ├── 依赖 IMemoryService    ← 接口（扩展 L1MemoryStore 模式）
  ├── 依赖 IContextBuilder   ← 接口（新定义）
  ├── 依赖 IToolProvider     ← 接口（新定义，CLI Agent → 空操作）
  │
  └── 不依赖任何具体实现
```

### 5.1 Memory 接口

```python
# domain/memory.py

class MemoryService(ABC):
    # —— 工作记忆（已有 L1MemoryStore，包装复用）——
    async def append_working(self, session_id: UUID, message: dict) -> None: ...
    async def get_working_window(self, session_id: UUID) -> list[dict]: ...

    # —— 长期记忆（新定义）——
    async def remember(
        self, session_id: UUID, content: str, tags: list[str] | None = None
    ) -> str:  # → memory_id
        """标记重要内容为长期记忆"""
        ...

    async def recall(
        self, session_id: UUID, query: str, top_k: int = 5
    ) -> list[MemoryItem]:
        """检索与 query 相关的长期记忆"""
        ...
```

桩实现：`remember()` 写 PG `long_term_memories` 表，`recall()` 用 ILIKE 模糊匹配。后续换 pgvector 不改接口。

### 5.2 Context 接口

```python
# domain/context.py

@dataclass
class ContextRequest:
    """纯数据输入，不依赖任何模块实例"""
    agent: Agent
    session: Session
    current_message: str
    working_memory: list[dict]           # L1 窗口（外部传入）
    long_term_memories: list[MemoryItem] # 长期记忆（外部传入）
    peer_messages: list[dict]            # 群聊其他成员消息
    group_members: list[Agent]           # 群组成员列表


class ContextBuilder(ABC):
    """组装 AgentRequest。纯函数，无副作用、无 IO。"""

    def build(self, ctx: ContextRequest) -> AgentRequest:
        """入参决定出参。不查数据库、不调 Redis。"""
        ...
```

同时 `AgentRequest` 需补字段：

```python
# 现有字段：request_id, session_id, messages, system_prompt, memory
# 新增：
peer_context: str | None = None       # 群聊其他 Agent 消息文本块
capability_prompt: str | None = None  # Agent 能力描述文本块
```

### 5.3 Tools 接口

```python
# domain/tools.py

class ToolProvider(ABC):
    """工具提供者"""

    async def list_tools(self, agent_id: UUID) -> list[ToolDefinition]: ...
    async def execute(self, agent_id: UUID, tool_name: str, args: dict) -> ToolResult: ...


class NoopToolProvider(ToolProvider):
    """CLI Agent 桩：工具由 CLI Harness 管理，AgentHub 不参与"""
    async def list_tools(self, agent_id): return []
    async def execute(self, agent_id, tool_name, args):
        raise NotImplementedError("CLI Agent 工具在 CLI 侧执行")
```

群聊 V1 直接使用 `NoopToolProvider`。后续 API Agent 接入时实现真实 Provider。

---

## 六、桩实现落地计划

| 接口 | 桩实现 | 文件位置 | 估时 |
|------|--------|---------|------|
| `MemoryService` | 扩展 L1 + PG long_term_memories（ILIKE） | `infrastructure/cache/memory_service.py` | 2h |
| `ContextBuilder` | 模板拼接 system_prompt + peer_context | `application/services/context_builder.py` | 1.5h |
| `ToolProvider` | NoopToolProvider 空操作 | `domain/tools.py` | 0.5h |
| `AgentRequest` 补字段 | peer_context, capability_prompt | `domain/llm/protocol.py` | 0.5h |
| `SessionManager` | CLI key 映射 + 清理 | `application/services/session_manager.py` | 1h |
| `Router` | @mention 解析 + Agent 查找 | `application/services/router.py` | 1.5h |

**总计 ~7h**，只搭接口骨架，不涉及复杂逻辑。

---

## 七、群聊依赖关系（接口版本）

```
ChatService.send_group_message()
  │
  ├─ 1. Pipeline: 持久化 + WS 广播 ............ 现有，无新依赖
  │
  ├─ 2. Router.resolve(message, session)
  │      → [TargetAgent(id, name), ...] ........ 新模块，无外部依赖
  │
  ├─ 3. 对每个 TargetAgent:
  │      │
  │      ├─ memory.recall(session, query) ....... 依赖 IMemoryService
  │      ├─ memory.get_working_window(session) ... 依赖 IMemoryService
  │      ├─ ContextBuilder.build(                 依赖 IContextBuilder
  │      │     ContextRequest(
  │      │       agent, session, message,
  │      │       working_memory, long_term_memories,
  │      │       peer_messages, group_members
  │      │     )
  │      │   ) → AgentRequest
  │      │
  │      └─ adapter.stream(AgentRequest) ......... 依赖 IExecutor（已有）
  │
  └─ 4. 收集响应 → 落库 + L1 + WS broadcast
```

每个「依赖」指向接口，不是实现。后续替换任一模块，接口不变则群聊代码不变。

---

## 八、相关文档

| 文档 | 内容 |
|------|------|
| `docs/design/group-creation_群组创建功能设计方案.md` | 群组创建功能完整设计 |
| `docs/adapter-cli-flow_全场景流程分析.md` §四/§五 | 群聊任务模式 + 讨论模式流程 |
| `docs/specs/domains/domain2-orchestration_域2-Agent编排.md` | M3 编排任务清单 |
| `docs/plan/背景_PRD_AgentHub_统一方案.md` | 当前权威 PRD |
| `docs/specs/01-architecture_架构定义.md` | 五层架构定义 |
