# CLI 流式输出架构设计

> **状态**: Phase 1 实施中 | **最后更新**: 2026-06-08 | **关联 ADR**: 0001 CLI 优先
>
> 本文档统合四运行时（ClaudeCode / OpenCode / Codex / PiAgent）流式事件映射分析、
> 前端渲染缺失分析、权限架构评估，形成完整的流式输出架构方案。

---

## 一、现状总览

### 1.1 协议层：StreamEventType（8 种事件类型）

定义于 `src/backend/app/domain/llm/protocol.py`：

| 事件类型 | 语义 | 前端 Store | 前端渲染 |
|----------|------|-----------|---------|
| `text` | 增量文本 | append to streaming message text | ReactMarkdown in MessageBubble |
| `thinking` | 模型思考过程 | **丢弃** | **不渲染** |
| `tool_call` | Agent 请求工具调用 | **丢弃** | **不渲染** |
| `tool_result` | 工具执行结果 | **丢弃** | **不渲染** |
| `request_approval` | 权限审批请求（事后） | **丢弃** | **不渲染** |
| `task_plan` | 任务计划 | **丢弃** | **不渲染** |
| `error` | 执行错误 | 独立错误气泡 | 错误文本 in MessageBubble |
| `done` | 流结束 | 哨兵消息 → 真实 ID | 完成渲染 |

**当前前端丢弃行**（`chatStore.ts:166` / `groupStore.ts:229`）：
```typescript
// thinking / tool_* / task_plan / request_approval：MVP 暂不渲染
return {}
```

### 1.2 四运行时事件生产能力矩阵

| 事件类型 | ClaudeCode | OpenCode | Codex | PiAgent |
|----------|-----------|----------|-------|---------|
| `text` | YES | YES | YES | YES |
| `thinking` | -- | YES | -- | YES |
| `tool_call` | YES | YES | -- | YES |
| `tool_result` | YES | YES | -- | YES |
| `request_approval` | -- | -- | -- | YES |
| `task_plan` | -- | -- | -- | -- |
| `error` | YES | YES | YES | YES |
| `done` | YES | YES | YES | YES |

**关键发现**：
- `task_plan` 当前**没有任何运行时生产**，仅为协议预留。
- `request_approval` 仅 PiAgent 通过 `extension_ui_request` RPC 生产。
- `thinking` 被 ClaudeCode 的 `_parse_line` 静默丢弃（只处理 `text` 和 `tool_use` 块）。

---

## 二、各运行时事件映射详情

### 2.1 ClaudeCode Runtime

**CLI 模式**: `claude --output-format stream-json --print --permission-mode acceptEdits`

| CLI 事件类型 | AgentHub 动作 | 映射的 StreamEvent | 备注 |
|-------------|--------------|-------------------|------|
| `system` | 丢弃 | -- | 初始元数据（模型名/工作区/工具列表）全部丢弃 |
| `assistant` → `text` 块 | 解析 | `TEXT` | 增量文本 |
| `assistant` → `tool_use` 块 | 解析 | `TOOL_CALL` | `call_id`/`name`/`input` |
| `assistant` → `thinking` 块 | **丢弃** | -- | Claude 扩展思考输出不可见 |
| `assistant` → 其他块类型 | **丢弃** | -- | 无兜底处理器 |
| `assistant` → `message.usage` | 解析 | `TEXT`（metadata） | Token 用量挂载到空文本事件 |
| `user` → `tool_result` | 解析 | `TOOL_RESULT` | `is_error` 决定 content/error 分流 |
| `user` → 其他块 | **丢弃** | -- | 非 tool_result 的 user 事件忽略 |
| `result` | 解析 | `DONE` | 提取 model/cost/duration + permission_denials/errors |

**已知缺失**：
- `thinking` 块 → 未发射 THINKING 事件
- `permission prompt` (ask-user) → 未发射 REQUEST_APPROVAL（仅在 DONE 元数据事后收集）
- `num_turns` → DONE 元数据未包含
- `ToolResult.artifact`（Diff/Preview/Deploy URL）→ 从未填充

### 2.2 PiAgent Runtime

**CLI 模式**: Pi RPC over stdio

