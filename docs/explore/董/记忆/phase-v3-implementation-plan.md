# 记忆系统 V3 — 实现方案

> 日期：2026-06-02 | 对应设计：`memory-system-design-v3.md`
> 无 `memory_type`，无 `get_memory`，有 `source`，有 `scope`

---

## 总体顺序

```
Phase 1: 数据层      → Phase 2: 应用服务    → Phase 3: API 层
    ↓                      ↓                      ↓
ORM + migration      MemoryService          REST router
域实体 + 仓储          MemorySelector         MCP endpoint
                           ↓
Phase 4: SP 注入     Phase 5: CLI MCP      Phase 6: 前端对齐
ContextBuilder 改     _build_cmd 加参数     types + panel 表单
```

Phase 4 和 Phase 5 可并行。Phase 6 在 Phase 3 API 接口确定后可并行。

---

## Phase 1：数据层

### 1.1 `app/infrastructure/db/models.py` — 新增 MemoryModel

```python
class MemoryModel(Base):
    __tablename__ = "memories"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("groups.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[UUID] = mapped_column(Uuid, index=True)   # 创建者，暂不 FK
    scope: Mapped[str] = mapped_column(String(10))             # 'agent' | 'group'
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual|chat|system
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
```

注意：`metadata` 是 SQLAlchemy 保留属性名，列名用 `metadata`、属性名用 `metadata_`（参考 MessageModel.extra 的同款处理）。

### 1.2 Alembic migration — `0005_create_memories.py`

```python
def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(10), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("scope IN ('agent', 'group')", name="ck_memories_scope"),
        sa.CheckConstraint("source IN ('manual', 'chat', 'system')", name="ck_memories_source"),
    )
    op.create_index("idx_memories_agent_scope", "memories", ["agent_id", "scope"])
    op.create_index("idx_memories_group", "memories", ["group_id"],
                    postgresql_where=sa.text("group_id IS NOT NULL"))
    op.create_index("idx_memories_pinned", "memories", ["agent_id", "scope", "pinned"],
                    postgresql_where=sa.text("pinned = true"))
    op.create_index("idx_memories_updated", "memories", ["agent_id", "scope",
                    sa.text("updated_at DESC")])
```

### 1.3 域实体 — `app/domain/entities/memory.py`（新建）

```python
@dataclass
class Memory:
    id: UUID
    agent_id: UUID
    user_id: UUID
    scope: str          # 'agent' | 'group'
    name: str
    description: str
    content: str
    source: str         # 'manual' | 'chat' | 'system'
    pinned: bool
    hits: int
    metadata: dict
    group_id: UUID | None
    created_at: datetime
    updated_at: datetime
```

### 1.4 仓储接口 — `app/domain/repositories/memory_repository.py`（新建）

```python
class MemoryRepository(ABC):
    @abstractmethod
    async def save(self, memory: Memory) -> None: ...

    @abstractmethod
    async def get_by_id(self, memory_id: UUID) -> Memory | None: ...

    @abstractmethod
    async def list_candidates(
        self, *, agent_id: UUID, group_id: UUID | None, limit: int = 50,
    ) -> list[Memory]:
        """候选集：pinned 优先 + 最近更新。
        群聊：scope='group' AND group_id=$2 OR scope='agent' AND agent_id=$1
        私聊：group_id=None → 只取 scope='agent' AND agent_id=$1
        """
        ...

    @abstractmethod
    async def list_by_agent(self, agent_id: UUID) -> list[Memory]: ...

    @abstractmethod
    async def increment_hits(self, memory_ids: list[UUID]) -> None:
        """批量 UPDATE hits = hits + 1（原子）。"""
        ...

    @abstractmethod
    async def delete(self, memory_id: UUID) -> None: ...
```

### 1.5 Postgres 实现 — `app/infrastructure/repositories/memory_repository.py`（新建）

