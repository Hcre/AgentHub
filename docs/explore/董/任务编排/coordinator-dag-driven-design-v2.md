# Coordinator 设计 v2 — DAG 驱动 + 事件循环

> 日期：2026-06-05 | 状态：设计稿 v2.2 | 取代：[[coordinator-queryloop-design]]（v1）
> 基础：MAF WorkflowBuilder（确定性 DAG）+ MAF Magentic（仅 plan/replan/final 语义）+ Claude Code queryLoop（退出码 + 被动压缩）
> 修订史：v2.0 初稿 → v2.1 补 §11/§13 → v2.2 回应 6 条反驳纠正过度声明 → **v2.3 厘清 Coordinator=Planner(CLI/LLM 推理)+Harness(确定性编排)，关闭工具/上下文洞（§1.1）**

---

## 0. 相对 v1 的核心变更

v1 把 MAF 的两个**本应分开**的子系统焊在一起（Magentic 每轮 LLM 重判 + WorkflowBuilder 静态 DAG），导致"调度权归属未定义"。v2 一次性收敛 7 个地基问题：

| # | v1 的问题 | v2 的决策 |
|---|----------|----------|
| 1 | DAG 与 `next_wave` 双调度冲突 | **DAG 独占调度**，删除 `progress_ledger.next_wave`；LLM 降级为异常点调用 |
| 2 | 标量 `stall_count` 在并行下语义破裂 | 取消计数器，改 **per-task 健康状态** + 全局 `replan_count` 守卫 |
| 3 | 用 LLM ledger 轮询检测卡死（贵且不准） | **四层机械检测**（心跳/超时/预算/重复），检测环节零 LLM |
| 4 | `frozen=True` 假不可变 | **事件溯源 + 可变投影**，靠 `task_events` 做不可变底座；单写者纪律解决并发 |
| 5 | `chat_history` 混淆转录与工作上下文，replan 让用户消息消失 | **三流分离**：群聊转录 / Coordinator 工作上下文 / 每 worker 会话 |
| 6 | 完成判定全靠 worker 自报，无验证 | **独立验证闸门**：plan 时声明 acceptance，Harness/Reviewer 执行，worker 不批自己作业 |
| 7 | `can_parallel` 只查声明文件，假安全 | **git worktree 结构隔离**，冲突从静默竞态变为显式 merge 冲突 |

**LLM 调用复杂度：从 O(轮次) 降到 O(里程碑 + 异常点)**（里程碑 ≪ 轮次，仍远比 v1 便宜；v2.2 修正——见下）。

补充两节（v2.1，2026-06-05）：
- **§11 Selector × Coordinator 边界（已决）**：从 v1 的"P1 待决"裁定为"Selector 常驻前门 + Coordinator 被投喂的临时引擎"。
- **§13 与现有代码的接线方案**：基于实读 `selector.py`/`chat_service.py`/`coordinator.py`，给出三根接线 + 上下文管理落点。

**v2.2 修订（2026-06-05）—— 回应 6 条反驳，纠正 v2 的过度声明**：

| # | v2 的 over-claim | v2.2 修正 | 章节 |
|---|-----------------|----------|------|
| 1 | "末尾 1 次 LLM 判完成" → plan 错也只在最后才发现 | 加**里程碑回顾**（DAG 汇聚点/偏离时）做中期 `still_on_track?` | §2.6 |
| 2 | "LLM 不参与调度"与"动态扩图是 LLM 介入点"矛盾 | 拆分**调度（就绪集，零 LLM）vs 图变更（造节点，用 LLM）**；区分动态输入 / 动态结构，定义扩图 code path | §2.4·§2.7 |
| 3 | 三流分离没设"replan 给多少上下文"旋钮 | **失败子树全保真 + 其余仅标题**；摘要**增量产出**，replan 时零额外调用 | §4.1 |
| 4 | "四层机械检测零 LLM"，固定静默阈值 | 阈值**条件化于上一动作类型** + thinking 非静默 + **OS 探活** + 预算兜底；残余靠预算截停后升级 | §5 |
| 5 | "Selector 是无状态的"说太绝对 | 改为**纯函数（无自持状态），但入参携带系统状态快照** | §13.3 |
| 6 | worktree "解决"冲突 → 实则只解文本冲突，语义冲突漏网 | 加**集成验证闸门**（全量测试）+ **模块不相交分解**降冲突面；残余是并行开发普遍极限，须显式暴露 | §6.4·§7.4 |

> 病根：v2 为反对 v1 的"每轮 LLM"，把钟摆甩到"机械/便宜"另一端。真相是**语义介入的粒度**——v1 每轮（太细）、v2 实写 plan+末尾（太粗），v2.2 落在**里程碑/汇聚点/扩图点/失败点/集成点**（中间粒度）。

**设计收口（v2.2，2026-06-05）**：A 类两个"实现前必拍"决策已在 §13.5 敲定（A1 decompose 预闸门 / A2 插话分类）。其余遗留问题归为 B 类（成本取舍，§14 分级兜住）与 C 类（多 Agent 普遍极限，已诚实标注，非本设计缺陷）。**设计阶段收口，进入 §14.1 MVP 实现。**

**v2.3 澄清（2026-06-05，实现中）**：厘清 Coordinator = **Planner（推理，LLM/CLI）+ Harness（编排，确定性代码）**，见 §1.1。关闭"协调者工具/上下文"两个洞——CLI 形态原生提供，不必自建。已落地代码（dag/scheduler/fsm）属 Harness 控制面，本次澄清**不影响**。

---

## 1. 架构定位

```
┌─────────────────────────────────────────────────────┐
│                DiscussionOrchestrator                │
│  ┌──────────┐   ┌────────────┐   ┌───────────────┐  │
│  │ Selector │   │ Coordinator│   │ Agent Workers │  │
│  │ 消息路由  │   │  DAG 编排  │   │  任务执行      │  │
│  └────┬─────┘   └─────┬──────┘   └───────┬───────┘  │
│       │ 模式切换       │ 事件驱动          │ worktree │
│       ▼               ▼                  ▼          │
│  DISCUSSION ←──────→ EXECUTION                      │
└─────────────────────────────────────────────────────┘
```

- **Coordinator 不是每轮发言的循环主**，而是 **DAG 状态机的事件响应器**。
- **关键区分**（v2.2 澄清）：
  - **调度** = 给定 DAG 算哪些**已有节点**就绪 → 纯函数，零 LLM。
  - **图变更** = 造**新节点** / 改图 → 用 LLM。
  - "LLM 不参与调度"准确指**不参与就绪集计算**，不是"不参与图变更"。
- LLM 在 5 类点被调：① plan ② **里程碑回顾**（§2.6）③ **图变更**：replan / 动态扩图（§2.7）④ 终止歧义 ⑤ final_answer。

### 1.1 Coordinator = Planner（推理）+ Harness（编排）（v2.3 澄清）

> 背景：设计推进中发现 Coordinator 在不断"长出 agent 特征"——工具（Read/Grep 探仓库）、上下文管理（三流/压缩）、agentic 循环。这些**本来就是 agent 干的活**，自己拿裸 LLM API 现攒这套装备 = 重造 CLI 已有的东西。v2.3 把这条边界讲清。

"Coordinator"这个名字捆了**两层**，必须拆开看：

