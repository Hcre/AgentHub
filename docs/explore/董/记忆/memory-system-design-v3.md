# AgentHub 记忆系统 — V3 设计方案

> 日期：2026-06-02 | 状态：**设计方案**
> 前置阅读：`memory-system-design-v1.md`（v1 文件方案，已废弃）、`memory-system-design-v2.md`（v2 探索）
> 参考：Claude Code 记忆机制分析 — 结构化文件 + LLM 选择器 + 时间感知

---

## 一、核心决策

### 1.1 一句话总结

AgentHub 的记忆 = **用户主动发起、PG 存储、LLM 检索、SP 注入、前端可见**。不碰自动记忆（归 CLI），不与 CLI memory 冲突。

### 1.2 与 v1 的根本差异

| 维度 | v1（文件方案） | v3（当前方案） |
|------|--------------|--------------|
| **触发** | CLI 自动写入 | **用户主动**（前端填 / 聊天指令） |
| **存储** | 本地 markdown 文件 | **PG** |
| **检索** | GREP + Read 工具 | **LLM 选择器**（从候选集选 ≤5 条） |
| **注入标签** | `<system-reminder>`（CLI 标签） | **`<agenthub-reminder>`**（自有标签） |
| **Pin** | 无 | **一等公民**（绕过 LLM，始终注入） |
| **群共享** | 通过文件间接 | group_id 字段，原生支持 |
| **前端** | 不可见 | MemoryPanel 面板 |
| **自动记忆** | 核心机制 | **不实现，归 CLI** |
| **CLI 耦合** | 强依赖三层注入 | **无耦合**，任何 CLI 都可用 |

---

## 二、架构全景

```
┌─────────────────────────────────────────────────────────────────┐
│                     前端 MemoryPanel                              │
│  创建 / 编辑 / 删除 / Pin / 按 type 过滤 / 衰减分数展示           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API
┌──────────────────────────▼──────────────────────────────────────┐
│                   MemoryService（CRUD）                          │
│  创建记忆 / 更新内容 / Pin 切换 / 删除 / hits 计数               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                      PG memories 表                              │
│  id, agent_id, group_id, user_id, name, description, type,      │
│  content, pinned, hits, created_at, updated_at, metadata JSONB  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 候选集查询
┌──────────────────────────▼──────────────────────────────────────┐
│                  MemorySelector（LLM 检索）                       │
│  候选集 → Haiku 选择 ≤5 条 → 返回相关记忆                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 选中的记忆
┌──────────────────────────▼──────────────────────────────────────┐
│              SystemPromptBuilder（注入到 SP）                     │
│  <agenthub-reminder> 包裹，带时间 + pin 标注                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、存储设计

### 3.1 PG 表结构

```sql
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,   -- scope='group' 时必填
    user_id UUID NOT NULL REFERENCES users(id),              -- 创建者
    scope VARCHAR(10) NOT NULL CHECK (scope IN ('agent', 'group')),
      -- 'agent':  Agent 私有记忆（跨群复用、私聊），group_id = NULL
      -- 'group':  群组共享记忆，group_id 指向群组
    name VARCHAR(150) NOT NULL,                              -- 简短标识
    description VARCHAR(300) NOT NULL,                       -- 一句话摘要（LLM 检索关键字段）
    content TEXT NOT NULL,                                   -- 全文
    source VARCHAR(20) NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'chat', 'system')),
      -- 'manual': 前端 Panel 手动填写
      -- 'chat':   聊天中 Agent 通过 save_memory Tool 写入
      -- 'system': 系统自动生成（预留）
    pinned BOOLEAN NOT NULL DEFAULT false,
    hits INT NOT NULL DEFAULT 0,                             -- 被检索命中次数
    metadata JSONB NOT NULL DEFAULT '{}',                    -- {why, how_to_apply, tags, ...}
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_memories_agent_scope ON memories(agent_id, scope);
CREATE INDEX idx_memories_group ON memories(group_id) WHERE group_id IS NOT NULL;
CREATE INDEX idx_memories_pinned ON memories(agent_id, scope, pinned) WHERE pinned = true;
CREATE INDEX idx_memories_updated ON memories(agent_id, scope, updated_at DESC);
```

### 3.2 存储选型理由

| 需求 | PG 支持 | 文件方案支持 |
|------|:---:|:---:|
| 按 agent/type/pin 过滤 | 原生 SQL | 应用层解析 frontmatter |
| 群共享并发写入 | 事务保护 | 文件锁，复杂 |
| 前端分页查询 | `LIMIT/OFFSET` | glob + 解析后切片 |
| 多实例部署 | 天然共享 | 需要 NFS |
| hits 计数更新 | 原子 `UPDATE hits = hits + 1` | 读-modify-写竞态 |
| LLM 检索候选集 | `ORDER BY pinned DESC, updated_at DESC LIMIT 50` | glob + sort |

瓶颈在 LLM 检索调用（~200ms），不在存储读写（~1ms）。PG 在元数据管理上明显更优，且前端 API 已指向 PG 路径。

---

## 四、LLM 检索机制

### 4.1 为什么不用向量检索

Claude Code 的结论：用 LLM 做选择题 > 向量相似度计算。理由：

| | 向量检索 | LLM 选择器 |
|---|---|---|
| **准确性** | 数值相似度，阈值难定 | 自然语言判断，可解释 |
| **时间感知** | 无（只要相似就召回） | LLM 能理解「3 天前可能已过时」 |
| **运维成本** | embedding pipeline + 向量索引 | 零额外基础设施 |
| **延迟** | embedding 计算 + 相似度排序 | ~200ms（候选集小时） |

候选集通常不超过 50 条（pinned + 最近 N 条），用嵌入式的价值不大。**Haiku 足以胜任选择任务**。

### 4.2 检索流程（单 Agent）

```
每次构建 SP 前：

