# Coordinator v3 步 2 — 多轮讨论回归 + SessionState 升级 + 执行态路由收口

> 日期：2026-06-08 | 状态：方案设计（SPEC v2，取代 2026-06-07 版）
> 依据：[[coordinator-architecture-overview]]
> 前序：步 1 已完成 90%（1c-core 前门重写，1c-exec 未做）
> 配套简化：步 3 的 `ask` tool + PAUSED 态 + resume 机制删除 → 步 2.5

---

## 0. 设计简化（前置声明）

本步涉及以下架构简化，已在 [[coordinator-architecture-overview]] 中确认：

1. **任务状态只有两种**：DONE（COMPLETED）和 NOT DONE（其他所有）。删除 PAUSED 态
2. **Worker 提问走正常文本流**：删除 `ask` tool。worker 问「用 Markdown 还是 CMS？」→ 文本直接推群聊，跟 respond 路径一样
3. **没有 `_feed_event` / `_waiting_node_key` / 显式 resume**：Planner 从 transcript 自然看到 worker 在等回复，判 `feed` 时重新 spawn worker（`--resume` 恢复上下文）
4. **PlanView 不需要 `waiting` 列表**：who's waiting 是 transcript 的事，不是 DAG 投影的事

**步 2 不负责实现上述简化**——那是步 2.5（删 ask/PAUSED/resume）。步 2 只保证**架构上不再依赖**这些概念。`feed` 的语义从「唤醒 PAUSED step」改为「重新派发该 step 的 worker」。

---

## 1. 实际交付范围

### 1.1 一句话

**步 2 做三件事：① 多轮讨论回归（strip → 反复 decide）、② SessionState 从手工构造升级为 `from_session` 工厂、③ 收口步 1 的 1c-exec（执行态消息走 decide，不再简化 feed）。删 DiscussionOrchestrator 循环 + Selector L2 keyword。**

### 1.2 不是什么

- **不是「统一两个循环」**。Orchestrator.run（任务执行 Harness）一行不改
- **不做 replan**（步 4）
- **不删 ask/PAUSED/resume**（步 2.5）。步 2 只确保 `feed` 语义不再依赖 PAUSED

### 1.3 当前代码基线

| 组件 | 文件 | 状态 |
|------|------|------|
| `ReactiveRouter.decide` | `reactive_router.py` | ✅ 完整实现 |
| `SessionState`/`PlanView`/`StepView` | `session_state.py` | ✅ DTO 已定义，手工构造 |
| `_handle_group` 前门 | `chat_service.py` | ✅ 1c-core 完成 |
| 执行态路由 | `chat_service.py:188-201` | ❌ 1c-exec 未做 |
| `CoordinatorGate` | — | ✅ 已删 |
| `Selector`（含 L2 keyword） | `selector.py` | ❌ 残留 17.7KB |
| `DiscussionOrchestrator` | `discussion_orchestrator.py` | ❌ 残留 12KB，三处 wiring |
| `CoordinatorRun.plan_view` | `coordinator_run.py` | ❌ 不存在 |
| `SessionState.from_session` | `session_state.py` | ❌ 不存在 |

---

## 2. 目标：统一路由

### 2.1 一扇门，一条路

不管群里有任务在跑还是纯聊天，所有消息走同一段代码：

```
用户消息 → ChatService._handle_group
  │
  ├─ @mention → _stream_one_agent（零 LLM）
  ├─ is_control → cancel / 忽略（零 LLM）
  ├─ is_broadcast → multi 全员（零 LLM）
  │
  └─ state = SessionState.from_session(session_id, members, message_repo, run)
     decision = Planner.decide(state)
     dispatch(decision)

     respond/multi → _stream_one_agent → continue（多轮）
     task          → Planner.plan + Orchestrator.run
     feed          → 重新派发该 step 的 worker
     done          → 静默
```

**`active_plan` 不是 mode 枚举，是 Planner 的输入字段**。跟 `transcript` 一样——有就有，没有就没有，Planner 自己看着办。ChatService 不区分。

### 2.2 与现状的差别

| | 步1(现状) | 步2 后 |
|---|---|---|
| 纯对话态 respond 后 | `return`（strip） | `continue`（多轮） |
| 执行态路由 | `if run is not None: ... return` | `SessionState.from_session → decide → dispatch` |
| SessionState 构造 | 手工 `SessionState(...)` | `SessionState.from_session(...)` |
| active_plan | 永远是 None | 非 None 时含真实 DAG 投影 |

---

## 3. SessionState v2

### 3.1 `from_session` 工厂

