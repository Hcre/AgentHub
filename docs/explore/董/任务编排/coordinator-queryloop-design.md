# Coordinator 主循环设计

> ⚠️ 已被取代：本文（v1）的"Magentic 每轮 LLM 重判 + 静态 DAG"双调度存在地基矛盾。
> 当前权威版本 → [[coordinator-dag-driven-design-v2]]（DAG 独占调度 + 事件驱动）。
> 本文保留作设计演进记录，勿据此实现。
>
> 日期：2026-06-05 | 状态：已取代 | 取代：[[coordinator-design-decision]]（方案 1）
> 基础：MAF Magentic（编排语义） + Claude Code queryLoop（工程骨架）

---

## 一、架构定位

```
┌─────────────────────────────────────────────────┐
│              DiscussionOrchestrator              │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐ │
│  │ Selector │  │Coordinator│  │ Agent Workers │ │
│  │ 消息路由  │  │ 任务编排  │  │  任务执行      │ │
│  └──────────┘  └──────────┘  └───────────────┘ │
│       │              │               │          │
│       └──────┬───────┘               │          │
│              │ 模式切换               │          │
│              ▼                       │          │
│     DISCUSSION ←→ EXECUTION          │          │
└─────────────────────────────────────────────────┘
```

- **Selector**：始终运行，判断每条消息意图。Coordinator 是它的一个路由目标
- **Coordinator**：EXECUTION 模式下激活，驱动任务分解→分发→评估→完成
- **之间的关系**：模式切换，不是角色替换。§7 详述

---

## 二、设计来源

| 来源 | 提供什么 | 对应章节 |
|------|---------|:---:|
| **MAF Magentic** | 编排语义：plan / progress_ledger / stall / replan / final_answer | §3 |
| **Claude Code queryLoop** | 工程骨架：不可变 State / 退出原因 / 被动压缩 / 异常兜底 | §4 |
| **AgentHub 特化** | 并行 wave 分发 / 群聊集成 / Selector 协作 | §5 §7 |
| **场景推演** | 用户插话 / 文件冲突 / 前端交互 | [[scenario-walkthrough]] |

---

## 三、编排语义（来自 MAF Magentic）

### 3.1 外循环：planning phase

```
用户任务触发
  │
  ▼
manager.plan()  ← LLM ×2
  │
  ├─ facts 分析:
  │     "已知: 用户需求 + 代码仓库结构 + 设计文档（如有）
  │      待查: UI 框架版本、API 端点是否存在"
  │     产出: 事实清单（已有知识 + 待查项）
  │
  └─ plan 制定:
        "基于事实，分解为子任务:
          1. 前端Agent → LoginForm.tsx
          2. 后端Agent → POST /api/auth/login
          3. 测试Agent → E2E 测试
         依赖: 3 依赖 1+2 完成
         并行: 1 和 2 可同时执行"
       产出: TaskLedger {facts, plan}
```

**LLM 调用次数**：2 次（facts + plan），不砍。

**Coordinator 的工具集**（只读）：

| 工具 | 用途 | 权限 |
|------|------|:---:|
| Read | 读取代码仓库文件 | 只读 |
| Grep | 搜索代码结构 | 只读 |
| Glob | 列出目录结构 | 只读 |
| FetchDoc | 读取用户上传的设计文档/PRD | 只读 |
| GetAgentCapabilities | 获取可用 Agent 列表及能力 | 只读 |

Coordinator 不是 Worker，不给写权限。

### 3.2 内循环：coordination phase

