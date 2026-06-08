# Coordinator v3 步 2 — 统一 SessionState + 回合循环 方案设计

> 日期：2026-06-07 | 状态：方案设计（SPEC）
> 依据：[[coordinator-design-v3]] §3/§9 步2
> 前序：步1（统一路由器，已完成 90%）· 步3（step-tools，已完成）
> 真机冒烟：2026-06-07 验证通过，tool name 常量正确

---

## 0. 问题定义：步 2 要解决什么

### 0.1 现状的三个断层

步1 落地后，群聊路由已经是「三反射 → decide 单点」。但下面三道裂缝没合上：

**裂缝 1：两个事件循环各跑各的**

```
DiscussionOrchestrator.run_discussion:        Orchestrator.run:
  for round in max_rounds:                      for step in max_steps:
    Selector.pick → stream → repeat               dispatch → await → settle → repeat
```

DiscussionOrchestrator 管对话，Orchestrator 管任务执行。两者**没有任何共享抽象**——一个用 `Selector` 选人，一个用 DAG scheduler 选节点。实际上对话的"选下一位发言人"和任务的"选下一个 dispatchable step"在抽象层是同一件事：**基于当前状态选择下一个要执行的动作**。

**裂缝 2：多轮讨论被 strip 砍掉了**

步1 决策 B（`_respond` 是否接 DiscussionOrchestrator 续轮）选了 strip：「回完即止」。这意味着 agent A 回完一句话后，即使 agent B 应该接话，也不会有第二轮。实际效果是**多轮讨论死了**——只有第一轮有人回。

步2 把多轮讨论以「反复 decide」的方式重建，而非回到 DiscussionOrchestrator 内部的 Selector 循环。

**裂缝 3：SessionState 只是轻量替身**

步1 的 `SessionState` 是手工拼的：`transcript` 从 `_recent_history` 取，`active_plan` 永远是 `None`（步1 的 `_handle_group` 只在纯对话态进 decide；执行态走了简化 feed 路由）。没有真正的 `active_plan` 投影，decide 在执行态看不到 DAG 状态。

---

## 1. 目标架构

### 1.1 一句话

**把 DiscussionOrchestrator 的回合循环和 Orchestrator 的任务循环，提取为一个共享的回合抽象。对话只是一步 respond 的退化执行。**

### 1.2 统一回合循环模型

```
┌─────────────────────────────────────────────────────┐
│  统一回合循环（替代 DiscussionOrchestrator +           │
│              Orchestrator 两个独立循环）              │
│                                                      │
│  while not terminal:                                 │
│    state = SessionState.from_streams(session_id)      │
│    decision = Planner.decide(state)                   │
│    ┌─ respond/multi → 轻执行：stream agent → repeat   │
│    ├─ task          → 重执行：起 Harness DAG → repeat │
│    ├─ feed          → 喂 waiting step → repeat       │
│    └─ done          → terminal                        │
│                                                      │
│  关键：每次循环重新构造 SessionState、重新 decide      │
│  —— 对话的"多轮接力"自然涌现（不是硬编码循环）         │
└─────────────────────────────────────────────────────┘
```

**与现状的关键差别**：

| | 现状 | 步2 后 |
|---|------|--------|
| 对话多轮 | DiscussionOrchestrator 内部 Selector 循环（strip 砍了） | 每轮回调 `Planner.decide` 重新决策，agent 回复后自动进下一轮 |
| 任务执行 | Orchestrator.run 内部 DAG 循环 | 不变（Harness 是确定性代码，只是回合抽象统一了外层） |
| SessionState | 手工拼的轻量版 | 从两条事件流（messages + task_events）投影的 read-model |
| 选人逻辑 | Selector L3（独立 LLM） | `Planner.decide` 的 respond/multi 输出 |

### 1.3 不变的部分

| 不变的 | 为什么 |
|--------|--------|
| `Orchestrator.run`（任务执行循环） | 它是 Harness——确定性 DAG/FSM/验收，不改 |
| `ReactiveRouter.decide` | 已经是统一前门，步2 只是把它的调用点从「ChatService 前门一次」改成「回合循环每轮一次」 |
| `ChatService._stream_one_agent` | 单 agent 流式执行不变 |
| 机械反射（@/control/broadcast） | 前门反射保留，不进循环 |
| `CoordinatorRun` / `CoordinatorRegistry` | 进程级注册不变 |

