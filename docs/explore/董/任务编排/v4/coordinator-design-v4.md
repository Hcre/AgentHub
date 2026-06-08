# Coordinator 设计 v4 — 单一大脑 + 统一路由 + 零模式

> 日期：2026-06-08 | 状态：设计稿 v4.0
> 取代：[[coordinator-design-v3]]（2026-06-07）· [[coordinator-architecture-overview-v2]]（2026-06-08）
> 关联决策：ADR-03（单一协调大脑）· [[design-evolution-why-simplify]]（推理链）· [[simplify-step-tools-no-ask-paused]]（简化决策）
> 不变基础：v2 §1–§7（Harness/DAG/FSM/验收/worktree/事件溯源，已实现）

---

## 0. v4 相对 v3 的核心变更

v3 的正确部分全部保留：一个 Planner 大脑、统一路由、SessionState 投影、两档 LLM 成本纪律。v3 的错误部分是 **§11（step = 有界对话）**——把 worker 提问当成需要专用 tool + 特殊状态 + 显式唤醒机制的例外流程。经过 5 个转折点的推理链（详见 [[design-evolution-why-simplify]]），结论是：

| v3 | v4 | 为什么 |
|----|----|--------|
| `ask` tool + `task_complete` tool 双协议 | `task_complete` 唯一结构化信号 | worker 能正常说话，executor 吞文本才是根因 |
| PAUSED / WAITING 子态 | DONE / NOT DONE 两种状态 | 问问题跟写代码一样，都是在干活 |
| `_feed_event` + `_waiting_node_key` + 显式 resume | Planner 从 transcript 判 feed → 重新 spawn worker（`--resume`） | 「谁在等答案」是对话连续性问题，不是 DAG 调度问题 |
| 完成闸门「两个都没调 → 追一刀」 | 「没调 task_complete → not_done」 | 不猜 worker 意图；没交卷就是没做完 |
| 执行态 / 纯对话态两张路由图 | 一张图 | `active_plan` 是 Planner 的输入字段，不是路由分支条件 |
| PlanView 含 `waiting` 列表 | PlanView 只有 steps 状态 | who's waiting 从 transcript 自然看到 |
| DiscussionOrchestrator + Selector L2 | 删除 | 多轮讨论 = for 循环 + decide |

**v4 是此后协调者模块的唯一权威设计文档。v3 归档。**

---

## 1. 架构总览：一个大脑 + 一副骨架 + N 只手

```
用户/Agent 消息
      │
      ▼
┌─────────────────────────────────────────┐
│          ChatService（前门）             │
│                                          │
│  零 LLM 反射：@mention / control / broadcast │
│  其余 → SessionState.from_session()       │
│       → Planner.decide(state)            │
│       → dispatch(action)                 │
└──────────────┬──────────────────────────┘
               │
     ┌─────────▼─────────┐
     │  Planner = 唯一大脑 │  ← LLM（一个大脑，两个视野）
     │                    │
     │  reactive: decide  │  「下一步干什么」
     │  deliberate: plan  │  「怎么分解」
     │                    │
     │  → respond / multi │  聊天
     │  → task            │  起任务
     │  → replan          │  改计划
     │  → feed            │  继续干活
     │  → note            │  旁路补充
     │  → done            │  静默
     └──┬──────────────┬──┘
        │              │
   轻 dispatch     重 dispatch
        │              │
    ┌───▼──────┐  ┌───▼────────────────────────┐
    │ respond  │  │       Harness（零 LLM）       │
    │ 流式出消息 │  │                              │
    │ 无验收    │  │  DAG 调度  compute_frontier   │
    │ 无产物    │  │  FSM 状态  完成/未完成        │
    └──────────┘  │  验收闸门  verify              │
                  └──────────┬───────────────────┘
                             │
                  ┌──────────▼──────────┐
                  │   Worker（手）        │
                  │   CLI session        │
                  │   全工具             │
                  │   唯一结构化信号：     │
                  │   task_complete      │
                  └─────────────────────┘
```

三层职责：

| 层 | 是谁 | 怎么决策 | 管什么 |
|----|------|---------|--------|
| **大脑** Planner | 一个 LLM，两个视野 | LLM 判断 | 路由（respond/task/replan/feed/note/done）、DAG 分解/重分解 |
| **骨架** Harness | 确定性代码 | 图论 + 命令 | DAG 调度、图手术（replan）、FSM、验收、异常通报、事件记录 |
| **手** Worker | agent CLI | agent 自己判断 | 写代码、读文件、问问题、交卷 |

**Harness 不是大脑**。`compute_frontier` 做的事是「遍历 DAG，找出依赖已满足的节点」——图论属性，零语义判断。跟 `for item in list` 同理。

---

## 2. 核心概念

### 2.1 对话是任务的退化，任务是对话的延伸

Planner 的输出永远是 plan。唯一的变量是视野与 step 类型：

| | 聊天（reactive） | 干活（deliberate） |
|---|---|---|
| Planner 视野 | horizon=1，每轮重规划 | horizon=N，规划一次 |
| step 类型 | `respond`（出消息） | `work`（写代码/改文件） |
| 终止条件 | LLM 判 done（软） | worker 调 `task_complete` + 验收通过（硬） |
| LLM 成本 | 每条消息一次轻调用 | 起任务一次重调用 + 后续 replan（步 4） |

决策层统一，执行引擎不统一：`respond` 不走 DAG/验收/worktree；`work` 才走完整 Harness。一句「hi」不该触发建图+验收。

### 2.2 任务只有两种状态

```
DONE        COMPLETED（验收通过）

NOT DONE    PENDING / QUEUED / RUNNING / FAILED / BLOCKED
            写代码、问问题、等回复、卡住了——全是 NOT DONE
```

**没有 PAUSED**。Worker 问「用什么技术栈」跟 worker 在写 `app.py` 没有本质区别——都是在干活，只是前者此刻需要输入才能继续。Harness 不需要区分，只关心一件事：**交卷了没有**。

