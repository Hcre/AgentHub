# 协调者模块 整体设计架构

> 日期：2026-06-08 | 基于 design v3 + 步1/步2/步3 讨论
> 涵盖：架构分层、路由模型、执行模型、状态投影、当前实现状态

---

## 1. 架构概览：一个大脑 + 一套骨架 + N 只手

```
用户/Agent 消息
      │
      ▼
┌─────────────────────────────────────────┐
│              ChatService（前门）          │
│                                          │
│  零 LLM 反射：@mention / control / broadcast │
│  其余 → SessionState.from_session()       │
│       → Planner.decide(state)            │
│       → dispatch(action)                 │
└──────────────┬──────────────────────────┘
               │
     ┌─────────▼─────────┐
     │  Planner = 唯一大脑 │  ← LLM（一次轻调用 / tool_use）
     │                    │
     │  reactive 视野      │  deliberate 视野
     │  decide(state)     │  plan(ctx)
     │  → respond/multi   │  → TaskDef[] → DAG
     │  → task            │
     │  → feed            │
     │  → done            │
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

三层定位：

| 层 | 是什么 | 决策方式 | 管什么 |
|----|--------|---------|--------|
| **大脑** Planner | 决定下一步做什么 | LLM | 路由（respond/task/feed/done）、任务分解（DAG 结构） |
| **骨架** Harness | 按图执行、跑验收 | 确定性代码 | 图遍历、FSM、验收命令、事件记录 |
| **手** Worker | 实际干活 | agent CLI | 写代码、读文件、调工具、提问、交卷 |

**Harness 不是大脑**。`compute_frontier` 做的事是「遍历 DAG，找出依赖已满足的节点」——这是图论属性，不需要语义判断。跟 `for item in list` 是同一性质的机械操作。

---

## 2. 核心命题：对话是任务的退化，任务是对话的延伸

一次对话发言 = 一个只有 1 步、step 类型为 `respond` 的退化 plan。

Planner 的输出永远是 plan。唯一的变量是视野与 step 类型：

| | 对话（reactive） | 任务（deliberate） |
|---|---|---|
| 视野 | horizon=1，每轮重规划 | horizon=N，规划一次 |
| step 类型 | `respond`（出消息，产物即消息本身） | `work`（写代码/改文件，产物=artifact） |
| 终止条件 | LLM 判 done（软） | worker 调 `task_complete` + 验收通过（硬） |
| LLM 成本 | 每条消息一次轻调用 | 仅 NEEDS_TASK 时一次重调用 + 后续 replan |

决策层统一，执行引擎不统一：`respond` 绝不走 DAG/验收；`work` 才走完整 Harness。

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
    transcript: tuple[Message, ...]     # 近 15 条消息（含 agent）
    active_plan: PlanView | None        # None=纯对话；非 None=DAG 投影

@dataclass(frozen=True)
class PlanView:
    steps: tuple[StepView, ...]         # 各节点 (id, worker, status)

@dataclass(frozen=True)
class StepView:
    step_id: str
    worker: str
    status: str                         # pending/running/completed/failed/blocked
```

- `active_plan is None` = 纯对话态。`active_plan 非 None` = 任务在跑
- **没有显式 mode 枚举**——态由 active_plan 派生
- **没有 waiting 列表**——worker 有没有在问问题，Planner 从 transcript 自然看到
- Read-model，不是可变对象。DAG 变更走单写者（Orchestrator）；transcript 来自 messages 表

---

## 4. 路由模型：一条路径

```
用户消息 → ChatService._handle_group
  │
  ├─ 反射① @mention 解析     → 命中 → _stream_one_agent
  ├─ 反射② is_control        → 命中 → cancel / 忽略
  ├─ 反射③ is_broadcast      → 命中 → multi 全员
  │
  └─ SessionState.from_session → Planner.decide(state)

      ┌────────────────────────────────────────┐
      │ respond(who) → _stream_one_agent       │
      │   → 回完 continue（多轮）              │
      │                                        │
      │ multi(who)  → 多人并行 stream          │
      │                                        │
      │ task        → Planner.plan(ctx)        │
      │             → 起 Harness（后台任务）    │
      │                                        │
      │ feed(step)  → 重新派发该 step 的 worker │
      │             → worker resume 上下文      │
      │                                        │
      │ done        → 静默                      │
      │ （replan 留步4）                        │
      └────────────────────────────────────────┘
```

