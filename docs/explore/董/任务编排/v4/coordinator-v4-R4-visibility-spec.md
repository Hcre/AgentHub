# R4 实现规格 — 可见性 + 异常通报：上游 summary 注入 + 终端状态入 transcript

> 日期：2026-06-08 | 状态：实现规格 | 关联：[[coordinator-design-v4]] §6.7、§9.2
> 前提：R0+R1 已完成（事件驱动 + 协议重塑）
> 风险：**小**（不碰控制流，纯数据注入 + 消息通道补线）

---

## 0. 目标

补两个信息可见性缺口：

1. **上游 summary 注入**：B 依赖 A，A COMPLETED 后 B 的 instruction 里包含 A 的 `task_complete` summary，B 知道上游做了什么、产物在哪。
2. **终端状态入 transcript**：Orchestrator 在关键节点（step 完成/失败/卡死/全完成）写 SYSTEM 消息到 `messages` 表 + 广播群聊 WebSocket，进入 transcript → Planner 和所有 worker 可见。

一句话验收：**B 依赖 A 时，B 的执行 prompt 里能看到「上游任务完成摘要：A（后端 API）已完成。FastAPI，端口 8000，接口见 api/v1/」。A 完成时群聊收到「✅ A（后端 API）已完成」。B 永久失败时群聊收到「❌ B（前端）已失败（重试 3 次不通过）：npm run build 报错」。**

---

## 1. 现状（两个缺口）

### 1.1 上游 summary 未注入

当前 `build_task_instruction`（`executor.py` line 47-57）：

```python
def build_task_instruction(node: TaskNode) -> str:
    t = node.task
    parts = [f"# 任务：{t.title}", t.description or ""]
    mech = [c.spec for c in t.acceptance if c.kind == "mechanical"]
    if mech:
        parts.append(
            "## 验收（你的产出必须让这些命令通过）\n"
            + "\n".join(f"- `{s}`" for s in mech)
        )
    return "\n\n".join(p for p in parts if p)
```

**问题**：只用了 `TaskDef.title` + `description` + 验收标准。B 依赖 A 时，B 不知道 A 做了什么。数据已经有了——`node.output`（`_settle` 在 `completed` 时设置为 task_complete summary）、`node.task.depends_on`（依赖列表）——只是没注入 instruction。

### 1.2 进度通报不入 transcript

当前 Orchestrator 的消息推送：

| 事件 | 位置 | 当前通道 | 入 messages 表？ |
|------|------|---------|-----------------|
| 任务启动（plan） | `_emit_plan` | `_progress` WS → 前端任务面板 | ❌ |
| Step 完成 | `_settle` → `_emit_update(node, "done")` | `_progress` WS → 前端任务面板 | ❌ |
| Step 永久失败 | `_settle` → `_emit_update(node, "failed")` | `_progress` WS → 前端任务面板 | ❌ |
| 全局卡死 | `_report_stall` → `_emit("text", ...)` | `_progress` WS → 前端任务面板 | ❌ |
| 全完成 | `_finish` → `_on_finish` → `on_done` → `_coord_post` | **`post_system_background` → messages 表 + WS** | ✅ |

只有全完成（`_finish`）通过 `_coord_post` → `post_system_background` 写入了 messages 表。其他事件只推 WebSocket 任务面板，不进 transcript。Planner 和 worker 的 CLI session 看不到「B 已完成」「C 启动中」「任务卡死了」。

---

## 2. 目标态

### 2.1 R4-1：上游 summary 注入 instruction

#### 2.1.1 TaskNode 加 `upstream_summaries` 字段

```python
# dag.py — TaskNode 加字段
@dataclass
class TaskNode:
    # ... 现有字段 ...
    upstream_summaries: dict[str, str] | None = None
    # ^ R4：上游 COMPLETED 节点的 task_complete summary。
    #   key = task_id, value = node.output（task_complete 的 summary）。
    #   _execute_and_settle 在调用 executor.run 前从 graph 填充。
    #   build_task_request → build_task_instruction 读取并注入指令。
```

#### 2.1.2 `build_task_instruction` 加上游摘要段

