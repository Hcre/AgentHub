# R1 实现规格 — 协议重塑：删 ask tool + PAUSED，not_done 统一 park

> 日期：2026-06-08 | 状态：实现规格 | 关联：[[coordinator-design-v4]] §6.3/§6.4/§6.6、[[coordinator-v4-event-driven]] 决策 2/5
> 前提：R0 已完成（事件驱动控制流就绪）
> 风险：**中**（改协议但不动控制流；R0 的 `_drive`/`_check_terminal`/park 路径不变）

---

## 0. 目标

删掉 v3 为「worker 提问」建的专用通道——ask tool、PAUSED 状态、`_waiting_node_key`——统一成 **not_done = 没交卷 = park 等 feed**。Worker 说话走正常 TEXT 事件推群聊（和对话路径同一条通道），不再被 executor 吞文本。

一句话验收：**worker 说「用什么技术栈」，这条消息出现在群聊里，worker 流结束后节点只是没做完（not_done），Harness 不判失败、不重试、不追一刀——等用户回话时 Planner 判 feed，用 `--resume` 把 worker 接着拉起。**

---

## 1. 现状（R0 之后的代码）

### 1.1 executor.py — 三个要删的东西

```python
# ① ask tool 检测（删）
_ASK_TOOL = "mcp__agenthub-step-tools__ask"

# ② TASK_EXEC_CONTRACT 仍提 ask tool（改）
TASK_EXEC_CONTRACT = (
    "..."
    "若信息不全无法继续，调用 `ask` 工具提出问题并等待回答，不要凭猜测推进。\n"  # ← 删
    "task_complete 和 ask 是本轮的唯一收尾方式..."  # ← 改
)

# ③ _consume 吞文本（改）
async for evt in adapter.stream(request):
    ...
    elif evt.type == StreamEventType.TEXT and evt.content:
        chunks.append(evt.content)  # ← 吞了，群聊看不到

# ④ _consume 检测 ask tool（删）
elif name == _ASK_TOOL:
    ask_question = ...  # ← 删

# ⑤ needs_reprompt → not_done（改名）
return WorkerOutcome(
    ok=False, status="needs_reprompt",  # ← ok=False, status="not_done"
    output=...
)
```

### 1.2 orchestrator.py — PAUSED 分支要删

```python
# _settle 仍保留 waiting→PAUSED 分支（删）
if outcome.status == "waiting":           # ← R1 后 executor 不再产出 waiting
    ...
    self._transition(node, TaskStatus.PAUSED)  # ← 删
    ...

# needs_reprompt 仍走 FAILED（改）
if outcome.status == "needs_reprompt":
    self._handle_failure(node, ...)       # ← 改为 not_done → park（不失败）
```

### 1.3 其他受影响文件

| 文件 | 现状 | 目标 |
|------|------|------|
| `ports.py` | `WorkerOutcome.status: "waiting" \| "needs_reprompt" \| ...`; `AskInfo` 定义 | 删 `"waiting"`，`"needs_reprompt"`→`"not_done"`；删 `AskInfo` |
| `enums.py` | `PAUSED = "paused"` | 删 |
| `fsm.py` | `RUNNING: {..., PAUSED, ...}`, `PAUSED: {RUNNING, CANCELLED}` | 删 PAUSED 所有行 |
| `mcp_step_tools.py` | `ask` tool + `_post_ask_message` | 删 |
| `dag.py` | `TaskNode.pending_answer`, `step_key` | **保留**（resume 数据） |

---

## 2. 目标态

### 2.1 executor.py：TEXT 推群聊 + 删 ask + needs_reprompt→not_done

```python
# 常量：只留 task_complete
_TASK_COMPLETE_TOOL = "mcp__agenthub-step-tools__task_complete"
# _ASK_TOOL → 删除

TASK_EXEC_CONTRACT = (
    "你被分配了一个具体任务。请直接完成它（写代码/改文件/跑命令），不要闲聊或只回复。"
    "严格遵守下方约束与验收标准。\n\n"
    "完成后必须调用 `task_complete` 工具，summary 说明：做了什么、产物在哪、关键决策。\n"
    "如果信息不全、需要确认或等待回复，直接以文本说出来，然后结束——"
    "不要猜测，用户看到后会回复你。"
)
```