**跟 `active_plan` 无关**——同一扇门，同一段代码，同一个 Planner。`active_plan` 只是 Planner 读到的字段之一，跟 `transcript` 一样。

---

## 5. 任务执行模型

### 5.1 两步走

```
reactive decide → "task"
  → Planner.plan(ctx)  ← deliberate，一次重 LLM
  → TaskDef[] = [
      {id:"A", worker:"后端", depends:[],   验收:"pytest tests/api"},
      {id:"B", worker:"前端", depends:["A"], 验收:"npm run build"},
      {id:"C", worker:"测试", depends:["A","B"], 验收:"npm run e2e"},
    ]
  → build_graph → TaskGraph
  → Orchestrator.run()  ← fire-and-forget 后台任务
```

### 5.2 执行循环（确定性，零 LLM）

```python
for _ in range(max_steps):
    ready = select_dispatchable(compute_frontier(graph))
    if ready:
        await _execute_and_settle(node)
        continue
    return _terminal()
```

每一步：PENDING → QUEUED → RUNNING → VERIFYING → COMPLETED（或 FAILED → PENDING 重试）。

### 5.3 两种状态，不是七种

从 Harness 视角，任务只有两种状态：

```
DONE（交卷了）            NOT DONE（还没做完）
  COMPLETED                 PENDING / QUEUED / RUNNING / FAILED / BLOCKED
  验收通过 ✅
```

**不需要 PAUSED**。Worker 问问题、等答案、跟人讨论——全是「还没做完」的自然组成部分。跟 worker 在写代码、在思考一样，Harness 不需要区分。

Harness 只关心一件事：**worker 调了 task_complete 没有**。调了 → 验收。没调 → 不是完成。

### 5.4 唯一的结构化信号：task_complete

Worker 跟 Harness 之间的结构化协议只需要一个 tool：

| tool | 含义 | Harness 反应 |
|------|------|-------------|
| `task_complete(summary)` | "活干完了，产物在此" | RUNNING → VERIFYING → 验收 → COMPLETED |

**不需要 `ask` tool**。Worker 提问就是正常的文本输出——跟对话路径一样，直接推群聊。跟 `Read`/`Write`/`Bash` 一样是普通的工具调用，不触发状态变更。

```
Worker CLI:
  → Read 代码
  → "存储方式没定。用 Markdown 还是接 CMS？"  ← 文本输出，推到群聊
  → 流结束（V0 短驻 stdin 关了）→ 不是完成，就是结束了

Harness:
  → WorkerOutcome(status="not_done")
  → 不转任何状态。step 保持 RUNNING。
```

后续流程：
- 用户回话 → `decide` 从 transcript 自然看到 worker 的问题 → 判 `feed(step)` → 重新 spawn worker（`--resume` 恢复上下文）
- 用户发别的话题 → `decide` 判 `respond(其他人)` → 不影响 worker
- 长时间没人理 → `decide` 在 respond 里顺带提醒「XX 还在等回复」

### 5.5 完成闸门

流结束但 `task_complete` 没调 → `WorkerOutcome(status="not_done")`。

这不是异常——worker 可能问了问题等答案，或者被 V0 短驻 CLI 的时间切断了。Harness 不做任何假设，只记录「还没完成」。

后续怎么处理由 Planner 决定：下次用户回话时判 `feed` → 重新派发。

---

## 6. 多轮对话：反复 decide

```
for round in range(max_rounds):
    state = SessionState.from_session(...)
    decision = Planner.decide(state)

    respond/multi → stream agent → continue  ← 回完继续
    task/feed     → 起 Harness / 重新派发 → return
    done          → return
```

防循环：

| 机制 | 位置 | 说明 |
|------|------|------|
| `already_responded: set[str]` | 循环内 Python set | 确定性防重，同人不选两次 |
| `max_discussion_rounds` | settings（默认 5） | 机械硬上限 |
| LLM 判 done | decide prompt | 主力出口 |

---

## 7. 执行期消息交互

执行态（active_plan 非 None）下用户消息跟纯对话态走**同一个路由**：

```
用户消息 → decide(SessionState)
  │
  ├─ respond(who)   → 闲聊/问进度，即时回复
  ├─ feed(step)     → 某 worker 在等答案，重新派发
  ├─ note(who, txt) → 旁路补充，入 worker 的消息队列，step 边界注入
  ├─ task           → 不应出现（已在执行态），降级 note
  └─ done           → 静默
```

