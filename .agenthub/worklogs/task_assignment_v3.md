# AgentHub 3 人团队任务分配方案（v3）

> 基准：完整 `PRD_AgentHub.md`（24 场景 + Command/Event 目录 + FSM）+ `架构设计_分层与数据流.md`（5 层洋葱）+ **已交付脚手架**。
> 时间轴：比赛 20 天里程碑 M1–M6（5/20–6/10），非旧版 8 周。
> 核心原则不变：**每人从数据库到前端完整交付一个功能域，可独立开发、测试、演示。**

---

## 一、为什么重做（v2 → v3）

v2 在没有 PRD 时拟定，需求不清导致以下偏差，v3 逐项修正：

| v2 问题 | PRD 依据 | v3 修正 |
|---------|---------|---------|
| Agent 管理压成 "Registry 4h" | §2.1 详情页 6 Tab + 对话式创建 + 权限矩阵 | 升级为域2 核心模块（≈26h） |
| 收件箱整块缺失 | §2.5 审批流四决策 + 通知 + 日历 | 域3 独立模块（≈22h） |
| 任务管理界面缺失 | §2.4 看板/筛选/父任务详情 | 域3 独立模块（≈18h） |
| AI 协作沉淀未分工 | §七 占评审 **30%** | 第八章显式分工，DRI = 域2 |
| 工时失衡 66/106/122 | — | 重新配平 ≈90/96/92 |
| 8 周 226h 时间轴 | §九 比赛 20 天 | 全部对齐 M1–M6 |
| 14h 共享基建列关键路径 | — | 脚手架已交付，见第二章 |

---

## 二、现状基线：脚手架已交付什么（各域起点）

脚手架（`AgentHub/`）已落地 5 层洋葱可运行骨架，**M1 环境搭建基本完成**。各域不再从零起步：

| 域 | 已交付骨架（可直接扩展） | 完成度 | 待补 |
|----|------------------------|--------|------|
| 域1 | `application/services/{chat,session}_service.py`、`api/ws/chat.py`、`api/routers/sessions.py`、`infrastructure/cache/memory_l1.py`、`frontend/src/components/chat/*` + `stores/{chat}`+`hooks/useWebSocket` | **MVP 私聊流式已通** | 群聊路由/上下文压缩/产物容器 |
| 域2 | `domain/task_engine/{fsm,harness,coordinator}.py`、`domain/llm/protocol.py`、`infrastructure/llm/{mock,claude}_adapter.py`、`application/services/agent_service.py`、`api/routers/agents.py`（全）、`groups.py`/`tasks.py`（stub） | **Agent CRUD + FSM + 适配器骨架** | 对话式创建/详情页/协调者实装/DAG/Worker |
| 域3 | `api/routers/{inbox,tasks}.py`（stub）、`infrastructure/cache/memory_l1.py`（L1 已用） | **仅 stub** | 任务管理/收件箱/产物/记忆 L2–L4 全量 |

> 共识：脚手架是三域共同跑道，**接口契约（第六章）以脚手架现有 Command/Event/适配器规格为准**，W1 内冻结。

---

## 三、三域定义（对齐架构层 + PRD 模块 + 场景编号）

```
用户视角                          → 域             → 架构落点
"选 Agent 聊天，消息能发能收能存"  → 域1 会话交互    → ChatService/WS/L1注入 (S8–S12,S22–S24)
"建 Agent、建群、丢需求自动分解"   → 域2 Agent与编排 → Agent/Group/Coordinator/TaskEngine (S1–S7,S13–S16)
"管任务、批审批、看Diff/预览产物"  → 域3 管理与产物  → Inbox/TaskBoard/Artifact/记忆 (S17–S21,产物内联)
```

### 域1：会话与交互层（IM Core）
**闭环**：消息能发能收能存能查，单聊+群聊+流式+多会话+三层上下文。
- 后端：`ChatService`、`SessionService`、WebSocket、MentionRouter（@解析路由）、L1 上下文注入消费、长对话压缩。
- 前端：主界面三栏布局 + 导航、`ChatView`/`SessionList`/`MessageList`/`StreamingText`、@补全菜单、**产物卡片渲染容器**（容器框架由域1，具体卡片组件由域3提供）。
- 数据：`sessions`、`messages`；Redis 会话状态/在线。

### 域2：Agent 与编排层（Brain）
**闭环**：Agent 能建能管，群组有协调者，需求能分解能调度能并行。
- 后端：`AgentService`（CRUD+对话式草案）、`GroupService`（建群自动生成协调者）、`CoordinatorService`（LLM 分解）、`Harness`（FSM/Guard/DAG/Worker 路由）、`TaskService`（创建+状态流转）、LLM Adapter（Claude/Codex/LiteLLM）。
- 前端：`AgentPanel`（列表/详情 6 Tab/表单+对话式创建）、群组创建与成员管理、`TaskPlanCard`、DAG 依赖图可视化。
- 数据：`agents`、`groups`、`group_members`、`tasks`、`task_events`（写侧）。

