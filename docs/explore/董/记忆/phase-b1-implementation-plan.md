# Phase B1 实现计划：后端统一记忆服务

> 日期：2026-06-01 | 状态：待实施（审查修正版 2026-06-01）
> 前置：`memory-system-direction-b-analysis.md`（方向评估与设计决策）
> 预计改动：~40 行删除/修改 + ~415 行新增 + ~80 行测试调整
>
> **审查修正记录**（9 项）：
> 1. ~~`MemoryModel.metadata`~~ → `extra` 别名，避免与 `Base.metadata` 冲突（严重）
> 2. `title` 截断冗余 if/else → 简化（轻微）
> 3. `[MEMORY:type]` 标记格式 → 改用 `<!-- MEMORY:type -->` HTML 注释防误匹配（中等）
> 4. L1 缓存存 `full` → 改存 `cleaned_content`（严重）
> 5. `deps.py` 两处构造 + `ChatService.__init__` 参数遗漏 → 补全（严重）
> 6. `context_builder.py` 缺 `import asyncio` → 补全（轻微）
> 7. `infrastructure/repositories/__init__.py` 导出遗漏 → 补全（轻微）
> 8. GIN 索引 PG-only 注释 → 补全（轻微）
> 9. `search()` 签名 `min_score` 不一致 → 统一去掉（中等）

---

## 一、B1 范围边界

### 要做

- PG `memories` 表 + Domain Entity + Repository + Service
- Agent 回复中 `<!-- MEMORY:type -->` 标记写入路径
- ContextBuilder 每轮按需注入记忆（`MemoryContext.l4_rag`）
- SystemPromptBuilder 重写 memory 指令段（切断 CLI 路径耦合）
- SP 稳定记忆注入（高频 facts/preferences）

### 不做

- 后端被动提取（Phase C）
- 语义/向量检索（B1：`ORDER BY updated_at`；B2：tsvector；C：ES hybrid）
- MCP Server / tool
- 跨 Agent 记忆共享（Phase D）
- MongoDB / Elasticsearch
- metadata sub_type 强制校验（B1 仅 JSONB 存储，不强制 schema）

---

## 二、参考 EverMem 的设计借鉴

| EverMem 机制 | B1 采用 | 具体做法 |
|-------------|---------|---------|
| "永不阻塞"容错原则 | ✅ | `_maybe_inject_memories()` 和 `_extract_memory_markers()` 静默降级 |
| 硬限制 5 条 + MIN_SCORE | ✅ | 注入 ≤5 条/轮，≤400 tokens |
| Append-Only 存储 | ✅ | 不原地更新，检索时 `ORDER BY updated_at DESC` 解析 |
| 通道隔离（不写 CLI 文件） | ✅ | 记忆走 `l4_rag` + SP，不碰 `~/.claude/projects/` |
| LLM 提取（6 calls/segment） | ❌ | B1 用 `<!-- MEMORY: -->` 标记，零额外 LLM 成本 |
| Case → Skill 演化 | ❌ | Phase D+ |

---

## 三、文件级改动清单

### 3.1 新增文件（8 个）

| # | 文件 | 所在层 | 行数 | 职责 |
|---|------|-------|------|------|
| 1 | `domain/entities/memory.py` | L2 | ~40 | Memory 实体 dataclass |
| 2 | `domain/repositories/memory_repository.py` | L2 | ~25 | MemoryRepository 协议（ABC） |
| 3 | `infrastructure/repositories/memory_repository.py` | L1 | ~90 | PG 实现：save/search/get_by_type/delete |
| 4 | `application/services/memory_service.py` | L3 | ~120 | 业务编排：CRUD + 检索 + 标记解析 |
| 5 | `alembic/versions/0005_create_memories.py` | L1 | ~35 | memories 表 migration |
| 6 | `tests/test_memory_entity.py` | — | ~30 | 实体校验测试 |
| 7 | `tests/test_memory_service.py` | — | ~80 | MemoryService 测试 |
| 8 | `tests/test_memory_repository.py` | — | ~60 | PG Repository 集成测试 |

