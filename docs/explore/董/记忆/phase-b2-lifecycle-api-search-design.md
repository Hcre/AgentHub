# Phase B2 详细设计：记忆老化淘汰 + REST API/前端 + 语义检索

> 日期：2026-06-01 | 状态：**详细设计**
> 前置：B1 已提交（`b8dc433`），`phase-b2-enhancement-design.md`（增强方向草案）
> 基于代码：`AgentHub-memory` worktree 实际文件

---

## 一、记忆老化与淘汰：衰减分数模型

### 1.1 问题

B1 是 Append-Only，没有任何清理机制。预期 3 个月后：

```
Agent "后端工程师" 的记忆池：
  facts    × 45  ← 其中 12 条过时（"重构进度 50%" 早已完成）
  preferences × 8
  procedures × 15 ← 其中 5 条重复（同一流程换了 3 种说法）
  context  × 80  ← 绝大多数是过期的会话上下文
  ─────────────
  总计 148 条，有效 < 60 条
```

检索返回 5 条，其中 2-3 条是垃圾 → 注入质量下降 → 用户体感"Agent 记忆力差"。

### 1.2 淘汰策略选型：固定上限 vs 衰减分数

两种方案对比：

| | 固定 80 条 + hits LRU | 衰减分数 |
|---|---|---|
| 高活跃 Agent（100 条全有价值） | 强制砍 20 条 | 全保留（分数都 > 0.1） |
| 低活跃 Agent（20 条全过期） | 不淘汰（没到 80） | 全淘汰（分数都 < 0.1） |
| 用户钉选的记忆 | 可能被淘汰 | 永不淘汰（pin_shield = ∞） |
| 高频命中的老记忆 | 可能被新记忆挤掉 | hits 高，抗衰减，保留 |
| 新增基础设施 | 0 | +2 列（pinned, source） |

**决策：衰减分数。** 不设硬上限，每条记忆有一个动态重要性分数。低于阈值的自动淘汰，高于阈值的无论总量多少都保留。

### 1.3 衰减分数模型

```
score = base_weight × recency_decay × usage_boost × pin_shield
```

| 因子 | 计算 | 说明 |
|------|------|------|
| `base_weight` | facts: 1.0, preferences: 0.9, procedures: 0.7, context: 0.3 | 类型固有重要性 |
| `recency_decay` | `1 / (1 + age_days / half_life)` | 越老越衰减；half_life 按类型不同 |
| `usage_boost` | `1 + log2(1 + hits)` | 被用过的记忆抗衰减 |
| `pin_shield` | `∞` if pinned else `1.0` | 用户钉选永不淘汰 |

**half_life 按类型**：

| 类型 | half_life | 效果 |
|------|----------|------|
| `facts` | 365 天 | 一年后 score 降到 50% |
| `preferences` | 365 天 | 同上 |
| `procedures` | 90 天 | 三个月后降到 50% |
| `context` | 7 天 | 一周后降到 50% |

**效果推演**：

```
"JWT 过期 7 天"（facts, 60 天前创建, hits=12, 未钉选）
  = 1.0 × 1/(1+60/365) × (1+log2(13)) × 1.0
  = 1.0 × 0.86 × 4.7 × 1.0
  = 4.04  ← 高分，保留

"API 重构到 L3"（context, 30 天前创建, hits=0, 未钉选）
  = 0.3 × 1/(1+30/7) × (1+0) × 1.0
  = 0.3 × 0.19 × 1.0
  = 0.057  ← 低于 0.1，淘汰

"用户偏好简洁回复"（preferences, 90 天前创建, hits=25, 已钉选）
  = 0.9 × ... × ... × ∞
  = ∞  ← 永不淘汰
```

**淘汰阈值**：score < 0.1。低于这个分的记忆几乎不可能被检索到，留着只是噪声。

### 1.4 实现

#### 1.4.1 Memory 实体新增字段

```python
# domain/entities/memory.py — 追加

@dataclass
class Memory:
    # ... 现有字段 ...
    pinned: bool = False       # 用户钉选，钉选后 pin_shield = ∞
    source: str = "marker"     # "marker" | "llm" | "manual"
```

