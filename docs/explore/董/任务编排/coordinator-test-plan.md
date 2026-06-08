# Coordinator 任务模块 — 测试计划

> 日期：2026-06-05 | 基于：[[coordinator-dag-driven-design-v2]] §14.1 MVP
> 范围：协调者任务编排模块（DAG / 调度 / 事件循环 / 验证闸门 / 卡死检测）
> 框架：pytest（`pytest.mark.unit` / `integration` / `e2e`）；覆盖率目标 80%+

---

## 阅读指引

- 每条用例给 **Given / When / Then** 骨架，可直接落成 `test_*` 函数。
- 标 **[MVP]** 的是第一批必测；**[标准]** 留到并行/worktree 档再写。
- **先读 §0**——不做可测接缝，下面全部测不了。
- 测试哲学：测 **plumbing 不测 LLM 智商**。挡住坏 plan，不验证"LLM 产出好 plan"。

---

## §0 可测性接缝（实现第一件事，不是测试） [MVP]

协调者依赖的 4 个不确定源必须做成可注入接口。**这不是测试用例，是被测代码的设计前提。**

```python
# 被测构造函数应接受这些依赖（依赖倒置）
Coordinator(
    llm: LLMPort,            # plan/分类/final → 可注入假结构化响应
    worker_pool: WorkerPort, # 派发 → 假 worker：定输出 + 控时序 + 模拟挂死/打转/说谎
    clock: ClockPort,        # 卡死检测 → fake clock 手动推进
    harness: HarnessPort,    # 验证命令 → 跑 true/false 或 mock
)
```

| 接缝 | Fake 必须能模拟 |
|------|----------------|
| `LLMPort` | 合法 plan / **畸形 JSON** / 含环 plan / 悬空依赖 plan / 分类返回各 kind |
| `WorkerPort` | 正常完成 / 失败 / **自报 done 但产物错** / 超时静默 / 重复动作打转 |
| `ClockPort` | `now()` 可手动推进，不依赖真实墙钟 |
| `HarnessPort` | 验证 pass/fail（或真跑 `true`/`false`） |

> **验收 §0**：没有这 4 个 Port，任何下游用例都无法确定性运行 → §0 是 MVP 的 P0。

---

## §1 DAG 构建与校验 [MVP] `unit`

纯逻辑，最高 ROI，无需任何 IO。

### TC-1.1 合法 plan 编译为正确 DAG
- **Given** 一份合法 TaskLedger（t-1 无依赖，t-3 依赖 t-1/t-2）
- **When** `harness.validate(plan)`
- **Then** 返回 DAG，节点数=3，t-3 的 `deps == {t-1, t-2}`，全部 `status == PENDING`

### TC-1.2 环 → 拒绝
- **Given** plan 中 t-1 `depends_on=[t-2]` 且 t-2 `depends_on=[t-1]`
- **When** `validate`
- **Then** 抛 `DagCycleError`（或返回校验失败对象），**不返回可执行 DAG**

### TC-1.3 悬空依赖 → 拒绝
- **Given** t-3 `depends_on=[t-99]`，t-99 不存在
- **When** `validate`
- **Then** 校验失败，错误指明缺失的 `t-99`

### TC-1.4 worker 不存在 → 拒绝
- **Given** t-1 `suggested_worker="不存在Agent"`，registry 无此项
- **When** `validate`
- **Then** 校验失败，错误指明未知 worker

### TC-1.5 畸形 JSON → 容错解析
- **Given** LLMPort 返回 ```` ```json {tasks:[...]} ``` ````（含 code fence / Python 关键字 `True`）
- **When** `Coordinator.plan()`
- **Then** 多层回退解析成功（code fence 剥离 / `True→true`）；若彻底无法解析 → 触发重试，重试耗尽抛明确错误，**不静默吞**

### TC-1.6 无 acceptance → 标 unverified，不静默通过
- **Given** t-1 的 `acceptance == []` 且未显式标 `no-verify`
- **When** `validate`
- **Then** t-1 标记为不可自动 VERIFIED（需人工或显式豁免），且该状态在产出里**可见**

---

## §2 调度 / frontier [MVP] `unit`

