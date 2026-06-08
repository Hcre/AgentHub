# R2 实现规格 — 路由统一：执行态走 decide，删 `if run is not None` 分支

> 日期：2026-06-08 | 状态：实现规格 | 关联：[[coordinator-design-v4]] §3/§4/§7
> 前提：R0+R1 已完成（事件驱动 + 协议重塑）
> 风险：**中**（改路由但不碰控制流；R0 的 Orchestrator 不变）

---

## 0. 目标

删掉 `_handle_group` 里的 `if run is not None` 特殊分支——执行态消息和纯聊天消息走同一段 `decide → dispatch`。SessionState 从「手工构造 `active_plan=None`」升级为「`from_session` 工厂读取真实的 DAG 投影」，Planner 自然看到有任务在跑、谁在等回复，据此出 `feed`/`note`/`respond`。

一句话验收：**任务执行中用户说「做得怎么样了」，消息不再被 `if run is not None` 拦截成 `try_feed` 盲喂，而是进 decide → Planner 看到 transcript + active_plan → 判 respond(后端阿强) → 后端阿强即时回复进度。控制消息（取消）仍在 decide 之前零 LLM 反射处理。**

---

## 1. 现状（要替换的东西）

### 1.1 chat_service.py — 执行态特殊分支（删）

```python
# _handle_group line 186-199
run = self._registry.get(session.id)

if run is not None:
    # 执行态特殊分支：blind feed / enqueue_note / control
    if self._is_control(text):
        await self._cancel_coordinator(session, run)
    else:
        fed = await run.try_feed(text)       # ← 盲喂：不看内容，找 park 节点就喂
        if fed:
            logger.info("feed 续跑 park 节点 session=%s", session.id)
        else:
            run.enqueue_note(text)            # ← 没 park 节点就当旁路消息
    return                                    # ← 执行态下直接返回，不进 decide
```

三个问题：

1. **`try_feed` 盲喂**：不判断消息内容是不是真的在回答 worker，只要 `parked_step_id` 非空就喂。用户说「做得怎么样了」也会被当成 feed 喂给 worker——这显然是错的，这是一句进度询问，应该由 Planner 判断是 respond。

2. **执行态下聊天死**：`try_feed` 失配（无 park 节点）时消息入 `_pending_notes`，但 `_pending_notes` 是 flat list，所有 worker 共享——「注意前端用 React」会同时注入给后端阿强的下次派发。

3. **`_pending_notes` 不分桶**：`list[str]`，一个 worker 的补充会被所有 worker 看到。R2 改为 `dict[str, list[str]]`，按 worker 名分桶。

### 1.2 SessionState — 手工构造 active_plan=None（改）

```python
# chat_service.py line 215-221
state = SessionState(
    session_id=session.id,
    members=tuple(members),
    transcript=tuple(await self._recent_history(session)),
    active_plan=None,                         # ← 永远是 None，不管有没有任务在跑
)
```

`SessionState` 类和 `PlanView` 类已定义（session_state.py），但没有 `from_session` 工厂方法，`PlanView` 也没有构造来源——`CoordinatorRun` 没有 `plan_view()` 方法。

### 1.3 PlanView.waiting — v3 残留（删）

```python
# session_state.py line 34
waiting: tuple[str, ...] = ()
```

v4 design §3 明确：**没有 `waiting` 字段**。谁在等答案——Planner 从 transcript 自然看到。这是对话连续性问题，不是 DAG 投影问题。R2 删此字段。

### 1.4 ReactiveRouter — feed 依赖 waiting（改）

```python
# reactive_router.py line 106-112
if action == "feed":
    step = payload.get("feed_step")
    answer = payload.get("answer")
    waiting = state.active_plan.waiting if state.active_plan else ()
    if not step or step not in waiting or not answer:       # ← 依赖 waiting 校验
        ...
```

`waiting` 删除后，feed step 的有效性校验改为从 `PlanView.steps` 中找 `not_done`（RUNNING 状态）节点。

### 1.5 受影响文件一览

