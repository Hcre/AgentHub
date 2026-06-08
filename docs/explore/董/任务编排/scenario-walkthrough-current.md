# 场景推演 — 基于当前代码（Phase 1-4 已实现）

> 日期：2026-06-06 | 代码版本：63bcc7f
> 范围：task_engine 模块（1139 行），Planner/Executor/Verifier 用 fake 跑通

---

## 模块总览

```
task_engine/                       测试
├── ports.py      (86L)  DTO/Protocol  ├── test_planner.py     (215L)
├── dag.py        (133L) 图校验         ├── test_verifier.py    (167L)
├── fsm.py        (65L)  状态机         ├── test_orchestrator.py(182L)
├── scheduler.py  (59L)  就绪集         ├── test_executor.py   (117L)
├── planner.py    (236L) LLM 分解       ├── test_context.py    (88L)
├── context.py    (148L) 上下文组装      ├── test_dag.py        (109L)
├── verifier.py   (123L) 机械验收       ├── test_fsm.py        (78L)
├── executor.py   (133L) Worker 派发    └── test_scheduler.py  (125L)
└── orchestrator.py(146L) 串行指挥       ──────────────────────────
                                         1081 行，91 passed
```

> 已删：`coordinator.py`（旧 stub）、`harness.py`（旧 PlannedTask）

---

## 场景：用户要求创建登录页面

### Phase 1：触发 → decompose

```
[用户]: 帮我创建登录页面，邮箱+密码+中文错误提示，5次失败锁定30分钟
```

此时 Phase 5 接线未实现。在测试中，通过依赖注入直接构造 Orchestrator：

```python
# 构造 PlanContext（context.py:111 gather_context 产出）
ctx = PlanContext(
    task="创建登录页面，邮箱+密码+中文错误提示，5次失败锁定30分钟",
    workers=("前端Agent", "后端Agent", "测试Agent"),
    agents_desc="- 前端Agent（React/TypeScript）\n- 后端Agent（FastAPI/Python）\n- 测试Agent（pytest/Playwright）",
    repo_tree="frontend/src/components/\nbackend/app/api/\ntests/",
    constraints=("错误提示用中文", "5次失败锁定30分钟"),
)

# 组装协作者（Phase 5 ChatService._start_coordinator 将做这件事）
planner = SeedPlanner(FakeTextLLM())      # planner.py:181
executor = AgentExecutor(...)              # executor.py:69
verifier = MechanicalVerifier(...)         # verifier.py
orch = Orchestrator(planner=planner, executor=executor, verifier=verifier, ctx=ctx)
result = await orch.run()
```

---

### Phase 2：Plan（planner.py:187-197）

```
Orchestrator.run()
  │
  ├─ defs = await self._planner.plan(self._ctx)     ← LLM 分解
  │
  │   Planner 内部（planner.py:187-197）:
  │     1. 检查 workers 非空（L188-189）
  │     2. 组装 prompt = SYSTEM_PROMPT + build_user_prompt(ctx)
  │        → 含 task + constraints + agents_desc + repo_tree
  │     3. _plan_with_parse_retry(base_prompt)（L192）
  │        ├─ _complete_with_backoff(prompt) → TextLLM.complete()
  │        │   ├─ 瞬时错误（Timeout/Connection）→ 退避重试 ≤2 次（L234-243）
  │        │   └─ 非瞬时错误（auth 等）→ 不重试（L244-245）
  │        └─ extract_json(text) → 三层回退（L67-75）
  │            ├─ ① 整段 json.loads + ast.literal_eval
  │            ├─ ② code fence 剥离
  │            └─ ③ 首个平衡 {} 块
  │        解析失败 → PlanParseError → 带反馈重试 ≤3 次（L215-230）
  │     4. parse_task_defs(raw)（L193）
  │        ├─ 非 mechanical acceptance → PlanParseError
  │        ├─ depends_on 去重
  │        └─ 重复 id → PlanParseError
  │     5. build_graph(defs, workers)（L194）
  │        ├─ 环检测 → DagValidationError
  │        ├─ 悬空依赖 → DagValidationError
  │        ├─ 未知 worker → DagValidationError
  │        └─ 空 acceptance 未标 no_verify → DagValidationError
  │
  ├─ self.graph = build_graph(defs, ...)             ← DAG 编译
  │     → TaskGraph(nodes={
  │         "t-fe": TaskNode(task=TaskDef(...), status=PENDING),
  │         "t-be": TaskNode(task=TaskDef(...), status=PENDING),
  │         "t-e2e": TaskNode(task=TaskDef(..., depends_on=["t-fe","t-be"]), status=PENDING),
  │       })
  │
  └─ self._record("plan_created", "", n=3)           ← 内存事件
```

**FSM 状态**：全部 PENDING
**LLM 调用**：plan() 内 1-4 次（取决于解析是否成功）

---

### Phase 3：内循环 Round 1 — dispatch t-fe（串行，一次一个）

