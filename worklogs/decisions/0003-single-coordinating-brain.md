# ADR-03: 单一协调大脑 — 收编 selector/planner 为同一决策层

> 架构决策记录 | 日期：2026-06-07 | 状态：已提议（方向已定，分步落地）
> 关联：[[0001-cli-first-pivot]] · [[0002-phase1-long-running-cli]] · `docs/explore/董/任务编排/coordinator-design-decision.md`

---

## 一、背景

当前一条用户消息进入群聊后，要经过两套**互相独立**的决策机制：

```
用户消息 → ChatService.handle
   ├─ CoordinatorGate.is_decompose  （LLM 二分类：任务 / 非任务）
   │      └─ 任务 → task_engine.Orchestrator（SeedPlanner 规划 → Executor 执行 → Verifier 验收）
   └─ 非任务 → DiscussionOrchestrator
              └─ Selector.pick（4 层路由，L3 是 LLM：选下一位发言人 / done）
```

`CoordinatorGate` 前面还有一道工作动词正则白名单（`has_work_intent`）做廉价预滤。

## 二、问题发现

### 2.1 直接症状（本次排查中暴露）

- 「可以直接干吧」「重试」「继续」这类**承接语**没有工作动词 → 被白名单挡在协调者门外 → 误进讨论模式，worker agent 用聊天方式「开干」，结构化 plan→execute→verify 流水线根本没启动。
- 任务执行中（`registry` 占位态），新消息只被当作 control（取消）或忽略——**无法用对话修改正在跑的计划**。

### 2.2 根因：一套系统里有"两个大脑"

把 Selector 和 Planner 的本质动作写出来：

| | 视野 | 本质动作 | 产出 |
|---|---|---|---|
| **Selector（选人）** | 1 步、被动 | 给定 目标+对话+agent → 决定**下一步谁动** | 一次 dispatch |
| **Planner（协调）** | 多步、主动 | 给定 目标+agent → 决定**接下来一串谁做哪步** | 持久 step 序列 |

二者是**同一个认知动作**——"给定目标和手下，决定谁该干什么"。唯一差别是**规划视野**：

> 选人 = 视野为 1、不持久化计划的协调。

这不是两个大脑，是**同一个调度大脑被劈成两半、且中间没有连接**。

### 2.3 "两个大脑"的真正危害：没有胼胝体

问题不在"有两个决策器"，而在**它俩不共享目标与状态、无法交接**：

- Selector 脑不知道有没有任务计划；Planner 脑不知道群里在讨论什么。
- Gate 在它俩之间硬切，**一切换意图就丢**（2.1 第一个症状的本质：选人脑里根本没有"我们正要开始一个任务"这个概念）。
- 它俩会**互相矛盾**：选人脑让讨论继续，而用户其实想执行；Planner 脑把一句提问拆成了任务。
- 2.1 的两个症状、以及此前撞到的双重 LLM 分类、白名单漏判，**全是这两个断连大脑的并发症**。

### 2.4 需要承认的正当理由：System-1 / System-2

两个决策器分开**有**一个正当动机：

- "下一句谁说"要**便宜、即时**（每回合判）→ 适合轻量反射。
- "规划一个项目"**贵、罕见** → 适合重量深思。

但 System-1 / System-2 仍是**一个大脑、共享一个目标**。这只能论证"一个脑可以有快/慢两种思考模式"，**论证不了"两个互不知情的独立大脑"**。

## 三、决策

**确立"单一协调大脑"为架构核心：selector 与 planner 收编为同一个协调大脑的两种 dispatch 粒度；task_engine 退为执行层（"手"，非"脑"）。**

```
        ┌──────────────────────────────────────┐
        │   协调大脑（per session/group，唯一决策源）  │
        │   持有: 目标(可空) + 对话状态              │
        │   每条消息 → 决定下一个 dispatch:          │
        │     · 轻 dispatch = 让某/某些 agent 回    │  ← 原 Selector
        │     · 重 dispatch = 出计划并执行          │  ← 原 Planner
        │     · done / 无操作 / control            │
        └───────────────┬──────────────────────┘
                        │ 调用（工具/手，不决策）
              task_engine: DAG 执行 + 机械验收
```

要点：

1. **协调者 = 唯一的脑**，统一持有目标与对话、统一做"下一步动作"决策。这正是 `coordinator-as-llm` 分支名的归宿。
2. **选人**降级为该脑的**轻量 dispatch**（@mention / capability 等零 LLM 反射 = 它的 System-1 快路）。
3. **规划**是该脑的**重量 dispatch**。
4. **task_engine 的 Executor/Verifier 是"手"**——只执行、不决策。
5. **对话是任务的退化特例**：在"决策 + 回合循环"层成立（action=respond、终止=收敛、产物可空）；但**不把 DAG/验收硬塞进每条聊天**——执行策略仍分轻/重两种，避免过度一般化拖垮 IM 低延迟。

### 边界划定（避免从"过度拆分"滑向"过度统一"）

| 层 | 对话 vs 任务 | 处理 |
|----|------------|------|
| 决策层（路由器） | 同一个 | **统一** |
| 回合循环（assess→dispatch→observe→repeat→terminate） | 同构 | **统一抽象** |
| 执行引擎 | 真不同（线性历史 vs DAG+验收+产物） | **保留两种策略** |

## 四、影响

### 收益
- 消除双重 LLM 分类与正则白名单漏判（2.1/2.3 全系列 bug 的根治）。
- 任务执行中可对话改计划（新消息 = 又一次路由输入）。
- 决策逻辑单点化，可观测、可演进。

### 代价 / 风险
- Selector 从"纯无状态发言人路由器"升级为"下一步动作路由器"，**定位与协议要重写**。
- 路由器与执行层的边界要严守，否则回退成"对话跑进任务引擎"的过度统一。
- 重构涉及 `chat_service` 接线、`Selector` 输出协议、`DiscussionOrchestrator` 循环、`CoordinatorGate` 删除。

## 五、分步落地（增量，不一次性推翻）

| 步 | 内容 | 风险 |
|----|------|------|
| **1. 统一路由器** | `CoordinatorGate.is_decompose` 并入 `Selector` L3：`decision` enum 加 `decompose`；删 `has_work_intent` 白名单；承接语理解放进 LLM system prompt（不硬编码）。`is_control` 正则保留为安全反射。`chat_service` 改为"先 `selector.pick(trigger)` → decompose 起协调者 / 否则进讨论循环"。 | 小，立即解决 2.1 第一症状 |
| **2. 抽回合循环** | 把 `DiscussionOrchestrator` 与 `task_engine.Orchestrator` 的循环提取为共享抽象，respond/task 作为两种 action 策略。 | 大，需单独设计 |
| **3. 任务中对话** | mid-run 消息进路由器 → 支持改计划 / 答疑 / 取消。 | 中，依赖步 2 |

**待决子问题（步 1 落地前需拍板）**：
- L2 capability 关键词层：任务文本天然含技术词，会被该层短路截胡进讨论 → 倾向**删除/降级**，让其落到 L3 由 LLM 判 decompose。
- `@某agent + 任务`（如 `@X 帮我做博客`）：走讨论还是进协调者 → v1 暂走讨论（显式 @ = 找人聊）。

## 六、关联

- 推翻/收敛的旧设计：`coordinator-design-decision.md`（协调者 = 纯 LLM 调用）在"协调者是脑"这点上一致，本 ADR 进一步把 selector 也收编进同一个脑。
- 后续：步 2 的回合循环抽象、步 3 的 mid-task 对话，各自另立设计文档。