| 文件 | 现状 | 目标 |
|------|------|------|
| `session_state.py` | PlanView 有 `waiting` 字段；无 `from_session` 工厂 | 删 `waiting`；加 `from_session()` |
| `chat_service.py` | `if run is not None` 特殊分支；`active_plan=None` 固定；`_pending_notes` 引用 | 删特殊分支；`SessionState.from_session()` 构造；`_pending_notes` 改按 worker 分桶（CoordinatorRun) |
| `coordinator_run.py` | `_pending_notes: list[str]`；无 `plan_view()` | `_pending_notes: dict[str, list[str]]`；加 `plan_view()` |
| `reactive_router.py` | feed 校验依赖 `waiting` | 改为从 `PlanView.steps` 找 not_done 节点 |

---

## 2. 目标态

### 2.1 SessionState.from_session() — 工厂方法

```python
# session_state.py
@classmethod
async def from_session(
    cls,
    *,
    session_id: UUID,
    members: tuple[Agent, ...],
    message_repo: MessageRepository,
    run: CoordinatorRun | None = None,
) -> SessionState:
    """从消息流 + 任务流构造只读投影。"""
    recent = await message_repo.list_by_session(session_id, limit=settings.l1_window_size)
    transcript = tuple(reversed(recent))
    active_plan = run.plan_view() if run else None
    return cls(
        session_id=session_id,
        members=members,
        transcript=transcript,
        active_plan=active_plan,
    )
```

### 2.2 PlanView — 删 waiting

```python
@dataclass(frozen=True)
class PlanView:
    """active_plan 非空时的 DAG 只读投影。"""
    steps: tuple[StepView, ...] = ()
    # v4: 无 waiting 字段。not_done 节点从 steps 中筛选 status=="running" 即可得到——
    # waiting = {s.step_id for s in steps if s.status == "running"}，保留 waiting 是数据冗余。
```

**为什么删 `waiting`**：`waiting` 和 `filter(steps, status=="running")` 是同一集合——R1 删 PAUSED 后 not_done 节点停在 RUNNING，两者计算等价。保留 waiting 等于在两个字段里表达同一个事实——冗余。且 §2.6 的 prompt 已经逐条展示所有 steps 的状态，Planner 能看到 RUNNING 节点，不需要 `waiting` 再列一遍。删除理由不是「Planner 能从 transcript 推断谁在等答案」，而是「信息已经在 steps 里了」。

### 2.3 CoordinatorRun.plan_view() — DAG 投影

```python
# coordinator_run.py
def plan_view(self) -> PlanView | None:
    """从 Orchestrator 当前 DAG 投影 PlanView。无任务 → None。"""
    if self._orchestrator is None or self._orchestrator.graph is None:
        return None
    steps = tuple(
        StepView(
            step_id=n.task.id,
            worker=n.task.suggested_worker,
            status=n.status.value,
        )
        for n in self._orchestrator.graph.nodes.values()
    )
    return PlanView(steps=steps)
```

纯数据投影，无业务逻辑。不对 Orchestrator 做任何写操作。

### 2.4 _pending_notes 按 worker 分桶

```python
# coordinator_run.py
_pending_notes: dict[str, list[str]] = field(default_factory=dict)
# key = worker 名 或 "*"（全局，所有 worker 的下次派发都注入）

def enqueue_note(self, text: str, worker: str | None = None) -> None:
    """执行期旁路消息入队。worker 指定 → 只投给该 worker；None → 全局。"""
    key = worker or "*"
    self._pending_notes.setdefault(key, []).append(text)
```

消费时（`orchestrator._execute_and_settle`）：

```python
# orchestrator.py _execute_and_settle — 消费 pending_notes
# 注意：_pending_notes 现在是 dict[str, list[str]]，需要按 worker 名取
notes_for_worker = (
    _pending_notes.pop(node.task.suggested_worker, [])   # 消费即删（自己的）
    + _pending_notes.get("*", [])                         # 不删（全局）
)
node.pending_notes = notes_for_worker
```

**为什么全局 `"*"` 用 `get` 不删**：全局 note（如 `enqueue_note("错误提示用中文")`）是跨 step 的约束，应该注入给每一个后续派发的 worker。worker 专用 note（如 `enqueue_note("用 React", worker="前端小美")`）是一次性的——只投给小美，投完就删。如果全局也 pop，只有第一个被派发的 worker 看到，后续 worker 收不到。