```
orchestrator.py:57-66 主循环:

max_steps = 3 * (3+1) + 2 = 14   ← 防死循环兜底

for _ in range(14):
    │
    ├─ _propagate_blocked()                              ← L58
    │     → unreachable_pending(graph) = []              ← 尚无失败
    │
    ├─ ready = select_dispatchable(                       ← L60-61
    │     compute_frontier(graph),  → ["t-fe", "t-be"]
    │     running_count=0, max_concurrency=1
    │   )
    │   → ready = ["t-fe"]                                ← 串行只取一个
    │
    └─ await _execute_and_settle(graph.nodes["t-fe"])    ← L65
```

**_execute_and_settle("t-fe")**（orchestrator.py:69-85）：

```
1. _transition(node, QUEUED)           PENDING → QUEUED ✓（fsm.py:20）
2. _transition(node, RUNNING)          QUEUED → RUNNING ✓（fsm.py:21）
3. node.worker = "前端Agent"

4. outcome = await _executor.run(node) ← 派 Worker
   │
   │ Executor.run()（executor.py:91-117）:
   │   ├─ resolve_agent("前端Agent") → Agent 实体
   │   ├─ build_task_request(node, agent, ...) → AgentRequest
   │   ├─ adapter = adapter_factory(agent)
   │   ├─ await _consume(adapter, request)
   │   │     → 消费事件流：TEXT 收集 / ERROR 捕获 / REQUEST_APPROVAL 检测
   │   │     → event_sink 转发（MVP=None, no-op）
   │   └─ return WorkerOutcome(ok=True, output="创建了 LoginForm.tsx…")
   │
   └─ outcome.ok = True ✓

5. node.output = "创建了 LoginForm.tsx…"
6. _transition(node, VERIFYING)        RUNNING → VERIFYING ✓（fsm.py:23）

7. verdict = await _verifier.verify(node)
   │
   │ MechanicalVerifier.verify()（verifier.py）:
   │   遍历 node.task.acceptance:
   │     Check(kind="mechanical", spec="npx tsc --noEmit"):
   │       → asyncio.create_subprocess_shell("npx tsc --noEmit", cwd=...)
   │       → exit 0 → Verdict(passed=True) ✓
   │     Check(kind="mechanical", spec="npm run build"):
   │       → exit 0 → Verdict(passed=True) ✓
   │   全部 pass → Verdict(passed=True)
   │
   └─ verdict.passed = True ✓

8. _transition(node, COMPLETED)        VERIFYING → COMPLETED ✓（fsm.py:30）
```

**FSM 状态**：t-fe=COMPLETED, t-be=PENDING, t-e2e=PENDING
**LLM 调用**：0 次（调度纯函数，执行/验证非 LLM）

---

### Phase 4：内循环 Round 2 — dispatch t-be

```
for 循环第二轮:

_propagate_blocked() → 仍无失败 → []

compute_frontier(graph):
  t-be: status=PENDING, depends_on=[] → 所有依赖已 COMPLETED（vacuously true）→ 就绪 ✓
  t-e2e: status=PENDING, depends_on=["t-fe","t-be"]
         t-fe=COMPLETED ✓, t-be=PENDING → 不满足 → 不就绪

ready = ["t-be"]

_execute_and_settle("t-be"):
  RUNNING → VERIFYING → VERIFIER → COMPLETED
  （同 Phase 3 流程，验收命令：pytest → exit 0）
```

**FSM 状态**：t-fe=COMPLETED, t-be=COMPLETED, t-e2e=PENDING

---

### Phase 5：内循环 Round 3 — t-e2e 就绪

```
compute_frontier(graph):
  t-e2e: depends_on=["t-fe","t-be"], 两者都 COMPLETED → 就绪 ✓

_execute_and_settle("t-e2e"):
  RUNNING → VERIFYING → VERIFIER → COMPLETED
```

**FSM 状态**：全部 COMPLETED

---

### Phase 6：终止

```
Round 4:

compute_frontier(graph) → []  ← 无就绪任务

_terminal()（orchestrator.py:100-108）:
  all(COMPLETED) → True
  → RunResult(COMPLETED, _build_summary())
  
_build_summary()（L111-121）:
  t-fe: ✅ 已完成（验收通过：npx tsc --noEmit; npm run build）
  t-be: ✅ 已完成（验收通过：pytest）
  t-e2e: ✅ 已完成（验收通过：pytest tests/e2e/）
```

---

## 异常路径：Verifier 抓出说谎 Worker

```
t-fe 的 Worker 输出：ok=True, output="做完了"
但 Verifier 跑 "npx tsc --noEmit" → exit 2（类型错误）

_execute_and_settle 第 7 步:
  verdict = Verdict(passed=False, reason="验收失败: npx tsc --noEmit (exit 2)")

_handle_failure(node, "验收失败: npx tsc --noEmit (exit 2)")（L87-92）:
  1. node.fail_reason = reason
  2. _transition(node, FAILED)          VERIFYING → FAILED ✓（fsm.py:31）
  3. node.retries += 1  →  retries=1
  4. TaskFSM.can_retry(1) → 1 < 3 → True
  5. _transition(node, PENDING)         FAILED → PENDING ✓（fsm.py:36）

→ t-fe 回到 PENDING，下一轮 compute_frontier 将再次捡起它
→ executor 重派时 build_task_instruction 注入 fail_reason
```

