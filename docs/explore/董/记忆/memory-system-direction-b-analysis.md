# 方向 B 分析：后端统一记忆服务 + CLI 注入通道适配

> 日期：2026-05-31 | 状态：**设计评估**
> 前置阅读：`memory-system-design-v1.md`（当前实现）、`everos_evercore_memory_analysis.md`（EverCore 参考）
> 问题域：如何让记忆系统 CLI 无关，支持 Claude Code / opencode / pi 等多 CLI 接入

---

## 一、问题陈述

当前 V1 设计让 Agent 通过 CLI 原生 Write 工具写 `memory/` 目录。这意味着：

1. 记忆格式/路径与 Claude Code 强耦合（`~/.claude/projects/{path}/memory/`）
2. 每接入一个新 CLI（opencode、pi），都需要为那个 CLI 的记忆约定重写一套 SP 指令
3. 同一个 Agent 在不同 CLI 间的记忆不互通

**方向 B 核心思路**：记忆存在 AgentHub 后端（PG），通过各 CLI 可用的通道注入。

---

## 二、EverMem 如何处理与 CLI 的冲突和重合

### 2.1 核心策略：完全旁路，通道隔离

EverMem **不碰 CLI 原生记忆系统的任何文件**，走的是完全独立的通道：

| 维度 | CLI 原生记忆 | EverMem |
|------|-------------|---------|
| **存储位置** | `~/.claude/projects/{path}/memory/`（本地文件） | EverMem Cloud API（远程 MongoDB + Milvus） |
| **写入方式** | Agent 用 Write 工具自主写 | Stop Hook 读 transcript → 提取 → 上传云端 |
| **读取方式** | CLI spawn 时 `<system-reminder>` 注入 MEMORY.md | UserPromptSubmit Hook 返回 `additionalContext` |
| **注入层** | Layer 1（`<system-reminder>`，spawn 时缓存） | Hook 返回值（每轮动态注入） |
| **管理者** | Agent 自己（自治写/读/删） | 外部服务（自动提取、语义检索） |
| **生命周期** | 随 CLI 安装/卸载 | 独立于 CLI，云端持久化 |

### 2.2 具体不冲突机制

1. **不写 `memory/` 目录** — EverMem 从不在 `~/.claude/projects/*/memory/` 下创建或修改任何文件。CLI 的 auto-memory 系统完全不知道 EverMem 的存在。

2. **用 Hook 返回值注入，不修改磁盘文件** — `inject-memories.js` 通过 Hook stdout 返回 `hookSpecificOutput.additionalContext`，这是 Claude Code Hook 系统的标准注入通道。它和 `<system-reminder>` 里的 MEMORY.md 是并行的、不同层的注入，不会互相覆盖。

3. **只读 transcript，不写 transcript** — `store-memories.js` 在 Stop 事件时只读 `~/.claude/projects/{hash}/{session}.jsonl`（对话记录），提取最后一轮对话文本上传到云端。它是只读的。

4. **两套记忆共存，互补关系** — CLI 原生记忆（Agent 自治，精准，适合项目事实/偏好）+ EverMem（全量被动提取，适合���史回溯/跨会话连续性）。两者功能不重叠。

5. **不禁用/不替代 CLI 原生记忆** — 安装 EverMem 插件后，CLI 的 auto-memory 功能继续正常运行。EverMem 不修改 `.claude/settings.json`，不 patch CLI 行为。

### 2.3 注入时机不冲突

```
CLI 原生注入（spawn 时，一次性）：
  <system-reminder>
    CLAUDE.md 内容
    MEMORY.md 内容       ← CLI 原生记忆在这里
    rules/*.md
    gitStatus / currentDate
  </system-reminder>

EverMem 注入（每轮 UserPromptSubmit Hook）：
  additionalContext:
    <relevant-memories>
      [2026-02-09 10:30 UTC]     ← EverMem 记忆在这里
      Discussion about JWT...
    </relevant-memories>
```

两者在 context window 中是不同的 block，Claude 能同时看到两者，不冲突。

### 2.4 EverMem 的 4 个 Hook 生命周期

| Hook | 触发时机 | 做什么 | 对 CLI 的影响 |
|------|---------|--------|-------------|
| `SessionStart` | CLI 启动 | 从云端拉最近 5 条记忆 + 本地 session 摘要 → 注入 `systemPrompt` | 只读，不修改 CLI 文件 |
| `UserPromptSubmit` | 用户每次发消息 | 用 prompt 做语义检索 → 注入 `additionalContext` | 只读，不修改 CLI 文件 |
| `Stop` | Claude 每次回复完毕 | 读 transcript JSONL → 提取最后一轮 → 上传云端 | 只读 transcript |
| `SessionEnd` | 会话结束 | 解析 transcript → 保存 session 摘��到本地 `sessions.jsonl` | 写自己的 `data/` 目录，不碰 CLI 目录 |

**关键**：所有 Hook 都 `continue: true`（永不阻塞 CLI 流程），所有错误都静默降级（`process.exit(0)`）。

---

## 三、当前 V1 实现的 CLI 耦合点审计