`_pending_notes` 仍由 CoordinatorRun 持有，Orchestrator 通过共享引用读取。R2 只改数据结构，R3/R5 的 Planner decide→note action 出 `note(who, text)` 时自然写入对应 worker 的桶。

### 2.5 chat_service.py — 统一路由

`_handle_group` 的核心变更：

```python
# _handle_group — R2 统一路由
async def _handle_group(self, session, group, trigger):
    # @mention 直达（不变）
    targets = await self._resolve_mentions(trigger.mentions, group)
    if targets:
        for target in targets:
            async for evt in self._stream_one_agent(...):
                yield evt
        return

    text = trigger.content or ""
    run = self._registry.get(session.id)

    # 反射② control — 执行态下零 LLM 取消（在 decide 前，不是路由是命令）
    if run is not None and self._is_control(text):
        await self._cancel_coordinator(session, run)
        return

    # 反射③ control — 无 run 时 control 是空操作（不变）
    if run is None and self._is_control(text):
        return

    members = await self._group_members(group)
    is_discussion = group.dispatch_mode == DispatchMode.DISCUSSION

    # 反射④ broadcast — 全体意图，零 LLM（不变）
    if is_discussion and self._is_broadcast(trigger):
        async for evt in self._respond(session, group, trigger, members):
            yield evt
        return

    # ── 统一路由：执行态和纯聊天走同一段 decide → dispatch ──
    state = await SessionState.from_session(
        session_id=session.id,
        members=tuple(members),
        message_repo=self._messages,
        run=run,                                     # ← 不再是 None
    )

    decision = await self._router.decide(state)
    logger.info(
        "decide session=%s action=%s who=%s has_plan=%s reason=%s",
        session.id, decision.action, decision.who,
        state.active_plan is not None, decision.reason,
    )

    if decision.action == "task":
        if state.active_plan is not None:
            # 已在执行态，降级为 note（design v4 §7：task → 降级为 note）
            run.enqueue_note(trigger.content or text)
        else:
            await self._start_coordinator(session, group, trigger)
        return

    if decision.action in ("respond", "multi"):
        if not is_discussion and state.active_plan is None:
            # 纯对话态：AT_ROUTING 群不自动出声，静默
            # 执行态：不受 dispatch_mode 约束——「做得怎么样了」必须即时回复（design v4 §7）
            return
        targets = [m for m in members if m.name in decision.who]
        async for evt in self._respond(session, group, trigger, targets):
            yield evt
        return

    if decision.action == "feed":
        if run is None:
            logger.warning("decide=feed 但无活跃 run，降级 done")
            return
        await run.on_feed(decision.feed_step, decision.answer or text)
        return

    if decision.action == "note":
        if run is None:
            return
        for worker_name in decision.who:
            run.enqueue_note(text, worker=worker_name)
        return

    # done → 静默
```

**关键变更**：

1. **`if run is not None` 特殊分支整个删除**。取而代之的是：
   - `control` 提升为反射②（仍在 decide 前——它是命令，不是路由）
   - `SessionState.from_session(run=run)` → Planner 看到真实的 `active_plan`
   - `decide` 返回 `feed`/`note`/`respond` → dispatch 统一处理

2. **`task` 执行期降级**：`state.active_plan is not None`（已在执行态）时 Planner 误判 `task` → 降级为 `note`，防起第二个并行 Orchestrator（design v4 §7）。

3. **`try_feed` 删除**。R0 过渡胶水——Planner 从 transcript + active_plan 判断用户是不是在回复某个 worker，出 `feed(step)` 带明确的 step_id。不再需要盲找 park 节点。

4. **`enqueue_note` 不再作为兜底**。Planner 明确判 `note(who, text)` 才会入队。闲聊/问进度出 `respond` 即时回复，不会石沉大海。

5. **`_pending_notes` 按 worker 分桶**：`note` action 的 `who` 决定入哪个 worker 的桶。

6. **执行态 `respond` 不受 `dispatch_mode` 约束**：`is_discussion` 检查仅纯对话态生效——执行态下「做得怎么样了」→ respond 必须即时回复，不管群是什么 mode。

### 2.6 ReactiveRouter — feed/note 适配

