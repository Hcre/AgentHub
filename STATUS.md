# 当前状态

> **最近更新: 2026-06-10 17:00**（袁, 分支 main）。完整变更历史见下方「更新日志」。
> **本会话 14 commit 已 rebase 到 origin/main（含队友 8 新提交）之上并 push（`6e1095c..bda3e4e`）**；功能完整度 76%→**89%**（绿测真相 + 私聊死路 + PPT + 版本历史 + 对话式代码修改 + FSM/DAG 派发 + 对话式创建 Agent）。下方各条目里 "未 push / 待 push" 均已作废（已全部 push）。
> - 数据源: `docs/plan/背景.md` (PRD +考察要点 +交付物) + git `200aba4:STATUS.md` (旧198 行) +3 新 ADR (0016/0017/0018) + worklogs/{袁,董,黎}/ + **本轮 grep16 router ×8 client ×7 nav实证**
> - 规则: 每次 push 或开始/结束任务时, 更新你自己那一行
> - 强约束: pre-push markdownlint-cli2 (D-13) — MD024/036/041 严, MD013 关 (per 2026-06-08 决策"不要瘦身")
> - 谁做的: 每个事件段首加 `[owner]` 标签, 进度表 row 直接 = 该人本周完成清单

---

## 🗒️ 更新日志 (newest first)

- **2026-06-10 16:45 — 对话式创建 Agent 落地（⚠️→✅）** (袁, 分支 main)：补 PRD §3「用户自建 Agent 对话式创建」。后端 `AgentDraftService`（自然语言→协调者 LLM(默认 DeepSeek 非 Claude)→`planner.extract_json` 抽 name/role/avatar/system_prompt/tags）+ `POST /api/agents/draft-from-chat`（422 解析失败）+ 5 pytest（fake LLM）。前端 `ConversationalAgentCreate` 模态（描述→生成草稿→可改预览→复用 POST /api/agents 创建）+ AgentsListPage「✨ 对话式创建」入口 + 4 vitest。live 真 DeepSeek E2E：「擅长数据库索引优化」→草稿{name:索引优化专家, role, system_prompt, 5 标签}，0 console 错。功能完整度 87%→**89%**（剩 ❌ = 代码冲突处理；⚠️ = 消息操作 E2E + 部署真实流水线；📋 = 桌面端）。未 push
- **2026-06-10 16:10 — 任务编排 FSM/DAG 派发落地（看板→真派发，M3+）** (袁, 分支 main)：补 PRD §2 编排深水区。**事件溯源 (AR-05)**：`TaskEvent` 实体 + `TaskEventRepository` + `task_events` append-only 落库 + Orchestrator 新增可选 `event_sink`（默认 None，356 测试零回归）。**派发**：`TaskService.dispatch` 状态机（pending→running→completed/failed）+ 事件记录 + `EngineTaskDispatcher`（看板 Task → `build_default_orchestrator`+`CoordinatorRun` 后台真跑，独立 session 持久化，复用 chat 同款引擎）+ `POST /api/tasks/{id}/dispatch` + `GET /api/tasks/{id}/events`。**前端**：`tasksApi.dispatch/events` + `taskStore.dispatchTask` + TaskCard「▶ 派发执行」按钮。**验证**：5 pytest（service 状态机/事件序/防重/append-only）+ 4 vitest（按钮）+ live（dispatch 无会话→优雅 failed + 3 事件 append；UI 按钮→endpoint→卡片移列，0 console 错）。诚实标注：真多 Agent run 复用 chat 引擎，未 live 触发（避 LLM/Claude billing）。4 commit，未 push
- **2026-06-10 13:30 — 产物预览 P2 三项补全（PPT / 版本历史 / 对话式局部修改）** (袁, 分支 main)：PRD §4 三个 ❌ 全部 ❌→✅。① **PPT 浏览** — `GET /api/fs/pptx-slides`（python-pptx）+ `SlideView`（4 pytest + 3 vitest + live 2 页翻页）。② **版本历史** — `file-history`/`file-at-rev`(含 diff)/`file-write` 3 端点 + `versions` 预览模式 + `VersionHistoryPanel`（6 pytest + live STATUS.md 50 commit 时间线 + 真 diff）。③ **对话式局部修改** — CodeView 选区→浮层→结构化 prompt→`agent-edit-request`→ChatView WS（11 vitest + live 选区→「第 4 行」→正确 prompt dispatch）。3 commit（`<pptx>`+`<versions>`+`<convedit>`）+ 3 截图，**未 push**。功能完整度 76%→**87%**（唯一剩 ❌ = 代码冲突处理）
- **2026-06-10 12:35 — 测试可信度修复 + 私聊死路闭环** (袁, 分支 main)：① **恢复绿测真相** — baseline 实测 12 后端 + 4 前端用例失败（与"全绿"声明矛盾），全是断言已被 v4 删除行为的陈旧测试：pin 鉴权放宽后的 owner/anonymous 测试、v4 R5 移到 reactive_router 的机械停词反射测试、pi_agent 构造签名漂移、pin inline-error 已删、WebPreviewCard 全屏 Dialog 改侧栏 preview tab。全部对齐已发布行为，**后端 346 passed/3 skipped、前端 116 passed**（commit `2135d3b`）。② **私聊 1v1 死路修复 (TD-06/07)** — `chatStore.hydrateFromSessions` 回灌后端 private session（幂等 + 写 sessionIds 续聊）+ LeftPanel mount 拉取 + 空态「发起私聊」CTA；Playwright 实测 **37/37 回灌会话均带后端 sessionId（全部可续聊）**、0 console 错误、5 vitest（commit `e0a8494`，截图 `p0-private-hydration-2026-06-10.png`）。两 commit 本地 ahead，**未 push**（per [[no-push-without-ask]]）
- **2026-06-10 07:32 — 会话归档（archive）落地** (袁, 分支 feature/chat/conversation-archive)：补完 PRD §1「对话列表」最后缺口（归档）。Conversation.archived 字段 + chatStore.setConversationArchived + LeftPanel 主列表过滤归档项 + 新增「已归档 (N)」可折叠分区 + 归档/取消归档 hover 按钮（含归档当前会话自动切走）；tsc+eslint 绿 + 3 vitest（归档/取消归档/不影响他项）+ 既有 pin 12 测试无回归 + Playwright 真实往返截图 2 张（`conv-archive-01/02`）。覆盖率 67%→71%→74%→**76%**（对话列表 ⚠️→✅）
- **2026-06-10 00:45 — pin 三层修复闭环** (袁, 分支 main)：群组 pin UI 缺失 + 消息 pin 401 永久显示 + ~~端点强制 JWT~~ → 实为**移除** pin 鉴权（前端无登录流程，强制 JWT 让功能不可用；只保留 session 归属校验）— 10 文件 + 6 截图；~~pytest 9/9~~ **(6/10 修正：该声明失真——owner/anonymous 两测当时仍断言被移除的严格行为，实际 fail；已于 6/10 12:35 对齐放宽后契约，见顶部条目)** + live curl + Playwright click + API verify `pinned=True`；commit `11b4c6c` 已 push origin/main；详见 [worklog](worklogs/袁/2026-06-10_pin-three-layer-fix.md)
- **2026-06-09 18:30 — pytest 现状修正** (袁, feature/frontend/preview-tabs)：修 14 个 v4 R2 后未同步的陈旧测试 + 删 2 孤儿测试模块 + 跳 1 v3 时代 AT_ROUTING 静默断言 + 修 1 真生产 bug `_RecordingSink` 签名 + 删 1 死源 coordinator_orchestrator.py；实测 356 pytest 全绿 / 2 skipped，替代 6/8 起的失真"332 无回归"叙事；详见 TD-14
- **2026-06-09 16:30 — #2 Tasks + #3 Inbox 全栈持久化 CRUD 落地** (袁, feature/frontend/preview-tabs)：两项后端 mock 骨架→真 service+表；前端弃 mock 接真 API；13 项缺口全闭环；alembic 0020；9 pytest + ~~332 无回归~~ (6/9 18:30 修正) + Playwright 4 截图
- **2026-06-09 07:30 — 后端已完成但前端缺失功能点补全** (袁, 同分支)：#9 编辑 Agent + #10 删除消息 + #12 ping 延迟 + #7 Templates 同步复核 + #4 CLI 重扫 + #8 Skills wrapper；此类缺口清零，余 #2/#3 后端为 mock 骨架
- **2026-06-09 02:40 — 预览面板 4 tab 真实 UI 落地** (袁, feature/frontend/preview-tabs)：Diff + Deploy 新建，Files/Webpage 验证；后端 fs/git-diff 端点新增；Playwright 7 截图
- **2026-06-09 01:40 — 后端 ↔ 前端缺口盘点** (per 袁 1:28a~1:31a inventory + 本轮 grep 复核)
- **2026-06-09 01:40 — 整合版** (整理而非瘦身)
- **2026-06-09 00:45 — 真测补完标注** (per [test-report-2026-06-09-comprehensive.html](docs/reports/test-report-2026-06-09-comprehensive.html))