### 域3：管理界面·收件箱·产物工具链（Surfaces & Tools）
**闭环**：任务可管理，操作可审批，产物可预览，记忆可检索。
- 后端：`InboxService`（通知/审批四决策/日历）、`TaskService`（查询/筛选/父任务详情）、产物生成（unified diff / Vite 预览 / Docker 部署 / Git）、记忆 L2–L4 + pgvector RAG。
- 前端：`TaskBoard`（列表/看板/筛选/父任务详情/甘特）、`Inbox`（全部/审批/任务/日历）、`DiffCard`/`PreviewCard`/`DeployCard`/`FileCard`/`DocCard`、`Settings`。
- 数据：`notifications`、`task_artifacts`、`knowledge_vectors`。

---

## 四、按里程碑的任务分配（M1–M6）

> 工时为 20 天内净开发估算。每条标注 PRD 依据 / 架构场景 / 脚手架落点。

### 成员 1 — 会话与交互层

| # | 里程碑 | 任务 | 工时 | 依赖 | PRD/场景 |
|---|--------|------|------|------|----------|
|1.1|M1|校验脚手架私聊链路：mock→真实 Adapter 流式端到端跑通|3h|脚手架|S11,S12|
|1.2|M2|✅ 会话/消息 CRUD 补全：分页历史 + Pin/取消 Pin + 软删除|5h|1.1|§6.3,S23|> 完成: 2026-05-22, 备注: 搜索/删除/Pin/Unpin 端点已补；软删除改为硬删除（缺 is_deleted 列）|
|1.3|M2|✅ 聊天 UI 完善：三栏布局 + SessionList 排序/置顶/搜索 + MessageBubble 角色样式|8h|1.1|§4.1,§2.2.4|> 完成: 2026-05-22, 备注: SessionList+MessageBubble+Sidebar集成；三栏第三栏待域2 Agent详情页|
|1.4|M2|🔄 流式细节：thinking 事件展示 + 错误重连 + token 计量条|5h|1.1|S12|> 完成: 2026-05-22, 备注: thinking事件+WS重连已完成；token计量条待后端暴露token count
|1.5|M3|@mentions：解析 + 前端自动补全菜单 + 路由（@Agent/@All/@协调者）|6h|域2 群组|S9,S10,§2.2.3|
|1.6|M3|群聊消息广播：Redis Pub/Sub + 多客户端同步 + 协调者卡片占位|6h|1.5,域2|S8|
|1.7|M3|多会话并行：SessionManager + 上下文隔离 + 会话归档|5h|1.3|§2.2.4|
|1.8|M4|三层上下文：热窗口(域3 L1)+Pin长期+历史摘要占位 + 长对话压缩触发|6h|1.2,域3 L2|S22,S24,§2.2.5|
|1.9|M4|产物卡片渲染容器：按 content_type 分发渲染（域3 提供卡片组件）|5h|域3 卡片|§2.2.6|
|1.10|M5|聊天 UI 打磨：动画/响应式/暗色主题 + 端到端联调|8h|全部|§3.3|

**小计 ≈57h** + 跨域支援域2（见第五章）。

### 成员 2 — Agent 与编排层

| # | 里程碑 | 任务 | 工时 | 依赖 | PRD/场景 |
|---|--------|------|------|------|----------|
|2.1|M1|Claude Adapter 实装：anthropic_api 流式 + claude_cli 模式 + 重试退避|6h|脚手架|§八,S12|
|2.2|M1|Agent CRUD 补全：详情查询(tasks/activities/channels) + 软删除级联出群|5h|脚手架|S1–S4|
|2.3|M2|Agent 详情页前端：6 Tab（概览/能力/记忆/任务/活动/设置）|8h|2.2|§2.1.3|
|2.4|M2|对话式创建 Agent：`/api/agents/draft` 生成 system_prompt+能力标签 + 前端向导|6h|2.1|§2.1.1,S1|
|2.5|M3|群组管理：建群自动生成协调者(is_system) + 成员增删 + 群详情|6h|2.2|S5–S7,§2.2.1|
|2.6|M3|Coordinator 实装：分解 Prompt + Few-shot + 结构化 JSON + 意图检测|10h|2.1,2.5|S13,§2.2.2|
|2.7|M3|Task Engine 串联：FSM 落库(task_events) + Guard + Harness 路由 Worker|8h|2.6|S14,S15|
|2.8|M3|DAG 编译执行：Celery Canvas + 环检测 + 并行/串行|6h|2.7|S13|
|2.9|M3|TaskPlanCard + DAG 可视化前端：分解卡片 + 依赖图 + 实时状态|7h|2.8|§2.2.6,§2.4.4|
|2.10|M4|Worker Pool：按 Agent 隔离队列 + 并发限流(默认3) + 负载路由|5h|2.7|§10.2|
|2.11|M4|Codex Adapter + LiteLLM 网关：双平台切换|6h|2.1|§7.2|
|2.12|M4|权限审批矩阵：危险操作(删除/push/deploy/外网)→AWAITING_APPROVAL|5h|2.7,域3 收件箱|§2.1.4,S18|