1. 查询候选集（scope 决定检索范围）

   群聊（为 Agent A 构建 SP）：
   -- group 记忆不按 agent_id 过滤，群内所有 Agent 的群记忆都可见
   -- agent 记忆只取 Agent A 自己的
   
   SELECT * FROM memories
   WHERE (
     (scope = 'group' AND group_id = $2)           -- 群内所有 Agent 创建的群记忆
     OR (scope = 'agent' AND agent_id = $1)         -- 只有 Agent A 的私有记忆
   )
   ORDER BY pinned DESC, updated_at DESC
   LIMIT 50

   私聊（为 Agent A 构建 SP）：
   -- 只取 Agent A 的私有记忆
   
   SELECT * FROM memories
   WHERE agent_id = $1 AND scope = 'agent'
   ORDER BY pinned DESC, updated_at DESC
   LIMIT 50

2. 拼装候选清单（只含 name + description + scope + pinned + 创建时间，不含全文）
   [1] 前端规范 — 用户希望回复简洁，不要加总结段落 (agent, pinned, 今天)
   [2] JWT 策略 — 过期时间 7 天，refresh 30 天 (group, 3 天前)
   ...

   候选清单不传 hits 字段。原因：hits 是后验指标（被选中才 +1），加入候选清单会形成
   反馈循环——曾被选中的更容易再被选中，新记忆永远没机会露脸。时间信息（created_at）
   已隐含 recency，不需要 hits 重复表达。前端 decayScore 用 hits 展示没问题，
   但不适合做检索信号。

3. 调用 Haiku 选择 ≤5 条相关记忆

4. 选中的记忆写入 SP → hits 计数 +1（批量 UPDATE）
```

### 4.2b 群聊：按需检索（嵌入 Selector 流程）

群聊不是所有 Agent 同时发言。Selector 决定每轮激活谁：

```
用户消息
  │
  ▼
Selector.pick()
  ├─ Layer 1: @mention → 直接指定 Agent B
  ├─ Layer 1.5: 「大家/各位」→ pick_multi 多个 Agent
  ├─ Layer 2: capability_tags 关键词匹配 → 指定 Agent C
  └─ Layer 3: LLM 决策 → 指定 Agent D 或 DONE
  │
  ▼
ContextBuilder.build_for_agent(selected_agent)  ← 只构建被选中的
  ├─ 查询候选集（该 Agent 的 scope=agent + 群 scope=group）
  ├─ LLM 选择器 ≤5 条
  └─ 拼入 SP 的 <agenthub-reminder>
  │
  ▼
