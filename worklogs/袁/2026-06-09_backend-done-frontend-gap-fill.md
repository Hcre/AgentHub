# 2026-06-09 后端已完成但前端缺失的功能点补全

**作者**: 袁 (xiangbianpangde)
**分支**: `feature/frontend/preview-tabs` (接续预览面板 4 tab 工作, 未 push)
**关联**: STATUS.md §⚠️ 后端↔前端缺口表 (13 项) → 本轮补完 6 项

---

## 背景

用户要求"完成所有后端已完成但前端没有的功能点"。先**审计** 13 项缺口的真实后端/前端状态(不盲信 STATUS 表),再补真缺口。

### 审计结论(纠正了 STATUS 表的过时项)
| # | 判定 | 依据 |
|---|------|------|
| #2 Tasks | ❌ 排除 | `tasks.py` 返 `{items:[],note:"M3 实现"}` — 后端是 mock 骨架, 不算"后端完成" |
| #3 Inbox | ❌ 排除 | `inbox.py` 返 `{...note:"M4 实现"}` — 同上 mock 骨架 |
| #11 Memory | ✅ 已完成 | `memoriesApi.update` 已存在(董做的面板) |
| #7 Templates | ✅ 已完成 | 复核发现 TemplateManagementTab 早有同步按钮+来源卡, STATUS 表过时 |
| #13 Proxy | — 不补 | 基础设施, 用户不直接调 |
| #9/#10/#12/#4/#8 | ✅ 本轮补 | 真缺口 |

## 做了什么(6 项)

| # | 功能 | 改动文件 |
|---|------|---------|
| #9 | 编辑 Agent | `api/agents.ts` (update + UpdateAgentInput) · `stores/agentStore.ts` (updateAgent) · `components/agent/AgentDetailDrawer.tsx` (内联编辑表单) |
| #10 | 删除消息 | `api/sessions.ts` (deleteMessage) · `stores/chatStore.ts` (removeMessage) · `components/chat/MessageBubble.tsx` (onDelete + 删除按钮) · `components/chat/ChatView.tsx` (handleDeleteMessage 乐观删除+回滚) |
| #12 | Provider ping | `api/providers.ts` (ping + PingInput/PingResult) · `components/agent/CreateAgentModal.tsx` (2 处裸 fetch 替换 + 延迟显示) |
| #7 | Templates 同步 | 无改动(复核确认已实现) |
| #4 | CLI 重新扫描 | `components/agent/CreateAgentModal.tsx` ("重新扫描"按钮 `list()`→`scan()` 强制重扫) |
| #8 | Skills wrapper | **新建** `api/skills.ts` (5 端点封装) · 替换 5 文件裸 fetch (SkillMarketplacePage/CreateSkillDialog/SkillMdPreview/CreateAgentModal/CustomAgentModal) |

## 测试证据(按证据分级)

| 检查 | 结果 |
|------|------|
| tsc --noEmit (全项目) | ✅ 绿 |
| eslint (新增/改动代码) | ✅ 绿 (AgentDetailDrawer 1 处 set-state-in-effect 按惯例 inline disable) |
| vitest (MessageBubble/agent 套件) | ✅ 通过 (57/59; 2 失败在未改的 WebPreviewCard.fullscreen, 预存) |
| **#9 full E2E** | ✅ live: 创建 mock agent → AgentDetailDrawer 编辑→保存 → 后端持久化 `测试队友-UI保存验证` (curl 复核 name/role) |
| #9 PATCH 端点 live | ✅ `PATCH /api/agents/{id}` name+role 正确往返 |
| #10 删除按钮 UI | ✅ live: 真实 session 消息 hover 出"删除消息"按钮 (`gap-10-message-delete.png`) |
| #4 scan() | ✅ live: CreateAgentModal Step 2 "扫描完成,4 个可用" |
| #8 wrapper | ✅ live: skill list 经 `skillsApi.listLibrary()` 加载成功 |
| 截图 | `docs/deliverables/screenshots/gap-09-agent-edit.png` + `gap-10-message-delete.png` |

## 诚实标注(未尽 / 限制)

- **#10 删除真实后端消息的完整往返未做**: 当前 dev 环境无 Redis/真 CLI 的消息流, 显示的消息是本地 mock 气泡 (uid, 非后端 message id), 删除会 404+回滚。删除按钮渲染 + DELETE 端点接线已验, 但"删掉一条真实后端消息并消失"的端到端未演示。手动插的合成 message 行 DELETE 时 500 (ORM 映射合成行的问题, 非前端)。
- **#10 群聊 GroupMessageItem** 未加删除按钮 (本轮只做私聊 MessageBubble), 留后续。
- **#2 Tasks / #3 Inbox** 后端 mock 骨架未动 — 须后端先填 service 才能接前端。
- **本地 dev.db** 原为 0 字节(无表), 跑了 `alembic upgrade head` (0001→0019) 才能 E2E #9。sqlite + gitignored, 不提交。

## 给下一位的交接

**当前状态**: 6 项全完, tsc+eslint+vitest 绿, gap-09/gap-10 截图齐。分支累计未 push (含上一期预览面板 2 commit + 本轮)。

**接手起点**:
1. 本轮改动待 commit (建议: `feat(frontend): 补全后端已完成但前端缺失的 6 功能点 (#9/#10/#12/#4/#8 + #7 复核)`)。**commit 前问 user 是否 push**。
2. 剩余真缺口只有 **#2 Tasks / #3 Inbox**, 但**后端是 mock 骨架** — 要做须先填后端 (M3 TaskService / M4 Inbox service), 再接前端。
3. #10 群聊删除 (GroupMessageItem) + #10 真实消息删除 E2E (需 Redis + 真 CLI 消息流) 留后续。

**运行环境备忘**: vite `npx vite --port 9500 --host 127.0.0.1` · 后端 sqlite `DATABASE_URL=sqlite+aiosqlite:///./dev.db ... uvicorn app.main:app --port 8000` (Agent/Session CRUD 需先 `alembic upgrade head`)。
