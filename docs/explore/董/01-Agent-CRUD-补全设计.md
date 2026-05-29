# Agent CRUD 补全设计（2.2）

> 任务: task_assignment_v3.md #2.2 | 工时: 5h | M2 阶段
> 分支: feature/domain2/agent-crud

## 一、现状分析

### 已完成
- Agent 基础 CRUD: POST/GET/PATCH/DELETE `/api/agents`
- `is_deleted` 字段 + `soft_delete` 仓储方法（`get_by_id` 已过滤已删除）
- `settings` JSON 字段已存在 DB 和实体层，但未在 `AgentOut` 暴露
- 前端 `agentsApi` + `agentStore` 基础骨架

### 待补充
1. **详情查询增强** — 当前 `GET /{agent_id}` 只返回 Agent 基本信息，缺少关联数据
2. **软删除级联** — 当前 `soft_delete` 只标记 `is_deleted=True`，未处理关联数据
3. **settings 暴露** — DB/实体层已有，Schema 层缺失

## 二、设计方案

### 2.1 Agent 详情查询增强

PRD §2.1.3 要求 Agent 详情页 6 Tab。其中「任务」「活动」需要关联查询。

#### 方案：新增子资源端点

```
GET /api/agents/{agent_id}        → AgentOut（基本信息，不变）
GET /api/agents/{agent_id}/tasks  → 该 Agent 作为 assignee 的任务列表
GET /api/agents/{agent_id}/activity → 该 Agent 相关的 task_events 时间线
```

**不在 GET /{agent_id} 中内联关联数据**，理由：
- tasks/activities 可能很多，内联导致响应膨胀
- 前端 Tab 按需加载，独立请求更灵活
- 保持 GET /{agent_id} 轻量，不影响列表页性能

#### GET /{agent_id}/tasks

```
查询条件: tasks.assignee_id = agent_id AND tasks.assignee_type = 'agent'
排序: created_at DESC
分页: offset/limit（可选，默认全量）
响应: list[TaskOut]
```

#### GET /{agent_id}/activity

```
查询条件: task_events.actor = f"agent:{agent_id}"
排序: created_at DESC
分页: offset/limit（可选，默认 limit=50）
响应: list[TaskEventOut]
```

### 2.2 AgentOut 扩展

追加 `settings` 字段：

```python
class AgentOut(BaseModel):
    # ... 现有字段保持不变 ...
    settings: dict          # 新增：Agent 自定义配置（仅 get 返回，create/update 不接受）
    updated_at: datetime    # 新增：更新时间
```

### 2.3 软删除级联

当前删除链路：`Router.delete` → `AgentService.delete` → `AgentRepository.soft_delete`

增强后：

```
AgentService.delete()
  1. 获取 agent（已有）
  2. await repo.soft_delete(agent_id)       # 标记 is_deleted
  3. await repo.clear_group_memberships(agent_id)  # 清除群组成员关系
  4. await bus.publish(AgentDeleted(...))    # 发布事件（已有）
```

**级联清除策略**（6 表架构下）：
- `sessions` 表：agent 被删除后，其私聊 session 保留但 agent 不可用（历史记录可读）
- `tasks` 表：已分配的任务不自动取消，assignee 保留（历史审计）
- 当前无 `groups`/`group_members` 表，此步先做占位，待域 2 建群模块（2.5）时补全
- **M2 阶段降级**：仅标记删除 + 发布事件，级联在 2.5 群组管理时统一处理

### 2.4 新增 Schema

```python
class TaskOut(BaseModel):
    id: UUID
    title: str
    status: str
    priority: str
    due_date: datetime | None
    tags: list[str]
    created_at: datetime

class TaskEventOut(BaseModel):
    id: UUID
    task_id: UUID
    event_type: str
    event_data: dict
    actor: str
    created_at: datetime
```

## 三、变更清单