| 层 | 本质 | 形态 |
|----|------|------|
| **Planner（推理）**：分解 / replan / 里程碑回顾 / final_answer | 读仓库、理解需求、上下文管理——**就是 agent** | **LLM**，可裸 API 也可 CLI session |
| **Harness（编排）**：派发 worker / DAG 状态 / FSM / 验证闸门 / 单写者事件溯源 / merge worktree | 确定性控制流，**绝不让 LLM 每轮来判** | **确定性代码**（dag/scheduler/fsm/事件循环） |

**关键纪律**：编排**绝不能**塞进 CLI/LLM——否则 LLM 要同时负责"派谁、跟踪谁、判验证"，正是 v1 的错（LLM 每轮在环里、调度不确定）。v2 的全部价值就是把编排剥成确定性代码。

#### CLI 不是"替代 LLM"，是"装备好的 LLM"

```
裸 LLM API:   chat_structured(prompt)→dict   · 无工具、无 agentic 循环
                                              · 要探仓库就得自建 ToolRegistry+上下文管理+tool 循环 ← agent 机制自建
CLI session:  LLM + Read/Grep/Glob + 上下文压缩 + agentic 循环（全原生）   ← 装备白给
```

**对接 CLI = 用"已经攒好装备的 LLM"，而不是自己给裸 LLM 攒装备。** 顺手关掉"协调者工具/上下文"两个洞（v1 §3.1 列过 5 件只读工具，v2 一度丢失——CLI 形态下它们由 CLI 原生提供，不必自建 ToolRegistry）。

#### Planner 的两种交付形态（对接 §14 分级）

| | Planner 形态 | 工具 | 何时 |
|---|---|---|---|
| 裸结构化 API（`chat_structured`，上下文预注入）| LLM，无工具 | 够用就用，简单好测 | **MVP** |
| CLI session（只读工具，自己 Read/Grep 探仓库 → `submit_plan` 吐 JSON）| 装备好的 LLM | 要自适应探索时 | **标准** |

两者都是"调 LLM 适配器拿结构化 dict"，Harness 拿到后 `build_graph` 校验——校验链不变。worker 已是 CLI session（`claude_adapter` 有 `chat_structured`），Planner 复用同一套适配器，不新造。

**一句话**：本质始终是 **LLM + Harness**；v2.3 只是把"Planner 的 LLM"以 CLI 这种装备形态交付，省掉自建 agent 机制。**Harness（含本文 §2–§7 全部确定性逻辑）一字不变。**

---

## 2. 调度模型：DAG 独占 + 事件驱动

### 2.1 为什么是 DAG 而不是每轮 LLM 重判

Magentic-One 每轮让 LLM 挑 `next_speaker`，前提是**没有预定 DAG**——任务开放式、图算不出来。但 Coordinator 在 plan 阶段**已经产出了带 `depends_on` 的 DAG**。一旦有 DAG，"下一波能跑谁"是确定性拓扑计算。继续每轮 LLM 重挑 = 为不需要的灵活性付每轮 8K token 税，且与 DAG 产生冲突。

**结论：DAG 是唯一调度权威。** LLM 不再产 `next_wave`。

### 2.2 主循环（事件驱动，无"轮次"）

```python
async def coordinate(state: CoordinatorState):
    state = await plan(state)              # LLM ×2，构建并校验 DAG
    dispatch_frontier(state)               # 启动初始就绪集

    async for event in event_bus(state.run_id):   # 单写者：所有变更串行经此
        match event:
            case WorkerDone(t):
                await verify_and_settle(t, state)   # 见 §6
                dispatch_frontier(state)
            case WorkerFailed(t):
                await handle_failure(t, state)      # retry 或 LLM.replan
            case WorkerTimeout(t) | WorkerLoop(t):  # 机械卡死，见 §5
                await handle_failure(t, state)
            case UserInterrupt(msg):
                await handle_interrupt(msg, state)  # 图变更

        match terminal_check(state):
            case AllDone():        return await final_answer(state)  # LLM ×1
            case Unreachable(blocked):
                await decide_replan_or_abort(blocked, state)         # LLM
            case BudgetExceeded(reason): return exit(reason)
            case Continue():       pass
```

`dispatch_frontier`：

```python
def dispatch_frontier(state):
    ready = [t for t in state.dag if t.status == PENDING
                                  and all(dep.status == VERIFIED for dep in t.deps)]
    ready = apply_concurrency_limits(ready, state)   # 全局/单 agent 上限 → 排队
    for t in ready:
        wt = create_worktree(t, base=state.integration_ref)  # §7
        dispatch_worker(t, worktree=wt)
        t.status = RUNNING
```

**`compile_wave` / `can_parallel` 在 v2 里几乎退役**：worktree 隔离后任意就绪任务都可并行，文件冲突推迟到 merge 阶段显式处理（§7）。

### 2.3 任务节点状态机（FSM）

> **命名对齐（实现澄清）**：下图的 `VERIFIED` 在代码 enum 里复用现有 `COMPLETED`（不另立新状态）。`fsm.py`/`scheduler.py`/`orchestrator.py` 一律用 `COMPLETED` 表示"已验证终态"，`compute_frontier` 按 `COMPLETED` 判依赖满足。本文行文仍用 VERIFIED 表语义，二者等价。

```
PENDING ──deps 满足──→ RUNNING ──worker_done──→ VERIFYING ──pass──→ COMPLETED(=VERIFIED)
   │                      │                         │
   │                      │ failed/timeout/loop     │ fail
   │                      ▼                         ▼
   └──上游 FAILED────→ BLOCKED              FAILED ──retry──→ PENDING
                                              │
                                              └──replan──→ (子树重建)
```

- `BLOCKED`：上游失败导致不可达，**不是 FAILED**——上游修复后可复活。
- `VERIFYING`：worker 报完成但还没过验证闸门，**此时不算 DONE**。
- 只有 `COMPLETED(=VERIFIED)` 才解锁下游。
- retry：`FAILED → PENDING`（回 frontier 重捡），CANCELLED 保留。

### 2.4 必须覆盖的复杂情况

| 情况 | 处理 |
|------|------|
| **动态输入**（多数"动态"其实是这个）| 「前端产出 N 文件 → 测试这 N 文件」**不需要扩图**。plan 时就建 `t_test`，`depends_on=[t_前端]`，instruction 模板化"测试 t_前端 产出"；dispatch 时把 t_前端 的 output 填进去。**节点早存在，仅输入运行时填充**，零 LLM。|
| **动态结构**（真扩图，较少）| 运行时才知道有哪些子任务（"勘探代码库 → 修发现的 bug"）。走 §2.7 扩图 code path = **作用域限定到该节点子树的轻量 replan**，用 LLM。|
| **部分失败** | wave 内一个失败，其余跑完各自 verify；失败的单独 replan，不连坐。|
| **下游不可达** | B 失败 → 依赖链标 `BLOCKED`。LLM 判：修 B 子树让其复活，还是整体 abort。|
| **环检测** | LLM 生成的 `depends_on` 可能成环 → **build 时校验拒绝并回灌让 LLM 修**，不进循环。|
| **并发上限** | ready 超配额 → 排队，frontier 分批 dispatch。|
| **replan 改图** | 子树修复 merge 新节点，可能让在飞任务失效 → 对相关 worker 发 reset 信号。|
| **用户插话改需求** | 等价"图变更"：注入新节点或重开 VERIFIED 节点，统一走 `UserInterrupt`，非特例。|

### 2.5 结构完成 ≠ 语义完成

DAG 全 VERIFIED 只代表"计划执行完"，不代表"满足用户意图"（计划本身可能错）。终止时 LLM 做 `is_request_satisfied` + `final_answer`，读的是机器验证结论（§6），不是 worker 散文。

