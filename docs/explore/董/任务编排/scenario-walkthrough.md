# 场景推演：协调者循环 + 并行 wave 模式

> 日期：2026-06-04 | 基于：[[coordinator-design-evolution]]

---

## 场景：用户要求创建登录页面

群组成员：用户、Coordinator、Selector、前端 Agent（React 专家）、后端 Agent（FastAPI 专家）、测试 Agent

---

### Phase 1：任务触发

```
时间  T+0s

[用户]: 帮我创建一个登录页面，支持邮箱密码登录，错误提示用中文
```

**Selector 判断**：
- 消息包含"创建"、"登录页面" → 工作执行意图
- 决策：`decompose`（触发协调者）

**发生了什么**：
- Selector 返回 `decision = "decompose"`
- DiscussionOrchestrator 收到 → 调用 Coordinator 启动

**前端显示**：群聊正常显示用户消息。Coordinator 头像出现「正在思考…」loading。

**待定**：DiscussionOrchestrator 此时是暂停讨论循环，还是继续运行？Coordinator 接管后 Selector 还路由消息吗？（见 `coordinator-design-evolution.md` §4.3）

---

### Phase 2：Plan（外循环）

```
时间  T+2s
```

**Coordinator 内部**：

```
manager.plan()
  │
  ├─ facts 分析  ← LLM 调用 1
  │     "已知：用户需要登录页面，邮箱+密码，中文错误提示
  │      需要确认：登录 API 是否已有？UI 框架是 React 还是 Vue？
  │      需要推导：需要表单组件、状态管理、API 调用、错误处理"
  │
  └─ plan 制定  ← LLM 调用 2
        "1. 前端 Agent：创建 LoginForm 组件（邮箱/密码输入、验证、错误展示）
         2. 后端 Agent：创建 /api/auth/login 端点（邮箱密码验证、JWT 签发）
         3. 测试 Agent：编写登录流程 E2E 测试
         依赖：Task-3 依赖 Task-1 和 Task-2 都完成
         并行：Task-1 和 Task-2 无依赖，可同时执行"

产出 TaskLedger {facts, plan}
```

**群聊显示**：

```
[Coordinator]: 📋 任务分解完成

已知信息：
- 登录页面，邮箱+密码认证，中文错误提示
- 使用 React + FastAPI 技术栈

执行计划：
1. 前端 Agent → 创建 LoginForm 组件
2. 后端 Agent → 创建 /api/auth/login 端点
3. 测试 Agent → 编写 E2E 测试（等 1+2 完成后执行）

[TaskPlanCard 弹出]
┌─────────────────────────────────────┐
│ 创建登录页面                         │
│ ░░░░░░░░░░░░░░░░░░░░ 0/3           │
│                                     │
│ ⚪ Task-1  LoginForm 组件    等待中   │
│ ⚪ Task-2  /api/auth/login   等待中   │
│ ⚪ Task-3  E2E 测试          等待中   │
│        ↳ 依赖 Task-1, Task-2        │
└─────────────────────────────────────┘
```

**待定**：Fact 分析提示「需要确认 UI 框架」，但 Coordinator 没有问用户就直接假设了 React。是否应该在这里插入一个确认步骤？当前设计有 `require_plan_signoff` 但这是审批不是澄清。（见 §4.3）

---

### Phase 3：内循环 Round 1

```
时间  T+5s
```

**Coordinator 内部**：

```
manager.create_progress_ledger()  ← LLM 调用 3

输入上下文:
  - task: "创建登录页面，邮箱+密码+中文错误提示"
  - 可用 Agent: [前端Agent(React), 后端Agent(FastAPI), 测试Agent]
  - 当前状态: 所有 Task 等待中，准备开始

产出 MagenticProgressLedger:
  is_request_satisfied:   false
  is_in_loop:             false
  is_progress_being_made: true（刚开始）
  
  next_wave: ["前端Agent", "后端Agent"]   ← 两个可以并行
  
  指令:
    前端Agent: "创建 LoginForm.tsx 组件：邮箱输入框（含格式校验）、
               密码输入框（最少6位）、登录按钮、错误信息展示区（中文）。
               使用 React + TypeScript，样式用 Tailwind CSS。
               文件范围：frontend/src/components/LoginForm.tsx"
    
    后端Agent: "创建 FastAPI 端点 POST /api/auth/login：
               接收 email + password，验证后返回 JWT token。
               错误返回中文提示（'邮箱格式不正确'、'密码错误'等）。
               文件范围：backend/app/api/auth.py"
```

**群聊显示**：

