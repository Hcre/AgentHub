# 场景推演 v2 — DAG 驱动 + 事件循环

> 日期：2026-06-05 | 基于：[[coordinator-dag-driven-design-v2]]
> 场景：用户要求创建登录页面（同 [[scenario-walkthrough]] 场景）

---

## 场景设定

群组成员：用户、Selector、Coordinator（临时）、前端 Agent、后端 Agent、测试 Agent

群聊上下文：之前用户在讨论登录方案，群里达成了共识——React + TypeScript + FastAPI + Tailwind CSS

---

## Phase 0：Selector 常驻前门（DISCUSSION 态）

```
用户: "帮我创建登录页面，支持邮箱密码登录，错误提示用中文，连续5次失败锁定30分钟"
```

**Selector.pick()**：

```
L1 @mention:  无 @ 前缀
L1.5 broadcast: 非广播消息
L2 capability: 消息包含"创建"、"登录"、"邮箱" → 可能匹配多个 Agent
L3 LLM 判断:  消息包含工作执行意图 → decision = decompose
```

**产出的 SelectorDecision**：
- `decision = decompose`
- `target = None`（Coordinator 不是群成员，是引擎）

**ChatService 收到 decompose**：

```
1. ContextHandoff 启动
   → 从完整群聊历史（不是 Selector 截的 15 条）+ L1 memory
   → 构建结构化交接产物

2. ContextHandoff 产出：
   {
     "task": "创建登录页面，邮箱+密码+中文错误提示，5次失败锁定30分钟",
     "constraints": [
       "错误提示用中文",
       "连续5次失败 → 锁定30分钟",
       "UI 框架：React + Tailwind CSS（群聊已确认）",
       "后端：FastAPI + JWT（群聊已确认）"
     ],
     "context": {
       "repo_structure": "frontend/src/components/..., backend/app/api/...",
       "existing_auth": "无，从零创建",
       "design_doc": null
     }
   }

3. Coordinator 被 spawn（临时引擎，不是群成员）
4. registry.register(session_id, coordinator_run)
5. Selector 下次 pick 时会收到 active_coordinator 参数
```

**前端显示**：用户消息正常显示。Coordinator 不发消息（它是引擎，不是人）。

---

## Phase 1：Plan（LLM ×2）

**Coordinator.plan()**：

```
调用 1 — facts 分析:
  输入: 结构化交接产物 + 代码仓库结构（Coordinator 通过 Read/Grep 工具读取）
  
  产出:
    已知:
    - 登录页面，邮箱+密码认证
    - React + Tailwind CSS 前端，FastAPI 后端，JWT
    - 无已有 auth 代码，从零创建
    - 错误提示中文，5次失败锁定30分钟
    
    待确认:
    - 表单组件库？群聊确认了 Tailwind CSS，直接用原生 HTML 表单 + Tailwind 样式
    - 是否需要验证邮箱格式？需求未提及 → 假设需要前端格式校验

调用 2 — plan 制定:
  输入: facts + 可用 Agent registry（前端Agent/后端Agent/测试Agent）
  
  产出 TaskLedger:
    tasks:
      t-1:
        title: "创建 LoginForm 组件"
        suggested_worker: "前端Agent"
        depends_on: []
        acceptance:
          - {kind: mechanical, spec: "npx tsc --noEmit", expect: "exit 0"}
          - {kind: mechanical, spec: "npm run build", expect: "exit 0"}
          - {kind: llm_judge, spec: "检查：组件包含邮箱输入（含格式校验）、密码输入（最少6位）、
             登录按钮、错误展示区（中文）。使用 Tailwind CSS 样式"}
        side_effect_level: readonly
      
      t-2:
        title: "创建 /api/auth/login 端点"
        suggested_worker: "后端Agent"
        depends_on: []
        acceptance:
          - {kind: mechanical, spec: "python -m pytest tests/unit/test_auth.py -x", expect: "exit 0"}
          - {kind: llm_judge, spec: "检查：POST 端点接收 email+password，返回 JWT，
             错误返回中文提示。退出码非 0 时返回对应错误信息"}
        side_effect_level: mutable
      
      t-3:
        title: "创建登录流程 E2E 测试"
        suggested_worker: "测试Agent"
        depends_on: ["t-1", "t-2"]    ← 汇聚点
        acceptance:
          - {kind: mechanical, spec: "python -m pytest tests/e2e/test_login.py -v", expect: "exit 0"}
          - {kind: llm_judge, spec: "检查：覆盖正确登录、错误邮箱、错误密码、空字段、
             5次失败锁定、锁定后正确密码也无法登录"}
        side_effect_level: readonly

  DAG 校验: Harness 校验 depends_on 引用合法，无环 ✓

  plan 策略:
    - t-1 拥有 frontend/src/components/
    - t-2 拥有 backend/app/api/
    - t-3 拥有 tests/e2e/
    模块边界不相交 → 集成期语义冲突面小
```