```python
async def _consume(self, adapter, request, node) -> WorkerOutcome:
    """消费事件流，检测 task_complete 终结工具。
    
    变更（v4 R1）：
      - TEXT 事件 → 推 event_sink（进群聊），不再吞入 chunks
      - 删 ask tool 检测
      - 流结束无 task_complete → WorkerOutcome(status="not_done", ok=True)
        not_done 不是失败——worker 只是没做完
    """
    done_summary: str | None = None

    async for evt in adapter.stream(request):
        if self._sink is not None:
            await self._sink(evt)  # TEXT/TOOL_CALL 都推群聊
        if evt.type == StreamEventType.TOOL_CALL and evt.tool_call:
            name = evt.tool_call.name
            if name == _TASK_COMPLETE_TOOL:
                done_summary = evt.tool_call.arguments.get("summary", "")
                logger.info("task_complete detected task=%s", node.task.id)
            # 非 task_complete TOOL_CALL → 忽略（已通过 event_sink 推群聊）
        elif evt.type == StreamEventType.ERROR:
            errored = evt.content or "worker error"
            return WorkerOutcome(ok=False, status="error", output=f"worker 报错: {errored}")
        elif evt.type == StreamEventType.REQUEST_APPROVAL:
            return WorkerOutcome(ok=False, status="error", output="worker 需要审批（MVP 不支持）")

    if done_summary is not None:
        return WorkerOutcome(ok=True, status="completed", output=done_summary)

    # 流结束没交卷 → not_done。不是失败。
    return WorkerOutcome(ok=True, status="not_done", output="worker 未调用 task_complete")
```

关键变更：
- **TEXT 不再 `chunks.append`**：改为推 `event_sink`（如果注入了），跟对话 `_stream_one_agent` 走同一条通道进群聊。`event_sink` 是 `AgentExecutor.__init__` 已支持的注入点。
- **删 `ask_question` 变量**和所有 ask tool 检测逻辑。Worker 正常说话就是 TEXT，不需要专用 tool。
- **`not_done` 的 `ok=True`**：不是失败。Orchestrator 的 `_settle` 据此跳过 `_handle_failure`。

### 2.2 orchestrator.py：_settle 简化

```python
async def _settle(self, node: TaskNode, outcome: WorkerOutcome) -> None:
    """结算 worker 产出：completed/not_done/error 三态收敛。"""
    if outcome.status == "completed":
        node.output = outcome.output
        self._transition(node, TaskStatus.VERIFYING)
        verdict = await self._verifier.verify(node)
        if verdict.passed:
            self._transition(node, TaskStatus.COMPLETED)
            await self._emit_update(node, "done")
        else:
            self._handle_failure(node, verdict.reason)
            await self._emit_update(node, "failed", node.fail_reason)
        return

    if outcome.status == "not_done":
        # 流结束没交卷。不转移、不失败、不重试。
        # node 保持 RUNNING，_drive 取不到新 ready → break → park。
        # 用户回话 → Planner 判 feed → on_feed 用 --resume 续跑。
        self._record("parked", node.task.id)
        return

    # outcome.ok == False（崩/超时）
    self._handle_failure(node, outcome.output or "worker 失败/超时")
    await self._emit_update(node, "failed", node.fail_reason)
```

变更：
- **`waiting`/PAUSED 分支整个删除**。Executor 不再产出 `waiting`。
- **`needs_reprompt` → `not_done`**：不调 `_handle_failure`，只 `_record("parked")`，节点停在 RUNNING。
- **`MAX_DISPATCH` 常量**：随 ask 的删除变得不再必要（R1 后只有 retry 会增加 dispatch_count）。先保留常量但 `_settle` 不再检查它。

`_execute_and_settle` 也需更新：

