# Coordinator v3 场景推理 — 数据传递与函数调用全链路

> 日期：2026-06-07 | 配套 [[coordinator-design-v3]]
> 目的：用一个端到端场景，把 v3 的「前门统一路由」+「work step 内 ask 往返」的**真实函数调用与数据形状**走清楚。
> 标注规则：`[现有]`=v2 已实现、v3 一字不改复用；`[v3改]`=改现有函数；`[v3新]`=新增。
> 代码锚点全部核对过真实签名（executor.py / orchestrator.py / dag.py / ports.py / protocol.py / chat_service.py / claude_code_runtime.py）。

---

## ⚠️ 蓝图 vs 代码：实现偏离（截至 2026-06-07，步3 已落地）

本文档是**设计蓝图**。§3–5（step-tools 执行层）已实现（步3），但有 4 处代码与蓝图不同；§1（前门统一路由）整章**未实现**（= 步1，见 [[coordinator-v3-step1-unified-router-plan]] + [[coordinator-scenario-v3-step1]]）。读本文时按下表折算：

| # | 蓝图位置 | 蓝图写法 | 代码实际 | 评价 |
|---|---------|---------|---------|------|
| 1 | §3.2 / §4.4 | `session_key = uuid5(S:step_id)`（step 级隔离） | `uuid5(S:agent_id)`（agent 级），靠同 worker resume 同会话 | 偏离：MVP 串行下等价；多 step 派同一 worker 会串上下文。已在 `build_task_request` 注释标注 |
| 2 | §4.2 | node_B「保持 RUNNING，不 transition」 | `RUNNING→PAUSED`（FSM 已有 PAUSED 态） | 偏离但**代码更干净**：用真状态，不赖在 RUNNING |
| 3 | §4.2 | `_post_ask_to_group`（Orchestrator 发问） | MCP `ask` tool handler 在 CLI 进程内直接落库+WS 广播（Sidecar Effect） | 偏离：发问主体是 MCP handler 不是 Orchestrator；Orchestrator 只转 PAUSED + 记 waiting key |
| 4 | §3.3 | 缺终结工具 → `resume 追一刀`（保住半成品） | `needs_reprompt → FAILED → 重试全新派发`（丢上下文） | 偏离：代码更糙，未做定向 resume+reprompt |

另：§4.3 答案路由（`Planner.decide` 返回 `action="feed"`）依赖步1，现用 `chat_service` 简化路由（执行态非 control 消息 → feed 第一个 waiting step）顶替；**步1 落地后自然收敛为蓝图写法**。

---

## 0. 场景设定

**群组**：`group#blog`，dispatch_mode=DISCUSSION，成员 3 个 agent：

| name | id（示意） | capability | runtime |
|------|-----------|-----------|---------|
| 后端阿强 | `a-be` | backend, api | claude_code（CLI） |
| 前端小美 | `a-fe` | frontend, ui | claude_code（CLI） |
| 测试小测 | `a-qa` | testing | claude_code（CLI） |

**用户输入**（trigger Message）：

```python
Message(session_id=S, role=USER, content="帮我做个博客系统，要能发文章")
```

我们追踪它从前门进来，到产出一张 3 步 DAG，其中 **step_B（前端）中途 ask 一次**，用户回答后 resume 完成。

---

## 1. 前门路由：一次 reactive Planner 决策（取代 gate+selector）

### 1.1 入口 `[现有]` `ChatService.handle_user_message(session, group, trigger)`

现状前门（chat_service.py:176-202）是 **gate 预滤 → is_decompose → selector** 三段。v3 把中间整段换掉。

```python
# chat_service.py 前门，v3 改造点
text = trigger.content
run = self._registry.get(session.id)          # [现有] CoordinatorRun | None

if run is not None:                            # [现有] 已有任务在跑
    if self._is_control(text):                 # [v3改] is_control 从 gate 移入 ChatService 前置反射
        await self._cancel_coordinator(session, run)
    else:
        decision = await self._planner.decide(state)   # [v3新] active_plan 非空分支 → 见 §4
    return

# ↓↓↓ 删掉 has_work_intent / is_decompose 整段（白名单消失）
decision = await self._planner.decide(state)   # [v3新] 唯一一次 reactive LLM 决策
```

### 1.2 构造 `SessionState` `[v3新]`（两条事件流的只读投影，design §3）