| 层 | 文件 | 变更 |
|----|------|------|
| L4 API | `routers/agents.py` | 新增 `GET /{agent_id}/tasks`、`GET /{agent_id}/activity` |
| L4 Schema | `schemas/agent.py` | `AgentOut` 追加 `settings`、`updated_at`；新增 `TaskOut`、`TaskEventOut` |
| L3 Service | `services/agent_service.py` | 新增 `get_tasks()`、`get_activity()` 方法 |
| L2 Repository | `agent_repository.py` | 新增 `get_tasks_by_agent()`、`get_events_by_agent()` 抽象方法 |
| L1 Impl | `infrastructure/repositories/agent_repository.py` | 实现上述方法（JOIN tasks/task_events 表） |
| L5 Frontend | `types/index.ts` | `Agent` 类型追加 `settings`、`updated_at` |
| L5 Frontend | `api/agents.ts` | 新增 `getTasks()`、`getActivity()` 调用 |
| DI | `api/deps.py` | 检查 AgentService 是否需要注入 TaskRepository |

## 四、场景推理模拟 — 全链路数据流

以下用两个核心场景，从前端用户操作逐层推导到数据库查询，验证设计闭环。

### 场景 A：用户查看 Agent 详情页，切换到「任务」Tab

```
用户操作
  │
  ▼
┌─ L5 Presentation ─────────────────────────────────────────────┐
│ AgentDetailPage.tsx                                           │
│   1. 路由 /agents/:id 进入详情页                               │
│   2. useEffect → agentsApi.get(id) → 渲染「概览」Tab           │
│   3. 用户点击「任务」Tab                                       │
│   4. useEffect → agentsApi.getTasks(id)                       │
│        GET /api/agents/{id}/tasks                             │
│   5. 收到响应 → setTasks(data) → 渲染 TaskList                │
└───────────────────────────────────────────────────────────────┘
  │
  │  HTTP GET /api/agents/{agent_id}/tasks
  ▼
┌─ L4 API ─────────────────────────────────────────────────────┐
│ routers/agents.py                                             │
│   @router.get("/{agent_id}/tasks", response_model=list[TaskOut])
│   async def get_agent_tasks(agent_id: UUID, svc: ServiceDep): │
│       return await svc.get_tasks(agent_id)                    │
│                                                               │
│   FastAPI 自动:                                               │
│     - 路径参数校验 (UUID)                                     │
│     - 依赖注入 AgentService                                   │
│     - 响应序列化 Pydantic → JSON                              │
│     - OpenAPI schema 生成                                     │
└───────────────────────────────────────────────────────────────┘
  │
  │  svc.get_tasks(agent_id)
  ▼
┌─ L3 Application ─────────────────────────────────────────────┐
│ services/agent_service.py                                     │
│   async def get_tasks(self, agent_id: UUID) -> list[TaskResponse]:
│       # 1. 校验 agent 存在（不存在抛 NotFoundError）          │
│       agent = await self._repo.get_by_id(agent_id)            │
│       if agent is None:                                       │
│           raise NotFoundError(...)                             │
│                                                               │
│       # 2. 委托仓储查询关联任务                                │
│       tasks = await self._repo.get_tasks_by_agent(agent_id)   │
│                                                               │
│       # 3. Domain Entity → DTO（解耦，不泄露内部字段）        │
│       return [TaskResponse.from_domain(t) for t in tasks]     │
│                                                               │
│   【关键决策】AgentService 需要注入 TaskRepository              │
│   当前构造函数只接受 AgentRepository + EventBus。              │
│   方案：追加 task_repo 参数（符合"服务编排多仓储"模式）        │
└───────────────────────────────────────────────────────────────┘
  │
  │  repo.get_by_id(agent_id)  ──── 验证 agent 存在
  │  repo.get_tasks_by_agent()  ── 查关联任务
  ▼
┌─ L2 Domain (接口) ───────────────────────────────────────────┐
│ repositories/agent_repository.py (抽象)                       │
│   @abstractmethod                                             │
│   async def get_tasks_by_agent(self, agent_id: UUID)          │
│       -> list[Task]: ...                                      │
│                                                               │
│   【归档理由】放在 AgentRepository 而非 TaskRepository         │
│   因为查询语义是"Agent 聚合根的任务"，属于 Agent 聚合边界内。  │
│   跨聚合查询在 L3 Service 层编排。                             │
└───────────────────────────────────────────────────────────────┘
  │
  │  依赖注入: PostgresAgentRepository(sqlalchemy_session)
  ▼
┌─ L1 Infrastructure ──────────────────────────────────────────┐
│ repositories/agent_repository.py (实现)                       │
│   async def get_tasks_by_agent(self, agent_id: UUID):         │
│       stmt = (                                                │
│           select(TaskModel)                                   │
│           .where(                                             │
│               TaskModel.assignee_id == agent_id,               │
│               TaskModel.assignee_type == "agent"               │
│           )                                                   │
│           .order_by(TaskModel.created_at.desc())              │
│       )                                                       │
│       result = await self._s.execute(stmt)                    │
│       return [_task_to_domain(m) for m in result.scalars()]   │
│                                                               │
│   生成 SQL:                                                   │
│   SELECT * FROM tasks                                         │
│   WHERE assignee_id = $1                                      │
│     AND assignee_type = 'agent'                               │
│   ORDER BY created_at DESC;                                   │
└───────────────────────────────────────────────────────────────┘
  │
  │  asyncpg → PostgreSQL
  ▼
┌─ Database ───────────────────────────────────────────────────┐
│ tasks 表                                                      │
│ ┌────┬──────────┬─────────────┬───────────────┬────────┐     │
│ │ id │ title    │ assignee_id │ assignee_type │ status │     │
│ ├────┼──────────┼─────────────┼───────────────┼────────┤     │
│ │ u1 │ "写API"  │ <agent_id>  │ "agent"       │ active │     │
│ │ u2 │ "修复BUG"│ <agent_id>  │ "agent"       │ done   │     │
│ │ u3 │ "部署"   │ <other_id>  │ "human"       │ pending│     │
│ └────┴──────────┴─────────────┴───────────────┴────────┘     │
│                                                               │
│ 返回: [u1, u2] 两条记录                                       │
└───────────────────────────────────────────────────────────────┘
```

