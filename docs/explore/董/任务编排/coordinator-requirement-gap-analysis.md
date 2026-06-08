# 协调者功能需求完整性审查

> 日期：2026-06-04 | 方法：已有文档全量审查 + 业界标准对照 | 来源：4 个权威框架

---

## 一、审查方法

1. 通读已有 4 份文档，提取已覆盖的功能需求
2. 搜索 4 个权威来源的功能需求清单：
   - **Microsoft Azure** — AI Agent Orchestration Patterns（2026.02）
   - **CrewAI** — Manager Agent 完整功能集
   - **arXiv:2510.02557v1** — Manager Agent 形式化模型（30 项需求）
   - **Anthropic** — Building Effective Agents（workflow vs agent 边界）
3. 逐项对照，标注覆盖状态

---

## 二、已有文档覆盖范围

| 文档 | 覆盖内容 |
|------|---------|
| `coordinator-design-decision.md` | 协调者定位、与 Selector 关系、触发机制、用户追问处理 |
| `task-execution-open-questions.md` | 路径不可达（3 层降级）、进度管理（FSM 事件）、人在环调整（skip/cancel/reassign）、文件冲突（4 策略） |
| `coordinator-research-report.md` | 业界对比、定量证据、Planner vs Orchestrator |
| `open-multi-agent_analysis_report.md` | open-multi-agent 架构分析、Task DAG、Scheduler |

---

## 三、差距清单

按功能域分类，对照三个业界框架的完整需求。

### 域 A：任务分解与规划

| # | 需求 | Microsoft | CrewAI | arXiv 论文 | 我们覆盖？ |
|---|------|:---:|:---:|:---:|:---:|
| A1 | 目标 → 结构化 TaskPlan（DAG） | ✅ | ✅ | ✅ | ✅ `Coordinator.decompose()` |
| A2 | 依赖关系检测（并行 vs 串行） | ✅ | — | ✅ | ✅ `detect_cycle()` + DAG 编译 |
| A3 | 层次化/嵌套分解（子任务的子任务） | ✅ | — | ✅ | ❌ **未覆盖** |
| A4 | 约束感知分解（硬约束 + 软约束） | — | — | ✅ `ℋ` + `𝒮` | ❌ **未覆盖** |
| A5 | 动态图修改（执行中增删 Task） | — | — | ✅ `AddTask`/`RemoveTask` | ❌ **未覆盖** |
| A6 | 任务优先级排序（非依赖性的） | — | ⚠️ | — | ❌ **未覆盖** |
| A7 | 协调者 prompt 设计（system prompt + few-shot） | — | — | — | ❌ **未覆盖** |
| A8 | 协调者输入输出契约（JSON Schema） | — | — | — | ⚠️ **部分**：`PlannedTask` 定义存在但 prompt 是占位文本 |

### 域 B：Worker 分配

| # | 需求 | Microsoft | CrewAI | arXiv 论文 | 我们覆盖？ |
|---|------|:---:|:---:|:---:|:---:|
| B1 | 基于能力标签分配 | ✅ | ✅ | ✅ | ⚠️ `Harness.route_worker()` 骨架，未接入 capability_tags |
| B2 | Worker 负载感知（当前忙/闲） | ✅ | ✅ | ✅ | ❌ **未覆盖** |
| B3 | Worker 可用性感知（在线/离线/被删） | ✅ | — | ✅ | ❌ **未覆盖** |
| B4 | 能力发现机制（协调者如何知道 Agent 能做什么） | — | — | ✅ `capability modeling` | ❌ **未覆盖**：只说了"注入 capability_tags"，没设计注入协议 |
| B5 | 强制分配覆盖（用户指定 Worker） | — | — | — | ⚠️ 人在环重分配已设计 |

### 域 C：验证与质量

| # | 需求 | Microsoft | CrewAI | arXiv 论文 | 我们覆盖？ |
|---|------|:---:|:---:|:---:|:---:|
| C1 | TaskPlan 结构校验 | ✅ | — | — | ✅ `Harness.validate()` |
| C2 | 循环依赖检测 | ✅ | — | — | ✅ `detect_cycle()` |
| C3 | Worker 输出质量验证 | — | ✅ Manager reviews | ✅ `quality verification` | ❌ **未覆盖** |
| C4 | 目标达成判定（所有 Task 完成 = 目标达成？） | — | — | ✅ `goal completion assessment` | ❌ **未覆盖** |

### 域 D：结果管理

| # | 需求 | Microsoft | CrewAI | arXiv 论文 | 我们覆盖？ |
|---|------|:---:|:---:|:---:|:---:|
| D1 | 多 Task 结果聚合/合成 | ✅ | ✅ | ✅ `artifact collection` | ❌ **未覆盖** |
| D2 | 产物注册表（Task 产出了什么文件/代码） | — | — | ✅ `artifact registry X` | ❌ **未覆盖** |
| D3 | 最终报告生成（向用户汇报完成情况） | — | — | ✅ `transparent reporting` | ⚠️ 进度推送已设计，汇总报告未设计 |

### 域 E：错误与异常

| # | 需求 | Microsoft | CrewAI | arXiv 论文 | 我们覆盖？ |
|---|------|:---:|:---:|:---:|:---:|
| E1 | Worker 失败重试 | ✅ | ✅ | — | ✅ FSM `FAILED → QUEUED` |
| E2 | 子树重新规划（失败后重分解） | ✅ | — | ✅ `re-planning on failure` | ✅ 回调 Coordinator 重规划子树 |
| E3 | 协调者自身失败处理（LLM 超时/格式错误） | — | — | — | ❌ **未覆盖** |
| E4 | 约束违反惩罚 | — | — | ✅ `constraint violation` | ❌ **未覆盖** |