```python
# executor.py
def build_task_instruction(
    node: TaskNode,
    *,
    upstream_summaries: dict[str, str] | None = None,
) -> str:
    """TaskDef → 任务指令文本（D1）。

    v4 R4：上游 COMPLETED 节点的 task_complete summary 注入「上游任务完成摘要」段。
    Worker 不需要知道下游在等它——那是 Harness 的事。
    Worker 只需要知道：自己的活、上游做了什么、用户补充了什么（design-v4 §6.7）。
    """
    t = node.task
    parts = [f"# 任务：{t.title}", t.description or ""]

    # 上游依赖摘要（R4）
    if upstream_summaries:
        parts.append(
            "## 上游任务完成摘要\n"
            + "\n".join(
                f"- {task_id}：{summary}"
                for task_id, summary in upstream_summaries.items()
            )
        )

    # 验收
    mech = [c.spec for c in t.acceptance if c.kind == "mechanical"]
    if mech:
        parts.append(
            "## 验收（你的产出必须让这些命令通过）\n"
            + "\n".join(f"- `{s}`" for s in mech)
        )
    return "\n\n".join(p for p in parts if p)
```

#### 2.1.3 `build_task_request` 传上游摘要

```python
# executor.py — build_task_request
def build_task_request(
    node: TaskNode, agent: Agent, *,
    session_id: UUID, group_id: UUID, workspace: str | None,
) -> AgentRequest:
    # ... 现有 system_prompt 构造 ...

    if is_resume:
        content = (
            f"针对你之前的问题，用户回复如下：\n\n{node.pending_answer}\n\n"
            "请基于此回复继续完成任务。完成后调用 task_complete；"
            "仍需确认则直接以文本说出来再结束。"
        )
        notes = node.pending_notes or []
        if notes:
            content += "\n\n## 用户执行期补充（请注意以下约束）\n" + "\n".join(f"- {n}" for n in notes)
    else:
        content = build_task_instruction(
            node,
            upstream_summaries=node.upstream_summaries,  # ← R4
        )
        notes = node.pending_notes or []
        if notes:
            content += "\n\n## 用户执行期补充（请注意以下约束）\n" + "\n".join(f"- {n}" for n in notes)
    # ...
```

#### 2.1.4 Orchestrator 在执行前填充 `upstream_summaries`

```python
# orchestrator.py — _execute_and_settle
async def _execute_and_settle(self, node: TaskNode) -> None:
    """派发一个节点：状态推进 → 收集上游摘要 → 执行 → 结算。"""
    if node.status == TaskStatus.PENDING:
        self._transition(node, TaskStatus.RUNNING)

    if node.worker is None:
        node.worker = node.task.suggested_worker
    node.dispatch_count += 1
    node.pending_notes = list(self._pending_notes)

    # R4：收集上游 COMPLETED 节点的 output（task_complete summary）
    node.upstream_summaries = _collect_upstream_summaries(node, self.graph)

    await self._emit_update(node, "running")

    outcome = await self._executor.run(node)
    await self._settle(node, outcome)
```

```python
# orchestrator.py — 新纯函数（模块级，可单测）
def _collect_upstream_summaries(
    node: TaskNode, graph: TaskGraph | None
) -> dict[str, str] | None:
    """收集上游 COMPLETED 节点的 output，供 worker instruction 注入。"""
    if graph is None:
        return None
    summaries = {}
    for dep_id in node.task.depends_on:
        upstream = graph.nodes.get(dep_id)
        if upstream is None:
            continue
        if upstream.status == TaskStatus.COMPLETED and upstream.output:
            summaries[dep_id] = upstream.output
    return summaries or None  # None = 无上游信息（非空 dict 才注入段）
```

#### 2.1.5 注入时机

- **首次派发**（`PENDING → RUNNING`）：上游摘要有效——依赖的节点已 COMPLETED，output 就绪。
- **resume 派发**（`on_feed`，节点已在 RUNNING）：不重新注入。`is_resume=True` 走的是 `pending_answer` 分支，不调 `build_task_instruction`。但 resume 时 worker 的 CLI session 已有之前的上下文（含首次派发时注入的上游摘要），不需要重复注入。
- **retry 派发**（`FAILED → PENDING → RUNNING`）：需要重新注入——跟首次派发走同一路径。