```python
# reactive_router.py — _parse_payload 变更

if action == "feed":
    step = payload.get("feed_step")
    answer = payload.get("answer")
    # R2: 不再依赖 waiting。从 PlanView.steps 中找 not_done 节点（RUNNING 状态）
    valid_steps = {
        s.step_id for s in (state.active_plan.steps if state.active_plan else ())
        if s.status == "running"
    }
    if not step or step not in valid_steps or not answer:
        logger.warning(
            "ReactiveRouter feed 无效（step=%r valid=%r），降级 done", step, valid_steps
        )
        return PlannerDecision.done("feed: invalid step/answer")
    return PlannerDecision(action="feed", feed_step=step, answer=answer, reason=reason)

if action == "note":
    raw_who = payload.get("who") or []
    if isinstance(raw_who, str):
        raw_who = [raw_who]
    who = tuple(n for n in raw_who if n in member_names)
    if not who:
        # 未指定目标 → 全局 note
        who = ("*",)
    return PlannerDecision(action="note", who=who, reason=reason)
```

`_build_prompts` 执行态部分同步更新——删 `waiting` 引用，改为展示各 step 状态：

```python
if state.active_plan is None:
    mode = (
        "## 当前态：纯对话（无任务在跑）\n"
        "判据：\n"
        "1. 用户要**实际写代码/改文件/跑命令的开发任务** → action=task\n"
        "2. 否则按讨论选人：谁该回 → respond+who；多人 → multi+who；无需回 → done\n"
        "注意：任务文本天然含技术词，别因为出现技术词就当讨论——按是否要动手干判。"
    )
else:
    step_lines = "\n".join(
        f"- {s.step_id}（{s.worker}）：{s.status}"
        for s in state.active_plan.steps
    )
    mode = (
        f"## 当前态：任务执行中\n"
        f"任务状态：\n{step_lines}\n\n"
        "判据：\n"
        "1. 若用户消息明显在回复某个 running step 的 worker 之前的提问 "
        "→ action=feed, feed_step=该 step_id, answer=用户回答原文\n"
        "2. 若用户在问进度/闲聊/旁白 → action=respond, who=最合适的 member\n"
        "3. 若用户在追加约束（「注意前端用 React」）→ action=note, who=受影响的 worker\n"
        "   （不知道谁受影响时 who=[\"*\"] 全局注入）\n"
        "4. 若用户在布置新的开发任务 → action=task\n"
        "5. 不需要回应 → done"
    )
```

### 2.7 PlannerDecision — 加 note action

```python
# reactive_router.py
Action = Literal["respond", "multi", "task", "feed", "note", "done"]
#                                                      ↑ 新增

# PlannerDecision — note 复用 who 字段表示目标 worker
# note 的 who 含义：("前端小美",) → 只入小美的桶；("*",) → 全局
```

tool schema 同步更新——`action` enum 加 `"note"`，`who` description 适配 note 语义。

---

## 3. 代码变动清单

| 文件 | 变 | 不变 |
|------|-----|------|
| `session_state.py` | `PlanView` 删 `waiting` 字段；`SessionState` 加 `from_session()` 工厂 | `StepView`/`PlanView`/`SessionState` 类定义 |
| `chat_service.py` | `_handle_group`：删 `if run is not None` 特殊分支；`SessionState` 构造改用 `from_session()`；加 `feed`/`note` dispatch 分支 | @mention/control/broadcast 前门反射；`_stream_one_agent`；`_start_coordinator` |
| `coordinator_run.py` | `_pending_notes`：`list[str]` → `dict[str, list[str]]`；`enqueue_note` 签名加 `worker` 参数；加 `plan_view()` 方法；**删 `try_feed`**（R0 过渡胶水，R2 Planner decide→feed 取代） | `start`/`on_feed`/`_spawn`/`cancel` |
| `reactive_router.py` | `Action` 加 `"note"`；`_parse_payload` feed 改用 `PlanView.steps` 校验（删 `waiting` 依赖）；加 `note` 解析分支；`_build_prompts` 执行态展示 steps 状态；tool schema 加 `note` | decide/raw_decide 结构；respond/multi/task/done 分支 |
| `orchestrator.py` | `_execute_and_settle` 消费 `_pending_notes` 时适配 dict 结构 | `start`/`on_feed`/`_drive`/`_settle`/`_check_terminal` |

---

## 4. 测试变更

### 4.1 新增测试

