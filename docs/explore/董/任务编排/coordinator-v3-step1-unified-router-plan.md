# Coordinator v3 步 1 — 统一路由器 实现计划

> 日期：2026-06-07 | 依据：[[coordinator-design-v3]] §4 / §5 / §9 步1 / §10 | 前序：[[coordinator-v3-step-tools-implementation-plan]]（步 3 已完成）
> 原则：TDD（RED→GREEN）、增量可独立验证、机械反射零 LLM 优先、失败降级永不阻塞用户

---

## 目标与范围

**目标**：把群聊前门的「两段决策」（`CoordinatorGate` 机械预滤+intent LLM + `Selector` L3 选人 LLM）合并成**一次 `Planner.decide()` reactive 决策**，输出 `respond / multi / task / done` 四种 action。删 `CoordinatorGate`，消掉脆弱白名单前门 bug（§10#3 回归点）。

**为什么先做这步**：设计 §9 明示步 1「现在就能干、且是终态组件（非临时补丁）」。当前 step-tools（步 3）是挂在残留 v2 gate 路由上跑的——步 1 把它迁到 v3 正经路由。

**本次范围**：
- 新增 `Planner.decide(reactive_ctx) -> PlannerDecision`（一次轻 LLM，tool_use 结构化输出）
- ChatService 群聊路由重写：机械反射前置 → `decide` → 分发到 respond（轻）/ task（重）
- 删 `CoordinatorGate`；`is_control` / `@mention` / 全体意图 提升为 ChatService 前门反射
- `task` action 接现有 `_start_coordinator`（步 3 的 Harness 不动）

**不在本次范围**（明确边界，防 scope 蔓延）：
- 统一 SessionState 投影（§9 步2）——本步用**轻量 reactive 上下文**（近窗口+active_plan 布尔+成员）替代，不依赖步2 的 read-model 抽象
- 任务中 replan / `active_plan` 非空时的 modify 分支（§9 步4）——本步 `active_plan` 非空仍走现有逻辑（control 取消 / feed waiting step / 否则忽略）
- DiscussionOrchestrator 多轮 selector 循环的去留（见下方**关键决策 B**，可二选一）

---

## ⚠️ 落地前必须拍板（设计 §10 + 本步新增）

这些决定计划怎么写，**请先逐条确认**：

| # | 开口 | 推荐 | 成本/牵连 |
|---|------|------|-----------|
| **A** | reactive 与 deliberate 是一次还是两档 LLM？ | **两档**（§2.2）：decide 一次轻调用出 respond/task；判 task 后才进 SeedPlanner.plan decompose | 不选两档=每句话付 decompose 成本（贵且慢）。选两档=多一次轻调用，但 decompose 只在真任务时付 |
| **B** | DiscussionOrchestrator 的 selector 多轮循环去留？ | **本步保留**（最小改动）：decide 选首位响应者 → DiscussionOrchestrator 仍用内部 Selector 续轮 | 去掉=多轮自动讨论消失（agent 互相接力没了），属步2 统一回合循环的活，本步不碰免回归 |
| **C** | capability 关键词层（Selector L2）去留？ | **删**（§10#3）：任务文本天然含技术词，该层把任务短路截胡进讨论 | 留=v2 那个脆弱白名单 bug 还在。删=这类消息落 decide 判 task，正是本步要修的回归点 |
| **D** | 每条非反射消息都付一次 decide LLM，成本可接受？ | **可接受**：用 selector 同款廉价模型（`settings.selector_*`），近窗口截断 | 现状是 has_work_intent 正则免费筛掉大部分，只工作意图付 is_decompose。新方案每条非反射消息付一次轻调用。量级与现 selector L3 相同（讨论消息本来就付），新增的是"纯闲聊也付一次"——可加机械短路兜底（见步 1c 可选优化） |
| **E** | `@某agent + 任务`（如 `@X 帮我做博客`）走 respond 还是 task？ | **respond**（§10#4，v1 显式 @ = 找人聊） | @mention 前门反射直达，不进 decide。边界后议 |

> 默认按推荐执行。若有不同意见，指出哪条，我改计划。