```python
state = SessionState(
    session_id = S,
    group      = group,                        # [现有] Group 实体
    members    = [a_be, a_fe, a_qa],           # [现有] list[Agent]
    transcript = await msgs.list_by_session(S, limit=15),  # [现有] 复用 _recent_history
    active_plan = None,                         # ← 此刻纯对话态（无任务在跑）
    constraints = [],
    run_handle = None,
    watermarks = {...},                         # [现有] Redis 读位
)
```

> `active_plan is None` ⟺ 纯对话态。**没有 mode 枚举**，态由 active_plan 派生（design §3）。

### 1.3 `[v3新]` `Planner.decide(state) -> PlannerDecision`

reactive 视野：喂近窗口（15 条截断，design §7 reactive 轻档），**零工具**。LLM 通过 tool_use 返回结构化决策（复用 selector.py:301 的 tool_use 解析范式）。

```python
@dataclass(frozen=True)
class PlannerDecision:           # [v3新]
    action: Literal["respond","multi","task","replan","feed","done"]
    who: str | None = None       # respond/multi 的目标 agent name
    feed_step: str | None = None # feed 的目标 step_id（§4）
    answer: str | None = None    # feed 的答案文本
    # task / replan 不在 reactive 出，只出信号，详细 DAG 由 deliberate plan() 给

# 本场景返回：
PlannerDecision(action="task")   # ← 判定为 NEEDS_TASK
```

> 对比 v2：这一步替代了 `gate.has_work_intent`（正则白名单，会漏"可以直接干吧"）+ `gate.is_decompose`（独立 LLM）+ `selector`。**承接语理解放进 Planner system prompt，不硬编码**（design §9 步1）。

---

## 2. deliberate 分解：`action="task"` → 出 DAG

### 2.1 `[现有]` `ChatService._start_coordinator(session, group, trigger)`

（chat_service.py:213）几乎不变——它本就是"收到 decompose 信号 → 起后台 Orchestrator"。v3 只是触发它的判定从 `is_decompose` 变成 `decision.action=="task"`。

```python
run = CoordinatorRun(session_id=S)                       # [现有]
if not self._registry.try_reserve(S, run): ...           # [现有] 同步占位防并发
orchestrator = await self._build_orch(                   # [现有]
    task=trigger.content, members=[a_be,a_fe,a_qa], session=session, group=group)
run.start(orchestrator, on_done=..., on_error=..., registry=self._registry)  # [现有] fire-and-forget
```

### 2.2 `[现有]` `Orchestrator.run()` 第一步：`Planner.plan(ctx)`

`_build_orch` 内组装 `PlanContext`（ports.py:50），喂给 deliberate plan：

```python
ctx = PlanContext(                                # [现有]
    task    = "帮我做个博客系统，要能发文章",
    workers = ("后端阿强","前端小美","测试小测"),   # = group 成员名，build_graph 校验用
    repo_tree = "<git ls-files 快照>",
    constraints = (),                              # 本场景无硬约束
    agents_desc = "后端阿强: backend,api\n前端小美: frontend,ui\n测试小测: testing",
)
defs: list[TaskDef] = await self._planner.plan(ctx)   # [现有] 唯一重 LLM 调用（deliberate）
```

产出（示意，TaskDef 见 dag.py:38）：

```python
defs = [
  TaskDef(id="A", title="后端：文章 CRUD API", suggested_worker="后端阿强",
          depends_on=[], acceptance=[Check(kind="mechanical", spec="pytest tests/api")]),
  TaskDef(id="B", title="前端：文章列表+发布页", suggested_worker="前端小美",
          depends_on=["A"], acceptance=[Check(kind="mechanical", spec="npm run build")]),
  TaskDef(id="C", title="端到端测试", suggested_worker="测试小测",
          depends_on=["A","B"], acceptance=[Check(kind="mechanical", spec="npm run e2e")]),
]
```

### 2.3 `[现有]` `build_graph(defs, {"后端阿强","前端小美","测试小测"})`

dag.py:77 校验（悬空依赖/未知 worker/无验收/环）→ 编译 `TaskGraph`：

```python
graph = TaskGraph(nodes={
  "A": TaskNode(task=defs[0], status=PENDING),
  "B": TaskNode(task=defs[1], status=PENDING),
  "C": TaskNode(task=defs[2], status=PENDING),
})
```

随后 `_emit_plan()`（orchestrator.py:153）→ ProgressSink 推前端 `task_plan` 事件（分发方案卡）。

---

## 3. 执行循环 step_A：闷头做完（大多数 step 走这条，零额外成本）

### 3.1 `[现有]` 调度选就绪集