之所以能不要「等待输入」这个状态，是因为调度是**事件驱动**（§6.2）而非轮询：worker 问完问题进程结束后没有任何事件触发，调度器自然休眠等 feed，不会重复派发同一个 step。轮询循环才需要一个「停车标记」拦住重复派发——v3 的 PAUSED 就是这个标记。事件驱动把轮询这一维抽掉，标记随之消失。节点仍记两样**数据**（非状态）：resume 句柄（feed 时 `--resume` 用）和依赖关系。详见 [[coordinator-v4-event-driven]]。

### 2.3 没有模式

`active_plan` 不是「模式开关」。只是 Planner 读到的字段之一——有 DAG 在跑就是 PlanView，没有就是 None。跟 `transcript` 一样，有就有，没有就没有。

**ChatService 不知道也不关心现在是什么态。**

### 2.4 唯一的结构化协议：task_complete

Worker 跟 Harness 之间只需要一个 tool：

| tool | 含义 | Harness 反应 |
|------|------|-------------|
| `task_complete(summary)` | 「活干完了，产物在此」 | RUNNING → VERIFYING → 验收 → COMPLETED |

Worker 说话、问问题、讨论——全是正常文本输出。跟对话路径一样，直接推群聊。跟 `Read`/`Write`/`Bash` 一样是普通操作，不触发状态变更。

**不需要 `ask` tool**。不是「worker 不能问问题」，是「executor 把文本吞了」。根因在 executor，不在协议。

### 2.5 没交卷就结束了

Worker 流结束但没调 `task_complete` → `WorkerOutcome(status="not_done")`。不是失败，就是还没做完。

可能原因：问了问题等回复（V0 短驻 CLI stdin 关了，自然结束）；被时间切断。Harness 不做假设。后续 Planner 判 `feed` 时重新派发（`--resume` 恢复上下文）。

---

## 3. SessionState：两条事件流的只读投影

```
messages 表──────────┐
  append-only        │  投影
  transcript         ├──→ SessionState ──→ Planner.decide(state)
                     │
task_events──────────┘
  append-only        │  投影
  active_plan        │
```

```python
@dataclass(frozen=True)
class SessionState:
    session_id: UUID
    members: tuple[Agent, ...]          # 候选 worker
    transcript: tuple[Message, ...]     # 近 15 条消息（含所有 agent）
    active_plan: PlanView | None        # None = 纯聊天；非 None = DAG 投影

@dataclass(frozen=True)
class PlanView:
    steps: tuple[StepView, ...]         # 各节点客观状态

@dataclass(frozen=True)
class StepView:
    step_id: str
    worker: str
    status: str                         # pending / running / completed / failed / blocked
```

- **Read-model，不是可变对象**。DAG 变更走 Orchestrator 单写者；transcript 来自 messages 表。
- **没有 `waiting` 字段**。谁在等答案——Planner 从 transcript 自然看到。这是对话连续性问题，不是 DAG 投影问题。
- **没有显式 mode 枚举**——态由 `active_plan` 派生。
- `from_session()` 工厂方法从 message_repo + run 构造，不手工拼。

### 3.1 PlanView 投影

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

纯数据投影，无业务逻辑。

---

## 4. 统一路由：一扇门，一条路

不管群里有任务在跑还是纯聊天，所有消息走同一段代码：

```
用户消息 → ChatService._handle_group
  │
  ├─ 反射① @mention 解析     → 命中 → _stream_one_agent（零 LLM）
  ├─ 反射② is_control        → 命中 → cancel / 忽略（零 LLM）
  ├─ 反射③ is_broadcast      → 命中 → multi 全员（零 LLM）
  │
  └─ state = SessionState.from_session(session_id, members, message_repo, run)
     decision = Planner.decide(state)
     dispatch(decision)
```

### 4.1 Planner.decide 七种 action

一次轻 LLM 调用（tool_use），喂 transcript（标注角色）+ members（标注能力）+ active_plan 状态。

| action | 含义 | dispatch |
|--------|------|----------|
| `respond(who)` | 找人回复 | `_stream_one_agent` → 回完 continue（多轮） |
| `multi(who)` | 多人并行回复 | 并行 `_stream_one_agent` |
| `task` | 起任务 | `Planner.plan(ctx)` → 起 Harness（后台） |
| `replan(requirement)` | 执行期改计划 | `Planner.plan(ctx + 新约束)` → Orchestrator 换图（§8） |
| `feed(step)` | 继续干活 | 重新 spawn 该 step 的 worker（`--resume`） |
| `note(who, text)` | 旁路补充 | 入 `_pending_notes[worker]`，step 边界注入 |
| `done` | 不需要回应 | 静默 |

`task` 和 `replan` 的区别：`task` 是 `active_plan is None` 时起新任务；`replan` 是 `active_plan 非 None` 时用户要求改计划。两者都走 deliberate 重 LLM，但 `replan` 需要 DAG 手术（§8），`task` 是新建图。

### 4.2 判断准则

Planner 从 transcript 的自然对话连续性判断，不依赖 waiting 列表：

```
transcript 最后一条是用户在跟某个 worker 对话的延续 → feed（让 worker 继续）
用户在闲聊/问进度                                    → respond（找人或自己答）
用户要改需求/改方案（active_plan 非空）                → replan（DAG 手术）
用户要写代码/改文件/跑命令（active_plan 为空）          → task（起 Harness）
不需要任何回应                                        → done
```

`feed` 的判断准则：「这条消息在跟谁对话」——不是「这条消息是不是答案」。对话连续性的判断比答案匹配更可靠、更通用。

`replan` 的判断准则：用户不是在跟具体 worker 对话（不是 feed），不是在闲聊（不是 respond），而是在**改变任务的根本方向**——「改成微服务」「别做博客了做文档站」「后端换成 Go」。

### 4.3 与 v3 路由的差别

| | v3 | v4 |
|---|---|---|
| 执行态路由 | `if run is not None: ... return`（独立分支） | 跟纯对话态走同一段 `decide → dispatch` |
| active_plan | 路由分支条件 | Planner 的输入字段 |
| feed | `has_waiting_step → 盲 feed` | `decide → feed(step)`（Planner 从 transcript 判断） |
| 执行态闲聊 | 被 `enqueue_note` 吞掉 | `decide → respond` → 即时回复 |
| PlanView.waiting | 有 | 无 |

