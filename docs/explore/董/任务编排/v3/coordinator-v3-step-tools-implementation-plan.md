# Coordinator v3 Step-Tools 实现计划

> 日期：2026-06-07 | 依据：[[coordinator-design-v3]] §11 + [[coordinator-scenario-v3]]
> 原则：TDD（每个 step RED→GREEN→REFACTOR）、每步一个可独立验证的闭合产物、用真实 CLI 验证关键路径（不靠 mock 猜 tool 名）

---

## 目标与范围

**目标**：把 v3 的「step = 有界对话」落成真的——worker 通过 MCP step-tools（task_complete / ask）与 Harness 的结构化协议，替换 v2 的"worker 闷头做 → 流结束 = done"的 fire-and-forget 模式。

**不在本次范围**：
- 前门统一路由（design §9 步1——那是另一条线，不改 Executor/Orchestrator）
- 统一 SessionState（design §9 步2——大重构，独立规划）
- 任务中 replan（design §9 步4——依赖 step 3 完成）

**本次边界**：MCP step-tools server + Executor 终结工具检测 + ask/waiting/feed/resume 完整回路。

---

## 前置知识

### 现有 MCP 注入路径（全部复用，不改）

```
CLI spawn → _write_mcp_config(agent_id, mcp_url)     # claude_code_runtime.py:617
  → tmp json {"mcpServers": {"agenthub-memory": ...}}
  → cmd.extend(["--mcp-config", mcp_path])             # line 419
  → CLI 启动 → SSE connect → POST tool call
  → mcp_memory.py ASGI wrapper 解析 session_id → ContextVar 注入 agent_id
  → tool handler 从 ContextVar 读 agent_id
```

### 现有 tool_use 解析（全部复用，不改）

```
claude_code_runtime._parse_line(line, seq)              # line 498
  → assistant block: type="tool_use" → StreamEvent(
        type=TOOL_CALL,
        tool_call=ToolCall(
            call_id=block["id"],                         # line 538
            name=block["name"],                          # line 539
            arguments=block["input"],                    # line 540
        )
    )
  → user block: type="tool_result" → StreamEvent(
        type=TOOL_RESULT,
        tool_result=ToolResult(call_id=block["tool_use_id"])  # line 581
    )
```

### 现有 Executor（本次主要改动点）

```
executor.py:
  AgentExecutor.__init__(resolve_agent, adapter_factory, session_id, group_id, workspace, timeout, event_sink)
  AgentExecutor.run(node) → WorkerOutcome
  AgentExecutor._consume(adapter, request) → (text, errored, blocked)   # ← 这里加 TOOL_CALL 检测

orchestrator.py:
  Orchestrator.run() → RunResult   # 主循环，加 waiting 分支
  _execute_and_settle(node)         # 结算，加 waiting 分支
```

### 关键不确定项（步 1 做完立刻消除）

**CLI 中 MCP tool 的实际 `name` 字段值**。现有 `_write_mcp_config` 写的是 `{"mcpServers": {"agenthub-memory": {...}}}`，但 `save_memory` 在 stream-json 中的 `name` 字段到底带不带 `mcp__agenthub-memory__` 前缀——现在不确定。**步 1 第一个验证动作就是 spawn CLI 试调 `task_complete`，看 stream-json 中 `name` 的实际值**，然后用这个值修正步 2 的匹配逻辑。

---

## 步 1：MCP Step-Tools Server 骨架 + task_complete 单 tool（~1.5h）

### 目标

新建 `api/mcp_step_tools.py`，仿 `mcp_memory.py` 骨架，暴露一个 `task_complete` tool，可 curl 验证。

### 新建文件

**`src/backend/app/api/mcp_step_tools.py`**

骨架对照 `mcp_memory.py` 逐段抄：

| mcp_memory.py | mcp_step_tools.py |
|---|---|
| `FastMCP("agenthub-memory")` | `FastMCP("agenthub-step-tools")` |
| `_agent_id_ctx` 一个 ContextVar | 三个 ContextVar：`_agent_id_ctx` / `_session_id_ctx` / `_group_id_ctx` |
| `_session_agent_map`（session→agent） | 同上，多存 session_id / group_id |
| SSE wrapper 解析 `?agent_id=` | 解析 `?agent_id=&session_id=&group_id=` |
| POST `/messages/` 只注入 agent_id | 同时注入 session_id / group_id |
| `save_memory` tool（5 参数） | `task_complete(summary: str)` → 写 log + 返回 `{"status": "ok"}` |