纯函数，确定性。**至少一条 property test。**

### TC-2.1 无依赖全就绪
- **Given** DAG 三节点均 `depends_on=[]`，全 PENDING
- **When** `compute_frontier(dag)`
- **Then** 返回 {t-1, t-2, t-3}

### TC-2.2 依赖未满足则阻塞
- **Given** t-3 依赖 t-1/t-2，二者 PENDING
- **When** `compute_frontier`
- **Then** 返回 {t-1, t-2}，**不含 t-3**

### TC-2.3 部分完成解锁下游
- **Given** t-1=VERIFIED，t-2=VERIFIED，t-3 PENDING 依赖二者
- **When** `compute_frontier`
- **Then** 返回 {t-3}

### TC-2.4 串行 MVP：并发=1 只派一个 [MVP 关键]
- **Given** frontier={t-1, t-2}，`max_concurrency=1`
- **When** `dispatch_frontier`
- **Then** 仅 1 个进入 RUNNING，另一个仍 PENDING 排队

### TC-2.5 上游失败 → 下游 BLOCKED（非 FAILED）
- **Given** t-1=FAILED，t-3 依赖 t-1
- **When** 重算 frontier / 状态传播
- **Then** t-3.status == **BLOCKED**（不是 FAILED，不是 PENDING）

### TC-2.6 确定性（property）
- **Given** 任意合法 DAG 状态快照
- **When** 对同一快照调 `compute_frontier` 两次
- **Then** 两次结果完全相等（无随机、无顺序依赖）

---

## §3 任务 FSM 状态转移 [MVP] `unit`

表驱动（`pytest.mark.parametrize`）。

### TC-3.1 合法转移放行
- **Given/When/Then**（参数化）：
  `PENDING→RUNNING` ✓，`RUNNING→VERIFYING` ✓，`VERIFYING→VERIFIED` ✓，`VERIFYING→FAILED` ✓，`RUNNING→FAILED` ✓，`FAILED→PENDING`(retry) ✓，`BLOCKED→PENDING`(上游修复) ✓

### TC-3.2 非法转移拒绝
- **Given** 节点处于 PENDING
- **When** 试图直接 →VERIFIED
- **Then** 抛 `IllegalTransition`，状态不变

### TC-3.3 retry 计数自增
- **Given** t-1 FAILED，`retries=0`
- **When** retry → PENDING
- **Then** `retries == 1`；重复至 `max_retries` 后再 fail → 不再回 PENDING，转升级路径

### TC-3.4 终态不可再转移
- **Given** t-1=VERIFIED
- **When** 任何转移尝试
- **Then** 拒绝（VERIFIED 是终态）

---

## §4 验证闸门 [MVP] `integration`

**v2 相对 v1 的命门，单独重点测。**

### TC-4.1 说谎 worker 必须判 FAILED [MVP 命门]
- **Given** WorkerPort 注入一个 worker，**自报 `done` 但其 acceptance 命令返回 `false`**
- **When** `verify_and_settle(t)`
- **Then** t.status == **FAILED**，捕获 `fail_reason`，**绝不 VERIFIED**

### TC-4.2 机械验证通过 → VERIFIED
- **Given** worker 完成，acceptance 命令返回 `true`（exit 0）
- **When** `verify_and_settle`
- **Then** t.status==VERIFIED，产出增量摘要写入 `task_events`

### TC-4.3 验证在任务环境内跑，不污染主目录
- **Given** 任务有 worktree（标准）或隔离工作目录
- **When** 验证命令执行
- **Then** 命令 cwd 是任务环境，主仓未被改动（断言主目录无副作用）

### TC-4.4 失败原因回灌
- **Given** acceptance 失败，stderr="测试 X 不通过"
- **When** verify 失败 → 进入 retry
- **Then** 下一次 dispatch 的 instruction 含该失败原因

---

## §5 事件循环 / 单写者 / 事件溯源 [MVP] `integration`

### TC-5.1 并发回调不污染 state
- **Given** 两个 worker 几乎同时 emit `WorkerDone`
- **When** 事件经单写者 event_bus 串行处理
- **Then** 最终 state 一致、无丢失更新；无论 emit 顺序，结果确定

