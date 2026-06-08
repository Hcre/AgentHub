# Coordinator 设计 v3 — 单一 Planner 大脑 + 统一路由

> 日期：2026-06-07 | 状态：设计稿 v3.0 草案
> 关联决策：[[0003-single-coordinating-brain]]（ADR-03）· 取代 [[coordinator-dag-driven-design-v2]] 的前门部分
> **复用**：v2 §1–§7（Harness/DAG/FSM/验收/worktree/事件溯源，已实现，一字不变）
> **取代**：v2 §11（Selector×Coordinator 边界）、v2 §13（前门接线）、v2 §13.5 A1（decompose 预闸门）

---

## 0. v3 相对 v2 的核心变更

v2 在「执行期」想清楚了单一路由器（§11 很好），却在「讨论→执行的入口」上退回了双脑：给边界消息单独搭了个 `work_intent_prefilter`（机械白名单）+ `llm_intent_check`（独立 LLM）的预闸门（§13.5 A1）。白名单是封闭集套开放集，必漏——「可以直接干吧」「重试」这类承接语没有工作动词，直接被挡在协调者门外（实测 bug，2026-06-07）。

v3 收敛一个地基问题：**把"选人"和"协调"统一为同一个 Planner 大脑的两种规划视野**。

| # | v2 的问题 | v3 的决策 |
|---|----------|----------|
| 1 | gate + selector + planner = 三处 LLM 决策，前两者重叠 | **一个 Planner 大脑**：reactive 视野=选发言人，deliberate 视野=decompose/replan |
| 2 | decompose 用机械白名单预滤（脆弱，开放集必漏） | **删白名单**：路由是 Planner 的一次决策，"是不是任务"只是它的一种输出 |
| 3 | "执行态/讨论态"两套路由分支（A2 独立分类器） | **不分态**：插话进同一 Planner，`active_plan` 是它读到的状态 |
| 4 | 双脑无共享状态（"没有胼胝体"），交接丢意图 | **统一 SessionState**：两条事件流的只读投影，Planner 每次读全量 |

**不变的**：v2 §1–§7 的全部 Harness（确定性编排）。v3 只动"大脑"和"前门"，不动"骨架"和"手"。

---

## 1. 架构定位：一个大脑 + 一套骨架 + N 只手

```
┌──────────────────────────────────────────────────────────┐
│                     ChatService（前门）                     │
│   control 机械反射（停/取消）→ 直达 run                      │
│   否则 → Planner.decide(SessionState)                      │
└───────────────────────────┬──────────────────────────────┘
                            │
              ┌─────────────▼─────────────┐
              │   Planner = 唯一大脑（LLM）  │
              │   输出 action:             │
              │   respond / task / replan  │
              │   / done / (control 已前置) │
              └──────┬──────────────┬──────┘
            轻 dispatch          重 dispatch
                 │                  │
        ┌────────▼───────┐  ┌───────▼──────────────────────┐
        │ respond 执行     │  │ Harness（v2 §1–§7，零 LLM）    │
        │ agent 出消息     │  │ DAG 调度/FSM/验收/worktree/事件 │
        │ 无验收/无产物    │  │  └─ 派 worker 执行 work-step   │
        └────────────────┘  └──────────────────────────────┘
                 │                  │
                 └──── worker（手，CLI session，全工具）────┘
```

**三层定位**（沿用 v2 §1.1 的 LLM/Harness 二分，把"选人"也收进 LLM 层）：

| 层 | 是谁 | 形态 | 工具 | 上下文 |
|----|------|------|------|--------|
| **大脑** Planner | 决定下一个 dispatch | LLM（裸 API 或 CLI session） | reactive 零工具 / deliberate 可选只读 | 分层供给（§7） |
| **骨架** Harness | DAG/FSM/验收/事件循环/merge | 确定性代码 | — | 读 SessionState |
| **手** Worker | 执行 respond / work step | agent CLI session | 全工具 | 自持 CLI 记忆 |

> **记忆边界**：跨会话长期记忆是 worker/agent 的事（现有 memory 系统不动）。Planner 的"记忆"就是 SessionState 的投影（§3），不另设。

---

## 2. 统一规划模型：一个 Planner，两个视野

**核心命题（ADR-03 具体化）**：Planner 的输出永远是一个 plan；plan 是 steps 的 DAG；**一次对话发言 = 一个只有 1 步、step 类型为 `respond` 的退化 plan**。"选谁发言"就是"规划一个 1 步 respond"。

唯一的变量是**规划视野**与 **step 类型**：

| | 对话（reactive） | 任务（deliberate） |
|---|---|---|
| 视野 | horizon=1，**每轮重规划** | horizon=N，**规划一次** |
| 为何 | 目标不可预测，只能走一步看一步 | 目标已知可分解 |
| step 类型 | `respond`（出消息，无验收，产物=消息） | `work`（写代码/改文件，有验收，产物=artifact） |
| 终止 | 收敛（软，LLM 判 done） | 全 VERIFIED 且 satisfied（硬，机械+末次 LLM） |

