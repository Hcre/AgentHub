# Coordinator v3 步1 专属推演 — 统一前门路由的数据流

> 日期：2026-06-07 | 配套 [[coordinator-design-v3]] §4/§5 + [[coordinator-v3-step1-unified-router-plan]]
> 目的：把 §1 前门（[[coordinator-scenario-v3]] 里标 `[v3新]` 还没建的那半截）单独走通——`Planner.decide` 在 **respond / task / feed** 三种返回下的完整函数调用与数据形状。
> 标注：`[现有]`=已实现复用；`[v3改]`=改现有；`[v3新]`=步1 新增；`[反射]`=机械零 LLM 前门。
> 决策前提（见 step1 计划「拍板」表）：A=两档 LLM、B=**本推演不展开续轮**（strip/keep 都不影响 decide 数据流，footnote 标）、C=删 capability 关键词层、D=接受 decide 成本、E=`@`走 respond。

---

## 0. 场景设定

**群组** `group#blog`，dispatch_mode=DISCUSSION，成员 3 agent：

| name | id | capability |
|------|----|-----------|
| 后端阿强 | `a-be` | backend, api |
| 前端小美 | `a-fe` | frontend, ui |
| 测试小测 | `a-qa` | testing |

一条会话 `S` 上**按时间顺序**进来 7 条消息，覆盖前门所有分支。每条都从 `ChatService._handle_group`（chat_service.py:161）进。

---

## 1. 前门骨架：三道机械反射 + 一次 decide

`[v3改]` 重写后的 `_handle_group`（删 gate 整段，decide 单点）：

```python
async def _handle_group(self, session, group, trigger):
    # ── 反射①：@mention 直达（[现有]，已在最前）──
    targets = await self._resolve_mentions(trigger.mentions, group)   # chat_service.py:272
    if targets:
        for t in targets: yield from self._stream_one_agent(...t...)  # E：@ 走 respond
        return

    text = trigger.content or ""
    run = self._registry.get(session.id)                              # [现有] CoordinatorRun|None

    # ── 反射②：control（[反射]，is_control 从 gate 移入）──
    if self._is_control(text):                                        # [v3改] 静态正则
        if run is not None: await self._cancel_coordinator(session, run)
        return                                                        # 无 run 时 control 空操作

    # ── 反射③：全体意图（[反射]，从 selector L1.5 提升为前门）──
    if run is None and self._is_broadcast(trigger):                   # [v3改] 用户消息触发
        async for evt in self._respond(session, group, trigger, who=ALL): yield evt
        return

    # ── 唯一一次 reactive LLM 决策（[v3新]）──
    state = self._build_session_state(session, group, trigger, run)   # [v3新] §2
    decision = await self._planner.decide(state)                     # [v3新] §3
    async for evt in self._dispatch(session, group, trigger, run, decision):  # §4
        yield evt
```

> **与现状差**：现状是 `is_control → has_work_intent → is_decompose → selector` 四段两脑；这里是 `三反射 → decide` 一段一脑。`has_work_intent`/`is_decompose`/capability 关键词层全删（C）。

---

## 2. `[v3新]` SessionState：两条事件流的只读投影

decide 的输入。步1 用**轻量版**（不依赖步2 的完整 read-model）：

```python
@dataclass(frozen=True)
class SessionState:              # [v3新]（步1 轻量版，步2 升级为完整两流投影）
    session_id: UUID
    members: tuple[Agent, ...]                    # [现有] 候选 worker
    transcript: tuple[Message, ...]               # [现有] 近窗口 15 条（复用 _recent_history）
    active_plan: PlanView | None = None           # None=纯对话态；非 None=任务在跑
    # ↑ 态由 active_plan 派生，无 mode 枚举（design §3）

@dataclass(frozen=True)
class PlanView:                  # [v3新] active_plan 非空时的 DAG 只读投影
    steps: tuple[StepView, ...]                    # 各 step 的 (id, worker, status)
    waiting: tuple[str, ...] = ()                  # 处于 waiting 的 step_id（feed 路由用）

@dataclass(frozen=True)
class StepView:
    step_id: str; worker: str; status: str        # status ∈ pending/running/paused/completed/...
```

构造（`run` 非空时从 Orchestrator 投影 DAG 状态）：

```python
def _build_session_state(self, session, group, trigger, run) -> SessionState:  # [v3新]
    recent = await self._recent_history(session)                  # [现有] chat_service.py:212
    plan = run.plan_view() if run is not None else None           # [v3新] run 暴露只读投影
    return SessionState(session_id=session.id, members=tuple(group_members),
                        transcript=tuple(recent), active_plan=plan)
```