---

## 5. 多轮讨论：反复 decide

步 1 的 strip（回完即止）升级为 keep（回完继续）：

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

    break  # done 或其他 → 退出
```

防循环三层：

| 机制 | 位置 | 说明 |
|------|------|------|
| `already_responded: set[str]` | 循环内 Python set | 确定性防重，同人不选两次 |
| `max_discussion_rounds` | settings（默认 5） | 机械硬上限 |
| LLM 判 done | decide prompt | 主力出口 |

---

## 6. 任务执行

### 6.1 两步走

```
decide → task
  → Planner.plan(ctx)  重 LLM，分解
  → TaskDef[] = [
      {id:"A", worker:"后端", depends:[],   验收:"pytest tests/api"},
      {id:"B", worker:"前端", depends:["A"], 验收:"npm run build"},
      {id:"C", worker:"测试", depends:["A","B"], 验收:"npm run e2e"},
    ]
  → build_graph → TaskGraph
  → Orchestrator.run()  fire-and-forget 后台
```

### 6.2 DAG 调度（事件驱动，确定性，零 LLM）

**不是轮询循环，是事件驱动。** Orchestrator 平时休眠，只在四类事件醒来：

```python
async def on_start(self):
    self.graph = build_graph(defs)
    await self._dispatch_ready()          # 派所有根节点（依赖已满足的）

async def on_node_complete(self, node):   # worker 调 task_complete + 验收通过
    self._transition(node, COMPLETED)
    if self._all_completed():
        return await self._finish()       # 全部完成 → 通报收尾
    await self._dispatch_ready()          # 派依赖刚满足的下游

async def on_node_failed(self, node):     # 重试耗尽 → 永久失败
    self._transition(node, FAILED)
    self._propagate_unreachable()         # 下游标不可达
    await self._report_stall()            # 通报群聊，等用户决定

async def on_feed(self, step, answer):    # 用户回话
    node = self.graph.nodes[step]
    node.pending_answer = answer
    await self._execute(node)             # --resume 续上下文，接着干

def _dispatch_ready(self):
    for nid in select_dispatchable(compute_frontier(self.graph)):
        self._execute(self.graph.nodes[nid])   # fire-and-forget 起 worker
```

`compute_frontier` / `select_dispatchable` 仍是纯函数（给定图算出谁 ready），只在事件里**调一次**，不再每圈轮询。

**为什么事件驱动**：轮询循环会把「问了问题正等回答」的节点每圈都重新判定为「该派」，于是同一个问题被反复派发——v3 为拦住它被迫引入 PAUSED 当拦路标记。事件驱动下，worker 问完问题进程结束后**没有任何事件触发**，调度器自然休眠等 feed，不会重复派发，**因此不需要任何「停车标记」**。详见 [[coordinator-v4-event-driven]] 决策 1。

每一步：PENDING → QUEUED → RUNNING → VERIFYING → COMPLETED（或 FAILED → 重试）。worker 流结束没交卷（not_done）= 没有事件，节点停在原地等 feed，调度器不动它。

### 6.3 Worker 怎么干活

Executor 调 CLI session。Worker 有全部工具（Read/Write/Bash…）。

**唯一的结构化信号**：`task_complete(summary)`。Worker 调这个 → Harness 知道交卷了 → 进验收。

**Worker 说话就是正常文本**。Executor 不再吞文本——TEXT 事件推 ws_manager.broadcast 到群聊。跟对话路径的 `_stream_one_agent` 输出走同一条通道。

```
Worker CLI:
  → tool_use Read     ← 正常干活
  → text "存储方式没定。用 Markdown 还是 CMS？"  ← 正常说话，推群聊
  → 流结束（V0 短驻 stdin 关了）→ not_done   ← 没交卷，就是没做完
```

### 6.4 完成闸门

流结束但 `task_complete` 没调 → `WorkerOutcome(status="not_done")`。

这不是异常。Harness 不做假设，不追一刀——worker 可能问了问题等回复，也可能被时间切断。后续 Planner 从 transcript 看到对话没结束，用户回话时判 `feed` 重新派发。

**与 v3 的差别**：v3 的完成闸门是「两个终结工具都没调 → resume 追一刀要求 worker 调一个」。v4 不需要——因为 `ask` tool 不存在，worker 不需要用 tool 来提问。没调 `task_complete` 只有一个含义：没做完。

### 6.5 验收闸门（保留 v2 §6）

即便调了 `task_complete`，验收闸门核 summary + 实际 artifact。产物不符验收标准 → 打回 RUNNING。堵住「调了 task_complete 但没干完」。

### 6.6 DAG 状态写入链路

**Orchestrator 是 DAG 状态的唯一写者**（单写者原则）。Worker 不直接改 DAG 状态——它只通过 `task_complete` tool 发出信号，由 Harness 的确定性代码执行状态转移。

完整链路：

```
Worker CLI session
  │
  │  tool_use {name: "task_complete", input: {summary: "..."}}
  │
  ▼
Executor._consume (stream-json 解析)
  │  检测 tool_call.name == "mcp__agenthub-step-tools__task_complete"
  │  → WorkerOutcome(ok=True, status="completed", output=summary)
  │
  ▼
Orchestrator._settle(node, outcome)
  │
  ├─ outcome.status == "completed":
  │     _transition(node, VERIFYING)         ← RUNNING → VERIFYING
  │     verdict = await verifier.verify(node)
  │     ├─ pass:  _transition(node, COMPLETED)  ← VERIFYING → COMPLETED（终态）
  │     └─ fail:  _handle_failure → FAILED → retry → PENDING
  │
  ├─ outcome.status == "not_done":
  │     # 流结束但没调 task_complete。不做任何转移，不算失败。
  │     # 无事件触发 → 调度器休眠，节点停在原地。
  │     # 用户回话 → Planner 判 feed → on_feed 重新派发（--resume）。
  │
  └─ outcome.ok == False:
        _handle_failure → FAILED → retry → PENDING（或永久 FAILED）