adapter.stream() → Agent 发言
```

**关键结论**：记忆检索不需要 `select_memories_for_group()` 那种全局并行。它天然是**单 Agent、按需触发**的，嵌入在 `build_for_agent()` 内部。Selector 选谁，就给谁检索记忆。

延迟分析：

| 场景 | Selector 决策 | 记忆检索 | 总增加延迟 |
|------|:---:|:---:|:---:|
| @mention 直达 | ~0ms | DB + LLM ≈ 200ms | 200ms |
| capability 匹配 | ~0ms | DB + LLM ≈ 200ms | 200ms |
| LLM 决策 | ~200ms | DB + LLM ≈ 200ms | 400ms（可并行） |
| Broadcast 多人 | ~0ms | N × 200ms 串行 | N × 200ms（需优化，见下） |

Broadcast 场景（Layer 1.5 命中「大家/各位」）：已知全员激活，没有「谁被选中」的不确定性。直接 `asyncio.gather` 并行所有 Agent 的记忆检索，不走 Selector → Memory 串行链。

```python
# Broadcast 路径特殊处理
if decision.reason.startswith("broadcast"):
    memories = await asyncio.gather(*[
        select_memories(agent) for agent in members
    ])
    # 总延迟 ≈ 200ms，与 Agent 数量无关
```

### 4.2c 延迟优化策略（二选一，暂不选定）

Selector LLM 决策 + Memory LLM 检索，两个 Haiku 调用串行叠加 ≈ 400-1000ms，在网络波动时可能接近 1-2 秒。

**策略 A：按需检索（默认，保守）**

不做预计算。Selector 返回后才对选中的 Agent 做记忆检索。

```
Selector LLM ████████ (300ms) → 返回 Agent B
                                   Memory LLM ████████ (300ms)
  总延迟: ~600ms
```

优点：零浪费，没被选中的 Agent 不做检索。
缺点：Layer 3 LLM 决策时，Selector + Memory 串行叠加延迟。

**策略 B：全量预计算（激进）**

当 Selector 将走 Layer 3 LLM 决策时，并行预计算所有 Agent 的记忆。Selector 返回后直接用。

```
Selector LLM ████████ (300ms)
Agent A Memory LLM ████████ (300ms)  ─┐
Agent B Memory LLM ████████ (300ms)  ─┤ 全部并行
Agent C Memory LLM ████████ (300ms)  ─┘
总延迟: max(300ms, 300ms) = 300ms
```

```python
if selector_will_use_llm:                    # Layer 3
    decision_task = selector.pick(...)        # Selector LLM
    memory_tasks = {a.id: select_memories(a) for a in members}  # 全量并行
    decision = await decision_task
    memories = await memory_tasks[decision.next_agent_id]  # 直接用
else:                                         # Layer 1/1.5/2
    decision = await selector.pick(...)        # 即时返回（零 LLM）
    memories = await select_memories(decision.next_agent_id)  # 只算被选中的
```

优点：Layer 3 路径下 Memory 延迟被 Selector 延迟遮盖，实际只增加 ~0ms。
缺点：浪费 N-1 次 Haiku 调用（N=5 时约 $0.0005）。Selector 命中 Layer 1/1.5/2 时退化为策略 A。

| | 策略 A（按需） | 策略 B（预计算） |
|---|---|---|
| Layer 1/2 延迟 | ~200ms | ~200ms |
| Layer 3 延迟 | ~600ms | ~300ms |
| 浪费 LLM 调用 | 0 | N-1 次/轮 |
| 实现复杂度 | 低 | 中 |

**暂不选定**，待 Selector + Memory 双系统跑通后实测延迟数据再决定。

### 4.2d 私聊

私聊只检索 `scope = 'agent'` 的记忆（Agent 私有记忆），单 Agent 无需并行：

```
SELECT * FROM memories
WHERE agent_id = $1 AND scope = 'agent'
ORDER BY pinned DESC, updated_at DESC
LIMIT 50
```

候选集 → LLM 选择 ≤5 条 → 注入 SP。流程同 4.2。

### 4.3 LLM 选择 prompt

```
You are a memory relevance judge. Given a conversation context and a list of
candidate memories, select up to 5 memories that are DIRECTLY relevant to the
current conversation.

Current conversation:
{dialogue_context}

Candidate memories:
{candidate_list}