**响应返回路径（逆向）**：DB rows → TaskModel → Task 实体 → TaskResponse DTO → Pydantic 序列化 → JSON → HTTP Response → React state → UI 渲染

---

### 场景 B：删除 Agent（软删除 + 级联清理）

```
用户操作
  │
  ▼
┌─ L5 Presentation ─────────────────────────────────────────────┐
│ AgentDetailPage.tsx / AgentListPage.tsx                       │
│   1. 用户点击「删除」按钮                                      │
│   2. 弹出确认对话框: "确定删除 Agent xxx？关联任务不会受影响"  │
│   3. 用户确认 → agentsApi.remove(id)                          │
│        DELETE /api/agents/{id}                                │
│   4. 收到 204 → 从列表中移除 → 跳转回列表页                   │
│   5. 收到 4xx/5xx → toast 错误提示                            │
└───────────────────────────────────────────────────────────────┘
  │
  │  HTTP DELETE /api/agents/{agent_id}
  ▼
┌─ L4 API ─────────────────────────────────────────────────────┐
│ routers/agents.py                                             │
│   @router.delete("/{agent_id}", status_code=204)              │
│   async def delete_agent(agent_id: UUID, svc: ServiceDep):    │
│       await svc.delete(DeleteAgentCommand(agent_id=agent_id)) │
│       return Response(status_code=204)                        │
└───────────────────────────────────────────────────────────────┘
  │
  │  svc.delete(command)
  ▼
┌─ L3 Application ─────────────────────────────────────────────┐
│ services/agent_service.py                                     │
│   async def delete(self, cmd: DeleteAgentCommand):            │
│       # Step 1: 获取 agent（不存在则 404）                    │
│       agent = await self._repo.get_by_id(cmd.agent_id)        │
│       if agent is None:                                       │
│           raise NotFoundError(...)                             │
│                                                               │
│       # Step 2: 软删除（is_deleted = True）                   │
│       await self._repo.soft_delete(cmd.agent_id)              │
│                                                               │
│       # Step 3: 清除群组成员关系 [M3 补全]                    │
│       await self._repo.clear_group_memberships(cmd.agent_id)  │
│                                                               │
│       # Step 4: 发布领域事件（触发通知/日志等副作用）         │
│       await self._bus.publish(                                │
│           AgentDeleted(agent_id=cmd.agent_id)                 │
│       )                                                       │
│                                                               │
│   【事件驱动副作用】                                           │
│   AgentDeleted → 订阅者:                                      │
│     - NotificationHandler: 通知相关用户                       │
│     - SessionHandler: 归档相关 session                        │
│     - (未来) 清理 Redis 缓存                                  │
└───────────────────────────────────────────────────────────────┘
  │
  │  repo.soft_delete()  ────── 标记删除
  │  repo.clear_group_...()  ── 级联清理
  ▼
┌─ L1 Infrastructure ──────────────────────────────────────────┐
│ repositories/agent_repository.py                              │
│                                                               │
│   async def soft_delete(self, agent_id: UUID):                │
│       m = await self._s.get(AgentModel, agent_id)             │
│       if m is not None:                                       │
│           m.is_deleted = True                                 │
│           await self._s.flush()                               │
│                                                               │
│   async def clear_group_memberships(self, agent_id: UUID):    │
│       """M2 占位 — M3 群组模块补全"""                         │
│       # 标记 agent 相关的 group session 为 archived           │
│       stmt = (                                                │
│           update(SessionModel)                                │
│           .where(                                             │
│               SessionModel.type == "group",                   │
│               SessionModel.agent_id == agent_id               │
│           )                                                   │
│           .values(status="archived")                          │
│       )                                                       │
│       await self._s.execute(stmt)                             │
│                                                               │
│   生成 SQL:                                                   │
│   UPDATE agents SET is_deleted = true WHERE id = $1;          │
│   UPDATE sessions SET status = 'archived'                     │
│     WHERE type = 'group' AND agent_id = $1;                   │
└───────────────────────────────────────────────────────────────┘
  │
  │  asyncpg → PostgreSQL
  ▼
┌─ Database ───────────────────────────────────────────────────┐
│ 事务边界: 所有操作在同一 AsyncSession 内，自动回滚             │
│                                                               │
│ agents:  [id=X, is_deleted=true]  ← 已标记，列表查询不可见   │
│ sessions: [status='archived']     ← 不再出现在活跃会话        │
│ tasks:   [assignee_id=X]          ← 保持不变（审计追溯）     │
└───────────────────────────────────────────────────────────────┘
```

