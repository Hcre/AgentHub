# Phase 3 规格 — Planner（真 LLM 分解，MVP 种子式）

> 日期：2026-06-06 | 属于：[[coordinator-mvp-implementation-plan]] Phase 3
> 前提：M1（Orchestrator）+ Phase 2（Verifier 机械层，对 llm_judge fail-closed）已落地。
> MVP 边界：种子单次 `chat_structured`，**只产 mechanical acceptance**，**不读文件**（tool_use 循环 §6.9 是标准档）。

---

## 1. 需求 / 约束 / 边界 / 验收标准

### 1.1 需求（做什么）

| 组件 | 职责 |
|------|------|
| `gather_context()` | 从 workspace + 群成员注册表 + 约束 + (可选)用户文档，组装 `PlanContext` 种子 |
| `SeedPlanner.plan(ctx)` | 一次 `chat_structured` → 解析 → 校验 → `list[TaskDef]` |
| `SeedPlanner.final_answer(graph)` | 一次 LLM → 汇总完成情况（文本） |

### 1.2 约束（必须遵守）

- **单次调用**：MVP 不做 tool_use 循环、不读文件。上下文一次性预注入。
- **只产 mechanical**：`acceptance` 每条 `kind` 必须是 `mechanical`（Verifier 对其他 fail-closed）。无法验证的任务 → `no_verify=true`（显式）。
- **worker 限群成员**：`suggested_worker` 必须 ∈ `ctx.workers`（= `group.member_ids` 的 Agent 名）。
- **纯推理**：Planner **不改状态、不派发、不验证**——只返回数据。校验归 `build_graph`，调度归 Orchestrator。
- **无环 + 依赖合法**：由 `build_graph` 兜底校验（Planner 不自校验，但 prompt 要求其遵守）。

### 1.3 边界（不做什么）

- 不读文件、不执行命令、不碰文件系统写（gather_context 只读、workspace 内）。
- 不决定调度顺序（只声明 `depends_on`，frontier 算就绪）。
- 不落库、不推前端（Orchestrator 负责）。

### 1.4 验收标准（Phase 3 本身算完成）

- `tests/test_planner.py` + `tests/test_context.py` 全绿（§6 用例）。
- e2e：Orchestrator + 真 SeedPlanner（mock LLM）+ 真 MechanicalVerifier 跑一个任务到 `COMPLETED`。
- ruff 干净，类型注解齐全。

---

## 2. 条件 → 动作（流程状态）

| 条件 | 系统动作 |
|------|---------|
| Selector 判定 decompose（§13.5） | `gather_context()` → `Planner.plan(ctx)` |
| LLM 返回合法 JSON 且解析出 ≥1 TaskDef | `build_graph` 校验 → 通过则交 Orchestrator |
| LLM 返回畸形 JSON | 多层容错解析（见 §3）；仍失败 → 重试（≤N 次） |
| 解析重试耗尽 | 抛 `PlanParseError` → 上报用户（MVP 不自动 replan） |
| `build_graph` 校验失败（环/悬空/未知 worker/无 acceptance） | MVP：抛 `DagValidationError` → 上报；标准档：回灌 LLM 修 |
| LLM 产出空 plan（0 任务） | 拒绝（`PlanEmptyError`）——plan 必须 ≥1 任务 |
| 所有任务 VERIFIED（Orchestrator 终止） | 调 `Planner.final_answer(graph)` → 汇总文本 |

---

## 3. 异常处理（统一方式）

### 3.1 异常分层 + 处理

| 异常 | 处理 |
|------|------|
| LLM 畸形 JSON | 多层容错：① 剥 ```code fence``` ② 提取首个平衡 `{}` ③ Python 关键字替换（True→true）④ `ast.literal_eval`。仍失败 → 重试 |
| 解析重试耗尽（默认 3） | 抛 `PlanParseError`，含最后一次原始输出片段 |
| plan 为空 | 抛 `PlanEmptyError` |
| 校验失败（环/悬空/未知 worker） | `build_graph` 抛 `DagValidationError`（已有）→ 上报 |
| 非 mechanical acceptance | build 时拒绝（§4 禁止项）或 prompt 约束在先；不静默放行 |
| LLM API 错误（超时/限流/key） | 捕获 → 退避重试（≤2）→ 仍失败抛 `PlannerLLMError` |
| LLM 返回非 dict（如纯文本无 JSON） | 当畸形 JSON 处理 |