> **为什么对话"感觉不一样"，本质是目标可预测性决定视野**。同一个大脑，两个视野 = System-1（快反射）/ System-2（慢深思）。

### 2.1 关键边界：统一决策，不统一执行（防过度统一）

- **统一**：决策层（Planner 决定下一个 dispatch）+ 回合循环抽象。
- **不统一**：执行引擎。`respond` 是**轻执行**（agent 出一条消息），**绝不**走 DAG/验收/worktree 那套；`work` 才走完整 Harness。

> 一句"hi"不该触发 decompose+建图+验收。对话是任务在**决策/规划层**的退化特例，**不在执行引擎层**。

### 2.2 两档 LLM 调用（成本纪律）

Planner 不是每条消息都付 decompose 的钱：

```
reactive 调用（轻，每条非 control 消息）:
    Planner.decide(state) → respond(who) | multi | done | NEEDS_TASK
                                                          │
deliberate 调用（重，仅 NEEDS_TASK 时）:                    ▼
    Planner.plan(state)  → 完整 DAG（decompose）
```

- 多数聊天止于 reactive 一次轻调用。
- 判 `NEEDS_TASK` 才进 deliberate 出 DAG。
- reactive 前还有零 LLM 反射快路（§4），@mention 等直接短路。

---

## 3. 统一状态：SessionState（两条事件流的只读投影）

ADR-03 说双脑缺"胼胝体"——SessionState 就是它。**但它不是新造的可变上帝对象，是 `messages` + `task_events` 两条 append-only log 的 read-model。**

```python
@dataclass
class SessionState:
    session_id: UUID
    group: Group
    members: list[Agent]

    # 对话流（投影自 messages 表，已事件溯源）
    transcript: list[Message]          # 追加不删（v2 §4 铁律）

    # 任务流（投影自 task_events，已事件溯源；纯对话时 None）
    active_plan: TaskGraph | None      # DAG + 各节点 FSM 状态
    constraints: list[str]             # handoff 产出的硬约束（v2 §11.6）

    # 运行句柄（进程级 registry）
    run_handle: CoordinatorRun | None  # 在跑的执行 + 取消句柄

    watermarks: dict[UUID, UUID]       # per-agent 读位（Redis，已有）
```

纪律：
- **read-model，不是新可变结构**。DAG 变更仍走单写者事件（v2 §3）；transcript 来自 `messages`。
- Planner 每次决策**读整个 State**（含有没有 `active_plan`）→ 这是统一路由的基础（§4）。
- `active_plan is None` ⟺ 纯对话态；非 None ⟺ 有任务在跑。**没有显式的 mode 枚举**，态由 active_plan 派生。

---

## 4. 统一路由：一个 Planner，消除双脑/双分类

```
用户/Agent 消息 → ChatService
  │
  ├─ is_control(text)  [机械正则，零 LLM，安全反射，离线可用]
  │     → 有 run：cancel；无 run：忽略
  │
  ├─ 零 LLM 反射快路（System-1）:
  │     @mention 直达（busy-aware，见 v2 §11.9）
  │     全体意图（大家/各位…，仅用户消息）
  │     （capability 关键词层：见下方"待决"）
  │
  └─ Planner.decide(SessionState)  [一次 reactive LLM]
        active_plan is None:
            respond(who) / multi / done → 轻执行（出消息）
            NEEDS_TASK → Planner.plan() → 起 Harness（重执行）
        active_plan 非 None（任务在跑）:
            chitchat   → respond(空闲 agent)，DAG 不动
            progress   → respond（读 DAG 状态答）
            modify     → replan（§6）
```

**与 v2 的差别**：

| | v2（已实现） | v3 |
|---|---|---|
| 决策段数 | 两段：gate（机械预滤+intent LLM）+ selector | **一次** Planner 决策 |
| "是不是任务" | 独立预闸门 + 脆弱白名单 | 只是这次决策的一种输出，**无白名单** |
| 执行态/讨论态 | 两套分支（A2 独立分类器） | 同一 Planner，`active_plan` 是输入 |
| control | 机械 | 机械（保留） |

**这一刀直接铲掉**：`CoordinatorGate.has_work_intent`、`is_decompose`、`_WORK_VERBS` 全删；`CoordinatorGate` 类消失（`is_control` 移入 ChatService 前置反射）。

---

## 5. 五种 action 与两种执行策略

```
Planner 输出 ∈ { respond(agent) | multi(agents) | task(plan) | replan(delta) | done }
                control 已在前门机械处理，不进 Planner
```