```python
ready = select_dispatchable(compute_frontier(graph), running_count=0, max_concurrency=1)
# → ["A"]（B/C 依赖未满足）
await self._execute_and_settle(graph.nodes["A"])     # orchestrator.py:73
```

### 3.2 `[现有]` `_execute_and_settle(node_A)` → `Executor.run(node_A)`

FSM：PENDING→QUEUED→RUNNING（orchestrator.py:74-75），`_emit_update(node,"running")` 推前端。然后：

```python
outcome = await self._executor.run(node_A)            # [现有] AgentExecutor.run
```

`AgentExecutor.run`（executor.py:91）内部：

```python
agent = self._resolve("后端阿强")                      # [现有] → Agent(a_be)
request = build_task_request(node_A, agent, session_id=S, group_id=G, workspace=ws)
# [v3改] session_key：从 uuid5(S:agent_id) 改为 uuid5(S:step_id) —— step 级隔离（design §11.3#1）
adapter = self._adapter_factory(agent)                # [现有] claude_code runtime
# [v3改] build_task_request 注入 --mcp-config 指向 step-tools（task_complete + ask）
output = await self._consume(adapter, request)        # 见 §3.3
```

### 3.3 `[v3改]` `Executor._consume`：新增终结工具检测 + 完成闸门

现状 `_consume`（executor.py:119）只看 TEXT/ERROR/REQUEST_APPROVAL。v3 加 **TOOL_CALL 终结检测**：

```python
async for evt in adapter.stream(request):             # [现有] 流式
    if evt.type == TEXT:        chunks.append(evt.content)         # [现有]
    elif evt.type == TOOL_CALL:                                    # [v3新]
        name = evt.tool_call.name      # claude_code_runtime.py:539 已填好
        if name.endswith("__task_complete"):
            done_summary = evt.tool_call.arguments["summary"]
        elif name.endswith("__ask"):
            ask_q = evt.tool_call.arguments["question"]
        # 原生工具 Read/Write/Bash 名字不匹配 → 忽略（design §11.0）
    elif evt.type == ERROR:     errored = evt.content              # [现有]

# DONE 后判定（完成闸门，design §11.3）：
if done_summary is not None:
    return WorkerOutcome(ok=True, status="completed", output=done_summary)   # [v3改]
if ask_q is not None:
    return WorkerOutcome(ok=True, status="waiting", ask=AskInfo(ask_q, step_key))  # [v3新]
# 两个终结工具都没调 → 不接受 turn-end，调用方 resume 追一刀（§3.4 不触发，step_A 正常 done）
return WorkerOutcome(ok=False, status="needs_reprompt", output="未调用终结工具")  # [v3新]
```

step_A 的 worker 干完调了 `task_complete`：

```python
# stream-json 实际事件（claude_code_runtime._parse_line 产出）：
StreamEvent(type=TOOL_CALL, tool_call=ToolCall(
    call_id="tu_01", name="mcp__step-tools__task_complete",
    arguments={"summary": "实现 /api/articles CRUD + pytest 通过"}))
# → WorkerOutcome(ok=True, status="completed", output="实现 /api/articles CRUD...")
```

`WorkerOutcome` 扩展（ports.py:29，v3 加 status/ask 两字段）：

```python
@dataclass(frozen=True)
class WorkerOutcome:            # [v3改]
    ok: bool
    status: Literal["completed","waiting","needs_reprompt","error"] = "completed"  # [v3新]
    output: str = ""
    ask: AskInfo | None = None  # [v3新]

@dataclass(frozen=True)
class AskInfo:                  # [v3新]
    question: str
    step_key: str               # = uuid5(S:step_id)，resume 时复用同 key
```

### 3.4 `[现有]` 结算 → 验收 → COMPLETED

```python
node_A.output = outcome.output                        # [现有]
self._transition(node_A, VERIFYING)                   # [现有]
verdict = await self._verifier.verify(node_A)         # [现有] 跑 `pytest tests/api`
# verdict = Verdict(passed=True)
self._transition(node_A, COMPLETED)                   # [现有]
await self._emit_update(node_A, "done")               # [现有] 推前端进度
```

> **summary 的去向**（design §11.0）：`node_A.output` 进 `_build_summary`（给用户的收尾汇总）、且作为下游 step_B 的上下文摘要（v2 §4 三流）。

---

## 4. 执行循环 step_B：worker 中途 ask → 往返 → resume（v3 核心红利）

### 4.1 `[现有]→[v3改]` 派发 step_B，worker 调 `ask`