---

## 2. SessionState v2：真正的事件流投影

### 2.1 从手工拼装到 read-model

步1 的 SessionState：

```python
# 手工拼装（ChatService._handle_group 内）
state = SessionState(
    session_id=session.id,
    members=tuple(members),
    transcript=tuple(await self._recent_history(session)),  # DB 查
    active_plan=None,  # ← 永远是 None（步1 只在纯对话态进 decide）
)
```

步2 的 SessionState：**从一个构造函数根据 session_id + run 状态投影**：

```python
class SessionState:
    """两条事件流（messages + task_events）的只读投影。"""
    session_id: UUID
    members: tuple[Agent, ...]
    transcript: tuple[Message, ...]          # ← messages 表投影（近窗口）
    active_plan: PlanView | None             # ← task_events 投影（若 run 在跑）
    constraints: tuple[str, ...]

    @classmethod
    async def from_session(
        cls,
        session_id: UUID,
        members: tuple[Agent, ...],
        message_repo: MessageRepository,
        run: CoordinatorRun | None,
    ) -> SessionState:
        recent = await message_repo.list_by_session(session_id, limit=15)
        transcript = tuple(reversed(recent))
        plan = run.plan_view() if run is not None else None
        return cls(
            session_id=session_id,
            members=members,
            transcript=transcript,
            active_plan=plan,
        )
```

### 2.2 PlanView：DAG 状态的只读投影

`CoordinatorRun` 需要暴露一个零副作用的方法，从 Orchestrator 的 `TaskGraph` 投影 `PlanView`：

```python
# coordinator_run.py — CoordinatorRun 新增
def plan_view(self) -> PlanView | None:
    """从正在跑的 Orchestrator 投影 DAG 状态（只读，不锁）。"""
    if self._orchestrator is None or self._orchestrator.graph is None:
        return None
    g = self._orchestrator.graph
    steps = tuple(
        StepView(step_id=n.task.id, worker=n.task.suggested_worker, status=n.status.value)
        for n in g.nodes.values()
    )
    waiting = tuple(
        n.task.id for n in g.nodes.values()
        if n.status == TaskStatus.PAUSED  # 或 RUNNING + 有未答 ask
    )
    return PlanView(steps=steps, waiting=waiting)
```

这个投影在步2 有两个消费者：
1. **`Planner.decide`**：active_plan 非空时，根据 waiting / 各 step 状态决策 feed / respond / done
2. **前端**：WS 推送 DAG 状态（已有 `_emit_update`，不依赖 PlanView）

### 2.3 升级路径（从步1 轻量版到步2 完整版）

步1 的 `SessionState` 只有 `session_id/members/transcript/active_plan=None/constraints`。步2 改为 `from_session` 工厂方法后：
- 纯对话态：跟步1 完全一样（active_plan=None）
- 执行态：active_plan 非 None，含 steps + waiting

**向后兼容**：`ReactiveRouter.decide` 的签名和逻辑不变——它本来就能处理 active_plan 非 None 的分支。步2 只是让 active_plan 终于能是非 None 了。

---

## 3. 统一回合循环设计

### 3.1 两个循环的对比分析

| | DiscussionOrchestrator.run_discussion | Orchestrator.run |
|---|---|---|
| **循环变量** | `for round in range(max_round)` | `for _ in range(max_steps)` |
| **决策** | `Selector.pick(history, members)` → LLM | `compute_frontier + select_dispatchable` → 确定性 |
| **执行** | `_stream_one(target)` → yield events | `executor.run(node)` → await outcome |
| **状态** | `already_spoken: set` | `TaskGraph`（FSM 状态机） |
| **终止** | Selector DONE / max_round / 人取消 | `_terminal()`：全 COMPLETED / FAILED / UNREACHABLE |
| **中断** | ChatService cancel（新用户消息来） | feed（等 ask 回答）/ cancel（control 消息） |

**关键发现**：两个循环的决策层（Selector vs DAG scheduler）完全不同——一个是 LLM 选人，一个是确定性拓扑排序。但它们的**外层结构**是同一模式：

```
初始化状态 → while not terminal:
    decision = 选下一步动作
    执行动作
    更新状态
```

### 3.2 统一循环：不合并两个循环，而是提取共享外层