**FSM 守卫**：
- `RUNNING → COMPLETED` 被 `VALID_TRANSITIONS` 阻断——必须经过 `VERIFYING`（fsm.py:23）
- `FAILED → PENDING` 仅在 `can_retry(retries < 3)` 为真时允许

---

## 异常路径：Worker 崩了

```
outcome = WorkerOutcome(ok=False, output="worker 自身失败/超时")

_execute_and_settle（L75-77）:
  → _handle_failure(node, "worker 自身失败/超时")
  → FAILED → retries+=1 → PENDING（重试）
```

---

## 异常路径：retry 耗尽

```
t-fe 反复失败 4 次后:

_handle_failure:
  retries=3, TaskFSM.can_retry(3) → 3 < 3 = False
  → 不转 PENDING，留在 FAILED

_propagate_blocked()（L95-97）:
  unreachable_pending(graph):
    t-e2e: depends_on=["t-fe","t-be"]
           t-fe=FAILED（∈ _UNREACHABLE_STATES）→ t-e2e 应判 BLOCKED
  → _transition(t-e2e, BLOCKED)          PENDING → BLOCKED ✓（fsm.py:20）

_terminal():
  any(FAILED) → RunResult(FAILED, summary)
  
summary:
  t-fe: ❌ 失败（原因：验收失败: ...）
  t-be: ✅ 已完成（验收通过：pytest）
  t-e2e: ⏸ 受阻（上游失败导致不可达）
```

---

## 当前代码的边界

| 能力 | 状态 | 代码位置 |
|------|:---:|------|
| Planner 真 LLM 分解 | ✅ | planner.py:181（需 TextLLM 适配器，Phase 5） |
| DAG 编译 + 校验 | ✅ | dag.py:77 build_graph |
| FSM 状态转移 | ✅ | fsm.py:19 VALID_TRANSITIONS |
| 就绪集计算 | ✅ | scheduler.py:20 compute_frontier |
| 串行调度循环 | ✅ | orchestrator.py:51 run() |
| Verifier 机械验收 | ✅ | verifier.py |
| Executor 派 Worker | ✅ | executor.py:91 run() |
| retry + BLOCKED 传播 | ✅ | orchestrator.py:87-97 |
| 退出原因码 + 机械汇总 | ✅ | orchestrator.py:100-137 |
| **Phase 5 接线**（Selector→ChatService→Orchestrator） | ❌ | 待实现 |
| **并发调度**（max_concurrency > 1） | ❌ | 标准档 |
| **LLM replan**（失败自动重规划） | ❌ | 标准档 |
| **worktree 隔离** | ❌ | 标准档 |
| **里程碑回顾** | ❌ | 完整档 |

---

## 数据流全景（一次完整执行）

```
Orchestrator.run()
  │
  ├─ [LLM] Planner.plan(ctx)           ← 1-N 次 API 调用
  │     └─ list[TaskDef]               ← 纯数据，无副作用
  │
  ├─ [纯函数] build_graph(defs)
  │     └─ TaskGraph {nodes: {id→TaskNode(PENDING)}}
  │
  ├─ [循环] for _ in range(max_steps):
  │     │
  │     ├─ [纯函数] compute_frontier(graph)
  │     │     └─ ["t-fe"]  ← 就绪 task id
  │     │
  │     ├─ [纯函数] unreachable_pending(graph)
  │     │     └─ []  ← 强制标 BLOCKED
  │     │
  │     ├─ [纯函数] select_dispatchable(..., max_concurrency=1)
  │     │     └─ ["t-fe"]  ← 串行只取一个
  │     │
  │     ├─ [FSM] _transition(node, QUEUED→RUNNING)
  │     │
  │     ├─ [IO] Executor.run(node)      ← Worker CLI/API
  │     │     └─ WorkerOutcome(ok, output)
  │     │
  │     ├─ [FSM] _transition(node, RUNNING→VERIFYING)
  │     │
  │     ├─ [IO] Verifier.verify(node)   ← 跑验收命令
  │     │     └─ Verdict(passed, reason)
  │     │
  │     └─ [FSM] _transition(node, VERIFYING→COMPLETED|FAILED)
  │           或 _handle_failure → FAILED→PENDING(retry)
  │
  └─ _terminal()
        └─ RunResult(reason, _build_summary())
```

**LLM 只在 plan() 里调**。调度、FSM、验证、汇总全是确定性代码。这是 v2 设计核心——DAG 独占调度，LLM 复杂度 O(异常点)。

---

## 关联文档

- [[coordinator-dag-driven-design-v2]] 权威设计
- [[coordinator-subsystem-collaborators]] 5 协作者分解
- [[coordinator-mvp-phase5-wiring-spec]] Phase 5 接线（最后一相）