#### 1.4.2 Migration

```python
# alembic/versions/0006_add_memory_lifecycle.py

def upgrade() -> None:
    op.add_column("memories", sa.Column("pinned", sa.Boolean(), default=False, server_default="false"))
    op.add_column("memories", sa.Column("source", sa.String(16), default="marker", server_default="marker"))
    op.create_index("idx_memories_pinned", "memories", ["agent_id", "pinned"])
```

#### 1.4.3 分数计算

```python
# memory_service.py — 新增

import math
from datetime import UTC, datetime

_HALF_LIFE_DAYS: dict[str, float] = {
    "facts": 365.0,
    "preferences": 365.0,
    "procedures": 90.0,
    "context": 7.0,
}

def compute_score(memory: Memory, now: datetime | None = None) -> float:
    """计算记忆的衰减分数。纯函数，无副作用。"""
    if memory.pinned:
        return float("inf")

    now = now or datetime.now(UTC)
    age_days = (now - memory.created_at).total_seconds() / 86400.0
    half_life = _HALF_LIFE_DAYS.get(memory.memory_type, 90.0)

    base = {"facts": 1.0, "preferences": 0.9, "procedures": 0.7, "context": 0.3}
    base_weight = base.get(memory.memory_type, 0.5)

    recency = 1.0 / (1.0 + age_days / half_life)
    usage = 1.0 + math.log2(1 + memory.hits)

    return base_weight * recency * usage

_EVICTION_THRESHOLD = 0.1
```

#### 1.4.4 淘汰逻辑

```python
# memory_service.py — 新增

async def evict_low_score(self, agent_id: UUID) -> int:
    """删除 score < 0.1 的记忆。返回删除数量。"""
    all_memories = await self._repo.get_all_by_agent(agent_id)
    now = datetime.now(UTC)
    to_delete = [
        m.id for m in all_memories
        if not m.pinned and compute_score(m, now) < _EVICTION_THRESHOLD
    ]
    for mid in to_delete:
        await self._repo.delete(mid)
    return len(to_delete)
```

触发时机：每次 `save_from_markers()` 后异步 fire-and-forget：

```python
# memory_service.py — save_from_markers() 末尾追加

asyncio.create_task(self._evict_if_needed(agent_id))
```

不是每次写入都全量扫描——加一个简单门控（距上次淘汰 < 1 小时跳过）：

```python
_last_eviction: dict[str, float] = {}  # agent_id -> timestamp

async def _evict_if_needed(self, agent_id: UUID) -> None:
    now = datetime.now(UTC).timestamp()
    key = str(agent_id)
    if key in _last_eviction and (now - _last_eviction[key]) < 3600:
        return
    _last_eviction[key] = now
    count = await self.evict_low_score(agent_id)
    if count:
        logger.info("Evicted %d low-score memories for agent=%s", count, agent_id)
```

#### 1.4.5 设计决策：为什么不再需要 TTL

`recency_decay` 本身就是 TTL 的连续化版本：

| TTL 方式 | 衰减分数方式 |
|---------|------------|
| context 7 天后硬删除 | context half_life=7d → 7 天后 score 降至 50%，14 天后 33%，持续自然衰减 |
| facts 永不过期 | facts half_life=365d → 一年后 50%，但 hits 高的抗衰减 |
| 需要后台 cron 定时扫 | 写入时 fire-and-forget 触发，无独立 cron |

不需要两套机制。衰减分数同时解决了「什么时候淘汰」（score < 0.1）和「淘汰谁」（低分优先），TTL 完全被覆盖。

#### 1.4.6 改动汇总

| 文件 | 改动 | 行数 |
|------|------|------|
| `domain/entities/memory.py` | 新增 `pinned: bool` + `source: str` | ~2 |
| `alembic/versions/0006_add_memory_lifecycle.py` | 新 migration（pinned + source 列） | ~20 |
| `infrastructure/db/models.py` | MemoryModel 新增两列 | ~4 |
| `memory_service.py` | `compute_score()` + `evict_low_score()` + `_evict_if_needed()` | ~45 |
| `memory_repository.py` | `get_all_by_agent()`（已有 `get_recent(limit=999)` 可复用） | ~0 |
| `core/config.py` | `memory_eviction_threshold: float = 0.1` | ~1 |
| **合计** | | **~72** |

