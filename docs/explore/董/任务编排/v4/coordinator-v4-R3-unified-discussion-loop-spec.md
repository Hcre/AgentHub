# R3 实现规格 — 多轮讨论统一：decide for 循环 + 删 DiscussionOrchestrator/Selector

> 日期：2026-06-08 | 状态：实现规格 | 关联：[[coordinator-design-v4]] §5、§13.2
> 前提：R0+R1 已完成（事件驱动 + 协议重塑）
> 风险：**小**（删死代码 + 在已有 decide 上加 for 循环；不碰控制流）

---

## 0. 目标

把「回完即止」（strip）升级为「回完继续」（keep）——一次用户消息触发多轮 agent 讨论，每轮经 `decide` 判断是否继续。同时删除 DiscussionOrchestrator（从未接线的死代码）和 Selector（被 ReactiveRouter 取代的 L2 关键词路由器）。

一句话验收：**用户说「帮我分析一下这个方案」，系统 decide → 后端阿强分析 → decide（还没结束）→ 前端小美补充 → decide（done）→ 静默。整个过程同一个 for 循环，没有 DiscussionOrchestrator，没有 Selector。**

---

## 1. 现状（要替换/删除的东西）

### 1.1 chat_service.py — strip 单轮（改）

```python
# _handle_group 当前：decide → respond → 结束（不回环）
if decision.action in ("respond", "multi"):
    if not is_discussion:
        return                              # ← AT_ROUTING 不自动应答
    targets = [m for m in members if m.name in decision.who]
    async for evt in self._respond(session, group, trigger, targets):
        yield evt
    return                                   # ← 回完即止，不继续
```

`_respond` 方法（line 259-272）只做单次流式，不感知循环。`self._discussion`（line 116）存了 DiscussionOrchestrator 实例但**从未被调用**——注释 line 266 说「若改 keep…调 self._discussion 续轮即可」，但从未改到 keep。

### 1.2 DiscussionOrchestrator — 死代码（删）

- `discussion_orchestrator.py`（314 行）：完整的回合循环类，含 `_stream_one`（重复 ChatService 的 `_stream_one_agent`）、`_flush_lock`（并发写 DB 锁）、`SelectorDecision` 引用
- 依赖 Selector 做回合决策（`Selector.pick(members, history, already_spoken)`）
- `max_round` 硬上限、`already_spoken` set、`pending_mentions` 队列、multi-pick 并发、首轮兜底随机选人——所有能力都已存在于 ReactiveRouter + 简单 for 循环，不需要独立类

### 1.3 Selector — L2 关键词层（删）

- `selector.py`（458 行）：四层路由（@mention 直达 → 全体关键词 → capability_tags 匹配 → LLM 决策）
- Layer 1/1.5（@mention/broadcast）：已在 ChatService 前门零 LLM 反射实现，重复
- Layer 2（capability_tags 关键词）：v4 已删除 capability 关键词层（design-v4 §13.1），Planner.decide 的 LLM 判断取代关键词匹配
- Layer 3（LLM 决策）：已被 ReactiveRouter.decide 完全取代，功能等价但调用链更短
- `SelectorDecision` dataclass：仅 DiscussionOrchestrator 使用，一并删除

### 1.4 受影响文件一览

| 文件 | 现状 | 目标 |
|------|------|------|
| `chat_service.py` | `_respond` 单轮；`self._discussion` 存而不用 | `_handle_group` 内 for 循环反复 decide；删 `self._discussion` |
| `discussion_orchestrator.py` | 314 行死代码 | **删除整个文件** |
| `selector.py` | 458 行，Layer 1/1.5 重复、Layer 2 已删除、Layer 3 被取代 | **删除整个文件** |
| `deps.py` | 构造 DiscussionOrchestrator/Selector 注入 ChatService | 删构造代码，ChatService 不再接收 discussion 参数 |
| `ws/chat.py` | 同上 | 删构造代码 |
| `config.py` | `selector_model`/`selector_provider`/`selector_max_prompt_chars` | **保留重命名**：这些配置实际上是 ReactiveRouter 在用（line 70-71），改名为 `reactive_model`/`reactive_provider`/`reactive_max_prompt_chars` |
| `enums.py` | `DispatchMode.DISCUSSION` | **保留**（Group.dispatch_mode 仍用它区分 AT_ROUTING vs DISCUSSION；R2 统一路由后再决定是否删） |

