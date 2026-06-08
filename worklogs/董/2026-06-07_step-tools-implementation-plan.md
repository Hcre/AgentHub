# Step Tools 分步实施计划 — MCP Server + Executor + Orchestrator 集成

> 日期：2026-06-07 | 状态：设计定稿，待实施
> 关联：[[coordinator-design-v3]] §9 步 3 + §11.3 MVP 档
> 前置：`_write_mcp_config` 已支持多 MCP server（`claude_code_runtime.py:617`），`mcp_memory.py` 骨架可直接抄

## 总体策略：三步，每步可独立验证

这条链路有 5 个组件互相咬合（MCP server → CLI --mcp-config → stream-json tool_use → Executor._consume → Orchestrator run 循环），但只有两个真正的验证点（MCP 通不通、Executor 检测对不对）。一步到位 = 把所有不确定性同时引爆，debug 时不知道是 MCP server 没收到、tool_use 没解析对、还是 resume 上下文丢了。

每步产物可独立跑，不依赖下一步。

---

## 关键前置（步 1 完成后、步 2 前）：用真实 CLI 确认 tool name

`--mcp-config` 注入的 MCP tool，CLI stream-json 里实际 `name` 字段长什么样，**现在不确定**。

- `save_memory` 在 mcp_memory.py 里注册时叫 `save_memory`（`@mcp.tool()` 装饰器）
- 但 `_write_mcp_config` 写的 server key 是 `"agenthub-memory"`
- CLI 可能给 tool name 加 `mcp__<server>__` 前缀，也可能不加

**步 1 做完后立即验证**：spawn 一个真实 CLI，用 `--mcp-config` 指向 step-tools server，让 worker 调 `task_complete`，看 `stream-json` 输出里 `tool_use` 事件的 `name` 实际值。这个信息决定步 2 `_consume` 的匹配逻辑怎么写。**别猜。**

---

## 步 1：MCP Server 骨架 + 单 tool（预计 1-2 小时）

### 范围

只做 `task_complete`，不做 `ask`。不碰 Executor/Orchestrator。纯新文件，零风险。

### 产物

**新文件 `src/backend/app/api/mcp_step_tools.py`**（仿 `mcp_memory.py`）：

```
FastMCP("agenthub-step-tools")
暴露 task_complete(summary: str) → 写 log + 返回 {"status": "ok"}
ASGI wrapper (_AgentMCPWrapper) 解析 ?agent_id=&session_id=&group_id=
三个 ContextVar: _agent_id_ctx / _session_id_ctx / _group_id_ctx
mount 到 FastAPI app: app.mount("/api/mcp/step-tools", ...)
```

### 骨架来源

直接抄 `mcp_memory.py`（`src/backend/app/api/mcp_memory.py`）的 `_AgentMCPWrapper`：

| mcp_memory.py | mcp_step_tools.py 改动 |
|---|---|
| `_agent_id_ctx` 1 个 ContextVar | 加 `_session_id_ctx`、`_group_id_ctx`，共 3 个 |
| SSE URL 只解析 `?agent_id=` | 多解析 `&session_id=&group_id=` 两个 query param |
| `FastMCP("agenthub-memory")` | `FastMCP("agenthub-step-tools")` |
| `save_memory` tool | `task_complete(summary: str)` 只写 log |
| `get_mcp_asgi()` 返回 wrapper | 同名函数，mount 到 `/api/mcp/step-tools` |

### main.py 改动

```python
# 在 mcp_memory 的 import 之后加：
from app.api.mcp_step_tools import get_mcp_asgi as get_step_tools_asgi

# 在 mcp_memory mount 之后加：
_step_asgi = get_step_tools_asgi()
if _step_asgi is not None:
    app.mount("/api/mcp/step-tools", _step_asgi)
```

### 验证

```bash
# Terminal 1: 启动后端
.venv/bin/uvicorn app.main:app --reload

# Terminal 2: curl 验证 SSE 连接建立 + tool 调用
curl -N -X GET "http://localhost:8000/api/mcp/step-tools/sse?agent_id=<uuid>&session_id=<uuid>&group_id=<uuid>"
# → 应收到 SSE 事件含 session_id

# 然后用该 session_id POST tool 调用
curl -X POST "http://localhost:8000/api/mcp/step-tools/messages/?session_id=<sid>" \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/call","params":{"name":"task_complete","arguments":{"summary":"test"}}}'
# → 后端 log 应出现 "task_complete OK agent=... session=... group=..."
```

### 风险：零

纯新文件，不碰任何现有代码。MCP 包可选（`try/except ImportError`），未安装时 mount 跳过。

---

