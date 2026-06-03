# V3 记忆系统 — 多轮群聊场景推演

> 日期：2026-06-02 | 用于验证 Selector + Memory 双系统协作

---

## 场景设定

**群组**：后端开发组（group_id = G1）
**用户**：董

**Agent 成员**：

| Agent | 角色 | capability_tags |
|-------|------|----------------|
| 后端专家 | 后端开发 | Python, FastAPI, SQLAlchemy, PostgreSQL |
| DBA | 数据库 | PostgreSQL, Redis, 索引优化, 迁移 |
| 测试专家 | QA | Pytest, Playwright, 集成测试 |

**已有记忆**（用户在前端手动添加）：

| ID | Agent | scope | name | description | content | pinned | 创建时间 |
|----|-------|-------|------|-------------|---------|:---:|------|
| M1 | 后端专家 | group | 不要用裸 SQL | 数据库操作必须走 ORM | 所有数据库操作必须使用 SQLAlchemy ORM，禁止手写 SQL。**Why:** 上季度裸 SQL 注入漏洞导致数据泄露 | ✅ | 今天 |
| M2 | 后端专家 | group | JWT 过期策略 | JWT access 7 天 refresh 30 天 | 认证策略：access_token 7 天过期，refresh_token 30 天。**Why:** 平衡安全性和用户体验 | ❌ | 2 天前 |
| M3 | DBA | group | 迁移流程 | 数据库迁移步骤规范 | 迁移必须：1) alembic revision --autogenerate 2) 手动审查生成的 SQL 3) 先在 staging 跑 4) 再上 prod | ✅ | 今天 |
| M4 | DBA | agent | Redis 集群信息 | 生产 Redis Cluster 配置 | 生产环境使用 Redis Cluster 7.x，3 主 3 从，哨兵模式。**Why:** 高可用要求 | ❌ | 5 天前 |
| M5 | 测试专家 | group | 集成测试连真实 DB | 所有集成测试必须连接真实 PostgreSQL，不要用 SQLite mock。**Why:** 上季度 mock 测试通过但 prod 迁移挂了 | ✅ | 3 天前 |
| M6 | 测试专家 | agent | Pytest 配置 | Pytest 并发配置 | Pytest 使用 pytest-xdist 并发运行，-n auto，单测超时 30s | ❌ | 1 天前 |

---

## Round 1：用户发起话题

```
用户 董: 「我们需要给用户表加一个 last_login_at 字段，大家怎么看」
```

### Step 1: Selector.pick()

**Layer 1 (@mention 检测)**：无 @mention → 跳过
**Layer 1.5 (全体意图)**：匹配到「大家怎么看」→ 触发全体意图

```python
SelectorDecision.pick_multi(
    agent_ids=(后端专家.id, DBA.id, 测试专家.id),
    reason="broadcast: 大家怎么看"
)
```

三个 Agent 全部被选中。DiscussionOrchestrator 串行处理。

### Step 2: 后端专家 — ContextBuilder.build_for_agent()

**候选集查询**：

```sql
WHERE (
  (scope = 'group' AND group_id = 'G1')   -- M1, M2, M3, M5
  OR (scope = 'agent' AND agent_id = 后端专家)  -- (无)
)
ORDER BY pinned DESC, updated_at DESC
LIMIT 50
```

候选集：M1(pinned) + M2 + M3(pinned) + M5(pinned) = 4 条

**记忆选择**：
- pinned 直接入选：M1（不要用裸 SQL）、M3（迁移流程）、M5（集成测试连真实 DB）→ 已占 3 条
- 剩余非 pinned：M2（JWT 过期策略）
- LLM 判断：当前对话关于「加字段」「last_login_at」，JWT 不相关 → 不选
- 最终：M1 + M3 + M5（3 条）

**注入 SP**：

```
<agenthub-reminder>
以下是与当前对话相关的群组记忆。
⚠️ 在采纳记忆中的建议前，必须主动验证其中的事实。

━━━ PINNED ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 [M1] 不要用裸 SQL — 数据库操作必须走 ORM (用户偏好，今天)
📌 [M3] 迁移流程 — 迁移必须 alembic + 手动审查 + staging 先跑 (流程，今天)
📌 [M5] 集成测试连真实 DB — 不要用 SQLite mock (偏好，3 天前)
</agenthub-reminder>
```