**`task_complete` handler 初版（步 1 只打 log，不写 DB）**：

```python
@mcp.tool()
async def task_complete(summary: str) -> dict:
    agent_id_str   = _agent_id_ctx.get()
    session_id_str = _session_id_ctx.get()
    group_id_str   = _group_id_ctx.get()
    logger.info("task_complete agent=%s session=%s summary=%.200s",
                agent_id_str, session_id_str, summary)
    return {"status": "ok", "summary": summary}
```

**`ask` tool 初版（步 1 只定义，不接 handler 逻辑，为步 3 留位置）**：

```python
@mcp.tool()
async def ask(question: str) -> dict:
    # 步 3 实现：写 Message + publish MessageSent + Harness 收 waiting
    raise NotImplementedError("ask 将在步 3 实现")
```

### 改动文件

**`src/backend/app/main.py`**：mount step-tools ASGI app

```python
from app.api.mcp_step_tools import get_mcp_step_tools_asgi
step_tools = get_mcp_step_tools_asgi()
if step_tools:
    app.mount("/mcp/step-tools", step_tools)
```

### 验证（RED → 直接验证，不走 TDD）

```bash
# 1. MCP server 可连接
curl -N "http://localhost:8000/mcp/step-tools/sse?agent_id=<uuid>&session_id=<uuid>&group_id=<uuid>"
# → 返回 SSE 事件，含 session_id

# 2. MCP tool 可调用
# 从 SSE 响应拿到 mcp_session_id，POST tool call：
curl -X POST "http://localhost:8000/mcp/step-tools/messages/?session_id=<mcp_session_id>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"task_complete","arguments":{"summary":"test"}},"id":1}'
# → 返回 {"status": "ok", "summary": "test"}
# → 后端 log 出现 "task_complete agent=... session=... summary=test"

# 3. ⚠️ 最关键：用真实 CLI 看 tool name 长什么样
# 写 --mcp-config 注入 → spawn CLI → 让 worker 调 task_complete →
# 看 stream-json 中 tool_use block 的 name 字段实际值
# 决定步 2 匹配用 "task_complete" / "mcp__agenthub-step-tools__task_complete" / 其他
```

### 产出清单

| 产物 | 文件 | 性质 |
|------|------|------|
| MCP server ASGI app | `api/mcp_step_tools.py` | 新建 |
| FastAPI mount | `main.py` | 改 1 行 |
| tool name 真值 | 验证产出的日志 | 决定步 2 匹配逻辑 |

---

## 步 2：Executor 接 `task_complete` 检测 + 完成闸门（~2.5h）

### 目标

Executor 从 stream-json 检测到 `task_complete` tool_use → WorkerOutcome(status="completed")。两个工具都没调就 DONE → needs_reprompt（打 log + 走现有 FAILED 路径，先不接 resume）。

**不碰 ask/waiting/resume。** 这是最小闭合回路——大多数 step 闷头做完，只走 task_complete。

### TDD 顺序

#### TC-2.1（RED→GREEN）WorkerOutcome 扩展

**文件**：`ports.py`

```python
@dataclass(frozen=True)
class WorkerOutcome:
    ok: bool
    status: Literal["completed","waiting","needs_reprompt","error"] = "completed"
    output: str = ""
    ask: AskInfo | None = None     # 步 3 用，步 2 留 None

@dataclass(frozen=True)
class AskInfo:                     # 步 3 用，步 2 只定义
    question: str
    step_key: str                  # uuid5(session_id, step_id)
```

**测试 `test_executor.py`**：验证 `WorkerOutcome(status="completed")` 可构造、字段默认值正确。

#### TC-2.2（RED→GREEN）build_task_request 注入 step-tools MCP

**文件**：`executor.py` → `build_task_request()`

扩展现有 `AgentRequest` 携带 MCP URL 信息。Executor 已在 `__init__` 持有 `session_id`/`group_id`，需传给 `_write_mcp_config`：

```python
# claude_code_runtime.py _write_mcp_config 扩展
def _write_mcp_config(agent_id: str, mcp_url: str,
                      session_id: str = "", group_id: str = "") -> str | None:
    url = f"{mcp_url}?agent_id={agent_id}"
    if session_id:
        url += f"&session_id={session_id}"
    if group_id:
        url += f"&group_id={group_id}"
    config = {
        "mcpServers": {
            "agenthub-step-tools": {
                "type": "sse",
                "url": url,
            }
        }
    }
    # ... 其余不变
```