比原 TTL + 固定上限方案（~103 行）少 ~30 行，且少了一个后台 cron。

---

## 二、REST API + 前端

### 2.1 API 设计

遵循项目现有模式（`/api/agents`、`/api/groups`），AP-01 kebab-case。

```
GET    /api/agents/{agent_id}/memories          ← 列出某 Agent 的记忆
GET    /api/agents/{agent_id}/memories/{id}      ← 查看单条
POST   /api/agents/{agent_id}/memories           ← 手动创建
PATCH  /api/agents/{agent_id}/memories/{id}      ← 修改（纠错）
DELETE /api/agents/{agent_id}/memories/{id}      ← 删除
GET    /api/agents/{agent_id}/memories/stats      ← 统计
```

记忆隶属于 Agent，所以嵌套在 `/agents/{agent_id}/` 下。

#### 2.1.1 Schema

```python
# schemas/memory.py — 新增

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from app.domain.entities.memory import MemoryType

class MemoryCreateRequest(BaseModel):
    memory_type: MemoryType
    content: str = Field(min_length=1, max_length=5000)
    group_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)

class MemoryUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    memory_type: MemoryType | None = None
    pinned: bool | None = None       # 用户钉选/取消钉选
    metadata: dict | None = None

class MemoryOut(BaseModel):
    id: UUID
    agent_id: UUID
    group_id: UUID | None
    memory_type: str
    title: str
    content: str
    metadata: dict
    hits: int
    pinned: bool                     # 是否钉选
    source: str                      # "marker" | "llm" | "manual"
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime

class MemoryStatsOut(BaseModel):
    total: int
    by_type: dict[str, int]  # {"facts": 12, "preferences": 5, ...}
    oldest: datetime | None
    newest: datetime | None
```

#### 2.1.2 Router

```python
# api/routers/memories.py — 新增

router = APIRouter(
    prefix="/api/agents/{agent_id}/memories",
    tags=["memories"],
)

@router.get("", response_model=list[MemoryOut])
async def list_memories(
    agent_id: UUID,
    svc: MemorySvcDep,
    memory_type: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[MemoryOut]:
    """列出 Agent 的记忆，支持按类型过滤 + 分页。"""
    if memory_type:
        memories = await svc.get_by_type(agent_id, memory_type)
    else:
        memories = await svc.get_recent(agent_id, limit=limit)
    return [MemoryOut(**m.__dict__) for m in memories]


@router.get("/stats", response_model=MemoryStatsOut)
async def memory_stats(agent_id: UUID, svc: MemorySvcDep) -> MemoryStatsOut:
    """返回 Agent 的记忆统计。"""
    return await svc.get_stats(agent_id)


@router.get("/{memory_id}", response_model=MemoryOut)
async def get_memory(
    agent_id: UUID, memory_id: UUID, svc: MemorySvcDep,
) -> MemoryOut:
    memory = await svc.get_by_id(memory_id)
    if not memory or memory.agent_id != agent_id:
        raise HTTPException(404, "Memory not found")
    return MemoryOut(**memory.__dict__)


@router.post("", response_model=MemoryOut, status_code=201)
async def create_memory(
    agent_id: UUID, body: MemoryCreateRequest, svc: MemorySvcDep,
) -> MemoryOut:
    """手动创建记忆（用户主动添加）。"""
    memory = Memory(
        agent_id=agent_id,
        memory_type=body.memory_type,
        title=body.content[:200],
        content=body.content,
        group_id=body.group_id,
        metadata=body.metadata,
    )
    await svc.save(memory)
    return MemoryOut(**memory.__dict__)


@router.patch("/{memory_id}", response_model=MemoryOut)
async def update_memory(
    agent_id: UUID, memory_id: UUID,
    body: MemoryUpdateRequest, svc: MemorySvcDep,
) -> MemoryOut:
    """修改记忆（用户纠错）。"""
    memory = await svc.get_by_id(memory_id)
    if not memory or memory.agent_id != agent_id:
        raise HTTPException(404, "Memory not found")
    if body.content is not None:
        memory.content = body.content
        memory.title = body.content[:200]
    if body.memory_type is not None:
        memory.memory_type = body.memory_type
    if body.metadata is not None:
        memory.metadata = body.metadata
    if body.pinned is not None:
        memory.pinned = body.pinned
    memory.updated_at = datetime.now(UTC)
    await svc.save(memory)
    return MemoryOut(**memory.__dict__)


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    agent_id: UUID, memory_id: UUID, svc: MemorySvcDep,
) -> Response:
    memory = await svc.get_by_id(memory_id)
    if not memory or memory.agent_id != agent_id:
        raise HTTPException(404, "Memory not found")
    await svc.delete(memory_id)
    return Response(status_code=204)
```