```python
async def _execute_and_settle(self, node: TaskNode) -> None:
    if node.status == TaskStatus.PENDING:
        self._transition(node, TaskStatus.QUEUED)
        self._transition(node, TaskStatus.RUNNING)
    # 删：elif node.status == TaskStatus.PAUSED → RUNNING
    # not_done 后 node 仍在 RUNNING，on_feed resume 时跳过状态转移

    if node.worker is None:
        node.worker = node.task.suggested_worker
    node.dispatch_count += 1
    node.pending_notes = list(self._pending_notes)
    await self._emit_update(node, "running")

    outcome = await self._executor.run(node)
    await self._settle(node, outcome)
```

`parked_step_id` 更新：

```python
@property
def parked_step_id(self) -> str | None:
    """串行 MVP：返回唯一 park 节点的 id（RUNNING 状态的节点）。"""
    if self.graph is None:
        return None
    for node in self.graph.nodes.values():
        if node.status == TaskStatus.RUNNING:  # 删 PAUSED
            return node.task.id
    return None
```

### 2.3 ports.py：WorkerOutcome/AskInfo

```python
@dataclass(frozen=True)
class WorkerOutcome:
    """Executor 跑 worker 的结果。

    status:
      completed    — worker 调了 task_complete，ok=True
      not_done     — 流结束但未调 task_complete（没交卷），ok=True（不是失败）
      error        — worker 自身崩/超时/流错误，ok=False
    """

    ok: bool
    status: Literal["completed", "not_done", "error"] = "completed"
    output: str = ""
    # ask: AskInfo | None = None  ← 删除
```

`AskInfo` 类删除。所有 `from app.domain.task_engine.ports import AskInfo` 的导入删掉。

### 2.4 fsm.py：删 PAUSED + QUEUED + AWAITING_APPROVAL（决策见 §8）

PENDING 直接 → RUNNING（不过 QUEUED）。审批态整行删除（死代码）。

```python
VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {
        TaskStatus.VERIFYING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.VERIFYING: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.FAILED: {TaskStatus.PENDING, TaskStatus.CANCELLED},
    TaskStatus.BLOCKED: {TaskStatus.PENDING, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
}
```

### 2.5 enums.py：删 PAUSED + QUEUED + AWAITING_APPROVAL

```python
class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    VERIFYING = "verifying"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

剩 7 个值，全部有代码产出/消费。`_execute_and_settle` 的 PENDING→QUEUED→RUNNING 改为 PENDING→RUNNING 单步：

```python
async def _execute_and_settle(self, node: TaskNode) -> None:
    if node.status == TaskStatus.PENDING:
        self._transition(node, TaskStatus.RUNNING)  # 删 QUEUED 中间态
    # not_done 后 node 仍 RUNNING，resume 时跳过状态转移
    ...
```

### 2.6 mcp_step_tools.py：删 ask tool

删除：
- `ask` tool 函数（`@mcp.tool() async def ask(...)` → 删）
- `_post_ask_message` 函数（私有辅助，仅 ask 用）
- docstring 中的 ask 描述（更新注释）

保留：
- `task_complete` tool
- ASGI wrapper、ContextVar 基础设施
- `get_mcp_step_tools_asgi()`

### 2.7 build_task_request：resume 文案更新

```python
def build_task_request(node, agent, *, session_id, group_id, workspace):
    ...
    is_resume = node.pending_answer is not None
    if is_resume:
        content = (
            f"针对你之前的问题，用户回复如下：\n\n{node.pending_answer}\n\n"
            "请基于此回复继续完成任务。完成后调用 task_complete。"
        )
        notes = node.pending_notes or []
        if notes:
            content += "\n\n## 用户执行期补充（请注意以下约束）\n" + "\n".join(f"- {n}" for n in notes)
    else:
        content = build_task_instruction(node)
        notes = node.pending_notes or []
        if notes:
            content += "\n\n## 用户执行期补充（请注意以下约束）\n" + "\n".join(f"- {n}" for n in notes)
    ...