```python
class PostgresMemoryRepository(MemoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, memory: Memory) -> None:
        existing = await self._s.get(MemoryModel, memory.id)
        if existing is None:
            self._s.add(_to_model(memory))
        else:
            _update_model(existing, memory)
        await self._s.flush()

    async def list_candidates(self, *, agent_id, group_id, limit=50):
        if group_id is not None:
            stmt = (
                select(MemoryModel)
                .where(
                    or_(
                        and_(MemoryModel.scope == "group", MemoryModel.group_id == group_id),
                        and_(MemoryModel.scope == "agent", MemoryModel.agent_id == agent_id),
                    )
                )
                .order_by(MemoryModel.pinned.desc(), MemoryModel.updated_at.desc())
                .limit(limit)
            )
        else:
            stmt = (
                select(MemoryModel)
                .where(MemoryModel.agent_id == agent_id, MemoryModel.scope == "agent")
                .order_by(MemoryModel.pinned.desc(), MemoryModel.updated_at.desc())
                .limit(limit)
            )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def increment_hits(self, memory_ids: list[UUID]) -> None:
        if not memory_ids:
            return
        stmt = (
            update(MemoryModel)
            .where(MemoryModel.id.in_(memory_ids))
            .values(hits=MemoryModel.hits + 1)
        )
        await self._s.execute(stmt)
```

---

## Phase 2：应用服务

### 2.1 `app/application/services/memory_service.py`（新建）

```python
class MemoryService:
    def __init__(self, repo: MemoryRepository) -> None:
        self._repo = repo

    async def create(self, *, agent_id, user_id, cmd: CreateMemoryCommand) -> Memory:
        scope = "group" if cmd.group_id else "agent"
        m = Memory(
            id=uuid4(), agent_id=agent_id, user_id=user_id,
            scope=scope, name=cmd.name, description=cmd.description,
            content=cmd.content, source=cmd.source,
            pinned=False, hits=0, metadata=cmd.metadata or {},
            group_id=cmd.group_id, created_at=now(), updated_at=now(),
        )
        await self._repo.save(m)
        return m

    async def update(self, memory_id, *, patch: UpdateMemoryCommand) -> Memory:
        m = await self._repo.get_by_id(memory_id)
        if m is None:
            raise NotFoundError(f"memory {memory_id}")
        updated = replace(m,
            name=patch.name if patch.name is not None else m.name,
            description=patch.description if patch.description is not None else m.description,
            content=patch.content if patch.content is not None else m.content,
            pinned=patch.pinned if patch.pinned is not None else m.pinned,
            metadata=patch.metadata if patch.metadata is not None else m.metadata,
            updated_at=now(),
        )
        await self._repo.save(updated)
        return updated

    async def list_by_agent(self, agent_id):
        return await self._repo.list_by_agent(agent_id)

    async def delete(self, memory_id):
        await self._repo.delete(memory_id)
```

### 2.2 `app/application/services/memory_selector.py`（新建）

