# Phase 4 规格 — Executor（派真群成员 Agent 执行）

> 日期：2026-06-06 | 属于：[[coordinator-mvp-implementation-plan]] Phase 4
> 前提：M1 + Phase 2（Verifier）+ Phase 3（Planner）已落地。
> MVP 边界：**串行、无 worktree、硬超时**；复用现有 `build_adapter_for_agent + adapter.stream` 派发路径。

---

## 0. 核心定位（已确认事实）

- **worker = 群成员 Agent**（`group.member_ids` 里的已注册 Agent 实体，非临时进程）。
- **Executor 是代码**（不是 LLM）。内部起 worker 的 CLI session，本身只编排"派发→收流→判结果"。
- **复用现有派发路径**：`build_adapter_for_agent(agent) → adapter.stream(request)`（chat_service / discussion_orchestrator 同款），不新建 CLI 管道。
- **Executor 是 5 协作者里权限最大的**：worker 要**写文件/跑命令**完成任务（不像 Planner 只读、Verifier 只跑验收命令）。

---

## 1. 需求 / 约束 / 边界 / 验收标准

### 1.1 需求（做什么）

`Executor.run(node) -> WorkerOutcome`：
1. 解析 `node.task.suggested_worker`（名）→ Agent 实体
2. 构造**任务执行请求**（指令 + cwd + 工具）
3. `build_adapter_for_agent(agent)` → `adapter.stream(request)`
4. 消费事件流、收集输出、判完成/失败/超时
5. 返回 `WorkerOutcome(ok, output)`

### 1.2 约束

- **串行**：MVP 一次跑一个（并发由 Orchestrator 控，Executor 只管单个）。
- **无 worktree**：worker 直接在 `session.workspace_path` 里改（标准档才隔离 worktree）。
- **硬超时**：单任务墙钟上限（`asyncio.wait_for`），超时杀 session。
- **ok ≠ 成功**：`ok=True` 仅表示"worker 正常跑完产出了结果"，**不代表任务做对了**——对错归 Verifier（命门：worker `ok=True` 但 Verifier 可判 False）。

### 1.3 边界（不做什么）

- 不改 DAG 状态、不验证、不决定调度（Orchestrator 的活）。
- 不解析/判断 worker 产物对错（Verifier 的活）。
- 不构造分解计划（Planner 的活）。
- MVP 不管 worktree 创建/合并（标准档）。

### 1.4 验收标准（Phase 4 算完成）

- `tests/test_executor.py` 全绿（fake adapter 隔离，不起真 CLI）。
- e2e：Orchestrator + 真 Executor(fake adapter) + 真 Verifier 跑任务到 COMPLETED。
- ruff + 类型注解。真 CLI 派发留**手动冒烟**（不进单测）。

---

## 2. 条件 → 动作

| 条件 | 动作 |
|------|------|
| Orchestrator 派发 node（已 RUNNING） | `Executor.run(node)` |
| worker 名能解析到 Agent | 构造请求 → adapter.stream → 收流 |
| 流正常结束（DONE 事件） | `WorkerOutcome(ok=True, output=收集的文本)` |
| 流抛错 / adapter 失败 | `WorkerOutcome(ok=False, output=错误信息)` |
| 超过墙钟上限 | 杀 session → `WorkerOutcome(ok=False, "执行超时")` |
| worker 名解析不到 Agent（race：被删） | `WorkerOutcome(ok=False, "worker 不存在")` |
| worker 触发审批阻断（REQUEST_APPROVAL）| MVP：当失败处理 / 记录（标准档接审批闸门） |

---

## 3. 异常处理

| 异常 | 处理 |
|------|------|
| adapter.stream 抛异常（网络/CLI 崩） | 捕获 → `WorkerOutcome(ok=False, reason)`，**不让异常逃逸到 Orchestrator** |
| 超时（wait_for TimeoutError） | 杀/取消 session（回收，避免僵尸）→ ok=False |
| worker 解析失败 | ok=False（防御性；build_graph 已校验名 ∈ members，此为 race 兜底） |
| worker 输出空 | ok=True 但 output=""——交 Verifier 判（大概率验收失败） |

**统一原则**：Executor **永不抛异常给 Orchestrator**——所有失败都收敛成 `WorkerOutcome(ok=False, reason)`。Orchestrator 靠 ok 走 handle_failure，保持单写者循环不被异常打断。

---

## 4. 禁止项（不允许发生）

| 禁止 | 防线 |
|------|------|
| Executor 改 DAG 状态 | 只返回 WorkerOutcome，无 graph 引用 |
| 异常逃逸打断 Orchestrator 循环 | 全 try/except 收敛成 ok=False |
| 超时 worker 残留（僵尸进程） | 超时必 kill + 回收 |
| worker 越出 workspace 改文件 | MVP：cwd=workspace（标准档 worktree 隔离）⚠️ 见 §9 安全 |
| 把 ok=True 当"任务成功" | 语义明确：ok=正常跑完，成功判定归 Verifier |
| 把 worker 执行流全推聊天刷屏 | 输出路由进任务面板（§见待决 D2） |

---

## 5. 通过 / 不通过 / 成功判定

### 5.1 算"正常跑完"（ok=True）
- 流以 DONE 结束，收集到 output（哪怕空）。

### 5.2 算"未跑完"（ok=False）
- 流抛错 / 超时 / worker 解析失败。

### 5.3 Phase 4 成功判定
- test_executor 全绿（正常完成 / 超时 / 流错 / worker 不存在 / 收集输出）。
- e2e：Orchestrator + Executor(fake) + Verifier 跑通到 COMPLETED。