**群聊显示**：

```
[系统]: 📋 Coordinator 已生成执行计划

┌─ TaskPlanCard ───────────────────────────┐
│ 创建登录页面                              │
│ ░░░░░░░░░░░░░░░░░░░░ 0/3                │
│                                          │
│ ⚪ t-1  LoginForm 组件          等待中     │
│ ⚪ t-2  /api/auth/login 端点    等待中     │
│ ⚪ t-3  E2E 测试             等待中       │
│        ↳ 依赖 t-1, t-2                  │
└──────────────────────────────────────────┘
```

**LLM 调用**：2 次（facts + plan）

---

## Phase 2：dispatch_frontier（DAG 纯函数，零 LLM）

**DAG.compute_frontier()**：

```
就绪检查:
  t-1: depends_on=[] → 就绪 ✓
  t-2: depends_on=[] → 就绪 ✓
  t-3: depends_on=["t-1","t-2"], t-1=PENDING, t-2=PENDING → 阻塞

并发检查:
  t-1 拥有 frontend/src/components/
  t-2 拥有 backend/app/api/
  模块边界不相交 → 可并行 ✓

全局并发上限: max 5 per run, 单 agent max 2 → t-1 + t-2 = 2, 不超 ✓

dispatch:
  t-1 → git worktree add .wt/t-1 <integration_ref>
         dispatch_worker("前端Agent", worktree=.wt/t-1, instruction=...)
         status → RUNNING, health.start()

  t-2 → git worktree add .wt/t-2 <integration_ref>
         dispatch_worker("后端Agent", worktree=.wt/t-2, instruction=...)
         status → RUNNING, health.start()
```

**dispatch 的 instruction 模板**（来自 TaskDef，不是 LLM 生成）：

```
前端Agent 收到的 instruction:
  任务: 创建 LoginForm 组件
  描述: 邮箱+密码+中文错误提示，React + Tailwind CSS
  验收: npx tsc --noEmit 通过，npm run build 通过，LLM 评审样式和错误文案
  工作目录: .wt/t-1（你的修改只能在这个目录里）
  约束:
    - 错误提示必须用中文
    - 邮箱需要格式校验
    - 密码最少 6 位

后端Agent 收到的 instruction:
  任务: 创建 /api/auth/login 端点
  描述: 接收 email+password，返回 JWT，中文错误提示
  验收: pytest 通过，LLM 评审错误文案
  约束:
    - POST /api/auth/login
    - 错误返回中文提示
    - 5次失败 → 锁定 30 分钟
```

**群聊显示**：

```
[TaskPlanCard 更新]:
🟡 t-1  LoginForm 组件          执行中
🟡 t-2  /api/auth/login 端点    执行中
⚪ t-3  E2E 测试             等待中
```

**LLM 调用**：0 次。调度是纯函数。

---

## Phase 3：并行执行 + 四层机械监控

```
时间 T+5s ~ T+50s

前端Agent（.wt/t-1）:
  流式输出: thinking → write LoginForm.tsx → tsc check → fix → build
  health.last_progress_ts 持续刷新
  
后端Agent（.wt/t-2）:
  流式输出: thinking → write auth.py → write test_auth.py → pytest → fix → pass
  health.last_progress_ts 持续刷新

机械监控（Harness 后台协程）:
  - t-1: 心跳活跃（最新事件 2s 前 → ok）
  - t-2: 心跳活跃（最新事件 3s 前 → ok）
  - 静默阈值：上次事件=edit_file → 期望 30s 内有下一个事件
              上次事件=bash:npm install → 容忍 120s
              上次事件=thinking → 不检查（thinking 本身是事件流）
```

**T+25s，后端 Agent 先完成**：

