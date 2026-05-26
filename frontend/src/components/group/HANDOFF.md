# 群聊（Phase 4）交接文档

> 当前是**假群聊（mock）**：能跑、能演示，但所有"智能"都是前端模拟。
> 这份文档给后续优化/接真实后端的同学。读完约 3 分钟。

## 现状：能做什么

- 左侧「频道」点击 → 进入对应群聊（`uiStore.openGroup`）
- 群聊头部：频道名 + 描述 + 成员头像条（点头像跳助手详情）+ 主题切换 + 设置
- 频道 Tab：聊天 / 文件 / 任务（文件是占位卡片；任务复用 `taskStore`，按成员过滤）
- 聊天：消息列表（@mention 高亮、协调者分发方案卡、"待批准"标记）+ 输入框
- 输入框：@mention 菜单（协调者 + 成员）、"需批准"开关、Enter 发送
- 发送后 1.2s 出现**模拟回复**（见下方接缝）

## 数据流与文件地图

```
左栏频道点击
  └─ uiStore.openGroup(groupId)        // 路由：section='group' + activeGroupId
       └─ CenterPanel 渲染 <GroupChatView/>   （section==='group' 时整屏，无右侧面板）
            ├─ groupStore.messagesByGroup[groupId]   // 消息数据
            ├─ groupStore.sendGroup(id, text, opts)  // 发送
            └─ 子组件：GroupMessageItem / CoordinatorPlan / GroupComposer / GroupMembersStrip
```

| 文件 | 职责 |
|------|------|
| `src/data/groups.ts` | mock：coordinator / groups / groupMessages 种子 |
| `src/stores/groupStore.ts` | 群组数据 + `sendGroup` + **MOCK SEAM**（`simulateGroupReply`） |
| `src/stores/uiStore.ts` | 路由：`activeGroupId` / `openGroup` / `viewAgent` |
| `src/components/group/GroupChatView.tsx` | 频道整屏视图（header/tabs/列表/composer） |
| `src/components/group/GroupMessageItem.tsx` | 单条消息（含 @mention 富文本、审批提示） |
| `src/components/group/CoordinatorPlan.tsx` | 协调者结构化分发方案卡 |
| `src/components/group/GroupComposer.tsx` | 输入框（@mention 菜单 + 需批准开关） |
| `src/components/group/GroupMembersStrip.tsx` | 成员头像条 |
| `src/components/group/actors.ts` | `who` → 展示 Actor（成员/协调者/user 统一查找） |

## ⚠️ MOCK 接缝（唯一要替换的地方）

全部"假"逻辑集中在 `groupStore.ts` 的 `simulateGroupReply(group, text)`，已用注释框标注。
它根据 @mention 决定谁回：

- `@协调者` → 返回 `kind:'plan'` 的分发方案（**当前是按成员数机械拆分的占位**）
- `@某成员` → 该成员一句 ack
- 无 @ → 协调者兜底 ack

### 接真实后端的步骤（2026-05-26 群聊 V1 + 讨论模式后端落地后）

> 后端 V1 @ 路由 + Selector 讨论循环已实现（commit feature/chat/group-chat-impl）。
> WS 协议与私聊统一为 `/ws/sessions/{session_id}`；StreamEvent 现含 `sender_agent_id` 字段。

1. **发送**：`sendGroup` 里 append 用户消息后，把 `setTimeout(simulateGroupReply...)` 那段删掉，
   改为通过 WS 推送 `{type:"message", content, mentions:[...]}` 到 `/ws/sessions/{group_session_id}`。
   注意 mentions 字段是 `string[]`（Agent name 列表），后端 `_resolve_mentions` 会解析。
2. **接收**：StreamEvent 推到 `messagesByGroup[groupId]`。**按 `sender_agent_id` 区分发言人**：
   - `sender_agent_id == null` → 用户消息（一般不会从 WS 推回，本地 append 即可）
   - `sender_agent_id != null` → 按该 agentId 路由到 `who` 字段，渲染对应 Agent 气泡/颜色
3. **流式聚合**：同一 `sender_agent_id` 的连续 TEXT 事件应聚合成同一条 message（按 seq 升序累加 content）。
   接近私聊 `chatStore.applyStreamEvent` 的逻辑，但 key 从 convKey 改为 `(groupId, sender_agent_id, latestSeqStart)`。
4. **死群兜底**：用户无 @ 且群组 `dispatch_mode != DISCUSSION` → 后端静默，无回复。
   前端不要 spinner 等回复，按发送即送达处理。
5. **讨论模式**：群组配置 `dispatch_mode=discussion` 时，无 @ 也会进入 Selector 回合循环。
   多个 Agent 会被依次唤起（串行），每位发言完一条独立 message。前端不需要特殊处理，
   按 `sender_agent_id` 自然渲染即可。
3. **类型已就位**：后端返回的消息只要符合 `GroupMessage`（`src/types/index.ts`）即可直接渲染，
   `kind:'plan'` + `CoordinatorPlan` 结构对应协调者拆解结果。
4. **审批**：`requiresApproval` 的消息目前只打标记。真实流程应：发起 → 进「收件箱·审批」(Phase 5 `inbox`)
   → 批准后后端才让助手执行。前端把审批项接到 inbox store 即可。
5. **派发按钮**：`CoordinatorPlan` footer 的「派发」目前是空按钮。应调
   `POST /api/tasks`（按 plan.steps 批量建任务），建完让这些子任务出现在「任务」看板（`taskStore`）。

### 与后端契约对齐

- 群组/成员：`GET /api/groups`（对应 PRD §6.2）。当前 `groups.ts` 的结构需与后端 schema 对齐。
- @mention 路由、协调者拆解：属域2 编排（见 `spec/domains/domain2-orchestration_域2-Agent编排.md`）。
- 协调者是一个 `id:'coordinator'` 的特殊 agent，不在普通 `agents` 列表里。

## 已知简化 / 待优化

- 分发方案卡的「改一下 / 派发」未接逻辑（应分别触发重新拆解 / 批量建任务）。
- @mention 只做了文本高亮 + 首个 mention 路由；多 mention、@all、自动补全未做。
- 文件 Tab 是写死的占位卡片。
- 群聊消息未持久化（刷新即回到种子数据）。
- 群组成员管理（加人/移除/建频道）未做；左栏频道「+」也未接。
- 时间戳用种子里的固定串 / `nowStamp()`，未统一格式化。