**测试**：验证临时 json 文件包含正确的 URL + query params。

#### TC-2.3（RED→GREEN）_consume 检测 task_complete

**文件**：`executor.py` → `_consume()`

现状返回 `tuple[str, str|None, bool]` → 改为返回 `WorkerOutcome`。

```python
async def _consume(self, adapter, request) -> WorkerOutcome:
    chunks: list[str] = []
    errored: str | None = None
    done_summary: str | None = None     # 新增
    saw_terminator = False               # 新增

    async for evt in adapter.stream(request):
        if evt.type == TOOL_CALL and evt.tool_call:
            name = evt.tool_call.name
            if name == "<步1确认的实际值>":           # 如 "mcp__agenthub-step-tools__task_complete"
                done_summary = evt.tool_call.arguments.get("summary", "")
                saw_terminator = True
            # 非 step-tools 的 TOOL_CALL（Read/Bash/Write/Grep）→ 忽略
        elif evt.type == TEXT and evt.content:
            chunks.append(evt.content)
        elif evt.type == ERROR:
            errored = evt.content

    if errored:
        return WorkerOutcome(ok=False, status="error", output=errored)
    if done_summary is not None:
        return WorkerOutcome(ok=True, status="completed", output=done_summary)
    # 两个终结工具都没调
    return WorkerOutcome(ok=False, status="needs_reprompt",
                         output="未调用 task_complete 或 ask 终结工具")
```

**测试 `test_executor.py`**：
- Fake adapter 产出一个含 `task_complete` TOOL_CALL 的流 → `WorkerOutcome(status="completed")`
- Fake adapter 产出不含终结 TOOL_CALL 的流 → `WorkerOutcome(status="needs_reprompt")`
- Fake adapter 产出 `Read`/`Bash` TOOL_CALL（非 step-tools）→ 忽略，看最终是否 needs_reprompt

#### TC-2.4（RED→GREEN）_execute_and_settle 处理 needs_reprompt

**文件**：`orchestrator.py` → `_execute_and_settle()`

```python
outcome = await self._executor.run(node)
if not outcome.ok:
    if outcome.status == "needs_reprompt":
        # 步 2：只打 log + 走 FAILED（先不 resume）
        logger.warning("step %s worker 未调用终结工具，视为 FAILED", node.task.id)
        self._handle_failure(node, "worker 未调用 task_complete 或 ask")
        await self._emit_update(node, "failed", node.fail_reason)
        return
    # 现有 error 路径不变
    self._handle_failure(node, "worker 自身失败/超时")
    ...
```

> **步 3 会把 `needs_reprompt` 升级为真正的 resume 追一刀**。步 2 只验证链路的"检测"端——MCP server 给了 tool → CLI 调了 tool → Executor 检测到了。

#### TC-2.5（集成验证）用真实 CLI 跑一个简单 step

```
step: "在 /tmp/test_step2.txt 写入 'hello v3'"
→ worker spawn → 读完环境 → Write 工具写文件
→ 调 task_complete(summary="已在 /tmp/test_step2.txt 写入 hello v3")
→ Executor 检测到 → WorkerOutcome(status="completed")
→ Orchestrator 正常结算 → COMPLETED
```

**这是步 2 的真检验**——MCP ↔ CLI ↔ Executor 全链路通了。

### 产出清单

| 产物 | 文件 | TC |
|------|------|-----|
| WorkerOutcome 扩展 | `ports.py` | TC-2.1 |
| _write_mcp_config 多传 query params | `claude_code_runtime.py` | TC-2.2 |
| build_task_instruction 加 task_complete 合约 | `executor.py` | (内联) |
| _consume TOOL_CALL 检测 + 完成闸门 | `executor.py` | TC-2.3 |
| _execute_and_settle needs_reprompt 分支 | `orchestrator.py` | TC-2.4 |
| 真实 CLI 集成验证 | 手动 | TC-2.5 |

---

## 步 3：ask + waiting + feed + resume 完整回路（~4h）

### 目标

步 2 验证了"调 task_complete → completed"链路。步 3 接上"调 ask → waiting → 群里问答 → feed → resume → task_complete"的完整闭环。

### 3a：mcp_step_tools.py — ask tool 真实现（~1h）

**改动**：`mcp_step_tools.py` → `ask` handler 从 `raise NotImplementedError` 改为真正写消息：