```python
@classmethod
async def from_session(
    cls,
    *,
    session_id: UUID,
    members: tuple[Agent, ...],
    message_repo: MessageRepository,
    run: CoordinatorRun | None,
) -> SessionState:
    recent = await message_repo.list_by_session(session_id, limit=15)
    transcript = tuple(reversed(recent))
    plan = run.plan_view() if run is not None else None
    return cls(
        session_id=session_id,
        members=members,
        transcript=transcript,
        active_plan=plan,
    )
```

### 3.2 `CoordinatorRun.plan_view()`

```python
def plan_view(self) -> PlanView | None:
    if self._orchestrator is None or self._orchestrator.graph is None:
        return None
    g = self._orchestrator.graph
    steps = tuple(
        StepView(step_id=n.task.id, worker=n.task.suggested_worker, status=n.status.value)
        for n in g.nodes.values()
    )
    return PlanView(steps=steps)
```

**不需要 `waiting` 列表**。谁在等答案——从 transcript 自然看到。DAG 投影只管 DAG 节点的客观状态。

### 3.3 DTO 不变

`SessionState`/`PlanView`/`StepView` 的字段签名不变。`PlanView.waiting` 字段保留但不填充（步 2.5 删除该字段）。

---

## 4. 多轮讨论回归

```python
max_rounds = settings.max_discussion_rounds  # 默认 5
already_responded: set[str] = set()

for round_idx in range(max_rounds):
    state = await SessionState.from_session(
        session_id=session.id, members=tuple(members),
        message_repo=self._messages, run=None,
    )
    decision = await self._router.decide(state)

    if decision.action in ("respond", "multi"):
        targets = [m for m in members
                   if m.name in decision.who and m.name not in already_responded]
        if not targets:
            continue
        for target in targets:
            async for evt in self._stream_one_agent(
                session=session, group=group, target=target, trigger=trigger
            ):
                yield evt
            already_responded.add(target.name)
        if round_idx == max_rounds - 1:
            break
        continue  # ← 回完继续，下一轮 decide

    if decision.action == "task":
        await self._start_coordinator(session, group, trigger)
        return

    # done / 其他 → 退出
    break
```

防循环：`already_responded: set[str]` + `max_rounds` 硬上限 + LLM 判 done。

---

## 5. 执行态路由收口（1c-exec）

### 5.1 旧 → 新

**旧**（`chat_service.py:188-201`）：

```python
if run is not None:
    if self._is_control(text):
        await self._cancel_coordinator(session, run)
    elif run.has_waiting_step():
        run.feed(text)
    else:
        run.enqueue_note(text)
    return
```

**新**：

```python
if run is not None:
    if self._is_control(text):
        await self._cancel_coordinator(session, run)
        return

    state = await SessionState.from_session(
        session_id=session.id, members=tuple(members),
        message_repo=self._messages, run=run,
    )
    decision = await self._router.decide(state)

    match decision.action:
        case "feed":
            # 重新派发 worker（从 transcript 自然看到谁在等答案）
            if decision.feed_step:
                run.feed(decision.feed_step, text)
            else:
                run.enqueue_note(text)
        case "respond" | "multi":
            targets = [m for m in members if m.name in decision.who]
            async for evt in self._respond(session, group, trigger, targets):
                yield evt
        case "note":
            if decision.who:
                for worker in decision.who:
                    run.enqueue_note(text, worker=worker)
            else:
                run.enqueue_note(text)
        case "done":
            pass
        case _:
            run.enqueue_note(text)
    return
```

### 5.2 行为变化

| 消息类型 | 旧行为 | 新行为 |
|---------|--------|--------|
| control | cancel | cancel（不变） |
| 回答 worker 的问题 | `has_waiting_step → 盲 feed` | `decide → feed(step)`。Planner 从 transcript 判断这条消息在回应谁 |
| 指定 worker 的补充 | `enqueue_note`（盲投） | `decide → note(who=("前端",))` → 入该 worker 的队列 |
| 闲聊/问进度 | `enqueue_note`（石沉大海） | `decide → respond` → **即时回复** |
| 通用补充 | `enqueue_note` | `decide → note(who=())` → 全局投递 |

**`enqueue_note` 仍是兜底**：任何 decide 无法处理的消息不进黑洞。

### 5.3 旁路消息按 worker 路由

`_pending_notes` 从 `list` 改为 `dict[str, list[str]]`（key = worker 名或 `"*"`）：

