# Phase B2 增强设计：LLM 兜底提取 + tsvector 全文检索 + 跨 Agent 记忆共享

> 日期：2026-06-01 | 状态：**设计草案**
> 前置：B1 已提交（`b8dc433`，`feature/domain2/memory-system-phase-a`）
> 基于 B1 实际代码：`memory_service.py`、`memory_repository.py`、`context_builder.py`、`chat_service.py`

---

## 〇、B1 现状快照

B1 已实现：

| 模块 | 现状 |
|------|------|
| 写入 | Agent 回复 `<!-- MEMORY:type --> content` → `ChatService` 正则解析 → `MemoryService.save_from_markers()` |
| 检索 | `ORDER BY updated_at DESC LIMIT 5`（纯时间排序，`query` 参数未使用） |
| 注入 | `ContextBuilder._maybe_inject_memories()` → `l4_rag` 填充 |
| 去重 | 写入侧精确匹配（`find_by_content`）+ 读取侧 `seen` set |
| 容错 | `asyncio.wait_for(5s)` + catch-all → `return None` |

---

## 一、回复级 LLM 兜底提取 vs 被动提取（EverMem 模式）

用户问：这两个有什么区别？

### 1.1 核心对比

```
回复级 LLM 兜底提取（B1.5）          被动提取（Phase C，EverMem 模式）
──────────────────────────          ────────────────────────────
触发时机：每条 Agent 回复后            触发时机：整个会话结束后
输入粒度：单条回复（~200-500 tokens）  输入粒度：完整 transcript（数千 tokens）
LLM 调用：1 次/触发                   LLM 调用：6-7 次/会话段
提取类型：4 种（同 B1 标记）            提取类型：5+ 种（Episode/Foresight/AtomicFact/Profile/AgentCase）
成本：~¥0.0006/次                     成本：~¥0.05-0.1/会话
基础设施：复用已有 Selector 的廉价 LLM  基础设施：需要独立记忆 LLM 管道
复杂度：~80 行                        复杂度：~500+ 行
目标：补漏 B1 Marker 遗漏              目标：全量自动记忆管理
```

### 1.2 本质区别

**回复级兜底**是 B1 的安全网：

```
Agent 回复 → 有 <!-- MEMORY: --> 标记？
              ├─ 有 → 同步解析存入（B1 已实现）
              └─ 没有 → 门控检查 → 通过 → 异步调 LLM 提取 → 存入
                                   └─ 不通过 → 跳过
```

它只处理 **Agent 忘了标记的情况**，输入是单条回复，提取的也是同样 4 种类型。是 Marker 路径的**补充**。

**被动提取**是完全独立的记忆管道：

```
会话结束 → 读完整 transcript → LLM 边界检测（分段）
    → 每段并行提取 5 种类型：
       ├── EpisodeMemory（叙事摘要）
       ├── Foresight（未来计划）
       ├── AtomicFact（不可分割事实）
       ├── ProfileMemory（用户画像 CRUD）
       └── AgentCase（问题解决方法）
    → 聚类 → Skill 演化 → ...
```

它不依赖 Agent 的任何行为，能捕获用户没要求记住但有价值的隐含信息（如"用户习惯在晚上提交代码"、"讨论过但未明确记录的架构决策"）。代价是每段对话额外 6-7 次 LLM 调用。

### 1.3 我的建议：先做回复级兜底，不做被动提取

| 理由 | 说明 |
|------|------|
| ROI | 80 行 + ¥0.06/天 vs 500+ 行 + ¥3-5/天 |
| 复杂度 | 回复级兜底不需要 transcript 读取、边界检测、多类型提取器、聚类管道 |
| 风险 | 被动提取质量高度依赖 LLM 提取能力，调优成本高 |
| 验证成本 | 回复级兜底 1 周可验证效果；被动提取需要积累足够数据才能评估 |
| 依赖 | 被动提取需要先有 tsvector/向量检索才能看出效果差异 |

**触发被动提取的条件**：
- 回复级兜底开启后，观察到 > 40% 的有价值信息仍未被捕获
- 需要跨轮对话的上下文理解（单条回复无法提取的信息）
- 需要 EpisodeMemory（叙事摘要）或 AgentCase（问题解决方法）

### 1.4 回复级 LLM 兜底提取：详细设计

#### 在 B1 代码上的改动点