---

## 📊 三人进度 (per git HEAD 200aba4, 06-08 EOD)

| 我 | 正在做 | 阻塞？ | 本周完成了 |
|----|--------|--------|-----------|
| **黎** (oldmanpushbike) | UI 日常维护 (feature/misc/daily-housekeeping, 6/10) | 无 | Template v4 (192 模板+favorites) ✅ + CLI streaming 全线 (5 种流式事件 UI+折叠组) ✅ + token 真数据修复 ✅ + diff 面板统一视图 ✅ + Ctrl+B 预览折叠快捷键 ✅ + 帮助弹窗真实内容 ✅ + 导航栏图标对调 ✅ + 搜索框自适应缩放 ✅ + 网页侧栏预览 ✅ + 删除确认弹窗 ✅ + 会话最近消息 ✅ + 新建文件夹白屏修复 (前后端参数传递不匹配 + FastAPI 422 对象渲染崩溃) ✅ |
| **董** (yii.d) | 协调者+任务编排部分 | 无 | 群聊全栈实现 ✅ + CLI 多模型代理 ✅ + ADR-02 长驻 CLI ✅ + 前端群聊 ✅ + 记忆系统 B 方向设计 ✅ + B1 后端实现 ✅ + B2 详细设计 ✅ + Agent 创建全链路 6 处 bug 修复 + 9 个测试 ✅ + MCP save_memory 端到端打通 ✅ + 前端记忆面板 ✅ + 记忆分支合并 main ✅ |
| **袁** (xiangbianpangde) | STATUS 收尾：绿测真相恢复 + 私聊死路闭环 (main, 6/10 12:35) | 🟢 后端 346 passed/3 skip + 前端 116 passed, 2 commit 待 push | **2026-06-10 12:35 绿测真相恢复 (TD-17)** + **私聊 1v1 死路修复 (TD-06/07, 37/37 续聊)** + **2026-06-09 18:30 pytest 现状修正** (修 14 个 v4 R2 后未同步的陈旧测试: 11 个 reactive_router (删 _state 的 dispatch_mode kwarg + 2 个 v3 行为断言 + 1 个 transcript 测试改顺序), 1 个 test_mcp _write_mcp_config 位置→kwargs, 1 个 test_claude_code_runtime 默认值 acceptEdits→bypassPermissions, 2 个 test_context Windows 路径分隔符; 跳 1 v3 时代 AT_ROUTING 静默断言 + 1 本机无 pi CLI 的工厂路由; 删 2 孤儿测试模块 (test_orchestrator_degrade + test_usage_e2e) + 1 死源 coordinator_orchestrator.py; 修 1 真生产 bug: _RecordingSink.__call__ 签名 2 参→3 参对齐 chat_service._coord_post; 改 2 个 v3 时代 events==[] 断言为 v4 真实行为 (任务受理 / 降级 note 的 1 条 system message 提示). 实测 356 pytest 全绿 / 2 skipped. 详见 TD-14) + **2026-06-09 16:30 #2 Tasks + #3 Inbox 全栈持久化 CRUD** (后端两项 mock 骨架→真 service: `TaskService`/`InboxService` + 2 Postgres 仓储 + alembic 0020 (tasks 补 2 列 + 新建 inbox_items 表) + `schemas/task.py`/`inbox.py` (含 422 校验) + 路由全接线; 前端 `api/tasks.ts`/`api/inbox.ts` (UI↔领域词表映射) + 弃 taskStore/inboxStore mock 改真 API + NavRail 加收件箱入口闭 TD-05; tsc+eslint 绿 + 9 pytest 三路径 + ~~332 pytest 无回归~~ (6/9 18:30 实测修正：当时实为 25 failed / 335 passed) + Playwright 4 截图 E2E (任务创建跨刷新持久化 + 收件箱批准→后端 resolved); 真 bug 修: 非法 enum 入参 500→422) + **2026-06-09 07:30 缺口补全 6 项** (#9 编辑Agent full E2E + #10 删除消息 + #12 ping延迟 + #7 Templates复核 + #4 CLI重扫 scan() + #8 Skills wrapper; tsc+eslint绿; gap-09/gap-10 截图; 审计排除 #2/#3 mock 骨架) + | t3 MCP P3 F3 路径 A @22:00 (2 commit fde10e4 + a2b9ff3) ✅ + t7 phase-3 @21:14 (4 commit pushed) ✅ + t7 partial @20:29 + t12 @19:43 + t6 @19:38 + t1/t2/t4 @19:18 + t8+t9 @18:45 + **2026-06-09 00:45 真测补完** (mcp.py 重复路由修复 + 4 路径 live curl + t7 pin Playwright 3 截图, 3 真 bug 暴露, pytest 332/351 (6/9 18:30 实测修正：当时实为 25 failed / 335 passed) + vitest 106/108 + live API 12/13 端点) + **2026-06-09 02:40 预览面板 4 tab 真实 UI** (Diff tab 新建 `DiffPanel.tsx` + 后端 `GET /api/fs/git-diff` + Deploy tab 新建 `DeployPanel.tsx` + `api/deploy.ts` + Files/Webpage 验证; tsc+eslint 绿; live git-diff 3 路径; Playwright 7 截图 `preview-tabs-0X-*.png`; 1 真 bug 暴露+修 `_os` NameError) |