#### 2.1.3 MemoryService 补充方法

```python
# memory_service.py — 新增

async def get_by_id(self, memory_id: UUID) -> Memory | None:
    return await self._repo.get_by_id(memory_id)

async def get_by_type(self, agent_id: UUID, memory_type: str) -> list[Memory]:
    return await self._repo.get_by_type(agent_id, memory_type)

async def delete(self, memory_id: UUID) -> None:
    await self._repo.delete(memory_id)

async def get_stats(self, agent_id: UUID) -> dict:
    """统计 Agent 的记忆分布。"""
    all_memories = await self._repo.get_recent(agent_id, limit=999)
    by_type: dict[str, int] = {}
    for m in all_memories:
        by_type[m.memory_type] = by_type.get(m.memory_type, 0) + 1
    return {
        "total": len(all_memories),
        "by_type": by_type,
        "oldest": min((m.created_at for m in all_memories), default=None),
        "newest": max((m.created_at for m in all_memories), default=None),
    }
```

#### 2.1.4 依赖注入 + 路由注册

```python
# api/deps.py — 新增
# get_memory_svc 已存在（B1），无需重复

# api/routers/__init__.py — 修改
from app.api.routers import agents, groups, inbox, memories, proxy, sessions, skills, tasks
__all__ = [..., "memories"]
```

### 2.2 前端

记忆管理入口放在 Agent 详情面板（RightPanel）中，作为一个新 Tab。

#### 2.2.1 API Client

```typescript
// api/memories.ts — 新增

import { api } from "./client";

export interface ApiMemory {
  id: string;
  agent_id: string;
  group_id: string | null;
  memory_type: "facts" | "preferences" | "procedures" | "context";
  title: string;
  content: string;
  metadata: Record<string, unknown>;
  hits: number;
  pinned: boolean;
  source: string;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemoryStats {
  total: number;
  by_type: Record<string, number>;
  oldest: string | null;
  newest: string | null;
}

export const memoriesApi = {
  list: (agentId: string, type?: string) =>
    api.get<ApiMemory[]>(
      `/api/agents/${agentId}/memories${type ? `?memory_type=${type}` : ""}`
    ),
  stats: (agentId: string) =>
    api.get<MemoryStats>(`/api/agents/${agentId}/memories/stats`),
  create: (agentId: string, input: { memory_type: string; content: string }) =>
    api.post<ApiMemory>(`/api/agents/${agentId}/memories`, input),
  update: (agentId: string, id: string, input: { content?: string; memory_type?: string; pinned?: boolean }) =>
    api.patch<ApiMemory>(`/api/agents/${agentId}/memories/${id}`, input),
  remove: (agentId: string, id: string) =>
    api.del<void>(`/api/agents/${agentId}/memories/${id}`),
};
```

#### 2.2.2 Store

