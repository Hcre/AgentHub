# 会话归档（archive）落地

- **日期**: 2026-06-10
- **作者**: 袁 (xiangbianpangde)
- **分支**: feature/chat/conversation-archive
- **关联**: PRD §1 IM 聊天「对话列表（新建/置顶/归档/搜索/排序）」最后缺口

## 背景

STATUS 对账中「对话列表」长期标 ⚠️ 部分：置顶/搜索/排序/新建早已实现，唯独**归档**缺失。本次补完，使该子功能升 ✅，整体覆盖率 74%→76%。

## 改动

| 文件 | 改动 |
|------|------|
| `types/index.ts` | `Conversation.archived?: boolean`；`IconName` 加 `archive`/`archiveRestore` |
| `components/ui/Icon.tsx` | 注册 lucide `Archive`/`ArchiveRestore` |
| `stores/chatStore.ts` | 新增 `setConversationArchived` action（并补全 `setConversationPinned` 的接口声明缺口） |
| `components/layout/LeftPanel.tsx` | 主私聊列表 `dmList` 过滤 `archived`；新增 `archivedList` memo（受同一搜索词过滤）+ `handleToggleArchive`（归档当前会话时自动切到剩余最近会话）；DM 项加归档 hover 按钮；底部新增「已归档 (N)」可折叠分区（取消归档按钮） |
| `components/layout/__tests__/LeftPanel.archive.test.tsx` | 3 vitest：归档/取消归档往返 + 不影响其他会话 |

## 验证（三档）

1. **tsc + eslint**：全绿
2. **vitest**：新增 3 测全过 + 既有 `LeftPanel.pin` 3 测无回归（layout 套件 12/12 绿）
3. **Playwright 真实往返**（dev :5300，注入 2 agent×4 会话）：
   - 归档「投资人备忘」→ store `archived:true`，主列表移除，出现「已归档 (1)」分区
   - 展开分区 + 取消归档 → `archived:false`，回到主列表，空分区消失
   - 截图：`docs/deliverables/screenshots/conv-archive-01-before.png` / `conv-archive-02-archived.png`
   - Console：仅 6 条后端 502（未起后端），**无本功能相关报错**

> 测试注入用的 DEV-only store 暴露（main.tsx）已在 commit 前回退，归档逻辑本身为真实运行。

## 设计取舍

- **local-only**：归档复用 `conversations` 持久化（zustand persist），不新增后端 session 字段——与置顶不同（置顶需 PATCH backing session）。归档是纯客户端展示态，无需服务端，避免过度设计。
- **分区默认收起**：归档为低频项，`openArchived` 默认 false。
- **仅有归档项时才渲染分区**：避免空分区噪音。

## 给下一位的交接

- 若后续要让归档**跨设备同步**，需在 `sessions` 表加 `archived` 列 + PATCH 端点（参照 `pinned` 的全链路）；当前仅本地。
- 群聊（群组）暂未加归档，只做了私聊。若需要可在 group section 复用同模式。
- 注意 `chatStore.ts` 有**历史遗留**：`removeConversation`/`removeConversations` 各重复定义两次（lines ~112/500、~132/514），后定义覆盖前定义，导致前者的 WS 关闭逻辑失活。非本次引入，留独立工单清理。