| RPC 类型 | StreamEvent | 备注 |
|----------|------------|------|
| `message_update` → `text_delta` | `TEXT` | 增量文本 |
| `message_update` → `thinking_delta` | `THINKING` | **唯一正确发射 THINKING 的运行时** |
| `message_update` → `toolcall_end` | `TOOL_CALL` | 工具调用完成时整块发射 |
| `message_update` → `done` | --（丢弃） | 等待顶层 `agent_end` |
| `message_update` → `error` | `ERROR` | 错误消息 |
| `message_start` (role=assistant) | `TEXT`/`THINKING`/`TOOL_CALL` | 非流式模式：解析完整 message.content |
| `message_end` | `TEXT`/`THINKING`/`TOOL_CALL`/`ERROR` | 最终消息 |
| `tool_execution_start` | --（丢弃） | 等待 tool_execution_end |
| `tool_execution_end` | `TOOL_RESULT` | 工具执行结果 |
| `agent_end` | `DONE` | 提取 model + usage（来自最后一条 assistant 消息） |
| `extension_ui_request` | `REQUEST_APPROVAL` | **唯一发射 REQUEST_APPROVAL 的运行时** |
| `response` (success=false) | `ERROR` | RPC 命令响应失败 |

### 2.3 OpenCode Runtime

| 事件 | StreamEvent | 备注 |
|------|------------|------|
| `text` 增量 | `TEXT` | 标准文本流 |
| `thinking` 增量 | `THINKING` | 思考过程 |
| `tool_call` | `TOOL_CALL` | 工具调用 |
| `tool_result` | `TOOL_RESULT` | 工具结果 |
| `error` | `ERROR` | 错误 |
| `done` | `DONE` | 流结束 |

### 2.4 Codex Runtime

| 事件 | StreamEvent | 备注 |
|------|------------|------|
| `item.completed` (text) | `TEXT` | 仅处理文本完成项 |
| `turn.completed` | `DONE` | 轮次结束 |
| 其他工具事件 | **丢弃** | Codex 发射但 Runtime 不解析 tool_call/tool_result |

---

## 三、前端渲染方案

### 3.1 渲染优先级与位置

在 MessageBubble 中，各块按以下顺序渲染：

```
1. Reply quote（引文小气泡，已有）
2. ThinkingBlock — Agent 的推理过程，在主文本之上
3. TaskPlanBlock — 结构化任务计划，在回答前展示
4. Main text content — ReactMarkdown 渲染的主文本
5. ToolCallBlock + ToolResultBlock 配对 — 工具调用技术细节，在主文本之下
6. ApprovalRequestBlock — 阻断性操作，需要用户交互
7. WebPreviewCard / DeployCard / Attachment / Actions（已有）
```

### 3.2 ThinkingBlock

**视觉特征**：琥珀色主题，可折叠，默认流式中展开/完毕后收起。

- 容器：`rounded-lg border border-amber-200/60 bg-amber-50/40 dark:bg-amber-950/20 px-3 py-2`
- 图标：`Brain` from lucide-react, `h-4 w-4 text-amber-600`，流式时 `animate-pulse`
- 标签：「思考过程」（中文），流式时追加 `…`
- 折叠：默认展开（流式中）→ 完成后收起
- 内容：ReactMarkdown 渲染，去除标题层级保持视觉扁平
- 流式游标：`w-1.5 h-4 bg-amber-500 animate-pulse`
- 用户交互：点击头部切换折叠；hover 显示复制按钮

**Store 集成**：
- `ChatMessage.thinking?: string` — applyStreamEvent 追加 `event.content`
- done 时保持 thinking 文本，streaming=false

### 3.3 ToolCallBlock

**视觉特征**：中性锌色主题，默认折叠，显示工具名+状态指示器。

- 容器：`rounded-lg border border-zinc-300/60 dark:border-zinc-700/60 bg-zinc-100/60 dark:bg-zinc-900/40`
- 图标：`Wrench` from lucide-react, `h-3.5 w-3.5 text-zinc-500`
- 工具名：`font-mono text-[12px] font-semibold`
- 状态指示器：pending→`Loader2` spinner, success→`CheckCircle` green, error→`XCircle` red
- 参数预览：`font-mono text-[11px] truncate max-w-[300px]`（前 60 字符）
- 折叠：默认折叠，用户点击展开查看完整 JSON 参数
- 与 ToolResultBlock 垂直配对，共享连续左边框

**Store 集成**：
- `ChatMessage.toolCalls?: ToolCallEntry[]`
- `ToolCallEntry = { id, callId, name, args, status: 'pending'|'success'|'error' }`
- `tool_call` 事件 → push 新条目（status=pending）
- `tool_result` 事件 → 按 callId 匹配更新 status

### 3.4 ToolResultBlock

**视觉特征**：嵌套在 ToolCallBlock 下方，显示工具返回内容。

- 容器：`border-t border-zinc-200/40 bg-zinc-50/40 dark:bg-zinc-950/30 px-3 py-2`
- 图标：`FileOutput` from lucide-react — green for success, red for error
- 标签：「返回结果」（成功）/「执行出错」（失败）
- 结果预览：`font-mono text-[11px] truncate`（前 80 字符）
- 折叠：**默认折叠**（工具结果嘈杂）
- 长文本截断：> 2000 字符显示前 2000 +「显示全部」按钮
- 内容区域：等宽字体，`max-h-48 overflow-y-auto`