**后端专家看到这段记忆后的回复**（预期）：

> 「加 last_login_at 字段我建议用 Alembic 迁移来做。先 `alembic revision --autogenerate` 生成 migration 文件，然后 @DBA 帮忙审查一下 SQL。注意走 ORM，不要手写 SQL。加完字段后 @测试专家 需要在集成测试里验证，记得连真实 DB 不要用 SQLite。」

### Step 3: DBA — ContextBuilder.build_for_agent()

**候选集查询**：

```sql
WHERE (
  (scope = 'group' AND group_id = 'G1')   -- M1, M2, M3, M5
  OR (scope = 'agent' AND agent_id = DBA)  -- M4
)
ORDER BY pinned DESC, updated_at DESC
```

候选集：M1(pinned) + M2 + M3(pinned) + M5(pinned) + M4 = 5 条

pinned 直接入选：M1, M3, M5（3 条）。剩余 2 个名额。

LLM 判断：M4（Redis 集群信息）与当前话题不相关 → 不选。M2（JWT）不相关 → 不选。

最终：M1 + M3 + M5（3 条，pinned 占满）

**DBA 的回复**（预期）：

> 「后端专家说得对，迁移我来审查。加字段这种操作比较常规，但注意 `last_login_at` 应该是 `TIMESTAMPTZ` 类型，记得建索引——用户表按 last_login_at 查询会很频繁。先在 staging 跑一遍确认没问题再上 prod。」

### Step 4: 测试专家 — ContextBuilder.build_for_agent()

候选集：M1(pinned) + M2 + M3(pinned) + M5(pinned) + M6 = 5 条

pinned 直接入选：M1, M3, M5（3 条）。剩余 2 个名额。

LLM 判断：M6（Pytest 并发配置）有一定相关性（测试相关）→ 选入。M2 不相关 → 不选。

最终：M1 + M3 + M5 + M6（4 条）

**测试专家的回复**（预期）：

> 「收到。我会加集成测试验证 `last_login_at` 字段的写入和查询，连真实 DB。测试用例包括：新用户创建时字段为 NULL、登录后更新、按时间范围查询。注意 M6 里提到的 pytest-xdist 并发跑测试时可能有时序问题，我会单独隔离这个 case。」

---

## Round 2：用户追问

```
用户 董: 「索引的事，DBA 你具体说一下」
```

### Step 1: Selector.pick()

Layer 1 (@mention 检测)：无 → 跳过
Layer 1.5：无全体关键词 → 跳过
Layer 2 (capability_tags)：关键词「索引」命中 DBA 的 tags → `「索引优化」`

```python
SelectorDecision.pick(DBA.id, reason="capability hit=1")
```

零 LLM 调用。只选 DBA。

### Step 2: DBA — ContextBuilder.build_for_agent()

候选集与 Round 1 相同。

pinned 直接入选：M1, M3, M5（3 条）。剩余 2 个名额。

LLM 判断：当前对话关于「索引」「具体说一下」。M1（ORM）相关、M3（迁移流程）相关、M4（不相关）、M5（测试相关但不直接）、M2（不相关）。

最终：M1 + M3 + M5（3 条 pinned）+ 非 pinned 全部不相关 = 3 条

**DBA 的回复**（预期）：

> 「好的。`last_login_at` 字段建议建一个 B-tree 索引，因为这个字段会频繁出现在 WHERE 和 ORDER BY 中。另外如果经常查「最近登录的用户」，可以考虑部分索引：`CREATE INDEX idx_users_last_login ON users(last_login_at DESC) WHERE last_login_at IS NOT NULL;`。M3 提到的迁移规范别忘了——先在 staging 验证索引效果。」

---

## Round 3：用户手动添加记忆