| action | 执行策略 | 验收 | 产物 |
|--------|---------|------|------|
| `respond` / `multi` | **轻**：调 agent CLI 出消息，追加 transcript | 无 | 消息 |
| `task` | **重**：`Planner.plan()` 出 DAG → 起 Harness（v2 §2 事件循环） | 有（v2 §6） | artifact |
| `replan` | 在跑的 Harness 内做图变更（§6） | 同上 | 同上 |
| `done` | 结束本轮讨论 | — | — |

`respond` 的轻执行复用现 `DiscussionOrchestrator` 的单 agent 流式逻辑（剥掉它自带的 selector 循环——选人已上移到 Planner）。`task` 的重执行复用 v2 已实现的 `task_engine.Orchestrator`。

---

## 6. 任务中插话改计划（统一循环的最大红利）

v2 把它砍到 MVP 只剩取消（§11.8），因为 v2 的"执行态"是独立路由分支。v3 里**插话就是又一条消息进同一个 Planner**——它读 State 看到 `active_plan` 非空，自己判 chitchat / progress / modify。

**modify 时执行循环的表现**（复用 v2 §2.2 事件循环 + §2.7 扩图）：

```
新消息 → Planner 判 modify → emit UserInterrupt(new_constraint) 到 run
  │
  └─ 事件循环收 UserInterrupt:
        Planner.replan(SessionState + new_constraint)   [deliberate LLM]
        diff(旧 DAG, 新 DAG)
        受影响的在飞 step → 给 worker 发 cancel/reset 信号
        已 VERIFIED 节点保留（成果不回滚，v2 §11.8）
        dispatch_frontier 重新派发新就绪集
```

**v3 比 v2 强**：v2 需要独立的"执行期插话分类器"（A2，额外 LLM 分支）；v3 里改不改计划是**同一个 Planner 决策**的自然输出——`active_plan` 只是它读到的状态。**一个脑，不分态。**

> 分级：MVP 仍可只做 control 取消（execution 期 modify 排队/忽略），但**架构上不再是特例**——升级到支持 modify 时无需新增路由分支，只是放开 Planner 在 active_plan 非空时返回 replan。

---

## 7. 上下文管理：按视野分层供给

v2 §13.3 那句"不给 selector 加记忆，但 handoff 和工作上下文要富"是对的——v3 里它俩变成**同一个 Planner 的两档上下文供给**。

| 视野 | 供给什么 | 落点 |
|------|---------|------|
| **reactive**（出"谁回"/判 NEEDS_TASK） | 近窗口（现 selector 的 15 条、每条截断） | ContextBuilder 轻档 |
| **deliberate**（decompose/replan） | 结构化需求+约束（handoff）+ 可选探仓库（只读工具）+ DAG 快照+任务结果摘要（v2 三流 §4） | ContextHandoff + Coordinator 工作上下文 |

- **"无状态"的准确含义**（v2 §13.3 措辞，现用于 Planner）：不自持可变状态、每次读 SessionState；**不等于"无上下文"**。
- **handoff 保留为独立组件**：讨论→任务时从完整历史+L1 memory 压缩出结构化需求+约束（不丢硬约束），喂给 `Planner.plan()`。

---

## 8. 与 v2 的关系（明确复用 / 取代边界）

| v2 章节 | v3 处置 |
|---------|---------|
| §1.1 LLM+Harness 二分 | **复用**，并把"选人"也归入 LLM 层 |
| §2 DAG 调度 / 事件循环 / FSM | **复用**（work-step 执行） |
| §3 事件溯源 + 单写者 | **复用**（task_events；SessionState 投影其上） |
| §4 三流分离 | **复用**（deliberate 上下文供给） |
| §5 机械卡死检测 | **复用** |
| §6 验收闸门 | **复用**（仅 work-step） |
| §7 worktree 隔离 | **复用**（仅 work-step 并行） |
| **§11 Selector×Coordinator 边界** | **取代**：不再"前门路由器 + 被投喂引擎"两个对象，而是一个 Planner 大脑 |
| **§13 前门接线** | **取代**：单 Planner 路由 |
| **§13.5 A1 decompose 预闸门** | **推翻**：删白名单，decompose 收进 Planner 一次决策 |
| v2 §2.3 FSM（无 WAITING 态） | **扩展**：step FSM 新增 waiting 子态 + 多轮 dispatch（§11.3） |

---

## 9. 落地分步（增量，对齐 ADR-03 三步）