```
[Coordinator]: @前端Agent 创建 LoginForm 组件，邮箱+密码+中文错误提示
[Coordinator]: @后端Agent 创建 POST /api/auth/login 端点，返回 JWT

[TaskPlanCard 更新]
┌─────────────────────────────────────┐
│ 🟡 Task-1  LoginForm 组件    执行中   │
│ 🟡 Task-2  /api/auth/login   执行中   │
│ ⚪ Task-3  E2E 测试          等待中   │
│ 进度: 0/3  ░░░░░░░░░░░░░░░░         │
└─────────────────────────────────────┘
```

**两个 Agent 同时开始执行**，各自在自己的 CLI session 里 work。

---

### Phase 4：并行执行中 + 用户插话

```
时间  T+5s ~ T+50s

前端Agent 在写 LoginForm.tsx  (L4 流式输出显示 thinking + tool calls)
后端Agent 在写 auth.py        (L4 流式输出显示 thinking + tool calls)
```

**T+30s，后端 Agent 先完成**：

```
[系统]: ✅ Task-2 /api/auth/login 完成（耗时 25s，消耗 12K tokens）

[Coordinator]: 收到后端 Agent 结果。接口已创建：
  - POST /api/auth/login
  - 接收 email/password → 返回 JWT
  - 错误提示文案：'邮箱格式不正确'、'密码错误'、'用户不存在'
```

**前端 Agent 还在跑**（T+35s）。

**T+40s，用户插话**：

```
[用户]: @Coordinator 后端接口有没有加登录失败次数限制？连续5次锁定30分钟
```

**关键抉择**：Coordinator 此时正在等前端 Agent 完成。怎么处理这条插话？

按照目前的设计，Coordinator 是一个循环中的消息处理器。但它当前正在等待 wave 1 的所有 Worker 完成。用户消息到达后：

**Option A（待定）**：Coordinator 立即暂停等待，处理用户消息
```
Coordinator → 后端Agent: "补充：加登录失败次数限制，5次/30分钟锁定"
Coordinator → 继续等前端Agent
```

**Option B（待定）**：Coordinator 记录用户要求，等这波 wave 完成后再处理
```
Coordinator 心里记下，等前端完成 → progress_ledger 中体现新要求
```

**前端显示（假设 Option A）**：

```
[Coordinator]: @后端Agent 补充需求：添加登录失败次数限制（连续5次 → 锁定30分钟）

[TaskPlanCard 更新]
┌─────────────────────────────────────┐
│ 🟡 Task-1  LoginForm      执行中     │
│ 🔄 Task-2  /api/auth/login 重新执行  │  ← 状态变了
│ ⚪ Task-3  E2E 测试        等待中     │
└─────────────────────────────────────┘
```

**这是需要决策的核心问题**：Coordinator 收到插话时的行为模型是什么？继续等待 wave 完成 vs 立即响应？如果立即响应，正在跑的 Agent 怎么办？（后端 Agent 刚完成，可以立即接收新指令。但如果前端 Agent 也受影响呢？等它跑完再告诉它要改？）

---

### Phase 5：内循环 Round 2

```
时间  T+55s

前端Agent 完成 → 系统消息 → 后端Agent 也完成（补充的限制功能）
```

**Coordinator 内部**：

```
manager.create_progress_ledger()  ← LLM 调用 4

输入上下文:
  - Task-1 完成: LoginForm.tsx 已创建，含邮箱/密码验证 + 中文错误提示
  - Task-2 完成: /api/auth/login 已创建 + 补充了登录失败限制
  - 用户要求: 5次失败锁定30分钟（已满足）
  - 剩余: Task-3 还没开始

产出:
  is_request_satisfied:   false
  is_in_loop:             false
  is_progress_being_made: true
  
  next_wave: ["测试Agent"]
  指令: "编写 E2E 测试：验证整个登录流程（正确登录、错误邮箱、错误密码、
         空字段、5次失败锁定）。文件范围：tests/e2e/test_login.py"
```

**群聊显示**：

```
[系统]: ✅ Task-1 LoginForm 组件完成（耗时 50s，消耗 18K tokens）

[Coordinator]: @测试Agent 编写 E2E 测试，覆盖：正确登录、错误输入、锁定逻辑

[TaskPlanCard 更新]
┌─────────────────────────────────────┐
│ 🟢 Task-1  LoginForm      已完成     │
│ 🟢 Task-2  /api/auth/login 已完成    │
│ 🟡 Task-3  E2E 测试       执行中     │
│ 进度: 2/3  ████████████░░░ 67%      │
└─────────────────────────────────────┘
```

---

### Phase 6：内循环 Round 3 — 完成

```
时间  T+80s

测试Agent 完成
```

**Coordinator 内部**：

```
manager.create_progress_ledger()  ← LLM 调用 5

输入上下文:
  - Task-1 ✅ LoginForm
  - Task-2 ✅ /api/auth/login
  - Task-3 ✅ E2E 测试全部通过（正确登录 ✅、错误邮箱 ✅、错误密码 ✅、
            空字段 ✅、锁定逻辑 ✅）

产出:
  is_request_satisfied: true ✓
```