```
chat_service.py:_stream_one_agent()
    │
    ├─ 现有 B1 代码（不变）：
    │   cleaned_content, mem_entries = MemoryService.parse_markers(full)
    │   if mem_entries: await self._memory_svc.save_from_markers(...)
    │   assistant_msg.content = cleaned_content
    │   await self._messages.save(assistant_msg)
    │   await self._l1.append(...)
    │   yield DONE  ← 用户看到回复
    │
    └─ 新增（异步，不阻塞）：
        if not mem_entries and self._should_extract(cleaned_content):
            asyncio.create_task(
                self._extract_memories_async(cleaned_content, target.id, group_id)
            )
```

#### 门控逻辑

```python
# chat_service.py 新增
_turns_since_last_extract: dict[UUID, int] = {}  # agent_id → turns

def _should_extract(self, agent_reply: str) -> bool:
    """判断是否需要 LLM 兜底提取。"""
    if _MEMORY_MARKER_RE.search(agent_reply):
        return False          # 已有标记 → 跳过
    if len(agent_reply) < 100:
        return False          # 回复太短，不太可能有值得记的
    # 频率控制：每 3 轮最多触发一次
    # （具体实现用 agent_id 级别的计数器）
    return True
```

#### 提取函数

```python
# memory_service.py 新增
MEMORY_EXTRACTION_PROMPT = """\
从以下 Agent 回复中提取值得长期记住的信息。
只提取以下 4 类：
- facts: 项目事实、架构决策、技术约定
- preferences: 用户偏好、工作习惯
- procedures: 可复用流程、操作步骤
- context: 任务状态、会话上下文

不要提取：临时状态、闲聊、一次性细节、已在回复中用 <!-- MEMORY: --> 标记过的内容。
确实没有值得记的 → 输出 []

输出 JSON 数组:
[{"type": "facts", "content": "..."}, ...]

Agent 回复：
{text}
"""

async def extract_from_reply(self, text: str) -> list[dict]:
    """LLM 提取记忆条目。返回空列表表示无值得记的。"""
    # 调用 Selector 的廉价 LLM（DeepSeek Flash）
    prompt = MEMORY_EXTRACTION_PROMPT.format(text=text[:2000])
    response = await self._llm.complete(prompt)
    return self._parse_extraction_response(response)
```

#### 成本

| 维度 | 数值 |
|------|------|
| 触发率 | ~30-40%（门控过滤后） |
| 模型 | DeepSeek V4 Flash |
| 单次 input | ~500 tokens |
| 单次 output | ~100 tokens |
| 日均（300 轮） | ~100 次 ≈ ¥0.06 |

#### 新增文件/改动

| 文件 | 改动 | 行数 |
|------|------|------|
| `memory_service.py` | 新增 `extract_from_reply()` + prompt 模板 | ~50 |
| `chat_service.py` | 新增 `_should_extract()` + `_extract_memories_async()` | ~25 |
| `core/config.py` | 新增 `memory_extraction_enabled: bool = False` 开关 | ~3 |
| **合计** | | **~78** |

---

## 二、tsvector 全文检索

### 2.1 问题

B1 的 `search()` 完全不看 `query` 参数：

```python
# infrastructure/repositories/memory_repository.py:68-79（当前代码）
async def search(self, agent_id: UUID, query: str, top_k: int = 5) -> list[Memory]:
    # B1: 时间排序（不接检索引擎），query 仅用于日志
    stmt = (
        select(MemoryModel)
        .where(MemoryModel.agent_id == agent_id)
        .order_by(MemoryModel.updated_at.desc())
        .limit(top_k)
    )
```

用户问"JWT 怎么配"，返回的是最新 5 条记忆，可能全部无关。

### 2.2 方案：tsvector 列 + ts_rank 排序

#### 2.2.1 Migration（0006）

```sql
-- 新增 tsvector 列 + GIN 索引
ALTER TABLE memories ADD COLUMN search_vector tsvector;

-- 中英文混合：先用 simple 配置（逐字拆分），后续可换 zhparser
UPDATE memories SET search_vector =
    setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('simple', coalesce(content, '')), 'B');

CREATE INDEX idx_memories_search_vector ON memories USING GIN (search_vector);

-- 自动更新触发器
CREATE OR REPLACE FUNCTION memories_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.content, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_memories_search_vector
    BEFORE INSERT OR UPDATE OF title, content ON memories
    FOR EACH ROW EXECUTE FUNCTION memories_search_vector_update();
```

**权重策略**：title 是 'A' 权重（高），content 是 'B' 权重（标准）。标题匹配优先。

**中文分词**：`simple` 配置对中文做逐字拆分（"JWT过期" → "j" "w" "t" "过" "期"），关键词匹配可用但不理想。如需精准中文分词，后续安装 `zhparser` 或 `pg_jieba` 扩展。但对 B2 来说够用——记忆内容以技术术语为主，英文关键词和中文单字匹配覆盖率已经不错。