### 3.2 修改文件（7 个）

| # | 文件 | 行数 | 改动内容 |
|---|------|------|---------|
| 1 | `system_prompt_builder.py` | ~+30 / -9 | 重写 `_memory_instructions()`；删除 `_cwd_to_cli_memory_path()` |
| 2 | `agent_file_manager.py` | -2 | 删除 `cleanup_agent_cwd()` 中的 `_cwd_to_cli_memory_path()` 调用（line 126） |
| 3 | `context_builder.py` | ~+50 | 新增 `_maybe_inject_memories()` 方法 |
| 4 | `chat_service.py` | ~+25 | `_stream_one_agent` 中添加 `<!-- MEMORY: -->` 标记解析 |
| 5 | `api/deps.py` | ~+20 | 注册 `MemoryService` 依赖；更新 `get_chat_service()` 和 `build_chat_service_for_ws()` 两处构造 |
| 6 | `domain/entities/__init__.py` | +1 | 导出 `Memory` |
| 7 | `domain/repositories/__init__.py` | +2 | 导出 `MemoryRepository` |
| 8 | `infrastructure/repositories/__init__.py` | +1 | 导出 `PostgresMemoryRepository` |

### 3.3 修改测试（4 个）

| # | 文件 | 行数 | 改动内容 |
|---|------|------|---------|
| 1 | `test_system_prompt_builder.py` | ~-10 / +20 | 删除 `test_memory_path_encoding`；更新 memory 相关断言 |
| 2 | `test_agent_file_manager.py` | ~-3 | 清理 memory path 引用 |
| 3 | `test_context_builder.py` | ~+25 | 新增 `l4_rag` 填充的测试用例 |
| 4 | `test_chat_service.py` | ~+15 | 新增 `<!-- MEMORY: -->` 标记解析测试 |

---

## 四、详细实现步骤

### Step 1: Memory 实体（`domain/entities/memory.py`）

遵循现有 `Group`、`Agent`实体模式：`@dataclass` + `__post_init__` 校验。

```python
"""Memory 实体（docs/explore/董/记忆/memory-system-direction-b-analysis.md §6）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from app.core.exceptions import DomainError

MemoryType = Literal["facts", "preferences", "procedures", "context"]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Memory:
    agent_id: UUID
    memory_type: MemoryType
    title: str
    content: str
    group_id: UUID | None = None
    metadata: dict = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)
    hits: int = 0
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.title or not self.title.strip():
            raise DomainError("Memory title 不能为空")
        if not self.content or not self.content.strip():
            raise DomainError("Memory content 不能为空")
        if self.memory_type not in ("facts", "preferences", "procedures", "context"):
            raise DomainError(f"无效的 memory_type: {self.memory_type}")
```

### Step 2: MemoryRepository 协议（`domain/repositories/memory_repository.py`）

遵循现有 `GroupRepository`、`AgentRepository` 模式：`ABC` 基类。

```python
"""MemoryRepository 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.memory import Memory


class MemoryRepository(ABC):
    @abstractmethod
    async def save(self, memory: Memory) -> None: ...

    @abstractmethod
    async def get_by_id(self, memory_id: UUID) -> Memory | None: ...

    @abstractmethod
    async def search(
        self, agent_id: UUID, query: str, top_k: int = 5
    ) -> list[Memory]: ...

    @abstractmethod
    async def get_by_type(
        self, agent_id: UUID, memory_type: str
    ) -> list[Memory]: ...

    @abstractmethod
    async def get_recent(
        self, agent_id: UUID, limit: int = 5
    ) -> list[Memory]: ...

    @abstractmethod
    async def find_by_content(
        self, agent_id: UUID, memory_type: str, content: str
    ) -> Memory | None:
        """精确匹配去重：同一 Agent 下 type+content 完全相同的记录。
        
        B1 第 1 层幂等拦截使用，覆盖 80% 重复场景。
        """
        ...

    @abstractmethod
    async def delete(self, memory_id: UUID) -> None: ...
```