```python
_SELECTOR_PROMPT = """\
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
- Return ONLY the IDs of selected memories, one per line. No other text."""

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_MAX_CONTEXT_CHARS = 3000
_MSG_MAX_CHARS = 300


class MemorySelector:
    def __init__(self, repo: MemoryRepository) -> None:
        self._repo = repo

    async def select_for_agent(
        self, *, agent_id: UUID, group_id: UUID | None, dialogue_context: str,
    ) -> list[Memory]:
        candidates = await self._repo.list_candidates(
            agent_id=agent_id, group_id=group_id
        )
        if not candidates:
            return []

        pinned = [m for m in candidates if m.pinned]
        non_pinned = [m for m in candidates if not m.pinned]

        selected_ids = await self._llm_select(non_pinned, dialogue_context)
        selected_non_pinned = [m for m in non_pinned if m.id in selected_ids]

        result = pinned + selected_non_pinned
        if result:
            await self._repo.increment_hits([m.id for m in result])
        return result

    async def _llm_select(self, candidates: list[Memory], ctx: str) -> set[UUID]:
        if not candidates:
            return set()
        candidate_list = "\n".join(
            f"[{m.id}] {m.name} — {m.description} ({m.scope}, {_age_label(m.created_at)})"
            for m in candidates
        )
        prompt_text = _SELECTOR_PROMPT.format(
            dialogue_context=ctx[:_MAX_CONTEXT_CHARS],
            candidate_list=candidate_list,
        )
        try:
            client = anthropic.AsyncAnthropic()
            resp = await client.messages.create(
                model=_HAIKU_MODEL, max_tokens=256,
                messages=[{"role": "user", "content": prompt_text}],
            )
            lines = resp.content[0].text.strip().splitlines()
            result = set()
            for line in lines:
                try:
                    result.add(UUID(line.strip()))
                except ValueError:
                    pass
            return result
        except Exception:
            logger.warning("MemorySelector LLM 调用失败，降级返回空集")
            return set()

    @staticmethod
    def build_dialogue_context(messages: list[dict]) -> str:
        """取最近 10 条，每条截断到 300 字符，总计 ≤3000 字符。"""
        recent = messages[-10:]
        parts = []
        for m in recent:
            role = m.get("role", "")
            content = (m.get("content", "") or "")[:_MSG_MAX_CHARS]
            parts.append(f"{role}: {content}")
        return "\n".join(parts)[:_MAX_CONTEXT_CHARS]
```

### 2.3 `app/schemas/memory.py`（新建）

```python
class MemoryCreate(BaseModel):
    name: str = Field(max_length=150)
    description: str = Field(max_length=300)
    content: str
    group_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)

class MemoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None
    pinned: bool | None = None
    metadata: dict | None = None

class MemoryOut(BaseModel):
    id: UUID
    agent_id: UUID
    group_id: UUID | None
    user_id: UUID
    scope: str
    name: str
    description: str
    content: str
    source: str
    pinned: bool
    hits: int
    metadata: dict
    created_at: datetime
    updated_at: datetime

class MemoryStatsOut(BaseModel):
    total: int
    oldest: datetime | None
    newest: datetime | None
```

---

## Phase 3：API 层

### 3.1 `app/api/routers/memories.py`（新建）

```python
router = APIRouter(prefix="/api/agents/{agent_id}/memories", tags=["memories"])

@router.get("", response_model=list[MemoryOut])
async def list_memories(agent_id: UUID, svc: MemoryServiceDep):
    items = await svc.list_by_agent(agent_id)
    return [MemoryOut.model_validate(m.__dict__) for m in items]

@router.post("", response_model=MemoryOut, status_code=201)
async def create_memory(agent_id: UUID, body: MemoryCreate, svc: MemoryServiceDep):
    m = await svc.create(agent_id=agent_id, user_id=agent_id,
                         cmd=CreateMemoryCommand(source="manual", **body.model_dump()))
    return MemoryOut.model_validate(m.__dict__)

@router.patch("/{memory_id}", response_model=MemoryOut)
async def update_memory(agent_id: UUID, memory_id: UUID, body: MemoryUpdate, svc: MemoryServiceDep):
    m = await svc.update(memory_id, patch=UpdateMemoryCommand(**body.model_dump(exclude_none=True)))
    return MemoryOut.model_validate(m.__dict__)

@router.delete("/{memory_id}", status_code=204)
async def delete_memory(agent_id: UUID, memory_id: UUID, svc: MemoryServiceDep):
    await svc.delete(memory_id)

@router.get("/stats", response_model=MemoryStatsOut)
async def memory_stats(agent_id: UUID, svc: MemoryServiceDep):
    return await svc.stats(agent_id)
```

### 3.2 `app/api/mcp_memory.py`（新建）