**小计 ≈78h**（最重，编排是系统大脑）→ 接受域1/域3 支援。

### 成员 3 — 管理界面·收件箱·产物工具链

| # | 里程碑 | 任务 | 工时 | 依赖 | PRD/场景 |
|---|--------|------|------|------|----------|
|3.1|M1|L1 记忆完善：滑动窗口 + 上下文注入接口（供域1/域2）|3h|脚手架|MVP6,S22|
|3.2|M2|任务管理后端：`TaskService` 查询/多条件筛选/排序/分页|6h|域2 tasks 表|S17,§2.4.2|
|3.3|M2|TaskBoard 前端：列表 + 看板(按状态分列) + 筛选栏 + 手动创建|8h|3.2|§2.4.2,§2.4.3,S16|
|3.4|M3|父任务详情页：子任务列表 + DAG 状态 + 产物汇总|5h|3.2,域2 DAG|§2.4.4|
|3.5|M3|收件箱后端：通知生成 + 未读计数(Redis) + 分类查询|6h|域2 事件|S20|
|3.6|M3|审批流：APPROVE/REJECT/EDIT/RESPOND 四决策 + checkpoint 恢复|6h|3.5,域2 HITL|S18,S19,§2.5.2|
|3.7|M4|Inbox 前端：全部/审批/任务/日历 4 Tab + 审批弹窗 + 未读 Badge|8h|3.5,3.6|§2.5,§4.2|
|3.8|M4|Diff 产物（全栈）：unified diff 生成 + Monaco/diff2html 卡片|7h|脚手架|§2.2.6|
|3.9|M4|网页预览（全栈）：Vite Dev Server 管理 + iframe Sandbox + 卡片|6h|脚手架|§2.2.6,§8|
|3.10|M4|L2 摘要记忆：超阈触发 + 分层摘要 + PG 存储（供域1 上下文）|5h|3.1|§2.2.5,S24|
|3.11|M5|一键部署 + L4 RAG（择一优先）：Docker 部署卡片 / pgvector 检索|8h|3.8|§2.2.6,§7.1|

**小计 ≈68h** + 接手部分打磨/E2E。

---

## 五、工时平衡与交叉支援

| 成员 | 域 | 自有 | +支援 | −被支援 | 实效 |
|------|----|------|-------|---------|------|
| 成员1 | 会话交互 | 57h | +20h(支援域2) | — | **77h** |
| 成员2 | Agent编排 | 78h | +12h(域3支援) | −20h | **70h** |
| 成员3 | 管理产物 | 68h | — | −12h | **56h**＋打磨/E2E ≈20h = **76h** |

趋于均衡（≈76h/人，20 天约 3.8h/天）。支援安排：

| 阶段 | 支援方 → 被支援方 | 内容 |
|------|------------------|------|
| M2 | 成员1 → 成员2 | Agent 详情页/对话式创建前端组件 |
| M3 | 成员1 → 成员2 | Coordinator 联调 + TaskPlanCard 前端 |
| M3 | 成员2 → 成员3 | 收件箱事件桥接 + HITL checkpoint 协议 |
| M5 | 成员3 → 全员 | E2E + Demo 视频统筹 |

---

## 六、域间接口契约（W1 冻结，以脚手架现状为基线）

### 6.1 Command / Event（已在脚手架定义，见 `application/commands`、`domain/events`）
- 域1 发 `SendMessageCommand` → 产 `MessageSent`/`Streaming*` 事件。
- 域2 `CoordinatorService.decompose_and_dispatch()` → 产 `TaskCreated`/`SubTaskCreated`/`TaskStateChanged`。
- 域2 危险操作 → `ApprovalRequested`；域3 消费生成 `Notification` → `ApprovalResolved` 回传域2 恢复执行。

