# 任务执行阶段待解决问题

> 日期：2026-06-03 | 状态：开放讨论 | 关联：[[coordinator-design-decision]] [[EXP-02_编排器设计模式]]

## 背景

协调者设计已决策（纯 LLM 调用，非完整 Agent），任务分解后的执行阶段需要设计以下问题。

> 2026-06-04 更新：经 [[task-execution-completeness-and-implementation-analysis]] 完整性审查，从 3 项扩展为 17 项（§§1-10 已有 + §§11-17 新增）。

---

## 问题 1：任务路径不可达

### 场景

协调者分解出 TaskPlan，Harness 通过 DAG 拓扑排序编译执行计划。但执行过程中可能出现：

- **Worker 不可用**：分配的 Agent 离线/被删除/超载
- **依赖不可达**：Task-A 依赖 Task-B 的输出，但 Task-B 失败后无重试配额，导致 Task-A 永远无法进入 ready 状态
- **资源不可用**：Task 需要的工具/文件/API 在执行时不可用（如 MCP 工具下线、网络超时）
- **DAG 死锁**：两个 Task 互相依赖（Harness `detect_cycle` 已拦截编译时环，但运行时隐性依赖仍可能死锁）

### 需要决策

| 选项 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A. Worker 自治重路由** | 执行失败的 Agent 自行决策替代路径（如换工具、换方法），在自己的 CLI session 内自修复 | 延迟最低，不需要协调者介入 | Agent 可能越权/偏离目标；质量不可控 |
| **B. 汇报协调者重新分解** | 失败触发 `TaskStateChanged(FAILED)` → Harness 检测依赖不可达 → 回调 `Coordinator.decompose()` 重新规划该子树 | 协调者有全局视角，质量可控 | 多一次 LLM 调用（成本 + 延迟）；需要传回完整上下文 |
| **C. 任务面板人工修复** | 不可达 Task 在 UI 高亮（红色 + 原因），用户在 TaskPanel 手动调整：重新分配 Worker / 跳过 / 取消子树 | 人在环，最终兜底 | 需要人工介入；用户可能不在线 |
| **D. 级联失败（当前默认）** | Task-B 失败 → `cascadeFailure` → 所有依赖 Task-B 的 Task 标记 `skipped` → 汇报用户 | 简单可预测 | 用户体验差（一个失败全链报废） |

### 建议方向

**分层处理**：

1. 第一层：Worker 自治重试（单 Task 内，不对 DAG 产生影响）— FSM 的 `FAILED → QUEUED` 已经支持，重试 3 次后才升级
2. 第二层：重试耗尽后回调协调者重新规划（仅该子树，不重跑整个 DAG）
3. 第三层：协调者也无法修复 → UI 高亮，用户手动介入

**设计要点**：
- 回调协调者时注入的上下文应包含：失败 Task 的 output/error + 受影响子树的结构 + 已有成功 Task 的结果
- 协调者输出「子树修复计划」而非全新 TaskPlan
- Harness 将修复计划合并到原 DAG 中（替换失败子树）

---

## 问题 2：任务进度管理

### 场景

用户发出任务需求后，需要知道：
- 当前进度（几个 Task 完成了、几个在执行、几个在等）
- 预估完成时间
- 每个 Task 的详细状态（输出内容、错误信息、耗时）

### 当前状态

| 已有能力 | 实现位置 | 缺口 |
|---------|---------|------|
| Task FSM（8 态） | `domain/task_engine/fsm.py` | ✅ |
| Task 状态变更事件 | `domain/events.py`（`TaskStateChanged`） | ⚠️ 事件发布未接入 WS 推送 |
| TaskBoard 前端 | 前端设计中有，后端 `tasks.py` 是 stub | ❌ 未实现 |
| 父任务+子任务 DAG 可视化 | 前端设计方案（`§2.4.4`） | ❌ 未实现 |
| 进度百分比 | 无 | ❌ 需要新增 |
| 时间预估 | 无 | ❌ 需要新增 |

### 需要设计

**进度指标**：
- 父任务层级：`已完成子任务 / 总子任务`（基础进度条）
- 考虑 DAG 权重：串行链的长度比并行组更重要
- 预估时间：基于历史 Task 平均耗时（首次无数据时显示「估算中」）

**进度推送机制**：
- `TaskStateChanged` 事件 → Redis Pub/Sub → WS 推送到群聊
- 前端 TaskPlanCard 实时更新进度条 + 各子任务状态颜色
- 不做轮询