Instructions:
- Only select memories that are clearly relevant to the current conversation.
- If uncertain, skip. Better to miss a relevant memory than to inject noise.
- Pinned memories should be selected UNLESS they are clearly irrelevant.
- Return ONLY the IDs of selected memories, one per line.
```

**`dialogue_context` 构造规则**：

| 场景 | 来源 | 截断 |
|------|------|------|
| 群聊 | `group_delta_text`（已有字段，原始消息） | 取最近 10 条消息，每条 ≤300 字符，总计 ≤3000 字符 |
| 私聊 | L1 窗口（`MemoryContext.l1_working`） | 同上 |

不调 LLM 做摘要——候选集的 `name` + `description` 已经足够短（≤150 字符），原始消息直接传即可。截断策略确保不因超长消息撑爆选择 prompt。

### 4.4 Pin 绕过

Pinned 记忆**不参与 LLM 检索**，直接注入。这是用户明确钉选的内容，无条件要看到。

Pin 的作用：
- 重要内容不因时间衰减被淘汰
- 不消耗 LLM 选择的 5 条名额
- 前端醒目展示（border-brand + pin 图标）

---

## 五、记忆内容结构规范

> 参考 CC 的四类型 `<when_to_save>` / `<how_to_use>` / `<body_structure>` 规范。

### 5.1 核心纪律

**只存代码推不出来的东西**。代码能 grep 到的信息存进记忆 = 权威的错误。

### 5.2 双通道反馈

CC 的 feedback 类型有一个关键设计：**记录失败 AND 成功**。只记纠正不记确认，Agent 行为会逐渐漂移——它知道什么不该做，但忘了什么该做。

- 用户说「不要 mock 数据库」→ 记（纠正）
- 用户说「对，就是这样，单 PR 提交」→ 也要记（确认）
- 确认型偏好更难捕捉，但同等重要

### 5.3 推荐正文结构

建议包含结构化字段（存在 `metadata` JSONB 中，前端可展开）：

```yaml
metadata:
  why: "上季度 mock 测试通过但 prod 迁移挂了"         # 为什么有这条规则
  how_to_apply: "所有标了「集成测试」的 case 都适用"   # 什么场景下生效
  source_message: "msg_abc123"                       # 来源消息 ID（可追溯）
```

为什么 `why` 重要：只记规则不记原因，Agent 在边界情况下无法独立判断该不该破例。

### 5.4 description 是检索索引

`description` 字段不是给人看的摘要，是给 LLM 选择器做**相关性匹配的关键词来源**。写法上应该：
- 包含会被搜索到的关键词
- 写清楚「这条记忆在什么场景下应该被选中」
- 例：「JWT 过期策略：access 7 天，refresh 30 天，适用于所有 auth 相关对话」

---

## 六、注入格式

### 6.1 `<agenthub-reminder>` 标签

为什么不用 `<system-reminder>`：

| | `<system-reminder>` | `<agenthub-reminder>` |
|---|---|---|
| **管理者** | CLI | AgentHub |
| **内容** | CLAUDE.md / MEMORY.md / rules | AgentHub 管理的记忆 |
| **刷新时机** | CLI 决定 | 每次构建 SP 时 |
| **冲突风险** | 与 CLI 内置指令混在一起 | 独立标签，CLI 不识别也不冲突 |

### 6.2 注入格式（含漂移防御）

```
<agenthub-reminder>
以下是与当前对话相关的群组记忆。

⚠️ 记忆反映保存时的状态，可能已过时。
在采纳记忆中的建议前，必须主动验证其中的事实：

- 如果记忆提到了文件路径 → 先检查文件是否存在
- 如果记忆提到了函数名或配置项 → 先 grep 确认
- 如果记忆提到了项目状态（「正在做 X」）→ 先检查当前代码/文档确认
- 记忆说「X 存在」≠「X 现在还存在」

如果用户要求忽略记忆中的内容，以用户指令为准，不要引用记忆来反驳。