---

## 3. `[v3新]` Planner.decide：一次 reactive tool_use

复用 selector.py 的 provider 分发 + tool_use 解析（selector.py:301 范式），只换 schema + system prompt。

```python
@dataclass(frozen=True)
class PlannerDecision:           # [v3新]
    action: Literal["respond","multi","task","feed","done"]   # replan 留步4
    who: tuple[str, ...] = ()    # respond/multi 的目标 agent name
    feed_step: str | None = None # feed 的目标 step_id
    answer: str | None = None    # feed 的答案文本

async def decide(self, state: SessionState) -> PlannerDecision:   # [v3新]
    # tool_use schema: {action, who[], feed_step, answer, reason}
    # system prompt 要点（承接语理解进 prompt，不硬编码）：
    #   active_plan is None:
    #     "要实际写代码/改文件/跑命令的开发任务" → task
    #     该谁回 → respond(who) / 多人 → multi(who) / 无需回 → done
    #   active_plan 非 None:
    #     上一条 agent 消息是某 waiting step 的 ask + 这条像回答 → feed(step,answer)
    #     否则 chitchat → respond / 无需回 → done
    #     （replan 留步4，步1 不出）
    ...降级铁律：任何异常/不可解析 → PlannerDecision(action="done")  # 永不阻塞用户
```

---

## 4. 三条返回的分发 `[v3新]` `_dispatch`

```python
async def _dispatch(self, session, group, trigger, run, d: PlannerDecision):
    match d.action:
        case "task":                          # → §4.A 重执行
            await self._start_coordinator(session, group, trigger)   # [现有] chat_service.py:219
        case "respond" | "multi":             # → §4.B 轻执行
            async for evt in self._respond(session, group, trigger, who=d.who): yield evt
        case "feed":                          # → §4.C 喂 waiting step
            if run is not None: run.feed(d.feed_step, d.answer)       # [v3新/步3已有] coordinator_run.feed
        case "done":
            logger.debug("decide=done，静默")
```

---

### 4.A 消息①「帮我做个博客系统」→ `task`

```python
trigger = Message(role=USER, content="帮我做个博客系统，要能发文章")
# 反射①@:无 反射②control:否 反射③broadcast:否
state = SessionState(active_plan=None, transcript=[...], members=(a_be,a_fe,a_qa))
decision = await planner.decide(state)
# → PlannerDecision(action="task")
# _dispatch → _start_coordinator → CoordinatorRun → Orchestrator.run()
#   （后续 = coordinator-scenario-v3 §2~§5，本推演不重复）
```

> **这一跳正是修白名单 bug 的地方**：现状若用户说「博客系统能不能直接做了」——没有「帮我/实现」工作动词 → `has_work_intent`=false → 落讨论 → capability「系统」可能命中某 agent 闲聊截胡。v3 这条消息进 `decide`，由 LLM 判 NEEDS_TASK，**无白名单可漏**。

---

### 4.B 消息②「这个 Strapi 的权限模型你们怎么看」→ `respond`

纯讨论，无任务意图：

```python
trigger = Message(role=USER, content="这个 Strapi 的权限模型你们怎么看")
state = SessionState(active_plan=None, ...)
decision = await planner.decide(state)
# LLM 读近窗口 + 成员能力 → 后端阿强最相关
# → PlannerDecision(action="respond", who=("后端阿强",))
# _dispatch → _respond(who=("后端阿强",)) → _stream_one_agent(target=a_be)  [现有] chat_service.py:295
```

`_respond` `[v3新]`（薄封装，把 who 翻成 Agent 复用现有单 agent 流）：

```python
async def _respond(self, session, group, trigger, who: tuple[str,...]):  # [v3新]
    agents = [self._by_name[n] for n in who if n in self._by_name]
    for a in agents:
        async for evt in self._stream_one_agent(session=session, group=group,
                                                target=a, trigger=trigger): yield evt
```

> **决策 B 的落点（本推演不展开）**：后端阿强回完后——
> - **strip**：到此为止，本回合结束。多轮接力等步2 统一循环。
> - **keep**：交 `DiscussionOrchestrator` 用内部 Selector 续选下一位。
> decide 的数据流两种都一样，差别只在「回完之后」。

消息③「大家都说说」会在**反射③**就被拦截（`_is_broadcast`），返回 `multi(全员)`，**根本不进 decide**——零 LLM。

---