| 步 | 内容 | 涉及代码 | 风险 |
|----|------|---------|------|
| **1. 统一路由器** | Planner reactive 决策吃掉 gate+selector L3；输出加 `task`；删 `CoordinatorGate`；`is_control` 前置；承接语理解放进 Planner system prompt（不硬编码） | `selector.py`→`planner`、`chat_service.py`、删 `coordinator_gate.py` | 小，立即解决前门 bug |
| **2. 统一 SessionState + 回合循环** | 把 `DiscussionOrchestrator` 循环与 `task_engine.Orchestrator` 循环提取共享抽象，respond/work 作为两种 step 执行策略；SessionState 作为两流投影 | `discussion_orchestrator.py`、`orchestrator.py`、新 `session_state.py` | 大，单独细化 |
| **3. step = 有界对话（MVP：多轮 --resume）** | `WorkerOutcome` 加 waiting/ask；Executor 做 resume dispatch；Orchestrator 处理 waiting→feed→rerun 链路；Planner 路由区分 ask-answer / modification | `executor.py`、`orchestrator.py`、`ports.py` | 中，依赖步 2 |
| **4. 任务中对话改计划（replan）** | 放开 active_plan 非空时 Planner 返回 replan；接 UserInterrupt → 图变更；与 waiting step 的交互（§11.4） | 事件循环、`coordinator_run.py` | 中，依赖步 3 |

**步 1 现在就能干、且是终态组件**（非临时补丁）。步 2/3/4 大，先各自细化设计再落地。

---

## 10. 待决开口（步 1 落地前需拍板）

1. **respond-step 要不要物理落进 DAG/task_events？** —— 倾向**不落**：reactive 路径直接出 `respond(agent)`，对话留在 `messages` 流。"对话是退化任务"是**概念**统一，不必**物理**塞进 task_events（否则每句话建图、徒增 event 噪音）。
2. **reactive 与 deliberate 是一次还是两档 LLM？** —— 倾向**两档**（§2.2）：reactive 一次轻调用出 respond/NEEDS_TASK，判 task 后才进 deliberate decompose。避免每句话付 decompose 成本。
3. **capability 关键词层（v2 L2）去留？** —— 倾向**删/降级**：任务文本天然含技术词，该层会把任务短路截胡进讨论（v2 §13.5 A1 正是为躲开它才搭了脆弱预闸门）。删掉让这类消息落到 Planner 判 NEEDS_TASK。**这是 v2 不敢碰、v3 必须正面处理的回归点。**
4. **`@某agent + 任务`**（如 `@X 帮我做博客`）走 respond 还是 task？ —— v1 暂走 respond（显式 @ = 找人聊），边界后议。

---

## 11. 执行即对话：step 是有界会话

v2 的 DAG 执行是刚性的：`dispatch → worker 闷头做 → 交卷 → verify`。worker 是智能体却被当成哑执行器——它不能在执行中发现不确定性、不能说"卡了/要问/发现还需要一步"。v2 §2.7 的"动态扩图"、§2.6 的"里程碑回顾"都是 **Planner 主动**，worker 无话语权。

v3 的解法不是在刚性流程上钉补丁（给"澄清"/"协商"/"发现子任务"等各开一个逃生口），而是**重新定义"一个 step 的执行"是什么**。

### 11.0 作用域：终结工具只在 work step 内，对话路径没有

> **本节是 §11 全部机制的前置作用域声明。读 §11.1–§11.5 前先读这节，否则会把"step 内对话"误当成"群里聊天"。**

ask / task_complete / 完成闸门 / 验收 / 进度监控——**整套只在 `work` step 的重执行里生效**。对话 `respond` 的轻执行（§2.1、§5）一概没有。两条路径的"turn 结束"语义根本不同：

| | **对话 respond（轻执行）** | **work step（重执行 Harness）** |
|---|---|---|
| 是什么 | agent 在群里说一句话 | agent 被派到 DAG 节点干活 |
| 产物 | 消息本身 | 文件改动 / artifact |
| 完成信号 | **流结束 = 完成**（自明） | 需要**显式终结工具** |
| step-tools 注入 | **不注入**，agent 没这俩工具 | 注入（`--mcp-config`，§11.2） |
| 验收 / FSM / 进度 | 无 | 有 |

**为什么对话不需要终结工具、work 需要**——三个差别决定的：

1. **产物可见性**：对话的产物*就是*那条消息，流结束 = 产物已交付，完成自明；work 干完一堆文件改动后，"我做完了"/"我停下想想"/"我在问问题"从流结束本身分不出来。
2. **下游耦合**：对话没有下游消费方；work step 有依赖它的 step + 验收闸门，需要一个干净的结构化交接载荷（summary）。
3. **验收边界**：对话无验收；work 有，必须知道"何时进 VERIFYING"。

**原生工具不会误触发终结判定**：完成闸门只匹配 step-tools 的 MCP 名（`mcp__step-tools__ask` / `mcp__step-tools__task_complete`，由 `--mcp-config` 注入并自动带 `mcp__<server>__` 前缀）。worker 中途的 `Read`/`Write`/`Bash`/`Grep` 是 CLI 原生工具，名字对不上，只是普通 step 内活动，harness 看见但不当终结信号（解析见 `claude_code_runtime._parse_line`，`name = block["name"]`）。