---

## 2. 目标态

### 2.1 chat_service.py：多轮 decide for 循环

`_handle_group` 的 respond/multi 分支从「单次 `_respond` + return」改为：

```python
# ── 多轮讨论循环（v4 §5：反复 decide，strip→keep）──
round_idx = 0
while True:
    round_idx += 1
    # 每轮重新构造 state（transcript 已包含前面轮次的回复）
    state = SessionState(
        session_id=session.id,
        members=tuple(members),
        transcript=tuple(await self._recent_history(session)),
        active_plan=run.plan_view() if run else None,  # R2 补；当前 run=None
    )
    decision = await self._router.decide(state)
    logger.info(
        "discuss session=%s round=%d → %s who=%s reason=%s",
        session.id, round_idx, decision.action, decision.who, decision.reason,
    )

    if decision.action == "task":
        await self._start_coordinator(session, group, trigger)
        return

    if decision.action in ("respond", "multi"):
        targets = [m for m in members if m.name in decision.who]
        if not targets:
            logger.warning(
                "decide %s 返回不存在的 target=%s，退出讨论",
                decision.action, decision.who,
            )
            break
        for target in targets:
            async for evt in self._stream_one_agent(
                session=session, group=group, target=target, trigger=trigger
            ):
                yield evt
        # 观测口：10 轮以上仍未收敛 → 运维可见（不做硬截断）
        if round_idx >= 10 and round_idx % 5 == 0:
            logger.warning(
                "discuss 已达 %d 轮仍未收敛 session=%s 最后 action=%s",
                round_idx, session.id, decision.action,
            )
        continue

    # done / feed / note（讨论态 prompt 不会出 feed/note，但显式处理）
    # done：LLM 判讨论已收敛，静默退出
    # feed/note：讨论态 prompt 不列，若 LLM 偶尔出 → 退出（不吞、不转义）
    break
```

**关键变更**：

1. **循环位置**：在 `_handle_group` 内，取代原来的 `if decision.action in ("respond", "multi")` 分支。循环只在 DISCUSSION 模式下进入——AT_ROUTING 群在循环入口前 `if not is_discussion: return`（见 §2.1 上下文），不会进此循环。

2. **每轮重建 SessionState**：transcript 已包含前面轮次 agent 的回复（`_recent_history` 每次查 DB/缓存），Planner 看到的是最新的对话上下文。

3. **LLM 判 done**：唯一出口。Planner 从 transcript 自然看到讨论已收敛（观点已充分表达、无新信息、或在重复），返回 `done`。不设机械轮次上限、不设每人发言次数限制——同一个人可以被追问多次，讨论该几轮就几轮。

4. **`task` 中断**：讨论中用户实质上在布置开发任务 → decide 判 `task` → 退出循环，起 Harness。

### 2.2 防循环：只靠 LLM 判 done + 观测口

| 机制 | 位置 | 说明 |
|------|------|------|
| LLM 判 done | decide prompt | 唯一出口 |
| 观测口 | `logger.warning`（10 轮起，每 5 轮） | 不截断，但运维可见 |

**不设任何机械限制**——没有轮次上限、没有每人发言次数上限。

为什么这是安全的：

- **LLM 天然会收敛**：每轮 transcript 增长，LLM 看到讨论在重复/无新信息时自然判 done。
- **同一个人多次发言是正常需求**：阿强回答了问题 → 小美追问 → 阿强澄清。`already_responded` 拦的是正常对话流。
- **观测口不是硬截断**：`round_idx >= 10` 起打 `logger.warning`，作用是运维可见——如果讨论真的卡住了，日志会有周期性告警，人工介入。不设 `max_rounds` 硬上限——截断正常讨论的代价大于一次异常的浪费。
- **根因在 LLM 质量**：如果 LLM 持续循环不止，是 prompt/model 问题，应该在 prompt 或模型层修复，不在循环控制层打补丁。

与 DiscussionOrchestrator 的防循环对比：