**群聊进度汇报**：
- 每个 Task 完成时自动发一条简短的系统消息到群聊：「✅ Task-1 前端页面创建完成（耗时 45s）」
- 全部完成时发汇总消息
- Agent 不需要主动汇报进度（FSM 事件驱动，系统消息）

**存储**：
- `task_events` 表（已设计，未创建）记录所有状态变更，追加不可变
- 进度百分比可由 SQL 聚合计算，不单独存储

---

## 问题 3：人在环调整

### 场景

任务执行过程中，用户可能需要：

- **调整路径**：修改依赖关系、跳过某个 Task、取消某个子树
- **查看执行情况**：实时看到 Task 的 output/日志/错误
- **处理文件冲突**：多个 Agent 同时修改同一文件时防止覆盖

### 3.1 调整路径

**需要定义的操作**：

| 操作 | 触发方式 | 效果 |
|------|---------|------|
| 跳过 Task | TaskPanel 点击「跳过」 | Task 标记 `skipped`，依赖它的 Task 正常 unblock |
| 取消子树 | TaskPanel 点击「取消子树」 | 选中 Task + 所有依赖它的 Task 标记 `cancelled` |
| 重新分配 Worker | TaskPanel 拖拽/下拉 | `task.assignee_id` 变更，重新入队 |
| 暂停/恢复 | TaskPanel 按钮 | FSM: `RUNNING → PAUSED → RUNNING` |
| 重新分解 | 用户发送「换个方案，把前端和后端合并为一个 task」 | Selector 返回 `decompose` → Coordinator 重新分解（含用户反馈） |

**约束**：
- 运行中的 Task 不能被跳过/取消（先暂停再操作）
- 历史 Task 不可修改（append-only 事件日志）
- 所有手动操作写入 `task_events`（审计追踪）

### 3.2 查看执行情况

**信息层级**：

| 层级 | 展示 | 数据来源 |
|------|------|---------|
| L1: 群聊消息 | 系统消息：「Task-1 ✅」「Task-2 执行中…」 | `TaskStateChanged` 事件 → WS |
| L2: TaskPlanCard | 父任务 DAG 图 + 进度条 + 各子任务状态颜色 | Task API 聚合查询 |
| L3: Task 详情面板 | 单 Task 完整信息：output/error/logs/耗时/token 消耗 | Task API 详情查询 |
| L4: CLI 实时流 | Agent 执行过程的原始流式输出 | WS stream（复用私聊流式通道，只读） |

**L4 是一个关键设计决策**：用户是否能看到 Agent 执行过程的原始 CLI 输出（thinking、tool calls、中间步骤）？

- 建议默认**可见但折叠**（类似 Claude Code 的 thinking 折叠）
- 安全敏感操作（如 deploy）需审批确认后才可见

### 3.3 文件冲突

**冲突场景**：
- Task-1（前端 Agent）和 Task-2（后端 Agent）同时修改 `api/types.ts`
- Task-3 修改 `README.md`，用户在 Task-3 执行期间手动编辑了 `README.md`

**处理策略**：

| 策略 | 描述 | 适用场景 |
|------|------|---------|
| **A. 协调者预分配文件** | Coordinator 分解时明确每个 Task 的文件范围（"你改 A.ts 和 B.ts，他改 C.ts"） | 文件边界清晰的任务 |
| **B. Agent 先读后写** | Worker 修改前先读文件最新版本，基于最新内容修改 | 冲突概率低的场景 |
| **C. Git 分支隔离** | 每个 Task 在独立分支上工作，完成后再合并 | 最安全但复杂度最高 |
| **D. 锁机制** | Task 声明要修改的文件列表（Lock），其他 Task 等待释放 | 冲突概率高的场景 |

**建议方向**：

1. **首期**：策略 A — 协调者分解时在 Task.description 中指定文件范围。这是最低成本的方案，依赖协调者分解质量。
2. **二期**：策略 B + C — Agent 先 pull 最新版本再修改；每个 Task 自动创建分支 `task/{task_id}`。
3. **冲突检测**：Harness 在 DAG 编译阶段检测两个并行 Task 是否声明了相同的文件范围 → 如果是，强制串行化或提示用户确认。

---

## 关联文档