```python
ready = select_dispatchable(...)   # → ["B"]（A 已 COMPLETED）
await self._execute_and_settle(graph.nodes["B"])
# _execute_and_settle → executor.run(node_B) → _consume
```

前端小美的 worker 读了一圈代码后，发现存储方式没定，调 `ask`：

```python
# stream-json 实际事件：
StreamEvent(type=TOOL_CALL, tool_call=ToolCall(
    call_id="tu_07", name="mcp__step-tools__ask",
    arguments={"question": "文章存储用 Markdown 文件还是接 CMS？"}))

# _consume 返回：
WorkerOutcome(ok=True, status="waiting",
    ask=AskInfo(question="文章存储用 Markdown 文件还是接 CMS？",
                step_key=uuid5(S, "B")))           # [v3新]
```

### 4.2 `[v3新]` `_execute_and_settle` 处理 `status=="waiting"`

**关键：node_B 状态保持 RUNNING，不进 VERIFYING，不 propagate_blocked**（design §11.3 step3）。

```python
outcome = await self._executor.run(node_B)
if outcome.status == "waiting":                       # [v3新] 分支
    node_B.step_key = outcome.ask.step_key            # [v3新] 存 resume key 到 node
    node_B.dispatch_count += 1                         # [v3新] 预算计数（design §11.5）
    # node_B.status 保持 RUNNING（不 transition！）
    await self._post_ask_to_group(node_B, outcome.ask.question)  # [v3新] 问题作为 agent 消息发群里
    return     # ← 不结算，挂起等答案；其他就绪节点（无）照常，run 循环 await 外部信号
```

`_post_ask_to_group` 落一条 agent 消息（前端小美发问），经 WS 推前端。用户在群里看到：

> **前端小美**：文章存储用 Markdown 文件还是接 CMS？

此刻 DAG 状态：`A=COMPLETED, B=RUNNING(waiting), C=PENDING`。run 协程挂起等 UserInterrupt/feed 信号（复用 v2 §2.2 事件循环；MVP 用 asyncio.Event/queue）。

### 4.3 用户回答 → 回到前门 → Planner 路由到 feed

```python
# 用户新消息：
Message(session_id=S, role=USER, content="用 CMS，接 Strapi")

# ChatService 前门：run 非空 → 非 control → Planner.decide(state)
state.active_plan = <TaskGraph 投影：A=COMPLETED, B=RUNNING-waiting, C=PENDING>  # [v3新] 非 None！
state.transcript[-2:] = [前端小美的 ask, 用户的回答]

decision = await self._planner.decide(state)          # [v3新] active_plan 非空分支
# Planner 读到：B 在 waiting、上一条 agent 消息是 B 的 ask、这条是用户回答
# → 返回：
PlannerDecision(action="feed", feed_step="B", answer="用 CMS，接 Strapi")  # [v3新]
```

> **这就是 design §11.4 的"同一张地图"**：Planner 不是看到"一条插话撞上一个 DAG"，而是读同一份 SessionState（含各 step 状态），判出这是回答 B 的 ask，而非 chitchat/replan。

### 4.4 `[v3新]` feed 信号进 run → resume dispatch step_B

```python
# ChatService 把 feed 投递给 run 句柄：
run.feed(step_id="B", answer="用 CMS，接 Strapi")      # [v3新] → 唤醒挂起的 run 循环

# Orchestrator 收 feed → 二次派发 node_B（resume）：
request = build_task_request(node_B, agent_fe, ...)
request.has_history = True                             # [v3改] → CLI 走 --resume
# session_key = node_B.step_key（同 key！design §11.3#1）—— 自动加载 Turn1 全上下文
request.messages = [{"role":"user","content":"用户回复：用 CMS，接 Strapi。请继续。"}]
outcome = await self._executor.run(node_B)            # [现有] 同一个 run 接口，第 2 次
```

worker resume 后继续，最终调 task_complete：

```python
StreamEvent(type=TOOL_CALL, tool_call=ToolCall(
    name="mcp__step-tools__task_complete",
    arguments={"summary":"前端完成：Strapi 集成 + 文章列表 + 发布页"}))
# → WorkerOutcome(ok=True, status="completed", output="前端完成：Strapi...")
```

### 4.5 `[现有]` 结算 step_B → COMPLETED

```python
node_B.output = outcome.output
self._transition(node_B, VERIFYING)
verdict = await self._verifier.verify(node_B)          # 跑 `npm run build`
self._transition(node_B, COMPLETED)
await self._emit_update(node_B, "done")
```