**核心设计决策**：两个循环不是合并成一个——是各自保留内核，只在外层共享一个 `SessionState → Planner.decide → dispatch` 的回合抽象。

```
ChatService._handle_group:
  (前门反射省略)

  while True:                          ← 统一回合循环（新增）
    state = SessionState.from_session(...)  ← 每轮重新投影
    decision = await self._router.decide(state)

    match decision.action:
      case "respond" | "multi":
        async for evt in self._respond(...): yield evt
        # agent 回复完，transcript 有新消息 → 下一轮 decide 自然看到

      case "task":
        run = await self._start_coordinator(session, group, trigger)
        # fire-and-forget：Harness 在后台跑
        # 下一轮 decide 看到 active_plan 非 None
        break  # 进入执行态监听（简化：task 后退出循环，等 Harness 完成）

      case "done":
        break
```

**但是等等**——如果 `task` 后退出循环，那执行态的消息怎么处理？

### 3.3 执行态的路由（步1 已解决，步2 不动）

执行态（active_plan 非 None）的消息路由在步1 已经处理了：

```python
# chat_service.py:188-201（步1 现状）
if run is not None:
    if self._is_control(text):          → cancel
    elif run.has_waiting_step():        → feed（简化版）
    else:                               → enqueue_note（旁路队列）
    return
```

步2 **不动这段**。步2 的范围是**纯对话态的多轮**——那个被 strip 砍掉的"agent 互相接力讨论"。

也就是说，统一回合循环的**实际形态**是：

```
纯对话态（active_plan is None）：
  while True:
    state ← 重新投影
    decision ← Planner.decide(state)
    respond → stream → 消息入 transcript → 循环继续（下一轮 decide 看到新消息）
    done → break

执行态（active_plan 非 None）：
  不变（步1 的简化路由 + 步4 的 decide→feed/replan）
```

**这听起来不如预期宏伟——但更务实**。步2 的真正价值是：
1. 多轮讨论回归（strip → 反复 decide）
2. SessionState 从手工拼装升级为真正的 read-model
3. 删 Selector keyword 层（L2）和 DiscussionOrchestrator（其职责被反复 decide 取代）
4. `PlanView` 为步4 replan 铺路

### 3.4 多轮讨论的具体实现

```
用户: "Strapi 权限模型你们怎么看"
  → 三反射不命中 → decide(state)
  → state.active_plan=None, transcript=[用户消息]
  → PlannerDecison(action="respond", who=("后端阿强",))

后端阿强: "Strapi 基于 RBAC，用户角色+权限矩阵..."
  → 消息入 transcript
  → 新一轮 decide(state)
  → state.transcript=[用户, 后端阿强]
  → PlannerDecision(action="respond", who=("前端小美",))  # LLM 判断前端也该说

前端小美: "前端对接主要关注 JWT 中间件..."
  → 消息入 transcript
  → 新一轮 decide(state)
  → PlannerDecision(action="done")  # 讨论收敛

循环结束
```

**防循环**（替代 Selector L1.5/DONE 的 `already_spoken`）：
- `Planner.decide` 的 system prompt 已有「讨论已收敛 → done」
- 硬上限：`max_rounds`（默认 5，可配），超了自动 done
- 人在环：用户随时发新消息 → 前门「run 非空」分支不命中 → 当前循环自然结束 → 新消息进新循环

### 3.5 用户新消息打断循环

这是 DiscussionOrchestrator 模式没有的问题——因为没有人在聊天的过程中发新消息（一轮是一个回合）。但统一循环下：

```
循环中（后端阿强正在 stream）：
  用户: "@前端小美 你说说"
  → ChatService._handle_group 的上一次调用还在 stream 中
  → 新的 _handle_group 调用进来
  → _resolve_mentions → 命中 @ → _stream_one_agent(前端小美)
  → 前后端同时 stream（并发，不是冲突）

循环结束（本轮 done）：
  前端小美回完了
  → 下一条用户消息进新的 decide → 新的循环开始
```

**这是正确的行为**：@mention 始终是前门反射直达，不经过回合循环。循环只处理「无明确目标的自由讨论」。

---

## 4. Selector 溶解计划

### 4.1 逐层映射

