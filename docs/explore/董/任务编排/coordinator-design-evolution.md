# 协调者设计演进：从一次性调用到事件驱动循环

> 日期：2026-06-04 | 状态：方向调整，待细化 | 取代：[[coordinator-design-decision]]

---

## 一、决策变更

```
旧方向（方案 1）：
  协调者 = 纯 LLM 调用 → Coordinator.decompose() 一次 → Harness 确定性执行 → 结束
  协调者在任务分解后就退出

新方向（方案 2+）：
  协调者 = MAF Magentic 风格的循环 + AgentHub 所需的并行 wave 分发
  协调者全程参与执行，评估进度、调整计划、响应插话
```

### 变更原因

1. **交互体验**：AgentHub 的核心是 IM 群聊协作。协调者作为"看得见的参与者"（在群里发言、分配任务、回答追问）跟产品定位一致；方案 1 的"幕后一次性分解"跟群聊体验割裂。

2. **成功率**：MAST 论文指出 41.77% 失败来自规格模糊。一次性分解正好踩在这个雷区——错了只能在 Task 失败后补救。循环模式每轮评估"是否在正确轨道上"，过程中纠偏。

3. **群聊兼容性**：方案 1 把协调和对话解耦，但 AgentHub 用户会在执行中 @协调者、Agent 之间需要交流。循环模式下的协调者就是一个自然的消息处理器。

4. **成本可接受**：Coordinator 的 LLM 调用在整个任务成本中占比极低。省几次调用换来 Worker 白跑的代价远大于多调几次。

### 不是全盘照抄

MAF Magentic 有两件事 AgentHub 不能直接抄：

| MAF 的设计 | AgentHub 需要的 | 原因 |
|-----------|----------------|------|
| 串行执行（每轮选一个 Worker） | **并行 wave 分发**（一次选一组 Worker） | 代码任务天然可并行，研究任务天然串行 |
| 协调者是唯一消息处理器 | **协调者是群聊中的普通参与者**，Selector 独立路由 | AgentHub 有自由群聊，MAF 是令牌环 |

---

## 二、目标架构

```
用户下达任务
  │
  ▼
┌─ 外循环：planning ───────────────────────────────────┐
│                                                       │
│  manager.plan()  ← LLM ×2（facts + plan）              │
│  [可选] 人审批 plan                                    │
│                                                       │
└───────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌─ 内循环：coordination ────────────────────────────────┐
│                                                       │
│  while 未完成:                                        │
│    │                                                  │
│    ├─ manager.create_progress_ledger()  ← LLM ×1      │
│    │     └─ 产出：完成判断 / 卡死判断 / 下一波选人 / 指令│
│    │                                                  │
│    ├─ 完成？ → prepare_final_answer() → 退出          │
│    │                                                  │
│    ├─ 卡死？ → stall_count++                          │
│    │   stall_count > 阈值 → _reset_and_replan()       │
│    │     ├─ context.reset()                           │
│    │     ├─ 通知 Worker 重置                           │
│    │     ├─ manager.replan()  ← LLM ×2                │
│    │     └─ 回到外循环                                  │
│    │                                                  │
│    └─ 正常：                                          │
│        ├─ 取 next_wave: [agent-A, agent-B]  ← 一组人  │
│        ├─ 分别发指令                                   │
│        ├─ 等待这波全部完成                              │
│        └─ 结果追加到 chat_history → 下一轮             │
│                                                       │
└───────────────────────────────────────────────────────┘
```

**与 MAF 的核心差异**：

```
MAF:     next_speaker: "researcher"          ← 选一个人
AgentHub: next_wave: ["frontend", "backend"]  ← 选一组人
```

---

## 三、LLM 调用次数

保持 MAF 完整，不砍，确保成功率优先。

| 阶段 | 调用内容 | 次数 |
|------|---------|:---:|
| plan | facts 分析 + plan 制定 | 2 |
| 每轮内循环 | progress_ledger（进度评估 + 选人 + 指令） | 1 |
| 最终 | final_answer | 1 |
| 如卡死 | facts_update + plan_update（replan） | 2 |

```
正常 3 轮任务: 2 + 3 + 1 = 6 次
复杂 5 轮 + 1 次卡死: 2 + 5 + 1 + 2 = 10 次
```

---

## 四、待解问题

### 4.1 并行 wave vs 串行评估的矛盾

MAF 每轮选一个人，评估的是"全局单一状态"。AgentHub 每轮选一组人，需要评估的是"N 个并行子任务各自的状态"。

**问题**：`progress_ledger` 的评估维度需要从"任务完成了吗"扩展到：