- [[coordinator-design-decision]] 协调者设计决策（纯 LLM 调用 vs 完整 Agent）
- [[EXP-02_编排器设计模式]] 编排器设计模式深度分析
- [[open-multi-agent_analysis_report]] open-multi-agent 项目分析
- `docs/specs/domains/domain2-orchestration_域2-Agent编排.md` M3 任务清单
- `docs/specs/01b-architecture-design_分层与数据流.md` S13/S14 数据流
- `docs/design/group-chat-discussion-mode_群聊讨论模式设计方案.md` 讨论模式

---

---

## 问题 4：协调者输入输出契约

### 场景

Coordinator.decompose() 需要一个完整的 prompt 工程设计和输出 Schema。

### 当前状态

`_build_prompt()` 是占位文本，`_parse()` 假设 LLM 自然返回合法 JSON。

### 需要设计

**4.1 Prompt 结构**

```
System Prompt（稳定，可缓存）:
  - 角色定义：「你是 AgentHub 的任务协调者…」
  - 分解规则：粒度、命名规范、依赖表达
  - 输出 Schema 说明
  - Few-shot 示例 × 3（不同复杂度）

User Prompt（动态，每次不同）:
  - 上下文：群聊最近 N 条消息摘要
  - 可用 Agent：[name, role, capability_tags, status]
  - 用户需求：原始消息
  - 已有进度：如为重新分解，注入已完成 Task 的结果
```

**4.2 输出 Schema**（结构化 JSON，tool_use 强制）

```json
{
  "tasks": [
    {
      "id": "task-uuid",
      "title": "string",
      "description": "string (含文件范围建议)",
      "suggested_worker": "agent_name (必须匹配可用 Agent.name)",
      "depends_on": ["task-uuid"],
      "estimated_complexity": "simple|medium|complex"
    }
  ],
  "rationale": "为什么这样分解（便于审计追溯）",
  "parallel_groups": [["task-uuid", "task-uuid"]]  // 可并行的组
}
```

**4.3 校验规则**

- `suggested_worker` 必须存在于传入的 Agent 列表
- `depends_on` 引用必须指向同 plan 内的 task id
- `title` 非空，`description` ≥ 20 字符
- `rationale` 非空

### 建议方向

- 使用 Anthropic tool_use 强制结构化输出（`tool_choice: {type: "tool", name: "create_task_plan"}`）
- prompt 模板化：`SELECTOR_PROMPTS[DispatchMode.DISCUSSION]` 类似方式

---

## 问题 5：协调者自身失败处理

### 场景

- LLM 超时（30s 无响应）
- 返回非法 JSON（无法解析）
- 返回的 agent_name 在数据库不存在（幻觉）
- 返回循环依赖的 plan（Harness detect_cycle 已拦截，但需降级）

### 需要设计

| 失败类型 | 降级策略 | 用户感知 |
|---------|---------|---------|
| LLM 超时 | 重试 1 次（更短超时）→ 仍失败则返回友好错误 | 系统消息：「任务分解超时，请简化需求或稍后重试」 |
| 非法 JSON | 重试 1 次（在 prompt 中追加"你的上一次输出不是合法 JSON"）→ 仍失败则降级到单 Agent | 降级为手动 @Agent |
| Worker 幻觉 | 过滤掉不存在的 agent_name，保留合法部分；如果全部非法 → 降级到人工 | 群聊提示：「部分 Agent 不存在，已调整分配方案」 |
| Harness 环检测 | Harness 拒绝 plan → 回调 Coordinator 重试（注入"上一次计划存在循环依赖"） | 最多重试 2 次 |
| API Key 不可用 | 降级到 Selector 的 keyword 规则路由 | 不阻塞用户 |

### 设计要点

- 所有降级路径都不能阻塞用户
- 降级时记录 `coordinator_error` 事件到 task_events

---

## 问题 6：Worker 能力发现

### 场景

Coordinator.decompose() 需要知道每个可用 Agent 能做什么，才能正确分配。

### 需要设计

**注入到 decompose prompt 的 Agent 信息**：

```python
def _build_agent_capability_block(agents: list[Agent]) -> str:
    """构造能力描述，注入 Coordinator prompt。"""
    return "\n".join(
        f"- {a.name}（角色：{a.role or '未指定'}；"
        f"能力标签：{', '.join(a.capability_tags) or '通用'}；"
        f"状态：{a.status}）"
        for a in agents
    )
```

**后续增强**：
- 加入历史 Task 成功率（论文建议的「能力元数据」）
- 加入当前负载（活跃 Task 数）

---

## 问题 7：任务结果聚合

### 场景

5 个子任务全部 COMPLETED。用户看到 5 条「Task-N ✅」系统消息。谁来说「总体完成了，这是摘要」？

