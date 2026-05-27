# 群聊（Phase 4 + WS 接入）交接文档

> 状态：群聊已接入真实后端 WS。Mock seam 已移除。读完约 3 分钟。

## 现状：能做什么

- 左侧「频道」点击 → 进入对应群聊（`uiStore.openGroup`）
- 切换群聊时自动 `findOrCreateSession` → 拉历史 → 挂 WS（`/ws/sessions/{session_id}`）
- 用户发送消息 → 解析 @mention → WS 推送 `{type:"message", content, mentions, dispatch_mode:"auto"}`
- 后端 StreamEvent 实时推回 → 按 `sender_agent_id` 聚合到对应 Agent 气泡 → 完成后哨兵 id 替换为正式 id
- 流式中文末显示闪烁光标（`msg.streaming === true`）
- @mention 菜单：协调者 + 群成员（`agentStore.agents` + `group.coordinatorName`）
- 频道 Tab：聊天 / 文件（占位）/ 任务（按成员过滤 `taskStore`）

## 数据流与文件地图

```
左栏频道点击
  └─ uiStore.openGroup(groupId)
       └─ <GroupChatView/>
            ├─ effect 1: groupsApi.findOrCreateSession(groupId)
            │             → groupStore.setGroupSession(groupId, sessionId)
            ├─ effect 2: groupStore.loadGroupHistory(groupId)  // GET /api/sessions/{sid}/messages
            ├─ effect 3: useGroupWebSocket(groupId, sessionId) // 连 /ws/sessions/{sid}
            │             onmessage → groupStore.applyGroupStreamEvent(groupId, event)
            ├─ render: groupStore.messagesByGroup[groupId]
            └─ <GroupComposer onSend={(text, opts) => sendGroup(groupId, text, opts)}/>
                                                  ↑
                                       sendGroup 通过 store.ws 直接发 WS
```

| 文件 | 职责 |
|------|------|
| `src/types/index.ts` | `Group`（+ `coordinatorId/Name/Role`）、`GroupMessage`（+ `streaming/mentions`）、`StreamEvent` |
| `src/api/sessions.ts` | `list({type})` / `createGroup` / `messages` |
| `src/api/groups.ts` | `list/create/rename/remove/checkName` + `findOrCreateSession` |
| `src/stores/groupStore.ts` | 群组 CRUD + WS 状态（`ws/connected`）+ 流式聚合（`applyGroupStreamEvent`）+ `sendGroup` |
| `src/stores/uiStore.ts` | 路由：`activeGroupId` / `openGroup` / `viewAgent` |
| `src/hooks/useGroupWebSocket.ts` | WS 生命周期 + 指数退避重连 + 把实例写入 store |
| `src/components/group/actors.ts` | `lookupActor(who, group?)`：优先 `agentStore`，协调者走 `group.coordinator*`，未知 UUID 走哈希色 |
| `src/components/group/GroupChatView.tsx` | 整屏视图 + 3 个生命周期 effect |
| `src/components/group/GroupMessageItem.tsx` | 单条消息（@mention 富文本 + 协调者徽章 + 流式光标） |
| `src/components/group/CoordinatorPlan.tsx` | 协调者结构化分发方案卡（M3 后端落地后会有真实数据） |
| `src/components/group/GroupComposer.tsx` | 输入框 + @mention 菜单（数据源：agentStore） |
| `src/components/group/GroupMembersStrip.tsx` | 成员头像条 |

## 后端契约

- WS：`/ws/sessions/{session_id}`，客户端发 `{type:"message", content, mentions[], dispatch_mode}`，服务端推 `StreamEvent`
- 群聊 session：先 `GET /api/sessions?type=group` 找已有，找不到 `POST /api/sessions {type:"group", group_id}`
- 历史：`GET /api/sessions/{sid}/messages`，字段包含 `sender_agent_id` / `created_at` / `mentions`
- 协调者：后端 Agent `is_system=true`，**不在 `GET /api/agents` 返回里**（被 `loadAgents()` 过滤），通过 `ApiGroup.coordinator` 拿到信息

## 流式聚合机制

哨兵 id 格式：`__streaming__{groupId}:{sender_agent_id}`，按发言人独立。同轮多 Agent 串行发言时互不干扰。

| event.type | 行为 |
|-----------|------|
| `text` | 累加到该 sender 的哨兵；无哨兵则新建 `streaming: true` |
| `done` | 哨兵 id 替换为 `uid('gm')`、`streaming: false` |
| `error` | 删除哨兵 + 追加 ⚠️ 错误消息 |
| `thinking`/`tool_*`/`request_approval`/`task_plan` | MVP 不渲染（保留扩展） |

## 降级行为

| 场景 | 行为 |
|------|------|
| 后端不可用 | `findOrCreateSession` catch → 无 session；`sendGroup` 仅本地回显 |
| WS 断开 | 指数退避重连（1s→2s→4s→...→10s max） |
| `sender_agent_id == null` | `who = 'unknown'`，灰色默认头像 |
| 协调者不在 agentStore | `lookupActor` 用 `group.coordinatorName` 兜底，未配则 `'协调者'` |
| 历史无 `created_at` | 当前时间（刷新后时间跳跃，不影响功能） |

## 已知简化 / 待优化

- 分发方案卡的「改一下 / 派发」未接逻辑（M3 Coordinator 实施后再接 `POST /api/tasks` 批量建任务）
- 审批流（`requiresApproval` + 收件箱）未接：当前只打标记
- `request_approval` StreamEvent 暂不渲染（后端权限阻断时会推，前端需要弹审批卡）
- 多 @mention 提示：当前 composer 只支持单条 @，多个用户手动输入
- 文件 Tab 是写死的占位卡片
- 时间戳格式简单（`M月D日 HH:mm`），未做相对时间 / 今天/昨天分组
