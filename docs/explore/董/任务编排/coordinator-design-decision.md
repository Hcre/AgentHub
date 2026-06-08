# 协调者设计决策

> 日期：2026-06-03 | 状态：已决策 | 关联：[[task-execution-open-questions]] [[EXP-02_编排器设计模式]]

## 决策结论

**协调者 = 纯 LLM 调用，非完整 Agent。**

## 两种方案的对比评估

### 方案 1：纯 LLM 调用（已采用）

```
Coordinator.decompose(history, members, trigger)
  → LLM 一次性调用
  → 结构化 TaskPlan JSON
  → Harness 校验 → 任务系统接管
  → Coordinator 退出，不参与后续流程
```

### 方案 2：完整 Agent（未采用）

```
Coordinator（永久 Agent，有自己的 CLI session）
  → 被 @ 触发 → decompose()
  → 向 Worker 发消息分配任务
  → 监控 Worker 状态
  → 收集结果
  → 在群里汇报进度
  → 回答用户追问
```

## 评估依据

| 维度 | 方案 1 | 方案 2 |
|------|:---:|:---:|
| 与 Anthropic "Building Effective Agents" 一致 | ✅ | ❌ |
| 成本 | 一次性 LLM 调用 | 持久 CLI session + 多轮，15x token |
| 与现有 FSM/Harness 互补 | ✅ 职责清晰 | ❌ 功能重叠 |
| 可靠性 | 失败域小 | 新增单点故障（36.94% 协调失败率，行业数据） |
| Anthropic 简单性原则 | ✅ 从最简开始 | ❌ 预先增加复杂度 |

## 业界参考

| 来源 | 协调者定位 | 与方案 1/2 的关系 |
|------|-----------|-------------------|
| Anthropic "Building Effective Agents" (2024.12) | LLM 调用（workflow 节点） | 支持方案 1 |
| Anthropic 多 Agent 研究系统 | 完整 Agent（特殊场景，不可预测任务） | 方案 2 仅适用特殊情况 |
| CrewAI Hierarchical Process | 完整 Agent（Manager） | 方案 2，有已知瓶颈问题 |
| open-multi-agent | 临时 Agent（用完即销毁） | 混合：分解是 Agent，后续是纯代码 |

## 与 Selector 的关系

- Selector 的 `select_next_speaker` tool schema 增加 `decision = "decompose"` 出口
- 当 Selector 判断用户消息包含工作执行意图（"帮我实现"、"做一个"等）→ 返回 `decompose`
- DiscussionOrchestrator 收到 `decompose` → 调用 `Coordinator.decompose()` → 产出的 TaskPlan 渲染为 TaskPlanCard 推送到群聊
- Selector 用廉价模型（Haiku），Coordinator 用深度模型（Opus/Sonnet）— 不合并两个 LLM

## 协调者需要交互时

协调者不是完整 Agent，但可以在以下情况作为群成员发言：

- 用户 @协调者 追问（如「为什么这样分配？」）→ Selector 路由 → 协调者发言回答
- 任务失败需要重新分解 → Harness 触发 `Coordinator.decompose()` → 结果以系统消息播报

这两种情况下协调者**只是一次 LLM 调用 + 把结果作为消息写回群聊**，不需要常驻的 CLI session。

## 待补：方案 1 实现时必须解决的前置问题

需求完整性审查（`coordinator-requirement-gap-analysis.md`）发现了 9 项关键缺失，其中 4 项 Critical：

| # | 缺失项 | 优先级 |
|---|--------|:---:|
| ① | Coordinator prompt 设计（system prompt + few-shot） | Critical |
| ② | 输入输出契约（JSON Schema + tool_use 强制） | Critical |
| ③ | 协调者自身失败处理（LLM 超时/格式错误降级） | Critical |
| ④ | Worker 能力发现（Agent 信息注入 decompose prompt） | Critical |
| ⑤ | Worker 输出质量验证 | High |
| ⑥ | 结果聚合（多 Task → 单总结） | High |
| ⑦ | 动态图修改（执行中增删 Task） | High |
| ⑧ | Worker 进程生命周期（超时/并发上限） | High |
| ⑨ | 并行度控制 | High |

以上已写入 `task-execution-open-questions.md` §4–§10。

## 关联文档

- [[task-execution-open-questions]] 任务执行 + 协调者核心流程待解决问题（10 项）
- [[coordinator-requirement-gap-analysis]] 功能需求完整性审查
- [[coordinator-research-report]] 业界调研报告
- [[open-multi-agent_analysis_report]] open-multi-agent 项目分析
- `docs/explore/EXP-02_编排器设计模式.md` 编排器设计模式深度分析
- `docs/design/group-chat-discussion-mode_群聊讨论模式设计方案.md` §6.1 Selector vs 协调者
- `docs/specs/01b-architecture-design_分层与数据流.md` S8/S13 场景