| 模块 | CLI 耦合点 | 耦合强度 |
|------|-----------|---------|
| `SystemPromptBuilder._memory_instructions()` | 指向 `~/.claude/projects/{path}/memory/`，教 Agent 用 Write 写 | **强** |
| `SystemPromptBuilder._cwd_to_cli_memory_path()` | Claude Code 特有的路径编码规则 | **强** |
| `AgentFileManager` + CLAUDE.md | 依赖 CLI 读取 CWD 下 CLAUDE.md | **中**（大多数 CLI 有类似行为） |
| `AgentFileManager` + context/*.md | Agent 用 Read 读取详情文件 | **低**（所有 CLI 都能 Read 文件） |
| `claude_code_runtime.py` + `cwd=` | spawn 时设 CWD | **中**（CLI 特有，但属于 Runtime 层） |
| `PiAgentRuntime` + 无 cwd | `asyncio.create_subprocess_exec(*cmd, ...)` 完全不传 cwd | **致命** — Pi Agent 零文件上下文 |
| `ContextBuilder` + user message 通道 | delta + 上下文通知走 stdin | **无**（所有 CLI 通用） |
| `GroupContext` 值对象 | 纯数据，无 CLI 依赖 | **无** |

### 3.1 双 Runtime CWD 差异（严重性高于预期）

审查发现 PiAgentRuntime 和 ClaudeCodeRuntime 在当前文件系统记忆方案下的兼容性差异是**致命的**：

```python
# claude_code_runtime.py:249 — 有 cwd
proc = await asyncio.create_subprocess_exec(*cmd, ..., cwd=cwd)
# Pi Agent 可以读取 CLAUDE.md + context/ + memory/（CLI 自动加载）

# pi_agent_runtime.py:102 — 无 cwd 参数
self._process = await asyncio.create_subprocess_exec(*cmd, ...)
# Pi Agent 完全收不到任何文件上下文
```

这意味着当前基于文件系统的记忆方案对 Pi Agent **完全不可用**。方向 B 对多 CLI 的价值不是"未来可能需要"，而是当前双 Runtime 架构下已经存在的硬需求。

---

## 四、改到方向 B 的影响评估

### 4.1 现有代码改动

| 文件 | 改什么 | 行数 |
|------|--------|------|
| `system_prompt_builder.py` | 重写 `_memory_instructions()`：不再教 Agent 写文件，改为描述系统记忆（ContextBuilder 注入） | ~30 行 |
| `system_prompt_builder.py` | 删除 `_cwd_to_cli_memory_path()`（不再需要） | -9 行 |
| `agent_file_manager.py:126-129` | `cleanup_agent_cwd()` 中调用了 `SystemPromptBuilder._cwd_to_cli_memory_path(cwd)`，删除该调用 | -2 行 |
| **合计现有改动** | | **~40 行** |

> **修正说明**：原估 `agent_file_manager.py` 需改 CLAUDE.md 模板 ~5 行。审查确认 `_render_claude_md()`（agent_file_manager.py:158-186）**并未引用 memory 路径**，无需修改。但漏列了 `cleanup_agent_cwd()` 中的调用点（line 126）。

### 4.2 新增代码

| 模块 | 职责 | 预估行数 |
|------|------|---------|
| `Memory` domain entity | 实体定义 | ~30 行 |
| `MemoryRepository`（Protocol） | 接口协议（遵循现有 domain/repositories/ 模式） | ~25 行 |
| `PgMemoryRepository`（L1） | PG 存取实现 | ~80 行 |
| `MemoryService`（L3） | 记忆 CRUD + 检索 + 淘汰 | ~150 行 |
| Alembic migration（0005） | `memories` 表 | ~40 行 |
| `ContextBuilder._maybe_inject_memories()` | 每轮检索记忆 → 填充 `MemoryContext.l4_rag` | ~50 行 |
| `SystemPromptBuilder` 稳定记忆注入 | SP 中嵌入高频 facts/preferences | ~30 行 |
| **合计新增** | | **~405 行** |

### 4.3 写入路径选择：不新起 MCP Server

> **重要修正**：代码库中不存在任何 MCP 基础设施（`mcp` 关键词零命中）。MCP tool 不是 ~100 行能搞定的——需要 MCP server 框架选型、tool 注册机制、与 AgentRuntime 的通信适配。

**Phase B1 采用更务实的写入方案**：

```
Agent 识别到值得记住的信息
    │
    ├─ 方式 1（B1 主路径）: Agent 在回复中输出特殊标记
    │   [MEMORY:facts] JWT 过期设为 7 天
    │   → 后端解析 Agent 回复 → 检测到 [MEMORY:] 标记 → 存入 PG
    │   → 零新增基础设施，利用已有的 stdout 解析链路
    │   成本：~30 行解析逻辑
    │
    ├─ 方式 2（Phase B2）: REST API endpoint
    │   POST /api/v1/memories → MemoryService.save()
    │   Agent 或前端可直接调用
    │
    └─ 方式 3（Phase C，借鉴 EverMem）: 被动提取
        对话结束 → 后端读 transcript → LLM 提取 → 存 PG
```

### 4.4 不改的部分

- `AgentFileManager`（CWD + context/ 保留 — 对所有 CLI 通用）
- `ContextBuilder`（user message 通道已 CLI 无关）
- `GroupContext`（纯值对象）
- `claude_code_runtime.py`（保留，方向 B 是加新 Runtime，不是改这个）
- `pi_agent_runtime.py`（保留，通过 stdin 通道注入记忆，不依赖 cwd）
- `ProcessPool`（长驻进程管理，CLI 无关）

### 4.5 测试影响

以下已有测试文件会受影响：

| 测试文件 | 受影响测试 | 需改动 |
|---------|-----------|--------|
| `test_system_prompt_builder.py` | `test_memory_path_encoding()`（line 54-61）| **删除** — 测试 `_cwd_to_cli_memory_path()`，该方法被删除 |
| `test_system_prompt_builder.py` | `test_build_with_all_fields()`（line 37-45）| **更新** — 断言 `# Memory` 存在，需改为断言新的记忆指令内容 |
| `test_system_prompt_builder.py` | `test_build_minimal()`（line 48-52）| **更新** — 同上 |
| `test_system_prompt_builder.py` | `test_delivery_contract_after_memory()`（line 70-79）| **可能需要更新** — 取决于新 SP 结构 |
| `test_agent_file_manager.py` | `test_cleanup_agent_cwd()`（line 133-140）| **小幅更新** — 如果 logger.info 文本改变或不再打印 memory path |
| `test_context_builder.py` | 群聊/私聊构建逻辑 | **扩展** — 新增 `l4_rag` 填充的测试用例 |

> 预估测试改动量：~30 行删除 + ~50 行新增。

---

## 五、方向 B 的记忆流设计

### 5.1 写入路径（Agent → 后端）

Phase B1 不引入 MCP Server（代码库零 MCP 基础设施），采用现有通道：

```
Agent 识别到值得记住的信息
    │
    ├─ B1 主路径: 回复中输出 [MEMORY:type] 标记
    │   Agent 在回复中写:
    │     [MEMORY:facts] JWT 过期设为 7 天
    │     [MEMORY:preferences] 用户偏好简洁回复
    │   → AgentService 解析 stdout → 检测 [MEMORY:] 标记 → MemoryService.save()
    │   → 零新增基础设施，用现有 stdout 解析 + AgentService 事件处理
    │
    ├─ B2（可选）: REST API POST /api/v1/memories
    │   前端或外部调用 → MemoryService.save()
    │
    └─ Phase C（借鉴 EverMem）: 被动提取
        对话结束 → 后端读 transcript → LLM 提取 → 存 PG
```

### 5.2 读取路径（后端 → Agent）

与项目现有架构的精确映射：

```
Agent 收到新任务
    │
    ├─ 通道 1: MemoryContext.l4_rag（已有字段，协议层已预留）
    │   protocol.py:20 — l4_rag: str | None = None  # "pgvector Top-K 检索结果"
    │   ContextBuilder._maybe_inject_memories() → 填充 l4_rag
    │   → Agent 在 user message 中（或 memory context 中）收到记忆
    │   → 所有 CLI 通用（走 AgentRequest，不经过 CLI 插件系统）
    │
    ├─ 通道 2: group_delta_text 前缀（群聊路径，已有字段）
    │   context_builder.py:122-125 — 拼接 delta + 上下文通知
    │   → 记忆检索结果可在此拼接，和群聊 delta 一起注入
    │
    └─ 通道 3: system_prompt 段注入（已有机�）
        system_prompt_builder.py:43-57 — build() 中 parts 拼接
        → 稳定 facts + preferences 存入 SP（spawn 时一次性注入）
```

> **修正说明**：原文档 §5.2 列出了 "Hook additionalContext" 通道。AgentHub 控制 Agent 的 stdin 管道，不走 CLI Hook 系统，该通道完全不适 用，已删除。注入通道全部走 `AgentRequest` 协议字段。

### 5.3 注入频率设计（借鉴 EverMem）

EverMem 的关键设计：**每轮触发检索逻辑，但只在命中时注入**（"每轮触发，按需注入"）。

```
用户发消息 → [触发检索逻辑]
                │
                ├─ prompt < 3 词 → 跳过，不检索
                ├─ 检索后无相关记忆（score < 0.1）→ 跳过，不注入
                └─ 命中相关记忆 → 注入 top 5 到 additionalContext
```

这意味着：
- **大多数轮次不注入**（短回复"好"/"继续" 或无相关记忆时）
- **只有语义命中时才花 token**
- **触发频率 = 每条用户消息**，但实际注入率可能只有 30-50%

我们的适配：AgentHub 控制 Agent 的 stdin，所以可以在 ContextBuilder 层实现同样逻辑：

```python
# ContextBuilder._maybe_inject_memories()
async def _maybe_inject_memories(self, trigger: Message, agent: Agent) -> str | None:
    """每轮触发，按需注入。返回 None 表示本轮不注入。"""
    # 条件 1: 消息太短不触发
    if len(trigger.content.strip()) < 10:
        return None

    # 条件 2: 检索相关记忆
    memories = await self._memory_svc.search(
        agent_id=agent.id,
        query=trigger.content,
        top_k=5,
        min_score=0.1,
    )

    # 条件 3: 无命中不注入
    if not memories:
        return None

    # 格式化注入
    return self._format_memory_injection(memories)
```

### 5.4 注入通道选择策略（精确映射到现有架构）

| 记忆特征 | 协议字段 | 注入频率 | 实现位置 |
|---------|---------|------|------|
| 稳定事实（架构、约定） | `AgentRequest.system_prompt` | spawn 时一次 | `SystemPromptBuilder.build()`（system_prompt_builder.py:43-57） |
| 高频偏好 | `AgentRequest.system_prompt` | spawn 时一次 | 同上 |
| 任务相关（流程、经验） | `MemoryContext.l4_rag` | 每轮命中时 | `ContextBuilder._maybe_inject_memories()` → 填充 l4_rag（protocol.py:20 已预留） |
| 跨会话连续性（首轮） | `MemoryContext.l4_rag` | 会话首轮 | `ContextBuilder.build_for_agent()` 首轮检测 |
| 群聊上下文变更 | `AgentRequest.group_delta_text` | 变更时（已有） | `ContextBuilder._build_group()`（context_builder.py:122-125，已有，不变） |

**与现有架构的精确对照**：

```
AgentRequest（protocol.py:23-41）
├── system_prompt: str               ← 稳定记忆（SP 段注入）
├── memory: MemoryContext            ← 记忆检索结果
│   ├── l1_working: list[dict]       ← Redis 滑动窗口（已有）
│   └── l4_rag: str | None           ← ★ 记忆检索结果填充此处
├── group_delta_text: str | None     ← 群聊 delta（已有，不变）
└── messages: list[dict]             ← 用户消息
```

> **不再列出 Hook additionalContext 通道**：AgentHub 控制 Agent stdin 管道，不走 CLI Hook 系统。

**Token 预算**：
- SP 段（稳定记忆）：≤ 300 tokens（3-5 条 facts + preferences，spawn 时一次性）
- `l4_rag`（任务记忆）：≤ 200 tokens/次（命中时才花，大多数轮次为 0）

---

## 六、数据模型草案（与现有 schema 对齐）

### 6.1 现有 schema 基础

当前 `models.py` 中所有表使用 UUID 主键（`Uuid` 类型 + `default=uuid4`），时间字段使用 `DateTime(timezone=True)`。关键外键：

- `agents.id`: `Mapped[UUID]` — `Uuid` 主键
- `groups.id`: `Mapped[UUID]` — `Uuid` 主键
- `sessions.id`: `Mapped[UUID]` — `Uuid` 主键

已有 Alembic 迁移版本：0001（initial）→ 0002（agent system base_url）→ 0003（partial unique name）→ 0004（create groups）。新增 migration 编号为 **0005**。

### 6.2 memories 表

```sql
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    group_id UUID REFERENCES groups(id) ON DELETE SET NULL,

    -- 分类
    memory_type VARCHAR(20) NOT NULL,  -- facts | preferences | procedures | context
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,

    -- 扩展元数据（可选，承载 sub_type + 类型特有字段）
    -- 例: {"sub_type": "progress", "status": "in_progress"}
    --      {"sub_type": "lesson", "outcome": "failed"}
    --      {"sub_type": "rpg_character", "traits": ["毒舌", "可靠"]}
    metadata JSONB DEFAULT '{}',

    -- 生命周期
    hits INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ,  -- NULL = 永不过期

    -- 检索
    -- Phase B2: 加 tsvector 全文索引
    -- Phase C: 加 vector embedding 列
    -- 注意：不设 CHECK 约束，类型由应用层 Pydantic Literal 校验（支持在线扩展）
);

CREATE INDEX idx_memories_agent_type ON memories(agent_id, memory_type);
CREATE INDEX idx_memories_agent_updated ON memories(agent_id, updated_at DESC);
-- 按 sub_type 检索（JSONB GIN 索引）
CREATE INDEX idx_memories_metadata ON memories USING GIN (metadata);
```

### 6.3 SQLAlchemy ORM 模型

```python
# infrastructure/db/models.py（追加）
class MemoryModel(Base):
    __tablename__ = "memories"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True
    )
    memory_type: Mapped[str] = mapped_column(String(20))  # 应用层校验，无 DB CHECK
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)  # 扩展元数据
    hits: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
```

与现有 `AgentModel`、`GroupModel` 完全一致的类型约定（`Uuid`/`DateTime(timezone=True)`/`Text`/`JSON`）。

---

## 六b、记忆类型设计与覆盖范围

### 6b.1 4 类型的覆盖边界

B1 定义 4 种类型，对照需求场景：

| 需求场景 | 归类到 | 示例 | 是否合适 |
|---------|--------|------|---------|
| 架构/约定/决策 | `facts` | "API 统一用 kebab-case"、"JWT 过期 7 天" | ✅ |
| 约束/红线 | `facts` | "禁止裸 SQL"、"禁止 print 生产路径" | ✅ 但与架构事实检索混在一起 |
| 用户工作偏好 | `preferences` | "提交前必须跑 ruff"、"用户偏好简洁回复" | ✅ |
| 角色扮演人格 | `preferences` | "扮演毒舌但可靠的资深工程师" | ⚠️ 不是偏好，是虚构设定 |
| 可复用流程 | `procedures` | "新增 Agent：建 Adapter → 注册 → 写 SP" | ✅ |
| 过往经验/教训 | `procedures` | "X 方案不适用，因为 Y" | ⚠️ 勉强，"教训"不是"流程" |
| 失败教训（反面经验） | `procedures` | "别用 redis pub/sub 做关键消息，会丢" | ⚠️ 同上 |
| 任务状态 | `context` | "API 重构写到 L3，L2 还没动" | ⚠️ 与"上次会话摘要"语义混淆 |
| 项目进度 | `context` | "登录模块 80%，支付模块 0%" | ❌ TTL 7 天自动消失，但进度跨周 |
| 会话连续性 | `context` | "上次完成了 API 重构，测试写到一半" | ✅ |
| 角色扮演状态 | **无处** | "当前故事阶段：第三章，主角在柏林" | ❌ 不是事实/偏好/流程/上下文 |
| 角色关系/事件 | **无处** | "NPC 张三已背叛主角" | ❌ 同上 |

**核心问题**：当前 4 类型只有一个分类维度——"这条记忆是什么性质"。但实际场景需要第二个维度——"生命周期和确定性"：

```
确定性高、生命周期长 → facts, preferences（很少变）
确定性中、生命周期中 → experience/lessons（可追加修正）
确定性低、变化快    → progress/tasks（频繁更新）
完全虚构/游戏逻辑  → RPG state（需与真实项目隔离）
```

### 6b.2 设计决策：4 类型 + metadata JSONB

B1 不拆分更多类型，原因是：
- Agent 自主选type时，4 种不会选错；类型越多越容易误分类
- EverMem 7 种类型的后果是提取 LLM 经常归错类
- 缺少的不是类型数量，是分类维度

**解决方案**：加 `metadata JSONB` 列，承载 `sub_type` + 类型特有的扩展字段：

```sql
-- 追加到 memories 表
metadata JSONB DEFAULT '{}'  -- 可选的扩展元数据
```

```python
# infrastructure/db/models.py（追加）
metadata: Mapped[dict] = mapped_column(JSON, default=dict)
```

**使用示例**：

```json
// 进度类记忆（壳是 facts，metadata 区分）
{
  "type": "facts",
  "title": "API 重构进度",
  "content": "已完成 L4 API 层，L3 Application 层进行中",
  "metadata": {
    "sub_type": "progress",
    "status": "in_progress",
    "progress_pct": 50
  }
}

// 经验教训（壳是 procedures，metadata 区分）
{
  "type": "procedures",
  "title": "Redis Pub/Sub 不适用于关键消息",
  "content": "尝试用 redis pub/sub 做任务分发，测试中发现重启丢消息。改用 RabbitMQ。",
  "metadata": {
    "sub_type": "lesson",
    "outcome": "failed",
    "alternative": "RabbitMQ"
  }
}

// 角色扮演
{
  "type": "preferences",
  "title": "AI 助手人格设定",
  "content": "扮演毒舌但可靠的资深工程师，擅长冷幽默",
  "metadata": {
    "sub_type": "rpg_character",
    "traits": ["毒舌", "可靠", "冷幽默"],
    "catchphrase": "你这个设计，三年前就被证伪了"
  }
}
```

**关键原则**：
- `metadata` 纯可选，B1 阶段不强制使用
- `sub_type` 值不设 CHECK 约束，应用层约定即可
- 后续需要新维度时，不 migration，直接在 metadata 里扩展
- 检索时 metadata 可参与过滤：`WHERE metadata->>'sub_type' = 'progress'`
- PG JSONB 支持 B-tree GIN 索引，查询性能不是问题

### 6b.3 MongoDB 对比评估

用户问：换 MongoDB 会不会更好？

| 维度 | PG + JSONB | MongoDB |
|------|-----------|---------|
| 固定字段（id/agent_id/title/timestamps） | ✅ 原生，类型安全 | ✅ Map 到 document fields |
| 变长 metadata | ✅ JSONB，可索引 | ✅ 天然嵌套，无需特殊列 |
| 类型间 schema 分化 | ⚠️ 靠应用层校验 JSONB 内容 | ✅ 每个 type 可有独立 validation schema |
| 关联查询（JOIN agents/groups） | ✅ SQL JOIN | ❌ 需 $lookup 或应用层拼 |
| 全文搜索 | tsvector（中等） | $text（中等，同样需分词器） |
| 新增基础设施 | 0 | +1 容器 + motor/mongoengine |
| Agent 切换存储看记忆 | ✅ SELECT * FROM memories | ✅ db.memories.find() — 同样简单 |
| 运维 | 已有备份方案 | 新备份方案 + 监控 |

**我的判断：B1 不需要 MongoDB。**

理由：

1. **JSONB 已经解决了 MongoDB 80% 的优势**。变长字段、嵌套结构、无 schema 扩展——JSONB 都能做到。

2. **MongoDB 的真正优势要到类型 schema 严重分化时才会体现**。比如 `facts` 有 "证据链"、`procedures` 有 "前置条件" + "步骤列表"、`rpg` 有 "角色关系图"——每种类型需要截然不同的字段、索引和校验规则。此时 MongoDB 的文档模型（一个 collection 一种 schema）比 PG 的 JSONB（一个列塞所有）更自然。

3. **但 B1 不会出现这种分化**。B1 所有类型都是 `title + content + metadata`，metadata 即使有 sub_type 差异也都是平铺的 key-value。

**如果未来要换 MongoDB 的触发条件**：
- 某个 memory type 的 metadata 嵌套深度 > 3 层
- 不同类型需要完全不同的索引策略（PG 单表无法做到）
- metadata 字段数 > 20 且频繁变化的 type > 3 个

**换的成本**：`MemoryRepository` 是 Protocol 接口（§8.3），加一个 `MongoMemoryRepository` 实现，DI 切换即可。业务层代码一行不改。

---

## 七、与 V1 的兼容性

方向 B 是**增量演进**，不是重写：

```
V1（已完成，保留）              方向 B（新增层）
─────────────────────         ─────────────────────
CWD + CLAUDE.md     ←──保留──  不变
context/*.md        ←──保留──  不变（群聊上下文仍走文件 + user message）
user message 通道   ←──保留──  l4_rag 注入 + group_delta_text 复用
SP (身份+约束)      ←──保留──  SP 中加入稳定记忆摘要
memory/ 路径指令    ←──删除──  替换为 [MEMORY:type] 标记 + MemoryContext.l4_rag
                              MemoryService（新增）
                              memories 表（新增）
                              MemoryRepository（Protocol，新增）
```

---

## 八、存储技术选型评估

### 8.1 文档存储：PG vs MongoDB

| 维度 | PG（当前栈） | MongoDB |
|------|-------------|---------|
| 已有基础设施 | ✅ docker-compose 已配置 | ❌ 需加容器 + motor/mongoengine + 连接池 |
| 记忆数据结构 | `TEXT` + 固定字段 + `JSONB` metadata | 对深层嵌套/动态 schema 有优势 |
| 关联查询 | `JOIN agents/groups` 天然支持 | 需应用层或 `$lookup`（弱） |
| 全文搜索 | tsvector（中文需 zhparser） | `$text`（中文同样需分词器） |
| 事务 | 强（跨表 ACID） | 4.0+ 支持但不如 PG 自然 |
| 运维成本 | 0（已有） | +1 容器 + 备份 + 监控 |

**当前决策**：Phase B1 用 PG（`TEXT` + `JSONB`）。理由：
- 记忆结构确定（type/title/content/agent_id/timestamps），不需要动态 schema
- 已有 PG 基础设施，零新增运维
- 规模 < 10K 条，PG 性能无瓶颈

**未来考虑**：若记忆内容演化为高度异构结构（如 EverMem 的 5 种 type 各自有完全不同的嵌套子字段），可评估迁移到 MongoDB。

### 8.2 检索引擎：pgvector vs Elasticsearch vs 专用向量库

| 维度 | pgvector | Elasticsearch 8.x+ | 专用向量库（Milvus/Qdrant） |
|------|---------|--------------------|-----------------------------|
| 新增基础设施 | 0（PG 扩展） | +1 容器（~512MB RAM） | +1 容器 |
| BM25 全文搜索 | ❌ 无（tsvector 是 PG 原生，非 BM25） | ✅ **最强**（倒排索引 + IK 中文分词） | ❌ 无或极弱 |
| 向量检索 | HNSW/IVFFlat，小规模够用 | kNN/HNSW，中等 | **最强**（专用优化 + 量化压缩） |
| 混合检索（BM25 + vector） | ❌ 需应用层手动融合 | ✅ **原生 RRF 融合**，一条查询 | 部分（Milvus 2.4 有，Qdrant 需应用层） |
| 中文支持 | zhparser/pg_jieba（一般） | IK 分词器（成熟） | 取决于 embedding 前处理 |
| 百万级性能 | 够用 | 中等（向量是附加能力） | **极强** |
| 适用场景 | 量小 + 快速验证 | 文本为主的混合检索 | 纯向量、图像/音频 embedding |

**Elasticsearch vs 专用向量库的本质区别**：

- **ES**：全文搜索引擎 + 后来加的向量能力。核心优势是 BM25 关键词匹配 + 结构化过滤 + 混合检索一条查询搞定。
- **专用向量库**：从第一天为 ANN（近似最近邻）设计。核心优势是大规模向量的极致性能（千万～亿级）+ 量化压缩 + 分布式分片。

**对记忆系统的适配性分析**：

记忆检索 = "用户说了一句话 → 找到相关历史记忆"，需要两种能力：
1. 关键词命中：用户提 "JWT" → 记忆里有 "JWT 过期 7 天" — **BM25 擅长**
2. 语义理解：用户问 "认证怎么配" → 记忆里是 "JWT 过期设为 7 天" — **向量擅长**
3. **两者融合效果最好** → ES 的 hybrid search 是最自然的选择

**最终选型路径**：

| 阶段 | 存储 | 检索 | 新增基础设施 |
|------|------|------|-------------|
| B1 | PG `memories` 表 | `WHERE type = X ORDER BY updated_at DESC LIMIT 5` | 0 |
| B2 | PG + `tsvector` 列 | `ts_rank()` 全文匹配（过渡方案） | 0 |
| **C（目标方案）** | **PG（主存储）+ Elasticsearch（检索索引）** | **BM25 + kNN hybrid search** | +1 ES 容器 |

### 8.3 架构约束：不写死存储实现

> **关键设计原则**：MemoryRepository 面向接口编程，检索策略可插拔。
> 遵循项目现有的 Repository Pattern：`domain/repositories/__init__.py` 中已有 5 个 Protocol 接口（Agent/Group/Message/Session/Task），MemoryRepository 遵循同一模式。

```python
# domain/repositories/memory_repository.py（L2 协议层）
# 遵循现有 domain/repositories/ 的 Protocol 模式
class MemoryRepository(Protocol):
    async def save(self, memory: Memory) -> Memory: ...
    async def search(self, agent_id: UUID, query: str, top_k: int, min_score: float) -> list[Memory]: ...
    async def get_by_type(self, agent_id: UUID, memory_type: str) -> list[Memory]: ...
    async def delete(self, memory_id: UUID) -> None: ...

# infrastructure/persistence/pg_memory_repository.py（L1，Phase B1-B2）
class PgMemoryRepository(MemoryRepository):
    """PG 实现：tsvector 全文搜索。"""
    ...

# infrastructure/persistence/es_memory_repository.py（L1，Phase C）
class EsMemoryRepository(MemoryRepository):
    """Elasticsearch 实现：BM25 + kNN hybrid。"""
    ...
```

Phase C 接入 ES 时，只需：
1. docker-compose 加 ES 容器
2. 实现 `EsMemoryRepository`
3. 依赖注入切换（`deps.py` 中换绑定）
4. 数据同步：PG 写入 → 异步 sync 到 ES 索引（PG 仍为 source of truth）

不需要改 `MemoryService`、`ContextBuilder` 等上层代码。

---

## 八b、开放问题（待后续决策）

1. **记忆容量上限**：每 Agent 多少条？超过怎么淘汰？
   - 建议：facts 无上限，context 按 TTL 7天，procedures 30天，总量 ≤ 50 条/Agent

2. **跨 Agent 记忆共享**：群内 Agent 能否看到彼此的记忆？
   - Phase D 再考虑，当前每 Agent 独立

3. **写入路径演进**：Agent 回复标记 vs REST API vs 被动提取？
   - Phase B1: Agent 回复中 `[MEMORY:type]` 标记（零新基础设施）
   - Phase B2（可选）: `POST /api/v1/memories` REST endpoint
   - Phase C: 后端被动提取（LLM 分析 transcript）

4. **注入 token 预算**：每轮最多注入多少记忆 token？
   - 硬限制 5 条 ≤ 400 tokens（借鉴 EverMem）

5. **ES 接入时机**：何时从 PG tsvector 切到 ES hybrid？
   - 当记忆量 > 1K 条/Agent 或用户反馈"检索不准"时触发评估

---

## 九、EverMem 记忆存储策略深度分析

### 9.1 存储决策：100% 自动，无手动存储接口

EverMem **没有** `save_memory` 或类似的手动存储 tool。用户无法主动说"记住这个"然后触发定向存储。

它的 MCP server 只暴露 `evermem_search`（检索），不提供写入接口。

**当用户说"记住 XXX"时**，唯一的路径是：
1. 这句话成为当前对话的一部分
2. Claude 回复后 Stop Hook 触发
3. 整轮对话（含"记住 XXX"）被上传到云端
4. 后端 LLM 从中提取出 AtomicFact / ProfileMemory

这意味着"手动"意图完全依赖后端 LLM 的理解能力 — 如果 LLM 提取时没把这条标记为重要记忆，它就可能被淹没。

**这是 EverMem 的设计缺口。** 对比 Claude Code 原生记忆，用户说"记住这个"时 Agent 会立即用 Write 写文件，确定性 100%。

### 9.2 两层存储决策链

```
┌─────────────────────────────────────────────────────────────┐
│ 第一层：插件侧（Stop Hook — store-memories.js）             │
│                                                              │
│ 触发时机：每次 Claude 回复完毕                                │
│ 决策逻辑：text 非空就上传（几乎零过滤）                       │
│ 过滤条件：                                                    │
│   - hasContent(text) → 纯空白跳过                            │
│   - 其他全存                                                  │
│                                                              │
│ 本质：全量录制，不做价值判断                                  │
└─────────────────────────────────────────────────────────────┘
                    │ 原始 user text + assistant text
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 第二层：后端（EverCore MemoryManager）                       │
│                                                              │
│ 步骤 1: MemCell 边界检测 — "几条消息算一段？"                │
│   策略：LLM 分析主题切换 → 找 boundary point                 │
│   兜底：> 65536 tokens 或 > 500 消息 → 强制切分              │
│   flush：会话结束 → 剩余消息打包                             │
│                                                              │
│ 步骤 2: 多类型并行提取 — "从这段对话中提取什么？"             │
│   每种类型用专门的 LLM prompt：                               │
│   ├── EpisodeMemory — 叙事摘要                               │
│   ├── Foresight — 未来计划/预期                              │
│   ├── AtomicFact — 不可分割的事实                            │
│   ├── ProfileMemory — 用户画像更新                           │
│   └── AgentCase — Agent 解决问题的方法                       │
│                                                              │
│ 步骤 3: 有效性判断 — "提取结果是否有效？"                    │
│   LLM 返回 None/空 → 不存                                    │
│   有内容 → 存到 MongoDB + Milvus 向量库                       │
│                                                              │
│ 成本：每次提取需要 5 个 LLM 调用（边界 1 + 提取 5 种类型）    │
└─────────────────────────────────────────────────────────────┘
```

### 9.3 与手动存储的关系

| 维度 | EverMem（纯自动） | Claude Code 原生（Agent 自治） | 我们应该做的 |
|------|-------------------|-------------------------------|-------------|
| 用户说"记住这个" | 间接（靠自动提取捞出来） | 确定性（Agent 立即 Write） | **提供 [MEMORY:] 标记写入，确定性存储** |
| 日常对话 | 全量录制 + LLM 提取 | 不存（除非 Agent 自己决定写） | **自动提取 + Agent 主动写** |
| 存储成本 | 高（每轮 API + 后端 LLM） | 零（文件系统） | 中（关键对话才提取） |
| 记忆精度 | 中（LLM 可能遗漏） | 高（Agent 主动决定） | 高（两种路径互补） |

### 9.4 我们的设计启示

**应提供双路径存储**：

1. **主动路径（Agent 回复标记）** — Agent 回复中输出 `[MEMORY:type]` 标记，确定性存储
   - 用户说"记住这个" → Agent 回复 `[MEMORY:facts] JWT 过期设为 7 天` → 后端解析存入
   - Agent 自己发现值得记的 → 回复中附带标记 → 存入
   - **补上 EverMem 缺失的手动接口**
   - **零新增基础设施**：利用现有 stdout 解析 + AgentService 事件处理

2. **被动路径（后端自动提取）** — 对话结束后分析
   - 从 transcript 中提取用户没明确要求记住但有价值的信息
   - 成本考虑：不是每轮都提取，只在会话结束时或累积 N 轮后
   - **Phase C 再做**（需要 LLM 调用成本）

```
用户说"记住 JWT 过期设为 7 天"
    │
    ├─ 主动路径（Phase B1，立即实现）
    │   Agent 回复中输出 [MEMORY:facts] JWT 过期设为 7 天
    │   → 后端 AgentService 解析 stdout → 检测到 [MEMORY:] 标记 → MemoryService.save()
    │   确定性 100%，零新增基础设施（利用已有 stdout 解析 + AgentService 事件处理）
    │
    └─ 被动路径（Phase C，后续实现）
        Stop 事件 → 后端读 transcript → LLM 提取
        可能提取出"JWT 过期设为 7 天"，也可能遗漏
        额外 LLM 成本，但能捕获用户没明确要求记住的隐含信息
```

---

## 十、EverMem 记忆提取与注入控制机制

### 10.1 EpisodeMemory 提取：LLM 驱动

后端提取 EpisodeMemory 的过程**完全依赖 LLM**，非规则引擎：

```
一段对话（MemCell）→ LLM 提取 → 6 次 LLM 调用：
  1. ConvMemcellExtractor: 边界检测（判断主题切换点）
  2. EpisodeMemory: 叙事摘要
  3. Foresight: 未来计划/预期
  4. AtomicFact: 不可分割事实
  5. ProfileMemory: 用户画像更新（唯一支持 CRUD）
  6. AgentCase: 问题解决方法
```

每种类型都有专门的 prompt template（如 `profile_prompts.py`、`episode_prompts.py`），LLM 返回结构化 JSON，后端解析后存入 MongoDB + Milvus。

**成本估算**：一个普通开发会话（~20 轮对话，切分为 2-3 个 MemCell），需要 12-18 次 LLM 调用仅用于记忆提取。

### 10.2 上下文挤占控制：硬限制 + 分数过滤

EverMem 的核心设计决策：**无论总记忆量多大，每次注入的 token 数恒定且可控**。

```
inject-memories.js 的控制参数：
  MAX_MEMORIES = 5     // 每次最多注入 5 条
  MIN_SCORE = 0.1      // 相关性分数低于 0.1 的直接丢弃
  topK = 15            // 向后端请求 15 条候选，前端再筛到 5 条

注入格式：
  [日期] 一行摘要文本

单条记忆 ~60-80 tokens，5 条 = 300-400 tokens。
```

**不管用户积累了 10 条还是 10000 条记忆，注入到 Claude 的永远是最相关的 ≤5 条，占 ≤400 tokens。**

控制链路：

```
总记忆池（无限增长）
    │ searchMemories(query, topK=15)
    ▼
15 条候选（后端按 hybrid score 排序）
    │ filter: score >= 0.1
    ▼
N 条有效候选（N ≤ 15）
    │ slice(0, MAX_MEMORIES=5)
    ▼
≤5 条注入记忆 → additionalContext → ~400 tokens
```

### 10.3 EverMem 更新策略：Append-Only + 检索时解析

EverMem **不做原地更新**（ProfileMemory 除外）。当同一主题的信息发生变化时：

```
Day 1: 存入 EpisodeMemory "API 开发完成 50%"
Day 2: 存入 EpisodeMemory "API 开发完成，开始测试"
Day 3: 存入 EpisodeMemory "测试通过，准备部署"
```

三条都保留，不合并不删除。"最新真相"通过 **检索时三层解析** 确定：

| 层级 | 机制 | 作用 |
|------|------|------|
| 1 | 相关性分数过滤 | score < 0.1 的老旧/无关记忆不注入 |
| 2 | 时间降序排列 | 最新的排在前面，LLM 阅读时先看到 |
| 3 | 注入 prompt 指令 | 明确告知 Claude "prefer MORE RECENT information when conflicts exist" |

**优点**：
- 实现简单（无需冲突检测/合并逻辑）
- 保留完整历史（审计友好）
- 检索自然过滤过时信息（老数据 score 自然衰减）

**缺点**：
- 存储持续增长（但对象存储成本低）
- 依赖检索质量（如果 score 不准，可能注入过时信息）

### 10.4 对我们的设计启示

| EverMem 机制 | 我们是否采用 | 理由 |
|-------------|-------------|------|
| LLM 提取（6 calls/segment） | Phase C（成本高） | B1 阶段用 [MEMORY:] 标记主动存，零额外 LLM 成本 |
| 硬限制 5 条 + MIN_SCORE | **采用** | 简单有效，400 tokens 对 200K 窗口可忽略 |
| Append-Only | **采用**（B1 阶段） | 简单实现，PG 存储成本低 |
| 检索时解析（score + time + prompt） | **采用** | 符合我们的 "ORDER BY updated_at DESC + 分数过滤" 方案 |
| ProfileMemory CRUD | Phase B2 | 需要 LLM 判断"是否应该覆盖旧记忆"，有成本 |

---

## 十一、EverMem 机制研究结论汇总

> 本节整合 2026-05-31 讨论中对 EverMem 的完整分析结论，作为后续方向 B 实施的设计依据。

### Q1: 我们的记忆如何注入？通过什么命令/system prompt？

**结论**：EverMem 使用两种 Hook 返回值通道注入，不修改磁盘文件：

| 注入时机 | Hook | 返回字段 | 内容 |
|---------|------|---------|------|
| 会话启动（一次） | SessionStart | `hookSpecificOutput.systemPrompt` | 最近 5 条记忆 + 上次 session 摘要 |
| 每轮消息（按需） | UserPromptSubmit | `hookSpecificOutput.additionalContext` | 语义检索命中的 ≤5 条相关记忆 |

**我们的适配**：AgentHub 不走 Hook（我们控制整个 Agent 输入管道），直接在 `ContextBuilder` 层面注入：
- SP 段（spawn 时一次）→ 稳定记忆
- user message 前置（每轮按需）→ 任务相关记忆

详见 §5.2 + §5.3。

---

### Q2: EverMem 的存储策略？手动还是自动？

**结论**：100% 自动，无手动存储接口。

- Stop Hook 在每次 Claude 回复完毕后触发
- 零过滤（text 非空即上传）
- 后端 LLM 做价值判断和分类提取（6 次 LLM 调用/段）
- MCP Server 只有 `evermem_search`，无 `save`/`write` tool

**设计缺口**：用户说"记住 X"时，无法确定性存储，依赖 LLM 提取能否捞到。

**我们的选择**：双路径（§9.4）
- Phase B1: Agent 回复中 `[MEMORY:type]` 标记（确定性，零新增基础设施）
- Phase C: 被动提取（补充捕获隐含信息）

详见 §9.1-9.4。

---

### Q3: 用户主动说"记住 X"时怎么处理？

**结论**：EverMem 没有专门的手动记录路径。

用户意图完全依赖自动提取链路：对话录制 → 后端 LLM 从中识别出"用户要求记住的信息" → 归类为 AtomicFact 或 ProfileMemory。

**风险**：如果 LLM 提取时没标记为重要，这条记忆可能丢失。

**我们的补全**：Agent 识别到"记住"意图 → 回复中输出 `[MEMORY:type]` 标记 → 后端解析存入。确定性 100%。SP 中会包含指令："当用户要求记住某事时，在回复中输出 [MEMORY:type] <content> 标记。"

---

### Q4: 记忆如何更新？第一天进度 A 第二天进度 B？

**结论**：Append-Only（不原地更新）。

唯一例外：ProfileMemory 支持 CRUD（LLM 判断旧条目是否应被新信息覆盖/删除）。

所有其他类型（EpisodeMemory、AtomicFact、Foresight、AgentCase）只新增不修改。

详见 §10.3。

---

### Q5: 记忆不更新，那注入到 CLI 的记忆如何筛选？

**结论**：检索时三层解析确定"当前真相"：

1. **相关性分数** — hybrid search score < 0.1 的不注入
2. **时间降序** — 最新的排在前面（LLM 先读到）
3. **Prompt 指令** — 告知 Claude "when conflicts exist, prefer MORE RECENT information"

实际效果：用户问"项目进度如何"→ 检索命中 Day1 和 Day2 两条记忆 → Day2 排第一（更新、score 更高）→ Claude 以 Day2 为准回答。

---

### Q6: 后端提取是通过 LLM 吗？

**结论**：是，完全由 LLM 驱动。

每段对话需要 6 次 LLM 调用：1 次边界检测 + 5 种类型各 1 次提取。无规则引擎、无关键词匹配。

成本：普通 20 轮会话（~2-3 个 MemCell）≈ 12-18 次 LLM 调用。

详见 §10.1。

---

### Q7: 全量注入是否有上下文挤占问题？

**结论**：不会。EverMem 用硬限制控制注入量：

- `MAX_MEMORIES = 5`（每次最多注入 5 条）
- `MIN_SCORE = 0.1`（低相关性直接丢弃）
- 单条 ~60-80 tokens × 5 = **≤400 tokens**

无论用户积累了多少记忆（10 条或 10000 条），每次注入恒定 ≤400 tokens，对 200K 上下文窗口可忽略（占比 0.2%）。

详见 §10.2。

---

## 十二、B1 核心设计约束（来自 EverMem 的工程经验）

> 以下不是"未来参考"，而是 B1 实现时必须遵守的约束。

### 12.0 记忆系统韧性原则（B1 强制）

**核心原则**：记忆系统是辅助层，不是关键路径。任何记忆相关故障**不得阻塞 Agent 的主任务**。

```
Agent 收到任务
    │
    ├─ ContextBuilder._maybe_inject_memories()  ← 辅助层
    │   失败 → return None → Agent 无感知
    │
    ├─ Agent 执行任务                                 ← 关键路径
    │
    └─ AgentService._extract_memory_markers()  ← 辅助层
        失败 → log → 丢弃，不影响回复展示
```

**B1 实现强制要求**：

| 约束 | 说明 |
|------|------|
| **永不抛异常** | `_maybe_inject_memories()` 和 `_extract_memory_markers()` 的顶层必须 catch-all |
| **超时保护** | 记忆检索不超过 5s，超时视为无结果 |
| **静默降级** | PG 连接失败 / 查询超时 / 语法错误 → 全部 return None，不通知 Agent |
| **不写 Agent 回复** | 记忆注入失败不改变 Agent 看到的任何内容 |
| **不写 Agent 输入** | `[MEMORY:]` 标记解析失败只丢弃标记，Agent 回复原文不变 |

**错误处理模板**：

```python
# 所有记忆辅助方法的标准模式
async def _maybe_inject_memories(self, trigger, agent) -> str | None:
    try:
        if len(trigger.content.strip()) < 10:
            return None
        memories = await asyncio.wait_for(
            self._memory_svc.search(agent_id=agent.id, query=trigger.content, top_k=5, min_score=0.1),
            timeout=5.0,
        )
        if not memories:
            return None
        return self._format_memory_injection(memories)
    except asyncio.TimeoutError:
        logger.warning("Memory search timeout for agent=%s", agent.id)
    except Exception:
        logger.warning("Memory injection failed", exc_info=True)
    return None  # 永远返回 None，不抛异常
```

---

## 十二b、EverMem 进阶机制（Phase C+ 参考）

> 以下机制 EverMem 已完整实现，但不属于 Phase B1 范围。记录在此作为长期演进参考。

### 12.1 Case → Skill 演化管道

EverMem 最复杂的子系统：Agent 解决问题的方法（Case）→ 聚类 → 提炼为可复用 Skill。

```
AgentCase（单次经验）
    │ ClusterManager: 两阶段 LLM 聚类（embedding 召回 + LLM 决策）
    ▼
MemScene（经验集群）
    │ AgentSkillExtractor: LLM 增量操作（add/update/none）
    ▼
AgentSkill（可复用技能）
    │ Maturity Scoring: 4 维度 LLM 评分（完整度/可执行性/证据/清晰度）
    ▼
Mature Skill（成熟技能，score ≥ 0.6）
    │ 低于 0.1 → 退役（保留审计，移除搜索）
```

**关键设计决策**：

- **增量更新而非全量重建**：新 Case 加入集群时，只对变化做增量操作（add/update/none），不改动无关 Skill。成本从 O(N) 降到 O(Δ)
- **双 prompt 策略**：根据 Case quality_score 选用 success/failure prompt（阈值 0.5），低质量经验走不同的处理逻辑
- **Hypothesis 检测**：LLM 将 "Potential Steps" 提升为 "Steps" 时触发重新评分
- **内容变化率控制**：`SequenceMatcher` 比较变更幅度，< 20% 跳过重新评分（避免无意义 LLM 调用）
- **Bad Case 过滤**：无 tool call + 4 条消息以内 + assistant token < 200 → 跳过提取（节省成本）

**对我们的启示**：AgentHub 的多 Agent 协作天然产生大量 Case。Phase D 可以考虑 Agent 在群聊中解决问题后，自动提取为群内共享的 Skill。但 B1 阶段完全不需要。

### 12.2 韧性模式（生产级必备）

EverMem 的 Hook 脚本有一套完整的容错设计，我们在 B1 阶段就应该采用：

| 模式 | EverMem 实现 | 我们应采纳 |
|------|-------------|-----------|
| **永不阻塞** | 所有 Hook `continue: true`，错误 `process.exit(0)` | `_maybe_inject_memories()` 失败 → 返回 None，不让 Agent 感知 |
| **静默降级** | `npm install --silent 2>/dev/null \|\| true` | 记忆服务不可用 → 跳过注入，不影响 Agent 执行任务 |
| **重试+退避** | 3-5 次 retry，间隔 0.5-1.0s | MemoryService.search() 失败 → 3 次重试 → 仍失败则跳过 |
| **fallback 链** | LLM 聚类失败 → embedding-only；embedding 失败 → 前 N 条 | 语义检索失败 → 回退到 ORDER BY updated_at |
| **读后重试** | transcript 可能未写完，5 次重试 100ms 间隔 | 不适用（我们不走 transcript） |
| **分布式锁** | Redis 锁保护 profile/cluster/skill 的并发写入 | Phase C 多 Agent 同时写记忆时需要 |

**注入层的韧性保证**（B1 即应实现）：

```python
async def _maybe_inject_memories(self, trigger, agent) -> str | None:
    try:
        if len(trigger.content.strip()) < 10:
            return None
        memories = await self._memory_svc.search(
            agent_id=agent.id, query=trigger.content, top_k=5, min_score=0.1
        )
        if not memories:
            return None
        return self._format_memory_injection(memories)
    except Exception:
        logger.warning("Memory injection failed, skipping", exc_info=True)
        return None  # 静默降级，不阻塞 Agent
```

### 12.3 Profile 压缩与去重（LLM 驱动）

#### 问题场景

ProfileMemory 存储用户画像信息（偏好、习惯、技能水平、性格特征等）。每次对话后，后端 LLM 从 transcript 中提取新的 profile 条目。随时间累积，同一个用户的 profile 可能膨胀到几十甚至上百条，其中许多是冗余或过时的。

例如：

```
第 1 天: "用户偏好 Python"
第 3 天: "用户主要用 Python 开发后端"
第 5 天: "用户喜欢 Python 的类型提示"
第 7 天: "用户团队已全面切换到 TypeScript"
```

4 条都存着，但第 1-3 条已经过时。如果全量注入给 LLM，会误导它以为用户还在用 Python。

#### EverMem 的解决方案

**两层机制**：

**第一层：增量更新去重（每次写入时）**

`PROFILE_UPDATE_PROMPT` 要求 LLM 在写入前逐条检查已有条目：

> "Before using 'add', carefully check ALL existing items. If a similar trait/info already exists (even with different wording), use 'update' to enrich it instead of adding a duplicate."

实际操作：LLM 看到已有 `"用户偏好 Python"`，新信息是 `"用户主要用 Python 开发后端"` → 不新增，而是将第一条更新为 `"用户偏好 Python，主要用于后端开发"`。

**第二层：满容量压缩（条目数触达阈值时）**

当条目超过 `max_items`（默认 25），触发 `PROFILE_COMPACT_PROMPT`，LLM 执行三类操作：

```
输入：25+ 条 profile 条目，部分重叠、部分过时
    │
    ├─ 合并相似条目 → "当前状态 + 趋势"
    │   例: 3 条关于 Python 的合并为 "Python 是主要后端语言（2025年至今），团队已探索 Rust 但未采用"
    │
    ├─ 删除过时/琐碎条目
    │   例: "用户昨天尝试了 Vim" → 删除（一次性事件，不重要）
    │   例: "用户在用 Python 2.7" → 删除（已过时，新记忆显示用 3.11）
    │
    └─ 精炼标签
        例: ["python", "Python", "python-dev"] → ["Python"]
        例: 删除不再适用的标签（如用户已不再用 Django）
```

**关键特性**：

| 特性 | 说明 |
|------|------|
| 触发方式 | 事件驱动（count > max_items），非定时任务 |
| 操作粒度 | 一次性 LLM 调用完成，不迭代 |
| 保留审计 | 压缩后的条目包含 evidence 引用，指向原始对话 |
| 幂等性 | 相同输入 → 相同压缩结果（LLM 决定论足够强） |
| 成本 | 仅在累积到 25 条时触发，不是每轮 |

#### 这个 LLM 是谁？

**关键区分**：Profile 压缩的 LLM 与用户对话的 LLM 是**完全不同的两个实例**：

```
┌─────────────────────────────────────────────────────────┐
│ 对话 LLM（Claude CLI）                                   │
│ - 接收用户消息 + 已注入记忆                               │
│ - 不知道记忆存储/压缩的存在                               │
│ - 工作：理解用户意图、写代码、回答问题                    │
│ - API key：用户的 Claude API key                         │
└─────────────────────────────────────────────────────────┘
                    │ transcript（只读）
                    ▼
┌─────────────────────────────────────────────────────────┐
│ 后端记忆 LLM（EverCore MemoryManager）                   │
│ - 独立于对话 LLM，有自己的 API key（服务端配置）          │
│ - 不参与用户对话，只处理记忆                              │
│ - 工作：读 transcript → 提取记忆 → 压缩/去重             │
│ - 每次对话段触发 6 次调用：边界检测 + 5 种类型提取        │
│ - Profile 压缩也是它做的（第 7 种 prompt）                │
│ - 部署在 EverMem 云端服务器，用户不可见                   │
└─────────────────────────────────────────────────────────┘
```

**Profile 压缩的完整流程**：

```
1. 对话 LLM 完成对话 → transcript 产出（JSONL 文件）
2. Stop Hook 读取 transcript → 上传到 EverMem Cloud API
3. 后端记忆 LLM 读取已有 profile（当前 25+ 条）+ 新 transcript 内容
4. 后端记忆 LLM 执行 PROFILE_COMPACT_PROMPT：
   a. 分析：哪些条目相似/过时/琐碎
   b. 合并：3 条 Python 相关 → 1 条 "当前状态 + 趋势"
   c. 删除：Python 2.7 条目（已过时，新记忆显示用 3.11）
   d. 精炼：重复标签去重，删除不再适用的标签
   e. 输出：<25 条压缩后的 profile
5. 压缩结果写回 MongoDB + 重新 embedding 写入 Milvus
6. 下次对话 LLM 启动时，SessionStart Hook 拉取的是压缩后的版本
```

**对话 LLM 完全不知道压缩发生过**。它只看到最新一版的 profile。

#### 对我们的影响

EverMem 和我们 Phase B1 的本质区别：

| 维度 | EverMem | 我们 Phase B1 |
|------|---------|-------------|
| **存记忆的 LLM** | 后端独立 LLM（6-7 次调用/段对话） | **对话 LLM 自己**（Agent 回复中输出 `[MEMORY:]` 标记） |
| **额外 LLM 成本** | 高（每段对话额外 6-7 次调用） | **零** |
| **压缩/去重 LLM** | 后端独立 LLM（阈值触发，1 次调用） | **不需要**（Agent 主动存，量可控） |
| **记忆质量** | 取决于提取 LLM 的能力 | 取决于对话 Agent 的判断力 |
| **基础设施** | 后端 LLM API key + 调用管理 + 速率限制 | 零新增（走已有 Agent 回复解析链路） |

**Phase B1 不做后端记忆 LLM 的原因就在这里**：EverMem 每段对话要额外消耗 6-7 次 LLM 调用用于记忆处理（提取 + 压缩）。我们先用对话 Agent 自身的判断力（`[MEMORY:]` 标记）零成本起步，验证记忆价值后再考虑是否引入后端提取 LLM。

### 12.4 不存在的机制（确认设计边界）

以下 EverMem **没有**实现的机制，确认我们可以安全跳过：

| 机制 | EverMem 状态 | 我们的决策 |
|------|-------------|-----------|
| TTL/时间衰减 | **无** | B1 不实现（与 EverMem 一致） |
| 定期去重扫描 | **无** | 不需要 |
| 跨用户记忆共享 | **无**（仅 group_id 隔离） | Phase D 前不实现 |
| 记忆版本管理 | **无** | Append-Only 已足够 |
| 记忆回滚 | **无** | 不需要 |

---

## 十三、B1 不做清单（设计边界）

> 以下能力已明确排除在 Phase B1 范围外。每一项都标注了推迟理由和目标 Phase，
> 防止实施时范围蔓延。

### 13.1 存储与检索

| 不做 | 理由 | 目标 Phase |
|------|------|-----------|
| **后端被动提取**（读 transcript → LLM 提取记忆） | 每段对话额外 6-7 次 LLM 调用，成本高；B1 用 `<!-- MEMORY: -->` 标记零成本替代 | Phase C |
| **向量检索**（pgvector / embedding） | B1 记忆量 < 50 条/Agent，`ORDER BY updated_at` 足够 | Phase C |
| **全文检索**（tsvector / BM25） | 同上，量小不需要关键词索引 | Phase B2 |
| **Elasticsearch hybrid search** | 需 +1 容器 + 索引同步管道，记忆量 < 1K 条时 ROI 为负 | Phase E |
| **MongoDB 文档存储** | 记忆结构确定（type/title/content/timestamps），PG `TEXT + JSONB` 足够；加 MongoDB 需 +1 容器 + 备份 + 监控 | 待评估（记忆内容高度异构时） |

### 13.2 去重与质量管理

| 不做 | 理由 | 目标 Phase |
|------|------|-----------|
| **语义去重**（LLM ADD/UPDATE/DELETE） | 需要后端记忆 LLM 对比已有条目 + 新内容，B1 不引入额外 LLM 调用 | Phase B2 |
| **向量聚类**（cosine similarity → cluster） | 需要 embedding 基础设施 | Phase C |
| **Profile 压缩**（LLM 合并相似/删除过时/精炼标签） | 阈值触发（>25 条），B1 记忆量远未达到 | Phase B2 |
| **Case → Skill 演化**（LLM 聚类 + 增量更新 + 成熟度评分） | EverMem 最复杂的子系统，需要独立 LLM 管道 | Phase D+ |
| **metadata sub_type 强制校验** | B1 仅 JSONB 存储，不强制 schema | Phase B2 |

### 13.3 多 Agent 协作

| 不做 | 理由 | 目标 Phase |
|------|------|-----------|
| **跨 Agent 记忆共享**（群内 Agent 可见彼此记忆） | 需要权限模型 + 共享策略设计，B1 每 Agent 独立 | Phase D |
| **群级记忆**（group_id 关联的记忆检索） | 表已预留 `group_id` 列，但 B1 检索只按 `agent_id` | Phase D |
| **分布式写入锁**（Redis 锁保护并发写入） | B1 单 Agent 串行写入，无并发冲突 | Phase C |

### 13.4 生命周期管理

| 不做 | 理由 | 目标 Phase |
|------|------|-----------|
| **TTL 自动过期**（`expires_at` 定时清理） | 表已预留 `expires_at` 列，B1 不实现 cron 清理 | Phase B2 |
| **定期去重扫描**（全表扫描合并重复） | EverMem 也没有；Append-Only + 读取侧去重已覆盖 | 不做 |
| **记忆容量硬上限**（每 Agent N 条强制淘汰） | B1 记忆量可控（Agent 主动标记，非全量录制），暂不需要 | Phase B2 |
| **记忆版本管理 / 回滚** | EverMem 也没有；Append-Only 保留完整历史已满足审计需求 | 不做 |
| **hits 计数自动更新**（读取时 +1） | B1 检索走 `ORDER BY updated_at DESC`，hits 字段预留但暂不使用 | Phase B2 |

### 13.5 基础设施

| 不做 | 理由 | 目标 Phase |
|------|------|-----------|
| **MCP Server / MCP tool**（`save_memory` tool 注册） | B1 用 `<!-- MEMORY: -->` 标记走现有 stdout 解析通道，不引入 MCP 协议栈 | 待评估 |
| **独立记忆服务进程**（gRPC/HTTP 记忆微服务） | 5 人团队，部署复杂度与收益不匹配；L3 Service 内嵌足够 | 不做（除非多项目共享记忆） |
| **记忆写入 Hook**（Stop 事件 → 自动提取） | 需要 Hook 基础设施 + 独立 LLM 调用 | Phase C |

### 13.6 为什么这些决策是安全的

1. **Append-Only + 读取去重** 在 < 50 条规模下不会产生不可接受的噪声
2. **Agent 主动标记**（非全量录制）意味着记忆增长率低（预计 2-5 条/会话），不会快速膨胀
3. **所有推迟的能力都有明确的触发条件**（记忆量 > 50 条、检索不准、多 Agent 协作需求），不是"永远不做"
4. **表结构已预留扩展列**（`metadata JSONB`、`expires_at`、`group_id`），未来不需要迁移改表
5. **Repository 接口已预留参数**（`search(query, top_k)`），切换检索引擎只需换实现，不改调用方

---

## 十四、B1 后续增强：回复级 LLM 自动提取

> 状态：**设计记录** | 实施时机：B1 完成后
> 问题：B1 的 `<!-- MEMORY: -->` 标记依赖 Agent 自觉——Agent 可能忘记写标记、判断失误、格式错误。
> 方案：每次 Agent 回复后，一次廉价 LLM 调用兜底提取。

### 14.1 问题

B1 的写入路径是「Agent 主动标记」：

```
Agent 回复中输出 <!-- MEMORY:facts --> content
    → ChatService.parse_markers() 解析
    → MemoryService.save_from_markers() 存入 PG
```

这条路径的前提是 Agent 照做。但实际情况：

- Agent 可能忘了（回复中不含标记行）
- Agent 可能判断失误（该记的没记）
- Agent 可能格式错误（写了 `[MEMORY:facts]` 而不是 `<!-- MEMORY:facts -->`）
- Agent 可能过度标记（什么都记，产生噪声）

这不是工程可依赖的确定性机制。

### 14.2 方案：Marker + LLM 兜底双路径

关键设计决策：**LLM 提取异步 fire-and-forget，不阻塞用户看到回复。**

B1 的 Marker 解析是同步的——正则匹配毫秒级，PG 写入也毫秒级，放在 `_stream_one_agent` 落库前执行没问题。但 LLM 调用延迟 1-3 秒，放在同一位置会阻塞整个回复管道。

LLM 提取的定位是「下次检索时才用到的数据」，不是本轮必须完成的事。所以用 `asyncio.create_task` 在后台跑：

```
Agent 回复完成
        │
        ├─ 同步路径（阻塞，必须完成）:
        │   parse_markers() → 有标记?
        │   ├─ 有 → save_from_markers() → PG 毫秒级
        │   └─ 没有 → 跳过
        │   assistant_msg.content = cleaned_content
        │   await messages.save()           ← 消息先落库
        │   await l1.append()               ← L1 更新
        │   yield DONE                       ← 用户立即看到回复
        │
        └─ 异步路径（fire-and-forget，不阻塞）:
            有标记? → 跳过（标记路径已覆盖）
            没有标记 + 门控通过?
              → asyncio.create_task(_extract_and_save())
              → 1-3 秒后 LLM 返回 → save_from_markers() → PG
              → 用户无感知，下次检索时可用
```

**为什么记忆写入可以接受延迟**：

记忆的使用方是「下一轮对话的检索注入」，不是本轮。LLM 提取晚 1-3 秒写入 PG，对用户本轮体验零影响。最坏情况：用户在 1 秒内连发两条消息，第二条消息的检索可能还拿不到第一条的 LLM 提取结果。但这只是 B1 兜底路径的边界 case——大部分记忆来自 Marker（立即写入），LLM 提取是补漏。

```python
# chat_service.py:_stream_one_agent — 示意

full = "".join(buffer)

# === 同步路径：Marker 解析（毫秒级） ===
cleaned_content, mem_entries = MemoryService.parse_markers(full)
if mem_entries:
    await self._memory_svc.save_from_markers(
        agent_id=target.id, mem_entries=mem_entries,
        group_id=group.id if group else None,
    )

assistant_msg.content = cleaned_content
await self._messages.save(assistant_msg)     # 消息落库
await self._l1.append(session.id, {...})     # L1 更新
# ... yield DONE ...                          # 用户看到回复 ← 到这里同步路径结束

# === 异步路径：LLM 兜底（fire-and-forget） ===
if not mem_entries and settings.memory_extraction_enabled:
    asyncio.create_task(
        self._extract_memories_async(
            cleaned_content, target.id,
            group.id if group else None,
        )
    )
    # ↑ 不 await，直接返回。task 在后台 1-3 秒内完成。

### 14.3 触发门控与实现

不是每轮 Agent 回复都调 LLM。门控条件：

```python
def _should_extract(self, agent_reply: str, turns_since_last: int) -> bool:
    """判断是否需要 LLM 兜底提取。"""
    if _MEMORY_MARKER_RE.search(agent_reply):
        return False          # 已有标记 → 跳过
    if len(agent_reply) < 100:
        return False          # 回复太短 → 跳过
    if turns_since_last < 3:
        return False          # 上一轮刚提取过 → 跳过
    return True
```

估计实际触发率 30-40%，每 3 轮对话触发一次。

LLM 提取 Prompt 模板（注入 `prompt_templates.py`）：

#### System Prompt

```
你是记忆提取助手。你的任务是从 AI Agent 的回复中提取值得长期记住的信息，
归类为四种记忆类型之一。只提取有长期价值的信息，忽略临时状态和闲聊。

## 记忆类型定义

| 类型         | 定义                                       | 示例                                        |
|-------------|-------------------------------------------|--------------------------------------------|
| facts       | 项目相关的确定性知识：架构决策、技术栈、API 约定、配置参数 | "JWT 过期时间 7 天，算法 HS256"               |
| preferences  | 用户/团队的工作偏好：沟通风格、工具选择、审批习惯      | "用户偏好用 ruff 格式化而非 black"             |
| procedures  | 可复用的操作流程：部署步骤、排错方法、常见任务流程     | "部署命令 docker compose up -d --build"      |
| context     | 短期任务状态：当前进度、最近决策、下一步计划          | "本周目标：完成记忆系统 B1 实现"              |

## 提取规则

1. 只提取 Agent 回复中**新出现的、值得长期保留**的信息
2. 不要提取用户已经知道的信息（如 Agent 复述用户的问题）
3. 不要提取临时状态：当前时间、临时变量值、一次性调试结果
4. 不要提取闲聊：问候、确认语（"好的""明白了""已处理"）
5. 不要提取代码实现细节：具体函数名、变量名、临时的代码片段
6. 一条记忆 = 一个独立知识点，不要合并多个不相关的事实
7. 确实没有值得记的 → 返回空数组 []

## Few-shot 示例

输入:
"JWT 配置在 .env 的 JWT_EXPIRE_DAYS，默认 7 天。用 HS256 算法签名。密钥通过 JWT_SECRET 注入。"
输出:
[{"type": "facts", "content": "JWT 过期时间 7 天，算法 HS256，配置键 JWT_EXPIRE_DAYS，密钥通过环境变量 JWT_SECRET 注入"}]

输入:
"好的，我帮你把那个 bug 修了。原因是 CORS 中间件没加 allow_origins。改好了。"
输出:
[]  ← 一次性修复，没有长期价值

输入:
"用户说以后回复尽量简洁，不要解释过程。另外他们团队用 ruff 做 lint，不用 black。"
输出:
[{"type": "preferences", "content": "用户偏好简洁回复，不要解释过程"}, {"type": "preferences", "content": "使用 ruff 而非 black 做 Python lint"}]

输入:
"今天已经把 B1 的 Markdown 渲染完成了。明天开始做 @mention 高亮。"
输出:
[{"type": "context", "content": "B1 Markdown 渲染已完成，下一步 @mention 高亮"}]

输入:
"部署步骤：先 build 镜像，然后 push 到 registry，最后在服务器上 restart compose。注意 restart 前要备份数据库。"
输出:
[{"type": "procedures", "content": "部署流程：build 镜像 → push registry → backup DB → docker compose restart"}]
```

#### User Message 模板

```
## Agent 角色
{agent_role} | 能力: {capability_tags}

## Agent 回复
{agent_reply}
```

#### 模型配置

| 参数 | 值 | 理由 |
|------|-----|------|
| 模型 | DeepSeek V4 Flash | 极廉价，已有 API key（复用 Selector） |
| temperature | 0 | 提取任务不需要创造性，0 保证输出稳定 |
| max_tokens | 512 | 5 条记忆 × 100 tokens 足够 |
| response_format | `{"type": "json_object"}` | 强制 JSON 输出 |

异步提取函数（`chat_service.py` 新增）：

```python
async def _extract_memories_async(
    self, text: str, agent_id: UUID, group_id: UUID | None
) -> None:
    """后台 fire-and-forget：LLM 提取 + 去重 + 写入。失败静默。"""
    try:
        entries = await asyncio.wait_for(
            self._memory_svc.extract_from_reply(text),
            timeout=10.0,
        )
        if entries:
            await self._memory_svc.save_from_markers(agent_id, entries, group_id)
    except asyncio.TimeoutError:
        logger.warning("Memory extraction timeout for agent=%s", agent_id)
    except Exception:
        logger.warning("Memory extraction failed", exc_info=True)
```

### 14.4 成本估算

| 维度 | 数值 |
|------|------|
| LLM 调用频率 | ~1 次/3 轮对话 |
| 模型 | DeepSeek V4 Flash（已有，`Selector` 复用同一 API key） |
| 单次 input | ~500 tokens（Agent 回复 + System Prompt） |
| 单次 output | ~100 tokens（JSON 数组） |
| 每次成本 | ~¥0.0006 |
| 每日 300 轮对话 | ~100 次提取 ≈ ¥0.06 |

成本可以忽略不计。

### 14.5 与 Phase C 被动提取的区别

| 维度 | 本方案（B1 后增强） | Phase C 被动提取 |
|------|-------------------|-----------------|
| 触发时机 | Agent 回复**单轮** | 会话结束时**批量** |
| 输入 | 单条 Agent 回复 | 完整 transcript（多轮对话 + 上下文） |
| LLM 调用 | 1 次/触发（逐轮） | 6-7 次/会话（边界 + 5 类提取） |
| 提取类型 | facts/preferences/procedures/context | 全部 5 种 + Cluster + Skill |
| 成本 | ~¥0.0006/次 | ~¥0.05-0.1/会话 |
| 基础设施 | 复用已有 `Selector` 的廉价 LLM | 需要独立记忆 LLM 管道 |
| 复杂度 | ~80 行（prompt 模板 + 门控 + 调用） | ~500+ 行（边界检测 + 5 类提取器 + 聚类 + 压缩） |
| 目标 | **兜底 B1 Marker 的遗漏** | **全量自动记忆管理** |

本方案是 Phase C 的**极简子集**——只做「单轮回复提取」，不做「全量 transcript 分析」，不做聚类/压缩/演化。

### 14.6 实施清单

| 文件 | 改动 | 行数 |
|------|------|------|
| `application/services/memory_service.py` | 新增 `extract_from_reply(text) → list[dict]` LLM 调用 | ~40 |
| `application/services/prompt_templates.py` | 新增 `MEMORY_EXTRACTION_PROMPT` 模板 | ~15 |
| `application/services/chat_service.py` | `_stream_one_agent` 中插入 `_maybe_extract_memories()` | ~20 |
| `core/config.py` | 新增 `memory_extraction_enabled: bool = False` 开关 | ~3 |

~80 行，改动集中在已有模块。

### 14.7 启用策略

建议用 feature flag 控制，不默认开启：

```
B1 完成 → 观察 Marker 路径的实际命中率（1-2 周）
         → 如果 Marker 覆盖 < 60% 的关键记忆场景 → 开启 LLM 兜底
         → 如果 Marker 覆盖 ≥ 80% → 继续观察，不急着开
```

---

*文档结束。此为方向评估，非最终设计。实施前需确认开放问题 + 与其他方向对比后决策。*