```python
@mcp.tool()
async def ask(question: str) -> dict:
    agent_id   = UUID(_agent_id_ctx.get())
    session_id = UUID(_session_id_ctx.get())
    group_id   = UUID(_group_id_ctx.get())

    # 落 DB + 广播（仿 post_system_background，coordinator_run.py:198）
    msg = Message(
        session_id=session_id,
        role=MessageRole.ASSISTANT,
        sender_agent_id=agent_id,
        content=f"❓ {question}",
    )
    async with session_factory() as db:
        await PostgresMessageRepository(db).save(msg)
        await db.commit()
    await get_event_bus().publish(
        MessageSent(session_id=session_id, message_id=msg.id,
                    role="assistant", sender_agent_id=str(agent_id),
                    content_type="text")
    )
    logger.info("ask agent=%s session=%s question=%.200s", agent_id, session_id, question)
    return {"status": "ok", "question": question}
```

> **不需要投送逻辑**。ask 就是群里一条 agent 消息——DB write + EventBus.publish + WS broadcast 全覆盖。回复的路由是 Planner 的事，不是 MCP tool 的事（见 scenario §4.2）。

### 3b：Executor._consume — 加 ask 检测（~0.5h）

```python
ask_q: str | None = None    # 在变量声明区新增

async for evt in adapter.stream(request):
    if evt.type == TOOL_CALL and evt.tool_call:
        name = evt.tool_call.name
        if name == TASK_COMPLETE_NAME:
            done_summary = evt.tool_call.arguments.get("summary", "")
            saw_terminator = True
        elif name == ASK_NAME:                                 # 新增
            ask_q = evt.tool_call.arguments.get("question", "") # 新增
            saw_terminator = True                               # 新增
    # ...

# DONE 后判定：
if ask_q is not None:
    step_key = str(uuid5(request.session_id, node.task.id))  # step 级隔离
    return WorkerOutcome(ok=True, status="waiting",
                         ask=AskInfo(question=ask_q, step_key=step_key))
```

### 3c：Orchestrator._execute_and_settle — waiting 分支（~1h）

```python
async def _execute_and_settle(self, node: TaskNode) -> None:
    self._transition(node, TaskStatus.QUEUED)
    self._transition(node, TaskStatus.RUNNING)
    node.worker = node.task.suggested_worker
    node.step_key = str(uuid5(self._session_id, node.task.id))  # 新增字段
    await self._emit_update(node, "running")

    outcome = await self._executor.run(node)

    if outcome.status == "waiting":                         # ── 新增分支 ──
        node.dispatch_count += 1
        if node.dispatch_count > MAX_DISPATCH:
            self._handle_failure(node, f"step 对话轮次超限（>{MAX_DISPATCH}）")
            await self._emit_update(node, "failed", node.fail_reason)
            return
        # node.status 保持 RUNNING！不进 VERIFYING
        await self._post_ask_to_group(node, outcome.ask.question)
        # 挂起，等外部 feed 信号唤醒（步 3d）
        return                                                  # ── 新增分支结束 ──

    # 现有 ok/error/needs_reprompt 路径不变
    if not outcome.ok:
        if outcome.status == "needs_reprompt":
            # 步 3 升级：真正的 resume 追一刀
            ...
        ...
```

`_post_ask_to_group` 落地：但消息**已经被 MCP tool handler 在 CLI 进程内写过了**——`ask` tool handler 在自己进程里调了 `Message.save()` + `publish()`。Harness 不需要再写一遍。这意味着：

> **关键发现**：`_post_ask_to_group` 可能是个 no-op——消息已经通过 MCP tool handler 的 Sidecar Effect 写入了。Harness 只需要：确认 `ask` 发生了、记录 `step_key`、挂起等 feed。不对，MCP tool handler 的 DB write 发生在和 WS handler 不同的 DB session 中，需要通过 EventBus 跨 session 通知。

实际问题：MCP server handler 用的 `session_factory()` 是和主请求不同的 PG session，消息落库后 commit。EventBus（InMemoryEventBus）是进程内的，跨 DB session 可见。但 `ws_manager.broadcast` 会推给所有连接的客户端。这条链路和 `post_system_background` 完全一样（coordinator_run.py:198），已验证通过。

**所以 `_post_ask_to_group` 不需要额外做什么**——ask tool handler 已经做了 DB write + EventBus publish + WS broadcast。Harness 这边只记录 step_key + dispatch_count + 保持 RUNNING，然后挂起。