#### 2.2.2 Repository 改动

```python
# infrastructure/repositories/memory_repository.py — 修改 search()

from sqlalchemy import func, text

async def search(
    self, agent_id: UUID, query: str, top_k: int = 5
) -> list[Memory]:
    """B2: tsvector 全文检索 + 时间衰减混合排序。"""
    if not query or not query.strip():
        # 无查询词 → 回退到时间排序（B1 行为）
        return await self.get_recent(agent_id, limit=top_k)

    tsquery = func.plainto_tsquery("simple", query)

    # 混合分数：ts_rank（相关性）+ 时间衰减加权
    # ts_rank 范围约 0-1，时间衰减用 1/(1 + age_days/30) 使 30 天前的记忆权重衰减到 0.5
    rank_expr = func.ts_rank(MemoryModel.search_vector, tsquery)
    age_days = func.extract("epoch", func.now() - MemoryModel.updated_at) / 86400.0
    time_decay = 1.0 / (1.0 + age_days / 30.0)
    # 综合分数：70% 相关性 + 30% 时间新鲜度
    combined_score = 0.7 * rank_expr + 0.3 * time_decay

    stmt = (
        select(MemoryModel)
        .where(
            MemoryModel.agent_id == agent_id,
            # 只返回有匹配的记录（ts_rank > 0）
            MemoryModel.search_vector.op("@@")(tsquery),
        )
        .order_by(combined_score.desc())
        .limit(top_k)
    )
    result = await self._s.execute(stmt)
    rows = [_to_domain(m) for m in result.scalars().all()]

    # 全文检索无结果 → 回退到时间排序（保底）
    if not rows:
        return await self.get_recent(agent_id, limit=top_k)
    return rows
```

#### 2.2.3 ORM Model 改动

```python
# infrastructure/db/models.py — MemoryModel 新增列
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import TSVECTOR

class MemoryModel(Base):
    # ... 现有字段 ...
    search_vector = mapped_column(
        TSVECTOR, nullable=True  # 由 DB 触发器自动填充
    )
```

#### 2.2.4 改动汇总

| 文件 | 改动 | 行数 |
|------|------|------|
| `alembic/versions/0006_add_tsvector.py` | 新 migration | ~40 |
| `infrastructure/db/models.py` | 新增 `search_vector` 列 | ~3 |
| `infrastructure/repositories/memory_repository.py` | 重写 `search()` | ~30 |
| **合计** | | **~73** |

#### 2.2.5 检索效果预期

| 场景 | B1（时间排序） | B2（tsvector） |
|------|--------------|---------------|
| "JWT 怎么配" → 记忆有 "JWT 过期设为 7 天" | ❌ 取决于是否是最新 5 条 | ✅ 关键词 "JWT" 命中 |
| "继续" → 2 字 | 跳过（len < 10） | 跳过（同 B1，`_maybe_inject_memories` 门控） |
| "部署流程" → 记忆有 "新增 Agent：建 Adapter → 注册" | ❌ 语义不匹配 | ⚠️ "部署" 不命中"Agent"，需向量检索 |
| 无关查询 → 无匹配记忆 | 返回最新 5 条（噪声） | 返回空 → 回退最新 5 条（同上，但可配置不回退） |

**tsvector 的局限**：只做关键词匹配，不做语义理解。"认证怎么配" 无法命中 "JWT 过期设为 7 天"（没有共同关键词）。这需要 Phase C 的向量检索（embedding）。

---

## 三、跨 Agent 记忆共享

### 3.1 需求场景

群聊中 3 个 Agent 协作开发：

```
Agent-前端 记住了 "API 用 kebab-case"
Agent-后端 记住了 "JWT 过期 7 天"
Agent-测试 记住了 "CI 必须跑 e2e"

现在 Agent-前端 收到任务 "调用登录接口"，它需要：
  ├── 自己的记忆："API 用 kebab-case" ✅ B1 已有
  └── Agent-后端 的记忆："JWT 过期 7 天" ❌ B1 看不到
```

### 3.2 共享模型设计

#### 3.2.1 核心概念：记忆可见性层级

```
可见性层级：

L0  Agent 私有记忆（B1 已有）
    └── agent_id = X, visibility = 'private'
    └── 只有 Agent X 能看到

L1  群组共享记忆（本次设计）
    └── group_id = G, visibility = 'group'
    └── 群 G 内所有 Agent 都能看到

L2  全局共享记忆（Phase D+）
    └── visibility = 'global'
    └── 所有 Agent 都能看到
```