### TC-5.2 事件重放重建相同 state [事件溯源不变量]
- **Given** 一次完整运行产生的 `task_events` 序列
- **When** 从空 state 重放全部事件
- **Then** 重建 state 与运行结束时的 state **逐字段相等**

### TC-5.3 中途崩溃后恢复
- **Given** 运行到一半的 `task_events`（部分 VERIFIED，1 个 RUNNING）
- **When** 重放恢复
- **Then** 状态正确还原；RUNNING 任务按策略重派或标失败（明确其一并测）

---

## §6 卡死检测 [MVP 仅硬超时] `unit`（fake clock）

### TC-6.1 墙钟上限触发超时 [MVP]
- **Given** t-1 RUNNING，`wall_limit=60s`，worker 仍在吐事件
- **When** fake clock 推进到 61s
- **Then** emit `WorkerTimeout(t-1)`，即使心跳活跃也截停

### TC-6.2 token 预算上限触发 [MVP]
- **Given** t-1 累计 token 超 `token_limit`
- **When** 检查
- **Then** `WorkerTimeout`，记录 budget 原因

### TC-6.3 条件化静默阈值 [标准]
- **Given** `last_action="bash:npm install"`（容忍 120s）vs `last_action="edit"`（30s）
- **When** clock 推进
- **Then** install 在 119s 不触发、edit 在 31s 触发

### TC-6.4 thinking 非静默 [标准]
- **Given** worker 持续吐 thinking 事件、无 tool/text
- **When** clock 推进超普通静默阈值
- **Then** **不触发**超时（thinking 是存活信号）

### TC-6.5 重复动作 → WorkerLoop [标准]
- **Given** 同 `(tool_name, args_hash)` 连续重复 > K 次
- **When** 检测
- **Then** emit `WorkerLoop(t)`

---

## §7 失败 / retry / replan [MVP 仅 retry] `integration`

### TC-7.1 retry 复用环境 + 注入失败原因 [MVP]
- **Given** t-1 第一次 FAILED
- **When** retry
- **Then** 复用其工作目录，instruction 含上次 `fail_reason`，`retries` 自增

### TC-7.2 retry 耗尽 → 升级 [MVP]
- **Given** t-1 retry 达 `max_retries` 仍 FAILED
- **When** 再次失败
- **Then** MVP：发系统消息求助用户并停在该任务（不死循环）

### TC-7.3 replan 子树作用域 [标准]
- **Given** 10 节点 DAG，t-7 失败
- **When** 构建 replan 上下文
- **Then** 上下文含 {t-7 全文 + 其直接依赖 + 下游}，**其余仅标题状态**（断言无关任务未注入全文）

### TC-7.4 replan_count 守卫 [标准]
- **Given** replan 反复触发达 `max_resets`
- **When** 再次触发
- **Then** 退出码 `stalled_repeatedly` / `max_resets`，不无限 replan

---

## §8 退出条件 [MVP] `unit`/`integration`

### TC-8.1 全 VERIFIED + 集成通过 → completed
- **Given** 所有节点 VERIFIED，集成验证 pass（MVP 串行可跳集成）
- **When** `terminal_check`
- **Then** 退出码 `completed`，触发 final_answer

### TC-8.2 各异常退出码
- **参数化**：budget 耗尽→`budget_exceeded`；replan 耗尽→`max_resets`；用户取消→`user_cancelled`；DAG 损坏→`irrecoverable_error`

---

## §9 端到端（场景即测试）[MVP] `e2e`

### TC-9.1 登录页场景串行跑通
- **Given** mock LLM（产出 3 任务 DAG）+ mock workers（确定产物，全部 acceptance pass）
- **When** `Coordinator.coordinate()` 串行执行到底
- **Then** 三节点全 VERIFIED，退出码 `completed`，final_answer 含三任务摘要；断言 LLM 调用次数 == 预期（plan 2 + final 1，无每轮税）

### TC-9.2 场景中一任务失败→retry→成功
- **Given** mock worker 让 t-1 首次 acceptance fail、retry 后 pass
- **When** 执行
- **Then** 最终 completed，`t-1.retries==1`，事件序列含 FAILED→PENDING→VERIFIED