### 4.C 消息⑥「用 CMS，接 Strapi」（任务执行中，step_B 在 waiting）→ `feed`

前提：此刻 `task` 已起，DAG 跑到 `A=completed, B=running→paused(waiting), C=pending`，前端小美刚 ask 过「Markdown 还是 CMS？」。

```python
trigger = Message(role=USER, content="用 CMS，接 Strapi")
run = self._registry.get(S)                       # 非空！
# 反射②control:否（"用 CMS" 不匹配取消正则）
state = SessionState(
    active_plan=PlanView(
        steps=(StepView("A","后端阿强","completed"),
               StepView("B","前端小美","paused"),
               StepView("C","测试小测","pending")),
        waiting=("B",)),                           # [v3新] B 在等回答
    transcript=(..., 前端小美的_ask, 用户的回答))
decision = await planner.decide(state)
# decide 读到：B 在 waiting、上一条 agent 消息是 B 的 ask、这条像回答
# → PlannerDecision(action="feed", feed_step="B", answer="用 CMS，接 Strapi")
# _dispatch → run.feed("B", "用 CMS，接 Strapi")   [步3 已实现] → 唤醒挂起 run → resume step_B
```

> **这就是 §11.4「同一张地图」**：decide 不是"插话撞 DAG"，是读同一份 SessionState（含 waiting 投影）判出"这是回答 B"，而非 chitchat / replan。
>
> **替代现状**：步3 我实现的是 `chat_service` 简化版——`run.has_waiting_step()` 为真就把消息 feed 给唯一 waiting step（MVP 串行只有一个）。**步1 落地后**升级为这里的 `decide` 版：能分辨「回答 ask vs 闲聊 vs（步4）改计划」，且支持多 waiting step 精确路由。

---

## 5. 七条消息的前门判定总表

| # | 消息 | 命中 | 出口 | 付 LLM |
|---|------|------|------|--------|
| 1 | 帮我做个博客系统 | decide | `task` → 起 Harness | 1（decide）+ N（plan） |
| 2 | Strapi 权限怎么看 | decide | `respond(后端阿强)` | 1 |
| 3 | 大家都说说 | 反射③broadcast | `multi(全员)` | **0** |
| 4 | @前端小美 看下这个 | 反射①@mention | respond(前端小美) | **0** |
| 5 | 取消 | 反射②control | cancel run | **0** |
| 6 | 用 CMS，接 Strapi（B waiting 中） | decide | `feed(B, …)` | 1 |
| 7 | 嗯好的（可选机械短路，D） | decide 前短路 | `done` 静默 | **0**（短路）/ 1（不短路） |

> 成本（D）：机械反射 + 可选短路兜住了 @/全体/control/纯应答四类零 LLM；真正付 decide 的是「需要判断的对话/任务/答案」——量级 ≈ 现 selector L3。

---

## 6. 步1 改动落点（对齐 step1 计划）

| 落点 | 文件 | 性质 |
|------|------|------|
| `_handle_group` 重写（三反射 + decide 单点） | `chat_service.py` | [v3改] |
| `is_control`/`is_broadcast` 前门反射 | `chat_service.py`（从 gate/selector 搬） | [v3改] |
| `_respond` / `_dispatch` 薄封装 | `chat_service.py` | [v3新] |
| `PlannerDecision` / `SessionState` / `PlanView` | `ports.py` + 新 `session_state.py` | [v3新] |
| `decide()` reactive 实现 | 新 `reactive_router.py` | [v3新] |
| 删 `CoordinatorGate` + capability 关键词层（C） | 删 `coordinator_gate.py`、`selector._resolve_keyword` | [删] |
| `run.plan_view()` 只读投影 | `coordinator_run.py` / `orchestrator.py` | [v3新] |

> **不动**：`_start_coordinator` 链路、`_stream_one_agent`、`build_graph`/调度内核、step-tools（步3）——前门换脑，骨架与手不动。

---

## 7. 本推演暴露的待确认

1. **decide 在 active_plan 非空时只出 feed/respond/done，不出 replan**（步4 才放开）——本推演已按此画。确认步1 边界就停在这。
2. **`run.plan_view()` 投影粒度**：步1 只需 (step_id, worker, status, waiting[])。够 feed 路由判断，不下放完整 task_event。
3. **决策 B 仍未定**（strip/keep）——本推演 decide 数据流与 B 无关，但 §4.B「回完之后」要等 B 拍板才能写 `_respond` 是否接 DiscussionOrchestrator 续轮。**这是步1 编码前最后一个开口。**