#### 3.2.2 数据模型变更

B1 的 `memories` 表已预留 `group_id` 列。新增 `visibility` 字段：

```sql
-- Migration 0007
ALTER TABLE memories
    ADD COLUMN visibility VARCHAR(10) NOT NULL DEFAULT 'private';
    -- 'private' | 'group' | 'global'

-- 群组记忆检索索引
CREATE INDEX idx_memories_group_visibility
    ON memories(group_id, visibility, updated_at DESC)
    WHERE visibility = 'group';

-- 更新 search_vector 触发器（如果已实现 tsvector）—— 不变
```

#### 3.2.3 Memory 实体扩展

```python
# domain/entities/memory.py
from typing import Literal

MemoryVisibility = Literal["private", "group", "global"]

@dataclass
class Memory:
    # ... 现有字段 ...
    visibility: MemoryVisibility = "private"
```

#### 3.2.4 写入路径：谁创建群组共享记忆？

**两种来源**：

**来源 1：Agent 主动标记**

扩展 `<!-- MEMORY: -->` 语法，支持 `@group` 后缀：

```
<!-- MEMORY:facts @group --> API 统一用 kebab-case
```

解析后 `visibility = "group"`，`group_id` 从当前群聊上下文获取。

```python
# memory_service.py — parse_markers() 扩展
# 新正则：支持可选 @group/@global 修饰符
_MEMORY_MARKER_RE = re.compile(
    r"^<!--\s*MEMORY:(\w+)\s*(?:@(\w+))?\s*-->\s*(.+)", re.MULTILINE
)
# group(1) = type, group(2) = visibility (None='private'), group(3) = content
```

**来源 2：私有记忆晋升**

Agent 判断某条私有记忆对群内其他人有价值时，可以将其共享：

```
<!-- MEMORY:facts @group --> JWT 过期设为 7 天（已与前端同步）
```

或者后续通过 REST API `PATCH /api/v1/memories/{id}` 修改 visibility。

#### 3.2.5 检索路径：群组内合并检索

```python
# infrastructure/repositories/memory_repository.py — 新增方法

async def search_with_group(
    self,
    agent_id: UUID,
    group_id: UUID | None,
    query: str,
    top_k: int = 5,
) -> list[Memory]:
    """检索 Agent 私有记忆 + 群组共享记忆（合并 + 去重 + 排序）。

    优先级：私有 > 群组（相同 content 只保留私有）。
    """
    conditions = [
        # 条件 1: Agent 自己的私有记忆
        sa.and_(
            MemoryModel.agent_id == agent_id,
            MemoryModel.visibility == "private",
        ),
    ]
    if group_id is not None:
        conditions.append(
            # 条件 2: 当前群的共享记忆（包括其他 Agent 贡献的）
            sa.and_(
                MemoryModel.group_id == group_id,
                MemoryModel.visibility == "group",
            ),
        )

    if query and query.strip() and hasattr(MemoryModel, "search_vector"):
        # B2+: tsvector 检索
        tsquery = func.plainto_tsquery("simple", query)
        rank_expr = func.ts_rank(MemoryModel.search_vector, tsquery)
        stmt = (
            select(MemoryModel)
            .where(
                sa.or_(*conditions),
                MemoryModel.search_vector.op("@@")(tsquery),
            )
            .order_by(rank_expr.desc())
            .limit(top_k * 2)  # 多取一些，去重后可能减少
        )
    else:
        # B1 回退: 时间排序
        stmt = (
            select(MemoryModel)
            .where(sa.or_(*conditions))
            .order_by(MemoryModel.updated_at.desc())
            .limit(top_k * 2)
        )

    result = await self._s.execute(stmt)
    all_memories = [_to_domain(m) for m in result.scalars().all()]

    # 去重：相同 content 只保留一条（优先私有）
    seen: dict[str, Memory] = {}
    for mem in all_memories:
        key = mem.content
        if key not in seen:
            seen[key] = mem
        elif mem.visibility == "private" and seen[key].visibility != "private":
            seen[key] = mem  # 私有覆盖群组

    return list(seen.values())[:top_k]
```

#### 3.2.6 注入格式化：区分来源

```python
# memory_service.py — format_injection() 扩展

@staticmethod
def format_injection(memories: list[Memory]) -> str | None:
    if not memories:
        return None

    lines = ["<agent-memories>"]
    seen: set[str] = set()
    count = 0
    for m in memories:
        if count >= 5:
            break
        if m.content in seen:
            continue
        seen.add(m.content)
        type_label = {
            "facts": "事实", "preferences": "偏好",
            "procedures": "流程", "context": "上下文",
        }.get(m.memory_type, m.memory_type)

        # 群组共享记忆标注来源
        source = ""
        if m.visibility == "group":
            source = " (群组共享)"

        lines.append(f"[{type_label}{source}] {m.content}")
        count += 1
    lines.append("</agent-memories>")
    return "\n".join(lines) if count > 0 else None
```