```

**谁改什么**：

| 组件 | 角色 | 改什么 |
|------|------|--------|
| **Worker** CLI | 信号发出者 | 调 `task_complete` tool。不感知 DAG |
| **Executor** | 信号翻译者 | stream-json → `WorkerOutcome` 结构体。不改状态 |
| **Orchestrator._settle** | 唯一写者 | 调 `_transition(node, to)`，经 `TaskFSM.assert_transition` 校验后写 `node.status` |
| **Verifier** | 验收裁判 | 返回 pass/fail。不改状态 |
| **Scheduler** | 只读查询 | `compute_frontier` / `unreachable_pending` 只读 DAG，返回 id 列表 |

**状态转移图**（v4 目标态，无 PAUSED）：

```
                    ┌──────────┐
                    │  PENDING │ ← retry（can_retry）
                    └────┬─────┘
                         │ _dispatch_ready（依赖满足）
                         ▼
                    ┌──────────┐
                    │  QUEUED  │
                    └────┬─────┘
                         │ _execute（起 worker）
                         ▼
                    ┌──────────┐
            ┌───────│ RUNNING  │───────┬──────────────┐
            │       └────┬─────┘       │              │
            │            │             │              │
            │     task_complete    error/超时      not_done
            │            │             │         （流结束没交卷）
            │            ▼             ▼              │
            │       ┌──────────┐  ┌────────┐         │ 无转移：停在 RUNNING
            │       │VERIFYING │  │ FAILED │          │ 调度器休眠等 feed
            │       └────┬─────┘  └────────┘          │
            │        ┌───┴───┐    →PENDING(retry)     │ on_feed(answer)
            │        ▼       ▼     或永久 FAILED       │  → --resume 续干
            │   ┌────────┐ ┌────────┐                 │  → 回 RUNNING
            │   │COMPLETED│ │ FAILED │                └──────────────┘
            │   │ (终态) │ └────────┘
            │   └────────┘
            │
            └── upstream 永久 FAILED → BLOCKED（下游不可达）
```

**没有 PAUSED**。not_done 不触发任何状态转移，也不算失败——节点停在 RUNNING（worker 进程已结束，但逻辑上「还没做完」），调度器因无事件而休眠，直到 `on_feed` 用 `--resume` 把它接着拉起。详见 [[coordinator-v4-event-driven]] 决策 1/3/4。

### 6.7 跨 Worker 信息可见性

**当前实现**：

Worker 收到的 context 由 `build_task_request()` 构造：

| 信息 | 来源 | 当前状态 |
|------|------|---------|
| 自己的任务指令 | `TaskDef.title` + `TaskDef.description` | ✅ 已注入 |
| 验收标准 | `TaskDef.acceptance`（mechanical 类） | ✅ 已注入 |
| 任务执行契约 | `TASK_EXEC_CONTRACT`（system prompt） | ✅ 已注入 |
| 上游依赖的 summary | `TaskNode.output`（上游 COMPLETED 节点的 task_complete summary） | ❌ **未注入** |
| 用户的旁路补充 | `_pending_notes` | ✅ 已注入（step 边界） |
| 用户对提问的回答 | `node.pending_answer`（resume 时） | ✅ 已注入 |
| 其他 worker 的实时进度 | Orchestrator 通报 | ❌ **未入 transcript** |
| 群聊 transcript | CLI session 上下文 | ✅ CLI 自带 |

**两个缺口**：

1. **上游 summary 未注入**：B 依赖 A，A COMPLETED 后 B 开始执行，但 B 的 instruction 里不含 A 的 `task_complete` summary。B 不知道 A 做了什么、产物在哪、有什么约定。B 只能靠自己读文件推断。

   修复：`build_task_instruction()` 增加依赖摘要段：
   ```
   ## 上游任务完成摘要
   - 后端 API（A）：已完成。FastAPI + PostgreSQL，接口定义在 api/v1/
   ```

2. **进度通报不入 transcript**：Orchestrator 的 `_emit_update` / `_emit_summary` 推 WebSocket（前端任务面板），不写 `messages` 表。Worker 的 CLI session transcript 里看不到「B 已完成」「C 启动中」这类消息。

   修复：Orchestrator 在关键节点（step 完成/失败/卡死）通过 ChatService 的消息通道写 `messages` 表 + 推群聊 WebSocket。消息进入 transcript → Planner 和所有 worker 可见。

**设计意图（v4 完全体）**：

```
Worker B 的 instruction：
  # 任务：前端页面
  用 React 实现博客前端

  ## 上游任务完成摘要
  - A（后端 API）：已完成。FastAPI，端口 8000，接口见 api/v1/。Auth 用 JWT。

  ## 验收
  - npm run build
  - npm run lint

  ## 用户执行期补充
  - 注意前端用 React
```

Worker 不需要知道 C（测试）在等它——那是 Harness 的事。Worker 只需要知道：自己的活、上游做了什么、用户补充了什么。

### 6.8 Worker 卡久了怎么办

**取消了 step dispatch budget**（原「每 step 最多 3 次 dispatch」机械截断）。理由：budget 想区分「空转很多轮」和「问了问题在等」，但删 ask 信号后它无法区分，会误杀正常多轮提问的 worker。详见 [[coordinator-v4-event-driven]] 决策 7。

改靠两条互补的兜底：

1. **Planner 从 transcript 判断**（主力）：每轮 decide 时自然看到「有人在等、N 轮对话过去了还没人回答」→ 在 respond 里顺带提醒「XX 还在等你的回复」。这是对话轮次维度的提醒，不依赖新机制——decide 已经能看到 transcript。
2. **wall-clock 超时**（兜底，v2 §5）：截「单次 dispatch 一轮太久」——worker 在一次执行内陷入死循环。两者互补：Planner 管「转太多轮」，超时管「一轮太久」。

---

## 7. 执行期消息交互

执行期（active_plan 非 None）下用户消息跟纯聊天走**同一个路由**：

```
用户消息 → decide(SessionState)
  │
  ├─ respond(who)   → 闲聊/问进度，即时回复
  ├─ feed(step)     → 某 worker 在等回复，重新派发
  ├─ note(who, txt) → 旁路补充，入 worker 消息队列，step 边界注入
  ├─ task           → 已在执行态，降级为 note
  └─ done           → 静默