---

## 前置知识（现状，全部已读代码核对）

### 当前群聊路由（`chat_service._handle_group`）

```
trigger → _resolve_mentions
  ├─ 有 @targets → 逐个 _stream_one_agent（@mention 已是前门反射）✅ 保留
  └─ 无 @：
       run = registry.get(session.id)
       ├─ run 非空（执行态）：is_control→cancel / waiting→feed / 否则忽略   ← 本步不碰
       └─ run 空：
            gate.has_work_intent(text)              ← 删
              └ gate.is_decompose(text, history)    ← 删，并入 decide
                  → _start_coordinator              ← 保留（task action 接这里）
            否则 → DiscussionOrchestrator.run_discussion（内含 Selector）
```

### 要删/改的组件

| 组件 | 现状 | 步 1 处置 |
|------|------|-----------|
| `CoordinatorGate.has_work_intent` | 正则工作动词预滤 | **删** |
| `CoordinatorGate.is_decompose` | 1 次 LLM 二分类 decompose/discuss | **删**，能力并入 `decide` |
| `CoordinatorGate.is_control` | 正则控制词 | **移**到 ChatService 前门反射（逻辑不变） |
| `Selector._resolve_mention` (L1) | @ 直达 | 已在 `_resolve_mentions` 前门，**Selector 内副本可留**（讨论续轮用，见决策B） |
| `Selector._resolve_broadcast` (L1.5) | 全体意图 | **提升**为 ChatService 前门反射（用户消息触发 multi） |
| `Selector._resolve_keyword` (L2) | capability 关键词 | **删**（决策 C） |
| `Selector._llm_decide` (L3) | LLM 选人 | 能力并入 `decide`（决策 B 保留时，Selector 续轮仍用其副本） |
| `SeedPlanner.plan` | decompose → DAG | **不改**（deliberate 视野，decide 判 task 后调它） |

### 复用的现成机械

- `Selector` 的 provider 分发 + tool_use 调用 + 降级 DONE 套路（`_llm_decide_anthropic/_openai`、`_parse_payload`）——`decide` 直接照搬，只扩 action 集。
- `_start_coordinator(session, group, trigger)` —— task action 直接调，零改动。
- `DiscussionOrchestrator.run_discussion` —— respond/multi action 复用（决策 B 决定是否剥循环）。

---

## 设计：`Planner.decide`

### PlannerDecision DTO（新增 `ports.py`）

```python
@dataclass(frozen=True)
class PlannerDecision:
    action: Literal["respond", "multi", "task", "done"]
    who: tuple[str, ...] = ()      # respond=1 个 worker 名；multi=多个；task/done=空
    reason: str = ""               # 可观测
    # task 的 plan 不在此出——decide 只判"是不是任务"，真 decompose 由 SeedPlanner.plan（两档，决策 A）
```

### ReactiveContext DTO（新增；步2 的 SessionState 轻量替身）

```python
@dataclass(frozen=True)
class ReactiveContext:
    recent: tuple[Message, ...]    # 近窗口（复用现 selector 的 15 条、每条截断）
    members: tuple[Agent, ...]     # 群成员（候选 worker）
    active_plan: bool              # 是否有 run 在跑（本步只读布尔；步4 才放开 replan）
```

### Planner.decide 协议（`ports.py` Planner Protocol 加方法）

```python
class Planner(Protocol):
    async def plan(self, ctx: PlanContext) -> list[TaskDef]: ...        # 既有（deliberate）
    async def decide(self, ctx: ReactiveContext) -> PlannerDecision: ... # 新增（reactive）
```

> 「一个 Planner，两个视野」：同一概念组件的两个方法。实现上 `decide` 走廉价模型 tool_use，`plan` 走既有 TextLLM。可同类双方法，也可 `ReactiveRouter` 持 LLM、`plan` 委托 `SeedPlanner`——**倾向后者**（decide 的 tool_use 机制更像 Selector，不污染 SeedPlanner 的纯文本解析）。

### decide 的 tool_use schema（扩 Selector 的 `select_next_speaker`）

