# 协调者模块 设计架构

> 日期：2026-06-08 | 取代旧版 overview
> 涵盖：架构分层、路由、执行、状态、当前实现、待做事项

---

## 1. 一句话

群聊里，消息进来 → 一个 Planner 决定该干什么 → 该聊天聊天，该干活干活。聊着聊着可以起任务，任务跑着跑着可以接着聊。没有模式切换，没有状态机膨胀。

---

## 2. 架构：一个大脑 + 一副骨架 + N 只手

```
消息
  │
  ▼
ChatService（前门）
  │  机械反射：@mention / control / broadcast（零 LLM）
  │  其余 →
  │
  ▼
┌─────────────────────────┐
│    Planner（唯一大脑）    │  ← LLM
│                          │
│  reactive: decide(state) │  「下一步干什么」
│  deliberate: plan(ctx)   │  「怎么分解」
│                          │
│  → respond / multi       │  聊天
│  → task                  │  起任务
│  → feed                  │  继续干活
│  → done                  │  静默
└────┬─────────────────┬───┘
     │                 │
  轻执行            重执行
     │                 │
  ┌──▼──────┐   ┌──────▼──────────────┐
  │ respond │   │      Harness        │
  │ 出消息   │   │  （确定性代码）      │
  │ 无验收   │   │  DAG 调度 · 验收闸门 │
  └─────────┘   └──────┬──────────────┘
                       │
                 ┌─────▼──────┐
                 │   Worker   │
                 │ CLI session│
                 │   全工具   │
                 │ 交卷:      │
                 │ task_      │
                 │ complete   │
                 └────────────┘
```

三层职责：

| 层 | 是谁 | 怎么决策 | 管什么 |
|----|------|---------|--------|
| 大脑 Planner | 一个 LLM，两个视野 | LLM 判断 | 路由（聊天/任务/继续/静默）、分解 DAG |
| 骨架 Harness | 确定性代码 | 图论 + 命令 | 按 DAG 顺序调度节点、转移状态、跑验收 |
| 手 Worker | agent CLI | agent 自己判断 | 写代码、读文件、问问题、交卷 |

**Harness 不是大脑**——`compute_frontier` 做的是「遍历 DAG，找出依赖已满足的节点」。跟 `for item in list` 同理，零语义判断。

---

## 3. 核心概念

### 对话是任务的退化，任务是对话的延伸

一次「说话」就是 Planner 规划的一个 1 步 respond。任务就是规划了一个 N 步的 work DAG。同一个大脑，只是视野不同。

| | 聊天 | 干活 |
|---|---|---|
| Planner 视野 | horizon=1，每轮重规划 | horizon=N，规划一次 |
| step 类型 | `respond`（出消息） | `work`（写代码） |
| 什么时候算完 | LLM 觉得聊完了 | worker 调 `task_complete` + 验收通过 |

### 任务只有两种状态

```
DONE        COMPLETED（验收通过）

NOT DONE    PENDING / QUEUED / RUNNING / FAILED / BLOCKED
            写代码、问问题、等回复、卡住了——全是 NOT DONE
```

**没有 PAUSED**。Worker 问「用什么技术栈」跟 worker 在写 `app.py` 没有本质区别——都是在干活，只是前者此刻需要输入才能继续。Harness 不需要区分，只关心一件事：**交卷了没有**。

### 没有模式

`active_plan` 不是「模式开关」。只是 Planner 读到的一个字段——有 DAG 在跑就是 PlanView，没有就是 None。跟 `transcript` 一样，有就有，没有就没有。**ChatService 不知道也不关心现在是什么态**。

---

## 4. 一条消息的旅程

不管群里有任务在跑还是纯聊天，都走同一扇门：

```
ChatService._handle_group
  │
  ├─ @mention     → _stream_one_agent（零 LLM）
  ├─ is_control   → cancel / 忽略（零 LLM）
  ├─ is_broadcast → multi 全员（零 LLM）
  │
  └─ SessionState.from_session(...)
       Planner.decide(state)
       dispatch(decision)
```

### SessionState

```python
@dataclass(frozen=True)
class SessionState:
    transcript: tuple[Message, ...]    # messages 表最近 15 条（含所有 agent）
    members: tuple[Agent, ...]         # 群成员
    active_plan: PlanView | None       # None=纯聊天；非 None=DAG 投影

@dataclass(frozen=True)
class PlanView:
    steps: tuple[StepView, ...]        # 每个节点 (id, worker, status)
```

Read-model，只读投影。不新建可变对象——DAG 变更走 Orchestrator 单写者，transcript 来自 messages 表。

### Planner 怎么判

一次轻 LLM 调用（tool_use），喂 transcript（标注角色） + members（标注能力） + active_plan 状态。

四条判断：

```
transcript 最后一条是用户在跟某个 worker 对话的延续 → feed（让 worker 继续）
用户在闲聊/问进度                                    → respond（找人或自己做答）
用户要写代码/改文件/跑命令                             → task（起 Harness）
不需要任何回应                                        → done
```

`feed` 不依赖 waiting 列表——Planner 从 transcript 的自然对话连续性判断「这条消息是跟谁的对话」。

---

## 5. 任务执行

### 起任务