```
manager.prepare_final_answer()  ← LLM 调用 6

"登录页面创建完成 ✅

📁 创建的文件：
- frontend/src/components/LoginForm.tsx（React + TypeScript + Tailwind）
- backend/app/api/auth.py（POST /api/auth/login）
- tests/e2e/test_login.py（5 个测试用例全部通过）

🔧 功能：
- 邮箱格式校验 + 密码最少 6 位
- 中文错误提示
- JWT token 签发
- 登录失败限制（5次 → 锁定 30 分钟）

共消耗 6 次 LLM 协调调用，Worker 总计消耗 ~45K tokens"
```

**群聊显示**：

```
[系统]: ✅ Task-3 E2E 测试完成（耗时 25s，消耗 15K tokens）

[Coordinator]: 登录页面创建完成 ✅
（上面 final_answer 的内容）

[TaskPlanCard 最终状态]
┌─────────────────────────────────────┐
│ 🟢 Task-1  LoginForm      已完成     │
│ 🟢 Task-2  /api/auth/login 已完成    │
│ 🟢 Task-3  E2E 测试       已完成     │
│ 进度: 3/3  ████████████████ 100%    │
└─────────────────────────────────────┘
```

---

### Phase 7：异常场景 — 卡死

如果 Task-1 前端 Agent 跑了 5 分钟还在 tool call 循环（反复读同一个文件）：

```
Round 1: 分发 wave 1 → 两个 Agent 都在跑
Round 2: 前端 Agent 还没完成…
         progress_ledger:
           is_progress_being_made: false  → stall_count: 1
Round 3: 前端 Agent 还在跑…
         progress_ledger:
           is_progress_being_made: false  → stall_count: 2
Round 4: 前端 Agent 还在跑…
         progress_ledger:
           is_progress_being_made: false  → stall_count: 3 > max(3)

→ _reset_and_replan():
    1. context.reset()      清空 chat_history
    2. MagenticResetSignal  通知前端Agent 重置 session
    3. manager.replan()     facts_update + plan_update
       "前端Agent 在创建 LoginForm 时陷入循环，可能原因：组件结构设计过于复杂。
        新方案：拆分为 LoginForm + InputField 两个子组件，先做简单的 InputField。"
    
→ 新 TaskPlan: 拆成子 Task → 重新分发 → 回到内循环
```

**群聊显示**：

```
[Coordinator]: ⚠️ Task-1 执行异常，正在重新规划…
[Coordinator]: 已调整方案：将 LoginForm 拆分为 LoginForm + InputField
[Coordinator]: @前端Agent 先创建 InputField 基础组件…
```

---

## 本次推演暴露的待解问题

| # | 场景 | 问题 | 影响 |
|---|------|------|------|
| 1 | Phase 1 | Coordinator 接管后，Selector 还路由消息吗？DiscussionOrchestrator 暂停还是继续？ | §4.3：Coordinator 和 Selector 的分工 |
| 2 | Phase 2 | Fact 分析发现"需要确认 UI 框架"但没问用户，直接假设了 React | 是否需要 plan review 或自动澄清步骤 |
| 3 | Phase 4 | 用户插话时，Coordinator 立即响应还是等 wave 完成？ | §4.2：消息优先级和排队模型 |
| 4 | Phase 4 | 后端 Agent 已完成，用户插话要求补充功能。是追加新 Task 还是重新打开旧 Task？ | Task 语义：COMPLETED 的 Task 能否被追加修改 |
| 5 | Phase 4 | 前端 Agent 还在跑，用户插话可能也影响前端。要不要打断正在跑的 Agent？ | Worker 的"可中断性" |
| 6 | Phase 5 | 整个流程 Coordiantor 是发言最多的角色，聊天流会被 Coordinator 刷屏 | 是否需要折叠/摘要 |
| 7 | Phase 7 | replan 重置了 chat_history，用户之前看过的对话被清掉了 | 用户体验——历史对话去哪了 |

---

## Token 用量汇总（本场景）

| 调用 | 次数 | 估计 token/次 | 小计 |
|------|:---:|:---:|:---:|
| plan (facts + plan) | 2 | 5K | 10K |
| progress_ledger | 3 | 8K | 24K |
| final_answer | 1 | 5K | 5K |
| **Coordinator 合计** | **6** | | **~39K** |
| Worker (前端) | 1 | 18K | 18K |
| Worker (后端) | 1 | 12K | 12K |
| Worker (测试) | 1 | 15K | 15K |
| **Worker 合计** | **3** | | **~45K** |
| **总消耗** | | | **~84K tokens** |

Coordinator 占 46%，Worker 占 54%。Coordinator 不是主要成本。