### 2.2 R4-2：终端状态入 transcript

#### 2.2.1 Orchestrator 加 `MessageSink`

```python
# ports.py — 新类型
# 消息通道：Orchestrator 在关键事件时写 SYSTEM 消息到 messages 表 + 广播群聊。
# 消息进入 transcript → Planner 和 所有 worker 的 CLI session 可见。
MessageSink = Callable[[str], Awaitable[None]]
```

```python
# orchestrator.py — __init__ 加 message_sink 参数
class Orchestrator:
    def __init__(
        self,
        *,
        # ... 现有参数 ...
        message_sink: MessageSink | None = None,  # R4：关键事件消息通道
    ) -> None:
        # ...
        self._message_sink = message_sink

    async def _post_message(self, content: str) -> None:
        """写 SYSTEM 消息到 messages 表 + 广播群聊（transcript 可见）。"""
        if self._message_sink is not None:
            await self._message_sink(content)
```

#### 2.2.2 各事件点的消息

| 事件 | 触发位置 | 消息内容 | 方法 |
|------|---------|---------|------|
| 任务启动 | `start()` → `_emit_plan()` 之后 | 计划摘要（各 step 名称 + 拓扑） | `_post_plan()` |
| Step 完成 | `_settle` → COMPLETED | 「✅ B（前端小美）已完成」 | `_post_step_done(node)` |
| Step 永久失败 | `_settle` → FAILED（retry 耗尽） | 「❌ B（前端小美）已失败（重试 3 次不通过）：npm run build 报错」 | `_post_step_failed(node)` |
| 全局卡死 | `_report_stall` | 「⚠️ 任务卡死：C 等待 B，但 B 已永久失败。请决定」 | `_report_stall`（已有，补 message_sink） |
| 全完成 | `_finish` | 「全部完成 ✅」+ 汇总 | `_finish`（已有，走 `_on_finish` → `_coord_post`，不动） |

具体实现：

```python
# orchestrator.py

async def _post_plan(self) -> None:
    """任务启动时通报群聊。"""
    assert self.graph is not None
    steps = []
    for n in self.graph.nodes.values():
        label = f"{n.task.id}（{n.task.suggested_worker}）"
        deps = ",".join(n.task.depends_on) if n.task.depends_on else "—"
        steps.append(f"  {label} ← {deps}")
    content = "开始执行：\n" + "\n".join(steps)
    await self._post_message(content)

async def _post_step_done(self, node: TaskNode) -> None:
    """Step 完成时通报群聊。"""
    summary = f"\n{node.output}" if node.output else ""
    await self._post_message(
        f"✅ {node.task.title}（{node.worker or node.task.suggested_worker}）已完成{summary}"
    )

async def _post_step_failed(self, node: TaskNode) -> None:
    """Step 永久失败时通报群聊。"""
    reason = f"：{node.fail_reason}" if node.fail_reason else ""
    await self._post_message(
        f"❌ {node.task.title}（{node.worker or node.task.suggested_worker}）"
        f"已失败（重试 {node.retries} 次不通过）{reason}"
    )
```

#### 2.2.3 `_settle` 中补消息调用

```python
# orchestrator.py — _settle 在 _handle_failure 后区分「retry」vs「永久失败」

async def _settle(self, node, outcome):
    if outcome.status == "completed":
        # ... 现有：VERIFYING → verdict ...
        if verdict.passed:
            self._transition(node, TaskStatus.COMPLETED)
            await self._emit_update(node, "done")
            await self._post_step_done(node)        # ← R4
        else:
            self._handle_failure(node, verdict.reason)
            await self._emit_update(node, "failed", node.fail_reason)
        return

    if outcome.status == "not_done":
        self._record("parked", node.task.id)
        return

    # error
    self._handle_failure(node, outcome.output or "worker 自身失败/超时")
    await self._emit_update(node, "failed", node.fail_reason)

def _handle_failure(self, node, reason):
    node.fail_reason = reason
    self._transition(node, TaskStatus.FAILED)
    node.retries += 1
    if TaskFSM.can_retry(node.retries):
        self._transition(node, TaskStatus.PENDING)  # retry
        # retry → 不通报群聊（内部重试，不是永久失败）
    # else: 永久失败 → 调用方（_settle）在 _handle_failure 返回后判断并通报
```