```python
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
    svc = get_memory_service_singleton()
    m = await svc.create(
        agent_id=_current_agent_id(),
        user_id=_current_agent_id(),
        cmd=CreateMemoryCommand(
            name=name, description=description, content=content,
            group_id=UUID(group_id) if group_id else None, source="chat",
        ),
    )
    return {"id": str(m.id), "source": "chat", "status": "saved"}

def get_mcp_router() -> APIRouter:
    return mcp.get_sse_app()
```

注意：`_current_agent_id()` 需在 CLI spawn 时通过环境变量传入 agent_id（见 Phase 5）。

### 3.3 `app/main.py` — 注册路由

```python
from app.api.mcp_memory import get_mcp_router

app.include_router(memories.router)
app.mount("/api/mcp", get_mcp_router())
```

### 3.4 `app/api/deps.py` — 注入 MemoryService

```python
def get_memory_repo(session: DbSession) -> PostgresMemoryRepository:
    return PostgresMemoryRepository(session)

def get_memory_service(
    repo: Annotated[PostgresMemoryRepository, Depends(get_memory_repo)],
) -> MemoryService:
    return MemoryService(repo)

MemoryServiceDep = Annotated[MemoryService, Depends(get_memory_service)]
```

---

## Phase 4：SP 注入（ContextBuilder 改动）

### 4.1 `app/application/services/context_builder.py`

```python
class ContextBuilder:
    def __init__(self, message_repo, agent_repo, l1_memory, watermarks,
                 memory_selector: MemorySelector | None = None) -> None:
        ...
        self._mem = memory_selector

    async def _build_group(self, ...) -> AgentRequest:
        ...
        # 现有逻辑不变，system_prompt 组装后追加记忆块
        memory_block = await self._build_memory_block(
            agent_id=target_agent.id, group_id=group.id,
            messages=delta.messages,
        )
        if memory_block:
            system_prompt = system_prompt + "\n\n" + memory_block
        ...

    async def _build_private(self, ...) -> AgentRequest:
        ...
        window = await self._l1.get_window(session.id)
        memory_block = await self._build_memory_block(
            agent_id=target_agent.id, group_id=None,
            messages=window,
        )
        if memory_block:
            system_prompt = (target_agent.system_prompt or "") + "\n\n" + memory_block
        ...

    async def _build_memory_block(
        self, *, agent_id: UUID, group_id: UUID | None, messages: list
    ) -> str:
        if self._mem is None:
            return ""
        ctx = MemorySelector.build_dialogue_context(
            [{"role": m.role if hasattr(m, 'role') else m.get('role', ''),
              "content": m.content if hasattr(m, 'content') else m.get('content', '')}
             for m in messages]
        )
        memories = await self._mem.select_for_agent(
            agent_id=agent_id, group_id=group_id, dialogue_context=ctx
        )
        if not memories:
            return ""
        return _render_agenthub_reminder(memories)
```

### 4.2 `app/application/services/prompt_templates.py` — 新增渲染函数

```python
def _render_agenthub_reminder(memories: list[Memory]) -> str:
    pinned = [m for m in memories if m.pinned]
    others = [m for m in memories if not m.pinned]

    lines = [
        "<agenthub-reminder>",
        "以下是与当前对话相关的记忆。",
        "",
        "⚠️ 记忆反映保存时的状态，可能已过时。采纳前必须主动验证：",
        "- 文件路径 → 先检查文件是否存在",
        "- 函数名或配置项 → 先 grep 确认",
        "- 项目状态 → 先检查当前代码/文档",
        "- 记忆说「X 存在」≠「X 现在还存在」",
        "如果用户要求忽略记忆，以用户指令为准。",
    ]
    if pinned:
        lines += ["", "━━━ PINNED ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        for m in pinned:
            lines += [f"📌 [{m.name}] — {_age_label(m.created_at)}",
                      f"**摘要**: {m.description}", f"**内容**: {m.content}", ""]
    if others:
        lines += ["━━━ 相关记忆 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        for m in others:
            age = _age_label(m.created_at)
            warn = _age_warning(m.created_at)
            lines += [f"📄 [{m.name}] — {age}"]
            if warn:
                lines.append(warn)
            lines += [f"**摘要**: {m.description}", f"**内容**: {m.content}", ""]
    lines.append("</agenthub-reminder>")
    return "\n".join(lines)


def _age_label(dt: datetime) -> str:
    delta = datetime.now(UTC) - dt
    if delta.days == 0: return "今天保存"
    if delta.days == 1: return "昨天保存"
    return f"{delta.days} 天前保存"

def _age_warning(dt: datetime) -> str:
    days = (datetime.now(UTC) - dt).days
    if days >= 30: return "⚠️ 已保存超过 30 天，强烈建议验证。"
    if days >= 2: return "⚠️ 已保存超过 2 天，可能已过时。"
    return ""
```