```

### 7.1 旁路消息按 worker 分桶

`_pending_notes` 从 `list[str]` 改为 `dict[str, list[str]]`：

```python
_pending_notes: dict[str, list[str]]  # key = worker 名 或 "*"

enqueue_note(text, worker="前端小美") → _pending_notes["前端小美"]
enqueue_note(text, worker=None)       → _pending_notes["*"]

# dispatch 时消费
node.pending_notes = (
    _pending_notes.pop("前端小美", [])   # 自己的
    + _pending_notes.get("*", [])        # 全局
)
```

### 7.2 feed 语义

`feed(step_id)` 的语义：Planner 从 transcript 判断这条消息是在跟某个 worker 对话的延续 → 重新 `executor.run(node)`（`--resume` 恢复上下文）。

**不是「唤醒 PAUSED step」**——因为没有 PAUSED。Worker 上次流结束但没交卷，现在重新 spawn，让它从上次的上下文继续。

### 7.3 投递时机

Worker 只在两个时刻可收到新消息：
1. Planner 判 `feed` → 重新 spawn
2. Step 边界 → pending_notes 注入下一个 step 的 instruction

已在飞的 step 收不到旁路消息——CLI 占线无法注入，是 V0 短驻模型的硬限。**这是接受的代价，不是 bug。** 后续 step 或 replan（步 4）补上。

---

## 8. 计划变更（Replan）

### 8.1 触发

执行期用户说「改成微服务架构」「别做博客了，做文档站」「后端换成 Go」→ `decide` 看到 `active_plan` 非空 + 消息是根本性需求变更 → `replan(requirement)`。

不是所有执行期消息都是 replan。「做得怎么样了」是 respond，「注意用 React」是 note，「你怎么看」是 feed。Planner 从 transcript 区分「改方案」和「问进度/闲聊/补充/接话」。

### 8.2 流程

```
User: "改成微服务架构"
  → decide(state, active_plan 非空) → action=replan(requirement="改成微服务架构")

ChatService:
  1. 构造 replan 上下文:
     - 当前 DAG 快照（各节点状态 + summary）
     - transcript（近 15 条）
     - 新需求文本
  2. new_tasks = await Planner.plan(replan_context)   ← deliberate 重 LLM
  3. diff = run.diff(new_tasks)                         ← Harness 确定性算影响面
  4. 破坏性？（要 cancel RUNNING / 丢 COMPLETED 成果）
       是 → 群聊发确认请求，等用户确认（复用 feed/done，无新通道），确认后才 run.replan()
       否 →（纯新增 / 只改 PENDING）直接 run.replan() + 群聊通报
```

**Orchestrator 不做 LLM 调用**——ChatService 调用 Planner.plan() 拿到新 TaskDef[] 后传给 Orchestrator。保持 Harness 零 LLM。

**破坏性才确认**（[[coordinator-v4-event-driven]] 决策 6）：cancel 在飞 worker / 丢已完成成果是难逆转操作，而 replan 触发只是一次 LLM 分类，误判（把「顺便用下 Go 的库」读成「后端换 Go」）会白杀在飞 worker。所以「要不要确认」由 **Harness 算 diff 客观裁定**，不靠 LLM 再赌一次：要动 RUNNING/COMPLETED 就先求确认，纯新增或只改 PENDING 直接换。

### 8.3 DAG 手术

Orchestrator.replan(new_tasks) 是确定性图操作：

```
1. 暂停调度（不 dispatch 新节点）

2. 构建新图: new_graph = build_graph(new_tasks)

3. Diff 旧图 vs 新图，逐节点处理:
   ┌─────────────────┬──────────────────────────────────────┐
   │ 节点状态          │ 处理                                 │
   ├─────────────────┼──────────────────────────────────────┤
   │ COMPLETED + 仍在 │ → 保留状态，不重做                     │
   │ COMPLETED + 消失 │ → 保留（成果不回滚）                   │
   │ RUNNING + 仍在   │ → 继续跑，不中断                       │
   │ RUNNING + 消失   │ → cancel worker session               │
   │ PENDING + 仍在   │ → 保留，等新图调度                     │
   │ PENDING + 消失   │ → 丢弃                                │
   │ 新增节点          │ → PENDING，等调度                     │
   └─────────────────┴──────────────────────────────────────┘

4. 原子换图: self.graph = new_graph