### 2.6 里程碑回顾（v2.2 新增，修正"末尾才发现 plan 错"）

**问题**：若 plan 本身错，但 Task 全部顺利 VERIFIED，只在末尾才判 unsatisfied → 用户等完全程才知道方向错了。

**注意 v1 也没真解决**：Magentic 的 `is_progress_being_made` 在"任务顺利产出"时 = true，**不会触发 replan**——它抓 stall，不抓 wrong-direction-with-progress。所以这是两版共同的洞，不是 v2 退步。

**修法：不是每轮，也不是只末尾，而是在 DAG 结构里程碑做中期回顾**：

| 触发点 | 说明 |
|--------|------|
| **汇聚点（fan-in 节点）** | 并行分支重新合流处 = 语义上"一个阶段完成"的天然检查点 → 一次 `still_on_track?` LLM 回顾 |
| **产出显著偏离 plan 假设** | 验证闸门本就读结果，顺带标记"过了 acceptance 但与预期不符" → 触发回顾 |

```python
case WorkerDone(t):
    await verify_and_settle(t, state)
    if is_join_point(t, state.dag) or t.diverged_from_plan:
        review = await milestone_review(state)      # LLM，仅里程碑
        if not review.on_track:
            await replan(state, reason=review.reason)
    dispatch_frontier(state)
```

里程碑数 ≪ 轮次数，故仍比 v1 每轮便宜。这把 §0 的 "O(异常点)" 诚实修正为 **"O(里程碑 + 异常点)"**。

### 2.7 图变更与动态扩图 code path（v2.2 新增）

调度（就绪集）零 LLM，但**造新节点**要 LLM。两条图变更路径共用同一套机制：

```python
async def mutate_graph(state, *, scope, reason):
    """replan 与动态扩图的统一入口。scope = 受影响子树（不是全图）。"""
    ctx = build_replan_context(state, scope)         # §4.1 子树作用域
    new_nodes = await llm_plan_subtree(ctx, reason)  # LLM：产出新 TaskDef
    validated = harness.validate_merge(new_nodes, state.dag)  # 环/依赖/worker 校验
    state.dag.merge(validated)                       # 合入，受影响在飞任务发 reset
```

- **replan**：由 `WorkerFailed` / 里程碑回顾 not-on-track 触发，scope = 失败子树。
- **动态扩图**：由标记为 `expandable` 的节点（其职责就是产子任务）完成时触发，scope = 该节点的子树。
- 二者都**不是"每轮重挑 next_wave"**——只在特定节点 / 失败 / 偏离时触发，是事件驱动的局部图变更，与"每轮全局调度决策"有本质区别。

`TaskDef` 增 `expandable: bool = False` 标记扩图点（见 §8）。

---

## 3. 状态模型：事件溯源 + 可变投影

### 3.1 放弃 `frozen=True`

`@dataclass(frozen=True)` 只防重新绑定属性，内部 `dict`/`list`/`set` 照样可变，是**假不可变**。真正的不可变底座是已有的 `task_events`（追加日志）。

```python
@dataclass            # 普通可变；不假装 frozen
class CoordinatorState:
    run_id: str
    task: str
    task_ledger: TaskLedger | None
    dag: TaskDAG                      # 节点 + 状态（可变投影）
    group_id: str                    # 群聊转录在别处，仅引用（见 §4）
    integration_ref: str             # 集成分支/基 commit
    replan_count: int = 0            # 全局活锁守卫
    budget: Budget                   # token / 墙钟 / 任务数上限
```

- **真相源**：`task_events` 追加不可变，可重放重建 `dag`。永不"丢状态"，故内存无需不可变。
- **`CoordinatorState` 是从事件重建的可变投影。**

### 3.2 单写者纪律（真正要解决的并发问题）

worker 回调异步并发，多个回调并发改同一 `state` 会竞态。解法不是 frozen，而是：

```
所有状态变更 → 串行经过单一 event_bus 协程 → 顺序 apply + append task_event
worker 回调只 emit 事件，从不直接改 state
```

写者唯一 ⇒ 无锁、无竞态、天然可审计（事件顺序即历史）。

---

## 4. 三流分离（修复 v1 的 chat_history 混淆）

v1 的 `chat_history` 同时当"用户可见群聊"和"Coordinator 工作草稿"，replan 一 reset 用户消息凭空消失。v2 拆三流：

| 流 | 持久化 | 可见 | reset 行为 | 存储 |
|----|:---:|:---:|----------|------|
| **群聊转录** | ✅ 追加不可变 | ✅ 用户看的就是它 | **永不 reset** | `messages` 表 / `group_id` |
| **Coordinator 工作上下文** | ❌ 派生 | ❌ | 可重建 | 每次 LLM 调用现 build |
| **每 worker 会话** | 每 CLI session | ❌ | 按 worker 清 | worker session |

工作上下文**不存成可变 history**，而是每次 LLM 调用时现算：

```python
def build_llm_context(state) -> list[Message]:
    return assemble(
        task          = state.task,
        dag_snapshot  = state.dag.summarize(),       # 各任务状态 + 结果摘要
        transcript    = recent_slice(state.group_id), # 转录窗口切片
        summaries     = state.dag.result_summaries(), # 已完成任务的摘要（非全文）
    )
```

- **"reset"（replan 时）= 用更紧窗口 + 摘要重建工作上下文**，丢冗长中段。**转录不动。**
- replan 反而往转录**新发**一条"⚠️ 已重新规划：<原因>"。用户一条消息都不丢；被弃的工作上下文在 UI 折叠成摘要卡，不是删除。

这也顺带实现了 queryLoop 的**被动压缩**：不主动每轮压，等 LLM 返回 `prompt_too_long` 才用更紧窗口重 build，同一调用只压一次。

### 4.1 replan 给多少上下文（v2.2 新增旋钮）

**问题**：10 个 Task 各产几千字，若 replan 时 dump 全部摘要，光摘要就几千 token；且摘要本身若现算又是一次 LLM。三流分离暴露了这个旋钮却没拧。

**两点拧定**：

1. **上下文是失败子树局部的，不是全局的**。t7 失败 → replan 只需：

   | 部分 | 保真度 |
   |------|--------|
   | t7 本身（错误 + 尝试过程） | **全保真** |
   | t7 的直接依赖（它被喂了什么） | **全保真** |
   | t7 的下游（受影响范围） | 全保真 |
   | 其余无关任务 | **仅标题 + 状态**，不给全文 |

   你担心的"几千 token 摘要"只在 naive dump 全部时发生——replan 本就该子树作用域（§2.7 的 `scope`）。

2. **摘要增量产出，replan 时零额外调用**。每个任务在 `VERIFIED` 转换时**顺带产出自己的摘要**（小调用，或直接抽取 worker 的 final message）。到 replan 时摘要已存在，是事件溯源的标准投影模式，**不在 replan 时现算**。

```python
build_replan_context(state, scope) = assemble(
    failure      = full(scope.failed_task),        # 全保真
    deps         = [full(d) for d in scope.deps],  # 全保真
    downstream   = [full(d) for d in scope.downstream],
    rest         = [title_status(t) for t in state.dag if t not in scope],  # 仅标题
)
```

---

## 5. worker 卡死检测：四层机械 + 探活 + 预算兜底

v1 用 LLM ledger 轮询判"有进展吗"——又贵又不准。v2 用机械，但 v2.2 纠正一个 over-claim：**固定全局静默阈值是错的**（`npm install` 静默 5 分钟正常，`edit file` 后静默 5 秒就可疑）。修法仍主要机械：

