# Coordinator MVP 实现方案

> 日期：2026-06-05 | 范围：§14.1 MVP（串行）| 基于：[[coordinator-subsystem-collaborators]] + [[coordinator-test-plan]]
> 原则：TDD（每相 RED→GREEN）、每相一个可独立交付的纵切、用 fake 隔离 LLM/CLI

---

## 目标与范围

**目标**：让 5 协作者子系统在**串行 MVP** 下端到端跑通——Planner 分解 → Orchestrator 调度 → Executor 执行 → Verifier 验收 → 完成。

**MVP 边界（§14.1）**：
- 串行（并发=1），**无 worktree**、**无事件总线**（串行 await 循环即可）
- Planner：种子单次 `chat_structured`，**不读文件**（方案① tool 循环是标准档，§6.9）
- Verifier：只机械检查（无 reviewer、无集成闸门）
- Executor：派一个 worker、等、硬超时；卡死检测只硬超时
- 失败：retry，耗尽 → 退出问人（无 LLM replan）

---

## 已建（复用，不重写）

| 文件 | 内容 | 测试 |
|------|------|------|
| `dag.py` | TaskDef/Check/TaskNode/TaskGraph/build_graph/校验 | test_dag (8) |
| `scheduler.py` | compute_frontier/unreachable_pending/select_dispatchable | test_scheduler (10) |
| `fsm.py` | VALID_TRANSITIONS/TaskFSM | test_fsm (18) |

= Scheduler + 状态模型（Harness 控制面的纯逻辑层）。**36 passed, ruff clean。**

## 待清理（旧骨架，相应相里删）

- `coordinator.py`（索引式 stub）→ Phase 3 用 `planner.py` 取代
- `harness.py`（索引式 PlannedTask）→ Phase 2 拆成 `verifier.py` 等，旧文件删

---

## 实现顺序（脊柱优先）

```
Phase 0 Ports        ← 可测前提，解锁全部
   ↓
Phase 1 Orchestrator ← 脊柱：用 fake 把已建的 scheduler/fsm 串成完整循环
   ↓                    （此刻"架构能跑"已证明）
Phase 2 Verifier(真) ← 换掉 fake：机械验收，含 TC-4.1 命门
Phase 3 Planner(真)  ← 换掉 fake：种子 + chat_structured 出 DAG
Phase 4 Executor(真) ← 换掉 fake：派真 worker CLI
Phase 5 接线         ← Selector decompose → spawn Orchestrator
```

**里程碑 M1 = Phase 0+1**：Orchestrator 用 fake 协作者把一个 mock DAG 跑到 completed。这一刻整个控制面（调度+FSM+循环+退出）已验证。之后每相只是把一个 fake 换成真实现。

---

## Phase 0 — Ports & DTOs（§0 可测接缝）

**目标**：定义协作者接口 + DTO + fake，解锁 Orchestrator 测试。

**新建 `ports.py`**：
```python
@dataclass(frozen=True)
class Verdict:        passed: bool; reason: str = ""
@dataclass(frozen=True)
class WorkerOutcome:  ok: bool; output: str = ""      # ok=False=worker 自身崩/超时
class ExitReason(StrEnum):  COMPLETED; FAILED; UNREACHABLE; BUDGET_EXCEEDED
@dataclass
class RunResult:      reason: ExitReason; summary: str = ""
@dataclass
class PlanContext:    task: str; agents: list; repo_tree: str; ...   # 种子

class Planner(Protocol):
    async def plan(self, ctx: PlanContext) -> list[TaskDef]: ...
    async def final_answer(self, graph: TaskGraph) -> str: ...
class Executor(Protocol):
    async def run(self, node: TaskNode) -> WorkerOutcome: ...
class Verifier(Protocol):
    async def verify(self, node: TaskNode) -> Verdict: ...
```

**新建 `tests/fakes.py`**：FakePlanner（返回预设 TaskDef）/ FakeExecutor（预设 outcome）/ FakeVerifier（预设 verdict，支持 per-attempt）。

**测试**：fake 符合 Protocol，能返回预期值。

---

## Phase 1 — Orchestrator 串行循环（脊柱）

**目标**：把已建的 scheduler/fsm/dag + Ports 串成完整串行循环。

**新建 `orchestrator.py`**：
```python
class Orchestrator:
    async def run(self) -> RunResult:
        defs = await self.planner.plan(self.ctx)
        self.graph = build_graph(defs, self.workers)         # Scheduler 校验
        while True:
            self._propagate_blocked()                        # unreachable → BLOCKED
            ready = select_dispatchable(compute_frontier(self.graph), running=0, max=1)
            if not ready: return await self._terminal()
            await self._execute_and_settle(self.graph.nodes[ready[0]])

    async def _execute_and_settle(self, node):
        self._transition(node, RUNNING)                      # 经 QUEUED
        outcome = await self.executor.run(node)              # 串行 await
        if not outcome.ok: return self._handle_failure(node, "worker 失败")
        self._transition(node, VERIFYING)
        verdict = await self.verifier.verify(node)           # Verifier 裁决
        self._transition(node, COMPLETED) if verdict.passed else self._handle_failure(node, verdict.reason)
```