### 需要设计

| 方案 | 描述 |
|------|------|
| **A. 系统消息汇总** | 所有 Task COMPLETED → 自动生成一条汇总消息：「✅ 全部 5 个任务完成：Task-1（前端页面）、Task-2（后端 API）、…」 |
| **B. 协调者汇总** | 父任务 COMPLETED → 触发 Coordinator 一次调用 → 基于所有 Task 的输出生成人类可读总结 |
| **C. 仅 TaskPlanCard 更新** | 前端 TaskPlanCard 显示全绿，不额外发消息 |

**建议**：首期 A + C 组合。B 等用户反馈需要更智能的汇总时再补。

---

## 问题 8：Worker 输出质量验证

### 场景

Task COMPLETED 只表示 Agent 完成了执行，不表示输出是正确的。

### 需要设计

| 验证层 | 机制 | 触发 |
|--------|------|------|
| L1: 结构验证 | Task output 非空、符合预期格式 | 自动（Harness） |
| L2: 自动化检查 | lint/typecheck/test 结果 | 可选（Task 声明 `verification: ["lint", "test"]`） |
| L3: Agent 交叉审查 | 另一个 Agent 审查输出 | Coordinator 标记该 Task 为 `review_required=true` |
| L4: 人工审查 | UI 审批 | 用户主动点击「审查」 |

**首期**：L1 自动，L4 人工可选。L2/L3 后续迭代。

---

## 问题 9：动态计划调整

### 场景

执行过程中发现：
- 某个 Task 不必要了（用户改了需求范围）
- 需要新增 Task（发现遗漏）
- Task 之间的依赖关系需要调整

### 需要设计

| 操作 | 触发方式 | 协调者参与？ |
|------|---------|:---:|
| 删除未开始的 Task | TaskPanel「取消」 | 否（Harness 级联取消依赖项） |
| 新增 Task 到现有 plan | 用户「再加一个 X 的任务」 | 是（Coordinator 分析新 Task 的依赖关系） |
| 修改依赖关系 | TaskPanel 拖拽连线 | 否（Harness 校验无环后提交） |
| 完全重新分解 | 用户「换个方案」 | 是（Coordinator 基于已有结果重新分解） |

**关键**：动态修改后 Harness 必须重新校验 DAG（尤其是有环检测）。

---

## 问题 10：Worker 进程生命周期

### 场景

每个 Worker（CLI session）需要管理：超时、资源限制、崩溃恢复、清理。

### 需要设计

| 管理维度 | 机制 | 参数 |
|---------|------|------|
| 超时 | Task 级别 timeout | 默认 10 min，可在 TaskPlan 中覆盖 |
| 并发上限 | 全局 + 单 Agent 上限 | 全局 max 5；单 Agent max 2 |
| 崩溃恢复 | FSM FAILED → QUEUED → 重 spawn | 重试 3 次，指数退避 |
| 资源清理 | Task 完成后清理临时文件 + 关闭 CLI session | 同步 |
| 优雅终止 | 用户取消 → SIGTERM → 等 5s → SIGKILL | 避免僵尸进程 |

**首期**：超时 + 并发上限（硬编码），崩溃恢复复用 FSM 重试。

---

## 问题 11：任务超时与僵尸清理

> 来源：[[task-execution-completeness-and-implementation-analysis]] §A.2-4

### 场景

长时间运行的 Worker Agent 可能出现：

- **挂死**：Agent 在 tool call 上无限等待（如 API 无响应）
- **死循环**：Agent 在对话循环中反复执行相同操作（MAST: "missing termination condition" 是最常见的规格模糊子类）
- **僵尸进程**：Agent 的 CLI 进程已退出但 FSM 状态仍为 RUNNING，Task 永远无法完成
- **孤儿 Task**：父 Harness 崩溃重启后，之前 spawn 的 Worker 进程仍在运行但无人管理

### 需要设计

| 场景 | 检测机制 | 处理 |
|------|---------|------|
| Task 超时 | Task 级别 `timeout`（默认 10 min，可在 TaskPlan 中覆盖） | FSM: `RUNNING → TIMED_OUT` → 释放依赖它的 Task（标记为 `skipped` 或触发 replan） |
| Agent 死循环 | Harness 检测：同一 Task 在 N 分钟内反复 `FAILED → QUEUED → RUNNING → FAILED` 超过阈值 | 标记 `STALLED` → 触发 replan |
| 僵尸 Task | Harness 定期轮询：FSM 状态 RUNNING 但 Worker 进程 PID 不存在 | 标记 `ZOMBIE` → 日志告警 → 人工清理 |
| 孤儿 Worker | Harness 启动时扫描：存在 RUNNING Task 但无对应活跃 Harness instance | 标记 `ORPHANED` → 可选自动 `kill` 或保留人工决策 |