**关键设计决策**：
- 软删除不物理删除数据，保留审计追溯能力
- `tasks` 表不级联修改 — 已完成任务属于历史事实，不应因 Agent 删除而消失
- `sessions` 归档而非删除 — 聊天记录可读但不可继续对话
- 事件发布解耦副作用 — 通知、缓存失效等通过 EventBus 异步处理

---

### 全链路调用栈对比

```
场景 A: 查看任务                     场景 B: 删除 Agent
─────────────────────              ─────────────────────
L5: agentsApi.getTasks(id)         L5: agentsApi.remove(id)
        │                                  │
L4: GET /{id}/tasks                 L4: DELETE /{id}
        │                                  │
L3: svc.get_tasks()                 L3: svc.delete()
        │                                  │
L2: repo.get_tasks_by_agent()       L2: repo.soft_delete()
        │                            + repo.clear_group_...()
L1: SELECT ... FROM tasks           L1: UPDATE agents SET...
     WHERE assignee_id = $1              UPDATE sessions SET...
        │                                  │
DB: tasks 表                        DB: agents/sessions 表
```

---

## 五、边界条件检查

参考 `spec/boundaries_边界矩阵.md`，自行补充以下边界：

| 边界条件 | 处理方式 |
|----------|---------|
| agent_id 不存在 | L3 先 `get_by_id` 校验，返回 `404 NotFoundError` |
| agent 已被软删除 | `get_by_id` 过滤 `is_deleted=True`，返回 None → 404 |
| agent 无关联任务 | 返回空列表 `[]`，不是 404 |
| agent 无活动记录 | 返回空列表 `[]`，不是 404 |
| 并发删除同一 agent | PostgreSQL 行级锁保证串行化，第二次 `get_by_id` 返回 None → 404 |
| 删除时 agent 正在执行任务 | 任务不中断，assignee 保留；通知任务发起者 Agent 已不可用 |
| settings 为空 | 返回 `{}`（默认空 dict），不抛异常 |

## 六、不在此次范围

- Agent 详情页 6 Tab 前端 UI（属于 2.3，后续任务）
- 对话式创建 Agent（属于 2.4）
- 群组管理 + 级联出群完整实现（属于 2.5，M3）
- 记忆 Tab 数据（L2/L4，属于域3）