| Selector 层 | 新位置 | 说明 |
|-------------|--------|------|
| L1 @mention | ChatService `_resolve_mentions`（前门反射） | 已存在，不变 |
| L1.5 broadcast | ChatService `_is_broadcast`（前门反射） | 已存在，不变 |
| L2 keyword | **删除** | 设计决策 C：任务文本天然含技术词，keyword 层把任务短路截胡进讨论 |
| L3 LLM decide | `ReactiveRouter.decide` respond/multi/done | 已存在（步1），多轮时反复调 |

### 4.2 DiscussionOrchestrator 去向

`DiscussionOrchestrator.run_discussion` 的核心逻辑：

```
for round in max_rounds:
    Selector.pick → stream_one → already_spoken.add
```

被「反复 decide + respond」取代后，DiscussionOrchestrator 不再需要。但它的 **`_stream_one`**（与 ChatService._stream_one_agent 同构但独立实现，避免循环依赖）需要合并。

**处置**：
- `DiscussionOrchestrator.run_discussion`（循环 + Selector）→ **删**
- `DiscussionOrchestrator._stream_one` → **合并进 ChatService**（共用 `_stream_one_agent`，DiscussionOrchestrator 不再需要独立实现）
- `DiscussionOrchestrator.__init__` 的依赖注入 → 删

### 4.3 Selector 类

步2 后 Selector 只剩 L3（LLM decide），而 ReactiveRouter.decide 已经在做同一件事。**整个 Selector 类可以删**，但需要确保：

1. `ReactiveRouter.decide` 的多轮能力：当前 system prompt 已经能处理多轮上下文中选下一位发言人
2. `already_spoken` 防重复：改由 decide 的 system prompt + transcript 窗口自然处理（LLM 能看到谁刚说过，不会重复选）

**保守策略**：步2 先删 L2 keyword 层 + DiscussionOrchestrator 循环；Selector L3 保留作为 `ReactiveRouter` 的委托（避免重写 tool_use 逻辑）。步4 之后再考虑合并两个 LLM 调用点。

---

## 5. 实现分步（TDD，每步可独立验证）

### 步 2a：`CoordinatorRun.plan_view()` + `SessionState.from_session`（~2h）

**范围**：让 SessionState 能从真实数据源投影。

**改动**：
- `coordinator_run.py`：加 `plan_view() → PlanView | None`
- `session_state.py`：加 `SessionState.from_session()` 工厂方法
- `PlanView` / `StepView`：已存在，确认字段够用

**测试**（fake）：
- TC-2a.1：`run=None` → `SessionState.from_session()` 返回 `active_plan=None`
- TC-2a.2：构造有 graph 的 Orchestrator → `plan_view()` 返回正确的 steps + waiting
- TC-2a.3：PAUSED 状态的 step 出现在 waiting 列表
- TC-2a.4：无 PAUSED step → waiting=()

### 步 2b：删 Selector L2 keyword 层（~1h）

**范围**：删除 `Selector._resolve_keyword` + 相关测试。

**改动**：
- `selector.py`：删 `_resolve_keyword` 方法 + `pick()` 中的 L2 调用
- `test_selector.py`：删 keyword 相关用例

**测试**：现有 selector 测试（L1/L1.5/L3）全绿。

### 步 2c：多轮讨论回归（~3h）

**范围**：ChatService 加统一回合循环，`respond` 后不退出而继续 decide。

**核心变更**：`ChatService._handle_group` 中纯对话态分支改成循环：

```python
# 现状（步1 strip）:
if decision.action in ("respond", "multi"):
    targets = [m for m in members if m.name in decision.who]
    async for evt in self._respond(session, group, trigger, targets):
        yield evt
    return  # ← 回完即止

# 步2 后（反复 decide）:
max_rounds = settings.max_discussion_rounds  # 默认 5
for _ in range(max_rounds):
    state = await SessionState.from_session(session.id, members, self._messages, run)
    decision = await self._router.decide(state)
    if decision.action in ("respond", "multi"):
        targets = [m for m in members if m.name in decision.who]
        async for evt in self._respond(session, group, trigger, targets):
            yield evt
        continue  # ← 回完继续，下一轮 decide 看到新 transcript
    if decision.action == "task":
        await self._start_coordinator(session, group, trigger)
        return
    # done / feed（纯对话态不会出 feed）
    break
```