### 4.3 `deps.py` — MemorySelector 注入

```python
mem_selector = MemorySelector(PostgresMemoryRepository(session))
ctx = ContextBuilder(msg_repo, agent_repo, l1, wm, memory_selector=mem_selector)
```

---

## Phase 5：CLI MCP 接入

### 5.1 `app/infrastructure/llm/claude_code_runtime.py`

```python
def _build_cmd(self, request: AgentRequest, session_key: str, *, resume: bool) -> list[str]:
    cmd = [
        "claude",
        "--output-format", "stream-json",
        "--verbose", "--print",
        "--permission-mode", self._permission_mode,
        "--max-turns", str(self._max_turns),
    ]
    if resume:
        cmd.extend(["--resume", session_key])
    else:
        cmd.extend(["--session-id", session_key])
    if request.system_prompt:
        cmd.extend(["--system-prompt", request.system_prompt])

    # MCP 注入
    if settings.mcp_memory_url:
        mcp_cfg = self._write_mcp_config(str(request.agent_id))
        if mcp_cfg:
            cmd.extend(["--mcp-config", mcp_cfg])   # ⚠️ 需验证 flag 名
    return cmd


def _write_mcp_config(self, agent_id: str) -> str | None:
    """写临时 MCP 配置文件。tempfile + atexit 保证 crash 清理。"""
    config = {
        "mcpServers": {
            "agenthub-memory": {
                "type": "sse",
                "url": settings.mcp_memory_url,
                "env": {"AGENTHUB_AGENT_ID": agent_id},
            }
        }
    }
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="agenthub_mcp_",
        delete=False, dir="/tmp",
    )
    json.dump(config, f)
    f.close()
    atexit.register(os.unlink, f.name)
    return f.name
```

### 5.2 `app/core/config.py` 新增

```python
mcp_memory_url: str = Field(default="", alias="MCP_MEMORY_URL")
# MCP_MEMORY_URL=http://127.0.0.1:8000/api/mcp/sse
```

---

## Phase 6：前端对齐

前端代码已同步修改完成（见当前工作树）：

- `src/frontend/src/types/index.ts` — `ApiMemory` 改为 `name`/`description`/`scope`/`source`，删 `title`/`expires_at`/`memory_type`
- `src/frontend/src/api/memories.ts` — `CreateMemoryInput` 改为 `name`/`description`/`scope`
- `src/frontend/src/stores/memoryStore.ts` — 删 `filterType`/`setFilter`
- `src/frontend/src/components/memory/MemoryPanel.tsx` — 删类型过滤/标签，表单加 `name`/`description` 输入框

---

## 实施顺序与依赖

| 顺序 | Phase | 依赖 |
|:---:|-------|------|
| 1 | Phase 1（模型+迁移） | 无 |
| 2 | Phase 2（服务+选择器） | Phase 1 |
| 3 | Phase 3（API+MCP） | Phase 2 |
| 4 | Phase 4（ContextBuilder） | Phase 2 |
| 5 | Phase 5（CLI MCP） | Phase 3 |
| 6 | Phase 6（前端） | Phase 3 |

Phase 4 和 Phase 5 可并行。Phase 6 已完成，只需后端 API 确定后联调。