### 3.2 统一原则

- **不静默吞**：任何异常都记日志（`logger.warning/error`）+ 抛领域异常。
- **领域异常**：`PlanParseError` / `PlanEmptyError` / `PlannerLLMError` 继承 `DomainError`（与 `DagValidationError` 同层）。
- **有界重试**：解析/API 重试都有上限，不无限循环。

---

## 4. 禁止项（不允许发生）

| 禁止 | 防线 |
|------|------|
| 静默通过非法 plan（环/悬空/无 worker） | `build_graph` 强制校验，抛异常 |
| 非 mechanical acceptance 流到 Verifier | prompt 约束 + build/Planner 出口校验拒绝 |
| `suggested_worker` 不在群成员里 | `build_graph` 已校验未知 worker |
| 空 acceptance 且未标 no_verify | `build_graph` 已校验 |
| Planner 改状态 / 派发 / 执行命令 | 接口只返回 `list[TaskDef]`；无副作用 |
| gather_context 读 workspace 外文件 | 路径限边界（realpath + startswith workspace） |
| 重复 task id | `build_graph` 已校验 |
| 空 plan 当成功 | `PlanEmptyError` |

---

## 5. 通过 / 不通过 / 成功判定

### 5.1 算通过（plan 合格）

- 解析出 `list[TaskDef]`，长度 ≥1
- 全部字段合法：id 唯一、title 非空、suggested_worker ∈ workers、depends_on 引用存在、无环
- 每个 acceptance 为 mechanical（或 no_verify=true）
- `build_graph` 不抛异常

### 5.2 不算通过

- 解析失败（重试耗尽）/ 空 plan / 校验失败（环/悬空/未知 worker/无验收）/ 含非 mechanical acceptance / LLM API 失败

### 5.3 Phase 3 成功判定

- 全部 §6 测试绿（解析容错、校验集成、gather_context、final_answer）
- e2e：真 Planner(mock LLM) + 真 Verifier 跑任务到 COMPLETED
- ruff + 类型注解

---

## 6. 代码规范 / 错误处理统一 / 可测可扩展可观测

### 6.1 代码规范

- Python：async + 类型注解 + ruff；**禁裸 print（用 logging）/ 禁同步阻塞**。
- 文件 <800 行；`planner.py` / `context.py` 拆分（推理 vs 上下文组装）。
- LLM 调用 async；JSON 解析独立函数（可单测）。

### 6.2 错误处理统一

- 所有 Planner 异常继承 `DomainError`：`PlanParseError` / `PlanEmptyError` / `PlannerLLMError`。
- 捕获点记日志（含 task 上下文），不裸 raise 第三方异常给上层。

### 6.3 必须可测 / 可扩展 / 可观测

| 维度 | 要求 |
|------|------|
| **可测** | LLM 经接口注入（`StructuredLLM` Protocol，mock 返回 plan dict）；gather_context 用临时 git 仓库；解析函数纯函数可单测 |
| **可扩展** | MVP `SeedPlanner` ↔ 标准 `AgenticPlanner`（tool_use 循环）共用 `Planner` Protocol，Orchestrator 不变 |
| **可观测** | 记录：plan 尝试次数、解析失败、校验失败、产出任务数、rationale。落 `events`（task_events 雏形） |

---

## 7. 数据结构 / 关键字段 / 接口 I/O

### 7.1 输入：PlanContext（种子，已在 ports.py，MVP 扩字段）

```python
@dataclass(frozen=True)
class PlanContext:
    task: str                       # 用户需求（必填）
    workers: tuple[str, ...]        # 群成员 Agent 名（必填，build_graph 校验）
    repo_tree: str = ""             # 目录树快照（git ls-files / walk）
    constraints: tuple[str, ...] = ()   # 交接约束（"错误提示中文"…）
    agents_desc: str = ""           # 成员能力描述（name + capability_tags）
    design_doc: str | None = None   # 用户上传文档（可选）
```