这里有个问题：`_handle_failure` 负责重试逻辑，调用方（`_settle` 的 `completed` 分支和 `error` 分支）调完 `_handle_failure` 后需要判断是否永久失败。当前 `_handle_failure` 内部吞了「retry」vs「永久失败」的区分——它在 `can_retry` 时做了 `PENDING` 转移，在不可重试时保持 `FAILED`。

更好的设计：`_handle_failure` 返回 bool 表示「是否永久失败」，调用方据此决定是否通报。

```python
def _handle_failure(self, node: TaskNode, reason: str) -> bool:
    """处理失败：FAILED → retry？返回 True 表示永久失败（重试耗尽或不可重试）。"""
    node.fail_reason = reason
    self._transition(node, TaskStatus.FAILED)
    node.retries += 1
    if TaskFSM.can_retry(node.retries):
        self._transition(node, TaskStatus.PENDING)  # retry
        return False  # 不是永久失败
    return True  # 永久失败，调用方应通报

# _settle 更新：
async def _settle(self, node, outcome):
    if outcome.status == "completed":
        node.output = outcome.output
        self._transition(node, TaskStatus.VERIFYING)
        verdict = await self._verifier.verify(node)
        if verdict.passed:
            self._transition(node, TaskStatus.COMPLETED)
            await self._emit_update(node, "done")
            await self._post_step_done(node)
        else:
            is_permanent = self._handle_failure(node, verdict.reason)
            await self._emit_update(node, "failed", node.fail_reason)
            if is_permanent:
                await self._post_step_failed(node)
        return

    if outcome.status == "not_done":
        self._record("parked", node.task.id)
        return

    # error
    is_permanent = self._handle_failure(node, outcome.output or "worker 自身失败/超时")
    await self._emit_update(node, "failed", node.fail_reason)
    if is_permanent:
        await self._post_step_failed(node)
```

#### 2.2.4 `_report_stall` 补 message_sink

```python
# orchestrator.py — _report_stall 已有 _emit("text", ...)，补 message_sink
async def _report_stall(self, description: str) -> None:
    """通报卡死到群聊（不释放 run，等用户决策）。"""
    logger.warning("任务卡死: %s", description)
    content = (
        f"⚠️ 任务卡死：{description}\n"
        "请决定：重试失败任务 / 调整计划 / 结束任务。"
    )
    await self._emit("text", {"content": content})  # 现有：WS 任务面板
    await self._post_message(content)                # ← R4：入 transcript
```

#### 2.2.5 `start` 补计划通报

```python
# orchestrator.py — start 补 _post_plan
async def start(self) -> None:
    defs = await self._planner.plan(self._ctx)
    self.graph = build_graph(defs, set(self._ctx.workers))
    self._record("plan_created", "", n=len(defs))
    await self._emit_plan()
    await self._post_plan()  # ← R4：计划入 transcript
    await self._drive()
```

#### 2.2.6 `_finish` ——不动（已有 `_on_finish` → `_coord_post`）

`_finish` 的 `_on_finish` 回调链：`on_finish(result)` → `on_done(result)` → `self._coord_post(session.id, result.summary)` → `post_system_background(session.id, content)`。这条链已经写 messages 表。R4 不碰。

#### 2.2.7 `build_default_orchestrator` 注入 message_sink

```python
# coordinator_run.py — build_default_orchestrator
async def build_default_orchestrator(
    *, task: str, members: list[Agent], session: Session, group: Group
) -> Orchestrator:
    # ...
    return Orchestrator(
        # ... 现有参数 ...
        progress=make_ws_progress_sink(session.id, group.coordinator_id, worker_ids),
        message_sink=lambda content: post_system_background(session.id, content),  # ← R4
    )
```

`post_system_background`（`coordinator_run.py` line 240-250）开独立 DB session 写 SYSTEM 消息 + 广播 WebSocket。Orchestrator 在后台 task 中运行，不能复用请求作用域的 repo/bus——`post_system_background` 正是为此设计的。