---

## 🎯 考察要点 4 维度覆盖 (per `docs/plan/背景.md` line 57-77)

| 维度 | 权重 | 评判要点 | 当前覆盖 | 谁做的 |
|------|------|---------|---------|-------|
| AI 协作能力 | 30% | 沉淀出和 ai 协作的 Spec/skill/rules 等协作规范 | ✅ `docs/conventions/` 9 篇 + `docs/specs/` 13 篇 + `worklogs/decisions/` 18 ADR + `skills/` 9 个 + `docs/templates/` 14 个 | 全员（黎/董/袁 + Mavis owner）|
| 功能完整度 | 25% | IM 核心体验是否流畅、多 Agent 调度是否跑通 | ✅ **89%** (23 完整 + 2 部分 + 1 未做 + 1 计划)，详见 [PRD 6 大功能对账](#-prd-6-大核心功能-vs-现状-对账) | 全员 |
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
> [2026-06-07 重对账 67% → 2026-06-09 复算 74% → 2026-06-10 复算 76%] 任务看板/审批流 + 对话列表归档 升 ✅ 后: 覆盖率 = (19+3×0.5)/27 = **76%** (per [ADR-0017](worklogs/decisions/0017-prd-core-feature-25pct-gate-audit.md))

| # | 子功能 | 状态 | 证据 | 谁做的 |
|---|--------|------|------|-------|
| **1. IM 聊天** | 对话列表（新建/置顶/归档/搜索/排序）| ✅ 完整 | 群组/私聊 tab + 卡片渲染；新建 ✅ 置顶 ✅ 搜索 ✅（跳转框 300ms debounce 过滤名称/Agent）排序 ✅（pinned 优先 + 最近消息时间）**归档 ✅（6/10 袁 — 已归档分区 + 归档/取消归档 + 3 vitest + Playwright 往返截图）** | 黎（UI 基础）+ 袁（6/9 pin Playwright 3 截图 + 6/10 归档全栈前端）|
| | 单聊 1v1（明确任务）| ✅ 完整 | S1 私聊 "技术负责人" + 3 建议 + 输入框 + 附件 + WS（Composer.tsx）；**死路已闭环 (6/10 袁, TD-06/07)** — 后端 private session 通过 `chatStore.hydrateFromSessions` 回灌列表 + 写 sessionIds 续聊，空态加「发起私聊」CTA；Playwright 实测 37/37 回灌会话可续聊 | 黎（前端 Composer）+ 董（WS）+ **袁 (6/10 hydrate 修复 — Playwright 37/37 sessionId 映射 + 5 vitest)** |
| | 群聊（多 Agent + @ + Orchestrator）| ✅ 完整 | S2 群聊 6 条消息流（用户→Coordinator 拆解→Claude/OpenCode/MockBot 并行→合并汇报）| 董（群聊全栈）+ 袁（E2E 验证）|
| | 消息类型（文本/代码/图片/文件/网页预览/Diff/部署卡）| ✅ 完整 | 文本/代码/网页预览/Diff 均 ✅；图片/文件 ✅（Composer + attachments.py 200）；**部署卡 ✅**（plan_ba86c4d0 frontend-p2 + backend-p2 联合落地 `c2d2a59`+`f45a92f`, MessageBubble 部署卡接 peer DeployCardView + 状态色 + 3 路径 test）| 黎（前端）+ 董（后端 P2）+ Mavis owner (P2 委派) |
| | 消息操作（回复/引用/重新生成/复制代码/应用 Diff/展开预览）| ⚠️ 部分 | 复制代码 ✅ 重新生成 ✅ **Pin ⚠️ 端点 401 → 已修 by t1-pin-auth (6/8 overnight)** + **回复/引用 ✅** + **全屏预览 ✅** 代码完整 (3 路径单测) E2E 需真 URL | 黎（前端 MessageBubble）+ 袁（Pin 401 修复 `b97c4fd`/`bd92b2a`/`5371f41`/`2cbfff8`）|
| | 上下文管理（pin 关键消息）| ✅ 完整 | Pin 按钮 + 后端 `/api/messages/{id}/pin` 端点（schema 钉死测试）；**session 校验 ⚠️**（alembic 0012+0013 dual head race 已修 by t1 merge `2843b06`）| 黎（UI）+ 袁（后端 t1-pin-auth 5 路径 12 pytest）+ **袁 (6/9 t7 session.pinned 已真测 — Playwright 3 截图 + live PATCH 200, 详见 §6)** [已真实测试 (AI 模拟)] |
| **2. Orchestrator** | 自动分派/聚合/并行 | ✅ 完整 | Coordinator 拆解 3 任务 + 3 Agent 并行 + 合并汇报（CoordinatorPlan.tsx）| 董 |
| | 失败降级 | ✅ 完整 | plan_ba86c4d0 backend-p2 `f45a92f`（19 文件 +1974 行 + 21/21 pytest 全绿）| Mavis owner (P2 委派) |
| | 任务看板持久化 + **FSM/DAG 派发 (M3+)** | ✅ 完整 | 袁 6/9 全栈 CRUD（`TaskService`+`tasks` 表 alembic 0020 + 前端 `taskStore`）；**6/10 袁 FSM/DAG 派发落地**：事件溯源 `TaskEvent`+`task_events`(AR-05) + Orchestrator `event_sink` + `TaskService.dispatch` 状态机 + `EngineTaskDispatcher`（看板 Task→build_default_orchestrator+CoordinatorRun 真跑，复用 chat 引擎）+ `POST /api/tasks/{id}/dispatch`+`GET /events` + 前端「▶ 派发执行」按钮；5 pytest（service）+ 4 vitest（按钮）+ live 验证（dispatch→3 事件 append + 状态机 pending→running→failed + 按钮→endpoint→卡片移列）；真多 Agent run 复用 chat 引擎未 live 触发（避 LLM billing）| 袁 |
| | 用户审批流 (收件箱批准/驳回) | ✅ 完整 | 袁 6/9 全栈：`InboxService`+`inbox_items` 表 + 前端批准/驳回接 resolve + NavRail 入口；Playwright 批准→后端 resolved `tasks-inbox-03/04` | 袁 |
| | 代码冲突处理 | ❌ 未做 | 已知缺口 | — |
| **3. 多 Agent 接入** | 适配器层（Claude Code + Codex + OpenCode + Pi）| ✅ 完整 | CLI/SDK 双轨（per ADR-0001）+ 11 个队友含 Codex/OpenCode/Pi | 董（CLI 接入）+ 黎（OpenCode fix）|
| | 用户自建 Agent（对话式创建）| ✅ 完整 | 表单向导 CreateAgentModal + **6/10 袁 对话式创建落地**：后端 `AgentDraftService`+`POST /api/agents/draft-from-chat`（自然语言→DeepSeek 抽取 name/role/avatar/system_prompt/tags，5 pytest）+ 前端 `ConversationalAgentCreate` 模态（描述→生成草稿→可改预览→创建，4 vitest）；live 真 DeepSeek E2E（"擅长数据库索引优化"→草稿"索引优化专家"+5 标签，0 console 错） | 董（表单向导 6 bug+9 测）+ 袁（对话式创建全栈）|
| | 联系人列表（头像/名称/能力标签）| ✅ 完整 | AI 队友页 11 个 + 头像 + role 标签（AgentsListPage）| 黎 + **袁 (6/9 Playwright 走 11 article 确认渲染, [已真实测试 (AI 模拟)])** |
| **4. 产物预览与编辑** | 网页 iframe 内联卡片 | ✅ 完整 | `WebPreviewCard.tsx:80` iframe sandbox（集成验证 A 验）| 黎 |
| | 文档渲染 | ✅ 完整 | plan_ba86c4d0 frontend-p0-p1 `d9cd8af`+`d6a1658` 落 DocumentRenderer 3-mode (per frontend-p0-p1 verifier) | Mavis owner (P0 委派) |
| | 【P2】PPT 浏览 | ✅ 完整 | **6/10 袁** — 后端 `GET /api/fs/pptx-slides`（python-pptx 抽每页标题/正文/备注，4 pytest）+ 前端 `SlideView`（缩略图导航 + 讲者备注，3 vitest）；live 真 .pptx 2 页渲染 + 翻页 0 console 错（`p2-pptx-slideview-2026-06-10.png`）| 袁 |
| | 展开全屏预览 | ✅ 完整 | plan_ba86c4d0 frontend-p0-p1（Dialog fullscreen 模式）| Mavis owner |
| | 代码编辑器 | ✅ 完整 | plan_ba86c4d0 frontend-p2 `c2d2a59`（MonacoEditor.tsx + Composer 代码模式 + 3 路径 test）| Mavis owner (P2 委派) |
| | 【P2】Diff 视图 | ✅ 完整 | `DiffView.tsx:29-41` 彩色 emerald/rose（集成验证 B 验）| 黎 |
| | 【P2】版本历史 | ✅ 完整 | **6/10 袁** — 后端 3 端点 `file-history`/`file-at-rev`(含 unified diff)/`file-write`(只覆盖已存在文件，6 pytest)+ 前端 `versions` 预览模式 + `VersionHistoryPanel`（FileTree→提交时间线→DiffView 对比→恢复确认）；live 对 STATUS.md 50 commit 时间线 + 真 diff 渲染（`p2-version-history-2026-06-10.png`）| 袁 |
| | 【P2】对话式局部修改（选中代码→描述修改）| ✅ 完整 | **6/10 袁** — CodeView 选区→「✨ 修改选中」浮层→组装结构化 prompt（相对路径+行范围+原文+需求）经 `agent-edit-request` 事件 → ChatView onSend/WS 发给当前 Agent；`lib/selectionEdit` 11 vitest + live 选区→浮层「第 4 行」→发送 dispatch 正确 prompt（`p2-conversational-edit-popover-2026-06-10.png`）| 袁 |
| **5. 【P2】部署发布** | 聊天发送"部署"指令 → 部署卡 | ✅ 完整 | plan_ba86c4d0 backend-p2 `f45a92f`（Deploy 端点）+ frontend-p2 `c2d2a59`（部署卡前端, peer DeployCardView + 状态色）| Mavis owner (P2 委派) |
| | 预览 URL / 静态站点 / 容器化 / 源码打包 | ⚠️ 部分 | 端点已落, 真实部署流水线未跑 E2E（M5/MVP 节奏）| — |
| **6. 【P2】多端支持** | Web 端（主力）| ✅ 完整 | localhost:5174 vite dev 跑通 | 黎 + **袁 (6/9 vite 9500 跑通 + Playwright 走完 t7 pin happy path, [已真实测试 (AI 模拟)])** |
| | 桌面端 | 📋 计划 | Tauri 2 计划冻结中（`feature/desktop/spec-freeze`, per ADR-0007），**等 4 Q 答稿** (Q5-1 通知 / Q5-2 身份 / Q7-1 版本号 / Q11-1 降级方案) | 黎（proposer, worklog 2026-06-06_讨论-web转桌面app可行性.md）+ 等 董/袁 reply |
| | 移动端 H5 | ✅ 完整 | **6/8 修正**: t3-mobile-h5 `a483424`+`8124e54` 落地 useMediaQuery (React 18 useSyncExternalStore + matchMedia SSR-safe) + AppShell 4 栏 mobile/desktop 分支 + 11 vitest (5 useMediaQuery + 6 AppShell) + 4 截图 (375/768/1280/hamburger) + BDD §6.5.1.1 B-6-P2-M02 5 When/Then | 袁（t3-mobile-h5, M5 overnight）|

**整体覆盖率**: ✅ 完整 23 / ⚠️ 部分 2 / ❌ 未做 1 / 📋 计划 1 = 共 27 项 → 覆盖率 = (23 + 2×0.5) / 27 = **89%**
(6/10 下午: PPT 浏览 + 版本历史 + 对话式局部修改 三项 ❌→✅ by 袁 产物预览补全（每项后端端点 + 前端面板 + pytest/vitest + live Playwright），76%→**87%**；唯一剩 ❌ = 代码冲突处理。6/10 上午: 对话列表 ⚠️→✅ 会话归档; 6/9: 任务看板 + 审批流 ⚠️→✅ Tasks/Inbox CRUD; 6/8: 移动 H5 ⚠️→✅; per [ADR-0018](worklogs/decisions/0018-plan-3eaba0fa-overnight-4track-close.md))

---

## ⚠️ 后端已做 / 前端未做 (per袁2026-06-091:31a inventory + 本轮 grep16 router ×8 client ×7 nav实证)

> **盘点方法**: `ls src/backend/app/api/routers/` (16 router) + `Grep "@router\.(get|post|patch|delete)"` → 后端端点枚举 + `ls src/frontend/src/api/` (8 client) + `Grep "<apiName>Api\.|/api/<path>"` → 前端调用方枚举 + `Read App.tsx + CenterPanel.tsx + NavRail.tsx` → 主导航可路由性
> **结论**: PRD6 大功能"覆盖71%"是按 feature维度打的; **按 endpoint维度**, 后端 ≥57端点 vs 前端8 client 文件 (内含 ~40 函数), **实际调用覆盖率 ≈60%**,缺口集中在 MCP/Deploy/Inbox/Tasks 等后端先做/前端待补的区域
> **谁做的**:建议按端点对 owner协商 — [袁] MCP P3-F3路径 A (前后端同步), [黎] Deploy/Inbox/Tasks UI, [董] Usage router 注册 (TD-11)

| # | 后端端点 (router) | 前端现状 | 影响 (per PRD6 大功能) |接手起点 |
|---|------------------|---------|----------------------|---------|
| **1** | **MCP** (`mcp.py`) 全套10端点: `GET /api/mcp/market`, `/market/templates`, `/market/{id}`, `POST /api/mcp/installations`, `DELETE /installations/{id}`, `POST /api/mcp/bindings`, `DELETE /bindings/{id}`, **`POST /api/mcp/servers` (袁6/8 fde10e4+a2b9ff3)** | ✅ **已落地** (袁 6/9, `9a0e631`) — `api/mcp.ts` 10 函数全包 + `SkillMarketplacePage.tsx` 加 "MCP 服务" tab (市场/已安装/MCP 三 tab) + 7 截图 | **PRD §3 多 Agent接入 + §4产物** 展示区已补 | ✅ DONE (后续可独立 McpMarketPage 拆分, 当前内嵌 SkillMarketplacePage 够用) |
| **2** | **Tasks任务列表** (`tasks.py`) 全套 CRUD: `GET /api/tasks` (筛选 status/priority), **`POST /api/tasks`** (袁6/9 真持久化), **`GET /api/tasks/{id}`**, **`PATCH /api/tasks/{id}`** (改状态/拖拽), **`DELETE /api/tasks/{id}`** | ✅ **已落地** (袁 6/9, feature/frontend/preview-tabs) — 后端: `TaskService` + `PostgresTaskRepository` (复用既有 `tasks` 表 + alembic 0020 补 assignee_label/due_label 列) + `schemas/task.py` (status/priority 422 校验) + 路由全接线; 前端: `api/tasks.ts` (UI↔后端词表映射 todo↔pending 等) + `taskStore.ts` 弃 mock 改 API (load/乐观 move/create/delete) | **PRD §2 Orchestrator + 任务看板** 持久化已补 (完整 FSM/DAG 派发留 task_engine M3+) | ✅ DONE (Playwright: UI 创建任务→刷新仍在 `tasks-inbox-02`; 9 pytest 三路径) |
| **3** | **Inbox收件箱** (`inbox.py`) 审批流: `GET /api/inbox` (type 过滤/排除 resolved), `GET /api/inbox/unread-count`, **`POST /api/inbox`**, **`POST /api/inbox/{id}/read`**, **`POST /api/inbox/{id}/resolve`** (approve\|reject) | ✅ **已落地** (袁 6/9) — 后端: `InboxItem` 实体 + `InboxRepository`/`PostgresInboxRepository` + `InboxService` + `inbox_items` 表 (alembic 0020) + `schemas/inbox.py`; 前端: `api/inbox.ts` + `inboxStore.ts` 弃 mock + InboxView 批准/驳回接 resolve + NavRail 新增"收件箱"入口 (闭 TD-05 无 nav) | **PRD §2 用户审批流** 已补 (与群聊 requiresApproval 对接) | ✅ DONE (Playwright: 批准→条目移除+后端 status=resolved `tasks-inbox-03/04`; 9 pytest) |
| **4** | **CLI PATH扫描刷新** (`cli.py`) `GET /api/cli/scan`, `POST /api/cli/scan/refresh` (`CliScheduler` 每1h 自动扫, scheduler 已落) | ✅ **已落地** (袁 6/9, feature/frontend/preview-tabs) — CreateAgentModal Step 2 "重新扫描"按钮改调 `providersApi.scan()` (POST /api/providers/scan 强制重扫 PATH) 替代原 `list()` (返 1h scheduler 缓存); 用户刚装的 CLI 立刻可见 | **PRD §3 "多 Agent接入" UX** 已补 (手动重扫) | ✅ DONE (live "扫描完成,4 个可用" 验证) |
| **5** | **Deploy列表/详情/删除** (`deploy.py`) `POST /api/deployments`, **`GET /api/deployments`** (list), **`GET /api/deployments/{id}`** (detail), `DELETE /api/deployments/{id}` | ✅ **已落地** (袁 6/9, feature/frontend/preview-tabs) — 新建 `api/deploy.ts` (list/get/start/remove) + `DeployPanel.tsx` (预览面板 "部署" tab: 历史列表 + 4 状态色 + 展开 build_logs + preview/download 链接 + 删除确认弹窗 + 3s 自动刷新) + 接入 RightPanel ActiveTabContent | **PRD §5部署发布 P2** 列表 + 删除已补 | ✅ DONE (Playwright `preview-tabs-06-deploy-empty.png` 验空态; 真实数据待 DB seed) |
| **6** | **Usage 全局** (`usage.py`) `GET /api/usage`, `/global`, `/agents/{id}`, `/sessions/{id}` | ⚠️ **TD-11: `/api/usage`端点未注册 main.py** — `TokenMonitorPanel.tsx` fetch `/api/usage/global` 直接404, pytest158 + vitest106绿但 main.py漏 import | **PRD §3 多 Agent接入** 的成本可视化缺 (用户看不到 token花费) | 单独立30min ticket "register usage router in main.py" (per TD-11), 然后验证 TokenMonitorPanel 不再404 |
| **7** | **Templates sync/source/export** (`templates.py`) `POST /api/templates/sync`, `GET /api/templates/source/status`, `GET /api/templates/{id}/export` | ✅ **已落地** (复核发现早已实现, 本轮确认) — `TemplateManagementTab.tsx` 顶栏"同步模板"按钮 (handleSync→syncSource) + 来源状态卡 (SyncStatusDot + url/branch/template_count/last_synced) + toast 反馈 | PRD §1 IM聊天式交互"模板扩展" 已补 | ✅ DONE (STATUS 表此前过时, 实测已有完整 UI) |
| **8** | **Skills library高级操作** (`skills.py`) `POST /api/skills/library/create`, `/generate`, `/batch-delete`, `DELETE /library/{name}` | ✅ **已落地** (袁 6/9) — 新建 `api/skills.ts` (skillsApi: listLibrary/createLibrary/generateLibrary/removeLibrary/batchDeleteLibrary, 保留 detail 错误提取) + 替换 5 文件裸 fetch (SkillMarketplacePage 3 处 + CreateSkillDialog 2 处 + SkillMdPreview + CreateAgentModal + CustomAgentModal) | 维护性债清偿; PRD §3适配器层不受影响 | ✅ DONE (live skill list 加载验证 wrapper 通) |
| **9** | **Agents PATCH** (`agents.py`) `PATCH /api/agents/{id}` (改 name/avatar/role/skills...) | ✅ **已落地** (袁 6/9) — `agentsApi.update(id, partial)` + `agentStore.updateAgent` (PATCH + 同步本地 agents/profiles) + AgentDetailDrawer 加"编辑"入口 (内联表单: 名称/角色/系统提示 + 取消/保存 + 校验 + 错误回显) | **PRD §3 "用户自建 Agent"** 改 name/role 已通 | ✅ DONE (**full E2E**: UI 编辑→保存→后端持久化 `测试队友-UI保存验证`; `gap-09-agent-edit.png`) |
| **10** | **Sessions DELETE message** (`sessions.py`) `DELETE /api/messages/{id}` | ✅ **已落地** (袁 6/9) — `sessionsApi.deleteMessage(id)` + `chatStore.removeMessage` + MessageBubble hover "删除消息"按钮 (确认弹窗) + ChatView `onDelete` 乐观删除+失败回滚 (仅绑后端 session 的真实消息启用) | **PRD §1 IM聊天式交互"消息操作"** 已补删除维度 | ✅ DONE (UI 删除按钮 live 渲染验证 `gap-10-message-delete.png`; DELETE 端点已接线, 群聊 GroupMessageItem 待后续) |
| **11** | **Memory update 接口** (`memories.py`路由在 `/api/agents/{id}/memories`) `PATCH /api/agents/{id}/memories/{mid}` | ⚠️ **`memoriesApi.update` 已包装但 MemoryPanel 是否调用待复核** (本轮 grep0命中 `.update(`) | PRD §3 多 Agent接入的"长期记忆" 编辑路径半缺 (用户可创建但不能修改内容) | MemoryPanel 加编辑 modal 接 memoriesApi.update |
| **12** | **Provider ping UI反馈** (`providers.py`) `POST /api/providers/ping` | ✅ **已落地** (袁 6/9) — `providersApi.ping(input)` 封装 (PingInput/PingResult 类型) + CreateAgentModal 两处裸 fetch 替换 + 成功显示 "连通正常 · {latency}ms" (emerald) / 失败显示 error (red) | **PRD §3 创建 Agent UX** 连通反馈已补 (含延迟) | ✅ DONE (连通测试按钮 + 状态行 live 渲染) |
| **13** | **Proxy debug面板** (`proxy.py`) `/proxy/agents/{id}/{path:path}` (通配转发 CLI →第三方) | ❌ **无 debug/diagnose UI** — proxy 是 CLI链路基础设施, 用户不直接调用 | PRD §3 多 Agent接入的"故障排查"缺 (用户看不到 proxy 是否通) | (低优先级) settings 加 ProxyStatusPanel 显示最近 N 次代理成功/失败 |

**整体盘点结论** (2026-06-09 16:30 更新 — 袁补完 #2 Tasks + #3 Inbox 全栈 CRUD, 13 项缺口**全部清零**):
- **P0 已闭环**: ✅ #1 MCP UI · ✅ #5 Deploy list/delete · ✅ **#2 Tasks 全栈 CRUD** (后端 mock 骨架 → `TaskService`+`PostgresTaskRepository`+真持久化; 前端弃 mock 接 `api/tasks.ts`; alembic 0020)
- **P1 已闭环**: ✅ #9 Agents PATCH · ✅ #10 Message DELETE · #6 Usage (✅ 已注册) · ✅ **#3 Inbox 审批流全栈** (后端 mock 骨架 → `InboxItem`+`InboxService`+`inbox_items` 表; 前端批准/驳回接 resolve; NavRail 加入口)
- **P2 已闭环**: ✅ #4 CLI 重新扫描 · ✅ #7 Templates 同步 · ✅ #8 Skills client wrapper · ✅ #12 Provider ping · #11 Memory (✅ 已存在) · #13 Proxy (基础设施不补)
- **剩余真缺口**: **无** (13 项全闭环)。Tasks 完整 FSM/DAG 派发编排 (派给 Agent 真跑) 仍留 task_engine M3+，本轮口径是持久化 CRUD。
- **覆盖率**: 后端端点 57 → 前端实际调用 (本轮新接 Tasks 5 端点 + Inbox 5 端点 = 10 端点)，"后端完成且前端缺失"类缺口**全部清零**；同时 #2/#3 后端从 mock 骨架升级为真实 service+表

### 🆕 预览面板 4 tab 真实 UI (袁 2026-06-09 02:40, 分支 feature/frontend/preview-tabs)

> Composer "+" 菜单 / 右栏预览面板的 4 个 PreviewMode (`previewModes.ts`) 全部接真实 UI:

| tab | 状态 | 实现 | 证据 |
|-----|------|------|------|
| 项目文件 (files) | ✅ 验证 | 既有 `FilePreview.tsx` + `fsApi.browse/read` | `preview-tabs-03-files-tree.png` (真实目录树) |
| 审查 diff (diff) | ✅ **新建** | `DiffPanel.tsx` + 后端 `GET /api/fs/git-diff` (subprocess git diff, 非 repo/超时优雅降级 200+ok:false) + 复用 `DiffView` (react-diff-viewer emerald/rose) + staged 切换 + 刷新 | `preview-tabs-04-diff-real.png` (真实 git diff 表格) + live 3 路径 (repo ok / 非 git ok:false / 不存在 404) |
| 部署 (deploy) | ✅ **新建** | `api/deploy.ts` + `DeployPanel.tsx` (历史列表 + 4 状态色 + build_logs 折叠 + 删除确认 + 3s 自动刷新) | `preview-tabs-06-deploy-empty.png` (isUuid 校验空态) |
| 网页 (webpage) | ✅ 验证 | 既有 `WebPageView` (iframe sandbox + URL bar) | `preview-tabs-05-webpage.png` (example.com iframe) |

- **接入点**: `RightPanel.tsx` `ActiveTabContent` switch 加 diff/deploy 2 case + `sessionId={activeConversationId ?? activeGroupId}` 注入
- **质量**: tsc 绿 + eslint 绿 (4 处 set-state-in-effect 按项目惯例 disable) + 后端 app import OK (81 routes) + 1 真 bug 暴露+修 (`fs_git_diff` 漏 `import os as _os` → NameError, live test 发现)
- **7 截图**: `docs/deliverables/screenshots/preview-tabs-0{0..6}-*.png` (menu/diff-empty/files-empty/files-tree/diff-real/webpage/deploy-empty)

### 🆕 后端已完成但前端缺失的功能点补全 (袁 2026-06-09 07:30, 分支 feature/frontend/preview-tabs)

> 按"后端完整 + 前端缺失"口径补完 6 项 (#9/#10/#12/#7/#4/#8)。先审计 13 项缺口真实状态:
> #2 Tasks / #3 Inbox 后端是 **mock 骨架** (返空 + M3/M4 TODO), 不算"后端完成", 排除; #11 Memory `memoriesApi.update` 已存在; #13 Proxy 基础设施不补。

| # | 功能 | 实现 | 验证 |
|---|------|------|------|
| #9 | 编辑 Agent | `agentsApi.update` + `agentStore.updateAgent` + AgentDetailDrawer 内联编辑表单 (名称/角色/系统提示) | **full E2E**: UI 编辑→保存→后端持久化, `gap-09-agent-edit.png` |
| #10 | 删除消息 | `sessionsApi.deleteMessage` + `chatStore.removeMessage` + MessageBubble hover 删除按钮 (确认) + ChatView 乐观删除+回滚 | UI 按钮 live 渲染 `gap-10-message-delete.png` + DELETE 端点已接线 |
| #12 | Provider ping | `providersApi.ping` 封装 + CreateAgentModal 2 处裸 fetch 替换 + 延迟显示 ("连通正常 · {ms}") | 连通测试按钮 + 状态行 live 渲染 |
| #7 | Templates 同步 | 复核发现 TemplateManagementTab 早已有同步按钮 + 来源状态卡 + toast | 无需改动 (STATUS 表此前过时) |
| #4 | CLI 重新扫描 | CreateAgentModal "重新扫描"改调 `providersApi.scan()` (强制重扫) 替代 `list()` (缓存) | live "扫描完成,4 个可用" |
| #8 | Skills wrapper | 新建 `api/skills.ts` (5 端点) + 替换 5 文件裸 fetch | live skill list 加载验证 wrapper 通 |

- **质量**: tsc 全绿 + eslint 新增代码全绿 (AgentDetailDrawer 1 处 set-state-in-effect 按惯例 disable) + vitest MessageBubble/agent 套件通过
- **诚实标注**: #10 删除真实后端消息的完整往返未做 (无 Redis/真 CLI 的消息流); 删除按钮渲染 + 端点接线已验。#2/#3 后端 mock 未动。
- **本地 dev.db** 跑了 alembic 0001→0019 迁移 (原 0 字节) 才能 E2E #9 (sqlite, gitignored, 不提交)

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
| TD-14 | pytest 失信 (6/8 STATUS 标"332 无回归"，实测 25 failed / 335 passed) + 2 孤儿测试模块 (import 已删的 coordinator_orchestrator / discussion_orchestrator, 0b83e6a 后失活) + 1 v3 时代 AT_ROUTING 静默断言不可达 | 6/9 18:30 | 🟡 中 | 袁 | **本 commit 闭环**: 修 14 个陈旧测试（v4 R2 删 mode 枚举后未同步 / 位置参数扩展后未同步 / 默认值变更后未同步 / Windows 路径分隔符）+ 删 2 孤儿测试模块 + 删 1 死源 coordinator_orchestrator.py + 修 1 真生产 bug（_RecordingSink 签名 2→3 参，lambda 调用 3 参一致）+ 跳 1 v3 时代断言（v4 改用 reactive router 静默）。实测 356 pytest 全绿 / 2 skipped（pi_agent 本机无 CLI）。修复后 STATUS 重新对齐 6/8 起的"332 无回归"叙事 **(6/10 复核：此声明再次失真，详见 TD-17)** |
| TD-17 | 绿测漂移复发：6/10 re-baseline 实测 **12 后端 + 4 前端 fail**，与 TD-14"356 全绿"+ pin"9/9"声明矛盾。根因均为断言已被 v4 删除行为的陈旧测试（pin 鉴权放宽后的 owner/anonymous、v4 R5 移到 reactive_router 的机械停词反射、pi_agent 构造签名漂移、pin inline-error 已删、WebPreviewCard 全屏 Dialog→侧栏 preview tab） | 6/10 12:35 | ✅ 已闭环 | 袁 | commit `2135d3b`：对齐已发布行为（rewrite/remove 陈旧断言 + skip guard + 删死 import）。实测**后端 346 passed/3 skipped、前端 116 passed**、tsc+eslint 绿。根治建议：CI 去掉 `continue-on-error` 让红测真拦 PR |

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