| 层 | 机制 | 抓什么 | 触发事件 |
|----|------|--------|---------|
| **a. 心跳（push，免费）** | worker CLI 流吐 thinking/tool_use/tool_result，**每 chunk 即存活信号**；记 `last_event_ts` 和 `last_action` | 进程级存活 | — |
| **b. 条件化静默超时** | 阈值**查表于 `last_action`**：上个事件=`bash:npm install` → 容忍长静默；=`edit` → 应很快有后续。**不是全局常量** | 该动作下的异常静默 | `WorkerTimeout` |
| **c. 墙钟 + token 预算（终极兜底）** | 单任务 max 时长 / max token，即使前几层判不准也封顶截停 | 不收敛 / 语义打转但文本多变（d 抓不到的）| `WorkerTimeout` |
| **d. 重复检测** | 对最近 `(tool_name, args_hash)` 滑窗，同签名重复 > K 次 | 反复读同文件 / edit-revert-edit | `WorkerLoop` |

**两条关键纠正**：

- **thinking 不是静默**——thinking 本身在流式吐 token，那是事件。真静默 = thinking/tool/text 全无。"deep thinking 30 秒"其实有事件流，**不触发 b**。
- **kill 前先 OS 探活**：b 超阈值不立即杀，先查子进程 CPU 占用 / 进程状态。**挂死进程 vs 慢但在干活的进程，OS 层可区分**，零 LLM。

**诚实让步**：存在一类残余——agent 吐"看似合理但语义打转"的事件、CPU 也忙、d 层精确重复抓不到。这一类**只能靠 c 层预算截停后升级 LLM 复审**，而不是每次 check 都 LLM。所以 LLM 是预算触发后的末端手段，不是主检测器。a/b/d 覆盖常见情况，c 兜底残余。

- "worker 主动报卡死" = 加速快路径，**不当主力**（真卡的 worker 常不自知）。
- **检测主体仍零 LLM**；仅 c 层兜底截停后、需判 retry/replan 时 LLM 介入。

### 5.1 per-task 健康，取消全局 stall_count

并行下标量计数器语义破裂（健康任务的进展会把卡死任务的计数减回去，且丢失"是哪个"）。v2：

```python
@dataclass
class TaskHealth:
    last_progress_ts: float
    action_window: deque        # 近 N 个动作签名，供重复检测
    wall_start: float
    tokens_used: int
```

- 卡死是**单任务属性**，决策天然 per-task（修哪个子树、杀哪个 worker 都明确）。
- 异构时长自动正确：健康但慢的任务持续刷新心跳即可。
- **全局只留 `replan_count` / `max_resets`** 守卫"整体活锁"（replan → 同样计划 → 再 replan）。它计 replan 次数，不计轮次。

---

## 6. 验证闸门（修复"信 worker 自报"）

**铁律：验证者必须独立于干活的 worker —— 不能让 worker 给自己批作业。**

### 6.1 谁声明验收标准

- **Coordinator 在 plan 时**给每个 `TaskDef` 附 `acceptance: list[Check]`。它分解了任务，知道每个"做完"长什么样。
- **契约化**：没有 acceptance = 不可验证 = 不能自动标 VERIFIED，必须回退人工或显式 `no-verify` 标记并在 UI 暴露，**禁止静默通过**。
- 用户可对"整体目标"追加/覆盖标准。

### 6.2 检查类型（按可信度分级）

| 级别 | 谁执行 | 例子 |
|------|--------|------|
| **机械/确定（最高）** | **Harness 自己跑**（它控制 worktree）：`pytest` / `tsc` / `npm build` / lint / 端点探活 / schema 校验，**抓退出码 = ground truth** | "测试过没过"不再信文字 |
| **LLM 评审（中）** | **独立 Reviewer agent**（另开 CLI session，只读+可跑测试，**绝非实现者本人**）审 diff 对照标准 | "错误提示真是中文吗"、"代码符合设计文档吗" |
| **人工闸门（不可逆/外部）** | 用户 | `side_effect_level == external`（deploy/git push/发邮件）**无条件要人批** |

### 6.3 流程

```python
async def verify_and_settle(t, state):
    t.status = VERIFYING
    results = []
    for check in t.acceptance:
        match check.kind:
            case "mechanical": results.append(harness.run(check, t.worktree))  # 铁的
            case "llm_judge":  results.append(await reviewer_agent.review(t.diff, check))
            case "human":      results.append(await request_human_approval(check))
    if all(r.passed for r in results):
        merge_worktree(t, state.integration_ref)   # §7，过验证才合并
        t.status = VERIFIED
    else:
        t.fail_reason = collect(results)            # 回灌
        emit(WorkerFailed(t))                        # → retry 或 replan
```

- `is_request_satisfied` 只在**所有任务 VERIFIED + 集成验证（§6.4）+ 末尾总验收**通过才为真。
- **Coordinator 只汇总裁决，自己不验。**
- 验证在 worker 改动的**那个 worktree 里、合并前**跑。
- 标准定不出的模糊任务 = 欠拆解信号 → 问用户 / 显式标 `unverified` 并 UI 亮出，别假装过了。

### 6.4 集成验证闸门（v2.2 新增，抓语义冲突的可测子集）

**问题**：per-task 验证只在各自 worktree 隔离跑。两任务各自测试都过，**合并后组合逻辑可能错**（语义冲突，§7.4）。

**修法**：所有 merge 完成后、`is_request_satisfied` 之前，在**集成分支**上跑**全量 build + 全量测试**（不是各任务的局部测试）。

```python
async def integration_gate(state) -> bool:
    # 所有 task VERIFIED 且 merge 完后
    result = harness.run_full_suite(state.integration_ref)  # 全量 build + test
    if not result.passed:
        # 集成失败 → 定位冲突任务对 → replan 或交 reviewer
        await handle_integration_conflict(result, state)
        return False
    return True
```

- 抓住**会破坏测试的那部分语义冲突**——代价是一次全量测试，不是 per-task。
- 抓不到的残余（测试照样过的语义冲突）是并行开发普遍极限，见 §7.4。

---

## 7. git worktree 结构隔离（替代声明文件冲突检测）

### 7.1 机制

每任务一个 worktree，写操作天然不冲突，`can_parallel` 几乎恒真（不再信 LLM 声明的文件）：

```
base = integration_ref（HEAD 或集成分支）
dispatch:  每 task → git worktree add .wt/<task_id> <base>，worker 只动自己的 wt
verify:    在 wt 里跑（测试对隔离改动）
settle:    过验证 → merge wt → integration_ref
```

### 7.2 难点从"执行期竞态"搬到"merge 期冲突"——这是进步

两任务都改共享文件 → git **显式报冲突**，而非静默丢更新。处理：

- 按确定顺序串行 merge，第二个在第一个之上。
- 冲突 → (a) 把第二个 worktree rebase 到新 base 并**重跑其 verify**（测试快则便宜），或 (b) 冲突本身变成"解冲突"任务交 agent，或 (c) replan。
- merge 顺序确定且记入 `task_events`，保证可复现。

### 7.3 两个必须写死的边界

1. **依赖目录不随 git 隔离**：`node_modules` / `.venv` / build 产物是 gitignore 的，每个 worktree 可能各自装依赖 → JS/Python 很贵。缓解：共享依赖目录软链 / 基础镜像 / 只给"真写代码"的任务开 worktree，只读任务共用一个。
2. **git 隔离 ≠ 副作用隔离**：worker 写共享 dev DB、调外部 API，完全绕过 worktree。**worktree 只隔离文件。** `side_effect_level ∈ {mutable, external}` 仍需串行化/锁/事务/沙箱。

