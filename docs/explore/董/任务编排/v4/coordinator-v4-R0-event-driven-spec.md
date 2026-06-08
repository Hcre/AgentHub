# R0 实现规格 — Orchestrator 轮询循环改事件驱动

> 日期：2026-06-08 | 状态：实现规格 | 关联：[[coordinator-design-v4]] §6.2、[[coordinator-v4-event-driven]] 决策 1/3/4
> 风险：**大**（控制流重写，是 R1–R5 的地基）

---

## 0. 目标

把 Orchestrator 从「轮询 for 循环」改为「事件驱动」。一句话验收：**worker 问完问题流结束后，没有任何代码主动再碰这个节点；用户回话（feed）时才用 `--resume` 把它接着拉起。中途没有重复派发，也没有把任务误判为失败/卡死。**

本步**只改控制流**，不动协议（ask tool、PAUSED 删除留 R1）。R0 完成后，现状的 ask/PAUSED 仍在，但 run loop 已是事件驱动——R1 把 not_done 接到 R0 的「park」路径上即可。

> 实操：R0 和 R1 耦合较紧（都改 `orchestrator._settle`），可合并一个 PR 做。本规格按职责分写，实现时按 R0→R1 顺序在同一分支推进。

---

## 1. 现状（要替换的东西）

`src/backend/app/application/services/...` 与 `src/backend/app/domain/task_engine/orchestrator.py`：

```python
# orchestrator.py — 轮询循环（删）
async def run(self) -> RunResult:
    defs = await self._planner.plan(self._ctx)
    self.graph = build_graph(defs, ...)
    max_steps = len(defs) * (...) + 2
    for _ in range(max_steps):                       # ← 删：轮询
        self._propagate_blocked()
        ready = select_dispatchable(compute_frontier(self.graph), ...)
        if ready:
            await self._execute_and_settle(self.graph.nodes[ready[0]])
            continue
        if self._waiting_node_key is not None:        # ← 删：PAUSED 挂起
            await self._await_feed_and_resume()        # ← 删
            continue
        return await self._terminal()                  # ← 改：终止判定
    return RunResult(ExitReason.BUDGET_EXCEEDED, ...)  # ← 删：max_steps 兜底
```

```python
# coordinator_run.py — 一次性跑到底（改）
async def _run(self, orchestrator, on_done, on_error, registry):
    result = await orchestrator.run()   # ← run() 一路跑到 RunResult
    await on_done(result)
    ...
    registry.release(self.session_id)   # ← 跑完即释放
```

**要删/要改清单**：
- `run()` 的 `for _ in range(max_steps)` + `max_steps` 兜底
- `_waiting_node_key`、`_await_feed_and_resume`
- `_terminal()` 的「frontier 空即终止」语义（改为只在事件里判终态）
- `coordinator_run._run` 的「await run() → 释放」模型（改为可挂起、feed 续跑）

---

## 2. 目标态：事件驱动 Orchestrator

### 2.1 三个入口事件 + 一个驱动器

```python
class Orchestrator:
    async def start(self) -> None:
        """事件①：任务启动。建图 → 驱动一次。"""
        defs = await self._planner.plan(self._ctx)
        self.graph = build_graph(defs, set(self._ctx.workers))
        self._record("plan_created", "", n=len(defs))
        await self._emit_plan()
        await self._drive()

    async def on_feed(self, step_id: str, answer: str) -> None:
        """事件③：用户回话。把答案喂给指定节点，--resume 续跑。"""
        node = self.graph.nodes.get(step_id)
        if node is None:
            return
        node.pending_answer = answer          # executor build_task_request 读它
        await self._execute_and_settle(node)  # has_history=True → --resume
        await self._drive()                   # 续跑链条

    async def _drive(self) -> None:
        """串行驱动器：派一个 ready → 跑完 settle → 再派。
        无 ready 可派时停下（不轮询、不终止），由 settle 决定后续。"""
        while True:
            self._propagate_blocked()
            ready = select_dispatchable(
                compute_frontier(self.graph), running_count=0, max_concurrency=1
            )
            if not ready:
                break                          # ← 停，不调 _terminal
            await self._execute_and_settle(self.graph.nodes[ready[0]])
        await self._check_terminal()           # 链条停了，判一次终态
```

事件② `on_node_complete` / `on_node_failed` 不是外部入口，是 `_settle` 内部收敛后由 `_drive` 自然续派（串行 MVP 下，完成即回 `_drive` 循环顶再取 ready）。并发放开后再拆成显式回调。

### 2.2 settle：四态收敛（not_done 不再失败）