```typescript
// stores/memoryStore.ts — 新增

import { create } from "zustand";
import { memoriesApi, type ApiMemory, type MemoryStats } from "../api/memories";

interface MemoryState {
  memories: ApiMemory[];
  stats: MemoryStats | null;
  loading: boolean;
  filter: string | null;  // memory_type filter

  fetchMemories: (agentId: string) => Promise<void>;
  fetchStats: (agentId: string) => Promise<void>;
  deleteMemory: (agentId: string, id: string) => Promise<void>;
  updateMemory: (agentId: string, id: string, content: string) => Promise<void>;
  togglePin: (agentId: string, id: string, pinned: boolean) => Promise<void>;
  setFilter: (type: string | null) => void;
}

export const useMemoryStore = create<MemoryState>((set, get) => ({
  memories: [],
  stats: null,
  loading: false,
  filter: null,

  fetchMemories: async (agentId) => {
    set({ loading: true });
    const filter = get().filter;
    const memories = await memoriesApi.list(agentId, filter ?? undefined);
    set({ memories, loading: false });
  },

  fetchStats: async (agentId) => {
    const stats = await memoriesApi.stats(agentId);
    set({ stats });
  },

  deleteMemory: async (agentId, id) => {
    await memoriesApi.remove(agentId, id);
    set((s) => ({ memories: s.memories.filter((m) => m.id !== id) }));
  },

  updateMemory: async (agentId, id, content) => {
    const updated = await memoriesApi.update(agentId, id, { content });
    set((s) => ({
      memories: s.memories.map((m) => (m.id === id ? updated : m)),
    }));
  },

  setFilter: (type) => set({ filter: type }),

  togglePin: async (agentId, id, pinned) => {
    const updated = await memoriesApi.update(agentId, id, { pinned });
    set((s) => ({
      memories: s.memories.map((m) => (m.id === id ? updated : m)),
    }));
  },
}));
```

#### 2.2.3 UI 组件

```
components/memories/
├── MemoryPanel.tsx       ← 主面板（Tab 入口）
├── MemoryCard.tsx        ← 单条记忆卡片（展示 + 编辑 + 删除）
├── MemoryStatsBar.tsx    ← 顶部统计（总数 + 类型分布饼图/数字）
└── MemoryFilterBar.tsx   ← 类型过滤 Tab（全部 / 事实 / 偏好 / 流程 / 上下文）
```

交互：
- 每条记忆卡片：hover 显示 📌钉选 / edit / delete 按钮
- 已钉选的卡片顶部显示 📌 图标，绿色边框
- 点 edit → 内联编辑 content → 保存
- 点 delete → 确认对话框 → 删除
- 顶部 stats bar：总 12 条 | 事实 5 | 偏好 3 | 流程 2 | 上下文 2
- 过滤 tab 切换：全部 / 按类型

#### 2.2.4 改动汇总

| 文件 | 层 | 行数 |
|------|---|------|
| `schemas/memory.py` | L4 | ~45 |
| `api/routers/memories.py` | L4 | ~90 |
| `api/routers/__init__.py` | L4 | ~2 |
| `api/deps.py` | L4 | ~0（B1 已注册） |
| `memory_service.py` | L3 | ~25 |
| `memory_repository.py`（Protocol） | L2 | ~3 |
| `frontend/src/api/memories.ts` | FE | ~30 |
| `frontend/src/stores/memoryStore.ts` | FE | ~45 |
| `frontend/src/components/memories/*.tsx` | FE | ~200 |
| **合计** | | **~440** |

---

## 三、语义检索：tsvector + pgvector 双路径

### 3.1 为什么不二选一

| | tsvector | pgvector |
|---|---|---|
| 搜索方式 | BM25 关键词匹配 | 语义向量相似度 |
| 优势 | "JWT" → 精确命中含 "JWT" 的记忆 | "认证" → 语义匹配含 "JWT" 的记忆 |
| 劣势 | "认证" 搜不到 "JWT 过期 7 天" | embedding 质量不好时排序反而不如关键词 |
| 写入成本 | 零（PG 触发器自动维护） | ~¥0.0001/次 embedding API |
| 写入延迟 | 0ms | ~100-300ms（API 调用） |
| 故障面 | 无外部依赖 | embedding API 挂了 → 写入降级（存了但不可语义检索） |
| 新增容器 | 零（PG 扩展） | 零（PG 扩展） |

两者互补：tsvector 做精确关键词命中的安全网，pgvector 做语义扩展。不二选一。

### 3.2 写入路径