**work step 内不存在合法的"两个都不调"**：结局只有三种——干完 `task_complete(summary)` / 卡住 `ask(question)` / 无意义也调 `task_complete("已满足，无需改动")`。"两个都没调就结束 turn" = worker 忘了或在文本里说完就跑，**永远是异常路径**，由完成闸门追一刀（§11.3）。对比对话路径"永远两个都不调"——因为那里压根没注入这俩工具。范围一分开，模糊地带消失。

**summary 给谁**（不是给用户的汇报，是 DAG 内部的结构化交接，四个消费方）：

1. **验收闸门**（v2 §6）：summary + 实际 artifact 对照验收标准，判 COMPLETED / 打回。
2. **下游 step 上下文**：依赖它的节点不靠读全部文件、靠 summary 传递成果（v2 §4 三流的"任务结果摘要"）。
3. **Planner deliberate 上下文**：replan / 用户问"做得怎么样了"时，读各节点 summary 拼全局进度。
4. **事件溯源**：写进 task_event，成为可回放的完成证据。

> 所以 summary 写"做了什么、产物在哪、关键决策"，给机器和下游看的交接，不是给人看的进度播报。

**进度怎么监控更新**（work step 才有，全部复用 v2 §2/§3，**不另设进度系统**）：

```
worker stream → Executor._consume
   见 tool name==…task_complete → WorkerOutcome(status=completed, output=summary)
   见 tool name==…ask           → WorkerOutcome(status=waiting, ask=…)
   DONE 但两者都没见 → 完成闸门：resume 追一刀（§11.3，不接受 turn-end）
        │
        ▼
Orchestrator 收 WorkerOutcome
   → 节点 FSM 迁移 RUNNING → VERIFYING →（验收）→ COMPLETED / FAILED
   → emit task_event（单写者 append-only，v2 §3）
        │
        ▼
SessionState 投影（task_events 的 read-model，§3）
   → WS 推前端（节点状态 / 进度）
   → 用户问"做得怎么样了" → Planner 读 active_plan 各节点状态答（§4 progress 分支）
```

**进度 = DAG 各节点 FSM 状态的投影**。对话路径没有这套：消息发出追加 transcript 即终态，无 FSM、无进度——因为"产物即消息"本身就是完成。

### 11.1 模型：step = 一段有验收边界的对话

> 一个 step = 一段**被限定了范围**的对话。入口是子目标 G（instruction），出口是 G 被验收。在这段对话里，worker 可以问、可以商量、可以发现子任务——这些是对话里的自然动作，不是特例节点。DAG 全程不动：依赖、并行、验收，全部照旧。

```
DAG: step_A ──→ step_B ──→ step_C

step_A：worker 闷头做，5s 完成（大多数 step 跟 v2 一样，零额外成本）
step_B：worker 中途提问 → 群里回答 → 继续 → 再问一次 → 继续 → done
        └─ 这段对话只存在 step_B 内部，step_C 不知道也不关心
step_C：闷头做，完成
```

**不是"选①刚性还是②纯对话"的二元选择**，是③骨架刚性 + 节点内弹性——**确定性调度 + 开放性执行**。

### 11.2 协议：两个 MCP tool，不解析文本

worker 通过 **tool_use**（结构化调用）表达 step 内对话的意图——不是文本模式匹配。CLI 原生支持 tool_use，后端 `_parse_line` 已有 tool_use 解析逻辑（`block_type == "tool_use"`），直接复用。

| tool | 含义 | DAG 反应 |
|------|------|---------|
| **`task_complete`**(summary) | "子目标 G 达成了" | step → VERIFYING → COMPLETED |
| **`ask`**(question) | "我需要这个信息才能继续" | step 保持 RUNNING；问题路由到群；答案回灌后 worker 继续 |

**为什么是 tool_use 而不是文本魔词**：`TASK_COMPLETE` 字符串匹配 = 靠模式猜 LLM 意图，跟前门 `has_work_intent` 正则白名单是同一种脆——LLM 可能忘写、可能换个措辞、可能在中间引用这个字符串。tool_use 是**结构化契约**：LLM 被训练为可靠地调用工具，Harness 从 stream-json 直接拿到 `{"name": "task_complete", "input": {"summary": "..."}}`，零猜测。

两个 tool 作为 MCP server 注入 CLI（`--mcp-config` 指向 AgentHub 提供的 `/mcp/step-tools` endpoint）。复用现有 memory MCP 的注入路径（`_write_mcp_config`）。

**对比 v2 补丁路的关键差异**：补丁路问"我要预先开哪些 ask 类型"（封闭枚举），v3 只给一个通用 `ask` tool——**开放，但有界**（step budget 防聊飞）。

### 11.3 实现路径

#### MVP 档：多轮 `--resume` + MCP step-tools（V0 短驻 CLI）