```
while (true):
    │
    ├─ progress_ledger = create_progress_ledger(state)  ← LLM ×1
    │     产出:
    │       is_request_satisfied:     {reason, answer}
    │       is_in_loop:               {reason, answer}
    │       is_progress_being_made:   {reason, answer}
    │       next_wave:                [{agent, task, instruction}]   ← 一组人
    │       need_replan:              {reason, answer}              ← AgentHub 新增
    │
    ├─ 判断 1: 完成了？
    │   └─ is_request_satisfied → prepare_final_answer() → 退出
    │
    ├─ 判断 2: 需要 replan？
    │   │  if need_replan OR (!is_progress_being_made):
    │   │      stall_count++
    │   │  else:
    │   │      stall_count = max(0, stall_count - 1)
    │   │
    │   └─ stall_count > max_stall_count → 触发 replan
    │         ├─ state.reset()        清空 chat_history，保留 task + dag_status
    │         ├─ 通知受影响 Worker 重置   MagenticResetSignal
    │         ├─ manager.replan()      ← LLM ×2（facts_update + plan_update）
    │         │     产出: 更新后的 TaskLedger + 子树修复计划
    │         ├─ merge_subtree_repair()   Harness 合并修复计划到 DAG
    │         └─ 回到外循环
    │
    └─ 判断 3: 正常执行
        ├─ 取 next_wave: [{agent, task, instruction}, ...]
        ├─ 校验: can_parallel(task_i, task_j)  ← 文件冲突检测
        ├─ 发指令: 给每个选中 Agent 发送 instruction
        ├─ 等待整波完成（或超时/失败）
        │     ├─ 全部完成 → 结果追加到 state.chat_history
        │     ├─ 部分失败 → 标记失败 Task，让下一轮 progress_ledger 判断是否需要 replan
        │     └─ 超时 → 标记，进入 stall 计数
        └─ 下一轮
```

**LLM 调用次数**：每轮 1 次（progress_ledger）。replan 时额外 2 次（facts_update + plan_update）。final_answer 时 1 次。

### 3.3 progress_ledger 的 AgentHub 扩展

MAF 的 progress_ledger 是串行场景（一轮一个 Worker），AgentHub 需要扩展到并行：

```json
{
  "is_request_satisfied": {
    "reason": "前两个任务完成，第三个任务还在跑",
    "answer": false
  },
  "is_in_loop": {
    "reason": "未检测到重复操作",
    "answer": false
  },
  "is_progress_being_made": {
    "reason": "前端和后端都已完成，测试在进行中",
    "answer": true
  },
  "next_wave": [
    {
      "agent": "测试Agent",
      "task_id": "task-3",
      "instruction": "编写 E2E 测试，覆盖正确登录、格式错误、空字段、锁定逻辑",
      "context": {
        "depends_on": ["task-1", "task-2"],
        "task_1_result": "LoginForm.tsx 已创建...",
        "task_2_result": "POST /api/auth/login 已创建..."
      }
    }
  ],
  "need_replan": {
    "reason": "正常进展中",
    "answer": false
  }
}
```

**next_wave 是数组**，不是 `next_speaker` 的单数。MAF 的 `instruction_or_question` 扩展为一对多的 `[{agent, task_id, instruction, context}]`。

---

## 四、工程骨架（来自 Claude Code queryLoop）

### 4.1 不可变 State 对象

每轮迭代构造新的 State，不修改旧 State。和 queryLoop 每轮的 `state = { ...state, ... }` 一致。

```python
@dataclass(frozen=True)
class CoordinatorState:
    # === 任务定义（plan 阶段产出，replan 时更新） ===
    task: str                         # 用户原始需求
    task_ledger: TaskLedger | None    # facts + plan
    agent_registry: dict[str, AgentCapability]  # 可用 Agent 及能力描述

    # === DAG 执行状态（每轮更新） ===
    dag_status: dict[str, TaskNode]   # task_id → 当前 FSM 状态 + worker + output

    # === 对话上下文 ===
    chat_history: list[Message]       # 群聊中与当前任务相关的消息
    pending_interruptions: list[Message]  # 执行期间的用户插话（待处理）

    # === 控制状态 ===
    round_count: int = 0
    stall_count: int = 0
    reset_count: int = 0
```

### 4.2 退出原因码

```
正常退出:
  completed          Coordinator 判断任务完成，final_answer 已产出
  user_cancelled     用户主动取消

上限退出:
  max_rounds         内循环轮次达到上限，强行止损
  max_resets         replan 次数耗尽，无法继续

卡死退出:
  stalled_repeatedly stall → replan → 再次 stall → replan，循环无法打破
  worker_unavailable  所有可用的 Worker 都离线/超载/被删除

资源退出:
  context_too_long   上下文太长，被动压缩后仍塞不下
  budget_exceeded    Token 预算耗尽
  api_key_failed     LLM API Key 不可用

异常退出:
  irrecoverable_error  不可恢复的运行时错误（如 DAG 损坏）
```

### 4.3 被动压缩（不主动压缩）

