# 2026-06-10 功能补全：产物预览 P2 三项 + 任务编排 FSM/DAG 派发

- **谁**: 袁 (xiangbianpangde) · **分支**: main（per [[merge-to-main-approved]]，未 push per [[no-push-without-ask]]）
- **授权**: 用户特批跳过 PR-01 评审 + 可用真实 CLI agent（但不用 Claude，见 [[feedback-avoid-claude-cli-agent]]）
- **目标**: `/goal 完成 STATUS.md 所有内容，除了录制视频` 的功能缺口

## 做了什么（按 commit）

### 产物预览 P2 三项（PRD §4 三个 ❌ → ✅）
1. **PPT 浏览**：后端 `GET /api/fs/pptx-slides`（python-pptx 抽每页标题/正文/备注；415/404/413/422 边界）+ 前端 `SlideView`（缩略图导航 + 讲者备注）+ FilePreview .pptx 分发。4 pytest + 3 vitest + live 真 .pptx 2 页翻页。
2. **版本历史**：后端 3 端点 `file-history`(git log --follow)/`file-at-rev`(git show + unified diff)/`file-write`(只覆盖已存在文件) + 前端 `versions` 预览模式 + `VersionHistoryPanel`（FileTree→提交时间线→DiffView 对比→恢复确认）。6 pytest + live 对 STATUS.md 50 commit 时间线 + 真 diff。
3. **对话式局部修改**：CodeView 选区→「✨ 修改选中」浮层→`lib/selectionEdit`（computeLineRange + relativePath + buildEditPrompt）组装结构化 prompt→`agent-edit-request` 事件→ChatView onSend/WS。11 vitest + live 选区→「第 4 行」→正确 prompt dispatch。

### 任务编排 FSM/DAG 派发（PRD §2，M3+，4 commit）
- **BP1 事件溯源 (AR-05)**：`TaskEvent` 实体 + `TaskEventRepository`/`PostgresTaskEventRepository`（append-only）+ Orchestrator 可选 `event_sink`（默认 None → 356 测试零回归）。
- **BP2 派发**：`TaskService.dispatch` 状态机（pending→running→completed/failed）+ 事件记录 + `TaskService.events`；`EngineTaskDispatcher`（L3）看板 Task → `build_default_orchestrator`+`CoordinatorRun` 后台真跑（独立 session 持久化 + 状态回写），复用 chat 同款引擎。
- **端点**：`POST /api/tasks/{id}/dispatch` + `GET /api/tasks/{id}/events`。
- **前端**：`tasksApi.dispatch/events` + `taskStore.dispatchTask`（乐观）+ TaskCard「▶ 派发执行」按钮。
- **验证**：5 pytest（service）+ 4 vitest（按钮）+ live（dispatch 无会话→优雅 failed + 3 事件 append：dispatched→transition(running)→transition(failed)；UI 按钮→POST /dispatch→卡片移列，0 console 错）。

## 关键决策 / 诚实标注（per [[feedback-no-fake-evidence]]）
- **真多 Agent run 未 live 触发**：`EngineTaskDispatcher` 复用 chat 已验证的 `build_default_orchestrator`+`CoordinatorRun`；新增的 glue（载入 members + event_sink + 状态回写）走独立 session 模式。但完整群组真跑会经 planner LLM + 真 agent（可能 claude+billing），故只 live 验了新接线（端点/服务/持久化/状态机/优雅降级），未触发真跑。
- **版本「恢复」未在 live repo 点**：会覆盖真实文件；backend pytest 覆盖 file-write（覆盖已存在 + 拒绝不存在）。
- **PPT 文本方案**：python-pptx 抽文本（非 LibreOffice 保真渲染图），简单零重依赖。

## 环境备注
- postgres 容器中途重启过一次 → backend 连接池 SSL 握手坏（`connection_lost during ssl upgrade`），`docker compose restart postgres` + 重启 backend 解决。DB 主机端口 **15432**。

## 覆盖率
PRD 功能完整度 76% → **87%**（PPT/版本历史/对话式局部修改 三项 ❌→✅）。FSM/DAG 派发让「任务看板」从「CRUD only」升级为「可真派发」。唯一剩 ❌ = 代码冲突处理（worktree 隔离 + git merge 检测，16-22h）。

## 给下一位的交接
- **未 push** 本会话共 ~13 commit（test 真相 + 私聊死路 + PPT + 版本历史 + 对话式编辑 + STATUS + FSM/DAG 派发 4 + 前端 dispatch）。等用户说推。
- **剩余大工程**：代码冲突处理 (❌, 16-22h) · 对话式创建 Agent (⚠️, 需 LLM) · 部署真实流水线 (⚠️, 1.5-2 周) · 桌面端 Tauri (📋, 5-7 周, 阻塞董/黎二审)。
- **FSM/DAG 后续**：真多 Agent run 的 live E2E（需配 opencode/haiku coordinator 避 claude）；启动恢复（从 task_events 重放重建未终态 run，M3+ 后置）。