### 7.4 文本冲突 ≠ 语义冲突（v2.2 补，诚实标注边界）

worktree 把**静默丢更新**变成**显式 merge 冲突**（真进步），但 git 只抓**文本重叠**。两 agent 改同一函数不同部分 → 行不重叠 → merge 干净 → 各自测试过 → **组合逻辑错**（语义冲突）。

**v2 没有、也不可能有"零成本机械检测"语义冲突**。分层应对：

| 手段 | 抓住的 | 代价 |
|------|--------|------|
| **集成验证闸门（§6.4）** | 会破坏测试的语义冲突 | 一次全量测试 |
| **模块不相交分解** | 从源头降冲突面：decompose **偏好沿模块缝切任务**（t_A 拥有 `frontend/`，t_B 拥有 `backend/`）→ 集成期语义冲突稀少 | plan prompt 加偏置 |
| **reviewer agent 复审** | 测试覆盖不到但语义可疑的 | LLM 成本，按需 |

**诚实兜底**：测试照样过的语义冲突**根本上不可机械检测**——这是**并行开发的普遍极限**（人类两个 PR 各自过 CI 仍可能语义冲突），不是 v2 特有缺陷。v2 不让它更糟，集成闸门抓可测子集，残余须**显式暴露给用户**（"以下改动并行完成，建议人工复核集成结果"），**不静默吞**。

---

## 8. 数据结构

```python
@dataclass
class TaskDef:
    id: str
    title: str
    description: str
    suggested_worker: str               # 匹配 agent_registry
    depends_on: list[str]
    acceptance: list[Check]             # ★ v2 新增：验收标准（空 = no-verify 须显式标记）
    side_effect_level: Literal["none", "readonly", "mutable", "external"]
    compensate: str | None              # external 级补偿步骤
    expandable: bool = False            # ★ v2.2：True = 完成时触发动态扩图（§2.7）
    input_template: str | None = None   # ★ v2.2：动态输入占位（如"测试 {t_前端.output}"，§2.4）
    # 注意：v1 的 files 字段退役，隔离改由 worktree 负责

@dataclass
class Check:
    kind: Literal["mechanical", "llm_judge", "human"]
    spec: str                           # mechanical: 命令；llm_judge: 评审标准；human: 提示
    expect: str | None                  # mechanical: 期望退出码/输出

@dataclass
class TaskNode:
    task: TaskDef
    status: Literal["PENDING","RUNNING","VERIFYING","VERIFIED","FAILED","BLOCKED"]
    worker: str | None
    worktree: str | None
    output: str | None
    fail_reason: str | None
    retries: int = 0
    health: TaskHealth | None = None    # 仅 RUNNING 时有

@dataclass
class TaskLedger:                       # plan 阶段产出
    facts: str
    plan: str
    tasks: list[TaskDef]                # 解析为 DAG，build 时校验无环
```

`progress_ledger` / `next_wave` / `ProgressLedger` 数据结构**整体删除**——调度归 DAG，完成判定归末尾单次 `final_answer`。

---

## 9. 退出原因码（保留 v1 §4.2，确实是改进）

```
正常:    completed / user_cancelled
上限:    max_tasks / max_resets
卡死:    stalled_repeatedly（replan 活锁）/ worker_unavailable
资源:    context_too_long（压缩后仍超）/ budget_exceeded / api_key_failed
异常:    irrecoverable_error（DAG 损坏等）
```

---

## 10. LLM 调用预算（DAG 驱动后）

| 阶段 | 调用 | 次数 | 说明 |
|------|------|:---:|------|
| plan | facts + plan | 2 | 含 DAG 校验 |
| 调度 | — | **0** | 拓扑算就绪集，纯函数 |
| 卡死检测（a/b/d 层）| — | **0** | 机械 + OS 探活（§5）|
| 里程碑回顾 | still_on_track? | 里程碑数 | v2.2：汇聚点/偏离时，≪ 轮次（§2.6）|
| 验证（mechanical）| — | 0 | Harness 跑命令 |
| 验证（llm_judge）| — | 按需 | 独立 reviewer，仅测试覆盖不到时 |
| 集成验证 | full suite | 0 | v2.2：Harness 跑全量测试（§6.4），非 LLM |
| 失败恢复 / 扩图 | replan / expand | 每次 ≤2 | 子树作用域（§2.7·§4.1）|
| 完成 | final_answer | 1 | 末尾单次 |

**正常 3 任务、0 里程碑路径：plan(2) + final(1) = 3 次 LLM**（v1 是 6 次）。有里程碑回顾时 +里程碑数；失败/扩图/评审按需增量。**复杂度 O(里程碑 + 异常点)，仍无"每轮税"。**

---

## 11. Selector × Coordinator 边界（已决）

### 11.1 "它俩做一样的事"的疑虑在 v2 已消解

这个疑虑来自 v1：v1 的 Coordinator 每轮用 LLM 产 `next_wave`，**那本质就是"选人"**，和 Selector 的"选谁发言"同构，所以显得冗余。

v2 把调度权收归 DAG 后，Coordinator 的 LLM 调用只剩 `plan/replan/final_answer`——**没有一个是"选下一个发言者"**。两者决策空间彻底分叉：

| | 决策对象 | 操作类型 |
|---|---------|---------|
| **Selector** | `{参与者}` | 选择（谁说话） |
| **Coordinator** | `{任务图操作}` | 分解 + 验证编排（什么工作推进） |

**冗余在 v2 已不存在。** 剩下唯一重叠的只有边界那一条消息的分类。

### 11.2 生命周期不同 —— 拆开是必要解耦，不是把简单功能搞复杂

- **Selector = 每群组常驻**。纯讨论是默认态，大部分时间无任务在跑，但消息一直要路由。
- **Coordinator = 每任务临时**。有活才 spawn，跑完就死。

生命周期不同 ⇒ 即便概念相邻也该是两个对象，否则常驻廉价路由器要永远背一身用不上的编排机器。

### 11.3 裁决：Selector 常驻前门 + Coordinator 被投喂的引擎

否决"两态轮流坐庄"（Selector 交班退场）的画面——因为**执行期讨论不会停**，Selector 一停就没人路由那些消息。正确模型：

```
DISCUSSION 态：Selector 路由 {用户, Agent 们}
   │ Selector 检测执行意图 → 压缩上下文 → spawn Coordinator
   ▼
EXECUTION 态：Selector 仍在前门，路由目标多了一个 Coordinator
   ├ 任务相关消息 → 喂给 Coordinator（UserInterrupt 事件）
   ├ 控制消息（@coordinator / 停 / 取消）→ 机械识别，直达 Coordinator
   └ 纯讨论 → 照旧在 Agent 间路由，不打断 DAG
```

**不是"一个东西的两个状态轮流"，而是"一个常驻路由器（Selector）+ 一个它按需 spawn 并投喂的临时引擎（Coordinator）"。**

### 11.4 这样如何同时解决"双重分类"与"打架"

- **不双重分类**：Selector 答"去哪"（一次分类，多数还能机械判），Coordinator 答"对任务图做什么操作"——**不同的问题，不是同一次分类重复两遍**。"加个限流"→Selector 判"任务相关→给 Coordinator"，Coordinator 判"注入新节点"（≈ 迷你 replan）。各答各的。
- **不打架**：路由权威唯一（Selector），Coordinator 不抢路由。
- 很多操作零 LLM："做完了吗"→读 DAG 状态机械答；"停"→机械识别。LLM 只在真·改需求时才上。