```python
async def _settle(self, node, outcome) -> None:
    if outcome.status == "completed":
        self._transition(node, VERIFYING)
        verdict = await self._verifier.verify(node)
        if verdict.passed:
            self._transition(node, COMPLETED)
            node.output = outcome.output       # 供下游 summary 注入（R4）
        else:
            self._handle_failure(node, verdict.reason)
        return

    if outcome.status == "not_done":           # ← R1 后唯一的「等输入」路径
        # 流结束没交卷。不转移、不失败、不重试。
        # _drive 这一轮取不到新 ready（node 仍 RUNNING）→ break → park。
        # 用户回话 → on_feed → --resume 续跑。
        self._record("parked", node.task.id)
        return

    # outcome.ok == False（崩/超时）
    self._handle_failure(node, outcome.output or "worker 失败/超时")
```

> R0 阶段 `not_done` 仍可能走现状的 `needs_reprompt`；R1 把它统一成上面这条（不失败、park）。R0 先保证 `_drive` 遇到「无 ready 但有未完成节点」时是 **break + park**，而不是 `_terminal` 终止。

### 2.3 终态判定：只判「真终态」，park 不算终

```python
async def _check_terminal(self) -> None:
    nodes = list(self.graph.nodes.values())
    if all(n.status == COMPLETED for n in nodes):
        await self._finish(ExitReason.COMPLETED)        # 全完成
        return
    # 有 FAILED 且下游被永久挡死 → 卡死，通报，但不释放 run
    stall = self._detect_stall()                         # §9.3 事件派生版
    if stall is not None:
        await self._report_stall(stall)                  # 进 transcript
        return                                            # ← 不释放，等用户 feed/replan/done
    # 既没全完成、也没卡死 → 有节点在 park（等 feed）→ 安静返回
    return                                                # ← run 留在 registry，等 on_feed
```

**关键**：`_check_terminal` **不一定释放 run**。三种结局：
- 全完成 → `_finish` → 释放 registry。
- 卡死（FAILED 挡死下游）→ 通报群聊 → **保留 run**，等用户决策。
- 有 park 节点 → 安静返回 → **保留 run**，等 `on_feed`。

---

## 3. CoordinatorRun 改造：可挂起、feed 续跑

现状 `_run` 是「await run() 跑到底 → on_done → 释放」。改为：

```python
def start(self, orchestrator, *, on_done, on_error, registry):
    self._orchestrator = orchestrator
    orchestrator._pending_notes = self._pending_notes
    orchestrator._on_finish = self._make_finish_cb(on_done, registry)  # 完成时回调
    orchestrator._on_error = on_error
    self._spawn(orchestrator.start())          # 后台跑 start()，可能 park 后自然结束

async def on_feed(self, step_id: str, answer: str) -> bool:
    """ChatService 判 feed 后调。续跑挂起的 run。"""
    if self._orchestrator is None:
        return False
    self._spawn(self._orchestrator.on_feed(step_id, answer))
    return True

def _spawn(self, coro) -> None:
    self._task = asyncio.create_task(self._guard(coro))   # 异常→on_error；不在此 release
```

**registry 释放时机改变**：不再是「`_run` 跑完即 `finally: release`」。改为**只在 `_finish`（全完成）或 `cancel`/用户 done 时释放**。park 状态下后台 task 自然结束，但 run 对象**留在 registry**，等下一个 `on_feed` 再 `_spawn` 一个续跑 task。

> 即 run 的生命周期 ≠ 单个 asyncio.Task 的生命周期。一个 run 可能由多个先后的 task 驱动（start 一个、每次 feed 一个），中间 park 时无 task 在跑，但 run 仍存活在 registry。

---

## 4. feed 的目标节点从哪来

现状 `feed(answer)` 靠 `_waiting_node_key`（单值，ask 设置）。R0 删 `_waiting_node_key` 后，`on_feed(step_id, answer)` 的 `step_id` 由**调用方（ChatService/Planner）给**：

- 串行 MVP：park 的节点全程最多一个 → ChatService 可从 PlanView 找「唯一非终态且无 worker 在跑」的节点，或 Planner decide 时给出 `feed_step`（reactive_router 已有 `feed_step` 字段）。
- R2 路由收口后，`feed_step` 由 Planner 从 transcript 判定（§4.2）。R0 阶段可先用「串行下唯一 park 节点」兜底，不阻塞 R0。

---

## 5. 删除清单（R0）