---

## 6. 代码规范 / 错误处理 / 可测可扩展可观测

### 6.1 规范
- async + 类型注解 + ruff；禁裸 print（logging）；禁同步阻塞（流式 async 消费）。
- `executor.py` 单文件；请求构造抽函数。

### 6.2 错误处理统一
- 所有失败 → `WorkerOutcome(ok=False, reason)`，不抛。
- 记日志：派发的 worker、耗时、ok、失败原因。

### 6.3 可测 / 可扩展 / 可观测

| 维度 | 要求 |
|------|------|
| **可测** | adapter 经接口注入——fake adapter `yield` 预设 StreamEvent（正常/错/慢）；agent 解析注入。**不起真 CLI** |
| **可扩展** | MVP `AgentExecutor`（串行无 worktree）↔ 标准 `WorktreeExecutor`（worktree 隔离），共用 `Executor` Protocol，Orchestrator 不变 |
| **可观测** | 可选 event sink（progress callback）：worker 流事件 → 任务面板/WS（Phase 5 接）。MVP 默认 no-op，仅收集 output |

---

## 7. 数据结构 / 关键字段 / 接口 I/O

### 7.1 输出：WorkerOutcome（已在 ports.py）
```python
@dataclass(frozen=True)
class WorkerOutcome:
    ok: bool        # 正常跑完=True；崩/超时/解析失败=False
    output: str = ""  # worker 最终文本产出（供 fail_reason / final_answer）
```

### 7.2 任务执行请求（复用现有 AgentRequest，但内容是"指令"非"聊天回复"）

| 字段 | 来源（任务执行 vs 现有聊天回复的差异）|
|------|------|
| content/prompt | **TaskDef 指令**（title + description + 约束 + acceptance 提示）——非"回复上一条群聊" |
| working_directory | `session.workspace_path`（标准档：`node.worktree`） |
| available_tools | **worker 的完整工具集**（写/改/跑——worker 要干活，非只读） |
| memory_context | 按需（MVP 可空） |

> 这是**待决 D1**：是新写 `build_task_request(node)` 还是复用 `ContextBuilder.build_for_agent`（后者构造的是聊天回复上下文，语义不符）。倾向**新写**任务执行请求构造器。

### 7.3 接口签名
```python
class AgentExecutor:                       # 实现 Executor Protocol
    def __init__(self, resolve_agent, adapter_factory, workspace, timeout=...): ...
    async def run(self, node: TaskNode) -> WorkerOutcome: ...
```
- `resolve_agent: Callable[[str], Agent | None]`（worker 名 → Agent，注入）
- `adapter_factory: Callable[[Agent], UnifiedAgent]`（= build_adapter_for_agent，注入）

---

## 8. 空值 / 异常值 / 重复值

| 情况 | 处理 |
|------|------|
| worker 名解析为 None | ok=False（race 兜底） |
| worker 输出空 | ok=True，output=""（Verifier 判） |
| 流中无 DONE 事件就断 | ok=False（异常结束） |
| workspace 不存在/不可写 | adapter 启动失败 → ok=False |
| 重复派发同一 node | 不该发生（Orchestrator 串行 + FSM 防重）；Executor 不去重，靠上游 |
| 超长 output | 截断存储（如 200 字符进 fail_reason，全文另存） |

---

## 9. 并发 / 权限 / 状态流转

| 维度 | 规则 |
|------|------|
| **并发** | MVP 串行，Executor.run 单任务；并发由 Orchestrator `select_dispatchable` 控。标准档并行 + worktree |
| **权限** ⚠️ | worker 有**写/执行权限**（要改代码跑命令）——5 协作者里最大。**安全边界**：MVP cwd=workspace（受信项目目录 + 信任 worker Agent 配置）；标准档 worktree 隔离限爆炸半径。落真实环境前复核 |
| **状态流转** | Executor **不碰 FSM**——它返回 WorkerOutcome，Orchestrator 据 ok 走 RUNNING→VERIFYING（ok）或 →FAILED（!ok）。副作用（改文件/跑命令）发生在 worker 进程内 |

---

## 10. 两个待决（实现前定）

| # | 待决 | 倾向 |
|---|------|------|
| **D1 请求构造** | 复用 `build_for_agent`（聊天回复语义）还是新写 `build_task_request`？ | **新写**——任务执行 ≠ 群聊回复，指令/工具/cwd 都不同 |
| **D2 输出路由** | worker 执行流去聊天时间线还是任务面板？ | **任务面板**（per-task，不刷屏）；MVP Executor 只收集 output，事件路由 Phase 5 接 WS |

---

## 11. 实现增量

| 文件 | 动作 |
|------|------|
| `executor.py` | 新建：AgentExecutor + build_task_request + 流消费 + 超时 |
| `tests/test_executor.py` | 新建：fake adapter 各场景 |
| `tests/test_orchestrator.py` | 加 e2e：Orchestrator + AgentExecutor(fake) + MechanicalVerifier |
| `ports.py` | 不动（Executor Protocol 已定义） |

---

## 关联文档

- [[coordinator-mvp-implementation-plan]] Phase 4 概述
- [[coordinator-subsystem-collaborators]] §5.4 Executor / worker=群成员
- [[coordinator-mvp-phase1-orchestrator]] WorkerOutcome / Executor Protocol
- [[coordinator-dag-driven-design-v2]] §5 卡死检测（标准档）/ §7 worktree（标准档）