5. 恢复调度: compute_frontier → dispatch
```

**铁律**：
- COMPLETED 节点成果不回滚（做过的活不白做）
- 受影响的 RUNNING 节点 cancel（继续跑旧方案浪费算力）
- 调度循环本身不需要感知「换图了」——`compute_frontier` 读的是当前图，换图后自然按新 DAG 排

### 8.4 与 feed/note 的边界

| 用户说了什么 | decide 判什么 | 为什么 |
|-------------|-------------|--------|
| 「用 Markdown」 | `feed(前端)` | 在跟小美对话，回答她的问题 |
| 「注意用 React」 | `note(who=("前端",))` | 补充约束，不改方向 |
| 「别做博客了，做文档站」 | `replan` | 根本性需求变更 |
| 「整体架构改成微服务」 | `replan` | DAG 结构要变 |
| 「后端换成 Go」 | `replan` | 可能影响已完成的后端节点 |

核心区分：「在跟一个 worker 继续对话」vs「在追加约束」vs「在推翻重来」。Planner 从 transcript 自然判断。

---

## 9. 异常处理（失败 / 不可达 / 失控）

异常处理 = Harness 检测事实 + 群聊通报 + Planner 读 transcript 建议 + 用户拍板。**同一扇门，同一套事件**——没有独立的异常处理通道。

### 9.1 异常分类

| 异常 | 检测 | 处理 |
|------|------|------|
| **Step 执行失败** | worker crash / 验收不通过 | 重试（最多 3 次） |
| **Step 永久失败** | 重试耗尽 | 标记 FAILED → `on_node_failed` 通报群聊 |
| **依赖不可达** | 节点依赖永久 FAILED 的节点 | 标记 BLOCKED → 通报群聊 |
| **全局卡死** | `on_node_failed` 后下游 PENDING 节点全被 FAILED 阻塞、无 ready 可派 | 通报群聊：哪些节点被谁阻塞 |
| **Worker 失控** | wall-clock 超时 / Planner 从 transcript 判断 | 通报群聊（见 §6.8，已取消 dispatch budget） |
| **Wall-clock 超时** | 单次 dispatch 超时（v2 §5） | 标记 FAILED → 重试或通报 |

### 9.2 通报机制

Harness 在以下时刻主动推送消息到群聊（复用现有 Orchestrator 消息推送通道）：

```
1. 任务启动时:    "开始执行：A(后端) → B(前端) → C(测试)"
2. Step 完成时:   "B(前端) 已完成"
3. Step 永久失败:  "B(前端) 已失败（重试 3 次不通过）: npm run build 报错 [摘要]"
4. 全局卡死:      "无法继续：C(测试) 等待 B(前端)，但 B 已永久失败。请决定：重试 B / 调整计划 / 跳过 C"
5. 任务全部完成:  "全部完成 ✅"
```

这些消息进入 transcript → Planner 在下一次 decide 看到 → 可建议下一步。

### 9.3 全局卡死的判定

事件驱动下卡死检测**不轮询**，在 `on_node_failed` 里顺手算：一个节点永久 FAILED 后，检查是否还有 ready 可派；若没有、且仍有未完成节点，就是卡死。

```python
def _detect_stall(self) -> StallReport | None:
    # on_node_failed 触发后调用
    if self._all_completed():
        return None
    if select_dispatchable(compute_frontier(self.graph)):
        return None  # 还有活能派，没卡死
    # 无 ready 可派、又没全完成 → 剩下的未完成节点都被 FAILED 挡住
    blocked = []
    for node in self.graph.nodes.values():
        if node.status in (Status.PENDING, Status.BLOCKED):
            blockers = [d for d in node.depends_on
                        if self.graph.nodes[d].status == Status.FAILED]
            if blockers:
                blocked.append((node, blockers))
    failed = [n for n in self.graph.nodes.values() if n.status == Status.FAILED]
    return StallReport(failed=failed, blocked=blocked)
```

注意：not_done 节点（worker 在等 feed）**不算卡死**——它不是 FAILED，调度器只是在休眠等用户回话。卡死专指「被永久 FAILED 挡死、无用户介入无法前进」。

**为什么只通报、不自动决策**：卡死后的选择（重试 / 改计划 / 跳过 / 接受部分结果）是业务决策，不能由 Harness 的确定性代码替用户做。Harness 的职责是精确描述「什么卡住了什么」，不是「该怎么办」。

### 9.4 用户响应卡死

```
Harness → 群聊: "C(测试) 等待 B(前端)，B 已永久失败。请决定。"

用户: 重试 B
  → decide → feed(B)          ← 跟「回答 worker 问题」是同一个 feed

用户: 跳过测试，直接上线
  → decide → replan(去掉 C)   ← 跟「改方案」是同一个 replan

用户: 算了，就这样吧
  → decide → done             ← 接受部分结果
```

**没有新 action，没有新通道。** Harness 通报的事实进入 transcript 后，用户回复跟任何其他消息一样进 decide → dispatch。feed/replan/done 的语义在异常场景下完全复用。

### 9.5 Worker 失控（20-30 轮）

Worker 连续多轮 dispatch 不交卷：

```
Turn 1: worker 说话"我先看看项目结构..." → 流结束 → not_done → 等 feed
Turn 2: feed → resume → worker 说话"有几个方案..." → 流结束 → not_done
Turn 3: feed → resume → worker 说话"还需要确认..." → 流结束 → not_done
...
```

**已取消 dispatch budget**（原「3 轮硬截断」）——理由见 §6.8 / [[coordinator-v4-event-driven]] 决策 7：budget 区分不了「空转」和「正常多轮提问」，会误杀后者。

改靠两条（§6.8）：

- **Planner 判断**（主力）：每次 feed 都经 decide，Planner 从 transcript 看到「这个 worker 转了很多轮还没产出」，可以选择停止追问、改派他人、或问用户「要不要换个思路」。这是带语义的判断，不是机械计数。
- **wall-clock 超时**（兜底）：截「单次 dispatch 一轮太久」（worker 卡在一次执行内的死循环）。

两者覆盖两种失控：Planner 管「转太多轮」，超时管「一轮太久」。

配合 wall-clock 超时（v2 §5 机械卡死检测）覆盖另一种失控：worker 在单次 dispatch 内陷入死循环。两者互补——预算截「太多轮」，超时截「一轮太久」。

---

## 10. 上下文管理：按视野分层供给

Planner 的两个视野用两档上下文：

| 视野 | 供给 | 落点 |
|------|------|------|
| **reactive**（decide） | 近窗口 15 条 transcript（每条截断）+ members 能力 + active_plan 投影 | ContextBuilder 轻档 |
| **deliberate**（plan/replan） | 结构化需求+约束（handoff）+ 可选探仓库（只读工具）+ DAG 快照 + 任务结果摘要 | ContextHandoff + 工作上下文 |

- handoff 保留为独立组件：讨论→任务时从完整历史+L1 memory 压缩出结构化需求+约束，喂给 `Planner.plan()`。
- 「无状态」= 不自持可变状态、每次读 SessionState；**不等于「无上下文」**。

---

## 11. 两档 LLM 成本纪律

```
reactive 调用（轻，每条非反射消息）:
    Planner.decide(state) → respond | multi | feed | note | done | task | replan
                                                                     │       │
deliberate 调用（重，仅 task/replan 时）:                             ▼       ▼
    Planner.plan(state)  → 完整 DAG（decompose 或 re-decompose）