```
WorkerDone(t-2) 事件入 event_bus

→ verify_and_settle(t-2):
    1. t-2.status → VERIFYING
    2. 机械验收:
       running: python -m pytest tests/unit/test_auth.py -x
       → 3 passed in 2.3s → exit 0 ✓
    3. LLM 评审（独立 Reviewer agent，不是后端Agent）:
       "错误提示是否都是中文？5次锁定实现是否正确？"
       → Reviewer 读 diff + 跑测试 → 通过 ✓
    4. 全部验收通过 → merge worktree .wt/t-2 → integration_ref
    5. t-2.status → VERIFIED
    6. t-2 产出摘要: "创建了 POST /api/auth/login，3个测试通过，
       错误文案:'邮箱格式不正确'/'密码错误'/'用户不存在'/'账户已锁定'"
       ← 增量产出，存进 task_events
    7. 释放 .wt/t-2 资源
    
→ dispatch_frontier():
    t-1 还在 RUNNING → t-3 deps 未全满足 → 无新就绪节点
```

**群聊显示**：

```
[系统]: ✅ t-2 /api/auth/login 端点完成（耗时 25s）

[TaskPlanCard 更新]:
🟡 t-1  LoginForm 组件          执行中
🟢 t-2  /api/auth/login 端点    已完成 ✓
⚪ t-3  E2E 测试             等待中
```

**T+40s，用户插话**：

```
[用户]: @Coordinator 后端有没有加登录失败次数限制？连续5次锁定30分钟
```

**消息到达 ChatService**：

```
Selector.pick(messages, active_coordinator=registry.get(session)):
  active_coordinator 非空 → EXECUTION 态
  消息目标 @Coordinator → 机械识别为"控制消息"
  → 不分类为普通对话
  → 直接转发到 active_coordinator（UserInterrupt 事件）
```

**Coordinator 收到 UserInterrupt**：

```
match UserInterrupt(msg):
    # msg 是 "@Coordinator 后端有没有加…"
    # 这不是改需求，是提问
    
    # read_dag_state(): t-2 已 VERIFIED，验收结果里包含:
    #   "错误文案中包含'账户已锁定'"
    #   → 锁定逻辑已实现 ✓
    
    # 直接机械回答，零 LLM:
    → 往群聊转录发一条 Coordinator 消息:
      "已确认：t-2 实现了失败次数限制，连续5次 → 锁定30分钟。
       验收时已验证返回'账户已锁定'错误提示。"
```

**群聊显示**：

```
[Coordinator]: 已确认：t-2 实现了失败次数限制，连续5次 → 锁定30分钟。
验收时已验证返回"账户已锁定"错误提示。

（这条消息写入群聊转录——三流中的"群聊转录"流。
 Coordinator 工作上下文不受影响，t-1 继续跑。）
```

**关键差异**：v1 的 Coordinator 需要停下循环来回这条消息，或者把它排队。v2 的 Coordinator 是一个事件处理器，插话就是普通事件，不阻塞正在跑的 Task。**t-1 没被打断。**

**T+50s，前端 Agent 完成**：

```
WorkerDone(t-1) 事件 → verify_and_settle(t-1):
  机械: npx tsc --noEmit → exit 0 ✓
         npm run build → exit 0 ✓
  LLM 评审: Reviewer 读 diff → 检查中文错误提示、Tailwind 样式、邮箱格式校验
           → Reviewer 发现: "忘记密码"链接文案是英文 "Forgot password?"
           → fail: {llm_judge, reason: "错误文案不是中文"}
  
  → t-1.fail_reason = "LLM 评审未通过: '忘记密码'链接文案为英文"
  → emit WorkerFailed(t-1)
```

**LLM 调用**：1 次（LLM 评审）。

---

## Phase 4：失败处理 — replan

```
WorkerFailed(t-1) 事件:

handle_failure(t-1):
  retries=0 < max_retries(3)
  → t-1.retries = 1
  → t-1.status → PENDING（重新入队）
  → 在 t-1 的 worktree 内，给失败原因注入到 instruction:
    "上次验收失败：'忘记密码'链接文案为英文，请改为中文。其他部分通过。"
  → dispatch_worker("前端Agent", worktree=.wt/t-1（复用）, instruction=...)
  
  ← 这是 retry，不是 replan。replan 是 retry 耗尽 + 机械检测判需要 LLM 重判时才触发。
```