### 6.2 适配器契约（已冻结，见 `adapter_interface_spec.md` / `domain/llm/protocol.py`）
- 域2 实现 `UnifiedAgent`，产出 `StreamEvent`；域1 只依赖抽象消费流。
- Tool 调用：域2 `ToolScheduler` → 域3 `ToolRegistry.register(DiffTool/DeployTool/...)`。

### 6.3 数据表归属

| 表 | 属域 | 跨域权限 |
|----|------|---------|
| `sessions`,`messages` | 域1 | 域2 可读（Agent 上下文） |
| `agents`,`groups`,`group_members`,`tasks`,`task_events` | 域2 | 域1/域3 可读 |
| `notifications`,`task_artifacts`,`knowledge_vectors` | 域3 | 域2 可写产物 |

### 6.4 WebSocket 通道
| 通道 | 发布 | 订阅 |
|------|------|------|
| `session:{id}:message` | 域1 | 域2 |
| `session:{id}:task_event` | 域2 | 域1（聊天卡片） |
| `session:{id}:artifact` | 域2 | 域3（触发 Diff/预览） |
| `inbox:{user}:update` | 域3 | 域1（未读 Badge） |

---

## 七、关键路径

```
M1(脚手架已就绪) → M2 单聊MVP        → M3 群聊+协调者         → M4 产物+自建Agent → M5 打磨/文档/视频 → M6 提交
                  域1:私聊UI/CRUD     域2:Coordinator/FSM/DAG  域3:Diff/预览/收件箱   全员联调            提交
                  域2:Adapter实装     域1:@/群聊广播           域2:权限/Codex        成员3:E2E+Demo
                  域3:TaskBoard       域3:任务详情/审批后端     域1:产物容器
```

- **关键路径**：域2 Coordinator(2.6)→TaskEngine(2.7)→DAG(2.8) 是 M3 成败核心；域1 群聊(1.6)、域3 任务详情(3.4)/审批(3.6) 均依赖它 → 域2 M3 优先级最高，提前并接受支援。
- **降级闸**：Coordinator 不稳 → 降级手动 @Agent（PRD §九）；Adapter 阻塞 → mock 保流程。

---

## 八、AI 协作能力沉淀（评审 30%，硬指标，DRI=成员2）

PRD §七要求在仓库体现 Spec/Skill/Rules/Harness。**显式分工，非附带产物**：

| 类型 | 产出文件 | 负责 | 说明 |
|------|---------|------|------|
| Spec | `specs/chat-ui.md` | 成员1 | 会话/消息 I/O + 边界 + 用例 |
| Spec | `specs/orchestrator.md`、`specs/agent-management.md` | 成员2 | 分解/FSM/Agent 模块规格 |
| Spec | `specs/inbox.md`、`specs/artifact.md` | 成员3 | 审批/产物模块规格 |
| Skill | `skills/react-component.skill`、`skills/api-endpoint.skill` | 成员1/成员2 | AI 生成符合规范代码模板 |
| Rules | `rules/coding-style.rule`、`rules/api-design.rule` | 三人共维护 | 已有 CLAUDE.md 编码规范，落为 rule |
| Harness | `harness/workflow.md` | 成员2 | 需求→Agent→review→合并产物流程 |

DRI（成员2）负责每周五汇总整合，确保 M5 前完整。

---

## 九、协作规范（沿用 v2 + 调整）

| 规范 | 要求 |
|------|------|
| 仓库 | 单仓库 `AgentHub/`，按架构层划分（已落地），共享代码在 `core/`/`domain/` |
| 分支 | `feature/<domain>/<desc>`，如 `feature/orchestration/coordinator` |
| 接口先行 | Command/Event/适配器契约（第六章）冻结后再实现，变更需 2 人 Review |
| PR | 至少 1 人 Review；跨域接口变更 2 人 |
| 站会 | 每日 10min 同步进度/阻塞/接口变更 |
| 集成 | 每周五全员集成，按里程碑成功闸门验收 |
| 质量 | 新功能必带测试（脚手架已配 pytest/vitest），覆盖率目标 80% |

---

## 十、M2 首阶段交付标准（5/27 前）

| 成员 | 必交 | 验收 |
|------|------|------|
| 成员2 | Claude Adapter 真实流式 + Agent CRUD/详情页 | `/api/agents` 全链路 + 真实模型流式回复 |
| 成员1 | 私聊 UI + 会话历史 + 流式打磨 | 浏览器内完成"需求→代码→流式展示"闭环 |
| 成员3 | TaskBoard（列表+看板+筛选）+ 手动建任务 | 任务可创建可筛选可看板展示 |

**M2 集成目标**：建 Agent → 私聊发需求 → 真实 Agent 流式回复 → 任务自动出现在 TaskBoard。一条链路跑通三域。