```

- 多数聊天止于 reactive 一次轻调用
- 判 `task` 或 `replan` 才进 deliberate 出 DAG
- `replan` 和 `task` 同档成本——都是一次 deliberate 重 LLM
- reactive 前还有零 LLM 反射快路（@mention/control/broadcast）

---

## 12. 完全体场景

```
用户: 帮我做个博客系统
  → decide → task → plan → DAG: A(后端) → B(前端) → C(测试)

用户: 后端用 FastAPI 还是 Express？
  → decide → respond(后端阿强)          ← 同一扇门，没有模式切换

后端阿强: FastAPI
  → decide → done
  ──── A 完成，B 开始 ────

前端小美（worker CLI）: 用 Markdown 还是 CMS？
  → 文本推送群聊                        ← 正常说话，不是 ask tool
  → 流结束 → not_done                  ← 没交卷，等回复

用户: 你怎么看？
  → decide → feed(前端小美)            ← 从 transcript 自然看到对话连续性

前端小美 resume: 倾向 Markdown。继续。
  → 继续干活 → task_complete("完成") → 验收 → COMPLETED

──── 一切同时发生 ────

用户: 做得怎么样了？
  → decide → respond(后端阿强)         ← 即时回复，不是石沉大海

后端阿强: 后端和前端都完成了，测试在跑。

用户: 注意前端用 React
  → decide → note(who=("前端小美"))   ← 入前端小美的 pending_notes

──── C 完成 ────

Orchestrator: 3 个任务，3 完成 → 推群聊
  → active_plan 回到 None             ← 自然回到纯聊天，没有「退出执行态」

用户: @前端小美 加个暗色模式
  → @mention 直达

用户: 帮我加个暗色模式切换
  → decide → task → 新的 DAG          ← 新一轮任务
```

**整个过程中没有出现**：
- `if run is not None:` 分支路由
- PAUSED 状态 / `_feed_event` / 显式 resume
- `ask` tool
- 执行态下群聊死亡（闲聊被 `enqueue_note` 吞掉）
- DiscussionOrchestrator / Selector / CoordinatorGate
- 模式切换

### 12.1 场景：执行期改计划（replan）

```
──── B(前端) 正在跑，C(测试) 等 B ────

用户: 别做博客了，改成文档站
  → decide → replan(requirement="改成文档站")

ChatService:
  → Planner.plan(当前 DAG 快照 + "改成文档站")
  → 新 DAG: A'(后端) → B'(前端) → C'(测试)   ← A 改成文档站 API
  → Orchestrator.replan(new_tasks):
      - A(后端) COMPLETED 但已不在新计划 → 保留但不复用（成果不回滚，但不连到新图）
      - B(前端) RUNNING → cancel
      - 新图: A'→B'→C' 全部 PENDING
  → 恢复调度: dispatch A'

Orchestrator → 群聊: "计划已更新：原后端成果保留，前端已取消。新计划 A'(文档站后端) → B'(文档站前端) → C'(测试)"

──── 继续按新 DAG 执行 ────
```

### 12.2 场景：Step 永久失败 + 用户决策

```
──── B(前端) 验收失败 3 次 ────

Orchestrator → 群聊: "B(前端) 已永久失败（npm run build 报错）。C(测试) 等待 B，已阻塞。请决定。"

用户: 重试 B
  → decide → feed(B)          ← feed 复用：重新 spawn B 的 worker

──── B 再次执行... ────

# 或者：

用户: 跳过前端测试，只跑后端测试
  → decide → replan(去掉 B，C 只依赖 A)
  → Planner.plan → 新 DAG: A → C
  → Orchestrator.replan: 移除 B，C 解除阻塞
  → 恢复调度: dispatch C

──── 继续 ────

# 或者：

用户: 算了，就这样吧
  → decide → done             ← 接受部分结果，静默