注意：B1 的 `search()` 不接外部检索引擎，内部是 `WHERE type = ... ORDER BY updated_at DESC`。方法签名预留 `query` 参数是为了 B2/B3 扩展兼容，B1 阶段 `query` 仅用于日志。

> **修正 #9**：设计文档 §5.3/§8.3/§12.0 的示例代码中 `search()` 传了 `min_score` 参数，
> 但此处 ABC 签名没有该参数。B1 无语义检索，无分数概念，统一不加 `min_score`。
> 设计文档中的 `min_score=0.1` 示例属于 Phase B2+ 的接口预览，不是 B1 实现规格。

### Step 3: PG 实现（`infrastructure/repositories/memory_repository.py`）

遵循 `PostgresAgentRepository` 模式：`AsyncSession` 注入 + `_to_domain` 转换函数。

```python
"""PostgresMemoryRepository：MemoryRepository 的 SQLAlchemy 实现。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.memory import Memory
from app.domain.repositories.memory_repository import MemoryRepository
from app.infrastructure.db.models import MemoryModel


def _to_domain(m: MemoryModel) -> Memory:
    return Memory(
        id=m.id, agent_id=m.agent_id, group_id=m.group_id,
        memory_type=m.memory_type, title=m.title, content=m.content,
        metadata=m.extra or {},  # ORM 属性名 extra，映射到 DB 列 metadata
        hits=m.hits,
        expires_at=m.expires_at, created_at=m.created_at, updated_at=m.updated_at,
    )


def _to_model(memory: Memory) -> MemoryModel:
    return MemoryModel(
        id=memory.id, agent_id=memory.agent_id, group_id=memory.group_id,
        memory_type=memory.memory_type, title=memory.title,
        content=memory.content, extra=memory.metadata,  # Domain.metadata → ORM.extra
        hits=memory.hits, expires_at=memory.expires_at,
        created_at=memory.created_at, updated_at=memory.updated_at,
    )


class PostgresMemoryRepository(MemoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, memory: Memory) -> None:
        existing = await self._s.get(MemoryModel, memory.id)
        if existing:
            existing.title = memory.title
            existing.content = memory.content
            existing.extra = memory.metadata  # ORM.extra → DB.metadata
            existing.hits = memory.hits
            existing.expires_at = memory.expires_at
            existing.updated_at = memory.updated_at
        else:
            self._s.add(_to_model(memory))
        await self._s.flush()

    async def get_by_id(self, memory_id: UUID) -> Memory | None:
        m = await self._s.get(MemoryModel, memory_id)
        return _to_domain(m) if m else None

    async def search(
        self, agent_id: UUID, query: str, top_k: int = 5
    ) -> list[Memory]:
        # B1: type 过滤 + 时间排序（不接检索引擎）
        stmt = (
            select(MemoryModel)
            .where(MemoryModel.agent_id == agent_id)
            .order_by(MemoryModel.updated_at.desc())
            .limit(top_k)
        )
        result = await self._s.execute(stmt)
        return [_to_domain(m) for m in result.scalars().all()]

    async def get_by_type(
        self, agent_id: UUID, memory_type: str
    ) -> list[Memory]:
        stmt = (
            select(MemoryModel)
            .where(
                MemoryModel.agent_id == agent_id,
                MemoryModel.memory_type == memory_type,
            )
            .order_by(MemoryModel.updated_at.desc())
        )
        result = await self._s.execute(stmt)
        return [_to_domain(m) for m in result.scalars().all()]

    async def get_recent(
        self, agent_id: UUID, limit: int = 5
    ) -> list[Memory]:
        stmt = (
            select(MemoryModel)
            .where(MemoryModel.agent_id == agent_id)
            .order_by(MemoryModel.updated_at.desc())
            .limit(limit)
        )
        result = await self._s.execute(stmt)
        return [_to_domain(m) for m in result.scalars().all()]

    async def find_by_content(
        self, agent_id: UUID, memory_type: str, content: str
    ) -> Memory | None:
        """精确匹配去重：同一 Agent 下 type+content 完全相同的记录。"""
        stmt = (
            select(MemoryModel)
            .where(
                MemoryModel.agent_id == agent_id,
                MemoryModel.memory_type == memory_type,
                MemoryModel.content == content,
            )
            .limit(1)
        )
        result = await self._s.execute(stmt)
        m = result.scalars().first()
        return _to_domain(m) if m else None

    async def delete(self, memory_id: UUID) -> None:
        m = await self._s.get(MemoryModel, memory_id)
        if m:
            await self._s.delete(m)
            await self._s.flush()
```