| DiscussionOrchestrator | R3 while 循环 | 优劣 |
|---|---|---|
| `already_spoken: set[UUID]` | 无——同一人可多次发言 | R3 更自然：追问/澄清不被系统拦 |
| `max_round` 硬上限 | 无——LLM 判 done 唯一出口 | R3 不截断正常讨论 |
| Selector.done（LLM 判定） | ReactiveRouter.decide → done | 等价，但 R3 少一层抽象 |
| `pending_mentions` 队列 | 不需要——@mention 已在 ChatService 前门零 LLM 处理 | R3 更简 |
| 首轮兜底随机选人 | 不需要——decide 不会在首轮返回 done（prompt 有指导） | R3 更简 |

### 2.3 _respond 方法：内联，删方法

`_respond` 当前只做「target 循环 → 流式」。R3 的 for 循环直接在 `_handle_group` 内调 `_stream_one_agent`，不再需要 `_respond` 方法。删 `_respond`，减少中间层。broadcast 路径也直接调 `_stream_one_agent`。

### 2.4 deps.py / ws/chat.py：删 DiscussionOrchestrator/Selector 构造

```python
# deps.py — 删（line 24-26, 130-138, 164-173）
from app.application.services.discussion_orchestrator import DiscussionOrchestrator  # 删
from app.application.services.selector import Selector                                # 删

# ChatService 构造：删 discussion 参数
chat_service = ChatService(
    ...
    discussion=DiscussionOrchestrator(...),  # ← 删整行
    ...
)
```

```python
# ws/chat.py — 删（line 19-21, 79-88）
from app.application.services.discussion_orchestrator import DiscussionOrchestrator  # 删
from app.application.services.selector import Selector                                # 删

# 同样删 DiscussionOrchestrator/Selector 构造
```

ChatService.\_\_init\_\_ 签名删 `discussion` 参数和 `self._discussion` 赋值。

### 2.5 config.py：重命名 selector_* → reactive_*

`selector_model`/`selector_provider`/`selector_max_prompt_chars` 在 ReactiveRouter 中使用（line 70-71），改名以反映实际用途：

```python
# config.py
reactive_model: str = "deepseek-chat"       # 原 selector_model
reactive_provider: str = "deepseek"         # 原 selector_provider
reactive_max_prompt_chars: int = 4000       # 原 selector_max_prompt_chars
# max_discussion_rounds — 删除（R3 不设机械轮次上限，防循环只靠 LLM 判 done，§2.2）
#   原用途：DiscussionOrchestrator 的硬截断上限，R3 整个类删除后该配置无消费者
```

`ReactiveRouter.__init__` 的 `settings.selector_model` → `settings.reactive_model`，`settings.selector_provider` → `settings.reactive_provider`。

### 2.6 ReactiveRouter feed 路径更新

当前 `_parse_payload` 的 feed 分支（line 106-112）依赖 `state.active_plan.waiting`——这是 v3 概念。R2 会删除 `waiting` 字段（design-v4 §3，PlanView 无 waiting）。R3 不依赖 waiting（当前执行态走 try_feed 而非 decide→feed），但为 R2 铺路：

```python
# feed 分支暂时保留但标记 deprecation
if action == "feed":
    step = payload.get("feed_step")
    answer = payload.get("answer")
    # TODO(R2): 取代 waiting 检查，从 PlanView.steps 找 not_done 节点
    if not step or not answer:
        logger.warning("ReactiveRouter feed 非法，降级 done")
        return PlannerDecision.done("feed: invalid step/answer")
    return PlannerDecision(action="feed", feed_step=step, answer=answer, reason=reason)
```

R3 不删这段，只删 `waiting` 引用（waiting 改为从 PlanView.steps 中筛选 not_done——此项留 R2）。

---

## 3. 代码变动清单

| 文件 | 变 | 不变 |
|------|-----|------|
| `chat_service.py` | `_handle_group`：删 DiscussionOrchestrator import；删 `self._discussion`；删 `_respond` 方法；respond/multi 分支改为 while True 循环（每轮 decide，LLM 判 done 退出，无机械上限） | `_handle_group` 其余路径（@mention/control/broadcast/task）；`_stream_one_agent`；`_start_coordinator` |
| `discussion_orchestrator.py` | **删除整个文件** | — |
| `selector.py` | **删除整个文件** | — |
| `deps.py` | 删 DiscussionOrchestrator/Selector import 和构造 | ChatService 其余参数 |
| `ws/chat.py` | 同上 | 其余 wiring |
| `config.py` | `selector_model`→`reactive_model`，`selector_provider`→`reactive_provider`，`selector_max_prompt_chars`→`reactive_max_prompt_chars`；**删 `max_discussion_rounds`**（DiscussionOrchestrator 已删，无消费者） | — |
| `reactive_router.py` | `settings.selector_*` → `settings.reactive_*` | decide 逻辑不动 |