```
save_from_markers() → PG INSERT
    │
    ├─ 同步（PG 触发器，零延迟）:
    │   tsvector 列自动填充                  ← 零故障面，永远可用
    │
    └─ 异步 fire-and-forget:
       调用 embedding API → pgvector 列填充  ← 降级安全，失败不影响写入
```

### 3.3 检索评分公式

```
score = ts_rank × 0.3 + cosine_similarity × 0.5 + time_decay × 0.2
```

三个因子各司其职：

| 因子 | 权重 | 作用 |
|------|------|------|
| `ts_rank` | 0.3 | 关键词精确命中 |
| `cosine_similarity` | 0.5 | 语义相似度（主力） |
| `time_decay` | 0.2 | 新鲜度偏好（同衰减分数模型的 recency_decay） |

回退链：

```
有 vector + tsvector → 加权混合评分
有 tsvector 无 vector → ts_rank × 0.7 + time_decay × 0.3
都没有               → ORDER BY updated_at（B1 兜底）
```

### 3.4 Migration

```python
# alembic/versions/0007_add_search_columns.py

def upgrade() -> None:
    # 1. tsvector 列 + GIN 索引 + 触发器
    op.add_column("memories", sa.Column("search_vector", TSVECTOR, nullable=True))
    op.execute("""
        UPDATE memories SET search_vector =
            setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('simple', coalesce(content, '')), 'B')
    """)
    op.create_index("idx_memories_search_vector", "memories", ["search_vector"],
                    postgresql_using="gin")
    op.execute("""
        CREATE OR REPLACE FUNCTION memories_search_vector_update()
        RETURNS trigger AS $$
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
    """)

    # 2. pgvector 扩展 + embedding 列 + IVFFlat 索引
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("memories", sa.Column("embedding", sa.NullType(), nullable=True))
    # 1536 维 = OpenAI text-embedding-3-small
    op.execute("""
        CREATE INDEX idx_memories_embedding
        ON memories USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 50)
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_memories_search_vector ON memories")
    op.execute("DROP FUNCTION IF EXISTS memories_search_vector_update()")
    op.drop_index("idx_memories_search_vector")
    op.drop_index("idx_memories_embedding")
    op.drop_column("memories", "search_vector")
    op.drop_column("memories", "embedding")
```

### 3.5 Repository search() 重写

```python
# infrastructure/repositories/memory_repository.py

async def search(
    self, agent_id: UUID, query: str, top_k: int = 5
) -> list[Memory]:
    """B2: tsvector × 0.3 + pgvector × 0.5 + time_decay × 0.2 混合检索。"""
    if not query or not query.strip():
        return await self.get_recent(agent_id, limit=top_k)

    has_tsvector = True  # PG 触发器保证
    has_vector = await self._agent_has_embeddings(agent_id)

    if not has_tsvector and not has_vector:
        return await self.get_recent(agent_id, limit=top_k)

    # 时间衰减
    age_seconds = sa_func.extract("epoch", sa_func.now() - MemoryModel.updated_at)
    time_decay = 1.0 / (1.0 + age_seconds / (30.0 * 86400.0))

    if has_vector:
        # embedding API 调用（在 MemoryService 层完成，此处接收向量）
        # 调用方先调 embedding API 获取 query_vector，传入此方法
        # 此处展示 SQL 结构
        similarity = MemoryModel.embedding.cosine_distance(query_vector).label("similarity")
        tsquery = sa_func.plainto_tsquery("simple", query)
        rank = sa_func.ts_rank(MemoryModel.search_vector, tsquery)
        score = (0.3 * rank + 0.5 * (1.0 - similarity) + 0.2 * time_decay).label("score")

        stmt = (
            select(MemoryModel, score)
            .where(MemoryModel.agent_id == agent_id)
            .order_by(score.desc())
            .limit(top_k)
        )
    else:
        # 回退：tsvector only
        tsquery = sa_func.plainto_tsquery("simple", query)
        rank = sa_func.ts_rank(MemoryModel.search_vector, tsquery)
        score = (0.7 * rank + 0.3 * time_decay).label("score")

        stmt = (
            select(MemoryModel, score)
            .where(
                MemoryModel.agent_id == agent_id,
                MemoryModel.search_vector.op("@@")(tsquery),
            )
            .order_by(score.desc())
            .limit(top_k)
        )

    result = await self._s.execute(stmt)
    rows = result.all()

    if not rows:
        return await self.get_recent(agent_id, limit=top_k)

    memories = [_to_domain(row[0]) for row in rows]

    # hits +1
    if memories:
        ids = [m.id for m in memories]
        await self._s.execute(
            sa.update(MemoryModel)
            .where(MemoryModel.id.in_(ids))
            .values(hits=MemoryModel.hits + 1)
        )
        await self._s.flush()

    return memories
```