### Step 4: MemoryService（`application/services/memory_service.py`）

业务编排层：CRUD + 标记解析 + 注入格式化。

```python
"""MemoryService：记忆 CRUD + 检索 + 标记解析（L3 业务编排）。"""

from __future__ import annotations

import logging
import re
from uuid import UUID

from app.domain.entities.memory import Memory
from app.domain.repositories.memory_repository import MemoryRepository

logger = logging.getLogger(__name__)

# <!-- MEMORY:type --> content（HTML 注释格式，防止与 Agent 正常文本误匹配）
_MEMORY_MARKER_RE = re.compile(r"^<!--\s*MEMORY:(\w+)\s*-->\s*(.+)", re.MULTILINE)


class MemoryService:
    def __init__(self, repo: MemoryRepository) -> None:
        self._repo = repo

    # ---- CRUD ----

    async def save(self, memory: Memory) -> None:
        await self._repo.save(memory)

    async def get_recent(self, agent_id: UUID, limit: int = 5) -> list[Memory]:
        return await self._repo.get_recent(agent_id, limit=limit)

    # ---- 标记解析 ----

    @staticmethod
    def parse_markers(text: str) -> tuple[str, list[dict]]:
        """从 Agent 回复中解析 <!-- MEMORY:type --> 标记。

        Returns:
            cleaned_text: 移除标记后的原文
            mem_entries: [{"type": "facts", "content": "..."}, ...]
        """
        entries: list[dict] = []
        lines = text.split("\n")
        cleaned: list[str] = []
        for line in lines:
            m = _MEMORY_MARKER_RE.match(line.strip())
            if m:
                entries.append({
                    "type": m.group(1),
                    "content": m.group(2).strip(),
                })
            else:
                cleaned.append(line)
        return "\n".join(cleaned), entries

    async def save_from_markers(
        self, agent_id: UUID, mem_entries: list[dict], group_id: UUID | None = None
    ) -> None:
        """将解析出的标记条目转为 Memory 实体并保存。

        第 1 层去重（精确匹配）：agent_id + type + content 完全相同的记录只刷新
        updated_at，不新增。覆盖 80% 重复场景（Agent 对同一事实输出完全相同的标记文本）。
        """
        from datetime import UTC, datetime

        for entry in mem_entries:
            mem_type = entry["type"]
            if mem_type not in ("facts", "preferences", "procedures", "context"):
                logger.warning("Unknown memory type=%s, skipping", mem_type)
                continue

            content = entry["content"]
            title = content[:200]  # title 是 content 的前 200 字符缩写

            # Layer 1: 精确匹配去重 — 相同 type+content 只刷新 updated_at
            try:
                existing = await self._repo.find_by_content(agent_id, mem_type, content)
            except Exception:
                logger.exception("Dedup lookup failed, fallback to insert")
                existing = None

            if existing is not None:
                existing.updated_at = datetime.now(UTC)
                try:
                    await self._repo.save(existing)
                    logger.debug("Memory dedup: type=%s content already exists, refreshed", mem_type)
                except Exception:
                    logger.exception("Failed to refresh existing memory: type=%s", mem_type)
                continue

            memory = Memory(
                agent_id=agent_id,
                group_id=group_id,
                memory_type=mem_type,
                title=title,
                content=content,
            )
            try:
                await self._repo.save(memory)
                logger.info("Memory saved: type=%s title=%s", mem_type, title[:80])
            except Exception:
                logger.exception("Failed to save memory: type=%s", mem_type)

    # ---- 注入格式化 ----

    @staticmethod
    def format_injection(memories: list[Memory]) -> str | None:
        """格式化记忆列表为注入文本（≤400 tokens）。

        Returns None 表示无记忆可注入。

        第 3 层去重（读取侧）：相同 content 只注入一次，兜底覆盖第 1 层漏掉的
        换说法的重复记忆（如 Agent 两次输出略有不同的同一事实）。
        """
        if not memories:
            return None

        lines = ["<agent-memories>"]
        seen: set[str] = set()
        for m in memories[:5]:  # 硬限制 5 条
            if m.content in seen:
                continue
            seen.add(m.content)
            type_label = {
                "facts": "事实",
                "preferences": "偏好",
                "procedures": "流程",
                "context": "上下文",
            }.get(m.memory_type, m.memory_type)
            lines.append(f"[{type_label}] {m.content}")
        lines.append("</agent-memories>")

        return "\n".join(lines)

    # ---- 检索（B1：过滤 + 排序） ----

    async def search(
        self, agent_id: UUID, query: str, top_k: int = 5
    ) -> list[Memory]:
        """检索相关记忆。B1 阶段按最近更新排序（暂不接检索引擎）。"""
        return await self._repo.search(agent_id, query, top_k=top_k)
```