---

## 3. 不动的部分

| 保留项 | 原因 |
|--------|------|
| `_emit_update` / `_emit_plan` / `_emit_summary` | WebSocket 任务面板推送，保持不动。R4 是**加法**——在已有 WS 通道外再加 messages 表通道 |
| `_finish` / `_on_finish` / `_coord_post` | 全完成的消息写入链路已存在，不重复 |
| `_settle` 三态收敛逻辑（completed/not_done/error） | 控制流不动，只在 completed/error 路径里加 `_post_step_done`/`_post_step_failed` |
| `build_task_request` resume 分支 | resume 时不重新注入上游摘要——CLI session 已有首次派发时的完整上下文 |
| `TaskNode.pending_answer` / `pending_notes` | R1 产物，R4 不碰 |
| `node.output` 的设置 | 已在 `_settle` 的 `completed` 分支设置，R4 只读 |

---

## 4. 代码变动清单

| 文件 | 变 | 不变 |
|------|-----|------|
| `dag.py` | `TaskNode` 加 `upstream_summaries: dict[str, str] \| None` 字段 | 其余字段 |
| `ports.py` | 加 `MessageSink` 类型 alias | 其余类型 |
| `executor.py` | `build_task_instruction` 加 `upstream_summaries` 参数 + 上游摘要段；`build_task_request` 传 `node.upstream_summaries` | resume 分支；`TASK_EXEC_CONTRACT`；`_consume` |
| `orchestrator.py` | `__init__` 加 `message_sink` 参数；`_execute_and_settle` 填充 `node.upstream_summaries`；`_settle` 的 completed/error 分支加 `_post_step_done`/`_post_step_failed`；`_handle_failure` 返回 `bool`；`_report_stall` 加 `_post_message`；`start` 加 `_post_plan`；新函数 `_collect_upstream_summaries`、`_post_message`、`_post_plan`、`_post_step_done`、`_post_step_failed` | `_drive`、`_check_terminal`、`_detect_stall`、`_finish`、`on_feed` |
| `coordinator_run.py` | `build_default_orchestrator` 传 `message_sink` | `CoordinatorRun` 本身不动；`post_system_background` 不动（直接复用） |

---

## 5. 测试

### 5.1 新增测试

| 测试 | 验证 |
|------|------|
| `test_upstream_summary_injected_to_dependent` | A COMPLETED（output="FastAPI done"）→ B 首次派发 → `build_task_instruction` 输出含「## 上游任务完成摘要」段 |
| `test_upstream_summary_not_injected_when_none` | 无上游依赖的节点 → instruction 不含上游摘要段 |
| `test_upstream_summary_not_injected_on_resume` | resume 时走 `pending_answer` 分支，不调 `build_task_instruction` |
| `test_step_done_posts_to_message_sink` | `_settle` completed + verdict passed → message_sink 收到「✅ ... 已完成」 |
| `test_step_failed_permanent_posts_to_message_sink` | `_settle` error + retry 耗尽 → message_sink 收到「❌ ... 已失败」 |
| `test_step_failed_retry_does_not_post` | `_settle` error + can_retry → message_sink 不调用 |
| `test_plan_start_posts_to_message_sink` | `start()` → message_sink 收到「开始执行：...」 |
| `test_stall_posts_to_message_sink` | `_report_stall` → message_sink 收到「⚠️ 任务卡死：...」 |
| `test_finish_does_not_double_post` | `_finish` 走 `_on_finish` → `_coord_post`，不通过 message_sink 重复 |

### 5.2 适配测试

| 测试 | 变 |
|------|-----|
| `test_executor.py` 中调 `build_task_instruction` 的测试 | 可能需要更新签名（加 `upstream_summaries=None`） |
| `test_orchestrator_event_driven.py` 中构造 Orchestrator 的测试 | 可能需要构造 `_handle_failure` 的返回值断言 |
| `test_coordinator_run.py` | `build_default_orchestrator` 传了 `message_sink`，验证不崩即可 |

---

## 6. 风险与注意