### 超时处理的分层策略

```
Task 级超时（第一层）
  → Task FSM: RUNNING → TIMED_OUT
  → 依赖该 Task 的其他 Task 自动 unblock（标记该 Task 为 skipped）
  
Harness 级超时（第二层）
  → 整个 TaskPlan 超时（如 30 min 总预算）
  → 取消所有未完成 Task
  → 汇报用户已完成部分的结果

资源级超时（第三层）
  → CLI session 空闲超时（如 5 min 无 tool call）
  → 主动关闭 session 释放资源
```

### 设计要点

- 僵尸检测的轮询间隔：建议 30s（太短浪费资源，太长延迟发现）
- 孤儿清理必须谨慎：先检查 Worker 进程是否真的无主（避免误杀正常运行但 Harness 临时重启的 Task）
- MAF Magentic 的 `stall_count` + hysteresis 机制可作为死循环检测的参考：连续 N 轮无实质性进展 → 标记 STALLED

---

## 问题 12：任务幂等性与精确一次执行

> 来源：[[task-execution-completeness-and-implementation-analysis]] §A.2-5

### 场景

重试机制（问题 1 已设计）要求 Task 可安全重试。但以下情况会导致问题：

- Worker 执行了副作用（如发送邮件、写入数据库、创建 Git 分支）但崩溃前未标记 Task 完成
- Harness 重试该 Task → 副作用被重复执行
- 传统 ACID 事务无法跨 Agent 边界

### 参考：Temporal Saga 模式

```
Saga = 一系列本地事务 + 补偿事务

正向流程：
  Task-A: 创建 Git 分支 ✅
  Task-B: 修改代码 ✅
  Task-C: 发送通知 ❌ 失败！

补偿流程（反向执行）：
  补偿 Task-B: git reset --hard（撤销代码修改）
  补偿 Task-A: git branch -D task/xxx（删除分支）
```

### 需要设计

| 策略 | 描述 | 适用场景 |
|------|------|---------|
| **A. 天然幂等** | Task 设计为可安全重复执行（如"确保文件 X 存在且内容为 Y"而非"创建文件 X"） | 优先推荐，不增加系统复杂度 |
| **B. 补偿事务** | Task 声明 `compensate` 动作（逆向操作），失败时 Harness 按逆序执行补偿 | 有副作用的 Task（发邮件、写数据库、创建资源） |
| **C. 幂等键** | Task 执行前生成 `idempotency_key`，写入 task_events；重试时检查 key 是否已存在 | 外部 API 调用（如 GitHub API、邮件服务） |
| **D. 只读先行** | TaskPlan 中标记只读 Task（搜索、分析），这些 Task 不需要幂等性处理 | 降低需要处理幂等性的 Task 数量 |

### 建议方向

1. **首期**：策略 A — Coordinator prompt 中要求尽量使用天然幂等的 Task 描述
2. **二期**：策略 C — 对关键外部 API 调用使用幂等键
3. **三期**：策略 B — 对高级场景实现 Saga 补偿

### 设计要点

- Coordinator 在分解时标记每个 Task 的 `side_effect_level: none|readonly|mutable|external`
- `external` 级别的 Task（如发邮件、部署）必须在 TaskPlan 中声明 `compensate` 步骤
- idempotency_key 格式：`{taskplan_id}:{task_id}:{attempt_number}`

---

## 问题 13：运行时状态持久化与崩溃恢复

> 来源：[[task-execution-completeness-and-implementation-analysis]] §A.2-6

### 场景

Harness 进程崩溃（OOM、服务器重启、部署更新）后：

- 内存中的 DAG 执行状态丢失
- 哪些 Task 已经完成？哪些正在执行？哪些在排队？
- Worker 的 CLI session 仍在运行（孤儿进程）
- 如何恢复到崩溃前的状态继续执行？

### 当前状态

| 已有 | 缺口 |
|------|------|
| `task_events` 表设计（追加不可变） | 表未创建 migration |
| Task FSM 状态可通过 events 重建 | 运行时 DAG 拓扑结构未持久化 |
| | Harness 无 checkpoint 机制 |
| | Worker session 映射关系仅存内存 |