**Store 集成**：
- `ChatMessage.toolResults?: ToolResultEntry[]`
- `ToolResultEntry = { id, callId, content, isError }`

### 3.5 ApprovalRequestBlock

**视觉特征**：突出琥珀色双线边框，**不可折叠**（阻断性操作），带批准/拒绝按钮。

- 容器：`rounded-lg border-2 border-amber-400/70 dark:border-amber-500/50 bg-amber-50/60 px-4 py-3 shadow-sm`
- 图标：`ShieldAlert` from lucide-react, `h-4 w-4 text-amber-600`
- 标题：「需要你的确认」
- 状态徽章：`待确认`(amber) / `已批准`(green) / `已拒绝`(red)
- 批准按钮：`Button variant='default' size='sm'` + Check 图标
- 拒绝按钮：`Button variant='outline' size='sm'` + X 图标
- 交互后：按钮消失，显示「已由 {user} 处理」
- **Phase 1 限制**：按钮为纯视觉占位，点击后仅翻转本地状态（乐观更新）。
  后端审批端点（`POST /api/approvals/{id}/resolve`）待 Phase 2 落地。

**Store 集成**：
- `ChatMessage.approvalRequest?: ApprovalRequestData`
- `ApprovalRequestData = { id, action, description, metadata?, status: 'pending'|'approved'|'denied', resolvedBy?, resolvedAt? }`

### 3.6 TaskPlanBlock

**视觉特征**：靛蓝色主题，默认展开（用户应首先看到计划）。

- 容器：`rounded-lg border border-indigo-200/70 dark:border-indigo-700/50 bg-indigo-50/30 dark:bg-indigo-950/20 px-4 py-3`
- 图标：`ListTodo` from lucide-react, `h-4 w-4 text-indigo-600`
- 标题：「任务计划」+ 步骤计数徽章「N 步」
- 步骤行：编号圆圈 + 标签 + 依赖标注 + 预计耗时
- 步骤间连接线：`border-l border-dashed border-indigo-200`
- 摘要行：总预计耗时
- 折叠：首次到达展开，之后可折叠
- 用户交互：点击头部切换折叠；hover 显示复制按钮
- **当前状态**：`task_plan` 无运行时生产，此组件为预留基础设施。
  后端 `TASK_PLAN` 事件生产待 Phase 2（pre-flight plan mode）。

---

## 四、权限架构

### 4.1 当前状态

| 能力 | 状态 |
|------|------|
| CLI permission mode | 硬编码 `acceptEdits`（`claude_code_runtime.py:50`） |
| permission_denials 事后检测 | 已实现（`chat_service.py:241-257`） |
| REQUEST_APPROVAL 事件发射 | 已实现（事后模式） |
| 前端渲染 REQUEST_APPROVAL | **丢弃**（chatStore.ts:166） |
| 重试端点 | **不存在** |
| 审批队列 / Inbox 集成 | **不存在** |

### 4.2 三种方案评估

#### 方案 A：实时交互式权限（拒绝）

- **原理**：拦截每个被阻止的工具调用，暂停 Agent，等待用户批准
- **阻塞因素**：Claude Code CLI `--print` 模式是非交互的，不发射 `permission_request` 事件，不等待 stdin
- **结论**：不可行，除非完全重建执行架构

#### 方案 B：事后审批 + 重试（Phase 1 采纳）

- **原理**：Agent 完成 → 收集 permission_denials → 展示审批卡 → 用户批准 → 以 `bypassPermissions` 重试
- **可行性**：中高。基础设施已大部就位
- **复杂度**：中。3 个新文件/模块 + 修改现有
- **跨 CLI 兼容性**：好。大多数 CLI 输出结构化错误/拒绝指示器
- **风险**：重试整个 Agent 轮次而非仅被阻止操作。缓解：使用 `--resume` 保留上下文

#### 方案 C：预飞计划审批（Phase 2 目标）

- **原理**：执行前 Agent 生成计划 → 用户审批 → Agent 按批准计划执行
- **可行性**：中高。协议已有 TASK_PLAN
- **UX**：最佳。用户在任何操作发生前控制
- **跨 CLI 兼容性**：最佳。依赖 Agent 推理而非 CLI 特定权限模型

### 4.3 推荐策略：C（主）+ B（安全网）