### Step 4b: 去重机制（借鉴 EverMem 5 层模型）

> **设计依据**：EverMem 有 5 层去重（Episode ID 幂等 → LLM ADD/UPDATE/DELETE → 向量聚类 → Skill 增量更新 → Profile 压缩）。
> B1 零 LLM 成本、零向量检索约束下，取其第 1 层（确定性标识幂等）+ 第 3 层（读取侧去重），
> 第 2/5 层留到 Phase B2+。

**EverMem 5 层去重全景（按触发顺序）**：

```
第 1 层：Episode ID 幂等（写入门口）
  每段对话有唯一 ID，处理过就不再处理。最粗粒度——防止同一段对话被重复提取。

第 2 层：LLM 判断 ADD / UPDATE / DELETE（Profile 写入时）
  LLM 看到已有条目列表 + 新提取内容，输出三种操作之一。
  语义级去重，能识别 "JWT 过期 7 天" 和 "JWT 的过期时间设为七天" 是同一件事。

第 3 层：向量聚类（Cluster 级）
  cosine_similarity >= threshold → 归入已有集群，相似记忆聚合。

第 4 层：Skill 增量更新（Top-K 向量匹配 + LLM 决策）
  新 Case 与已有 Skill 做相似度比对，LLM 判断是"新技能"还是"已有技能的补充"。

第 5 层：Profile 压缩（超阈值触发）
  150% 触发 → LLM 批量合并相似、删除过时、精炼标签。事后清理，不是写入拦截。
```

**EverMem 依赖分析**：第 2/4/5 层全依赖 LLM 判断，第 3/4 层依赖向量相似度。B1 两者都没有。

**B1 适配方案**（取 EverMem 第 1 层思路——确定性标识去重，零 LLM 成本）：

| 层 | EverMem | B1 适配 | 成本 |
|---|---------|---------|------|
| 幂等拦截 | Episode ID | `agent_id + type + content` 精确匹配 → 只刷新 `updated_at` | ~20 行 |
| 语义去重 | LLM ADD/UPDATE | 不做（B1 零 LLM 成本约束） | 0 |
| 读取去重 | 向量相似度排序 | `format_injection()` 中对 `content` 做 set 去重 | ~5 行 |
| 事后压缩 | LLM 压缩到 70% | Phase B2（当 agent 记忆 > 50 条时触发） | 0 |

**第 1 层覆盖 80% 场景**：Agent 对同一事实重复输出完全相同的 `<!-- MEMORY:type --> content` 行时，精确匹配命中，不新增记录，只刷新 `updated_at`。

**第 3 层兜底**：如果同一事实被 Agent 以略微不同的措辞存入（精确匹配失败），注入时 content set 去重确保不向 context window 注入重复内容。