> **预算兜底**（design §11.5）：若 worker 反复 ask 超过 `node.dispatch_count > 3` → `_handle_failure` → FAILED → 升级问用户。本场景 1 次 ask，正常。

---

## 5. step_C + 收尾

```python
ready = select_dispatchable(...)   # → ["C"]（A、B 均 COMPLETED）
await self._execute_and_settle(graph.nodes["C"])       # 测试小测，闷头做，e2e 通过 → COMPLETED
# 下一轮 ready = [] → _terminal()
```

`[现有]` `Orchestrator._terminal()`（orchestrator.py:108）：

```python
summary = self._build_summary()   # 机械拼，零 LLM（orchestrator.py:120）
# "任务执行结束：3 个任务，3 完成 / 0 未完成。
#  - 后端：文章 CRUD API：✅ 已完成（验收通过：pytest tests/api）
#  - 前端：文章列表+发布页：✅ 已完成（验收通过：npm run build）
#  - 端到端测试：✅ 已完成（验收通过：npm run e2e）"
await self._emit_summary(summary)                       # text + done 推前端
return RunResult(ExitReason.COMPLETED, summary)
```

`run.start` 注册的 `on_done`（chat_service.py:238）把 summary 作为协调者消息发群里，`registry.release(S)`。回到纯对话态（active_plan→None）。

---

## 6. 全链路数据形状一览（关键跳）

| # | 跳 | 函数 | 输入 | 输出 | 标注 |
|---|----|------|------|------|------|
| 1 | 前门 | `Planner.decide(state)` | `SessionState(active_plan=None)` | `PlannerDecision(action="task")` | [v3新] |
| 2 | 分解 | `Planner.plan(ctx)` | `PlanContext(task, workers, …)` | `list[TaskDef]` | [现有] |
| 3 | 建图 | `build_graph(defs, workers)` | `list[TaskDef]` | `TaskGraph` | [现有] |
| 4 | 派发 | `Executor.run(node)` | `TaskNode` | `WorkerOutcome` | [现有]接口/[v3改]内部 |
| 5 | 收流 | `Executor._consume` | `StreamEvent` 流 | `WorkerOutcome(status, ask)` | [v3改] |
| 6 | ask | （worker tool_use） | — | `ToolCall(name=…__ask, args)` | [现有]解析/[v3新]语义 |
| 7 | 挂起 | `_execute_and_settle` waiting 分支 | `WorkerOutcome(waiting)` | node 保持 RUNNING + 发问 | [v3新] |
| 8 | 路由答案 | `Planner.decide(state)` | `SessionState(active_plan≠None)` | `PlannerDecision(action="feed")` | [v3新] |
| 9 | resume | `Executor.run(node)` 第2次 | `TaskNode(step_key, has_history=True)` | `WorkerOutcome(completed)` | [现有]接口/[v3改] |
| 10 | 收尾 | `Orchestrator._terminal` | graph 终态 | `RunResult(COMPLETED, summary)` | [现有] |

---

## 7. v3 改动落点清单（按本场景出现顺序）

| 落点 | 文件 | 性质 | design 依据 |
|------|------|------|-------------|
| 前门换 `Planner.decide`，删 gate 白名单 | `chat_service.py` / 新 `planner` | [v3改]+[删] | §4、§9步1 |
| `SessionState` 两流投影 | 新 `session_state.py` | [v3新] | §3 |
| `PlannerDecision` / reactive 决策 | 新 `planner` | [v3新] | §2.2、§5 |
| `WorkerOutcome` 加 status/ask | `ports.py` | [v3改] | §11.3 |
| `_consume` 加 TOOL_CALL 终结检测 + 完成闸门 | `executor.py` | [v3改] | §11.0、§11.3 |
| step 级 session_key + `--mcp-config` 注入 step-tools | `executor.py` / `build_task_request` | [v3改] | §11.3#1#2 |
| `_execute_and_settle` 加 waiting 分支 | `orchestrator.py` | [v3新] | §11.3 |
| `run.feed()` + resume 派发 | `coordinator_run.py` / `orchestrator.py` | [v3新] | §11.3、§11.4 |
| step-tools MCP server | 新 `api/mcp_step_tools.py` | [v3新] | §11.2 |

> **骨架零改**：`build_graph` / `compute_frontier` / `select_dispatchable` / `TaskFSM` / `_transition` / `_build_summary` / `Verifier` 全部 [现有] 不动——v3 只动"大脑"（前门 Planner）和"手与骨架的接口"（ask/resume），**不动 DAG 调度内核**。这正是 design §0「只动大脑和前门，不动骨架和手」的代码级印证。