核心：**把一个 step 拆成多次 CLI 调用**，每次用 `--resume` 恢复上下文。worker 通过 `task_complete`/`ask` 两个 MCP tool 宣告意图，Harness 从 stream-json 的 tool_use 事件中直接拿到结构化信号——**零文本解析**。

```
═══════════════════════════════════════════════
  Turn 1: 首次 dispatch
═══════════════════════════════════════════════
Executor dispatch:
  session_key = uuid5(session_id:step_id)      ← step 级隔离
  has_history=False → --session-id new
  --mcp-config 注入 step-tools（task_complete + ask）

CLI 执行 → stream-json:
  assistant: text "我先读一下项目结构..."
  assistant: tool_use Read / Grep
  user: tool_result ...
  assistant: text "存储方式没定。"
  assistant: tool_use {name: "ask", input: {question: "用 Markdown 还是 CMS？"}}
  └─ _parse_line 产出 StreamEvent(type=TOOL_CALL,
       tool_call=ToolCall(call_id="...", name="ask", arguments={question: "..."}))

Executor._consume 看到 tool_call.name == "ask":
  → 记录 ask_question，继续读到 DONE
  → 返回 WorkerOutcome(ok=True, status="waiting",
       ask=AskInfo(question="用 Markdown 还是 CMS？", call_id="..."))

Orchestrator:
  step.status 保持 RUNNING（不变！）
  保存 step_key = session_key 到 node
  把 ask.question 作为 agent 消息发到群里
  └─ 不碰 DAG 结构，不 propagate_blocked，其他就绪节点照派

═══════════════════════════════════════════════
  用户回答 → Planner 路由 → 回到 step
═══════════════════════════════════════════════
用户: "CMS，用 Strapi。"
  → Planner.decide(SessionState)
     active_plan 非空 + 上一条是 step_B 的 ask
     → 判: 这是回答 step_B 的问题
     → action=feed(step_B, answer="CMS，用 Strapi。")

═══════════════════════════════════════════════
  Turn 2: resume dispatch（注入答案）
═══════════════════════════════════════════════
Executor re-dispatch:
  session_key = node.step_key （同 key！）
  has_history=True → --resume
  instruction: "用户回复：CMS，用 Strapi。请继续。"
  └─ --resume 自动加载 Turn1 完整上下文

CLI 执行 → stream-json:
  assistant: text "好，用 Strapi。我改集成..."
  assistant: tool_use Write ...
  assistant: tool_use {
    name: "task_complete",
    input: {summary: "前端已实现：Strapi CMS 集成 + 文章列表 + 图片优化"}
  }

Executor._consume 看到 tool_call.name == "task_complete":
  → 返回 WorkerOutcome(ok=True, status="completed", output=summary)

Orchestrator:
  step → VERIFYING → 验收 → COMPLETED ✅
═══════════════════════════════════════════════
```

**关键细节**：

1. **step 级 session_key**：`uuid5(session_id:step_id)`，不是 `uuid5(session_id:agent_id)`。每个 step 独立 session，互不污染。

2. **step-tools MCP**：AgentHub 提供一个轻量 MCP server（`/mcp/step-tools`），暴露两个 tool：
   - `task_complete(summary: str)` → Harness 从 tool_use 事件检测到此调用 → step 完成
   - `ask(question: str)` → Harness 检测到此调用 → step 等待答案
   
   CLI spawn 时通过 `--mcp-config` 注入（复用现有 `_write_mcp_config` 路径）。

3. **ask/task_complete 检测 + 完成闸门（严出，不宽进）**：`Executor._consume` 已有 tool_use 解析（`block_type == "tool_use"` → 产出 `StreamEvent(type=TOOL_CALL, tool_call=ToolCall(...))`）。只需新增：遍历 stream 时检查 `tool_call.name`：
   - `…task_complete` → 真 done，output 取 `tool_call.arguments["summary"]` → 进 VERIFYING
   - `…ask` → 记录 `tool_call.arguments["question"]`，继续读流直到 DONE，返回 waiting
   - **两个终结工具都没调就 DONE → 不接受这次 turn-end**（完成闸门）：resume 追一刀注入系统提示「你结束了但没调用 task_complete 或 ask。完成了就调 task_complete(summary)；需要信息就调 ask(question)」，计入 step 预算（§11.5，超 N 次 → FAILED 升级问用户）。

   > **为什么不留"无 tool → 视为 done"的宽进 fallback**（推翻早期草案）：那条 fallback 正是 ask-in-text 漏洞的根。worker 极常用纯文本提问而忘调 `ask` tool——若把它当 done，会把"用 Markdown 还是 CMS？"当成 artifact 进验收。完成闸门用**结构检测（终结工具缺席，100% 可靠）取代语义检测（猜文本是不是问题，开放集必脆）**：harness 从 stream-json 精确知道调没调 step-tools，不去猜文本语义。它同时堵住两类失败——忘调 task_complete、纯文本提问后结束 turn——追一刀后 worker 自然改调对应工具。
   >
   > 配套 **验收反向网**：即便调了 task_complete，验收闸门（v2 §6）核 summary + 实际 artifact；产物像问句 / 无产物 / 验收标准未达 → 打回 RUNNING。堵住"调了 task_complete 却把问题塞进 summary"。
   >
   > 配套 **system prompt 合约**：step instruction 明写协议——"必须以 task_complete 或 ask 结束；遇到影响方案的不确定性必须 ask，禁止自行假设"。降低 worker 忘调 / 自作主张的频率（必要但不充分，故仍需上面两道结构兜底）。