已在上方 Step 3（`find_by_content`）、Step 4（`save_from_markers` 精确匹配 + `format_injection` set 去重）中实现。

---

### Step 5: Migration 0005

遵循 `0004_create_groups.py` 模式：idempotent（检查表是否存在）。

```python
"""0005_create_memories

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-01
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "memories" in inspector.get_table_names():
        return

    op.create_table(
        "memories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("group_id", sa.Uuid(), sa.ForeignKey("groups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("memory_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), default=dict, server_default="{}"),
        sa.Column("hits", sa.Integer(), default=0, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_memories_agent_type", "memories", ["agent_id", "memory_type"])
    op.create_index("idx_memories_agent_updated", "memories", ["agent_id", "updated_at"])
    # PG-only: GIN 索引用于 JSONB metadata 的 sub_type 检索，SQLite 不兼容
    op.create_index("idx_memories_metadata", "memories", ["metadata"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_table("memories")
```

### Step 6: ORM 模型（`infrastructure/db/models.py` 追加）

> **修正 #1**：`metadata` 属性名与 `Base.metadata`（SQLAlchemy `MetaData` 实例）冲突，
> 会导致运行时错误。采用 `MessageModel` 已验证的别名模式：Python 属性名 `extra`，DB 列名 `metadata`。

```python
class MemoryModel(Base):
    __tablename__ = "memories"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True
    )
    memory_type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    # Python 属性名 extra，DB 列名 metadata（避免与 Base.metadata 冲突）
    extra: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
```

### Step 7: 重写 SystemPromptBuilder._memory_instructions()

删除 `_cwd_to_cli_memory_path()` 方法（system_prompt_builder.py:71-78）。
重写 `_memory_instructions()` 为基于 `<!-- MEMORY: -->` 标记的指令。

> **修正 #3**：标记格式从 `[MEMORY:type]` 改为 `<!-- MEMORY:type -->`（HTML 注释），
> 防止 Agent 正常文本中以 `[MEMORY:xxx]` 开头的行被误匹配。HTML 注释不会被 Markdown 渲染，
> 且在自然语言中出现概率极低。

```python
def _memory_instructions(self) -> str:
    """生成 ~250 tokens 的记忆指令段（CLI 无关）。"""
    return """# Memory

You have a memory system managed by AgentHub. When you encounter information worth remembering, output it on a separate line in your reply using this exact format:

<!-- MEMORY:type --> content

Types:
- facts: Project knowledge (architecture, conventions, decisions)
- preferences: User/team working style and preferences
- procedures: Reusable workflows and past solutions
- context: Session continuity (what was done last time)

Examples:
<!-- MEMORY:facts --> JWT 过期时间设为 7 天
<!-- MEMORY:preferences --> 用户偏好用 ruff 格式化而非 black
<!-- MEMORY:procedures --> 部署命令：docker compose -f src/docker/docker-compose.yml up -d --build

When the user says "remember this" or "记一下", use this format. The system will parse markers from your reply and store them. Do NOT use the Write tool for memory — markers in your reply are the correct path."""
```

### Step 8: ContextBuilder._maybe_inject_memories()

在 `context_builder.py` 的 `ContextBuilder` 类中新增方法，在 `_build_group()` 和 `_build_private()` 中调用。

```python
import asyncio  # 修正 #6：补全缺失的 import

# 新增依赖注入
def __init__(self, ..., memory_svc: "MemoryService | None" = None):
    ...
    self._memory_svc = memory_svc

async def _maybe_inject_memories(
    self, target_agent: "Agent", trigger: "Message"
) -> str | None:
    """每轮触发，按需注入。失败静默降级。"""
    if self._memory_svc is None:
        return None
    try:
        if len(trigger.content.strip()) < 10:
            return None
        memories = await asyncio.wait_for(
            self._memory_svc.search(
                agent_id=target_agent.id,
                query=trigger.content,
                top_k=5,
            ),
            timeout=5.0,
        )
        if not memories:
            return None
        return self._memory_svc.format_injection(memories)
    except asyncio.TimeoutError:
        logger.warning("Memory search timeout for agent=%s", target_agent.id)
    except Exception:
        logger.warning("Memory injection failed", exc_info=True)
    return None
```