---

## 4. 测试变更

### 4.1 新增测试

| 测试 | 验证 |
|------|------|
| `test_multi_round_discuss_two_agents_then_done` | decide 第一轮→respond(阿强)→流式→第二轮→respond(小美)→流式→第三轮→done→退出 |
| `test_multi_round_same_agent_can_speak_again` | 阿强发言 → 小美追问 → decide 再次选阿强澄清 → 阿强正常发言（不被 already_responded 拦截） |
| `test_multi_round_task_interrupts_loop` | 第三轮 decide 返回 task → 退出循环，起 Harness |
| `test_multi_round_done_exits_immediately` | 首轮 decide 返回 done → 不流式，直接退出 |

### 4.2 删除测试

| 测试 | 理由 |
|------|------|
| `test_selector_*`（所有 Selector 相关测试） | Selector 类删除 |
| `test_discussion_orchestrator_*`（所有 DiscussionOrchestrator 相关测试） | DiscussionOrchestrator 类删除 |

### 4.3 适配测试

| 测试 | 变 |
|------|-----|
| `test_handle_group_*` 中涉及 DISCUSSION 模式的路由测试 | 确认 respond/multi 触发 for 循环而非单次 _respond |
| `test_reactive_router_*` | `settings.selector_*` → `settings.reactive_*` 引用更新 |

---

## 5. 不动的部分

| 保留项 | 原因 |
|--------|------|
| ReactiveRouter.decide | R3 只改调用方式（单次→循环），不改 decide 本身 |
| `_stream_one_agent` | 多轮讨论的流式仍用它，不做修改 |
| ChatService 前门机械反射（@mention/control/broadcast） | 零 LLM，不依赖讨论循环 |
| MemorySelector | 独立组件（记忆检索），不是讨论选人器 |
| DispatchMode 枚举 | R2 统一路由后再决定是否删 |
| CoordinatoRun / Orchestrator | 不碰任务执行路径 |

---

## 6. 风险

1. **LLM 成本**：每条用户消息可能触发多次 decide（讨论几轮就几次）。v4 §11 的「两档成本纪律」已涵盖此场景（reactive 调用是廉价模型）。DiscussionOrchestrator 原本也是每轮一次 Selector LLM 调用，R3 不增加调用量。LLM 判 done 是自然收敛点，不会无限循环。

2. **循环内 state 刷新**：每轮 `_recent_history` 查 DB，但上一轮 agent 的回复可能尚未落库（`_stream_one_agent` 在流式结束后才 `await self._messages.save()`）。→ **需要确保每轮流式完成后再查 history**。实现时 for 循环的 `await` 已保证顺序：`_stream_one_agent` 是 async generator，`async for` 结束意味着流式已完成 + 落库已完成。

3. **`_recent_history` 每轮 DB 查询**：每条用户消息触发 N 轮讨论 = N 次 `_recent_history` 查询（查最新 15 条消息）。3-5 轮讨论还好，极端 10+ 轮时是浪费。优化方向（后续 PR，不阻塞 R3）：首轮查一次，后续轮手动拼接上一轮 agent 的回复到 transcript 尾部——节省 N-1 次 DB 查询。当前先保持每轮 DB 查询的简单实现。<｜end▁of▁thinking｜>

4. **DISCUSSION vs AT_ROUTING**：当前 DISCUSSION 模式才进入多轮循环（AT_ROUTING 直接返回）。R2 统一路由后两种模式的行为将趋同，但 R3 保留现有 gating 逻辑不动。

5. **DiscussionOrchestrator 的 `_flush_lock` 能力丢失**：原 DiscussionOrchestrator 有并发写 DB 锁（`_flush_lock`），但 R3 的 for 循环**串行**执行（一个 agent 流完才进下一轮），不涉及并发写 DB，不需要这个锁。

5. **broadcast 路径**：当前 `_handle_group` line 208-212 的 broadcast 路径调用 `_respond`。删 `_respond` 后需改为直接调 `_stream_one_agent`（串行对多人流式）。

---

## 7. 与 R2 的耦合