```
{
  wave_results: [
    { task_id: "A", status: "completed", output_summary: "..." },
    { task_id: "B", status: "failed",   error: "..." },
    { task_id: "C", status: "in_progress" }
  ],
  dependency_impact: "B 失败导致 D 和 E 不可达",
  next_wave: ["C"],  // C 还在跑，不发新 wave；或 ["D-fix"] 如果 B 需要 replan
  need_replan: true  // B 失败影响了关键路径
}
```

**需要设计**：Coordinator 的 progress_ledger prompt 如何同时处理并行子任务的状态矩阵。

### 4.2 并行执行期间的用户插话

```
Timeline:
  11:00  Coordinator 分发 wave 1 [Agent-A, Agent-B]
  11:01  用户: "@Coordinator Agent-B 别忘了加错误处理"
  11:02  Agent-A 完成
  11:03  Agent-B 完成
```

**问题**：
- Agent-A 完成后，Coordinator 是做 progress_ledger 还是先回用户？
- 用户消息和 Worker 回复到达顺序不确定，谁来排队？
- Coordinator 回复用户时，是继续等 Agent-B 还是新的评估已经需要包含用户的新要求？

**需要设计**：消息分发层如何区分"Worker 执行结果"、"用户指令"、"用户闲聊"，以及 Coordinator 在不同消息类型间的优先级。

### 4.3 协调者只是群聊中的一个收听者

MAF 假设协调者是唯一的话筒持有者。AgentHub 的群聊里每个人随时能说话。

**问题**：
- Selector 独立路由消息时，Coordinator 不知道 Selector 做了什么决定
- Agent 之间的私聊（如 Worker-A 问 Worker-B API 签名），Coordinator 需要知道吗？
- 非 Worker Agent 的发言（如旁观者指出错误），Coordinator 要不要纳入评估？

**需要设计**：Coordinator 和 Selector 的关系。是 Selector 把"任务执行相关消息"转发给 Coordinator（Coordinator 降级为一个消息消费者），还是 Coordinator 替代 Selector 成为执行期间的唯一路由者？

### 4.4 前端交互

并行 wave 模式需要前端同时展示：

| 组件 | 内容 | 状态 |
|------|------|:---:|
| 聊天流 | Coordinator 发言 + 系统消息 + Worker 完成通知 | 正常滚动 |
| TaskPlanCard | DAG 图 + 多 Task 状态矩阵 + 进度条 | 多个 Task 同时变色 |
| Worker 流式输出 | 每个运行中 Worker 的 CLI 输出 | 可能 2-3 个同时流式 |

**问题**：
- 多个 Worker 同时在跑时，聊天流会不会被系统消息刷屏？
- TaskPlanCard 的 DAG 图在执行期间如何动态更新（新增 Task、删除、依赖变更）？
- L4（CLI 实时流）需要在群聊里用折叠方式展示多个 Worker 的输出吗？

### 4.5 文件冲突在并行 wave 中的处理

MAF 的串行模式天然避免文件冲突（同一时间只有一个人改文件）。AgentHub 的并行 wave 必须面对：

- Wave 1 中 Agent-A 和 Agent-B 同时修改 `shared/types.ts`
- Coordinator 在分发 wave 时能否预判冲突？
- 如果预判了，是强制串行化还是让 Agent 各自改再合并？

---

## 五、与现有设计的关系

| 已有设计 | 影响 |
|---------|------|
| `coordinator-design-decision.md`（方案 1） | **被本文取代**，方向改为循环模式 |
| `task-execution-open-questions.md`（17 项） | 大部分仍然有效，需增加本文 §4 的 5 个新问题 |
| `maf-implementation-analysis.md` | 参考实现，但须注意 MAF 串行和 AgentHub 并行的差异 |
| `coordinator-pattern-deep-research.md` | Anthropic 简单性原则不再适用；MAST 可靠性数据支持本次转向 |
| DiscussionOrchestrator + Selector | 其地位待定——执行期间 Selector 和 Coordinator 如何分工（§4.3） |

---

## 六、下一步

1. 解决 §4.3：Coordinator 和 Selector 在执行期间的关系模型
2. 设计并行 wave 的 progress_ledger prompt
3. 保留 MAF 的 plan/replan/stall/hysteresis 逻辑，改动 next_speaker → next_wave
4. 原型验证：多 Worker 并行执行 + 用户插话 + Coordinator 循环评估的可行性

## 关联文档

- [[task-execution-open-questions]] 任务执行待解问题（17 项）
- [[maf-implementation-analysis]] MAF 源码分析
- [[coordinator-pattern-deep-research]] 协调者模式深度调研
