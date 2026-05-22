# 域1：IM 聊天与交互 — 任务清单

> 职责：会话列表、聊天窗口、消息路由、流式输出、收件箱审批
> 技术栈：React (ChatView/Inbox) + FastAPI (WS/SSE) + PostgreSQL + Redis Pub/Sub

---

## 一、域1 系统范围

```
┌─ 前端 ──────────────────────────────┐
│ ChatView (群聊+私聊)                 │
│ SessionList (会话列表)                │
│ MessageBubble / StreamingText        │
│ DiffCard / PreviewCard               │
│ InboxView (收件箱+审批)               │
└────────────┬────────────────────────┘
             │ WS + REST
┌────────────┴────────────────────────┐
│ L4 API Gateway                      │
│ SessionRouter / WsHandler            │
│ InboxRouter (notifications)          │
│ ApprovalRouter                       │
└────────────┬────────────────────────┘
             │
┌────────────┴────────────────────────┐
│ L3 Application                      │
│ ChatService: send_message()          │
│ InboxService: 通知创建/已读/日历     │
└────────────┬────────────────────────┘
             │
┌────────────┴────────────────────────┐
│ 数据: sessions/messages/notifications│
│ Redis: Pub/Sub + 热上下文             │
└─────────────────────────────────────┘
```

---

## 二、全部任务

### M1（5/20-22）：前端脚手架

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 1.1 | React + Vite + Tailwind + Zustand 脚手架 | 4h | 页面可渲染 |
| 1.2 | 基础组件：ChatWindow + SessionList + MessageBubble | 4h | 静态 UI 可用 |

### M2（5/23-27）：单聊基础

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 1.3 | WebSocket 连接管理 (useWebSocket) + 心跳/重连 | 6h | 延迟 < 500ms，断线 < 3s 恢复 |
| 1.4 | 会话列表 + 创建会话 (POST /api/sessions) | 4h | 私聊/群聊均可创建 |
| 1.5 | 消息发送 + 历史加载 (分页) | 4h | 向上滚动加载更多 |
| 1.6 | StreamingText 流式渲染 | 6h | 逐 token 渲染，无闪烁 |
| 1.7 | 代码块高亮 + 基础文本 Diff | 4h | 代码可读 |
| 1.8 | Agent 列表 + 选择 Agent 进入私聊 | 4h | 点击头像 → 私聊窗口 |

### M3（5/28-6/1）：群聊 + 路由

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 1.9 | 群组创建 + 成员管理 UI | 6h | 创建群组 → 添加 Agent → 协调者自动出现 |
| 1.10 | @mentions 输入自动补全 (AgentMention) | 4h | 输入@ → 弹出列表 → 选择 |
| 1.11 | dispatch_mode 切换 (auto/direct) | 2h | 群聊默认 auto |
| 1.12 | 协调者系统蓝标展示 + 不可移除 | 2h | 成员列表中蓝色标识 |
| 1.13 | 任务分解卡片 (TaskPlanCard) | 4h | 子任务列表 + 负责人 + 依赖箭头 |

### M4（6/2-5）：产物 + 收件箱

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 1.14 | DiffCard：diff2html 内联渲染 + 展开/折叠 | 8h | 绿色/红色标注，每文件 Tab |
| 1.15 | PreviewCard：iframe sandbox 嵌入 | 6h | 点击展开全屏 |
| 1.16 | 收件箱 UI + 未读 Badge | 6h | 分类筛选 + 实时更新 |
| 1.17 | 审批卡片 + APPROVE/REJECT 按钮 | 4h | 审批→Agent 继续/取消 |
| 1.18 | Pin 消息 + 上下文指示器 | 2h | Pin 后视觉标记 |

### M5（6/6-9）：打磨

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 1.19 | 暗色/亮色主题 | 4h | 切换无闪烁 |
| 1.20 | 响应式布局 + 移动端适配 | 4h | 窄屏可用 |
| 1.21 | UI 动画 + 交互细节 | 4h | 流畅 |

---

## 三、工时汇总

| M | 工时 |
|----|------|
| M1 | 8h |
| M2 | 32h |
| M3 | 18h |
| M4 | 26h |
| M5 | 12h |
| **合计** | **96h** |

---

## 四、关键文件

```
frontend/src/
├── components/chat/
│   ├── ChatWindow.tsx         # 主聊天区域
│   ├── SessionList.tsx        # 左侧会话列表
│   ├── MessageBubble.tsx      # 消息气泡分发
│   ├── StreamingText.tsx      # 流式渲染
│   └── AgentMention.tsx       # @自动补全
├── components/cards/
│   ├── DiffCard.tsx           # diff2html 卡片
│   ├── PreviewCard.tsx        # iframe 预览
│   └── TaskPlanCard.tsx       # 任务分解卡片
├── components/inbox/
│   ├── InboxView.tsx          # 收件箱主页
│   ├── ApprovalCard.tsx       # 审批卡片
│   └── CalendarView.tsx       # 日历视图
├── hooks/
│   ├── useWebSocket.ts
│   ├── useStreaming.ts
│   └── useSession.ts
└── stores/
    ├── chatStore.ts
    └── inboxStore.ts
```