R2（路由统一）会改 `SessionState.from_session` + `plan_view()` 工厂方法。R3 的 for 循环里构造 `SessionState` 的方式会受 R2 影响——当前手工构造 `SessionState(...)`，R2 后改为 `SessionState.from_session(...)`。

实现顺序建议：**R3 先用当前 `SessionState(...)` 手工构造，R2 接上后改为 `from_session` 工厂**。两者不冲突——接口兼容、单向替换。

---

## 8. 实现记录

> 实现日期：2026-06-08 | 状态：已实现，测试全绿（230 passed，2 个 pi_agent e2e 预存失败与本次无关）

### 与规格的偏离 / 审查修正

1. **`selector_max_prompt_chars` 删除而非改名（审查 N1）。**
   规格 §2.5 让它改名 `reactive_max_prompt_chars`，但实测 ReactiveRouter 用硬编码
   `_MAX_TRANSCRIPT=15`/`_PER_MSG_CHARS=300`，**不读此配置**；唯一消费者是已删的 selector.py。
   故直接删除（改名后零消费者 = 死配置）。`selector_model/provider` 才改名为 `reactive_model/provider`。

2. **加 `_DISCUSS_SOFT_LIMIT=10` 软观察口（审查问题 3）。**
   不设硬截断（同意规格「防循环只靠 LLM 判 done」），但 ≥10 轮打 `logger.warning`——
   运维可见异常，绝不截断正常讨论。成本为零。

3. **执行态 respond 单轮，不进讨论循环。**
   R2 引入执行态 respond（「做得怎么样了」即时回复）。R3 的多轮循环**仅纯对话 DISCUSSION 态**进入；
   执行态（active_plan 非空）respond 走单轮 `_stream_targets` 后返回——不把进度询问变成多轮讨论。
   AT_ROUTING 纯对话态仍静默。三态门禁：执行态单轮 / DISCUSSION 多轮 / AT_ROUTING 静默。

4. **`_respond` 删除，拆为 `_stream_targets`（单轮）+ `_discuss_loop`（多轮）。**
   broadcast 路径内联 `_stream_one_agent` 循环（不再借道 `_respond`）。

### 防循环机制（最终）

- **唯一出口**：LLM 判 done（或 task 中断起 Harness，或 who 幻觉/非 respond → 收敛退出）。
- **无机械上限**：同一 agent 可被多轮选中（追问/澄清不被拦），无 `already_responded`、无 `max_round`。
- **软观察**：≥10 轮打 warning。
- who 幻觉（LLM 返回不存在 agent 名）→ 立即 `return`，不 continue（输入没变会死循环）。

### 部署注意

- `.env` 若曾配 `SELECTOR_MODEL`/`SELECTOR_PROVIDER`，需改为 `REACTIVE_MODEL`/`REACTIVE_PROVIDER`
  （pydantic 字段改名 → 旧环境变量不再映射，会静默用默认值）。默认 `deepseek-chat`/`deepseek` 不变。

### 改动文件

| 文件 | 改动 |
|------|------|
| `chat_service.py` | 删 `discussion` 依赖/`_discussion`/`_respond`；respond/multi 改三态门禁（执行单轮/DISCUSSION 多轮 `_discuss_loop`/AT_ROUTING 静默）；broadcast 内联；加 `_stream_targets`/`_discuss_loop` + `_DISCUSS_SOFT_LIMIT` |
| `discussion_orchestrator.py` | **删除**（314 行死代码，从未接线） |
| `selector.py` | **删除**（458 行，L1/1.5 重复、L2 已删、L3 被 ReactiveRouter 取代） |
| `deps.py` / `ws/chat.py` | 删 DiscussionOrchestrator/Selector import + 构造；ChatService 不再收 discussion 参数 |
| `config.py` | `selector_model/provider` → `reactive_model/provider`；删 `selector_max_prompt_chars` + `max_discussion_rounds` |
| `reactive_router.py` | `settings.selector_*` → `settings.reactive_*` |

### 测试

- 删 `test_selector.py`（Selector 类删除）。
- 改 `test_chat_service.py`：两个构造 helper 去掉 discussion 参数。
- 新增 4 个多轮讨论测试：respond(A)→respond(B)→done、同一 agent 多轮、task 中断循环、首轮 done 不回环。
- DiscussionOrchestrator 无独立测试文件（其逻辑已并入 chat_service 测试）。