### 3d：CoordinatorRun.feed() — 唤醒挂起的 run（~1h）

这是步 3 最棘手的部分——把现有串行 `for _ in range(max_steps)` 的主循环改成能接收外部信号。

**方案：asyncio.Event**

```python
# Orchestrator 新增属性
self._feed_event: asyncio.Event = asyncio.Event()
self._pending_feed: dict[str, str] = {}  # step_id → answer

def feed(self, step_id: str, answer: str) -> None:
    """外部调用：喂答案给 waiting step。"""
    self._pending_feed[step_id] = answer
    self._feed_event.set()

# 主循环改造
async def run(self) -> RunResult:
    # ... plan + build_graph ...
    for _ in range(max_steps):
        self._propagate_blocked()
        ready = select_dispatchable(...)
        if not ready:
            return await self._terminal()

        node_key = ready[0]
        node = self.graph.nodes[node_key]

        # 如果该节点处于 waiting 且有 pending feed → resume
        if node.status == TaskStatus.RUNNING and node.dispatch_count > 0:
            # resume dispatch（不是首次）
            answer = self._pending_feed.pop(node_key, None)
            if answer is None:
                # 节点在 waiting 但没收到 feed → 挂起等信号
                self._feed_event.clear()
                await self._feed_event.wait()   # 阻塞直到 feed() 被调
                continue                          # 重新循环，这次 pending_feed 有值
            await self._resume_and_settle(node, answer)
        else:
            await self._execute_and_settle(node)
    return RunResult(ExitReason.BUDGET_EXCEEDED, self._build_summary())

async def _resume_and_settle(self, node, answer):
    """二次派发：复用 Executor.run(node)，但注入答案 + has_history=True + --resume"""
    # 更新 request 的 instruction 注入答案
    # session_key 复用 node.step_key
    # has_history=True → CLI 走 --resume（自动加载上次全上下文）
    outcome = await self._executor.run(node)    # 同样的接口！
    # 正常结算（同 _execute_and_settle 的 completed/error 分支）
```

### 3e：Planner.decide — active_plan 非空时路由 feed（~0.5h）

这是唯一需要碰 Planner 的地方——但不是新增 LLM 调用，是在现有 `decide` 逻辑里加分支：

```
Planner.decide(SessionState):
  active_plan 非空:
    上一条 agent 消息是 ask（sender_agent_id 对应的 step 在 waiting）
    当前用户消息是自然语言回答（非 control）
    → PlannerDecision(action="feed", feed_step=<waiting_step_id>, answer=<用户消息>)
```

> **注意**：这一步依赖 design §9 步 1（统一路由器）把 `Planner.decide` 建好。如果步 1 还没落地，步 3d 可以暂时用简化路由代替——"任何用户消息直接 feed 给第一个 waiting 的 step"（单 step waiting 场景可用，多 step 同时 waiting 才需要 Planner 分辨）。

### TC-3 系列测试

| TC | 内容 | 类型 |
|----|------|------|
| TC-3.1 | `mcp_step_tools.ask` handler 写 DB + publish + log | 单元（fake DB/fake bus） |
| TC-3.2 | `_consume` 检测 ask TOOL_CALL → WorkerOutcome(waiting) | 单元（fake adapter 流） |
| TC-3.3 | `_execute_and_settle` waiting 分支：保持 RUNNING + dispatch_count++ | 单元（mock executor） |
| TC-3.4 | `dispatch_count > 3` → FAILED | 单元 |
| TC-3.5 | `CoordinatorRun.feed("B","answer")` → resume dispatch → completed | 集成（fake adapter） |
| TC-3.6 | 完整场景：ask → waiting → feed → resume → task_complete → COMPLETED | 集成（真实 CLI） |

### 产出清单

| 产物 | 文件 | TC |
|------|------|-----|
| ask tool handler 真实现 | `mcp_step_tools.py` | TC-3.1 |
| Executor ask 检测 | `executor.py` | TC-3.2 |
| _execute_and_settle waiting 分支 + 预算 | `orchestrator.py` | TC-3.3, TC-3.4 |
| TaskNode.step_key / dispatch_count | `dag.py` | (字段) |
| CoordinatorRun.feed() + run 循环挂起/唤醒 | `coordinator_run.py` + `orchestrator.py` | TC-3.5 |
| Planner.decide feed 路由 | `planner` | (依赖 design §9 步 1) |
| step instruction 加 ask 协议 | `executor.py` | (内联) |
| 完整场景集成验证 | 手动 | TC-3.6 |