1. **`_handle_failure` 返回值变更**：现有调用方（`_settle` 两处）需要更新。搜索全局所有 `_handle_failure` 调用点确认无遗漏。

2. **resume 时不注入上游摘要**：resume 时 `is_resume=True`，走 `pending_answer` 分支，不调 `build_task_instruction`。Worker 的 CLI session 已有首次派发时的完整指令（含上游摘要），重复注入无意义且会稀释 `pending_answer` 的焦点。这是正确行为，不需要「修复」。

3. **`_collect_upstream_summaries` 在 `on_feed` 路径也被调用**：`on_feed` 直接调 `_execute_and_settle`，也会填充 `node.upstream_summaries`。对 resume 路径无效（resume 不读它），但无害——填了就填了。

4. **消息频率**：一条用户消息可能触发多个 step 完成（`_drive` 串行派发，一个做完续派下一个），短时间内会落多条 SYSTEM 消息。这是期望行为——每条都是独立事件。如果前端需合并显示，在展示层处理。

5. **`_post_step_failed` 在 retry 耗尽时才调用**：`_handle_failure` 内部做了 `PENDING` 转移（retry）时返回 `False`，调用方不通报。只有 `can_retry` 返回 `False`（重试 3 次耗尽或不可重试）时才通报。这避免了每次重试都刷群聊。

---

## 7. 实现记录

> 实现日期：2026-06-08 | 状态：已实现，测试全绿（242 passed，2 pi_agent 预存失败无关）

### 按规格实现

- **R4-1 上游摘要**：`TaskNode.upstream_summaries` 字段；`build_task_instruction` 注入「## 上游任务完成摘要」段；`_collect_upstream_summaries(node, graph)` 模块函数（只收 COMPLETED + 有 output 的上游，空则 None）；`_execute_and_settle` dispatch 前填充。resume 路径不重注（走 pending_answer 分支）。
- **R4-2 入 transcript**：`MessageSink` 类型（ports.py）；Orchestrator `__init__` 加 `message_sink`；`_post_message/_post_plan/_post_step_done/_post_step_failed` 五个 helper；`start` 加 `_post_plan`；`_settle` 完成→`_post_step_done`、永久失败→`_post_step_failed`；`_report_stall` 加 `_post_message`；`_handle_failure` 改返回 `bool`（永久失败才通报，retry 不刷群聊）；`build_default_orchestrator` 注入 `message_sink=post_system_background`。

### 超出规格：turn-end drain（design §7.3，用户设计细化）

`_execute_and_settle` 从「跑一次→结算」改成 **while 循环**：每轮跑完先让输出落群聊，再看自己定向桶——这轮期间又来本 worker 的消息 → 作为「第二轮对话」续跑注入，桶空才 `_settle`。

- **(b) 决策**：即便这轮 `task_complete` 了，自己桶非空也先续 turn、不结算（验收推迟到桶空）。worker turn-1 输出照常可见，不被吞。
- **全局桶 `"*"` 不触发续跑**：只有自己定向桶非空才续 turn；全局约束搭便车在下次 dispatch 注入，不放大成 N 个 worker 各重开一轮。
- 解决的痛点：in-flight 期间来的 note 不再被动等下次自然 dispatch，而是 worker 这轮跑完就续上。

### 边角（V0 接受）

- resume（on_feed）走 drain 循环时 `pending_answer` 在循环内持续 set，turn-2 若被 note 触发会重复出现在 prompt——CLI --resume 已有上下文，冗余无害。
- 硬停（立刻杀在飞 worker）仍缺——cancel 只 `_task.cancel()` 不杀子进程。属独立缺口，见会话讨论，待排期（要 executor 暴露进程句柄）。

### 改动文件

`dag.py`(+字段) · `ports.py`(+MessageSink) · `executor.py`(上游摘要段) · `orchestrator.py`(主要：_collect_upstream_summaries / turn-end drain / message_sink + 5 helper / _handle_failure→bool) · `coordinator_run.py`(注入 message_sink)

### 测试

新增 `test_orchestrator_r4.py`（9）：上游摘要注入/收集/流转、_post_plan/done、永久失败才通报、卡死入 transcript、turn-end drain 续跑、全局桶不触发。