```

改：`"仍需澄清则再调用 ask"` → 删除。

---

## 3. 不动的部分

| 保留项 | 原因 |
|--------|------|
| `node.pending_answer` | resume 数据，feed 必需 |
| `node.step_key` | CLI session 隔离锚点，不变 |
| `node.dispatch_count` | 保留常量 MAX_DISPATCH，不再在 _settle 检查（R2 可清理） |
| `build_task_request` 的 `has_history` 逻辑 | resume 机制核心，不变 |
| `task_complete` tool | 唯一结构化信号，不动 |
| `AgentExecutor.event_sink` 注入 | 已有支持，只需在 `_consume` 里真正用它推 TEXT |

---

## 4. 代码变动清单

| 文件 | 变 | 不变 |
|------|-----|------|
| `executor.py` | 删 `_ASK_TOOL`；`_consume` 删 ask 检测+TEXT 吞→推 sink；`needs_reprompt`→`not_done`(ok=True)；`TASK_EXEC_CONTRACT` 改文案 | `task_complete` 检测；`build_task_request`（仅微调 resume 文案） |
| `orchestrator.py` | 删 `_settle` 的 waiting/PAUSED 分支；`needs_reprompt`→`not_done`（park，不失败）；`_execute_and_settle` 删 QUEUED 中间态（PENDING 直达 RUNNING）；`parked_step_id` 认 RUNNING 为 park 态 | `start`/`on_feed`/`_drive`/`_check_terminal`/`_finish` |
| `ports.py` | `WorkerOutcome.status` 删 `"waiting"`，`"needs_reprompt"`→`"not_done"`；删 `AskInfo` | `WorkerOutcome` 其余字段；`Verdict`/`RunResult` 等 |
| `enums.py` | 删 `PAUSED` + `QUEUED` + `AWAITING_APPROVAL`（剩 7 值） | 其余 TaskStatus 值 |
| `fsm.py` | 删上述 3 态所有转移；PENDING 直达 RUNNING | 其余转移表 |
| `mcp_step_tools.py` | 删 `ask` tool + `_post_ask_message` | `task_complete` tool；ASGI wrapper |
| 所有测试 | 适配新 API | — |

---

## 5. 测试变更

### 5.1 删 ask tool 带来的测试变更

| 测试 | 变 |
|------|-----|
| `test_orchestrator.py::test_ask_suspends_then_feed_resumes_to_completed` | executor 返回 `not_done`（非 `waiting`），节点保持 RUNNING；feed 后 resume |
| `test_orchestrator.py::test_feed_nonexistent_step_noop` | 不变（只改 node 起始状态） |
| `test_orchestrator.py::test_ask_dispatch_overflow_fails` | **删除**——MAX_DISPATCH 不再在 _settle 检查 |
| `test_orchestrator_event_driven.py::test_waiting_parks_without_finish` | executor 返回 `not_done`，断言节点 RUNNING（非 PAUSED） |
| `test_orchestrator_event_driven.py::test_feed_resumes_parked_node_and_continues_chain` | 同上 |

### 5.2 executor 测试变更

| 测试 | 变 |
|------|-----|
| `test_executor.py::test_tool_call_detection` | 删 ask tool 测试用例；`needs_reprompt`→`not_done` |
| `test_executor.py::test_text_events_pushed_to_sink`（新） | 验证 TEXT 事件推到 event_sink |

### 5.3 fsm 测试变更

| 测试 | 变 |
|------|-----|
| `test_fsm.py` 中涉及 PAUSED 的测试 | 删 PAUSED 转移断言 |

---

## 6. 风险

1. **TEXT 推群聊依赖 `event_sink` 注入**——当前 `build_default_orchestrator` 创建 `AgentExecutor` 时传 `event_sink=None`（MVP 注释"worker 流不推"）。R1 需要改为真正的 WS broadcast sink，否则 worker 说话群聊看不到。如果暂时不改 `build_default_orchestrator`，R1 在测试中验证能力但生产仍静默——不阻塞 R1 通过，但需标记为 R1.5 todo。

2. **`not_done` 的 `ok=True`**——现有代码 `if not outcome.ok` 守卫会跳过 not_done。确认 `_settle` 中 `completed` 分支在 `not outcome.ok` 之前，不会误入 error 分支。

3. **删 3 态后 DB 兼容**——DB 里若有 `"paused"`/`"queued"`/`"awaiting_approval"` 历史行，读出来 str→TaskStatus 会崩。R1 scope：只改 enum，不做 migration。但需查 DB 里 task 状态是否真持久化——若 task_engine 当前是纯内存 DAG（无 task 表落库），则无历史行问题，风险消除。**实现前先确认这一点**。

4. **ask tool 删除后旧 worker CLI session 残留**——已连接的旧 CLI 进程如果缓存了 ask tool 定义，不会立即消失；但这些 session 在 R1 部署时已不存在（CLI 短驻，V0 不保留），实际无影响。

---

## 7. 与 R0 的耦合

R0 和 R1 都改 `_settle`。实现顺序：在同一分支按 R0→R1 推进：
- R0 建好 `_drive` 的 break+park 路径（已完成）
- R1 把 `not_done` 接到这条路径上，删除 waiting/PAUSED 死代码

R1 完成后，`_settle` 的三态：`completed` → 验收 → COMPLETED/FAILED；`not_done` → park（RUNNING 不动）；`error` → FAILED + retry。

---

## 8. 决策记录：「两态」≠ TaskStatus 的状态数

> 2026-06-08，董。这个困惑出现两次了，固化到文档。

### 8.1 「两态」说的是 WorkerOutcome，不是 TaskStatus

v4 反复讲的「只有 DONE / NOT DONE 两态」，指的是 **worker 一轮跑完的结果**——即 `WorkerOutcome.status`：

| WorkerOutcome.status | 含义 |
|---|---|
| `completed` | worker 调了 `task_complete`，交卷了 |
| `not_done` | 流结束没调 `task_complete`，没交卷（提问/被切断/还在想，都归这类） |
| `error` | worker 进程崩/超时（异常，不是正常结果） |

「两态」是 `completed` vs `not_done` 这条线。砍 PAUSED 的依据就在这里：worker 在等用户回复 和 worker 在写代码，对 Harness 是同一件事——**都没交卷**。不需要给「等回复」单列一个状态。

### 8.2 TaskStatus 是另一个维度：DAG 节点的调度位置

`TaskStatus` 不回答「worker 干完没」，它回答「调度器该拿这个节点怎么办」。这是任务看板的「列」，跟「某人这趟活干完没」是两个维度。逐个证明不可省：

| TaskStatus | 调度器据此做什么 | 删了会怎样 |
|---|---|---|
| `PENDING` | 节点存在但依赖未满足/没轮到，先不派 | 无法表达「t2 依赖 t1，t1 没完成前 t2 不能派」 |
| `RUNNING` | 已派发，worker 在跑（**或跑完没交卷在等 feed**） | not_done 无处停 |
| `VERIFYING` | worker 声称完成，但**自报不可信**，待验收闸门核实 | 违反 v2 §6 不变量「RUNNING 不能直达 COMPLETED」，失去 FSM 层强制验收 |
| `BLOCKED` | 上游 FAILED，**永远等不到依赖**，别再轮询它 | 与 PENDING 混淆 → 卡死检测（`_detect_stall`）失效，调度器空转 |
| `COMPLETED` | 终态，验收通过 | — |
| `FAILED` | 崩/超时/验收没过，可重试或永久失败 | — |
| `CANCELLED` | 用户喊停 | — |

**关键**：`not_done`（worker 交卷态）≠ 任何单独的 TaskStatus。not_done 的节点停在 `RUNNING`——因为从调度看，「worker 跑完没交卷在等 feed」和「worker 还在跑」没区别，调度器对两者都是「不动它，等事件」。这正是 §8.1「不需要给等回复单列状态」在调度层的体现。

### 8.3 为什么不能再少

剩 7 个已是下限。每个对应调度器必须区分的一个处境（见上表「删了会怎样」）。再砍只有两条路，都不可接受：
- 删 `VERIFYING` → 丢掉验收闸门的 FSM 强制力（worker 自报即完成，回到「说谎 worker 蒙混过关」）。
- 并 `BLOCKED` 入 `PENDING` → 卡死检测失效，被永久挡死的节点会被反复当成「待派发」空转。

PAUSED/QUEUED/AWAITING_APPROVAL 能删，是因为它们**不对应任何独有的调度处境**：PAUSED=RUNNING（都是「没交卷，等着」）、QUEUED=RUNNING 的瞬间前奏（串行下无观察窗口）、AWAITING_APPROVAL=没人产出的死代码。
