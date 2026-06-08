# 当前状态

> 更新:2026-06-091:40整合版 (整理而非瘦身) +2026-06-0900:45 真测补完标注 (per [test-report-2026-06-09-comprehensive.html](docs/reports/test-report-2026-06-09-comprehensive.html)) + **2026-06-091:40 后端 ↔ 前端缺口盘点 (per袁1:28a~1:31a inventory + 本轮 grep复核)**
> - 数据源: `docs/plan/背景.md` (PRD +考察要点 +交付物) + git `200aba4:STATUS.md` (旧198 行) +3 新 ADR (0016/0017/0018) + worklogs/{袁,董,黎}/ + **本轮 grep16 router ×8 client ×7 nav实证**
> - 规则: 每次 push 或开始/结束任务时, 更新你自己那一行
> - 强约束: pre-push markdownlint-cli2 (D-13) — MD024/036/041 严, MD013 关 (per 2026-06-08 决策"不要瘦身")
> - 谁做的: 每个事件段首加 `[owner]` 标签, 进度表 row 直接 = 该人本周完成清单

---

## 📊 三人进度 (per git HEAD 200aba4, 06-08 EOD)

| 我 | 正在做 | 阻塞？ | 本周完成了 |
|----|--------|--------|-----------|
| **黎** (oldmanpushbike) | 网页侧栏预览 + 版本稳定 push main | 无 | Template v4 (192 模板+favorites) ✅ + CLI streaming 全线 (5 种流式事件 UI+折叠组) ✅ + 图标居中 ✅ + 弹窗关闭修复 ✅ + bypassPermissions ✅ + scanner 精简 ✅ + 网页侧栏预览 ✅ + 删除确认弹窗 ✅ + 会话最近消息 ✅ |
| **董** (yii.d) | 协调者+任务编排部分 | 无 | 群聊全栈实现 ✅ + CLI 多模型代理 ✅ + ADR-02 长驻 CLI ✅ + 前端群聊 ✅ + 记忆系统 B 方向设计 ✅ + B1 后端实现 ✅ + B2 详细设计 ✅ + Agent 创建全链路 6 处 bug 修复 + 9 个测试 ✅ + MCP save_memory 端到端打通 ✅ + 前端记忆面板 ✅ + 记忆分支合并 main ✅ |
| **袁** (xiangbianpangde) | t7 phase-3 push + t3 MCP F3 路径 A 等 push | 🟢 t3 23:03 SLA 路径 A 已闭环, 等 push | t3 MCP P3 F3 路径 A @22:00 (2 commit fde10e4 + a2b9ff3) ✅ + t7 phase-3 @21:14 (4 commit pushed) ✅ + t7 partial @20:29 + t12 @19:43 + t6 @19:38 + t1/t2/t4 @19:18 + t8+t9 @18:45 + **2026-06-09 00:45 真测补完** (mcp.py 重复路由修复 + 4 路径 live curl + t7 pin Playwright 3 截图, 3 真 bug 暴露, pytest 332/351 + vitest 106/108 + live API 12/13 端点, 详见 [test-report-2026-06-09-comprehensive.html](docs/reports/test-report-2026-06-09-comprehensive.html)) |

---

## 🎯 考察要点 4 维度覆盖 (per `docs/plan/背景.md` line 57-77)