**测试**（test_orchestrator.py，用 fake）：
- TC-9.1 三任务 happy → COMPLETED，全 VERIFIED(=COMPLETED)，final_answer 被调
- TC-9.2 一任务验收失败一次 → retry → 通过，retries==1
- **TC-4.1 命门**：executor.ok=True（worker 自称完成）但 verifier 永远 fail → 任务**绝不 COMPLETED**，退出 FAILED
- BLOCKED 传播：一任务 retry 耗尽 FAILED → 下游 BLOCKED → 退出 UNREACHABLE/FAILED
- §8 退出码：completed / failed / budget

**⚠️ 本相要拍的决策**：retry 回 `PENDING`（frontier 重捡，需改 fsm FAILED→PENDING）还是 `QUEUED`（dispatcher 也拉 QUEUED）。建议 **PENDING**（串行循环最简），改 fsm + test_fsm 一行。

> 📄 **Phase 0+1 照着就能写的详细方案（完整代码 + 测试用例）→ [[coordinator-mvp-phase1-orchestrator]]**

---

## Phase 2 — Verifier（真，机械验收，§4）

**目标**：换掉 FakeVerifier，跑真实机械检查（TC-4.1 命门落地）。

**新建 `verifier.py`**：
```python
class MechanicalVerifier:
    async def verify(self, node) -> Verdict:
        for check in node.task.acceptance:
            if check.kind == "mechanical":
                code = await run_command(check.spec, cwd=node.worktree or self.workspace)
                if code != 0: return Verdict(False, f"{check.spec} 退出码 {code}")
        return Verdict(True)
```

**测试**：TC-4.1（worker ok 但 `false` 命令 → FAILED）、TC-4.2（`true` → pass）、TC-4.3（在 workspace 内跑）、TC-4.4（失败原因捕获）。MVP 只 mechanical，跳过 llm_judge/集成闸门。

**清理**：旧 `harness.py` 的 detect_cycle 已被 dag.py 取代，删旧文件。

---

## Phase 3 — Planner（真，MVP 种子式，§1）

**目标**：换掉 FakePlanner，种子 + 单次 `chat_structured` 出 DAG。

**新建 `planner.py` + `context.py`**：
```python
def gather_context(session, handoff, design_doc=None) -> PlanContext:   # context.py
    ws = session.workspace_path
    return PlanContext(task=..., agents=registry.list(), repo_tree=list_tree(ws), ...)

class SeedPlanner:                                                       # planner.py（MVP）
    async def plan(self, ctx) -> list[TaskDef]:
        raw = await self.llm.chat_structured(build_seed_prompt(ctx))
        return parse_task_defs(raw)        # 容错解析（TC-1.5）→ build_graph 校验
    async def final_answer(self, graph) -> str: ...
```

**测试**：mock LLM 返回 plan dict → TaskDefs；畸形 JSON → 容错（TC-1.5）；list_tree 用临时 git 仓库。

**清理**：旧 `coordinator.py` stub 删，逻辑进 `planner.py`。

> 标准档的方案① tool_use 循环（§6.9）**本相不做**——留作后续增强。

---

## Phase 4 — Executor（真，派 worker CLI）

**目标**：换掉 FakeExecutor，派真 worker CLI session。

**新建 `executor.py`**：复用 `claude_code_runtime`，`run(node)` = 起 worker（instruction + cwd=workspace）、等完成、捕获输出 → WorkerOutcome。MVP：串行、无 worktree、硬超时（`asyncio.wait_for`）。

**测试**：mock runtime（不起真 CLI）验证 dispatch/超时/outcome 映射；真 CLI 留手动冒烟。

---

## Phase 5 — 接线（Selector → Orchestrator）

**目标**：§13 接线落地。

- `selector.py`：加 decompose 预闸门（§13.5 A1）+ `SelectorDecision.decompose()`
- `chat_service.py`：收 decompose → gather_context → 起 `Orchestrator.run()` 后台任务
- 进度经 EventBus/WS 推（复用 watermark）

**测试**：TC-10.1（decompose 预闸门命中）、TC-10.2（纯讨论不触发不加 LLM 回归）。

---

## 依赖图 & 估量

| Phase | 依赖 | 档位 | 估量 | 风险 |
|------|------|------|------|------|
| 0 Ports | — | MVP | 小 | 低 |
| 1 Orchestrator | 0 + 已建 | MVP | **中（核心）** | 低（纯逻辑+fake） |
| 2 Verifier | 0 | MVP | 小 | 低 |
| 3 Planner | 0 | MVP | 中 | 中（LLM 解析容错） |
| 4 Executor | 0 | MVP | 中 | **中高（接真 CLI 运行时）** |
| 5 接线 | 1-4 | MVP | 中 | 中（改 selector/chat_service，有回归面） |

**建议节奏**：先打通 M1（Phase 0+1，纯 fake，证明架构）→ 再 2/3（换真 Verifier/Planner）→ 最后 4/5（接真 CLI + 系统接线，风险最高放最后）。


## 关联文档

- [[coordinator-mvp-phase1-orchestrator]] **Phase 0+1 详细方案**（照着就能写：完整代码 + 测试）
- [[coordinator-subsystem-collaborators]] 协作者职责 + §6 上下文/工具决策
- [[coordinator-test-plan]] 各 TC 的 given/when/then
- [[coordinator-dag-driven-design-v2]] v2.3 确定性逻辑细节