### 参考：MAF CheckpointStorage

```
MAF 的 checkpoint 机制：
  - Superstep boundary 自动保存快照
  - 快照内容：conversation history + task ledger + progress ledger + agent session
  - 恢复：从最近快照重建所有 Executor 状态
  - thread_id 关联多次运行
```

### 需要设计

**Checkpoint 内容**：

```python
class HarnessCheckpoint:
    taskplan_id: str
    dag_snapshot: dict  # 当前 DAG 拓扑 + 各 Task 状态
    active_workers: dict  # {task_id: {session_id, pid, started_at}}
    completed_results: dict  # {task_id: TaskResult}
    coordinator_context: dict  # 供 replan 使用的上下文
    created_at: datetime
```

**恢复流程**：

```
Harness 启动
  → 检查是否存在未完成的 TaskPlan（task_events 中有 RUNNING 但没有 COMPLETED/FAILED）
  → 如果存在：
      1. 从 task_events 重建各 Task 的当前 FSM 状态
      2. 扫描孤儿 Worker（PID 不存在但 FSM 为 RUNNING → 标记 ZOMBIE）
      3. 对 ZOMBIE Task：如果 Worker 进程可恢复 → 重连；否则 → 标记 FAILED → 触发重试/replan
      4. 对 PENDING/QUEUED Task：重新入队
      5. 继续执行
```

**保存时机**：
- 每次 Task 状态变更后（已有 `TaskStateChanged` 事件）
- Harness 空闲时（每 30s 一次 heartbeat）
- 人在环暂停点（问题 3 操作前）

### 设计要点

- 不追求完整的进程快照（太重），改为事件溯源（event sourcing）：从 task_events 重放恢复状态
- orphan 检测需要 SERVER_INSTANCE_ID（区分"Harness 重启"和"Harness 仍在运行但 Task 挂了"）
- 与 Anthropic 的 rainbow deployment 同理：更新时不能直接 kill 旧 Harness（会导致所有正在执行的 Task 变成孤儿）

---

## 问题 14：Token 预算与成本控制

> 来源：[[task-execution-completeness-and-implementation-analysis]] §A.2-8

### 场景

Anthropic 多 Agent 研究系统消耗 15x token。AgentHub 生产环境需要控制成本：

- 一次复杂任务的分解 + 执行可能消耗数十万 token
- 不同 Agent 使用不同模型（Opus → Sonnet → Haiku），成本差异大
- 用户没有无限预算

### 需要设计

**预算层级**：

```
TaskPlan 级预算（最外层）
  ├── 总 token 上限（默认 500K，可配置）
  ├── Coordinator 分解调用预算（单次 ≤ 50K）
  └── 超过总预算 → 停止执行，汇报已完成部分

Task 级预算（中间层）
  ├── 单 Task token 上限（默认 100K）
  ├── 按 estimated_complexity 分配：
  │     simple: ≤ 30K
  │     medium: ≤ 80K
  │     complex: ≤ 150K
  └── 超限 → TaskFailed(TOKEN_EXCEEDED) → replan 或降级到更简单方案

Agent 级预算（最内层）
  ├── Worker CLI session 单次 max_tokens 参数
  └── 模型选择策略：
        default: Haiku（日常）
        medium_task: Sonnet（中复杂度）
        complex_task: Opus（高复杂度，需显式标记）
```

**降级策略**：

| 预算超限层级 | 降级动作 |
|------------|---------|
| Agent 单次超限 | 切换模型（Opus → Sonnet → Haiku）重试 |
| Task 超限 | 触发 replan（拆分为更小的 Task） |
| TaskPlan 超限 | 停止执行，汇报已完成部分，标记剩余 Task 为 `cancelled` |

**用户可见**：
- TaskPlanCard 显示预算消耗进度条：「已用 234K / 500K tokens」
- 接近预算时（>80%）发系统警告消息
- 每个 Task 完成时汇报 token 消耗（已在问题 2 的 L3 信息层级中）

### 设计要点

- Token 计数来源：LLM API 响应的 `usage` 字段（精确）+ CLI session 的估算（近似）
- 预算超限不是错误，是预期的资源约束——用户应能看到"钱花在哪了"

---

## 问题 15：Worker 输出格式标准化

> 来源：[[task-execution-completeness-and-implementation-analysis]] §A.2-9

### 场景

当前设计 Task.result 是自由文本。但下游 Task 依赖上游 Task 的结构化输出：