```
action ∈ {respond, multi, task, done}
  respond → who=[一个成员名]
  multi   → who=[多个成员名]
  task    → who=[]（判定为"要动手干的开发任务"，后续 SeedPlanner.plan 接手）
  done    → who=[]（无需响应/讨论收敛）
```

system prompt 要点（**承接语理解放进 prompt，不硬编码**，§9 步1）：
- 判"是不是要实际写代码/改文件/跑命令的开发任务" → `task`（取代 is_decompose；**无白名单**）
- 否则按讨论选人：谁该回 → `respond` / 多人 → `multi` / 无需回 → `done`
- active_plan=true 时本步仍保守（不出 task/replan，交回现有执行态逻辑）——避免与步4 抢边界

---

## 分步实现（TDD）

### 步 1a：DTO + 协议（~0.5h）

- `ports.py`：加 `PlannerDecision`、`ReactiveContext`、`Planner.decide` 协议方法。
- **TC-1a.1**：`PlannerDecision(action="respond", who=("前端",))` 可构造、默认值正确。

### 步 1b：ReactiveRouter.decide 实现（~2h）

- 新 `app/application/services/reactive_router.py`（或 `domain/task_engine/router.py`）。
- 照搬 Selector 的 provider 分发 + tool_use + 降级；扩 action 集；接 active_plan 入 prompt。
- 降级铁律：任何异常/不可解析 → `PlannerDecision(action="done")`（永不阻塞用户，与 Selector 一致）。
- **TC-1b.1**（fake LLM）：返回 `task` → decision.action=="task"。
- **TC-1b.2**：返回 `respond` + agent_name → who 命中成员。
- **TC-1b.3**：LLM 异常 → 降级 done。
- **TC-1b.4**：返回不存在的 agent_name → 降级 done（不崩）。
- **TC-1b.5**：返回 `multi` 多名 → who 含全部命中成员。

### 步 1c：ChatService 群聊路由重写（~2h）

新 `_handle_group` 骨架：

```python
async def _handle_group(self, session, group, trigger):
    targets = await self._resolve_mentions(trigger.mentions, group)
    if targets:                                  # 前门反射①：@mention 直达
        ... 逐个 _stream_one_agent; return

    text = trigger.content or ""
    run = self._registry.get(session.id)
    if run is not None:                          # 执行态：本步不碰（步4 才放 replan）
        if self._is_control(text): await self._cancel_coordinator(...)
        elif run.has_waiting_step(): run.feed(text)
        else: logger.debug("执行中忽略")
        return

    if self._is_control(text):                   # 前门反射②：control（无 run 时空操作/忽略）
        return
    if self._is_broadcast(trigger):              # 前门反射③：全体意图 → multi 全员
        async for evt in self._respond_multi(session, group, trigger, all_members): yield evt
        return

    decision = await self._router.decide(self._build_reactive_ctx(session, group, trigger))
    match decision.action:
        case "task":
            await self._start_coordinator(session, group, trigger); return
        case "respond" | "multi":
            async for evt in self._respond(session, group, trigger, decision.who): yield evt
        case "done":
            logger.debug("decide=done，静默"); return
```

- `is_control` / `is_broadcast` 作为 ChatService 静态方法（从 gate/selector 搬正则，逻辑不变）。
- `_respond`：把 decision.who 翻成 Agent → 复用 `_stream_one_agent`（决策 B 保留循环则委托 DiscussionOrchestrator 续轮；剥离则单发）。
- **可选优化（决策 D 兜底）**：decide 前加一道**纯机械短路**——明显无意图的极短消息（"嗯"/"好的"/"哈哈"）直接 done，省一次 LLM。非必须，可后置。
- **TC-1c.1**：注入 fake router 返回 task → `_start_coordinator` 被调。
- **TC-1c.2**：fake router 返回 respond(前端) → 该 agent 被 stream。
- **TC-1c.3**：control 消息 → 不调 router（前门拦截）。
- **TC-1c.4**：全体意图消息 → multi 全员，不调 router。
- **TC-1c.5**：执行态（run 非空）非 control 非 waiting → 不调 router（保持现忽略语义）。