**关键细节**：
- `trigger` 仍然是原始触发消息（不是最后一条——因为这是首次 `_handle_group` 调用）
- 每轮的 `state.transcript` 会包含上一轮 agent 刚回复的消息（因为已经落库 + L1）
- 但有一个**微妙的时序问题**：`_respond` 是异步 generator，yield 出去的 event 还没落库时，下一轮 decide 的 transcript 看不到刚回的消息。需要确保每轮结束后消息已落库。

**时序修复**：`_respond` 改为 `await` 完成后再进下一轮（collect 全量 events 而非 lazy yield），或者在每轮 decide 前显式刷 L1/DB。

**测试**（fake）：
- TC-2c.1：fake router 第1轮 respond(后端) → 第2轮 respond(前端) → 第3轮 done
- TC-2c.2：达到 max_rounds 自动终止
- TC-2c.3：中间某轮判 task → 退出循环，调 `_start_coordinator`

### 步 2d：删除 DiscussionOrchestrator 循环 + 清理（~1.5h）

**范围**：删 `DiscussionOrchestrator.run_discussion`；合并 `_stream_one` 到 ChatService。

**改动**：
- `discussion_orchestrator.py`：删 `run_discussion` 方法；保留 `_stream_one` → 改名/移到 ChatService
- `chat_service.py`：`__init__` 去 `discussion` 参
- `wiring` / `chat.py`：注入点更新

**测试**：现有 `test_chat_service.py` 全绿（讨论路由改为走统一循环）。

---

## 6. 文件改动总览

```
改动:
  session_state.py                # from_session 工厂 + PlanView/StepView 扩展
  coordinator_run.py              # plan_view() 只读投影
  chat_service.py                 # 统一回合循环 + _respond 改为多轮
  selector.py                     # 删 L2 _resolve_keyword
  discussion_orchestrator.py      # 删 run_discussion；_stream_one 移入 ChatService

新建:
  tests/test_session_state.py     # TC-2a

删除（步2d 之后）:
  discussion_orchestrator.py      # 整个文件（如果 _stream_one 已合并）
  test_discussion_orchestrator.py # 讨论循环用例

不改（复用）:
  reactive_router.py              # decide 接口不变
  session_state.py                # SessionState/PlanView/StepView DTO 字段不变
  orchestrator.py（task_engine）  # Harness 循环不变
  executor.py                     # 终结工具检测不变
  mcp_step_tools.py               # MCP server 不变
  coordinator_run.py              # start/feed/enqueue_note 不变
  ports.py                        # PlannerDecision 不变
```

---

## 7. 与前后步的衔接

### 7.1 步2 依赖步1 的什么

- `ReactiveRouter.decide`：步2 的多轮循环就是对 `decide` 的反复调用。步1 已经实现了 respond/multi/done，步2 不新增 action。
- `SessionState` / `PlanView` / `StepView` DTO：步1 已定义，步2 不改字段，只加工厂方法。

### 7.2 步2 为步4 铺了什么路

- `SessionState.from_session` + `run.plan_view()`：步4 的 `active_plan` 非空时 `decide` 能读到 DAG 状态，这是 `replan` action 的前提。
- 统一回合循环：步4 的「任务执行中插话 → decide → replan」只是在不退出循环的前提下多一种 action 分支。

### 7.3 步2 不依赖步3

步2（纯对话态多轮）与步3（step-tools、ask/resume）无交集——对话路径不注入 step-tools MCP，不触发终结工具检测。

---

## 8. 风险清单

| 风险 | 影响 | 缓解 |
|------|------|------|
| 多轮 decide 的 LLM 成本 | 每轮 agent 回复后付一次 decide 轻调用 | 廉价模型 + 近窗口截断；max_rounds 硬上限；量级 ≈ 现 Selector L3 频率 |
| decide 多轮不收敛 | 循环一直 respond 不判 done | prompt 强调"讨论收敛即 done"；max_rounds 硬上限；用户随时打断 |
| transcript 时序：agent 回复未落库就进下一轮 | 下一轮 decide 看不到刚回的消息 | `_respond` 改为 collect 完成后再循环；或每轮前显式 await 落库 |
| 删 DiscussionOrchestrator 后 wiring 断裂 | ChatService.__init__ 依赖 discussion 参 | 先删调用再删注入，diff 逐步验证 |
| Selector L2 删除后任务关键词不再截胡讨论 | 任务消息走 decide 判 task 而非 keyword 直选 agent | 这是**期望行为**（设计决策 C）；不影响正确性 |