- Task-1（搜索）→ JSON 结果 → Task-2（分析）需要解析 JSON
- 如果 Task-1 输出是自然语言"我找到了 3 个结果……" → Task-2 需要自己从文本中提取结构化数据
- AWS Builder 文章指出：结构化 Agent 间协议可将 token 消耗降低 70%

### 需要设计

**Task 输出 Schema**（在 TaskPlan 中声明）：

```python
class TaskDef:
    # ... 已有字段 ...
    expected_output_schema: dict | None  # JSON Schema
    # 例如：{"type": "object", "properties": {"files": {"type": "array"}}, "required": ["files"]}
```

**输出传递规则**：

```
Task-A (output_schema: FileList)
  → Harness 校验 output 是否符合 FileList schema
  → 符合 → 将结构化 output 注入 Task-B 的 prompt 上下文
  → 不符合 → 标记 Task-A 为 FAILED（L1 结构验证失败，见问题 8）

Task-B (depends_on: [Task-A])
  → prompt 中自动注入：## Task-A 的输出\n```json\n{task_a_output}\n```
```

**格式选项**：

| 格式 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| JSON Schema | 严格结构化数据 | 可自动校验、可被下游 Agent 的 tool_use 消费 | 要求 Agent 能输出合法 JSON |
| Markdown 模板 | 半结构化报告 | 灵活，人类易读 | 难以自动校验 |
| Key-Value | 简单状态传递 | 最简 | 表达能力有限 |
| File Path | 大文件传递 | 不占 context | 需要共享文件系统 |

### 建议方向

- Coordinator 在分解时为每个 Task 声明 `expected_output_schema`
- 首期支持 JSON Schema + Markdown
- 下游 Task 的 prompt 模板化：`## 上游 Task {id} 的输出\n{output}\n\n## 你的任务\n{description}`
- 参考 OpenAI structured outputs 的 `strict: true` 模式（JSON 合规性从 35% → 100%）

### 设计要点

- 输出格式标准化与问题 8（质量验证）是互补的：格式标准是"输出应该长什么样"，质量验证是"输出内容对不对"
- 格式校验在 Harness 层自动执行，不消耗额外 LLM 调用

---

## 问题 16：DAG 子树修复合并算法

> 来源：[[task-execution-completeness-and-implementation-analysis]] §A.2-7

### 场景

Coordinator.replan() 产出子树修复计划后，Harness 需要将其合并到正在运行的 DAG 中。

当前文档只说"将修复计划合并到原 DAG 中（替换失败子树）"，未定义合并算法。

### 需要设计

**合并策略矩阵**：

| 策略 | 操作 | 对运行中 Task 的影响 | 适用场景 |
|------|------|---------------------|---------|
| **REPLACE** | 用新子树完全替换失败子树 | 如果子树中还有 RUNNING Task → 先发送 cancel 信号，等优雅终止（5s timeout）→ 再替换 | 原方案完全不可行 |
| **INSERT_AFTER** | 在失败 Task 之后插入新的恢复路径 | 不终止运行中 Task | 只需补充额外步骤 |
| **RETRY_MODIFIED** | 保留原 Task 结构，修改 description/assignee/max_retries | 如果 Task 当前在 QUEUED → 更新参数后重新 dispatch | 原 Task 定义有问题（如分配了错误的 Worker） |
| **PRUNE** | 移除失败子树，将所有依赖该子树的 Task 直接 unblock | 被 prune 的 Task 中如果有 RUNNING → cancel | 该子树的结果非必需 |

**合并算法伪代码**：

```python
def merge_subtree_repair(
    original_dag: DAG,
    failed_subtree_root: TaskId,
    repair_plan: SubtreeRepairPlan,
    strategy: MergeStrategy
) -> DAG:
    # 1. 在 original_dag 中定位失败子树
    subtree = original_dag.get_subtree(failed_subtree_root)
    
    # 2. 根据策略处理运行中 Task
    running_tasks = [t for t in subtree if t.status == RUNNING]
    for t in running_tasks:
        if strategy == REPLACE or strategy == PRUNE:
            send_cancel_signal(t)
            wait_for_termination(t, timeout=5)
    
    # 3. 执行合并
    if strategy == REPLACE:
        original_dag.remove_subtree(failed_subtree_root)
        original_dag.attach_subtree(repair_plan.new_subtree, attach_point=failed_subtree_root.parents)
    elif strategy == INSERT_AFTER:
        original_dag.insert_after(failed_subtree_root, repair_plan.new_tasks)
    elif strategy == RETRY_MODIFIED:
        original_dag.update_task_params(failed_subtree_root, repair_plan.modifications)
    elif strategy == PRUNE:
        original_dag.remove_subtree(failed_subtree_root)
        for dep in original_dag.get_dependents(failed_subtree_root):
            dep.remove_dependency(failed_subtree_root)
    
    # 4. 重新校验 DAG（环检测 + 完整性）
    original_dag.validate()
    
    return original_dag
```