### 域 F：执行管理

| # | 需求 | Microsoft | CrewAI | arXiv 论文 | 我们覆盖？ |
|---|------|:---:|:---:|:---:|:---:|
| F1 | Worker 进程生命周期管理（spawn/超时/清理） | ✅ `ActivationManager` | — | — | ❌ **未覆盖**：CLI Pool 有进程管理，但不受协调者控制 |
| F2 | Budget/Token 管控 | ✅ | — | — | ⚠️ domain2 spec 中提到 Harness Budget Controller，未实现 |
| F3 | 并行度控制（同时最多 N 个 Worker） | ✅ | — | — | ❌ **未覆盖** |
| F4 | 审批门控（危险操作暂停等确认） | ✅ | — | — | ⚠️ FSM 有 `AWAITING_APPROVAL` 状态，但触发逻辑未设计 |
| F5 | Worker 间通信监控（Agent 私聊协调） | — | — | ✅ `communication surveillance` | ❌ **未覆盖** |
| F6 | Worker 进程恢复（崩溃后 `--resume`） | ✅ | — | — | ⚠️ 场景推理文档讨论了但未设计协议 |

### 域 G：审计与可观测

| # | 需求 | Microsoft | CrewAI | arXiv 论文 | 我们覆盖？ |
|---|------|:---:|:---:|:---:|:---:|
| G1 | 不可变事件日志 | — | — | ✅ `audit trail` | ✅ `task_events` append-only |
| G2 | 协调者决策可追溯（为什么这样分？） | — | — | ✅ `transparent reporting` | ⚠️ `TaskPlan.rationale` 字段存在但 prompt 不要求解释 |
| G3 | 协调者性能指标（分解耗时、准确率） | — | — | — | ❌ **未覆盖** |

---

## 四、优先级分类

### Critical（核心功能，缺失意味着系统跑不起来）

| # | 缺失项 | 为什么 critical |
|---|--------|----------------|
| **A7** | 协调者 prompt 设计 | 当前 `_build_prompt` 是占位文本——没有 system prompt + few-shot，分解质量不可控 |
| **A8** | 输入输出契约 | 协调者输出随机 JSON vs 严格 Schema → Harness 解析不可靠 |
| **E3** | 协调者自身失败处理 | LLM 超时/返回非法 JSON → 整个分解链路中断，没有降级方案 |
| **B4** | Worker 能力发现 | 协调者不知道 Agent 能做什么 → 分配随机/错误 |

### High（严重影响用户体验或可靠性）

| # | 缺失项 | 为什么 high |
|---|--------|------------|
| **C3** | Worker 输出质量验证 | Task 标记 COMPLETED 但产出是错的 → 后续依赖 Task 基于错误结果执行 |
| **D1** | 结果聚合 | 5 个 Task 完成了，用户只看到 5 条「Task-N ✅」，没有一个人说「整体搞定了，这是结果」 |
| **F3** | 并行度控制 | 10 个 Task 同时 READY → 10 个 CLI 同时 spawn → 系统资源爆炸 |
| **A5** | 动态图修改 | 执行中发现某个 Task 不必要 → 无法删除，白白执行 |
| **F1** | Worker 进程生命周期 | 无超时管理 → 一个 Worker 卡死，整个 DAG 永久阻塞 |

### Medium（影响效率或扩展性）

| # | 缺失项 | 为什么 medium |
|---|--------|--------------|
| **A3** | 嵌套分解 | 复杂 Task 无法拆分子任务 → 单个 Agent 承担过重任务 |
| **A6** | 任务优先级 | 两个 Task 都 READY 但 Worker 只有一个 → 没有优先级规则 |
| **D3** | 最终报告 | 用户需要手动查看每个 Task 结果再自己总结 |
| **G2** | 决策可追溯 | 协调者分配方案不合理时无法 debug |

### Low（锦上添花，后续迭代）

| # | 缺失项 |
|---|--------|
| A4 | 约束感知分解（硬/软约束） |
| E4 | 约束违反惩罚 |
| F5 | Worker 间通信监控 |
| G3 | 协调者性能指标 |
| B2 | Worker 负载感知 |
| B3 | Worker 可用性感知 |

---

## 五、结论

**已有 4 份文档覆盖了"协调者是什么"和"任务执行后怎么办"，但缺失了协调者核心流程中最关键的环节：**

```
已有覆盖：
  协调者定位 ✅ → 触发机制 ✅ → 分解后做什么 ✅ → 执行中异常 ✅

缺失环节：
  ┌─────────────────────────────────────────────────────┐
  │                                                     │
  │  ① 分解前：协调者怎么知道 Agent 能做什么？            │  ← B4 能力发现
  │  ② 分解中：prompt 怎么写？输出长什么样？              │  ← A7/A8
  │  ③ 分解失败：LLM 挂了怎么办？                        │  ← E3
  │  ④ 执行后：Task 结果对吗？怎么合并？                  │  ← C3/D1
  │  ⑤ 执行中变：怎么动态增删 Task？                     │  ← A5
  │                                                     │
  └─────────────────────────────────────────────────────┘
```

**4 个 Critical + 5 个 High 缺失项需要在开始 M3 编码前设计完。**

---

## 关联文档

- [[coordinator-design-decision]] — 已决策
- [[task-execution-open-questions]] — 三个执行问题
- [[coordinator-research-report]] — 业界调研
- [[open-multi-agent_analysis_report]] — 项目分析
- `docs/specs/domains/domain2-orchestration_域2-Agent编排.md` — M3 任务清单