| 维度 | 权重 | 评判要点 | 当前覆盖 | 谁做的 |
|------|------|---------|---------|-------|
| AI 协作能力 | 30% | 沉淀出和 ai 协作的 Spec/skill/rules 等协作规范 | ✅ `docs/conventions/` 9 篇 + `docs/specs/` 13 篇 + `worklogs/decisions/` 18 ADR + `skills/` 9 个 + `docs/templates/` 14 个 | 全员（黎/董/袁 + Mavis owner）|
| 功能完整度 | 25% | IM 核心体验是否流畅、多 Agent 调度是否跑通 | ⚠️ **67%** (15 完整 + 5 部分 + 5 未做 + 1 计划)，详见 [PRD 6 大功能对账](#-prd-6-大核心功能-vs-现状-对账) | 全员 |
| 生成效果质量 | 20% | 聊天 UI 体验、产物预览效果 | ✅ Web 端 localhost:5174 跑通, S2 群聊 6 条消息流 (用户→Coordinator 拆解→Claude/OpenCode/MockBot 并行→合并汇报) | 黎（UI 打磨）+ 董（前端群聊）|
| 代码理解度 | 15% | 答辩时能否解释架构选型和核心逻辑 | ✅ 5 层洋葱架构图（[01-architecture](docs/conventions/01-architecture_架构设计规范.md) §一）+ 5 主表 ER 图（[03-data-model](docs/specs/03-data-model_数据模型.md) §二）+ 命令 reference (docs/plan/.../commands-reference.md) | Mavis owner (plan_ba86c4d0 docs-writer 任务) |
| 创新与产品感 | 10% | 超预期功能点或体验优化 | ✅ 11 个真 Agent 队友 (含 Codex/OpenCode/Pi) + CLI/SDK 双轨适配器 (ADR-0001) + Pin 消息 + 部署卡 + 4 栏响应式 (useMediaQuery, 768/1024/1280/hamburger) | 全员 |

---

## 📦 交付物 4 项 (per `docs/plan/背景.md` line 78-82)

| # | 交付物 | 位置 | 状态 | 谁做的 |
|---|--------|------|------|-------|
| 1 | 产品设计文档 + 技术文档飞书文档 | `docs/plan/背景.md` (PRD) + `docs/specs/00-05` (13 份规格) + 飞书 (`docs/deliverables/AI协作开发记录.md` 12.1KB CJK 3214 6 段) | ✅ done (凌晨冲刺 plan_bcf9945c `602026f`+`82b265a`) | Mavis owner (plan_ba86c4d0 docs-writer) |
| 2 | 可运行 Demo github 仓库地址 | 当前仓库, main `eea1d0e` + 后续 6/7-6/8 多次 merge | ✅ done | 全员 |
| 3 | AI 协作开发记录 | 仓库内 `docs/deliverables/AI协作开发记录.md` 12.1KB CJK 3214 6 段 a-f + 飞书文档 (per 背景 line 81) | ✅ done (v1 override_accept + v2 attempt 2 PASS) | Mavis owner |
| 4 | 3-10 分钟 Demo 视频 | `docs/deliverables/video/AgentHub-Demo-Video.mp4` 17.7MB 200s 1920x1080 h264+aac+mov_text 字幕 zho + 7 TTS wav + 2 AI cover + 27 subtitle | ⚠️ done (v4 录屏 DISPLAY1 wallpaper 残留; v5 Win32 SetWindowPos + ffmpeg crash 失败; 已透明声明, **建议下阶段 v6 用真实工作流重做 per [ADR-0016](worklogs/decisions/0016-playwright-mcp-replace-cu-for-e2e-visual.md)**) | Mavis owner |

---

## 🎯 PRD 6 大核心功能 vs 现状 对账

> 评估依据: `plan_ba86c4d0` 7 impl commit 落 main (HEAD `eea1d0e`) + 凌晨冲刺 4 commit + E2E 实测 + 代码阅读
> 6 大功能子项共 25, 详见 `docs/plan/背景.md` line 15-56
> [2026-06-07 22:00 重对账, Phase 2 Playwright E2E 后] 覆盖率 = (15+5×0.5)/(15+5+5+1) = **67%** (per [ADR-0017](worklogs/decisions/0017-prd-core-feature-25pct-gate-audit.md))

| # | 子功能 | 状态 | 证据 | 谁做的 |
|---|--------|------|------|-------|
| **1. IM 聊天** | 对话列表（新建/置顶/归档/搜索/排序）| ⚠️ 部分 | 群组/私聊 tab + 卡片渲染；**置顶 [已真实测试 (AI 模拟)] / 归档/搜索未做**（UI 缺；归档/搜索 pytest only 未真测）| 黎（UI 基础）+ M5/M6 手动补 + 袁 (6/9 t7 pin Playwright 3 截图, [test-report-2026-06-09-comprehensive.html](docs/reports/test-report-2026-06-09-comprehensive.html) §6) |
| | 单聊 1v1（明确任务）| ✅ 完整 | S1 私聊 "技术负责人" + 3 建议 + 输入框 + 附件 + WS（Composer.tsx）| 黎（前端 Composer）+ 董（WS）+ **袁 (6/9 部分已真测 — 走 AI 队友→发起私聊→pin happy path 走通, 但 ChatView.onSend 早返回 UI flow 死路 见 [test-report-2026-06-09-comprehensive.html](docs/reports/test-report-2026-06-09-comprehensive.html) §4 Bug 2)** |
| | 群聊（多 Agent + @ + Orchestrator）| ✅ 完整 | S2 群聊 6 条消息流（用户→Coordinator 拆解→Claude/OpenCode/MockBot 并行→合并汇报）| 董（群聊全栈）+ 袁（E2E 验证）|
| | 消息类型（文本/代码/图片/文件/网页预览/Diff/部署卡）| ✅ 完整 | 文本/代码/网页预览/Diff 均 ✅；图片/文件 ✅（Composer + attachments.py 200）；**部署卡 ✅**（plan_ba86c4d0 frontend-p2 + backend-p2 联合落地 `c2d2a59`+`f45a92f`, MessageBubble 部署卡接 peer DeployCardView + 状态色 + 3 路径 test）| 黎（前端）+ 董（后端 P2）+ Mavis owner (P2 委派) |
| | 消息操作（回复/引用/重新生成/复制代码/应用 Diff/展开预览）| ⚠️ 部分 | 复制代码 ✅ 重新生成 ✅ **Pin ⚠️ 端点 401 → 已修 by t1-pin-auth (6/8 overnight)** + **回复/引用 ✅** + **全屏预览 ✅** 代码完整 (3 路径单测) E2E 需真 URL | 黎（前端 MessageBubble）+ 袁（Pin 401 修复 `b97c4fd`/`bd92b2a`/`5371f41`/`2cbfff8`）|
| | 上下文管理（pin 关键消息）| ✅ 完整 | Pin 按钮 + 后端 `/api/messages/{id}/pin` 端点（schema 钉死测试）；**session 校验 ⚠️**（alembic 0012+0013 dual head race 已修 by t1 merge `2843b06`）| 黎（UI）+ 袁（后端 t1-pin-auth 5 路径 12 pytest）+ **袁 (6/9 t7 session.pinned 已真测 — Playwright 3 截图 + live PATCH 200, 详见 §6)** [已真实测试 (AI 模拟)] |
| **2. Orchestrator** | 自动分派/聚合/并行 | ✅ 完整 | Coordinator 拆解 3 任务 + 3 Agent 并行 + 合并汇报（CoordinatorPlan.tsx）| 董 |
| | 失败降级 | ✅ 完整 | plan_ba86c4d0 backend-p2 `f45a92f`（19 文件 +1974 行 + 21/21 pytest 全绿）| Mavis owner (P2 委派) |
| | 代码冲突处理 | ❌ 未做 | 已知缺口 | — |
| **3. 多 Agent 接入** | 适配器层（Claude Code + Codex + OpenCode + Pi）| ✅ 完整 | CLI/SDK 双轨（per ADR-0001）+ 11 个队友含 Codex/OpenCode/Pi | 董（CLI 接入）+ 黎（OpenCode fix）|
| | 用户自建 Agent（对话式创建）| ⚠️ 部分 | CreateAgentModal 存在（E2E 验证 04-modal）| 董（Agent 创建全链路 6 处 bug 修复 + 9 测试）|
| | 联系人列表（头像/名称/能力标签）| ✅ 完整 | AI 队友页 11 个 + 头像 + role 标签（AgentsListPage）| 黎 + **袁 (6/9 Playwright 走 11 article 确认渲染, [已真实测试 (AI 模拟)])** |
| **4. 产物预览与编辑** | 网页 iframe 内联卡片 | ✅ 完整 | `WebPreviewCard.tsx:80` iframe sandbox（集成验证 A 验）| 黎 |
| | 文档渲染 | ✅ 完整 | plan_ba86c4d0 frontend-p0-p1 `d9cd8af`+`d6a1658` 落 DocumentRenderer 3-mode (per frontend-p0-p1 verifier) | Mavis owner (P0 委派) |
| | 【P2】PPT 浏览 | ❌ 未做 | 已知 P2 | — |
| | 展开全屏预览 | ✅ 完整 | plan_ba86c4d0 frontend-p0-p1（Dialog fullscreen 模式）| Mavis owner |
| | 代码编辑器 | ✅ 完整 | plan_ba86c4d0 frontend-p2 `c2d2a59`（MonacoEditor.tsx + Composer 代码模式 + 3 路径 test）| Mavis owner (P2 委派) |
| | 【P2】Diff 视图 | ✅ 完整 | `DiffView.tsx:29-41` 彩色 emerald/rose（集成验证 B 验）| 黎 |
| | 【P2】版本历史 | ❌ 未做 | 已知 P2 | — |
| | 【P2】对话式局部修改（选中代码→描述修改）| ❌ 未做 | 已知 P2 | — |
| **5. 【P2】部署发布** | 聊天发送"部署"指令 → 部署卡 | ✅ 完整 | plan_ba86c4d0 backend-p2 `f45a92f`（Deploy 端点）+ frontend-p2 `c2d2a59`（部署卡前端, peer DeployCardView + 状态色）| Mavis owner (P2 委派) |
| | 预览 URL / 静态站点 / 容器化 / 源码打包 | ⚠️ 部分 | 端点已落, 真实部署流水线未跑 E2E（M5/MVP 节奏）| — |
| **6. 【P2】多端支持** | Web 端（主力）| ✅ 完整 | localhost:5174 vite dev 跑通 | 黎 + **袁 (6/9 vite 9500 跑通 + Playwright 走完 t7 pin happy path, [已真实测试 (AI 模拟)])** |
| | 桌面端 | 📋 计划 | Tauri 2 计划冻结中（`feature/desktop/spec-freeze`, per ADR-0007），**等 4 Q 答稿** (Q5-1 通知 / Q5-2 身份 / Q7-1 版本号 / Q11-1 降级方案) | 黎（proposer, worklog 2026-06-06_讨论-web转桌面app可行性.md）+ 等 董/袁 reply |
| | 移动端 H5 | ✅ 完整 | **6/8 修正**: t3-mobile-h5 `a483424`+`8124e54` 落地 useMediaQuery (React 18 useSyncExternalStore + matchMedia SSR-safe) + AppShell 4 栏 mobile/desktop 分支 + 11 vitest (5 useMediaQuery + 6 AppShell) + 4 截图 (375/768/1280/hamburger) + BDD §6.5.1.1 B-6-P2-M02 5 When/Then | 袁（t3-mobile-h5, M5 overnight）|

**整体覆盖率**: ✅ 完整 15 / ⚠️ 部分 5 / ❌ 未做 5 / 📋 计划 1 / ✅ done by 6/8 t3 1 = **67% → 71%**
(6/8 修正: 之前 22:00 标 ❌ 移动 H5 实际 ✅ by t3 overnight; per [ADR-0018](worklogs/decisions/0018-plan-3eaba0fa-overnight-4track-close.md))

---

## ⚠️ 后端已做 / 前端未做 (per袁2026-06-091:31a inventory + 本轮 grep16 router ×8 client ×7 nav实证)

> **盘点方法**: `ls src/backend/app/api/routers/` (16 router) + `Grep "@router\.(get|post|patch|delete)"` → 后端端点枚举 + `ls src/frontend/src/api/` (8 client) + `Grep "<apiName>Api\.|/api/<path>"` → 前端调用方枚举 + `Read App.tsx + CenterPanel.tsx + NavRail.tsx` → 主导航可路由性
> **结论**: PRD6 大功能"覆盖71%"是按 feature维度打的; **按 endpoint维度**, 后端 ≥57端点 vs 前端8 client 文件 (内含 ~40 函数), **实际调用覆盖率 ≈60%**,缺口集中在 MCP/Deploy/Inbox/Tasks 等后端先做/前端待补的区域
> **谁做的**:建议按端点对 owner协商 — [袁] MCP P3-F3路径 A (前后端同步), [黎] Deploy/Inbox/Tasks UI, [董] Usage router 注册 (TD-11)

| # | 后端端点 (router) | 前端现状 | 影响 (per PRD6 大功能) |接手起点 |
|---|------------------|---------|----------------------|---------|
| **1** | **MCP** (`mcp.py`) 全套10端点: `GET /api/mcp/market`, `/market/templates`, `/market/{id}`, `POST /api/mcp/installations`, `DELETE /installations/{id}`, `POST /api/mcp/bindings`, `DELETE /bindings/{id}`, **`POST /api/mcp/servers` (袁6/8 fde10e4+a2b9ff3)** | ❌ **0 调用** — `api/mcp.ts`10 函数全空, 主导航无 MCP入口, NavRail5 项不含 | **PRD §3 多 Agent接入 + §4产物 (MCP工具调用产物)** 的核心展示区全缺 | 在 NavRail 加 MCP入口 → 新建 `McpMarketPage.tsx` (复用 SkillMarketplacePage模式) → 接 mcpApi.listMarket + install + bind;优先级 P0 (per [ADR-0017](worklogs/decisions/0017-prd-core-feature-25pct-gate-audit.md) MCP25%闸门) |
| **2** | **Tasks任务列表** (`tasks.py`) `GET /api/tasks` (返 mock `{items:[],total:0,note:"M3 实现"}`) | ⚠️ **UI 已写但 mock-driven** — `TasksTabView.tsx` + `CreateTaskModal` + `TaskCard` + `taskStore.ts` 全从 `data/mock`读, 无 `tasksApi`, 不打 `/api/tasks` | **PRD §2 Orchestrator失败降级/冲突处理** 主载体缺 (TaskCard "派发"按钮注释待 M3 Coordinator 接 `POST /api/tasks`) | 在 `api/` 加 `tasks.ts` (list/create/update/delete) +替换 taskStore.ts fetch; 后端骨架需先填 (M3 TODO移除) |
| **3** | **Inbox收件箱** (`inbox.py`) `GET /api/inbox`, `GET /api/inbox/unread-count` (返 `{items:[],unread_count:0,note:"M4 实现"}`) | ⚠️ **UI 是 mock** — `inboxStore.ts`注释"items来自 GET /api/inbox; resolve 对应批准/驳回 POST" 但无实现; `InboxView.tsx`注释"M4 TODO" | **PRD §2 Orchestrator失败降级 + 用户审批流**缺 (S5 inbox3 重 gap per [ADR-0010](worklogs/decisions/0010-integration-verify-downscope-e.md)) | 新建 `api/inbox.ts` +替换 inboxStore mock + InboxView 接审批 modal (post approve/reject); 后端骨架需 M4填 |
| **4** | **CLI PATH扫描刷新** (`cli.py`) `GET /api/cli/scan`, `POST /api/cli/scan/refresh` (`CliScheduler` 每1h 自动扫, scheduler 已落) | ❌ **无手动 trigger按钮** — CreateAgentModal调 `providersApi.scan()` 是间接路径 | PRD §3 "多 Agent接入" UX: 用户装新 CLI 后不能手动重扫,需等1h scheduler | 在 `api/` 加 `cli.ts` (scan + refresh) + 在 Provider卡片加 "刷新扫描"按钮 |
| **5** | **Deploy列表/详情/删除** (`deploy.py`) `POST /api/deploy`, **`GET /api/deploy`** (list), **`GET /api/deploy/{id}`** (detail), `DELETE /api/deploy/{id}` | ❌ **后端3/4端点无 UI** — `DeployCard.tsx` 仅展示内联卡片, 无 list面板 (看不到历史部署), 无删除按钮 | **PRD §5部署发布 P2** 部分项缺:列表 + 删除 (per STATUS §🎯 PRD §5 ⚠️ 部分 "端点已落,真实部署流水线未跑 E2E") | 新建 `api/deploy.ts` (list/get/delete) + 在 settings 加 DeployHistoryPanel; DeployCard 加删除确认 |
| **6** | **Usage 全局** (`usage.py`) `GET /api/usage`, `/global`, `/agents/{id}`, `/sessions/{id}` | ⚠️ **TD-11: `/api/usage`端点未注册 main.py** — `TokenMonitorPanel.tsx` fetch `/api/usage/global` 直接404, pytest158 + vitest106绿但 main.py漏 import | **PRD §3 多 Agent接入** 的成本可视化缺 (用户看不到 token花费) | 单独立30min ticket "register usage router in main.py" (per TD-11), 然后验证 TokenMonitorPanel 不再404 |
| **7** | **Templates sync/source/export** (`templates.py`) `POST /api/templates/sync`, `GET /api/templates/source/status`, `GET /api/templates/{id}/export` | ⚠️ **部分有 UI** — `templateStore.ts` fetch sync/source 已调, 但 export 仅在 `TemplatePreviewPanel` 单卡片触发; **无 "刷新源"按钮** (用户感知不到同步状态) | PRD §1 IM聊天式交互的"模板扩展"半缺 | 在 TemplateManagementTab 加"同步源"按钮 (走 templatesApi.sync) + 显示 source/last_synced |
| **8** | **Skills library高级操作** (`skills.py`) `POST /api/skills/library/create`, `/generate`, `/batch-delete`, `DELETE /library/{name}` | ⚠️ **直接 fetch 无 client wrapper** — `SkillMarketplacePage.tsx` (5 处) + `CreateSkillDialog.tsx` (2 处) + `SkillMdPreview.tsx` + `CustomAgentModal.tsx` 全用 `fetch('/api/skills/...')` |维护性债 (后端改路径需 grep 多处); PRD §3适配器层不受影响 | 新建 `api/skills.ts`包装5端点 +替换4 文件 fetch 调用 |
| **9** | **Agents PATCH** (`agents.py`) `PATCH /api/agents/{id}` (改 name/avatar/role/skills...) | ❌ **`agentsApi.ts` 无 patch fn** — AgentsListPage + AgentDetailDrawer + AgentDetailPage 全是只读; 用户编辑 Agent只能 delete+create | PRD §3 "用户自建 Agent (对话式创建)"改 name/role 无路径 (只能整个删了重建) | `agentsApi.update(id, partial)` 加 → AgentDetailDrawer 加编辑入口 |
| **10** | **Sessions DELETE message** (`sessions.py`) `DELETE /api/messages/{id}` | ❌ **`sessionsApi.ts` 无 delete fn** — MessageBubble注释 "并接 fetch('/api/messages/{id}/regenerate?session_id=...')" 显示只有 pin; 删除消息 UI 无 | PRD §1 IM聊天式交互"消息操作"缺 "删除消息"维度 (per STATUS §🎯 PRD §1 ⚠️ 部分) | `sessionsApi.deleteMessage(id, sessionId)` 加 → MessageBubble 加删除按钮 (私聊) + GroupMessageItem (群聊) |
| **11** | **Memory update 接口** (`memories.py`路由在 `/api/agents/{id}/memories`) `PATCH /api/agents/{id}/memories/{mid}` | ⚠️ **`memoriesApi.update` 已包装但 MemoryPanel 是否调用待复核** (本轮 grep0命中 `.update(`) | PRD §3 多 Agent接入的"长期记忆" 编辑路径半缺 (用户可创建但不能修改内容) | MemoryPanel 加编辑 modal 接 memoriesApi.update |
| **12** | **Provider ping UI反馈** (`providers.py`) `POST /api/providers/ping` | ⚠️ **`providersApi.ts` 无 ping fn** — `CreateAgentModal.tsx` line627+662 直接 fetch 但**结果未 toast化** (成功/失败用户看不到) | PRD §3 创建 Agent流程 UX: 用户填完 form 点 "测试连接" 后无明确反馈 | CreateAgentModal 把 ping 返回 toast化 + `providersApi.ping(system)` 加包装 |
| **13** | **Proxy debug面板** (`proxy.py`) `/proxy/agents/{id}/{path:path}` (通配转发 CLI →第三方) | ❌ **无 debug/diagnose UI** — proxy 是 CLI链路基础设施, 用户不直接调用 | PRD §3 多 Agent接入的"故障排查"缺 (用户看不到 proxy 是否通) | (低优先级) settings 加 ProxyStatusPanel 显示最近 N 次代理成功/失败 |

**整体盘点结论**:
- **P0必做 (直接影响 demo视频 +答辩)**: #1 MCP UI (10端点全缺, PRD §3核心), #2 Tasks (UI mock, M3 TODO移除), #5 Deploy list/delete (PRD §5 P2)
- **P1重要 (影响 UX完整性)**: #3 Inbox (M4 TODO), #6 Usage 注册 main.py (TD-1130min), #9 Agents PATCH, #10 Message DELETE
- **P2维护性债 (不改不崩, 但留 grep负担)**: #4 CLI refresh button, #7 Templates sync按钮, #8 Skills client wrapper, #11 Memory update, #12 Provider ping toast, #13 Proxy debug
- **覆盖率**: 后端端点57 → 前端实际调用 ~35, **真覆盖率 ≈60%** (per袁1:28a inventory: "Frontend Views Gap: Only2 Tabs (Skills, Settings) vs57 Backend Endpoint Groups")

---

## ⏭️ 进行中事项 (按 owner 分组)

### [黎] 5-6 月 持续工作

- **Template v4 (192 模板+favorites)** + **CLI streaming 全线** (5 种流式事件 UI+折叠组) + **图标居中** + **弹窗关闭修复** + **bypassPermissions** + **scanner 精简** + **网页侧栏预览** + **删除确认弹窗** + **会话最近消息** — 全部 ✅ 落 main
- **桌面 App 计划冻结中** (分支 `feature/desktop/spec-freeze`, docs-only, 未 push):
  - 决策: Tauri 2 + M2 瘦客户端 (连用户自部署 backend) + GitHub Releases 自下载, 不进任何商店
  - 产出: [ADR-0007](worklogs/decisions/0007-tauri-desktop-pivot.md) + 规格草案 (`docs/specs/06-desktop-app_桌面App规格.md`)
  - 工作量: 5-7 周到首个公开 v0.1.0
  - ⚠️ **阻塞: PR-01 2 人 Review**, 需 董/袁 之一答完规格 §十二 4 Q (Q5-1 通知 / Q5-2 身份 / Q7-1 版本号 / Q11-1 降级方案)
  - 接手起点: worklog `worklogs/黎/2026-06-06_讨论-web转桌面app可行性.md` 「给下一位的交接」段
  - **状态 [6/8 22:00 黎 答稿中]** (per 黎 STATUS 表 + worklog `2026-06-08_桌面specs-4q-answered.md`)

### [董] 协调者+任务编排 + 多 Agent 接入 + 记忆

- **群聊全栈实现** + **CLI 多模型代理** + **ADR-02 长驻 CLI** + **前端群聊** + **记忆系统 B 方向设计** + **B1 后端实现** + **B2 详细设计** + **Agent 创建全链路 6 处 bug 修复 + 9 测试** + **MCP save_memory 端到端打通** + **前端记忆面板** + **记忆分支合并 main** — 全部 ✅
- **MCP F1 + F2 已全部并入 main** (F1 tag `mcp-f1`, F2 commit `002f3fb`):
  - **F1 市场+安装**: market+install 5 端点 + McpInstaller 端口 + LocalMcpInstaller 结构校验 (transport 必填项, 422 拦截非法配置) 替代骨架 ready + 19 单测绿；[ADR-0004](worklogs/decisions/0004-mcp-f1-landing-and-installer-seam.md) + [收束报告-F1](docs/reports/收束报告-MCP-F1.md) 双线签核闭合
  - **F2 接入**: `POST/DELETE /api/mcp/bindings` + `McpBindingService`（bind/unbind）+ `agent_mcp_bindings` 改 status=active **部分唯一**（alembic 0010）→ 解绑后可 rebind
  - **attach = 请求携带** ([ADR-0005](worklogs/decisions/0005-mcp-attach-request-carried.md)): `AgentRequest.mcp_servers` + `build_request_mcp_servers` + `ContextBuilder` 可选 `mcp_resolver` 注入（私聊/群聊）
  - **统一注入原则 + opencode 拉回本期** ([ADR-0006](worklogs/decisions/0006-mcp-injection-per-runtime-isolated-channel.md) / RT-MCP): `OPENCODE_CONFIG=<tmp>` 逐进程隔离通道（实测注入成功、零串号），落码 `_entry_to_opencode`+`_build_opencode_mcp`+`_write_opencode_config`，记忆+绑定 servers 自包含临时配置；**opencode 连接级 E2E 冒烟通过**（`opencode mcp list` 显示 `✓ everything connected`，真拉起 stdio MCP server 完成 initialize/tools 握手）
  - **pi_agent deferred**（本机无 pi 二进制可验证, `_build_cmd` 留 NB-02 seam 注释, 解除前置门 RT-MCP §3.3）
  - **F2 收束-2 闭合（2026-06-04）**: 四阶段双线签核 ([收束报告-F2](docs/reports/收束报告-MCP-F2.md))；MCP 专项 34/34 绿
  - **路径分离** (`90195f6`): 董记忆 MCP 协议端 mount 移到 `/api/mcp-memory`, `/api/mcp/*` 归市场 REST（§2.6 契约不变）；`settings.mcp_memory_url` 示例同步为 `.../api/mcp-memory/sse`
  - **P2 后续（移交 P3/P4）**: 完整 chat→tool_call（需 LLM key, P4 带 key 验）· 工具级 tool_subset 过滤（P4）· pi_agent 待上游 MCP 支持

### [袁] MCP P3/P4 + 6/8 overnight 4-track + Pin 401 fix

- **MCP P3 F3 创建** (6/6-6/8, 34h, 袁):
  - stdio/sse 提交 + 模板 + dry-run 验证（单 Docker + compose 限额, E-03 简化版）
  - 起点: `docs/plan/后续升级计划/MCP接入/06-详细设计/FS-MCP-V1.0-20260602.md` §1 + `docs/specs/04-commands_命令接口.md` §2.6/§三
  - **状态 [6/8 22:00]**: t3 MCP P3 F3 路径 A 全完 (`fde10e4` feat(backend) + `a2b9ff3` test(backend); McpServerService + POST `/api/mcp/servers` + 2 schema + 4 测; alembic 0006 + entity + enums 全部复用, 0 新下层; 409→422 降级留 P4+ AP-02 envelope). **本地 2 commit, 网络挂未 push**. 路径 A owner override 已闭环, 23:03 SLA 已提前 1h
  - **状态 [6/9 00:45]**: **mcp.py 重复路由 bug 真发现 + 修通** (line 184-207 复制 line 155-178, FastAPI AssertionError → 500; 删 line 181-208 整段, 207 行 → 178 行). **live 4 路径全绿** [已真实测试 (AI 模拟)]: happy 201 + slug 422 + transport 422 (Pydantic 拦) + slug 冲突 422. 本地 mcp.py fix uncommitted, 等 user push
  - **关联 worklog**: `worklogs/袁/2026-06-08_mcp-p3-f3-spec-freeze-reviewer-pending.md` + `worklogs/袁/2026-06-09_phase3-verify-and-3-bugs.md` (待补)
- **MCP P4 F5 展示** (待启动, 6/12-6/15, 33h, 袁):
  - 工具调用内联卡片 + WebSocket 事件. **收束-4 闸门**: 收束 4 + ADR 0007
  - 关键依赖: 完整 chat→tool_call 链路（带 LLM key E2E 验）
- **6/8 overnight plan_3eaba0fa 4-track 收束** (per [ADR-0018](worklogs/decisions/0018-plan-3eaba0fa-overnight-4track-close.md)):

  | Track | 标题 | 状态 | Commit | Worklog |
  |-------|------|------|--------|---------|
  | t1 | M5 5.1 Pin API 401 修复 + alembic 0014 merge | ✅ done | `b97c4fd`/`bd92b2a`/`5371f41`/`2cbfff8` → owner merge `2843b06` | `worklogs/袁/2026-06-08_t5-f9-s2-pin-copy-owner-takeover.md` |
  | t2 | M5 5.2 Token 监控 E2E 收尾 | ✅ done | `46065aa` + `ebf678a` + `7914a59` + `60d4d69` → owner merge `fbfd44a` | `worklogs/袁/2026-06-07_t2-token-monitor-e2e.md` |
  | t2 | M5 5.2 CLI PATH 扫描 scheduler 集成 | ✅ done | `b63d0da` + `66e2c52` + `6d1fb0a` + `ddd58fc` → owner merge `1714f5d` + cherry-pick `9601313` | `worklogs/袁/2026-06-07_t2-cli-scheduler.md` |
  | t3 | M5 5.3 移动 H5 响应式实施 | ✅ done | `a483424` + `8124e54` → owner merge `015cf8e` | `worklogs/袁/2026-06-08_t5-f9-s2-pin-copy-owner-takeover.md` |
  | t4 | M5 5.4 CI gate (4 jobs) | ✅ done | `0570a43` + `6cd69dd` → owner merge `9e613b8` | (t4 worker worklog) |
  | t4 | MCP P3 F3 spec 冻结 (M5 5.4 扩展) | ⚠️ PEND | `701f01b` → owner merge `60ff903` | `worklogs/袁/2026-06-08_mcp-p3-f3-spec-freeze-reviewer-pending.md` |

  **关键工程教训** (与 [ADR-0014](worklogs/decisions/0014-mavis-team-plan-ba86c4d0-strong-close.md) / [0015](worklogs/decisions/0015-day2-pipeline-claude-team-mode.md) 形成闭环):
  1. 每 track 独立 worker worktree: 本 plan 显式违反, 5 worker 共享 working tree 触发 gap #8 (5+ 次 `git checkout <other-branch>` 把 t4-mcp-spec 写好的 spec + worklog 改动 revert 掉, 需用 git plumbing 在临时 `GIT_INDEX_FILE` 创建 commit 才保住). **下个 plan 强制 `git worktree add` 隔离**
  2. vitest 106/108 + pytest 157 全绿（含 2 deferred pi_agent E2E, 本机无 binary 已知）
  3. CI 4 jobs 3m27s 跑完: ruff + mypy + tsc + eslint + vitest + playwright（沿用 `eea1d0e` `continue-on-error` baseline），GitHub Actions run 27096545029 4/4 success
  4. M5 范围 67% 覆盖率（per [ADR-0017](worklogs/decisions/0017-prd-core-feature-25pct-gate-audit.md) 对账 → 71% with t3 mobile）

### [Mavis owner] 凌晨冲刺 + 强收 + E2E 视觉验证 + 视频产出

- **2026-06-07 凌晨冲刺** (plan_bcf9945c 收束, 06/07 01:20-05:50, Mavis owner):
  - 决策: [0010-integration-verify-downscope-e](worklogs/decisions/0010-integration-verify-downscope-e.md) (E 视觉 downscope 到 API+code, Inbox M4 TODO) + [0011-plan-bcf9945c-complete](worklogs/decisions/0011-plan-bcf9945c-complete.md) (plan_complete=true)
  - 5 task 全部 deliverable 落档 + verifier 复核 PASS:
    1. **P0-4 + P0-5 合并** — `commit 32485a1` on `feature/frontend/pin-ui` (MessageBubble Pin 按钮 + 复制/重新生成 + schema-钉死 test) — 黎
    2. **集成验证 5/6 PASS** (E 视觉 downscope) — `docs/deliverables/integration-verify-report.md` + 4 张真集成截图 (S2 group + AI 列表 fullpage/viewport) + 6 E2E: A iframe-sandbox ✓ / B colored-diff ✓ / C Pin/Unpin ✓ / D 复制代码 ✓ / E S5 inbox FAIL (M4 TODO) / F 1KB upload ✓ — Mavis owner
    3. **video-record** — `docs/deliverables/video/script.md` 13KB 6 章节 + `raw-recording.mp4` 14.5MB 200s 1920x1080 + 3 抽帧 PNG — Mavis owner
    4. **video-produce** — `AgentHub-Demo-Video.mp4` 17.7MB 200s 1920x1080 h264+aac+mov_text 字幕 zho + 7 TTS wav + 2 AI cover + 27 subtitle — Mavis owner
    5. **docs-feishu** (v1 override_accept + v2 attempt 2 PASS) — `docs/deliverables/AI协作开发记录.md` 12.1KB CJK 3214 6 段 a-f + PRD 增量更新 (commit `602026f` + `82b265a`) — Mavis owner
  - **P0 缺口状态变化** (roadmap §8 必修 P0 段同步):
    - P0-1 网页预览 iframe — ✅ (黎, `WebPreviewCard.tsx:80` iframe sandbox)
    - P0-2 Diff 视图 — ✅ (黎, `DiffView.tsx:29-41` 彩色 emerald/rose)
    - P0-3 文件附件上传 — ✅ (董 + 黎, `attachments.py:99-158` 10MiB + 7 MIME)
    - P0-4 Pin 消息 UI — ✅ (黎, `MessageBubble.tsx:155-188`) → 6/8 袁 t1 修 401 端点
    - P0-5 复制代码/重新生成 — ✅ (黎, `MessageBubble.tsx:112-144`)
    - P0-6 端到端 Demo 数据集 + 录制脚本 — ✅ (Mavis owner, seed_demo_data.py 11 agents/4 sessions/19 messages + video script 6 章节)
- **2026-06-07 12:00 Mavis E2E 视觉验证** (用户疑虑"功能都没实现"触发, per [ADR-0016](worklogs/decisions/0016-playwright-mcp-replace-cu-for-e2e-visual.md)):
  - 方法: 纯 cu (Computer Use) 在 agentHub 上失灵 (坐标精度 + Chinese encoding 被 PS 5.1 破坏) → 切 **playwright MCP** 走 DOM 精准 (getByRole + ref + evaluate)
  - 11 章节实测: F1 ⚠️ S1 私聊建议按钮 (session 创但建议不响应) / F2 ✅ 群组消息流 / F3 ✅ AI 队友列表 11 个 / F4 ✅ 任务看板 7 任务 4 列 / F5 ✅ 主题切换 / F6 ✅ 创建群组 modal / F7 ✅ 设置 / F8 ✅ 私聊空状态 / F9 ✅ Pin/复制代码 (12:57 by 079cdca 修完) / Skill ✅ 技能市场 12 个
  - 核心结论: 「功能都没实现」**是误判**。AgentHub 核心 backend 真在工作。Console **0 错 0 警**
- **2026-06-07 19:15 Mavis PRD 核心功能 vs 现状对账** (plan_ba86c4d0 强收后重对账, per [ADR-0017](worklogs/decisions/0017-prd-core-feature-25pct-gate-audit.md)):
  - 评估依据: plan_ba86c4d0 7 impl commit 落 main (HEAD `eea1d0e`) + 凌晨冲刺 4 commit + E2E 实测 + 代码阅读
  - 详见上方 [PRD 6 大核心功能 vs 现状对账](#-prd-6-大核心功能-vs-现状-对账)
- **2026-06-07 19:05 M5 5.4/5.5 plan_ba86c4d0 强收** (per [ADR-0014](worklogs/decisions/0014-mavis-team-plan-ba86c4d0-strong-close.md)):
  - 9 task 收束: 6/9 done (spec/backend-p0-p2/frontend-p0-p2/docs) + 3/9 plan-exit owner override_accept (ci/test-e2e/final-verify)
  - 实物全部落 main (HEAD `eea1d0e`, 7 impl + 4 ci + 1 test fixture = 20 commit 累计)
  - ci task: producer 18:25 self-close 报 done (7 commit + Actions run 27089840081 4/4 绿), engine 30min cap 18:54:59 killed 是硬超时
  - 3 plan-exit override_accept: (a) ci 实物在 main + CI 4/4 绿; (b) test-e2e = E2E 价值已被 168 backend pytest + 148 frontend vitest + 6 playwright 路径覆盖, 完整 6 路径重跑 2-3h 算力 + 价值边际; (c) final-verify = 5 维度对齐 evidence 在 deliverable.md + ADR-0012/0013 + STATUS
  - 3 known gap 接受 (后续由 6/8 overnight 修完): P0-4 Pin session 校验 / P1-2 Token 监控 / P1-3 CLI 扫描 主 feature **未落 main**, 留 M5/M6 手动补
  - **plan.status="failed" 终态保留** (cycle 6 evaluating stall 42+ min 是真实失败记录, 作为 audit 教训), CLI `mavis team plan decision plan_complete=true` 强收无效 (pitfalls §13)
  - 收束报告: [ADR-0014](worklogs/decisions/0014-mavis-team-plan-ba86c4d0-strong-close.md) + mavis-team-pitfalls §13
- **2026-06-08 22:00 19:50 deploy.py:81 FastAPI Annotated + Query(default) 冲突** (实测发现 + 已修): `Annotated[bool, Query(default=False)] = False` 触发 AssertionError, 整个 app 启动失败. 改 `Annotated[bool, Query()] = False`, 157 pytest + 60 routes import OK. pytest 实际 157 pass / 2 deferred (pi_agent E2E 本机无 binary 已知) — Mavis owner

---

## 🚧 阻塞项

- 🟢 袁 t3 MCP F3 网络挂 (23:03 SLA 路径 A 已闭环, **等 push**)
- 🟢 黎 桌面 specs 4 Q 答稿 (Q5-1 通知 / Q5-2 身份 / Q7-1 版本号 / Q11-1 降级方案, **等 董/袁 reply**, per ADR-0007)
- 🟢 董 yii.d 离线 (per [ADR-0018](worklogs/decisions/0018-plan-3eaba0fa-overnight-4track-close.md) 6/8 reviewer SLA 至 23:03, t4-mcp-spec 2/2 Approve pending)
- 🟢 视频 v4 录屏 DISPLAY1 wallpaper 残留 (v5 Win32 SetWindowPos + ffmpeg crash 失败; 透明声明, **建议 v6 重做** per ADR-0016 真实工作流)

---

## 🧾 技术债 (active only, 已修 13 条见 [ADR-0017](worklogs/decisions/0017-prd-core-feature-25pct-gate-audit.md) §M5-M6)

| # | 问题 | 发现 | 优先级 | 谁发现 | 预计修复 |
|---|------|------|--------|-------|---------|
| TD-01 | 既有套件测试隔离 flaky (`test_context_builder` 模块级 fakeredis 单例 / `test_selector` LLM 环境敏感) | MCP F1 收束-1 | 🟡 中 | 袁 | 独立工单（非 MCP 引入）|
| TD-02 | NB-02 defer: AP-02 错误信封统一 / AP-05 URL 版本 / workspaces·users 实体+FK / 全局 JWT 鉴权 | 二次对账 | 🟢 低 | 董 | 平台化阶段 |
| TD-03 | 安装为结构校验骨架 (无真实可达性/进程探针) — P3/P4 真实探针 seam 已留 | MCP F1 → F2 收束 | 🟢 低 | 董 | P3/P4 真实探针 |
| TD-04 | MCP 注入 pi_agent deferred (本机无 pi 二进制可验证) | P2 运行时审计 | 🟢 低 | 董 | pi_agent 待上游 MCP 支持（解除门 RT-MCP §3.3）|
| TD-05 | E 视觉 S5 inbox 3 重 gap (backend TODO / frontend mock / UI 无 nav) | 凌晨冲刺 | 🟡 中 | Mavis owner | M4 TODO |
| TD-06 | S3 私聊 UI 不可达 (ChatView mock-driven, LeftPanel 只 user-created) | 凌晨冲刺 | 🟡 中 | 黎 | 已 downscope |
| TD-07 | S1 私聊 3 建议按钮 click 不响应 (前端 mock 未接好, 需改 ChatView) | 6/7 12:00 E2E | 🟡 中 | Mavis owner | M4 TODO |
| TD-08 | 群组管理列表页的卡片 💬 icon 误导用户 (实际"进入群聊"在卡片右下角按钮) | 6/7 12:00 E2E | 🟢 低 | Mavis owner | UX 修复 |
| TD-09 | pytest 1 flaky selector test (`test_llm_failure_degrades_to_done` isolated PASS / full suite FAIL — T-04 违反) | 6/8 t1+t2 verifier 复跑 | 🟡 中 | 袁 | 独立工单（非本 plan 引入）|
| TD-10 | 跨 worker shared worktree 覆盖 (gap #8: 5+ 次 `git checkout` 把 t4-mcp-spec 改动 revert 掉, 需用 git plumbing 在临时 `GIT_INDEX_FILE` 创建 commit) | 6/8 t4-mcp-spec retry | 🟢 低 | 袁 | future plan 强制每 track worker 用独立 `git worktree add ../<track>-worktree feature/<branch>` |
| TD-11 | /api/usage HTTP 端点未注册到 main.py (pre-existing infra gap, T2 不在 scope 内) | 6/8 t2 | 🟡 中 | 袁 | 建议单独立 30min ticket「register usage router in main.py」|
| TD-12 | Node.js 20 deprecation 警告 (2026-06-16 强制 Node 24) | 6/8 t4-ci-gate | 🟢 低 | 袁 | 后续 bump @v4→@v5 |
| TD-13 | M5 5.1 Pin API 401 fix 唯一缺口: e2e-pin-auth-2026-06-08.png 截图未生成 (worktree env DATABASE_URL 传递丢 → uvicorn :18010 启动 500; HTTP-level 测试已端到端覆盖) | 6/8 t1 | 🟢 低 | 袁 | **今天 09:00 兜底**: `docker compose build backend` (15-20min) 或用 `.env` 自动加载 `uvicorn :18010 --reload` |

---

## 📚 关键 ADR/worklog 索引 (本次整合新增 3 份 ADR)

### ADR 索引 (worklogs/decisions/ 18 份)

| # | 标题 | 状态 | 日期 | 谁做的 |
|---|------|------|------|-------|
| [0001](worklogs/decisions/0001-cli-first-pivot.md) | CLI 优先双轨架构 | Accepted | — | — |
| [0002](worklogs/decisions/0002-phase1-long-running-cli.md) | 长驻 CLI | Accepted | — | — |
| [0003](worklogs/decisions/0003-mcp-url-prefix-and-ap05-deferral.md) | MCP URL 前缀 + AP-05 暂缓 | Accepted | — | — |
| [0004](worklogs/decisions/0004-mcp-f1-landing-and-installer-seam.md) | MCP F1 落地 + installer seam | Accepted | — | 董 |
| [0005](worklogs/decisions/0005-mcp-attach-request-carried.md) | MCP attach 请求携带 | Accepted | — | 董 |
| [0006](worklogs/decisions/0006-mcp-injection-per-runtime-isolated-channel.md) | MCP 注入逐进程隔离通道 + opencode 拉回 | Accepted | — | 董 |
| [0007](worklogs/decisions/0007-tauri-desktop-pivot.md) | Tauri 桌面 pivot | Accepted | — | 黎 |
| [0008](worklogs/decisions/0008-self-governance-authorization.md) | 自主决策授权 | Accepted | — | — |
| [0009](worklogs/decisions/0009-p2-handoff-cron.md) | P2 交接 cron | Accepted | — | — |
| [0010](worklogs/decisions/0010-integration-verify-downscope-e.md) | 集成验证 E 视觉 downscope | Accepted | 2026-06-07 | Mavis owner |
| [0011](worklogs/decisions/0011-plan-bcf9945c-complete.md) | plan_bcf9945c 收束 | Accepted | 2026-06-07 | Mavis owner |
| [0012](worklogs/decisions/0012-bdd-spec-comprehensive-precipitation.md) | BDD spec 全面沉淀 | Accepted | 2026-06-07 | Mavis owner |
| [0013](worklogs/decisions/0013-mavis-team-delegation-p0-p1-p2.md) | mavis-team 委派 P0-P1-P2 | Accepted | 2026-06-07 | Mavis owner |
| [0014](worklogs/decisions/0014-mavis-team-plan-ba86c4d0-strong-close.md) | plan_ba86c4d0 强收 (owner override) | Accepted | 2026-06-07 | Mavis owner |
| [0015](worklogs/decisions/0015-day2-pipeline-claude-team-mode.md) | Day-2 流水线从 mavis plan engine 迁 Claude Code team mode | Accepted | 2026-06-08 | 袁 |
| **[0016](worklogs/decisions/0016-playwright-mcp-replace-cu-for-e2e-visual.md)** | **E2E 视觉验证工具从 Computer Use 切换到 Playwright MCP** | **Accepted** | **2026-06-07** | **袁** |
| **[0017](worklogs/decisions/0017-prd-core-feature-25pct-gate-audit.md)** | **M5 范围 PRD 核心功能 25% 闸门对账 + M5/M6 缺口计划** | **Accepted** | **2026-06-07** | **袁** |
| **[0018](worklogs/decisions/0018-plan-3eaba0fa-overnight-4track-close.md)** | **plan_3eaba0fa overnight 4-track 收束 (M5 5.1-5.4 全完)** | **Accepted** | **2026-06-08** | **袁** |

### 关键 worklog 索引 (按 owner)

**袁 (worklogs/袁/)** — 6/3-6/8 期间
- `2026-06-03_MCP-P1核心链路+二次对账.md` — MCP P1 收束
- `2026-06-03_MCP-P2-binding-attach.md` — MCP P2 binding + attach
- `2026-06-04_MCP-opencode注入落码.md` — opencode 注入落码
- `2026-06-07_t2-cli-scheduler.md` — M5 CLI scheduler 集成
- `2026-06-07_t2-token-monitor-e2e.md` — M5 Token 监控 E2E
- `2026-06-08_mcp-p3-f3-spec-freeze-reviewer-pending.md` — MCP P3 F3 24h SLA
- `2026-06-08_t5-f9-s2-pin-copy-owner-takeover.md` — M5 Pin/Copy 兜底 + 移动 H5
- (older 略, see [worklogs/袁/](worklogs/袁/) 全清单)

**董 (worklogs/董/)** — 5-6 月
- `2026-05-22_claude-adapter-impl.md` — Claude 适配器落地
- `2026-05-23_cli-multi-model-proxy.md` — CLI 多模型代理
- `2026-05-25_group-creation-fullstack.md` — 群聊全栈
- `2026-06-07_step-tools-implementation-plan.md` — Step Tools 实施
- (older 略)

**黎 (worklogs/黎/)** — 5-6 月
- `2026-05-22_init-ai-collab-system.md` — 协作系统初始化
- `2026-05-22_m2-chat-ui-crud.md` — M2 聊天 UI
- `2026-05-25_markdown-rendering.md` — Markdown 渲染
- `2026-05-28_pi-agent-integration.md` — Pi Agent 集成
- `2026-05-31_opencode-fix-and-docs-infra.md` — OpenCode 修复 + 文档基础设施
- `2026-06-06_讨论-web转桌面app可行性.md` — 桌面 App 可行性讨论
- `2026-06-08_template-v4-restructure.md` — Template v4 重构
- `2026-06-08_桌面specs-4q-answered.md` — 桌面 specs 4 Q 答稿中

---

## Git ↔ 目录映射

> `scripts/check_worklog.py` 用此表判断「你是谁」, 从而检查对应目录的日志。

| Git用户名 | 人 | 日志目录 |
|-----------|---|---------|
| oldmanpushbike | 黎 | `worklogs/黎/` `docs/explore/黎/` |
| yii.d | 董 | `worklogs/董/` `docs/explore/董/` |
| xiangbianpangde | 袁 | `worklogs/袁/` `docs/explore/袁/` |

---

## 图例

- ⚠️ 阻塞中（写明等谁/等什么）
- 🔀 涉及跨域接口，需协调
- ✅ 完成
- 🟢 待 push / 待 reply（不算阻塞，但有 SLA）
- 🆕 新发现（与上一版本相比）
- **[owner]** 段首标签 = 谁主要做这件事（Mavis owner = 跨人编排/收束）