#### 3.2.7 ContextBuilder 改动

```python
# context_builder.py — _maybe_inject_memories() 修改

async def _maybe_inject_memories(
    self, target_agent: Agent, trigger: Message,
    *, is_first_turn: bool = False, group_id: UUID | None = None,
) -> str | None:
    # ... 门控检查（不变）...
    if group_id is not None:
        # 群聊：合并检索（私有 + 群组共享）
        memories = await asyncio.wait_for(
            self._memory_svc.search_with_group(
                agent_id=target_agent.id,
                group_id=group_id,
                query=trigger.content,
                top_k=5,
            ),
            timeout=5.0,
        )
    else:
        # 私聊：只检索私有（B1 行为）
        memories = await asyncio.wait_for(
            self._memory_svc.search(
                agent_id=target_agent.id,
                query=trigger.content,
                top_k=5,
            ),
            timeout=5.0,
        )
    # ... 格式化注入（不变）...
```

#### 3.2.8 SP 指令扩展

群聊场景下，SP 中增加群组共享记忆的说明：

```
## 群组记忆
群内 Agent 可以共享记忆。使用 @group 后缀标记需要共享的信息：
  <!-- MEMORY:facts @group --> 内容
不加 @group 的记忆仅你自己可见。
只共享对群内其他 Agent 有价值的信息（如 API 约定、架构决策），不要共享个人偏好。
```

### 3.3 安全与隔离

| 约束 | 说明 |
|------|------|
| 不跨群泄露 | `group_id` 是 WHERE 条件的一部分，不同群的记忆互不可见 |
| 不降级 | 群组记忆共享失败 → 回退到只查私有记忆，不阻塞 |
| 不覆盖 | 群组共享记忆不会覆盖 Agent 私有记忆（去重时私有优先） |
| 无删除权限 | B2 阶段只有记忆的创建者能删除自己的记忆（含共享的） |

### 3.4 改动汇总

| 文件 | 改动 | 行数 |
|------|------|------|
| `alembic/versions/0007_add_visibility.py` | 新 migration | ~20 |
| `domain/entities/memory.py` | 新增 `visibility` 字段 | ~5 |
| `memory_service.py` | `parse_markers()` 支持 `@group`；`format_injection()` 标注来源 | ~20 |
| `infrastructure/repositories/memory_repository.py` | 新增 `search_with_group()` | ~40 |
| `context_builder.py` | `_maybe_inject_memories()` 传 `group_id` | ~10 |
| `system_prompt_builder.py` | 群聊 SP 增加群组共享记忆说明 | ~10 |
| **合计** | | **~105** |

---

## 四、实施顺序与依赖

```
          B1（已完成）
              │
    ┌─────────┼─────────┐
    │         │         │
    ▼         ▼         ▼
  B1.5       B2a       B2b
  LLM兜底   tsvector   跨Agent共享
  (~78行)   (~73行)    (~105行)
  无依赖    无依赖     依赖 B2a（共享检索用 tsvector）
```

**建议顺序**：

1. **B2a tsvector**（先让检索准起来，不然共享的记忆也检索不到）
2. **B2b 跨 Agent 共享**（依赖 tsvector 做群组合并检索）
3. **B1.5 LLM 兜底**（先观察 Marker 命中率，需要时再开）

---

## 五、开放问题

| # | 问题 | 建议 |
|---|------|------|
| 1 | tsvector 中文分词用 `simple`（逐字）还是装 `zhparser`？ | B2 先用 `simple`，够用再说。AgentHub 记忆内容技术术语多，英文关键词命中率高 |
| 2 | 群组共享记忆的容量？ | 每群 ≤ 100 条（所有 Agent 贡献总和），超出淘汰 hits 最低的 |
| 3 | Agent 能否编辑/撤回已共享的记忆？ | B2 只支持删除（创建者自删），编辑留 Phase C |
| 4 | 全局共享记忆（L2）何时做？ | 当存在跨群共用的知识（如公司级规范）时再考虑，目前不需要 |
| 5 | tsvector + visibility 的联合索引？ | 群组检索量 < 1K，不需要；超 1K 后加 `idx_memories_group_search(group_id, visibility) INCLUDE (search_vector)` |

---

*文档结束。待确认后进入实施。*