**群聊路径**（`_build_group`）：将返回值填充到 `MemoryContext.l4_rag`。

```python
# context_builder.py:_build_group — 现有 line 127-138 之前插入
mem_l4 = await self._maybe_inject_memories(target_agent, trigger)
memory_context = MemoryContext(l4_rag=mem_l4) if mem_l4 else None

return AgentRequest(
    ...
    memory=memory_context,  # 群聊此前不设 memory
    group_delta_text=group_delta_text,
)
```

**私聊路径**（`_build_private`）：现有 line 155 已设 `memory=MemoryContext(l1_working=window)`，扩展：

```python
# context_builder.py:_build_private — line 155 改为
mem_l4 = await self._maybe_inject_memories(target_agent, trigger)
memory = MemoryContext(
    l1_working=window,
    l4_rag=mem_l4,
)
```

### Step 9: ChatService 标记解析

`chat_service.py:_stream_one_agent` 中 line 256（`full = "".join(buffer)`）之后插入：

> **修正 #4**：DB 和 L1 缓存**都**使用 `cleaned_content`（不含标记），保持一致。
> 否则下一轮 Agent 上下文（L1）中会出现原始标记行，导致 Agent 困惑或重复输出标记。

```python
full = "".join(buffer)

# 解析并存储 <!-- MEMORY: --> 标记
cleaned_content, mem_entries = MemoryService.parse_markers(full)
if mem_entries:
    try:
        await self._memory_svc.save_from_markers(
            agent_id=target.id,
            mem_entries=mem_entries,
            group_id=group.id if group else None,
        )
    except Exception:
        logger.warning("Memory marker parsing failed", exc_info=True)

assistant_msg.content = cleaned_content  # DB 存清洗后内容

# L1 缓存也存 cleaned_content（不是 full），保持与 DB 一致
await self._l1.append(
    session.id, {"role": "assistant", "content": cleaned_content}
)
```

### Step 10: deps.py 依赖注册

> **修正 #5**：原计划只列了新增 getter，遗漏了 `get_chat_service()` 和
> `build_chat_service_for_ws()` 两处 `ContextBuilder` / `ChatService` 构造需要传入 `memory_svc`。
> 不改会导致 `TypeError: __init__() missing required argument`。

```python
# 新增 imports
from app.infrastructure.repositories.memory_repository import PostgresMemoryRepository
from app.application.services.memory_service import MemoryService

# 新增 getter（请求范围，随 DbSession 生命周期）
async def get_memory_repo(session: DbSession) -> PostgresMemoryRepository:
    return PostgresMemoryRepository(session)

async def get_memory_svc(
    repo: PostgresMemoryRepository = Depends(get_memory_repo),
) -> MemoryService:
    return MemoryService(repo)

# ---- 以下为已有函数的修改 ----

# get_chat_service()（约 line 128-132）：
#   1. 新增参数 memory_svc: MemoryService = Depends(get_memory_svc)
#   2. ContextBuilder(..., memory_svc=memory_svc)
#   3. ChatService(..., memory_svc=memory_svc)

# build_chat_service_for_ws()（约 line 164-168）：
#   1. 手动构造 memory_repo = PostgresMemoryRepository(session)
#   2. memory_svc = MemoryService(memory_repo)
#   3. ContextBuilder(..., memory_svc=memory_svc)
#   4. ChatService(..., memory_svc=memory_svc)

# ChatService.__init__ 签名变更：
#   def __init__(self, ..., memory_svc: MemoryService) -> None:
#       self._memory_svc = memory_svc
```

### Step 11: 导出更新

```python
# domain/entities/__init__.py 追加
from app.domain.entities.memory import Memory

# domain/repositories/__init__.py 追加
from app.domain.repositories.memory_repository import MemoryRepository

# 修正 #7：infrastructure/repositories/__init__.py 追加
from app.infrastructure.repositories.memory_repository import PostgresMemoryRepository
```