```python
try:
    response = await llm_call(state)
except ContextTooLong:
    if state.has_attempted_compact:
        raise  # 同一轮内已经压过一次还是塞不下 → 退出
    state = compact(state)
    state = state.with_flag(has_attempted_compact=True)
    retry  # 重试当前轮
```

- 不每轮主动压缩（MAF 也没做），等 API 返回 `prompt_too_long` 才补救
- 压缩同一轮只做一次，避免死循环
- 压缩策略：只保留最近 N 轮对话 + 各 Task 的结果摘要（不是全文）

### 4.4 wave 后台分发（流式并行）

```python
async for chunk in llm_stream:
    yield chunk                              # 即时推给前端
    if chunk.is_complete_next_wave:
        for item in chunk.next_wave:
            dispatch_worker(item)             # 不等 LLM 流完就发指令
```

queryLoop 在模型流式输出时，识别出 tool_use 就立刻启动后台执行。Coordinator 同样：progress_ledger 一旦产出 next_wave，不等 JSON 完整流完，立刻开始给 Worker 发指令。

### 4.5 异常兜底分层

```python
try:
    progress = await create_progress_ledger(state)
except LLMTimeout:
    retry(2, backoff="exponential")
except LLMInvalidJSON:
    retry_with_feedback("你的上一条输出不是合法 JSON")
except LLMApiError:
    return ExitReason.API_KEY_FAILED
```

每类异常有独立的恢复路径，不统一 catch。

---

## 五、AgentHub 特化

### 5.1 并行 wave 文件冲突检测

```python
def can_parallel(task_a: TaskDef, task_b: TaskDef) -> bool:
    # 有文件交集 → 不能并行
    if task_a.files and task_b.files:
        if task_a.files & task_b.files:
            return False
    return True

def compile_wave(wave: list[TaskDef]) -> list[list[TaskDef]]:
    """如果 wave 内存在冲突，拆分为子 wave 串行执行。"""
    # 贪心分组：同一个 wave 内所有 Task 两两不冲突
    ...
```

Coordinator 的 progress_ledger 产出 next_wave 后，Harness 在分发前做冲突检测。有冲突就拆成子 wave。

### 5.2 用户插话处理

执行期间用户消息到达：

```
if message.target == "@Coordinator":
    if message.is_task_modification:       // "加上限流"、"换个方案"
        → 暂停当前 wave 等待，处理修改
    elif message.is_question:              // "你做完了哪些"
        → Coordinator 不打断 wave，用当前 state 直接回答
    elif message.is_cancel:                // "停下"
        → 发 MagenticResetSignal → return USER_CANCELLED
    else:                                  // 闲聊
        → 追加到 pending_interruptions，不打断循环
```

### 5.3 群聊进度推送

```
Task 开始:  系统消息 + TaskPlanCard 状态变 🟡
Task 完成:  系统消息 "✅ Task-N 完成（耗时 Xs，消耗 Y tokens）" + 状态变 🟢
Task 失败:  系统消息 "❌ Task-N 失败（原因）" + 状态变 🔴
Wave 完成:  Coordinator 发言总结当前 wave 结果
全部完成:   Coordinator final_answer + TaskPlanCard 全绿
```

UI 不轮询，全部走 `TaskStateChanged` 事件 → WS 推送。

---

## 六、数据结构

### 6.1 TaskLedger

```python
@dataclass
class TaskLedger:
    facts: str                    # LLM 分析的事实文本
    plan: str                     # LLM 生成的执行计划文本
    tasks: list[TaskDef]          # 结构化 Task 列表（可从 plan 解析或 LLM tool_use 产出）

@dataclass
class TaskDef:
    id: str                       # UUID
    title: str
    description: str              # 含文件范围建议
    suggested_worker: str         # 必须匹配 agent_registry 中的 name
    depends_on: list[str]         # 依赖的 task_id
    estimated_complexity: Literal["simple", "medium", "complex"]
    files: set[str] | None        # 声明要修改的文件（冲突检测用）
    side_effect_level: Literal["none", "readonly", "mutable", "external"]
    compensate: str | None        # external 级别 Task 的补偿步骤
```

### 6.2 ProgressLedger