---

## §10 Selector 接线（A1/A2）[MVP 部分] `unit`

### TC-10.1 decompose 预闸门命中 [MVP]
- **Given** DISCUSSION 态，消息="帮我创建登录页面"（含工作动词）
- **When** `pick(active_coordinator=None)`
- **Then** 机械预滤命中 → llm_intent_check 返回 decompose → `SelectorDecision.decompose()`

### TC-10.2 纯讨论不触发、不加 LLM [MVP 回归]
- **Given** 消息="我觉得用 React 比较好"（无工作动词）
- **When** `pick`
- **Then** 机械预滤**未命中** → **不调 intent LLM** → 走原有 L1/L1.5/L2/L3 发言选择（断言 LLMPort.intent_check 调用次数==0）

### TC-10.3 执行期 control 机械取消 [MVP]
- **Given** EXECUTION 态，消息="停"
- **When** `pick(active_coordinator=coord)`
- **Then** `is_control` 命中 → `interrupt(kind="control")`，**零 LLM**

### TC-10.4 执行期非 control 插话 MVP 排队 [MVP]
- **Given** EXECUTION 态，消息="加个限流"（非 control）
- **When** `pick`
- **Then** MVP：排队/忽略，不触发图变更（A2 分类是标准档）

### TC-10.5 question/modification 分类 [标准]
- **参数化**："做完了吗"→question；"换个方案"→modification；闲聊→discussion

---

## §11 worktree / 集成 [标准] `integration`（需 git）

### TC-11.1 每任务独立 worktree、改动隔离
- **Given** 两并行任务
- **When** 各自 dispatch
- **Then** 各在 `.wt/<id>`，互不可见对方改动直到 merge

### TC-11.2 merge 冲突被显式检测（非静默）
- **Given** 两任务改同文件重叠行
- **When** 串行 merge 第二个
- **Then** git 报冲突 → 触发 rebase+重 verify / replan，**不静默丢更新**

### TC-11.3 worktree base 陈旧处理
- **Given** t-2 已 merge 进 integration_ref，t-1 worktree 基于旧 ref
- **When** t-1 完成待 merge
- **Then** 先 rebase 到新 integration_ref 再 verify（断言基已更新）

### TC-11.4 集成验证闸门
- **Given** 各任务局部测试通过、已全 merge
- **When** `integration_gate`
- **Then** 跑全量 build+test；失败 → 不标 satisfied，定位冲突任务对

### TC-11.5 共享副作用不被 worktree 隔离（警示用例）
- **Given** 两后端任务测试都打共享 dev DB
- **When** 并行跑
- **Then** 验证测试隔离策略（独立 schema/事务）生效，否则记为已知限制并暴露

---

## §12 不要测的（明确划线）

- **LLM 的分解质量** —— 模型的活，不可单测。测"坏 plan 被挡"（§1），不测"好 plan 被产出"。
- **LLM 评审的语义正确性** —— 测 reviewer 被正确调用 + 其 verdict 被正确消费，不测它判得对不对。
- **真实 CLI worker 行为** —— 用 fake worker；真 CLI 留到手动/集成冒烟，不进单测。

---

## 测试金字塔与优先级

```
        e2e (§9)         ← 2-3 条，mock LLM+worker，跑通主链路
      ───────────
   integration (§4,5,7)  ← 验证闸门 / 事件溯源 / 单写者
  ─────────────────────
 unit (§1,2,3,6,8,10)    ← DAG/frontier/FSM/退出码/Selector，最厚一层
```

**MVP 第一批落地顺序**：§0 接缝 → §1 → §2 → §3 → §4（命门 TC-4.1）→ §8 → §9.1 端到端。
§5/§6/§7/§10 紧随。§11 及各 [标准] 用例随并行档启动再写。

---

## 关联文档

- [[coordinator-dag-driven-design-v2]] 设计稿 v2.2（含 §14 落地分级、§13.5 A 类定论）
- [[scenario-walkthrough-v2]] 场景推演（e2e 用例 §9 的剧本来源）