━━━ PINNED ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 [记忆 #1] — 用户偏好，今天保存
**摘要**: 用户希望回复简洁，不要加总结段落
**内容**: （全文）

━━━ 相关记忆 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 [记忆 #2] — 3 天前保存
⚠️ 已保存超过 2 天，可能已过时。
**摘要**: 后端使用 SQLAlchemy 2.0 async session，数据库 PostgreSQL 16
**内容**: （全文）

📄 [记忆 #3] — 今天保存
**摘要**: 所有 API 端点必须在 deps.py 注册依赖注入
**内容**: （全文）
</agenthub-reminder>
```

### 6.3 漂移防御的设计要点

| 机制 | 作用 |
|------|------|
| **行动导向的验证指令** | 「先检查文件是否存在」优于「注意记忆可能过期」（CC A/B 测试：行动导向 3/3 vs 抽象 0/3） |
| **具体验证步骤** | 文件路径 → ls、函数名 → grep、项目状态 → 读当前代码。不给模糊指令 |
| **忽略语义** | 「以用户指令为准，不要引用记忆反驳」——不是「承认然后覆盖」，是彻底忽略 |
| **时间标注** | 2 天/30 天两档警告，让 Agent 自然形成「越旧越不信」的态度 |

时间标注规则：

| 年龄 | 标注 |
|------|------|
| 今天 / 昨天 | 不警告 |
| ≥ 2 天 | ⚠️ 已保存超过 2 天，可能已过时 |
| ≥ 30 天 | ⚠️ 已保存超过 30 天，强烈建议验证 |

---

## 七、写入机制

### 7.1 两条路径，同一存储

```
路径 1：前端 Panel 手动填写
  用户 → MemoryPanel → POST /api/agents/{id}/memories → MemoryService.create() → PG

路径 2：聊天 @Agent 指令
  用户 → "@Agent 记住 xxx" → Agent 调用 save_memory Tool → MemoryToolHandler → PG
```

两种路径写入同一张 `memories` 表，前端同一套展示。

### 7.2 Tool 接入架构：内嵌 MCP 端点

Claude Code 原生支持 MCP 协议。不需要自己造轮子。

**架构**：

```
Agent CLI 进程
  │
  ├─ Read / Write / Edit / Bash / Grep ...  → CLI 自处理
  │
  └─ save_memory / get_memory              → HTTP SSE → AgentHub MCP 端点
                                                          │
                                                          └─ MemoryService → PG
```

Agent 通过 MCP 的 `tools/list` 看到完整工具列表，`save_memory`/`get_memory` 与原生工具无差别。

**三步接入**：

**Step 1 — MCP 端点**（FastAPI 内嵌，与 AgentHub 同进程）：

```python
# src/backend/app/api/mcp_memory.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("agenthub-memory")

@mcp.tool()
async def save_memory(
    name: str,
    description: str,
    content: str,
    group_id: str | None = None,
) -> dict:
    """保存用户主动要求的记忆。用户说「记住 xxx」时调用。"""
    ...
```

只提供一个 tool。不提供 `get_memory`——每次 `build_for_agent()` 已经自动检索并注入相关记忆，Agent 不需要自己查。两个入口会导致 Agent 不确定该信任 SP 里注入的记忆还是自己查到的。

通过 SSE transport 挂到 FastAPI router：`/api/mcp/sse`

**Step 2 — CLI 启动时注入 MCP 配置**：

> ⚠️ 实施前确认：`claude --help | grep -i mcp` 验证 flag 名称。若 CLI 不支持 `--mcp-config`，fallback：spawn 前写入 `~/.claude/.mcp.json`（CLI 默认 MCP 配置文件路径），exit 后恢复。

```python
# claude_code_runtime.py — _build_cmd() 追加
cmd = [
    "claude",
    "--output-format", "stream-json",
    "--verbose", "--print",
    "--permission-mode", self._permission_mode,
    "--max-turns", str(self._max_turns),
    "--mcp-config", mcp_config_path,   # ← 新增（需验证 flag 名）
]
```

`mcp_config.json` 内容：

```json
{
  "mcpServers": {
    "agenthub-memory": {
      "type": "sse",
      "url": "http://127.0.0.1:{port}/api/mcp/sse"
    }
  }
}
```

**临时文件清理**：用 `tempfile.NamedTemporaryFile` + `atexit.register` 保证 crash 时也清理。FastAPI shutdown event 兜底扫描 `/tmp/agenthub_mcp_*.json`。

**Step 3 — SP 中声明工具**：

```
# Memory
使用 save_memory 保存用户主动要求的记忆（用户说「记住 xxx」时）。
已有记忆会自动注入到每次对话中，不需要你主动查找。
个人自动记忆由系统管理，不需要你主动写入文件。
```

**完整生命周期**：

```
CLI spawn ─────────────────────────────────────────────── CLI exit / crash
  │                                                            │
  ├─ 后端写临时 mcp_config.json (tempfile)                      ├─ atexit + finally 清理
  ├─ CLI 启动，读 mcp_config，连接 /api/mcp/sse                  ├─ FastAPI shutdown 兜底扫描
  ├─ tools/list → 返回 save_memory                             ├─ SSE 断开
  ├─ Agent 推理时可调用 save_memory                             └─ MCP 端点随进程终止
  ├─ tool_use → CLI → POST SSE → MemoryService → PG
  └─ tool_result ← PG 结果 ← Agent 继续推理
```

### 7.3 工具定义：save_memory

| 参数 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| name | string | ✅ | 简短标识（≤100 字符） |
| description | string | ✅ | 一句话摘要，LLM 检索的关键字段 |
| content | string | ✅ | 完整正文 |
| group_id | string | — | 群组 ID，私聊时自动留空 |

返回：`{id: UUID, source: "chat", status: "saved"}`

只提供 `save_memory`，不提供 `get_memory`。每次 `build_for_agent()` 已自动检索 + 注入，不需要 Agent 主动查。两个记忆入口会导致 Agent 不确定该信任 SP 里的还是自己查到的。

### 7.4 不实现自动记忆

```
自动记忆（Agent 自己判断"值得记"并写入）→ 归 CLI。
AgentHub 不实现 extractMemories 类的后台代理。

原因：
- CLI 已经有成熟的自动记忆机制（extractMemories stopHook）
- 我们做自动记忆会与 CLI 重复写入，产生冲突
- 用户主动记忆 + 手动管理是 AgentHub 的核心差异化价值
```

---

## 八、与 CLI memory 的冲突预防

### 8.1 三层层隔离

```
Layer 1（CLI 管理，我们不碰）:
  CLAUDE.md / MEMORY.md / rules / skills → <system-reminder> 注入
  CLI 的自动记忆写入 MEMORY.md，在下次 spawn 时注入
  我们不在 SP 中告诉 Agent CLI memory 路径

Layer 2（AgentHub 管理）:
  --system-prompt 内容，包括：
  - Agent 身份/人格
  - 行为约束（Delivery Contract）
  - <agenthub-reminder> 选中的记忆  ← 我们的记忆
  - 上下文版本 hash

Layer 3（Harness 管理，我们不碰）:
  hooks / MCP / deferred tools 动态注入
```

### 8.2 SP 中的 Memory 指令

不指向 CLI 的 memory 路径，只声明我们的 Tool：

```
# Memory
使用 save_memory 工具保存用户主动要求的记忆（用户说「记住 xxx」时）。
已有记忆会自动注入，不需要你主动查找。
不要使用 Write 工具操作本地的 memory/ 目录——个人自动记忆由系统自动管理。
```

关键点：
- **不告诉 Agent CLI memory 路径**（不暴露 `~/.claude/projects/...`）
- **不禁止 CLI 自动记忆**（Agent 自己写了 MEMORY.md 我们不管）
- **不冲突**（我们的走 Tool → PG，CLI 的走 Write → MEMORY.md）
- **不给 get_memory**（自动注入已覆盖检索需求，双向入口导致信任混乱）

### 8.3 为什么不冲突

两个系统按**触发者**自然分流：

| | CLI 自动记忆 | AgentHub Memory |
|---|---|---|
| **触发者** | Agent 自主判断 | 用户明确指令 |
| **存储** | MEMORY.md 文件 | PG memories 表 |
| **注入** | `<system-reminder>` | `<agenthub-reminder>` |
| **Agent 操作** | Write 工具写 memory/ | 我们的 Tool 写 PG |

最坏情况：Agent 把同一条信息同时写进两个系统 → 重复记忆，浪费 token 但不产生错误。
CLI 升级 → 不受影响，我们不依赖 CLI memory 的任何行为。

---

## 九、前端

### 9.1 现状

已有完整实现，无需大改：

- `src/frontend/src/api/memories.ts` — CRUD API client
- `src/frontend/src/stores/memoryStore.ts` — Zustand store（load, create, update, delete, togglePin）
- `src/frontend/src/components/memory/MemoryPanel.tsx` — 全功能面板

面板功能：
- Pin/Unpin 切换
- 编辑 / 删除（带确认）
- 手动添加记忆表单
- 衰减分数展示（基于时间 + hits + pin 加权）

### 9.2 需要调整的点

后端 PG schema 是权威源，前端类型向它对齐：

| 前端当前 | 后端 PG | 调整 |
|---------|---------|------|
| `ApiMemory.title` | `name VARCHAR(150)` | 改为 `name`，前端同步 |
| 无 `description` | `description VARCHAR(300)` | `ApiMemory` + `CreateMemoryInput` 新增 |
| 无 `source` | `source VARCHAR(20)` | `ApiMemory` + `CreateMemoryInput` 新增 |
| `expires_at` | 无（用时间衰减替代） | 删除，前端不再展示 |
| `memory_type` 过滤/标签 | 无此字段 | 删除 type badge、过滤 Tab、衰减类型系数 |
| `decayScore` 纯前端 | `hits` + `updated_at` | 保留前端计算，去掉 type 半衰期系数 |
| 无 `group_id` 筛选 | `group_id` + `scope` | `CreateMemoryInput` 新增 scope 字段 |

---

## 十、与 Claude Code 设计原则的对照

| CC 原则 | AgentHub 应用 |
|---------|-------------|
| **LLM 做选择题** | Haiku 从候选集选 ≤5 条，不用 embedding |
| **索引常驻 + 内容按需** | 候选清单只传 description，命中才加载全文 |
| **时间感知 + 主动验证** | 注入带时间标注，≥2 天警告，≥30 天强警告 |
| **结构化优于自由文本** | name + description + content + metadata 必填 |
| **不该存代码推得出来的东西** | 让 Agent 自己判断「这是代码里有还是需要记忆」（Tool prompt 中说明） |

---

## 十一、需要新增/改动的组件

### 11.1 新增

| 组件 | 职责 | 优先级 |
|------|------|:---:|
| `MemoryService` | CRUD + hits 计数 + 候选集查询（按 scope 过滤） | P0 |
| `MemorySelector` | LLM 检索：候选集 → Haiku 选择 ≤5 条（嵌入 `build_for_agent()` 内部） | P0 |
| `MemoryToolHandler` | MCP 端点：`save_memory` tool 实现（SSE transport，FastAPI 内嵌） | P0 |
| PG migration | `memories` 表创建（含 scope 字段） | P0 |

### 11.2 需改动

| 文件 | 改动 |
|------|------|
| `SystemPromptBuilder` | 在 SP 末尾拼接 `<agenthub-reminder>` 记忆块 |
| `ContextBuilder._build_group()` | 调用 MemorySelector → 注入结果到 SP |
| `claude_code_runtime.py` | 移除 v1 的 `cwd=` 相关改动（不再需要 Agent CWD 文件）|

### 11.3 需删除/废弃

| 组件 | 原因 |
|------|------|
| `AgentFileManager` | v1 文件方案，与 v3 PG 方案矛盾 |
| `GroupContext` 值对象 | 记忆不再走文件，不再需要此对象 |
| SP 中的 CLI memory 路径指令 | 替换为 Tool 路径指令 |

### 11.4 不引入

- ❌ pgvector — LLM 选择器替代
- ❌ embedding pipeline — 不需要
- ❌ extractMemories 后台代理 — 自动记忆归 CLI
- ❌ 新 PG 表外键 — `memories` 一张表够用

---

## 十二、与 v1 的迁移路径

v1（`feature/memory/local-vector`）中需要保留的部分：
- `SystemPromptBuilder` 框架（修改 SP 拼接逻辑，加入记忆块）
- `ContextBuilder` 中的上下文构建逻辑

需要删除/重写的部分：
- `AgentFileManager`：CWD 创建 + CLAUDE.md 渲染 + context/ 详情文件 → 全部删除
- `GroupContext`：值对象 + hash 触发重 spawn 逻辑 → 记忆不通过文件传递，不再需要
- `claude_code_runtime.py` 中的 `cwd=` 传递 → 不再需要

需要新增的部分：
- `MemoryService`：PG CRUD 层
- `MemorySelector`：LLM 检索
- `MemoryToolHandler`：Tool API
- PG migration：`memories` 表

---

> **下一步**：确认本文档后，在 worktree 中实施。前端改动最小（已有完整 Panel），后端主要集中在 MemoryService + MemorySelector + SP 注入。