```python
@dataclass
class ProgressLedger:
    is_request_satisfied: Assessment     # {reason, answer}
    is_in_loop: Assessment
    is_progress_being_made: Assessment
    next_wave: list[WaveItem]            # [{agent, task_id, instruction, context}]
    need_replan: Assessment              # AgentHub 新增
    wave_dependency_impact: str | None   # "B 失败导致 D 和 E 不可达"
```

### 6.3 AgentCapability

```python
@dataclass
class AgentCapability:
    name: str
    role: str
    capability_tags: list[str]          # ["frontend", "react", "typescript"]
    status: Literal["online", "busy", "offline"]
    active_tasks: int                    # 当前活跃 Task 数
    max_concurrent_tasks: int = 2
    modifies_files: bool = True          # False → 只读，可无限制并行
    side_effects: list[str] = []         # ["git_push", "deploy", "send_email"]
```

---

## 七、Selector 与 Coordinator 的关系

### 7.1 模式模型

```
DISCUSSION 模式（默认）:
  Selector 路由所有消息
  Coordinator 休眠
  用户 ↔ Agent 自由对话，效果和现在一样

  触发条件: Selector 判断消息包含工作执行意图
  切换: DISCUSSION → EXECUTION

EXECUTION 模式:
  Selector 继续运行，但路由优先级调整：
  
  消息类型                    → 路由目标
  ─────────────────────────────────────────
  @Coordinator 追问            → Coordinator
  对 Worker 的指令/反馈        → Coordinator（决定是否转给 Worker）
  Worker 执行结果              → Coordinator（系统消息类型）
  Worker 间技术确认            → 直接路由（不经过 Coordinator）
  群聊闲聊                    → 对应 Agent（不打断 Coordinator）
  新任务请求                  → Coordinator 判断：插入当前执行 vs 排队
```

### 7.2 不合并的理由

- Coordinator 是阻塞式循环——它在等 wave 完成时，不应该挡其他消息的路
- Selector 的逻辑已经存在，不需要改
- 解耦：一个管"消息给谁"，一个管"任务到哪了"

### 7.3 DiscussionOrchestrator 的职责

模式切换逻辑放在 DiscussionOrchestrator 里。Selector 做完判断后、实际发送前，加一层：

```python
if mode == EXECUTION and message.is_task_relevant:
    redirect_to = coordinator
else:
    redirect_to = selector.original_target
```

---

## 八、LLM 调用预算（正常任务）

| 阶段 | 调用 | 次数 | 估算 token |
|------|------|:---:|:---:|
| plan | facts 分析 + plan 制定 | 2 | ~10K |
| 每轮内循环 | progress_ledger | N | N × ~8K |
| replan（按需） | facts_update + plan_update | 2 | ~10K |
| 完成 | final_answer | 1 | ~5K |
| **Coordinator 合计（3 轮）** | | **6** | **~39K** |
| **Worker 合计（3 个 Task）** | | **3** | **~45K** |

Coordinator 不是主要成本。不砍调用，确保成功率优先。

---

## 九、关键设计决策

| # | 决策 | 原因 |
|---|------|------|
| 1 | 保持 MAF 完整 plan（facts + plan） | 先盘点后规划降低出错率 |
| 2 | 保持 MAF 完整 replan（facts_update + plan_update） | 失败后更新判断再出新方案 |
| 3 | next_wave 是数组（非 next_speaker 单数） | 代码任务天然可并行 |
| 4 | State 不可变，每轮构造新的 | queryLoop 验证过的工程模式 |
| 5 | 被动压缩，不主动压缩 | 避免无效 token 消耗 |
| 6 | Selector 不替换，Coordinator 是路由目标 | 解耦消息路由和任务编排 |
| 7 | Coordinator 工具集只读 | 不给写权限，防止越权 |
| 8 | 保持 4.4 wave 后台分发 | 最大化并行利用 |
| 9 | 保持 4.5 退出原因码 | 异常场景各自有明确的退出路径 |
| 10 | 保持 5.2 用户插话分层处理 | 群聊环境不能锁死用户 |

---

## 关联文档

- [[coordinator-design-evolution]] 设计演进（方案 1 → 本次设计）
- [[scenario-walkthrough]] 场景推演（7 个待解问题）
- [[task-execution-open-questions]] 任务执行待解问题（17 项）
- [[maf-implementation-analysis]] MAF 源码分析
- [[coordinator-pattern-deep-research]] 协调者模式深度调研