| 文件 | 删/改 |
|------|------|
| `orchestrator.py` | 删 `run()` for 循环、`max_steps`、`_waiting_node_key`、`_await_feed_and_resume`；改 `_terminal`→`_check_terminal`（park 不终止）；加 `start`/`on_feed`/`_drive`/`_finish` |
| `coordinator_run.py` | 改 `_run`→`start` 用 `_spawn`；加 `on_feed`；registry 释放移到 `_finish`/`cancel`；删 `has_waiting_step`/`feed(answer)` 旧签名（R2 统一） |
| `scheduler`（compute_frontier/select_dispatchable） | **保留不动**——纯函数，事件里照调 |
| `fsm.py`/`enums.py` | R0 不动（PAUSED 删除留 R1） |

---

## 6. 测试（TDD，先写）

事件序列驱动的单测，覆盖控制流分支：

| 测试 | 序列 | 期望 |
|------|------|------|
| 线性全完成 | start → A 完成 → B 完成 | run 释放，ExitReason.COMPLETED |
| not_done 挂起 | start → A 报 not_done | `_drive` break，run **不释放**，无重复派 A |
| feed 续跑 | 上一条后 on_feed(A, ans) | A 以 has_history=True 重跑 → 完成 → 续派下游 |
| 卡死通报 | start → A 永久 FAILED，B 依赖 A | `_report_stall` 调用，run **不释放** |
| 卡死后 feed 重试 | 上一条后 on_feed(A) | A 重跑 |
| 并发占位 | max_concurrency=1 | 同时只有一个节点 RUNNING |

断言重点：**not_done 不触发 `_handle_failure`、不触发重复派、不释放 registry**——这是 R0 的核心契约，是前几轮争论的落点。

mock：`_planner.plan` 返回固定 TaskDef[]；`_executor` 按测试脚本返回 WorkerOutcome 序列；`_verifier` 返回固定 verdict。

---

## 7. 风险与未决

1. **registry 生命周期变复杂**：run 可在「无 task 在跑」时存活。需确认 `CoordinatorRegistry` 支持「持有一个无活跃 task 的 run」，cancel/超时清理路径要覆盖 park 态。
2. **wall-clock 超时**（§6.8 兜底）在 park 态怎么挂：park 节点等 feed 可以无限久（人可能离开），超时只应截「单次 dispatch 太久」，**不截 park**。实现时 timeout 包在 `_execute_and_settle` 内单次执行上，不包 park 等待。← 这点要在 R0 明确，否则 park 会被超时误杀。
3. **并发放开**（非 R0）：`_drive` 串行循环改成「一次派所有 ready」+ 每个 worker 完成回调 `on_node_complete` 显式续派。届时 feed 目标消歧（多 park 节点）才成为问题。R0 锁死 `max_concurrency=1` 回避。

---

## 8. 实现记录（2026-06-08）

### 8.1 实现结果

- `orchestrator.py`：删 `run()` for 循环、`_await_feed_and_resume`、`_waiting_node_key`、`_feed_event`、`has_waiting_step()`、`feed(answer)`、`_terminal()`。加 `start()`、`on_feed(step_id, answer)`、`_drive()`、`_check_terminal()`、`_finish()`、`_detect_stall()`、`_report_stall()`、`parked_step_id`。
- `coordinator_run.py`：`_run`→`_guard`+`_spawn`，registry 释放移到 `_finish`/`cancel`。加 `on_feed(step_id, answer)`、`try_feed(answer)`。
- `chat_service.py`：`has_waiting_step`/`feed`→`try_feed`。
- 测试：20 新/旧测试全部通过（7 R0 事件驱动 + 13 v3 适配），229 全量通过（1 预存失败与变更无关）。

### 8.2 实现中发现的额外设计点

1. **`_propagate_unblocked` 是必需的**——规格未提及。当 FAILED 节点被 on_feed 手动重试成功、变为 COMPLETED 后，下游 BLOCKED 节点需要反向复活（BLOCKED→PENDING）。`_drive` 每轮先 `_propagate_blocked` 再 `_propagate_unblocked`，保证阻塞/复活双向传播。

2. **`_execute_and_settle` 需处理非 PENDING 起始状态**——on_feed 直接调 `_execute_and_settle`，但节点可能处于 PAUSED（resume）或 RUNNING（R1 not_done park）。PAUSED→RUNNING 跳过 QUEUED 阶段。worker 仅在 None 时设置（首次派发）。

3. **`_on_finish` 回调必须是 async**——类型为 `Callable[[RunResult], Awaitable[None]]`。测试中所有回调需显式声明 `async def` 或使用 `_Capture` 类实现 `async __call__`。