**约束**：

| 约束 | 说明 |
|------|------|
| 不可替换 COMPLETED Task | 已完成的结果是事实，不允许修改已有成功 Task |
| 合并后 DAG 必须无环 | Harness detect_cycle 重新校验 |
| 合并是原子操作 | 要么全部成功，要么保持原 DAG 不变（在临时副本上操作） |
| 合并写入 task_events | `taskplan_modified` 事件记录修改前后 DAG 结构 |

### 设计要点

- 合并操作是最危险的操作之一（涉及运行中 Task 的取消 + 新 Task 的注入），必须有完整的审计日志
- 如果合并后协调者又产出了修复计划（嵌套 replan），限制最大 replan 深度为 3

---

## 问题 17：资源调度与并发池化

> 来源：[[task-execution-completeness-and-implementation-analysis]] §A.2-10

### 场景

多个 TaskPlan 同时运行、多个用户同时使用 AgentHub：

- 全局最多同时运行几个 CLI session？
- 如何避免一个用户占满所有 Worker？
- GPU/内存资源如何分配？
- 多租户之间的隔离？

### 当前状态

问题 10 设计了单 TaskPlan 内的并发上限，但未涉及跨 TaskPlan 的全局资源调度。

### 需要设计

**资源池模型**：

```
全局资源池（Harness 管理）
├── Worker CLI session 池（最大 20 个，可配置）
│   ├── 保留（reserved）：2 个（系统/紧急任务）
│   └── 共享（shared）：18 个
│       ├── 单用户上限：5 个
│       └── 单 TaskPlan 上限：5 个
│
├── 模型调用配额
│   ├── Opus: 全局 3 并发
│   ├── Sonnet: 全局 10 并发
│   └── Haiku: 全局 20 并发
│
└── 文件系统资源
    └── 每个 Worker: 独立 git worktree（已在文件冲突 §3.3 设计中）
```

**调度策略**：

| 策略 | 描述 | 适用场景 |
|------|------|---------|
| **FIFO** | 先到先服务 | 默认 |
| **Priority** | TaskPlan 优先级（用户角色、紧急程度） | 生产环境 |
| **Fair Share** | 按用户均分资源 | 多租户 |
| **Deadline** | 有明确截止时间的 TaskPlan 优先 | 定时任务 |

**首期建议**：FIFO + 硬上限（全局 10 session，单用户 3 个）。

**资源超限处理**：

```
新 Task 需要 Worker 但池已满
  → 加入等待队列（QUEUED 状态，不占 session）
  → 等待位置显示在 TaskPanel：「排队中… 前方 2 个任务」
  → 超时（30 min 未获取资源）→ 通知用户并保持排队
```

### 设计要点

- Worker session 池不同于 HTTP 连接池：每个 CLI session 是一个独立进程（~200MB 内存），池大小受服务器内存限制
- 资源监控指标：活跃 session 数、排队 Task 数、平均等待时间 → Prometheus metrics
- 与问题 11 的僵尸清理协调：僵尸 session 占用池配额，必须及时回收

---

## 关联文档补充

- [[coordinator-requirement-gap-analysis]] 功能需求差距分析
- [[coordinator-research-report]] 业界调研报告
- [[task-execution-completeness-and-implementation-analysis]] 完整性审查+实现分析
- [[maf-implementation-analysis]] Microsoft Agent Framework 实现分析（含源码）

## 给下一位的交接

这些问题（1-17）都是 M3（任务编排落地）的前置设计问题。当前代码状态：
- `Coordinator` / `Harness` / `FSM` 是骨架（prompt 占位，Worker 执行未接入）
- `DiscussionOrchestrator` + `Selector` 已实现（群聊调度可用）
- `TaskBoard` 前端和后端 API 都是 stub
- `task_events` 表在设计文档中存在但未创建 migration

建议下一阶段：
1. 先对齐协调者设计（纯 LLM 调用，见 [[coordinator-design-decision]]）
2. 然后回答本文档三个问题
3. 最后才开始写 M3 代码