| 测试 | 验证 |
|------|------|
| `test_execution_state_decide_feed` | active_plan 非空 + 用户在回复 running step → decide=feed → `run.on_feed` 被调用 |
| `test_execution_state_decide_respond` | active_plan 非空 + 用户在闲聊/问进度 → decide=respond → agent 即时回复 |
| `test_execution_state_decide_note` | active_plan 非空 + 用户在追加约束 → decide=note → 入正确 worker 的桶 |
| `test_execution_state_control_cancels_before_decide` | active_plan 非空 + 用户发「取消」→ 零 LLM 取消，不进 decide |
| `test_plan_view_from_orchestrator` | Orchestrator 有 3 节点（1 COMPLETED + 1 RUNNING + 1 PENDING）→ `plan_view()` 返回 3 个 StepView |
| `test_pending_notes_per_worker_bucketing` | enqueue_note("用 React", worker="前端小美") → 只入小美的桶 |
| `test_pending_notes_global_star` | enqueue_note("错误提示中文", worker=None) → 入 "*" 桶，所有 worker 可见 |
| `test_from_session_with_run` | `from_session(run=run)` → active_plan 非空，steps 与 Orchestrator 的 DAG 一致 |
| `test_from_session_without_run` | `from_session(run=None)` → active_plan=None |
| `test_task_during_execution_downgrades_to_note` | active_plan 非空 + decide=task → 不入 `_start_coordinator`，降级 `enqueue_note`（防并行 Orchestrator） |
| `test_execution_respond_not_blocked_by_at_routing` | AT_ROUTING 群 + 执行态 + decide=respond → 正常回复（不被 `is_discussion` 拦截） |

### 4.2 删除/适配测试

| 测试 | 变 |
|------|-----|
| `test_feed_*` 中依赖 `waiting` 的测试 | `waiting` 字段删 → 断言改为检查 `PlanView.steps` |
| `test_try_feed_*` 相关测试 | `try_feed` 方法删除 → **删除测试**（R0 过渡胶水，R2 Planner decide→feed 取代盲找） |
| `test_handle_group_*` 中测试 `if run is not None` 分支的 | 改为测试 `decide → feed/note` 路由 |

---

## 5. 不动的部分

| 保留项 | 原因 |
|--------|------|
| Orchestrator（start/on_feed/_drive/_settle） | R0/R1 成果，控制流和协议不变 |
| CoordinatorRun.start/on_feed/_spawn | R0 事件驱动模型不变 |
| `on_feed(step_id, answer)` | 保留（Planner decide→feed 的落点）。删的是 `try_feed(answer)`——盲找 park 节点的便利方法 |
| `parked_step_id` | Orchestrator 上保留，`plan_view()` 不依赖它 |
| ChatService 前门机械反射（@mention/control/broadcast） | 零 LLM，不依赖路由统一 |
| `_respond` 方法 | 保留（R3 会改/删） |

---

## 6. 风险

1. **Planner 判 feed 的可靠性**：R2 把 feed 判断从 `try_feed`（只要 park 节点存在就喂）改为 Planner 从 transcript 判。这是正确的方向——`try_feed` 会把「做得怎么样了」也当成 feed——但 LLM 判断对话连续性存在误判可能。缓解：feed 的 LLM prompt 明确要求「用户消息在回答某个 running step 的 worker 之前的提问」才出 feed，且 R0 的 `on_feed` 会校验 step_id 是否存在。

2. **`_pending_notes` 的 immutable 引用**：`orchestrator._pending_notes` 现在是指向 `coordinator_run._pending_notes` 的共享引用（coordinator_run.py line 105: `orchestrator._pending_notes = self._pending_notes`）。R2 把类型从 `list[str]` 改成 `dict[str, list[str]]` 后，`orchestrator._execute_and_settle` 里的消费代码需要适配——不能直接 `list(self._pending_notes)`。

3. **PlanView 实时性**：`plan_view()` 每次调用都从 Orchestrator.graph 重新构造——这是 read-model 投影，开销 O(N) （N = 节点数，通常 <10）。可以接受。

4. **ReactiveRouter tool schema 兼容**：`action` enum 加 `"note"` 后 LLM 可能偶尔返回 note 但其实该是 respond——通过 prompt 约束（note 只在追加约束时出）。降级路径：无效 note（who 无目标）→ done（静默，不阻塞）。