### 11.5 产品语义裁定：Coordinator = 引擎，不是人

用户**不通过独立通道直接跟 Coordinator 对话**，所有消息都走 Selector 这扇门。这绕过了"Coordinator 是不是群里一个人"的纠结。

### 11.6 交接压缩必须保约束

讨论→执行的上下文压缩**必须保住需求/约束清单**（"错误提示用中文""5 次锁定 30 分钟"是执行硬约束），不能只做叙事摘要。交接产物是**结构化需求 + 约束清单**，不是一段话总结。详见 §13.3。

### 11.7 执行 / 讨论共存模型（不是接管）

**协调者只接管"任务执行（DAG）"，不接管群聊。** Selector 常驻前门，执行期讨论不被锁死——执行与讨论**共存**，不是互斥的模式切换。

```
任务执行（DAG 调度/派发）  → Coordinator 管
群组对话（谁说话）          → Selector 管（一直在）
                            ↑ 两者共存
```

执行期用户消息按类型分流：

| 执行期消息 | 处理 | 执行受影响 |
|-----------|------|:---:|
| 闲聊 / 与任务无关 | 路由给**空闲** agent，正常讨论 | 否 |
| "做到哪了" | Orchestrator 读 DAG 状态机械回答 | 否 |
| **"重新讨论下设计"**（想改方案）| 见 §11.8 | 是 |
| @ 空闲 agent | 正常聊天 | 否 |
| **@ 正在执行的 agent** | 见 §11.9 | 取决于内容 |

### 11.8 执行中想重新讨论设计 —— MVP 取消重讨论，标准暂停 replan

| | 做法 |
|---|------|
| **MVP** | **取消 → 回纯讨论 → 讨论 → 新执行**。用户发"停/重新讨论" → Orchestrator 收 cancel → DAG 终止 → 回 DISCUSSION → 自由讨论 → 新方案再 decompose。MVP 无暂停机制（串行循环）|
| **标准** | **暂停 → 讨论 → replan/resume**，不用全取消，省掉进行中工作 |

**成果保留（重要）**：MVP 取消时，**已 VERIFIED 的任务成果保留**（文件留在 workspace），cancel 只停后续派发。否则"执行一半→讨论→继续"每次都白做。`user_cancelled` 退出不回滚已完成节点。

```
讨论设计 ──decompose──→ 执行中
   ↑                      │
   └── 用户"停/重新讨论" ──┘   (MVP: cancel→回讨论；已 VERIFIED 成果保留)
   讨论新方案 ──decompose──→ 新执行
```

### 11.9 @ 正在工作的 agent —— busy-aware 路由（防 CLI session 撞车）

worker 执行任务用的是该 Agent 的 CLI session（key=`uuid5(session_id:agent_id)`）。**现状 Selector L1 @mention 直接路由、零 busy 检查**——若 @ 一个正在执行的 worker，聊天回复会撞上正在执行的同一 session。

**修正：EXECUTION 态 Selector 先查 busy**（Agent 实体 `status`/`workload` 字段）：

| @ 对象 | 处理 |
|--------|------|
| **空闲 agent** | 正常聊天（不影响其他 agent 执行）|
| **正在执行的 worker** | **不起聊天轮次**（避撞车）→ 转 **Coordinator** 当 `UserInterrupt`。因为 @ 忙碌 worker 几乎都是任务相关（纠正/问进度），该由掌握任务状态的 Coordinator 处理 |

**MVP 行为**：@ 忙碌 worker → Coordinator 回"该 agent 执行中，消息已记录，完成后处理"（MVP 不支持执行中改需求），不打断不撞车。**标准**：Coordinator 按 §A2 分类（问进度→机械答；改需求→replan）。

> 落地：worker 执行时标 `status=busy`，Selector L1 对 busy 成员改走 EXECUTION 路由（属 Phase 5 接线 + 标准 A2）。

---

## 12. 关键设计决策

| # | 决策 | 原因 |
|---|------|------|
| 1 | DAG 独占调度，删 next_wave | 有 DAG 就不需要每轮 LLM 重判；消除双调度冲突 |
| 2 | 事件驱动，无轮次 | 调度是 DAG 纯函数；LLM 复杂度 O(里程碑 + 异常点)（v2.2 修正）|
| 3 | per-task 健康，删全局 stall_count | 并行下标量语义破裂；replan 需知"是哪个" |
| 4 | 机械卡死检测 + 条件化阈值 + OS 探活 + 预算兜底 | LLM 判活锁贵；阈值须条件化于动作类型，非全局常量（v2.2）|
| 5 | 事件溯源 + 可变投影 + 单写者 | task_events 才是真不可变底座；frozen 是假象 |
| 6 | 三流分离 | replan 不能让用户群聊消息消失 |
| 7 | 独立验证闸门 | worker 不能批自己作业；完成判定要 ground truth |
| 8 | worktree 结构隔离 | 声明文件冲突是假安全；git 把竞态变显式冲突 |
| 9 | 保留退出码 + 被动压缩 | queryLoop 真正值得抄的两点 |
| 10 | 删 §4.4 流式抢跑分发 | 50s 任务前省 500ms JSON 流是噪音，纯 cargo-cult |
| 11 | Selector 常驻前门 + Coordinator 被投喂引擎（§11） | 冗余在 v2 已消解；生命周期不同；单分类器解决双重分类与打架 |
| 12 | 上下文管理不放 Selector，放交接压缩 + Coordinator 工作上下文（§13.3） | Selector 是常驻廉价路由器，纯函数但不隔离系统状态 |
| 13 | 里程碑回顾（§2.6） | plan 错不能只末尾发现；中期回顾，粒度介于每轮与只末尾之间（v2.2）|
| 14 | 调度 vs 图变更分离 + 动态输入/结构区分（§2.7）| "LLM 不参与调度"指就绪集；造节点仍用 LLM；多数"动态"是动态输入零 LLM（v2.2）|
| 15 | replan 子树作用域 + 增量摘要（§4.1）| 失败子树全保真、其余仅标题；摘要预算可控（v2.2）|
| 16 | 集成验证闸门 + 模块不相交分解（§6.4·§7.4）| worktree 只解文本冲突；语义冲突靠全量测试 + 降冲突面，残余是普遍极限须暴露（v2.2）|
| 17 | 执行/讨论共存，非接管（§11.7）| 协调者只管 DAG，群聊仍 Selector；执行期讨论不锁死 |
| 18 | 执行中重讨论：MVP 取消重来 + 成果保留，标准暂停 replan（§11.8）| MVP 无暂停；已 VERIFIED 不回滚 |
| 19 | @ 忙碌 worker → Coordinator，非起聊天轮次（§11.9）| 同 CLI session 撞车；@ 忙碌 worker 几乎都任务相关 |

> **Phase 5 接线待办（新增）**：worker 执行时标 `status=busy`；Selector L1 对 busy 成员改走 EXECUTION 路由；`user_cancelled` 不回滚已 VERIFIED 节点。

---

## 13. 与现有代码的接线方案

> 基于实读 `src/backend/app/` 现状（2026-06-05）。下列文件路径与行号为当前真实代码，非设计草案。

### 13.1 现状盘点（已存在的 vs 缺的）