**三道兜底的关系**：system prompt 合约（降频，prompt 层）→ 完成闸门（堵 turn-end 缺终结工具，结构层）→ 验收反向网（堵 summary 注水，验收层）。前两道靠"工具缺席"这一**结构信号**，不靠猜文本语义。

> **残余风险（无机制可解，须显式承认）**：以上只覆盖"worker 暂停并结束 turn"。若 worker 在文本里自言自语「存储没定，我先假设 Markdown」然后**不停、继续干**——它从没暂停，没有 turn-end 可拦，任何 tool_use 机制都捕获不到。这是"agent 基于错误假设闷头推进"，唯一杠杆是 system prompt 合约 + 验收兜底。**没有协议能强制一个不认为自己需要停的 agent 停下来。**

4. **多轮预算**：每 step 最多 N 次 dispatch（默认 3），超了 → FAILED。计数器放 node：`node.dispatch_count += 1`。

5. **为什么用 `--resume` 而不是 stdin JSONL**：V0 短驻 CLI 每次 `stdin.write(prompt) + write_eof()`，stdin 关闭后无法再注入。V0 路径的多轮 = 多次 spawn + `--resume`。resume 自动恢复完整上下文——对话历史、读过的文件、工具调用结果、记忆——全部在 session 文件里。

#### 标准档：单次长驻内暂停（V1 长驻 CLI）

V1 长驻 CLI 的 stdin **不关**，step-tools MCP 的 `ask` 可以做真正的"单次执行中暂停"：

```
Worker CLI session (V1 长驻，stdin 开着，同一 --mcp-config):
  → 收到 instruction
  → 执行中...
  → call ask("用 Markdown 还是 CMS？")
     └─ MCP server 收到 → post 问题到群里 → 等待答案（长轮询）
     └─ 答案到达 → MCP server 返回给 CLI → tool_use 完成
  → 继续执行...
  → call task_complete("前端已实现")
```

- `ask` MCP tool 在长驻模式下是**同步阻塞**：CLI 调用 tool，MCP server 不立即返回，而是等答案到达再 resolve。CLI 视角 = 一次普通的 tool_use 调用，只是耗时较长。
- **DAG 视角完全透明**：step 只是一次 dispatch（耗时可能几秒到几分钟），timeout 照旧兜底。Harness 一行不改。

| | MVP（多轮 --resume） | 标准（长驻内暂停） |
|---|---|---|
| CLI 模式 | V0 短驻 | V1 长驻 |
| step-tools | 同一 MCP server，同一组 tool | 同左 |
| step 内交互 | 多次 spawn + resume | 单次长连接内暂停 / 阻塞等答案 |
| 实现复杂度 | Executor 做 resume dispatch + Orchestrator 处理 waiting | 仅 MCP server 改为长轮询；Executor/Orchestrator 不改 |
| 体验 | turn 边界有 spawn 延迟 | 真正流式暂停 |
| Harness 改动 | `WorkerOutcome` 加 waiting + dispatcher 做 rerun | **零** |

**先 MVP、再标准**：MVP 验证"step = 对话"在概念上成立后，标准档是纯体验升级——`Executor.run(node)` 的 contract 不变，只是内部实现从"多次 spawn"变成"一次长连接 + 同步阻塞 ask"。

### 11.4 step 内对话 × 外部改计划（replan）的交互

这是两个层级的"改变"在同时发生——需要讲清它们怎么互不冲突。

```
层级 1（step 内）: worker 在 ask     ← 问个问题，step 悬着等答案
层级 2（DAG 级）: 用户要改计划       ← UserInterrupt → replan
```

**它们在同一个 Planner 路由里自然分辨**：

```
新消息 → Planner.decide(SessionState)
  active_plan 非空, step_B 状态=RUNNING, worker 刚发过 ask
  ┌─ "CMS，用 Strapi"              → feed(step_B, answer)     ← 层级 1
  ├─ "算了，别做博客了，做文档站吧"   → replan(delta)            ← 层级 2
  └─ "前端做得怎么样了"             → respond(读 DAG 答)        ← 层级 1
```

**层级 2（replan）触发时，正 WAITING 的 step 怎么处理**：