---

## 五、测试计划

### 5.1 新增测试文件

**`test_memory_entity.py`** — 实体校验：
- 有效 Memory 构造成功
- title/content 为空抛 DomainError
- 无效 memory_type 抛 DomainError
- metadata 默认值为 {}

**`test_memory_service.py`** — 业务逻辑：
- `parse_markers()` 正确解析 `<!-- MEMORY:type -->` 单条/多条/无标记
- `parse_markers()` 正确清除标记行
- `parse_markers()` 不误匹配非标记行（如自然文本中含 MEMORY 字样）
- `format_injection()` 空列表返回 None
- `format_injection()` 超过 5 条截断
- `format_injection()` 相同 content 去重（只注入一次）
- `save_from_markers()` 无效 type 跳过并 log warning
- `save_from_markers()` 失败不抛异常
- `save_from_markers()` 重复 type+content → 不新增记录，只刷新 updated_at

**`test_memory_repository.py`** — PG 存取：
- save 新 Memory → get_by_id 可获取
- save 已存在 Memory → 更新
- get_recent 按 updated_at DESC 排序
- `find_by_content` 精确匹配命中 → 返回已有 Memory
- `find_by_content` 无匹配 → 返回 None
- delete 后 get_by_id 返回 None

### 5.2 修改已有测试

| 测试 | 改动 |
|------|------|
| `test_memory_path_encoding` | **删除**（方法已删除） |
| `test_build_with_all_fields` | 更新 `"# Memory"` 断言为新的指令文本 |
| `test_build_minimal` | 同上 |
| `test_agent_file_manager.test_cleanup_agent_cwd` | 删除 memory path 日志断言 |
| `test_context_builder` | 新增：记忆注入成功填充 `l4_rag`；记忆服务异常时静默降级 |
| `test_chat_service` | 新增：`<!-- MEMORY:facts -->` 标记正确解析并存储，文本中标记行被移除；L1 缓存存 `cleaned_content`（不含标记） |

---

## 六、执行顺序与依赖

```
Phase B1 执行 DAG：

Step 5: Migration 0005
    │
    ├─→ Step 6: ORM Model ──→ Step 3: PG Repository (含 find_by_content)
    │
Step 1: Memory Entity
    │
    ├─→ Step 2: Repository Protocol (含 find_by_content)
    │       │
    │       └─→ Step 4: MemoryService (含去重逻辑)
    │               │
    └─→ Step 11: Export updates
                    │
                    ├─→ Step 7: SPB rewrite ──→ Test update
                    ├─→ Step 8: ContextBuilder ──→ Test update
                    ├─→ Step 9: ChatService ──→ Test update
                    └─→ Step 10: deps.py wiring
```

**可并行执行**：
- Step 1-5-6-11（L2 + L1 基础设施）与 Step 7（SPB 重写）无依赖
- Step 3 → Step 4 → Step 10 是串行链

---

## 七、验收标准

1. Agent 回复中输出 `<!-- MEMORY:facts --> JWT 过期 7 天` → `memories` 表新增一条记录，回复文本中不包含该标记行
2. Agent 下一条消息时 `l4_rag` 中包含已存的记忆
3. SP 中不含 `~/.claude/projects/` 或 Write tool 路径引用
4. PG 不可用时注入 + 标记解析均静默降级，Agent 正常执行任务
5. 已有测试全部通过，新测试覆盖 ≥ 80%

---

## 八、后续 Phase 预览

| Phase | 交付内容 | 触发条件 |
|-------|---------|---------|
| B2 | tsvector 全文搜索替换 `ORDER BY updated_at` | 记忆量 > 50 条/Agent |
| C | pgvector 向量检索 + 后端被动提取 | B2 检索质量不够 + LLM 成本预算确认 |
| D | 跨 Agent 记忆共享 | 群聊场景需要 |
| E | Elasticsearch hybrid search | 记忆量 > 1K 条 且中文语义匹配需求 |