```
decide → task
  → Planner.plan(ctx)  重 LLM，分解
  → TaskDef[] → build_graph → TaskGraph
  → Orchestrator.run()  fire-and-forget 后台
```

### DAG 调度（确定性）

```python
for _ in range(max_steps):
    ready = select_dispatchable(compute_frontier(graph))
    if ready:
        execute → verify → COMPLETED 或 重试
    else:
        terminal()
```

每一步：排队 → 执行 → 验收 → 完成（或失败重试）。

### Worker 怎么干活

Executor 调 CLI session。Worker 有全部工具（Read/Write/Bash…）。

**唯一的结构化协议**：`task_complete(summary)`。Worker 调这个 → Harness 知道交卷了 → 进验收。

Worker 说话、问问题、讨论——全是正常文本输出。跟对话路径一样，直接推群聊。**不需要专用 tool。** 跟 `Read`/`Write` 一样是普通操作，不触发状态变更。

### 没交卷就结束了

Worker 流结束但没调 `task_complete` → `not_done`。不是失败，就是还没做完。

可能原因：问了问题等回复（V0 短驻 CLI stdin 关了，自然结束）；被时间切断了。Harness 不做假设。后续 Planner 判 `feed` 时重新派发（`--resume` 恢复上下文）。

### Worker 在等人回复时，用户发了别的消息

正常。Worker 不是 PAUSED——她处在 NOT DONE。用户的每条消息照常进 `decide`：

```
用户: 接口文档写好了吗
  → decide → respond(后端阿强)     ← 跟 worker 无关

用户: 用 Markdown
  → decide → feed(前端小美)        ← 这是在跟小美说话

用户: 整体架构改成微服务
  → decide → replan（步4）
```

**卡久了怎么办**：`decide` 从 transcript 自然看到「有人在等、N 轮对话过去了还没人回答」→ 在 respond 里顺带提醒「XX 还在等你的回复」。

---

## 6. 旁路消息

用户执行期发的补充（「注意前端用 React」），decide 判 `note(who=("前端小美",))` → 入 `_pending_notes["前端小美"]`。下次 dispatch 前端 step 时注入 instruction 末尾。

```python
_pending_notes: dict[str, list[str]]  # 按 worker 分桶

enqueue_note(text, worker="前端小美") → _pending_notes["前端小美"]
enqueue_note(text, worker=None)       → _pending_notes["*"]（全局）

# dispatch 时消费
node.pending_notes = (
    _pending_notes.pop("前端小美", [])   # 自己的
    + _pending_notes.get("*", [])        # 全局
)
```

---

## 7. 完全体场景

```
用户: 帮我做个博客系统
  → decide → task → plan → DAG: A(后端) → B(前端) → C(测试)

用户: 后端用 FastAPI 还是 Express？
  → decide → respond(后端阿强)          ← 同一扇门，没有模式切换

后端阿强: FastAPI
  → decide → done
  ──── A 完成，B 开始 ────

前端小美（worker CLI）: 用 Markdown 还是 CMS？
  → 文本推送群聊                        ← 正常说话，不是 ask tool
  → 流结束 → not_done                  ← 没交卷，等回复

用户: 你怎么看？
  → decide → feed(前端小美)            ← 从 transcript 自然看到对话连续性

前端小美 resume: 倾向 Markdown。继续。
  → 继续干活 → task_complete("完成") → 验收 → COMPLETED

──── 一切同时发生 ────

用户: 做得怎么样了？
  → decide → respond(后端阿强)         ← 即时回复，不是石沉大海

后端阿强: 后端和前端都完成了，测试在跑。

用户: 注意前端用 React
  → decide → note(who=("前端小美"))   ← 前端下一个 step 注入

──── C 完成 ────

Orchestrator: 3 个任务，3 完成 → 推群聊
  → active_plan 回到 None             ← 自然回到纯聊天，没有「退出执行态」

用户: @前端小美 加个暗色模式
  → @mention 直达

用户: 帮我加个暗色模式切换
  → decide → task → 新的 DAG          ← 新一轮任务
```

---

## 8. 当前实现状态

| 模块 | 状态 | 说明 |
|------|------|------|
| **前门路由** | ✅ 90% | 纯对话态 decide 单点完成；执行态仍走简化 feed |
| **ReactiveRouter** | ✅ 完成 | respond/multi/task/feed/done 五种 action |
| **SessionState** | ✅ DTO | 手工构造，缺 `from_session` 工厂 |
| **Orchestrator** | ✅ 基础功能 | DAG 调度 + 验收；仍含 PAUSED/`_feed_event`/resume |
| **Executor** | ✅ 基础功能 | task_complete/ask 检测；worker 文本未推群聊 |
| **step-tools MCP** | ✅ 含 ask | 需删 ask tool（步 2.5） |
| **CoordinatorGate** | ✅ 已删 | — |

**残留旧代码待删**：`selector.py`（17KB）、`discussion_orchestrator.py`（12KB）

### 待做

1. **步 2** — 多轮讨论 + SessionState 升级 + 执行态路由收口 + 删 DiscussionOrchestrator/Selector
2. **步 2.5** — 删 ask tool + PAUSED 态 + resume 机制；worker 文本推群聊
3. **步 4** — replan