```

---

## 13. 实现状态与路线

### 13.1 当前状态

| 模块 | 状态 | 说明 |
|------|------|------|
| **前门路由** | ✅ 90% | 纯对话态 decide 单点完成；执行态仍走简化 feed（1c-exec 未做） |
| **ReactiveRouter** | ✅ 完成 | respond/multi/task/feed/done 五种 action；缺 replan |
| **SessionState** | ✅ DTO | 手工构造，缺 `from_session` 工厂 |
| **Orchestrator** | ✅ 基础功能 | DAG 调度 + 验收；**仍是轮询循环**（R0 改事件驱动）；仍含 PAUSED/`_waiting_node_key`（R1 删）；resume 机制**保留** |
| **Executor** | ✅ 基础功能 | task_complete 检测；worker 文本未推群聊（R1 改）；缺上游 summary 注入 |
| **跨 Worker 可见性** | ❌ 缺口 | 上游 summary 未注入；进度通报不入 transcript（R4 补） |
| **task_complete MCP** | ✅ 完成 | 唯一保留的结构化信号 |
| **异常通报** | ❌ 未实现 | 终端状态不推群聊（R4） |
| **replan** | ❌ 未实现 | decide 无 replan action；Orchestrator 无图手术（R5） |
| **ask MCP tool** | ❌ 待删 | R1 删除 |
| **resume 机制** | ✅ 保留 | `pending_answer` + CLI `--resume`。feed 的前提，**不删**（[[coordinator-v4-event-driven]] 决策 5） |
| **CoordinatorGate** | ✅ 已删 | — |

**残留旧代码待删**：`selector.py`（17KB，含 L2 keyword）、`discussion_orchestrator.py`（12KB，三处 wiring）、轮询 `run()` 循环

### 13.2 待做（事件驱动重构，对照 [[coordinator-v4-event-driven]]）

| 步 | 内容 | 涉及 | 风险 |
|----|------|------|------|
| **R0** | **Orchestrator 轮询循环改事件驱动**：`run()` for 循环 → `on_start/on_node_complete/on_node_failed/on_feed` 事件处理器；删 `_waiting_node_key`/`_await_feed_and_resume` | `orchestrator.py` | **大** |
| **R1** | 协议重塑：删 `ask` tool + PAUSED 态；not_done 不走 FAILED（等 feed）；executor 文本推群聊；**resume 保留不动** | `executor.py`、`orchestrator.py`、`mcp_step_tools.py`、`enums.py`、`fsm.py` | 中 |
| **R2** | 路由统一：`SessionState.from_session` + `plan_view()`；删 `if run is not None` 分支，执行态走 `decide → dispatch`；旁路消息按 worker 分桶 | `session_state.py`、`coordinator_run.py`、`chat_service.py`、`reactive_router.py` | 中 |
| **R3** | 多轮讨论并进 decide for 循环 + already_responded；删 `DiscussionOrchestrator` + `Selector` L2 | `chat_service.py`、多处 wiring | 小 |
| **R4** | 可见性 + 异常通报：上游 summary 注入 instruction；终端状态写 messages 入 transcript | `executor.py`、`orchestrator.py` | 小 |
| **R5** | replan：decide 加 `replan` action + `on_replan` 图 diff + swap；**破坏性才出 diff 求确认** | `reactive_router.py`、`chat_service.py`、`orchestrator.py` | 大 |

依赖：**R0 是地基**（事件驱动重写，配套测试），R1 依赖 R0。R4 不碰控制流，可与 R2/R3 并行早做。R5 最后，唯一带「破坏性确认」。

---

## 14. 关键设计决策

| 决策 | 结论 | 位置 |
|------|------|------|
| 大脑数量 | 一个 Planner，两种视野（reactive + deliberate） | §1 |
| **调度模型** | **事件驱动**（启动/依赖完成/feed 三触发点），非轮询循环。拔掉 v3「状态×模式×轮询」组合爆炸的根 | §6.2 |
| DAG 状态唯一写者 | Orchestrator。Worker 只发信号（task_complete），不改状态 | §6.6 |
| 跨 Worker 信息 | 上游 summary 注入 instruction + 进度通报入 transcript。Worker 只知「自己的活+上游做了什么+用户补了什么」 | §6.7 |
| Harness 角色 | 确定性骨架，零 LLM。图遍历 + FSM + 验收 + 状态写入 | §1 |
| LLM 调用档位 | 两档：reactive decide（轻）+ deliberate plan（重，含 replan） | §11 |
| 执行引擎统一吗 | 路由层统一；执行引擎不统一（respond 轻 / work 重） | §2.1 |
| 任务有几种状态 | 两种：DONE（COMPLETED）和 NOT DONE（其他所有） | §2.2 |
| 按不按「态」分路由 | 不分。`active_plan` 是 Planner 输入字段，不是路由分支条件 | §2.3 |
| Worker 怎么提问 | 正常说话，文本推群聊。不需要专用 tool | §2.4 |
| Worker 怎么交卷 | `task_complete(summary)`——唯一结构化信号 | §2.4 |
| Worker 没交卷流就结束了 | `not_done`——不是失败，就是没做完。无事件触发，调度器休眠等 feed | §2.5 |
| Worker 卡住了怎么办 | Planner 从 transcript 自然看到，在 respond 里顺带提醒 | §6.8 |
| feed 语义 | 重新派发 worker（`--resume` 续上下文），不是「唤醒 PAUSED step」。resume 机制保留 | §7.2 |
| 多轮讨论 | strip → keep：反复 decide | §5 |
| 执行期改计划 | `replan` action → Planner.plan 重新分解 → Orchestrator DAG 手术（§8） | §8 |
| DAG 手术铁律 | COMPLETED 不回滚；受影响的 RUNNING cancel；原子换图 | §8.3 |
| **replan 破坏性确认** | 要 cancel RUNNING / 丢 COMPLETED 成果 → Harness 算 diff → 先求确认；纯新增/改 PENDING → 直接换 | §8.2 |
| 异常通报 | Harness 通报事实到群聊 → 进入 transcript → Planner 读 → 用户决定 | §9.2 |
| 卡死不自动决策 | 重试/跳过/改计划是业务决策，Harness 只描述「谁卡住了谁」 | §9.3 |
| **resume 机制** | 保留（`pending_answer` + `--resume`）。续上下文，feed 的前提；resume 句柄是数据不是状态 | §13.1 |
| Worker 失控 | **取消 dispatch budget**；改 Planner 从 transcript 判断 + wall-clock 超时兜底 | §6.8 §9.5 |
| replan vs feed vs note | 改方向→replan / 接话→feed / 补约束→note。Planner 从 transcript 区分 | §8.4 |
| capability 关键词层 | 删除 | §13.1 |
| @agent+任务 | 走 respond（显式 @ = 找人聊） | §4.1 |

---

## 附录 A：与 v2/v3 的复用与取代边界

| v2 章节 | v4 处置 |
|---------|---------|
| §1–§7 Harness/DAG/FSM/验收/worktree/事件溯源 | **复用**（一字不变） |
| §11 Selector×Coordinator 边界 | **取代**：不再有 Selector，Planner 统一决策 |
| §13 前门接线 / §13.5 A1 decompose 预闸门 | **取代**：单 Planner 路由，无白名单 |

| v3 章节 | v4 处置 |
|---------|---------|
| §1–§10 大脑/路由/SessionState/上下文/成本纪律/落地分步 | **复用思想，细节更新** |
| §11 step = 有界对话（ask tool + PAUSED + resume） | **推翻**：简化为 DONE/NOT DONE + 自然对话 |
| §11.6 旁路消息队列 | **保留并改进**：按 worker 分桶 |

---

## 附录 B：相关文档索引

| 文档 | 位置 |
|------|------|
| v3 原始设计（已归档） | `../v3/coordinator-design-v3.md` |
| 推理链：为什么简化 | `../v3/design-evolution-why-simplify.md` |
| 简化决策记录 | `../../../../worklogs/decisions/simplify-step-tools-no-ask-paused.md` |
| 步 2 实现规格 | `../v3/coordinator-v3-step2-unified-loop-spec-v2.md` |
| 步 1 实现方案 | `../v3/coordinator-v3-step1-unified-router-plan.md` |
| 场景演练 | `../v3/coordinator-scenario-v3.md` |