| 组件 | 文件 | 现状 |
|------|------|------|
| **Selector** | `application/services/selector.py` | ✅ 四层路由器（L1 @mention / L1.5 broadcast / L2 capability / L3 LLM tool_use）。**LLM 只是兜底层**，机械前门已实现。**纯函数：无自持可变状态**（`pick(members, history, already_spoken)`），但不隔离于系统状态——见 §13.3。|
| Selector 决策空间 | `selector.py:276` `_tool_schema` | ❌ enum 仅 `["next","multi","done"]`，**无 `decompose` 出口** → 当前没有 Selector→Coordinator 的路 |
| **DiscussionOrchestrator** | `application/services/discussion_orchestrator.py` | ✅ 有界回合循环（`max_round` 默认 3），即起即灭。`_load_members:297` 已注释"不含协调者" |
| **驱动点** | `application/services/chat_service.py:156-162` | `_handle_group` 仅在 `DispatchMode.DISCUSSION` 跑 `run_discussion`，**无 Coordinator 分支** |
| **Coordinator** | `domain/task_engine/coordinator.py` | ⚠️ 仅骨架：`decompose(message, agents, history) → TaskPlan`，注释"MVP 骨架，M3 接真实 LLM"。**无人调用**，无事件循环/FSM/验证 |
| **Harness** | `domain/task_engine/harness.py` | 有 `validate(plan)`（DAG 校验雏形） |
| 基础设施 | `core/events.py` `EventBus` / `watermark_store` | ✅ 已有事件总线 + watermark 推送机制，可复用做异步进度推 |

**结论：方向对（机械前门 + LLM 兜底已落地），缺的是三根接线。**

### 13.2 三根接线（按严重度）

| # | 接线 | 改动点 | 必要性 |
|---|------|--------|:---:|
| 1 | **决策出口 `decompose`** | `selector.py`：`SelectorDecision` 加 `decompose()` 构造器；`_tool_schema` enum 加 `"decompose"`；L3 prompt 增加"识别执行意图"规则。**触发器留 L3 LLM，不做关键词**（执行意图天生模糊，关键词会误触发，区别于 L1.5 broadcast） | 必须，否则不通 |
| 2 | **CoordinatorRun 事件循环** | `coordinator.py`：当前只有 `decompose`（= v2 的 plan 阶段）。需补全 §2 的事件驱动主循环 + §2.3 FSM + §5 机械卡死检测 + §6 验证闸门 | 必须，是 v2 主体 |
| 3 | **后台任务化 spawn + WS 异步推** | `chat_service.py`：`send_and_stream` 是"请求→流→结束"模型；Coordinator 跑几分钟、期间用户还发消息，**不能塞进一次请求的同步子流**。需起独立后台任务，进度经 `EventBus` 异步推（复用现有 watermark），并注册到 `active_runs[session_id]` | **真正的架构改动**，最易低估 |

### 13.3 上下文管理放哪（关键纠偏：不在 Selector）

**Selector 必须保持无状态。** 它是常驻廉价路由器，现在的"最近 15 条、每条截 300 字、代码块省略"（`selector.py:236-244`）对"选谁发言"**完全够用**——路由不需要完整上下文。给它加记忆 = 错误。

上下文管理属于另外两处：

| 处 | 职责 | 落点 |
|----|------|------|
| **① 交接压缩**（讨论→协调者） | 从**完整历史 + L1 memory**（不是 Selector 那截 15 条）构建**结构化需求 + 约束清单**。现 `coordinator.py:23` 收 `conversation_history: list[dict]`，若直接 dump 原始历史 = 劣质摘要，会丢硬约束 | **新组件** ContextHandoff，喂给 `Coordinator.decompose` |
| **② Coordinator 工作上下文**（执行期） | §4 三流分离：DAG 快照 + 各任务结果摘要 + 转录窗口，每次 LLM 调用现 build，replan 时重建 | Coordinator 自身职责 |

**Selector 唯一要新增的"上下文"是一个输入参数** `active_coordinator: Handle | None`——让它知道本 session 有无协调者在跑（有则任务相关消息路由给 Coordinator，控制消息走机械快路径）。

**措辞精确化（v2.2，回应"纯函数 vs 状态参数"反驳）**：说 Selector"无状态"太绝对。准确是——

- **Selector 是纯函数**：无自持可变状态，同入参 → 同输出。
- **但不隔离于系统状态**：调用方每次注入一份系统状态快照（`active_coordinator`）。
- **职责落在调用方**：`ChatService` 维护 run-registry，每次 `pick` 时查表注入。

即"纯函数"约束的是 Selector 内部，不代表它与系统状态绝缘。设计本身不变，只是不再把"无状态"说成"与系统状态无关"。

### 13.4 接线后的消息流

```
用户消息 → ChatService.send_and_stream
  → Selector.pick(members, history, active_coordinator=registry.get(session))
     ├ active 为空（DISCUSSION 态）:
     │    decision=next/multi/done → run_discussion（现状不变）
     │    decision=decompose       → ContextHandoff 压缩 → Coordinator.decompose
     │                              → 起 CoordinatorRun 后台任务 → registry 注册
     └ active 非空（EXECUTION 态）:
          @coordinator/停/取消（机械） → emit UserInterrupt 到 CoordinatorRun
          任务相关（L3 LLM 判）        → emit UserInterrupt（task_modification）
          纯讨论                      → run_discussion（不打断 DAG）
  → CoordinatorRun 进度 → EventBus → WS 异步推（复用 watermark）
```

### 13.5 A 类决策敲定（实现前定论，2026-06-05）

两个"写代码前必须拍板"的问题，决定如下。**两者都不破坏现有 L1/L1.5/L2/L3 发言选择逻辑。**

#### A1：decompose 放哪 —— 独立"意图预闸门"，不混入发言选择层

**否决**"塞进 L3 enum"（L2 命中会先短路，到不了 L3）和"demote L2"（动现有讨论行为，有回归风险）。

**决定**：decompose 是**模式决策（要不要开始执行）**，不是**发言选择（谁说话）**——架构上是不同的决策，所以放在发言选择层**之前**做，且只在 DISCUSSION 态：

```python
async def pick(members, history, active_coordinator):
    last = history[-1]
    if active_coordinator is None:               # DISCUSSION 态
        # === 新增：意图预闸门（在 L1 之前）===
        if work_intent_prefilter(last):          # 机械：祈使 + 动作词(帮我/实现/创建/写个) 且非纯提问
            intent = await llm_intent_check(last, history)   # 1 次聚焦 LLM：decompose | discuss
            if intent == "decompose":
                return SelectorDecision.decompose()
        # === 以下 L1/L1.5/L2/L3 完全不动 ===
        return await _existing_speaker_selection(members, history)
    else:                                        # EXECUTION 态（见 A2）
        return await _execution_routing(last, active_coordinator, members, history)
```

- **机械预滤先行**：纯讨论（"我觉得 React 好"）无动作词 → **跳过 LLM**，零成本走原有逻辑。LLM 只在有工作动词的候选消息上烧，正是该花的地方。
- **不碰现有四层**：零回归风险。

#### A2：执行期插话分类 —— control 机械，其余 1 次聚焦分类

修正场景推演 Phase 3 "零 LLM 机械回答"的错误（分类本身需要判断）：