## 步 2：Executor 接上 task_complete 检测（预计 2-3 小时）

### 范围

只接 `task_complete`，不做 `ask`/waiting/resume。最小闭合回路——MCP server ↔ CLI ↔ Executor 全链路通了。

### 产物

#### 2a. `_write_mcp_config` 同时注入 step-tools

**文件**：`src/backend/app/infrastructure/llm/claude_code_runtime.py:617`

现有 `_write_mcp_config` 只写一个 MCP server（`agenthub-memory`）。需要加第二个：

```python
config = {
    "mcpServers": {
        "agenthub-memory": {
            "type": "sse",
            "url": f"{mcp_url}?agent_id={agent_id}",
        },
        "agenthub-step-tools": {                    # 新增
            "type": "sse",
            "url": f"{step_tools_url}?agent_id={agent_id}&session_id={session_id}&group_id={group_id}",
        }
    }
}
```

函数签名加 `session_id` 和 `group_id` 参数，调用方（`claude_code_runtime.py` 内 spawn CLI 处）传入。

#### 2b. WorkerOutcome 加 status 字段

**文件**：`src/backend/app/domain/task_engine/ports.py:29`

```python
@dataclass(frozen=True)
class WorkerOutcome:
    ok: bool
    output: str = ""
    status: str = "completed"  # 新增: "completed" | "needs_reprompt"
```

现有 `ok=True/False` 路径不变。`status` 区分"真完成"和"看起来完成了但没调终结工具"。

#### 2c. Executor._consume 加 TOOL_CALL 检测

**文件**：`src/backend/app/domain/task_engine/executor.py:119`

现有 `_consume` 已解析 `StreamEventType.TOOL_CALL`（`protocol.py:50`），`ToolCall` 有 `name` 字段（`protocol.py:59-62`）。只需在事件循环中新增：

```python
# 在 _consume 的 for 循环中，现有 TEXT/ERROR/REQUEST_APPROVAL 分支之后：
elif evt.type == StreamEventType.TOOL_CALL and evt.tool_call is not None:
    name = evt.tool_call.name
    if "task_complete" in name:         # 模糊匹配，容前缀
        completed = True
        task_summary = evt.tool_call.arguments.get("summary", "")
    # else: 非 step-tools 的 TOOL_CALL → 忽略（原生 Read/Write/Bash 等）
```

返回值从 `tuple[str, str | None, bool]` 扩展为包含 completed flag + task_summary。

对应 `run()` 中：
- `task_complete` 检测到 → `WorkerOutcome(ok=True, status="completed", output=summary)`
- 两个终结工具都没调 → `WorkerOutcome(ok=True, status="needs_reprompt")`（先只打 log + 让 step 走现有 FAILED 路径）

#### 2d. build_task_instruction 加协议合约

**文件**：`src/backend/app/domain/task_engine/executor.py:37`

```python
def build_task_instruction(node: TaskNode) -> str:
    # 现有逻辑...
    parts.append(
        "## 协议\n"
        "完成后必须调用 task_complete(summary) 工具。"
        "summary 写：做了什么、产物在哪、关键决策。"
    )
```

### 验证

用真实 CLI 跑一个简单 step（如"在 /tmp 建一个 test.txt 写 hello"）：

- worker 调了 `task_complete` → `_consume` 检测到 → `WorkerOutcome(status="completed")` → Orchestrator 正常走 VERIFYING → COMPLETED
- worker 没调 → `WorkerOutcome(status="needs_reprompt")` → log 警告 → step 走 FAILED（暂不 resume）

### 风险

| 风险 | 缓解 |
|------|------|
| tool name 前缀不确定 | 步 1 后用真实 CLI 验证（见"关键前置"），匹配用 `"task_complete" in name` 容前缀 |
| WorkerOutcome 改 contract 导致现有 step 炸 | 只加字段，`ok=True/False` 路径不变；现有代码不读 `status` |
| `_write_mcp_config` 调用方多 | 先 grep 所有调用点，逐个传参 |

---

## 步 3：ask + waiting + feed + resume（预计 3-4 小时）

### 范围

最后接上完整的 step 内对话回路。这是唯一需要改 Orchestrator.run() 主循环的地方，也是 design §9 标"大"的那块。

### 产物

#### 3a. mcp_step_tools.py 加 ask tool

```python
@mcp.tool()
async def ask(question: str) -> dict:
    """向群组提问，等待回答后继续。"""
    # MVP: 只写 log + 返回确认
    # 标准档: 长轮询等待答案
    logger.info("ask agent=%s session=%s question=%s", ...)
    return {"status": "asked", "question": question}
```

#### 3b. WorkerOutcome 加 AskInfo

**文件**：`ports.py`