---

## 步 3 的两个简化策略（如果 run 循环改造太难）

v3 design §11.3 留了「MVP 多轮 `--resume`」的后路——每次 ask 后 CLI 退出，resume 时重新 spawn。这意味着**不用改 run 循环挂起/唤醒逻辑**：

```
Turn1: spawn CLI → worker 调 ask → _consume 返回 waiting → step 保持 RUNNING
       → run 循环自然结束本轮 → 下一轮 ready=[]（B 在 RUNNING 但不完成也没 FAIL）
       → _terminal()? 不——需要新的终止条件："有 waiting step → 不终止，等外部信号"

Turn2: 用户回答 → feed 信号 → resume dispatch（和 Turn1 同一个 session_key + --resume）
```

这比改主循环的 asyncio.Event 方案简单——**只需要一个「有 waiting step 时不终止」的判定 + feed 触发下一轮循环」。但代价是 spawn 延迟（每次 resume 重新启动 CLI 进程 ~2-3s）。

选择策略：
- **如果 design §9 步 2（统一循环）还没做** → 用 MVP 多轮方案，不改主循环结构
- **如果步 2 已完成、有共享循环抽象** → 用 asyncio.Event 方案，改一次到位

---

## 风险清单

| 风险 | 影响 | 缓解 |
|------|------|------|
| CLI 中 MCP tool name 带的前缀不确定 | 步 2 匹配逻辑写死会炸 | 步 1 第一个验证动作就是真 CLI 看值 |
| `--mcp-config` flag 在当前 CLI 版本名不同 | CLI spawn 时 MCP 没注进去 | 步 1 curl 先验证 MCP server 独立可用；若 flag 名不同则修正 |
| MCP SSE 连接在 CLI 子进程内网络不通 | tool call 发不出去 | 步 1 用 CLI 真调一次确认通 |
| `task_complete` 调了但 summary 为空 | 验收阶段无内容可判 | task_complete 加 `summary` 必填校验（MCP tool 层） |
| worker 在文本里问完问题不调 ask，继续往下干 | 闷头推进基于错误假设 | 无协议可强制；system prompt 降频 + 验收兜底（design §11.3 残余风险） |
| resume 时上下文丢失 | worker 忘记之前干了什么 | session_key = uuid5(S, step_id) 保证同 key；`--resume` 从 session 文件恢复 |
| 多个 step 同时 waiting，feed 错配 | 答案发给错的 step | 简化策略：MVP 只允许一个 ask（`max_concurrency=1` + ask 时 block 其他派发）；未来靠 Planner 路由分辨 |

---

## 文件改动总览

```
新建:
  src/backend/app/api/mcp_step_tools.py        # MCP server (task_complete + ask)
  src/backend/tests/test_mcp_step_tools.py     # MCP handler 测试

改动:
  src/backend/app/main.py                       # + mount step-tools ASGI
  src/backend/app/domain/task_engine/ports.py   # WorkerOutcome + AskInfo
  src/backend/app/domain/task_engine/dag.py     # TaskNode + step_key/dispatch_count
  src/backend/app/domain/task_engine/executor.py # _consume TOOL_CALL 检测
  src/backend/app/domain/task_engine/orchestrator.py # waiting/feed/resume 分支
  src/backend/app/infrastructure/llm/claude_code_runtime.py # _write_mcp_config 多传 query params
  src/backend/app/application/services/coordinator_run.py  # CoordinatorRun.feed()
  src/backend/tests/test_executor.py            # TC-2.3/TC-3.2
  src/backend/tests/test_orchestrator.py        # TC-2.4/TC-3.3-3.5

不改（复用）:
  src/backend/app/domain/task_engine/scheduler.py  # compute_frontier/select_dispatchable 不动
  src/backend/app/domain/task_engine/fsm.py         # TaskFSM 不动
  src/backend/app/domain/task_engine/dag.py         # build_graph/校验 不动
  src/backend/app/domain/task_engine/verifier.py    # MechanicalVerifier 不动
  src/backend/app/domain/llm/protocol.py            # StreamEvent/ToolCall 不动（已有 name 字段）
  src/backend/app/api/ws/chat.py                    # WS handler 不动
  src/backend/app/api/mcp_memory.py                 # 参考模板，不修改
  src/backend/app/core/events.py                    # EventBus 不动
  src/backend/app/infrastructure/ws/connection_manager.py  # ws_manager 不动
```