**T+65s，前端 Agent 第二次完成**：

```
WorkerDone(t-1) →
  verify_and_settle(t-1):
    机械: ✓
    LLM 评审: "所有文案均为中文" ✓
  → t-1.status → VERIFIED
  → merge worktree .wt/t-1 → integration_ref
  → 产出摘要
```

**群聊显示**：

```
[系统]: 🔄 t-1 第一次验收未通过（忘记密码链接为英文），已自动修正
[系统]: ✅ t-1 LoginForm 组件完成（总耗时 65s，含 1 次修正）

[TaskPlanCard]:
🟢 t-1  LoginForm 组件          已完成 ✓
🟢 t-2  /api/auth/login 端点    已完成 ✓
⚪ t-3  E2E 测试             等待中
```

---

## Phase 5：汇聚点回顾（里程碑 LLM）

```
dispatch_frontier():
  t-3 deps = [t-1, t-2]，均为 VERIFIED → 就绪 ✓

但 t-3 是汇聚点（fan-in 节点）。
在 dispatch 前，触发汇聚点中期回顾:

still_on_track = coordinator.review_milestone(state):
  输入: t-1 摘要 + t-2 摘要 + 原始约束清单 + DAG 剩余结构
  判断: "t-1 和 t-2 的产出是否覆盖了所有约束？是否有遗漏？"
  
  LLM 分析:
    ✅ 邮箱+密码登录（t-1 + t-2 覆盖）
    ✅ 中文错误提示（t-1 + t-2 覆盖，验收已验证）
    ✅ 5次锁定30分钟（t-2 覆盖）
    ✅ JWT（t-2 覆盖）
    
    计划之外的情况:
    - t-1 产出了"忘记密码"链接，但需求未提及 → 额外功能，移除？
    
  产出: "所有约束已满足。t-1 额外添加了'忘记密码'链接（非需求），
        建议保留——不影响主流程且有用户价值。继续 t-3。"

→ dispatch_worker("测试Agent", worktree=.wt/t-3, instruction=...)
```

**LLM 调用**：1 次（汇聚点回顾）。

---

## Phase 6：测试执行

```
测试Agent（.wt/t-3）:
  → write tests/e2e/test_login.py
  → 覆盖: 正确登录、错误邮箱、错误密码、空字段、5次锁定、锁定后正确密码

verify_and_settle(t-3):
  机械: python -m pytest tests/e2e/test_login.py -v
        → 6 passed in 8.5s ✓
  LLM 评审: "所有场景覆盖，测试验证了中文错误提示和锁定逻辑" ✓
  → VERIFIED
  → merge worktree .wt/t-3 → integration_ref
```

---

## Phase 7：集成验证 + final_answer

```
所有 Task VERIFIED → terminal_check = AllDone

集成验证（机械，零 LLM）:
  在集成分支（已含 t-1, t-2, t-3 全部 merge）:
    tsc --noEmit → exit 0 ✓
    npm run build → exit 0 ✓
    pytest → 全部通过 ✓

Coordinator.final_answer()  ← LLM ×1:

  输入: 所有 Task 的摘要 + 约束清单 + 集成验证结果
  
  产出（写入群聊转录）:

  "登录页面创建完成 ✅

  创建的文件：
  - frontend/src/components/LoginForm.tsx
    （邮箱+密码+中文错误提示 + Tailwind CSS）
  - backend/app/api/auth.py
    （POST /api/auth/login，JWT，5次锁定30分钟）
  - tests/e2e/test_login.py（6 个测试全部通过）

  约束验证：
  ✅ 中文错误提示 → 已验收
  ✅ 邮箱格式校验 → 已验收
  ✅ 5次失败锁定 → 已验收
  ✅ 密码最少6位 → 已验收
  ✅ TypeScript 编译通过 → 已验收
  ✅ 全量集成测试通过 → 已验收

  额外说明：
  - 前端额外添加了"忘记密码"链接（非需求，已保留）

  共 3 个 Worker 任务，Coordinator LLM 调用 4 次，Worker 总计 ~45K tokens"

→ registry.unregister(session_id)
→ Coordinator 销毁，回到 DISCUSSION 态
```

**群聊显示**：