```
User sends message
        │
        ▼
  plan_first? ──yes──→ CLI: 计划模式 → TASK_PLAN → [Approve/Edit/Deny]
        │                                                │
        no                                               ▼
        │                                         CLI: bypassPermissions
        ▼                                         --resume + approved plan
  CLI: acceptEdits                                       │
  (直接执行)                                              ▼
        │                                          DONE (clean)
        ▼
  DONE with permission_denials?
        │
        yes
        ▼
  REQUEST_APPROVAL → [Retry] [Dismiss]
        │
        ▼
  CLI: bypassPermissions --resume
  (仅重新执行被阻止操作)
```

### 4.4 分阶段路线

| 阶段 | 内容 | 预估 |
|------|------|------|
| **Phase 1**（当前） | 前端渲染 5 种事件类型；Thinking/ToolCall/ToolResult/ApprovalCard/TaskPlan 可视化 | 2-3 天 |
| **Phase 2** | 后端重试端点 + 预飞计划模式；Inbox 审批队列集成 | 1-2 周 |
| **Phase 3** | 全局模式切换 + Redis 允许列表 + 24h 超时自动拒绝 | 1 周 |

---

## 五、数据模型扩展

### 5.1 ChatMessage 新增字段

```typescript
interface ChatMessage {
  // ...existing fields...
  thinking?: string
  toolCalls?: ToolCallEntry[]
  toolResults?: ToolResultEntry[]
  approvalRequest?: ApprovalRequestData
  taskPlan?: TaskPlanData
}

interface ToolCallEntry {
  id: string
  callId: string
  name: string
  args: Record<string, unknown>
  status: 'pending' | 'success' | 'error'
}

interface ToolResultEntry {
  id: string
  callId: string
  content: string
  isError: boolean
}

interface ApprovalRequestData {
  id: string
  action: string
  description: string
  metadata?: Record<string, unknown>
  status: 'pending' | 'approved' | 'denied'
  resolvedBy?: string
  resolvedAt?: string
}

interface TaskPlanData {
  summary: string
  steps: TaskPlanStep[]
  totalEta?: number
}

interface TaskPlanStep {
  id: string
  label: string
  eta?: number
  depends?: string[]
}
```

### 5.2 GroupMessage 同步扩展

GroupMessage 获得相同的 `thinking`/`toolCalls`/`toolResults`/`approvalRequest`/`taskPlan` 可选字段。

所有字段默认为 `undefined`，现有消息序列化无影响（Zustand persist 兼容）。

---

## 六、文件变更清单（Phase 1）

| 文件 | 操作 | 说明 |
|------|------|------|
| `docs/plan/cli-streaming-architecture_流式输出架构设计.md` | **新增** | 本文档 |
| `src/frontend/src/types/index.ts` | 修改 | 新增 ToolCallEntry / ToolResultEntry / ApprovalRequestData / TaskPlanData 接口；ChatMessage 和 GroupMessage 新增可选字段 |
| `src/frontend/src/stores/chatStore.ts` | 修改 | `applyStreamEvent` 处理 thinking / tool_call / tool_result / request_approval / task_plan |
| `src/frontend/src/stores/groupStore.ts` | 修改 | `applyGroupStreamEvent` 同上 |
| `src/frontend/src/components/chat/ThinkingBlock.tsx` | **新增** | 思考过程渲染组件 |
| `src/frontend/src/components/chat/ToolCallBlock.tsx` | **新增** | 工具调用渲染组件 |
| `src/frontend/src/components/chat/ToolResultBlock.tsx` | **新增** | 工具结果渲染组件 |
| `src/frontend/src/components/chat/ApprovalRequestBlock.tsx` | **新增** | 审批请求渲染组件 |
| `src/frontend/src/components/chat/TaskPlanBlock.tsx` | **新增** | 任务计划渲染组件 |
| `src/frontend/src/components/chat/MessageBubble.tsx` | 修改 | 集成 5 个新 Block 组件到渲染顺序 |
| `src/frontend/src/components/group/GroupMessageItem.tsx` | 修改 | 同上（群聊版本） |

---

## 七、后端缺口（Phase 2+）

| 缺口 | 影响 | 优先级 |
|------|------|--------|
| ClaudeCode `thinking` 块丢弃 | 扩展思考不可见 | 中 |
| ClaudeCode 无 `REQUEST_APPROVAL` 中继 | 权限提示无法实时 | 高 |
| `task_plan` 无运行时生产 | TASK_PLAN 事件永不发射 | 低（先有前端基建） |
| `ToolResult.artifact` 未填充 | Diff/Preview URL 不可用 | 低 |
| `system` 事件元数据丢弃 | 模型/工作区信息不可用 | 低 |
| Codex `tool_call`/`tool_result` 解析缺失 | 工具调用不可见 | 中 |