```
UserInterrupt(replan) 进事件循环:
  1. 遍历 RUNNING 节点:
     若节点在 waiting（有未答的 ask）→ cancel 该 step
     若节点在闷头跑 → 如果受 replan 影响 → cancel；否则继续
  2. Planner.replan(SessionState + 新约束)
  3. diff 旧 DAG vs 新 DAG
  4. 已 COMPLETED 节点保留（成果不回滚）
  5. dispatch_frontier 新就绪集
```

**为什么层级 1 和 2 不冲突**：因为 Planner 就是同一个脑，它读同一份 SessionState（含 transcript + active_plan + 各 step 状态）。它看到的不是"一条插话"撞上"一个 DAG"，而是**一张完整的地图**——上面有正在等的 step、正在跑的 step、刚来的消息。路由是同一张地图上的同一个决策。

### 11.5 成本控制（"有界"从哪来）

"对话式 step"的恐惧是 worker 聊飞——v1 的全局 LLM 每轮判就是这个反面。约束来自三层：

| 层 | 机制 | 说明 |
|----|------|------|
| **step 预算** | 每 step 最多 N 次 dispatch（默认 3）；总 token/时间上限（复用 v2 §5 墙钟） | 机械截停，零 LLM；超了 → FAILED，升级问用户 |
| **ask 路由** | Planner 只做一次路由决策（把答案 feed 给哪个 step），**不是每轮重新 plan** | 是轻 reactive 调用，不是贵 deliberate |
| **DAG 不动** | ask/answer 链路是 step 内部的，不触发 replan、不重算 frontier、不搅动其他并行 step | 隔离成本作用域 |

**跟 v1 全局对话的根本差别**：v1 是"整个执行都在对话里"——每轮 LLM 判下一步所有 agent 的调度。v3 是"调度是确定性的、对话只在单个 step 内部"。**隔离了爆炸半径**：聊飞影响一个 step，不污染整条 run。

### 11.6 执行期旁路消息：队列 + 边界投递

**问题**：任务执行中，目标 worker 的 CLI **占线**——它被 Executor 占着干活，不是一个同时监听群聊的人。用户此刻发的非答案、非取消消息（如「注意前端用 React」），worker 实时收不到。当前实现直接**忽略（吞掉）**——用户的补充凭空消失。

**worker 只在两个时刻可达**：① 主动 `ask` 暂停时；② 干完一个 step 时。两者之间发给她的消息只能先 held 住。

**机制**：进程内队列 + step 边界投递（零 LLM，不走 Planner）。执行态消息三分：

```
执行态（active_plan 非空）消息：
  is_control            → cancel run（机械，§4 前门反射）
  有 step 在 waiting     → feed（答案解卡，§11.3）—— 她卡着等这条，必须立刻送
  否则（占线旁路消息）   → enqueue 进 run._pending_notes  ← 本节新增（替代"忽略"）
```

**投递**：每次 dispatch 一个 step 时，把累积的 `_pending_notes` 作为「## 用户执行期补充」段附到该 step 的 instruction 末尾（`build_task_request` 注入）。

**三条边界（显式承认）**：

1. **只对之后 dispatch 的 step 生效**；已在飞的 step 吃不到——CLI 占线无法注入，是 CLI 模型硬限。「注意用 React」若在前端 step 已经在跑时才说，这个 step 晚了，靠后续 step 或 §6 replan。**这是接受的代价，不是 bug。**
2. **不做"这条给谁"的分类**：累积全量注入每个后续 step（不按 step 路由），宁可都看到、由 agent 自行取舍。零 LLM。要精确路由（多 step、判答案 vs 闲聊）是 [[coordinator-v3-step1-unified-router-plan]] 的 1c-exec 升级项，非本节。
3. **不是 replan**：只追加约束/提示文本，**不改 DAG 结构**。要加/删 step、改依赖 → 走 §6 replan（deliberate）。本节是「轻补充」，replan 是「改图」。

**接口**：`CoordinatorRun.enqueue_note(text)` → Orchestrator `_pending_notes: list[str]`；dispatch 前 `build_task_request(..., notes=pending_notes)` 注入。投递不清空（累积，幂等——agent 重复看到同一约束无害），可设上限 N 防 instruction 膨胀。

> **与 ask/feed 的分工**：feed 是"她卡住等这一条，立刻送"；队列是"她占线没等任何东西，这条先存着，边界再给"。前者解卡（不能等），后者补料（可以等）。两者都不动 DAG。

---

> 收口：v3 = 一个 Planner 大脑（两视野）+ 一套 Harness 骨架（v2 复用）+ **step 是有界对话**（两个原语 ask/done）+ N 只 worker 手 + 一个 SessionState 胼胝体。把 v2 在执行期想清楚的"单一路由"延伸到前门，同时把执行从"黑盒 fire-and-forget"升为"有边界、可对话但调度仍确定性"——不回到 v1 的全局对话失控。