```
[Coordinator]: 登录页面创建完成 ✅
（上面摘要）

[TaskPlanCard 最终]:
🟢 t-1  LoginForm 组件          已完成 ✓
🟢 t-2  /api/auth/login 端点    已完成 ✓
🟢 t-3  E2E 测试             已完成 ✓
进度: 3/3  ████████████████ 100%
```

---

## LLM 调用总结

| 阶段 | 调用 | 次数 | 触发 |
|------|------|:---:|------|
| plan | facts + plan | 2 | 必选 |
| t-1 验收 | llm_judge（Reviewer） | 1 | 如果有机 mechanical 覆盖不到 |
| t-2 验收 | llm_judge（Reviewer） | 1 | 同上 |
| t-1 重试验收 | llm_judge（Reviewer） | 1 | 同上 |
| 汇聚点回顾 | still_on_track | 1 | t-3 是 fan-in 节点 |
| t-3 验收 | llm_judge（Reviewer） | 1 | 同上 |
| final | final_answer | 1 | 必选 |
| **合计** | | **8** | |

对比 v1（6 次）：

| | v1 | v2 |
|---|---|---|
| plan | 2 | 2 |
| 每轮 progress_ledger | 3 | **0**（调度纯函数） |
| 汇聚点回顾 | 0 | **1**（新增，防止方向错误） |
| llm_judge 验收 | 0（v1 不验证） | **4**（独立 reviewer） |
| final | 1 | 1 |
| **合计** | **6** | **8** |

v2 的 LLM 次数是 8 次，比 v1 多 2 次——多出来的是独立验证（4 次 reviewer）和汇聚点回顾（1 次），省了 3 次 progress_ledger。

**但实际上能省**：
- 如果 t-1 和 t-2 只设 mechanical 验收（tsc/pytest），不需要 llm_judge → 省 3 次
- 汇聚点回顾如果不是 fan-in 节点（无依赖合并），可跳过
- 最优路径（全 mechanical 验证 + 无汇聚点）：2+1=3 次（plan + final）

**真正的收益不在 LLM 次数，在 LLM 的用途**：
- v1 的 3 次 progress_ledger 花在"谁该干活"——v2 花在"活干得对不对"
- 前者是调度决策（DAG 已经做了），后者是质量保证（v1 完全没有）

---

## 与 v1 推演的关键差异

| 时刻 | v1 发生了什么 | v2 发生了什么 | 差异 |
|------|-------------|-------------|------|
| 用户插话 "@Coordinator 后端有没有加锁定" | Coordinatior 在循环里，需要决定：打断 wave 还是排队 | Coordinator 读 DAG 状态，机械回答，不打断 t-1 | v2 不阻塞执行 |
| t-1 "忘记密码"是英文 | v1 的 progress_ledger 不知道（它不读验收结果） | llm_judge 评审抓到 → 自动 retry | v2 有验证，v1 依赖 Worker 自报 |
| 后端完成→谁调度 t-3 | v1 等下一轮 progress_ledger LLM 调用才选 t-3 | dispatch_frontier() 纯函数立即算：t-1 还在跑→t-3 不就绪 | v2 确定性，v1 有延迟 |
| 两个 Worker 同时跑 | v1 用 can_parallel 声明文件检查 | v2 用 worktree 隔离，文件物理隔离 | v2 不依赖 LLM 声明的文件列表 |
| 全部完成后 | v1 final_answer 汇总 Worker 的自报结果 | v2 先跑集成测试 → final_answer 读机械验证结果 | v2 的 final_answer 读的是 ground truth |

---

## 本次推演暴露的问题

| # | 问题 | 严重度 |
|---|------|:---:|
| 1 | llm_judge 验收次数取决于 Task 数量——3 个 Task 就要 3 次 reviewer 调用。可以用 mechanical 替代时跳过，但并非所有场景都能替代 | 中 |
| 2 | 汇聚点回顾在 t-3 这种单任务场景价值有限（只有 1 条依赖链）。真正的价值在多分支汇聚时（如 5 个并行分支汇入 1 个） | 低 |
| 3 | 用户插话"做得怎么样了"→ 机械回答没问题。但用户插话"换个方案，前后端合并为一个服务"→ 这就是图变更 = LLM，但 v2 没说"改需求"和"提问"的分界怎么判 | 中 |
| 4 | retry 复用原有 worktree——如果 Agent 第一次把 worktree 搞乱了（删了不该删的文件），复用 worktree 可能导致第二次也失败 | 中 |