```
用户在前端 MemoryPanel 点击「手动添加记忆」：
  Agent: 后端专家
  scope: group
  name: last_login_at 字段设计
  description: 用户表 last_login_at 字段定义
  content: 用户表新增 last_login_at TIMESTAMPTZ，允许 NULL，建 B-tree 降序索引。
  来源：Round 1-2 讨论决策
```

```
POST /api/agents/后端专家/memories
  → MemoryService.create()
  → PG INSERT (M7)
  → 前端 MemoryPanel 即时显示
```

M7 属于 `scope=group`，后续任何 Agent 被激活时都会出现在候选集中。

### Round 3 同时触发：用户 @后端专家 追问

```
用户 董: 「@后端专家 你来实现这个迁移，迁移文件名用 0009_add_last_login_at」
```

### Step 1: Selector.pick()

Layer 1 (@mention 检测)：命中「@后端专家」→ 直接指定

```python
SelectorDecision.pick(后端专家.id, reason="@mention=后端专家")
```

零 LLM 调用。

### Step 2: 后端专家 — ContextBuilder.build_for_agent()

候选集更新：新增 M7（属于 scope=group 且 group_id=G1）

pinned：M1 + M3 + M5（3 条）。剩余 2 个名额。

LLM 判断：当前对话关于「实现迁移」「last_login_at」。M7 直接相关 → 选入。M2（不相关）、其他 pinned 已占满。

最终：M1 + M3 + M5 + M7（4 条）

**后端专家的回复**（预期）：

> 「好的，我来看。M7 里已经记录了字段设计：`last_login_at TIMESTAMPTZ NULL`，降序索引。按照 M3 的迁移规范：先 `alembic revision --autogenerate -m "0009_add_last_login_at"`，手动审查生成的 SQL，确保加了索引语句。M1 要求走 ORM，迁移脚本里用 `op.add_column` 和 `op.create_index`。迁移写好了 @DBA 审查，然后先跑 staging。」

---

## 关键指标汇总

| Round | 触发方式 | Selector 成本 | Memory 成本 | 选中的 Agent | 注入记忆数 |
|:---:|------|:---:|:---:|------|:---:|
| 1 | 「大家怎么看」| 0ms（Layer 1.5） | 3 × (DB+LLM) ≈ 600ms 串行 | 后端专家 + DBA + 测试专家 | 3/3/4 |
| 2 | 「索引」关键词 | 0ms（Layer 2） | DB+LLM ≈ 200ms | DBA | 3 |
| 3a | 前端手动 | 无 | 无 | 无 | — |
| 3b | @后端专家 | 0ms（Layer 1） | DB+LLM ≈ 200ms | 后端专家 | 4 |

**关键观察**：

1. **Selector 多数轮次零 LLM** — 3 轮中只有 Round 1 broadcast 场景涉及串行多人；Round 2/3b 都是 Layer 1/2 命中，无需 LLM
2. **Pinned 记忆持续生效** — M1/M3/M5 每轮都注入，形成了 Agent 行为的「基线约束」
3. **群记忆自动共享** — M7 由用户添加后，后续 Agent 被激活时自动可见
4. **Agent 私有记忆不泄露** — M4（DBA 的 Redis 配置）和 M6（测试专家的 Pytest 配置）仅在各自 Agent 激活时可见，互不可见
5. **记忆驱动行为** — 每个 Agent 的回复都明确引用了注入记忆中的规范（M1 ORM、M3 迁移、M5 真实 DB），证明检索命中有效

---

## 潜在问题

| 问题 | 严重度 | 缓解 |
|------|:---:|------|
| Round 1 broadcast 时 3 个 Agent 串行各做一次 Memory LLM ≈ 600ms | 中 | 当前串行是 DiscussionOrchestrator 的 loop，不是记忆系统的锅。如果用策略 B（预计算）可降到 300ms |
| pinned 记忆过多 → 扩容候选集 | 低 | 前端限制 pinned ≤10 条。超过 5 条 pinned 时不调 LLM，全量注入 |
| M5（3 天前）和 M1（今天）同是 pinned，但 M5 已经 3 天 → 可能过时 | 低 | `<agenthub-reminder>` 已注入 ⚠️ 警告，Agent 被提示「3 天前，可能已过时」 |