**消息不盲投**：`_pending_notes` 从单队列改为按 worker 分桶：

```python
_pending_notes: dict[str, list[str]]  # key = worker 名 或 "*"

enqueue_note(text, worker="前端小美") → _pending_notes["前端小美"]
enqueue_note(text, worker=None)       → _pending_notes["*"]

# dispatch 时消费
node.pending_notes = (
    _pending_notes.pop("前端小美", [])  # 只取自己的
    + _pending_notes.get("*", [])       # 全局消息
)
```

---

## 8. 完全体场景

```
用户: 帮我做个博客系统，要能发文章
  → decide → task → plan → DAG: A(后端) → B(前端) → C(测试)
  → Orchestrator 后台启动

用户: 后端用 FastAPI 还是 Express？
  → decide → respond(后端阿强)     ← 同一扇门，active_plan 非 None

后端阿强: FastAPI，异步支持好
  → decide → done

──── A 完成，B 开始 ────

前端小美（worker CLI）: "存储方式没定。用 Markdown 还是接 CMS？"
  → 文本推群聊                    ← 不是 ask tool，就是说话
  → 流结束 → not_done            ← 没交卷，不是失败，就是没做完

用户: 你怎么看？
  → decide → feed(B)             ← 从 transcript 自然看到小美在等回复

前端小美 resume: "我倾向 Markdown。继续了。"
  → 继续干活 → task_complete("前端完成") → 验收 → COMPLETED

──── 一切正常 ────

用户: 做得怎么样了？
  → decide → respond(后端阿强)   ← 即时回复，不是 enqueue_note

后端阿强: 后端和前端都完成了，测试在跑。

──── C 完成 ────

用户: @前端小美 加个暗色模式
  → @mention 直达

用户: 帮我加个暗色模式切换
  → decide → task → 新的 DAG     ← 上一轮任务已完成，active_plan 又回到 None
```

**整个过程中**没有出现：
- `if run is not None:` 分支
- PAUSED 状态 / `_feed_event` / 显式 resume
- `ask` tool
- 执行态下群聊死亡
- DiscussionOrchestrator / Selector / CoordinatorGate

---

## 9. 与当前实现的主要差距

| 现在 | 完全体 | 差距 |
|------|--------|------|
| 执行态消息走 `if run is not None: ... return` | 跟纯对话态走同一段 `decide → dispatch` | 步 2c |
| `active_plan` 永远是 None | `active_plan` 是真实 DAG 投影 | 步 2a |
| `has_waiting_step → 盲 feed` | `decide → feed`（Planner 从 transcript 判断） | 步 2c |
| 闲聊 `enqueue_note` → 石沉大海 | `decide → respond` → 即时回复 | 步 2c |
| SessionState 手工构造 | `SessionState.from_session()` 工厂 | 步 2a |
| 多轮讨论死亡（strip） | 反复 decide 接力 | 步 2b |
| `ask` tool + PAUSED 态 + resume 机制 | 删 `ask`，worker 说话走正常的文本流；PAUSED 态删除 | **步 2.5（新）** |
| DiscussionOrchestrator + Selector 残留 | 已删除 | 步 2d |

---

## 10. 关键设计决策

| 决策 | 结论 |
|------|------|
| 大脑数量 | 一个 Planner，两种视野（reactive + deliberate） |
| LLM 调用档位 | 两档：reactive decide（轻）+ deliberate plan（重） |
| 执行引擎统一吗 | 路由层统一；执行引擎不统一（respond 轻 / work 重） |
| 任务有几种状态 | 两种：DONE（COMPLETED）和 NOT DONE（其他所有） |
| 按不按「态」分路由 | 不分。`active_plan` 是 Planner 的输入字段，不是路由分支的条件 |
| Worker 怎么提问 | 正常说话。文本推群聊，跟 respond 路径一样。不需要专用 tool |
| Worker 怎么交卷 | `task_complete(summary)`——唯一结构化信号 |
| Worker 没交卷流就结束了 | `not_done`——不是失败，就是没做完。等 Planner 判 feed 再派 |
| capability 关键词层 | 删除 |
| strip vs keep（多轮） | keep：反复 decide |
| @agent+任务 | 走 respond（显式 @ = 找人聊） |