### 步 1d：删 CoordinatorGate + 清理（~1h）

- 删 `coordinator_gate.py` + `tests/test_coordinator_gate.py`（is_control 正则迁移到 ChatService 后，相关用例搬过去）。
- ChatService `__init__`：去 `coordinator_gate` 参，加 `reactive_router`（缺省懒构造）。
- 决策 C 若删 capability 层：删 `Selector._resolve_keyword` + 相关用例。
- 决策 B 若剥离 Selector 循环：DiscussionOrchestrator 改单发（**本步不推荐，留步2**）。
- `wiring`/`chat.py` 注入点更新（`ws/chat.py` 构造 ChatService 处）。
- **TC-1d.1**：全链路 wiring 测试——构造 ChatService（fake router）→ 发任务消息 → 起 coordinator；发讨论消息 → respond。

---

## 验证

```bash
MAINPY=/home/huishuohuademao/workspace/AgentHub/src/backend/.venv/bin/python
$MAINPY -m pytest tests/test_reactive_router.py tests/test_chat_service.py tests/test_wiring.py --no-cov -q
$MAINPY -m ruff check app/application/services/reactive_router.py app/application/services/chat_service.py app/domain/task_engine/ports.py
```

回归重点：`test_chat_service.py` 现有讨论/任务路由用例必须改造（gate→router）后全绿。

---

## 风险清单

| 风险 | 影响 | 缓解 |
|------|------|------|
| decide 每条消息付 LLM（决策 D） | 成本/延迟 | 廉价模型 + 近窗口截断 + 可选机械短路；量级≈现 selector L3 |
| 删 gate 后承接语/任务判定全交 LLM prompt | 误判任务/漏判 | prompt 明写判据 + 降级 done（漏判=当讨论，不误触发 Harness）；真实消息集回归测 |
| 决策 B 保留 Selector 循环 = 两处选人逻辑（decide + Selector 续轮） | 重复/不一致 | 本步接受（标 TODO 步2 收口）；首位由 decide，续轮由 Selector，职责清晰 |
| 现有 `test_chat_service.py` 大改 | 回归面 | 先读全量用例，逐个映射 gate→router 语义，确保覆盖不降 |
| `is_control` 正则迁移漏 case | 取消失效 | 整段搬运 + 原 gate 用例同步迁移，不重写正则 |

---

## 文件改动总览

```
新建:
  app/application/services/reactive_router.py     # Planner.decide reactive 实现
  tests/test_reactive_router.py                   # TC-1b

改动:
  app/domain/task_engine/ports.py                 # PlannerDecision + ReactiveContext + Planner.decide
  app/application/services/chat_service.py         # _handle_group 重写 + is_control/is_broadcast 前置 + 注入 router
  app/application/services/selector.py             # 删 _resolve_keyword（决策 C）；L3 视决策 B 去留
  app/api/ws/chat.py                               # ChatService 注入点（去 gate，加 router）
  tests/test_chat_service.py                       # gate→router 用例改造
  tests/test_wiring.py                             # 注入更新

删除:
  app/application/services/coordinator_gate.py     # 整类删除
  tests/test_coordinator_gate.py                   # is_control 用例迁 test_chat_service

不改（复用）:
  app/domain/task_engine/planner.py                # SeedPlanner.plan 不动（deliberate）
  app/domain/task_engine/orchestrator.py           # 步3 Harness 不动
  app/application/services/coordinator_run.py       # _start_coordinator 链路不动
  app/application/services/discussion_orchestrator.py # 决策 B 保留则不动
```

---

## 与后续步的衔接

- **步 2（统一 SessionState + 回合循环）**：把本步的 `ReactiveContext` 升级为 SessionState 两流投影；收口决策 B 的双选人逻辑（DiscussionOrchestrator 循环并入统一回合循环）。
- **步 4（replan）**：放开 `decide` 在 `active_plan=true` 时返回 `modify/replan`，接 UserInterrupt → 图变更。本步已把 active_plan 作为 decide 输入预留了这个口子。