5. **`from_session` 的 DB 依赖**：`SessionState.from_session` 需要 `message_repo` 做 DB 查询。之前 `_recent_history` 是在 `_handle_group` 里调，位置变化但不增加 DB 查询次数。

---

## 7. 与 R3 的耦合

R3（多轮讨论循环）会在 `_handle_group` 内加 decide for 循环。R2 先做路由统一（删 `if run is not None` 分支、`from_session` 工厂），R3 在这个统一路由上把 respond/multi 分支从单轮改成 for 循环。

两者接口兼容：R2 的 `decide → dispatch` 是 R3 的 `while True: decide → dispatch` 的退化版本（单轮 = 循环体执行一次后 break）。

---

## 8. 实现记录

> 实现日期：2026-06-08 | 状态：已实现，测试全绿（69 passed，2 个 pi_agent e2e 预存失败与本次无关）

### 与规格的偏离（含理由）

1. **`from_session` 签名改为吃 `active_plan`，不吃 `run`。**
   规格 §2.1 让 `SessionState.from_session(run=CoordinatorRun)`，但 `coordinator_run.plan_view()`
   返回 `PlanView`（须 import session_state），而 `from_session` 又要 import coordinator_run
   → **循环依赖**。改为 `from_session(*, session_id, members, message_repo, window, active_plan=None)`，
   由 chat_service 调 `run.plan_view()` 后把结果传入。依赖单向化（coordinator_run → session_state），
   SessionState 保持纯投影、不反向认识 run handle。比规格更干净。

2. **`from_session` 多一个 `window` 参数。**
   规格在 factory 内读 `settings.l1_window_size`。改为调用方传 `window`——
   session_state 不依赖 settings，可测性更好（fake repo 直接传 window）。

3. **note 不加 `note_text` 字段（与 R5 §2.1.2 的提法相反）。**
   R5 草案把 `note_text` 归功于 R2，但 R2 §2.7 明确 note 文本取自原始消息。
   实现遵循 R2：`PlannerDecision` 无 `note_text`，chat_service 用 `trigger.content` 入桶。
   **R5 实现时需删掉 §2.1.2 的 `note_text` 那行**。

### pending_notes 分桶语义（明确化）

- **本 worker 桶**：`pop` 消费——一次性，注入后即清。retry/resume 时 CLI session 已有上下文，不重注。
- **全局桶 `"*"`**：`get` 不清——持续注入每个后续 dispatch（全局约束对新 worker 仍有效）。
- 此非对称是有意的，已在 orchestrator.py 消费点加注释。

### 已知前提（标准档需复查）

- **decide 快照 vs on_feed 的 TOCTOU**：decide 读 `plan_view()` 快照判 feed(step_X)，
  到 on_feed 执行时 step_X 状态可能已变。**仅因串行 MVP park 期间无并发推进才安全**。
  标准档开并发后，on_feed 须校验节点仍处可续跑态（RUNNING/FAILED），否则拒绝重派。

### 改动文件

| 文件 | 改动 |
|------|------|
| `session_state.py` | 删 `PlanView.waiting`；加 `from_session` 工厂（吃 active_plan，非 run） |
| `coordinator_run.py` | `_pending_notes` → `dict[str,list]`；`enqueue_note(worker=)`；加 `plan_view()`；删 `try_feed` |
| `orchestrator.py` | `_pending_notes` 类型改 dict；消费点按桶取（worker pop + 全局 get） |
| `reactive_router.py` | `Action` 加 `note`；feed 校验改筛 running step；加 note 解析；prompt 展示 steps；schema 加 note |
| `chat_service.py` | 删 `if run is not None` 特殊分支；统一 `decide → dispatch`；加 feed/note 分支 + task 执行态降级；删 `_recent_history` |

### 测试

- 新增 `test_coordinator_run_r2.py`（7）：plan_view 投影、note 分桶、orchestrator 消费、from_session。
- 新增 `test_chat_service.py` 4 个执行态集成测试：feed→on_feed、note→入桶、task→降级 note、AT_ROUTING 执行态 respond 不被拦。
- 改 `test_reactive_router.py`：feed 校验改 running step；删 `waiting` kwarg；加 2 个 note 测试。