```python
async def _execution_routing(last, coord, members, history):
    if is_control(last):                         # 机械：停/取消/暂停/stop/cancel
        return SelectorDecision.interrupt(coord, kind="control")  # 零 LLM
    if not directed_at_coordinator(last):        # 没 @coord 也非任务相关 → 闲聊
        return await _existing_speaker_selection(members, history)
    kind = await llm_classify(last, history)     # 1 次：question | modification | chitchat
    match kind:
        case "question":     return SelectorDecision.interrupt(coord, kind="question")
        #   → Coordinator 读 DAG 状态机械回答（答案机械，但分类用了 1 次 LLM）
        case "modification": return SelectorDecision.interrupt(coord, kind="modification")
        #   → 图变更（§2.7 replan/expand）
        case "chitchat":     return await _existing_speaker_selection(members, history)
```

**一条非 control 插话 = 1 次分类 LLM**，接受。不做脆弱的关键词分类（"加了限流吗"含"加"却是提问）。

#### A1/A2 的分级落地

| | MVP（§14.1）| 标准（§14.2）|
|---|---|---|
| A1 decompose 预闸门 | ✅ 必须（否则触发不了协调者）| ✅ |
| A2 control 机械取消 | ✅ 只做这个 | ✅ |
| A2 question/modification 分类 | ❌ **执行期不接受改需求**：非 control 插话先排队/忽略，跑完再说 | ✅ 全量 |

MVP 把执行期插话砍到只剩"取消"，回避 A2 的分类成本。改需求是标准档能力。

---

## 14. 落地分级（MVP / 标准 / 完整）

> 防止 v2.2 的"全都要"导致首版难产。三档**各自是能独立交付的完整闭环**，不是半成品；升档触发条件明确。**减法优先：先砍到 MVP 能跑，再按真实需求逐档加。**

### 14.1 档 1 — MVP：串行最小闭环

**目标**：验证主链路"协调者分解 → 分派 → 验证 → 汇总"能端到端跑通。

**关键简化：并发度 = 1（串行拓扑执行）** —— 一次只跑就绪集里的一个任务。这一刀**绕开 worktree / merge / 集成冲突全家桶**，MVP 复杂度骤降。仍是 DAG 驱动，只是 concurrency=1。

| 启用 | 不做（接受风险） |
|------|----------------|
| DAG 调度 + 事件循环 + FSM（§2.2-2.3）| 并行 / worktree / 集成闸门（串行无 merge，天然不需要）|
| plan：decompose + Harness 校验（§2.1）| 里程碑回顾（§2.6）—— 接受"plan 错末尾才知" |
| 机械验证（有 acceptance 才验，§6.2 机械层）| llm_judge / human 闸门 |
| 硬超时兜底（§5 c 层墙钟/token）| a/b/d 精细卡死检测 + OS 探活 |
| **转录不删铁律**（§4，一行纪律）| 三流完整重建 / 被动压缩 |
| 单写者 + `task_events`（§3）| LLM replan —— 失败则**重试 N 次 → 升级问用户** |
| Selector `decompose` + spawn（§13）| 动态扩图 / 模块不相交分解 |
| 退出码子集：completed/failed/cancelled/budget | 多档 HITL / 补偿 |
| 基础任务面板 + 完成消息（Q2）| per-task 流展开 / 干预控件 |

**升档信号**：用户要并行加速 / 串行太慢 / 失败需要自动改方案而非每次问人。

### 14.2 档 2 — 标准：并行 + 安全网

**目标**：真实可用——并行加速 + 自动纠错。在 MVP 上增量加：

| 新增 | 章节 | 备注 |
|------|------|------|
| **并行执行 + worktree 隔离 + 集成验证闸门** | §2·§7·§6.4 | **三件套绑定**：并行才需 worktree，worktree 才需集成闸门 |
| 全卡死检测（a/b/d + 条件化阈值 + OS 探活）+ per-task 健康 | §5·§5.1 | 取代 MVP 的单一硬超时 |
| **LLM replan**（子树作用域 + 增量摘要）| §2.7·§4.1 | 取代 MVP 的"重试→问人" |
| llm_judge 验证 + external 人工闸门 | §6.2 | 测试覆盖不到的语义 + 不可逆操作 |
| 三流完整（工作上下文重建 + 被动压缩）| §4 | replan 上下文质量 |
| 前端 per-task 流展开 + 干预控件（暂停/取消/反馈）| Q2 | 多路并行不刷屏 |
| （可选）plan review 人工闸门 | Q1 | 高风险任务执行前批准 |

**接受的风险**：长 plan 跑偏仍末尾才发现；语义冲突只抓测试可见的；开放式任务做不了。

**升档信号**：长链路任务（>N task / 有汇聚点）/ 开放式任务（勘探类）/ 高风险生产副作用。

### 14.3 档 3 — 完整：复杂 / 高风险

在标准上增量加：

| 新增 | 章节 | 适用 |
|------|------|------|
| **里程碑回顾**（汇聚点中期纠偏）| §2.6 | 长链路，防 plan 跑偏 |
| **动态扩图**（运行时产子任务）| §2.7 | 开放式任务（"勘探→修 bug"）|
| 模块不相交分解偏置 | §7.4 | 降语义冲突面 |
| external 补偿步骤 + 4 层 HITL | §6·§8 | 高风险生产操作可回滚 |
| 语义冲突**显式暴露** + reviewer agent 复审 | §7.4 | 测试照样过的残余冲突 |

### 14.4 机制 × 档位 速查矩阵

| 机制 | MVP | 标准 | 完整 |
|------|:---:|:---:|:---:|
| DAG 调度 + 事件循环 + FSM | ✅ | ✅ | ✅ |
| plan（decompose + 校验）| ✅ | ✅ | ✅ |
| 机械验证闸门 | ✅ | ✅ | ✅ |
| 转录不删 + 单写者 + task_events | ✅ | ✅ | ✅ |
| Selector decompose + spawn | ✅ | ✅ | ✅ |
| 串行执行（concurrency=1）| ✅ | — | — |
| 硬超时兜底（仅 c 层）| ✅ | ↑ 升级 | ↑ |
| 并行 + worktree + 集成闸门 | — | ✅ | ✅ |
| 全卡死检测（a/b/d + 探活）+ per-task 健康 | — | ✅ | ✅ |
| LLM replan（子树 + 增量摘要）| — | ✅ | ✅ |
| llm_judge + external 人工闸门 | — | ✅ | ✅ |
| 三流完整 + 被动压缩 | — | ✅ | ✅ |
| 前端 per-task 流 + 干预控件 | — | ✅ | ✅ |
| plan review | — | 可选 | ✅ |
| 里程碑回顾 | — | — | ✅ |
| 动态扩图 | — | — | ✅ |
| 模块不相交分解 + 语义冲突暴露 + reviewer | — | — | ✅ |
| 补偿 + 4 层 HITL | — | — | ✅ |

> **落地建议**：MVP 是骨架验证，**别为它做 worktree**（串行就够）。等真有并行需求再整体上档 2 的"并行三件套"。档 3 的里程碑回顾/扩图按**任务画像**触发（长链路、开放式才开），不是默认全开。

---

## 关联文档

- [[coordinator-subsystem-collaborators]] 子系统协作者分解（5 协作者怎么咬合、谁是 LLM 谁是代码、上下文/工具）
- [[coordinator-test-plan]] 测试计划（given/when/then 骨架，实现前必读）
- [[coordinator-queryloop-design]] v1（本文取代）
- [[coordinator-design-evolution]] 设计演进
- [[scenario-walkthrough]] 场景推演（7 待解问题，本文解决其中 4/5/6/7）
- [[task-execution-open-questions]] 待解问题（Selector 边界已在 §11/§13.5 定论）
- [[maf-implementation-analysis]] MAF 源码分析