```python
@dataclass(frozen=True)
class AskInfo:
    question: str
    call_id: str = ""

@dataclass(frozen=True)
class WorkerOutcome:
    ok: bool
    output: str = ""
    status: str = "completed"  # "completed" | "waiting" | "needs_reprompt"
    ask: AskInfo | None = None
```

#### 3c. Executor._consume ask 检测

```python
elif "ask" in name:
    ask_info = AskInfo(
        question=evt.tool_call.arguments.get("question", ""),
        call_id=evt.tool_call.call_id,
    )
    # 继续读流到 DONE
```

`run()` 中：`ask` 检测到 → `WorkerOutcome(status="waiting", ask=ask_info)`

#### 3d. Orchestrator._execute_and_settle waiting 分支

**文件**：`orchestrator.py:73`

```
_execute_and_settle(node):
    outcome = await executor.run(node)
    
    if outcome.status == "waiting":
        node.step_key = session_key   # 保存以便 resume
        node.ask_info = outcome.ask
        # step 保持 RUNNING，不调 _handle_failure
        # 把 ask.question 发到群里（_post_ask_to_group）
        return  # 不碰 DAG，其他就绪节点照派
    
    if outcome.status == "completed":
        # 现有逻辑：→ VERIFYING → COMPLETED
    
    if outcome.status == "needs_reprompt":
        # 步 3 真正实现 resume 追一刀
        if node.dispatch_count < MAX_DISPATCH:
            node.dispatch_count += 1
            # 调度一次 re-dispatch（has_history=True, --resume）
            # instruction 加 "你结束了但没调 task_complete 或 ask。请调用对应工具。"
        else:
            self._handle_failure(node, "step 预算耗尽（未调终结工具）")
```

#### 3e. CoordinatorRun.feed() + Orchestrator resume dispatch

**文件**：`coordinator_run.py`

```python
class CoordinatorRun:
    async def feed(self, step_id: str, answer: str) -> None:
        """向正在 waiting 的 step 注入用户回答。"""
        # 查找 node，重新 dispatch（has_history=True, --resume）
```

#### 3f. Planner 路由区分 ask-answer / modification

在 Planner.decide() 中：`active_plan` 非空 + 上一条是某 step 的 ask → 判 feed（不是新任务、不是 modification）。

#### 3g. L2 验收反向网

即便调了 `task_complete`，验收闸门核 summary + 实际 artifact：
- summary 像问句 → 打回 RUNNING
- 无产物 / 验收标准未达 → 打回 RUNNING

### 验证

真实多轮场景：前端小美 ask → 用户回答 → resume → task_complete → 验收通过。

---

## 为什么不能一步到位

| 一步到位的风险 | 分步怎么消解 |
|---|---|
| MCP 没注进去 vs Executor 没解析到 → 分不清 | 步 1 curl 验证 MCP server 独立可用 |
| tool_use name 不对（`mcp__step-tools__task_complete` 前缀不确定） | 步 1 后跑真实 CLI 看 name 实际值 |
| WorkerOutcome 改 contract 导致现有 step 全部炸 | 步 2 只加字段不改现有逻辑，ok=True/False 路径不变 |
| resume 上下文丢了 debug 时要同时排查 MCP + session_key + has_history | 步 3 时前三层已确认正确，排查范围缩到 run 循环挂起/唤醒 |

## 每一步产物都是可跑的

- **步 1** = MCP server 可 curl 验证（独立进程）
- **步 2** = 简单 step 走 `task_complete` 正常完成（大多数 step 的行为），ask/resume 暂不支持但闭环
- **步 3** = 完整回路，多轮 ask→resume→complete

没有一步是"搭了一半等下一步才能用的脚手架"。

---

## 涉及文件清单

| 文件 | 步 1 | 步 2 | 步 3 |
|------|:---:|:---:|:---:|
| `src/backend/app/api/mcp_step_tools.py` | **新建** | — | 加 ask tool |
| `src/backend/app/main.py` | mount | — | — |
| `src/backend/app/infrastructure/llm/claude_code_runtime.py` | — | 改 `_write_mcp_config` | — |
| `src/backend/app/domain/task_engine/ports.py` | — | `WorkerOutcome` 加 status | 加 `AskInfo` |
| `src/backend/app/domain/task_engine/executor.py` | — | `_consume` 加工具检测 + `build_task_instruction` | ask 检测 + resume 追一刀 |
| `src/backend/app/domain/task_engine/orchestrator.py` | — | — | `_execute_and_settle` waiting 分支 + 完成闸门 |
| `src/backend/app/application/services/coordinator_run.py` | — | — | `feed()` + resume dispatch |