```python
# 入队
enqueue_note(text, worker="前端小美") → _pending_notes["前端小美"]
enqueue_note(text, worker=None)       → _pending_notes["*"]

# 消费（dispatch 时 pop）
node.pending_notes = (
    _pending_notes.pop("前端小美", [])
    + _pending_notes.get("*", [])
)
```

### 5.4 feed 的语义

`feed(step_id, answer)` 的语义从「唤醒 PAUSED step」改为「重新派发该 step 的 worker」。

Worker 上次流结束但没调 `task_complete`（可能问了问题等回复）→ Planner 从 transcript 判断这条消息是回复 → `feed` → Orchestrator 重新 `executor.run(node)`（`--resume` 恢复上下文，注入用户回答）。

步 2 不负责改 Orchestrator 内部实现（那是步 2.5）。只保证 ChatService 层的 `feed` 调用语义正确。

---

## 6. 清理

### 6.1 删除 DiscussionOrchestrator 循环

整文件 `discussion_orchestrator.py` 删除。三处 wiring（`chat_service.py`/`deps.py`/`ws/chat.py`）去除 import + 构造。

### 6.2 删除 Selector L2 keyword

`selector.py:172` `_resolve_keyword` + `pick()` 中对其的调用。

### 6.3 删除顺序

```
1. 写 chat_service.py 新循环（步 2b）
2. 验证测试通过
3. 删 DiscussionOrchestrator import + __init__ 参
4. 删 deps.py / ws/chat.py 的 DiscussionOrchestrator 构造
5. 跑 wiring 测试
6. 删 discussion_orchestrator.py + test_discussion_orchestrator.py
7. 删 Selector._resolve_keyword
```

---

## 7. 实现分步（TDD）

### 步 2a：`CoordinatorRun.plan_view()` + `SessionState.from_session`（~1.5h）

- `coordinator_run.py`：`plan_view() → PlanView | None`
- `session_state.py`：`from_session()` classmethod
- `PlanView` 不含 `waiting`

### 步 2b：多轮讨论回归（~2h）

- `chat_service.py` 纯对话态 `for` 循环 + `already_responded`

### 步 2c：执行态路由收口 + 旁路消息按 worker 路由（~2h）

- `chat_service.py` 执行态分支 → `from_session → decide → dispatch`
- `reactive_router.py` → `_build_prompts` + `_parse_payload` + tool schema 加 `note` action
- `coordinator_run.py` → `enqueue_note(text, worker=None)` 签名变更
- `orchestrator.py` → `_pending_notes: dict[str, list[str]]` + 按 worker pop

### 步 2d：删 DiscussionOrchestrator + Selector L2（~1h）

---

## 8. 文件改动总览

```
改动:
  session_state.py       # +from_session()
  coordinator_run.py     # +plan_view()；enqueue_note 签名变更
  chat_service.py        # 多轮 for 循环 + 执行态 decide 路由 + note dispatch + 去 DiscussionOrchestrator 注入
  reactive_router.py     # +note action（tool schema + prompt + parse）
  orchestrator.py        # _pending_notes: list → dict[str, list[str]]
  selector.py            # 删 _resolve_keyword
  deps.py / ws/chat.py   # 去 DiscussionOrchestrator

新建:
  tests/test_session_state.py

删除:
  discussion_orchestrator.py
  test_discussion_orchestrator.py

不改:
  session_state.py DTO 字段
  executor.py（步 2.5 再动：删 ask 检测 + worker 文本推群聊）
  orchestrator.py 主循环（步 2.5 再动：删 PAUSED/_feed_event/resume）
  dag.py / scheduler.py / fsm.py
  mcp_step_tools.py（步 2.5 再动：删 ask tool）
  ports.py
```

---

## 9. 风险清单

| 风险 | 缓解 |
|------|------|
| 多轮 decide 成本 | 廉价模型 + 近窗口 15 条 + max_rounds 硬上限 |
| decide 不收敛 | max_rounds + already_responded 防重 + 用户随时 @ 打断 |
| 执行态 decide 判错 action | prompt 强调从 transcript 匹配对话连续性；降级入队不丢消息 |
| DiscussionOrchestrator 删除后 wiring 断裂 | 按 §6.3 顺序逐步删，diff 验证 |

---

## 10. 与前后步的衔接

- **依赖步 1**：`ReactiveRouter.decide`、`SessionState` DTO、`_respond`/`_stream_one_agent`
- **为步 4 铺路**：`plan_view()` + 执行态 `decide` 调用 → 步 4 加 `replan` action 只改 decide，路由层不动
- **步 2.5 后继**：删除 `ask` tool + PAUSED 态 + resume 机制；executor 改 worker 文本推群聊