### 3.6 中文分词说明

`simple` 配置对中文逐字拆分：

```
"JWT过期设为7天" → 'j' 'w' 't' '过' '期' '设' '为' '7' '天'
查询 "JWT" → 匹配 ✅（'j' && 'w' && 't'）
查询 "过期" → 匹配 ✅（'过' && '期'）
查询 "认证" → tsvector 不匹配 ❌，但 pgvector 语义匹配 ✅
```

pgvector 补齐了 tsvector 对中文语义的短板。两个配合后，关键词和语义都能覆盖。

**如需更好中文分词**（可选），安装 `zhparser`：
```sql
CREATE EXTENSION zhparser;
CREATE TEXT SEARCH CONFIGURATION chinese (PARSER = zhparser);
```

### 3.7 改动汇总

| 文件 | 改动 | 行数 |
|------|------|------|
| `alembic/versions/0007_add_search_columns.py` | 新 migration（tsvector + pgvector） | ~55 |
| `infrastructure/db/models.py` | `search_vector` + `embedding` 两列 | ~6 |
| `memory_service.py` | embedding API 调用 + `search()` 封装 | ~35 |
| `infrastructure/repositories/memory_repository.py` | 重写 `search()` 混合评分 | ~55 |
| `core/config.py` | `embedding_model: str` + `embedding_api_key: str` | ~3 |
| **合计** | | **~154** |

---

## 四、三块的依赖关系与实施顺序

```
              ┌──────────────────┐
              │  0006             │
              │  pinned + source  │  ← 衰减分数基础设施
              │  migration        │
              └────────┬─────────┘
                       │
              ┌────────┼─────────┐
              │        │         │
              ▼        ▼         ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │ compute_ │ │ 0007     │ │ REST API │
       │ score()  │ │ tsvector │ │ + Schema │
       │ + evict  │ │+pgvector │ │ + Router │
       └──────────┘ └────┬─────┘ └────┬─────┘
                         │            │
                         ▼            ▼
                  ┌──────────┐ ┌──────────┐
                  │ search() │ │ 前端 UI  │
                  │ 重写     │ │ memories │
                  └──────────┘ └──────────┘
```

**建议分 3 个 commit**：

| # | 内容 | 估计行数 |
|---|------|---------|
| 1 | 0006 migration（pinned + source）+ compute_score() + evict | ~70 |
| 2 | 0007 migration（tsvector + pgvector）+ search() 重写 + embedding | ~155 |
| 3 | REST API + Schema + Router + 前端 | ~440 |

---

## 五、向 Phase C 的过渡路径

tsvector + pgvector 已经是 PG 生态内能做到的最强组合。Phase C 的 ES hybrid 在以下场景仍有优势：

| 触发条件 | 为什么 ES 更好 |
|---------|---------------|
| 记忆量 > 1K 条/Agent | pgvector IVFFlat 在百万级以下没问题，但 ES 的分布式分片更适合大规模 |
| 需要 BM25 + 向量原生融合（RRF） | pgvector 的混合评分在应用层手动加权，ES 原生 RRF 更精确 |
| 需要 facet/聚合分析 | ES 的聚合查询是原生能力 |

切换成本不变（Repository 接口不动，只换实现）。B2 的 pgvector 经验会直接指导 Phase C 的 ES 索引设计——两者用的 embedding 模型和向量维度完全一致。

---

*文档结束。待确认后按 §四 顺序实施。*