### 7.2 LLM 输出 JSON 契约（chat_structured 返回）

```json
{
  "tasks": [
    {
      "id": "t1",
      "title": "创建 LoginForm 组件",
      "suggested_worker": "前端Agent",
      "description": "邮箱+密码+中文错误提示",
      "depends_on": [],
      "acceptance": [
        {"kind": "mechanical", "spec": "npm run build", "expect": null}
      ],
      "no_verify": false
    }
  ],
  "rationale": "前后端可并行，测试依赖二者"
}
```

### 7.3 输出：list[TaskDef]（已在 dag.py）

关键字段：`id`（唯一）、`title`、`suggested_worker`（∈workers）、`depends_on`（list[str]）、`acceptance`（list[Check]，MVP 全 mechanical）、`no_verify`。

### 7.4 接口签名

```python
def gather_context(session, handoff, design_doc: str | None = None) -> PlanContext: ...

class StructuredLLM(Protocol):            # 可注入接缝
    async def chat_structured(self, prompt: str) -> dict: ...

class SeedPlanner:                        # 实现 Planner Protocol
    def __init__(self, llm: StructuredLLM, model: str): ...
    async def plan(self, ctx: PlanContext) -> list[TaskDef]: ...
    async def final_answer(self, graph: TaskGraph) -> str: ...
```

---

## 8. 空值 / 异常值 / 重复值

| 情况 | 处理 |
|------|------|
| 空 repo_tree（绿地项目） | 正常 plan（无现有代码可读，靠需求分解） |
| 空 workers（群无成员） | 拒绝：无法 plan，抛 `PlanEmptyError`/上报（无可派对象） |
| LLM 缺字段（无 id/title/worker） | id/title/worker 必填，缺 → 解析层拒绝该任务 / 整体 `PlanParseError` |
| acceptance 缺失 / 空 | 必须 `no_verify=true` 否则 `build_graph` 拒绝 |
| `expect` 非整数串 | Verifier 已守卫（Phase 2）；Planner 出口可预校验 |
| 重复 task id | `build_graph` 拒绝 |
| 重复 depends_on | 去重（无害，解析时 dedupe） |
| depends_on 引用不存在 | `build_graph` 拒绝（悬空依赖） |
| null / 多余字段 | 忽略多余；null 用默认值 |

---

## 9. 并发 / 权限 / 状态流转

| 维度 | 规则 |
|------|------|
| **并发** | Planner 无状态，每次 plan/final 独立调用，无共享可变状态 → 无并发问题。一个 run 内 plan 调一次 |
| **权限** | gather_context **只读** workspace，路径限边界（不可越界、不可写）。Planner 无执行权限 |
| **状态流转** | Planner **不参与** FSM——它产出的 TaskDef 进 `build_graph` 后节点初始全 `PENDING`，之后流转归 Orchestrator |
| **副作用** | 零副作用（不写文件、不落库、不派发）。唯一外部交互 = 调 LLM（读）+ 读 workspace（读） |

---

## 10. 实现增量（Phase 3 文件）

| 文件 | 动作 |
|------|------|
| `context.py` | 新建：gather_context + list_tree（git ls-files/walk，路径限边界） |
| `planner.py` | 新建：SeedPlanner + 容错 JSON 解析 + prompt 构造 |
| `ports.py` | 加 `StructuredLLM` Protocol；PlanContext 扩字段（constraints/agents_desc/design_doc） |
| `app/core/exceptions.py` | 加 `PlanParseError`/`PlanEmptyError`/`PlannerLLMError`（继承 DomainError） |
| `coordinator.py`（旧 stub）| **删**，逻辑进 planner.py |
| `tests/test_planner.py` / `test_context.py` | 新建 |

---

## 关联文档

- [[coordinator-mvp-implementation-plan]] Phase 3 概述
- [[coordinator-subsystem-collaborators]] §5.2 Planner / §6 上下文与工具（方案①）
- [[coordinator-dag-driven-design-v2]] §2.1 plan / §6 验证闸门
- [[coordinator-test-plan]] §1 DAG 校验 / §3 Planner
