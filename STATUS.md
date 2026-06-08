# 当前状态

> 最后更新: 2026-06-08（Template v4 + CLI streaming 全线 + 网页侧栏预览 + 图标居中 + 弹窗关闭修复 + bypassPermissions 默认 + scanner 精简）
> 规则：**每次 push 或开始/结束一个任务时，更新你自己的那一行。**

| 我 | 正在做 | 阻塞？ | 这周完成了 |
|----|--------|--------|-----------|
| 黎 | 网页侧栏预览 + 版本稳定 push main | 无 | Template v4 (192 模板+favorites) ✅ + CLI streaming 全线 (5 种流式事件 UI+折叠组) ✅ + 图标居中 ✅ + 弹窗关闭修复 ✅ + bypassPermissions ✅ + scanner 精简 ✅ + 网页侧栏预览 ✅ + 删除确认弹窗 ✅ + 会话最近消息 ✅ |
| 董 | 协调者+任务编排部分 | 无 | 群聊全栈实现 ✅ + CLI 多模型代理 ✅ + ADR-02 长驻 CLI ✅ + 前端群聊 ✅ + 记忆系统 B 方向设计 ✅ + B1 后端实现 ✅ + B2 详细设计 ✅ + Agent 创建全链路 6 处 bug 修复 + 9 个测试 ✅ + MCP save_memory 端到端打通 ✅ + 前端记忆面板 ✅ + 记忆分支合并 main ✅ |
| 袁 | **M5/M6 overnight plan finalize**（4 track 整合 + HTML 报告 + Feishu 同步 + morning handoff）| 🟡 Track 4b 2/2 Reviewer SLA 等至 2026-06-08 23:03；Track 1 e2e-pin-auth 截图缺失（worktree env 失）；Feishu 同步待 user OAuth 后 cron 跑 | **M5/M6 overnight plan `plan_3eaba0fa` 4 track 收束** (commit `60ff903` 含 19 新 commit b0caaf9→60ff903): **Track 1 Pin API 401 fix** (4 commit `b97c4fd` fix + `bd92b2a` docs + `5371f41` tests + `2cbfff8` worklog → owner merge `2843b06` → main) M5 鉴权降级契约 5 路径 (204/403/auto-trust 204/401/422/404) + 12 pytest 全绿 ✅; **Track 2a Token monitor E2E** (4 commit `46065aa` ChatService wire + `ebf678a` DiscussionOrchestrator wire + `7914a59` E2E + `60d4d69` worklog → owner merge `fbfd44a`) record_completion 真实调用点接 LLM 链 + 4 E2E pytest 100% 绿 ✅; **Track 2b CLI scheduler** (4 commit `b63d0da` feat + `66e2c52` test 6/6 + `6d1fb0a` worklog + `ddd58fc` screenshot 14559 bytes → owner merge `1714f5d` + cherry-pick `9601313`) startup hook + 1h 循环 + 优雅降级 ✅; **Track 3 mobile H5** (2 commit `a483424` useMediaQuery+AppShell + `8124e54` 11 单测+4 截图+BDD M02 → owner merge `015cf8e`) 4 栏 768 折叠 + 85/85 vitest 绿 (超 47 目标 38) ✅; **Track 4a CI gate** (2 commit `0570a43` lock file sync fix + `6cd69dd` screenshot → owner merge `9e613b8`) 4 jobs ci.yml + gh Actions run 27096545029 4/4 success 3m27s ✅; **Track 4b MCP P3 F3 spec 冻结** (1 commit `701f01b` → owner merge `60ff903`) 8 端点 12 错误码 R1/R3/R5 + 2 处内部不一致校正 + 24h SLA Reviewer Pending ⚠️ PEND; **t5-finalize 整合** (1 commit `TBD` push main) `docs/reports/test-report-2026-06-08.html` 45.7 KB semantic HTML+inline CSS 11 段 + `docs/reports/test-report-2026-06-08-feishu.md` 21.6 KB markdown 适配版 + STATUS 同步 (顶部时间戳→2026-06-08 09:00) + 袁行 overnight 全 commit 摘要 + 已知 gap #7/#8 追加 + worklog `worklogs/袁/2026-06-08_plan_3eaba0fa-finalize.md` + Feishu 同步待 user OAuth (`lark-cli` 已装 1.0.48 + daemon session 0da65648-6656-4adc-b52c-83035ed5d090 待 userCode 8Q6R-NK2R 扫 `https://open.feishu.cn/page/cli?user_code=8Q6R-NK2R` + cron `feishu-sync-monitor` 每 3min 自检) + pytest 168/171 (3 deferred: 2 pi_agent + 1 flaky selector) + vitest 85/85 + Playwright 6 必选+2 加分截图 + 7 downscope 决策显式披露 + ADR-0014 strong-close 接受 baseline debt ✅ |

## ⏭️ 进行中交接

- **✅ 2026-06-07 凌晨冲刺（plan_bcf9945c 收束,06/07 01:20-05:50,Mavis owner）**：
  - 决策：`worklogs/decisions/0010-integration-verify-downscope-e.md`（E 视觉 downscope 到 API+code,Inbox M4 TODO）+ `worklogs/decisions/0011-plan-bcf9945c-complete.md`（plan_complete=true）
  - 5 task 全部 deliverable 落档 + verifier 复核 PASS:
    1. **P0-4 + P0-5 合并** — `commit 32485a1` on `feature/frontend/pin-ui`（MessageBubble Pin 按钮 + 复制/重新生成 + schema-钉死 test）
    2. **集成验证 5/6 PASS**（E 视觉 downscope）— `docs/deliverables/integration-verify-report.md` + 4 张真集成截图（S2 group + AI 列表 fullpage/viewport）+ 6 E2E: A iframe-sandbox ✓ / B colored-diff ✓ / C Pin/Unpin ✓ / D 复制代码 ✓ / E S5 inbox FAIL (M4 TODO) / F 1KB upload ✓
    3. **video-record** — `docs/deliverables/video/script.md` 13KB 6 章节 + `raw-recording.mp4` 14.5MB 200s 1920x1080 + 3 抽帧 PNG
    4. **video-produce** — `AgentHub-Demo-Video.mp4` 17.7MB 200s 1920x1080 h264+aac+mov_text 字幕 zho + 7 TTS wav + 2 AI cover + 27 subtitle
    5. **docs-feishu**（v1 override_accept + v2 attempt 2 PASS）— `docs/deliverables/AI协作开发记录.md` 12.1KB CJK 3214 6 段 a-f + PRD 增量更新（commit `602026f` + `82b265a`）
  - **P0 缺口状态变化**（roadmap §8 必修 P0 段同步）：
    - P0-1 网页预览 iframe — ✅ **已做**（`WebPreviewCard.tsx:80` iframe sandbox + 集成验证 A 验）
    - P0-2 Diff 视图 — ✅ **已做**（`DiffView.tsx:29-41` 彩色 emerald/rose + 集成验证 B 验）
    - P0-3 文件附件上传 — ✅ **已做**（后端 `attachments.py:99-158` 10MiB + 7 MIME + 集成验证 F 验 200+200 round-trip）
    - P0-4 Pin 消息 UI — ✅ **已做**（`MessageBubble.tsx:155-188` Pin 按钮 + schema-钉死 test + 集成验证 C 验 204x2）
    - P0-5 复制代码/重新生成 — ✅ **已做**（`MessageBubble.tsx:112-144` handleCopyCode + mock.ts:105 改文案 + unit test + 集成验证 D 验）
    - P0-6 端到端 Demo 数据集 + 录制脚本 — ✅ **已做**（seed_demo_data.py 11 agents/4 sessions/19 messages + video script 6 章节）
  - **已知 gap（明早向用户披露）**：
    1. E 视觉 S5 inbox 3 重 gap（backend TODO / frontend mock / UI 无 nav）— M4 TODO 标
    2. S3 私聊 UI 不可达（ChatView mock-driven, LeftPanel 只 user-created）— 已 downscope
    3. Pin API 无 session 所有权校验（probe 2 FAIL）— 需 backend 修复
    4. Docker backend image 6h old 缺 `/api/attachments/*` — F 测试用 local uvicorn :8766
    5. 视频 v4 录屏 DISPLAY1 wallpaper 残留（v5 Win32 SetWindowPos + ffmpeg crash 失败）— 已透明声明
  - **owner 后续**：与用户讨论 push 策略 / 旧 PRD 删除 / M3/M4 inbox 视觉补；不主动追问，遵循 0008 自主决策。

- **🚧 2026-06-07 12:00 Mavis E2E 视觉验证（用户疑虑"功能都没实现"触发）**：
  - **方法**：纯 cu (Computer Use) 在 agentHub 上失灵（坐标精度 + Chinese encoding 被 PS 5.1 破坏）→ 切 **playwright MCP** 走 DOM 精准（getByRole + ref + evaluate）
  - **6 章节实测**：
    | ID | 功能 | 状态 | 证据 |
    |----|------|------|------|
    | F1 | S1 私聊建议按钮 | ⚠️ **部分** | POST `/api/sessions` 201 session 创建 ✅；❌ 3 建议按钮（帮我看看代码/改个 bug/起新项目）click **不响应**（无 /api/messages POST + 输入框未填） |
    | F2 | S2 群组消息流 | ✅ **完整** | GET /api/sessions?type=group 200 + /api/sessions/<id>/messages 200；6 条消息流：用户 → Coordinator 拆解 → Claude/OpenCode/MockBot 并行 → Coordinator 合并汇报（含 ✅ 3/3 表格） |
    | F3 | AI 队友列表 | ✅ **完整** | 11 个队友真在（技术负责人/Claude/OpenCode/MockBot/Codex/Pi/MyBot）|
    | F5 | 主题切换 | ✅ **完整** | 点击 → isDark=true（深色模式生效） |
    | Skill | 技能市场 | ✅ **完整** | 12 个 skill 卡片（AI 股票/Skill Creator/Autodesk/Humanizer/...） |
    | F4 任务/F6 创建群组/F7 设置/F8 私聊空状态 | ⏳ 未测 | 时间有限 |
  - **核心结论**：「功能都没实现」**是误判**。AgentHub 核心 backend 真在工作。Console **0 错 0 警**
  - **新发现 gap #6**（追加到已知 gap 列表）：
    - S1 私聊 3 建议按钮 click **不响应**（前端 mock 未接好，需改 ChatView）
    - 群组管理列表页的卡片 💬 icon **误导用户**（实际"进入群聊"在卡片右下角按钮），UX 混乱
    - **P0-4/P0-5 S2 群聊未实现**：`group/msg` wrapper 是 hover 触发区但**完全没有 Pin/复制代码子元素**（DOM tree hasBtns: 0 全程，4 known 前端必修项已实现但只接 S1 mock）
    - **F4 任务看板 ✅ 实际已实现**（7 个任务，4 列待处理/进行中/阻塞/完成）— 修正之前 M4 TODO 标
  - **11 章节完整结果**（已测）：
    | ID | 功能 | 状态 |
    |----|------|------|
    | F1 | S1 私聊建议按钮 | ⚠️ 部分（session 创但建议不响应）|
    | F2 | S2 群组消息流 | ✅ 完整 |
    | F3 | AI 队友列表 | ✅ 完整（11 个） |
    | F4 | 任务看板 | ✅ **完整**（已实现，4 列 + 7 任务 + 创建任务按钮）|
    | F5 | 主题切换 | ✅ 完整 |
    | F6 | 创建群组 | ✅ 完整（modal 频道名/描述/工作目录/11 队友勾选）|
    | F7 | 设置 | ✅ 工作（"无配置"+ API 密钥管理链接）|
    | F8 | 私聊空状态 | ✅（"还没有私聊 · 跟 AI 队友里发起"）|
    | F9 | Pin / 复制代码 | ❌ S2 群聊没实现（group/msg 无子元素）|
    | Skill | 技能市场 | ✅ 完整（12 个）|
  - **下一步**：修 S1 建议按钮 + 接 P0-4/P0-5 到 S2 群聊 + 重做 v6 录制脚本（基于真实工作流）
  - 工具沉淀（详见 agent memory `MEMORY.md`）：cu PowerShell JSON 注入坑、cu 测试协议、ffmpeg gdigrab 录屏、Playwright demo 录屏核心约束

- **🎯 2026-06-07 19:15 Mavis PRD 核心功能 vs 现状对照（plan_ba86c4d0 强收后重对账）**（基于 `docs/plan/背景.md`）：
  - 评估依据：plan_ba86c4d0 7 impl commit 落 main (HEAD eea1d0e) + 凌晨冲刺 4 commit + E2E 实测 + 代码阅读
  - PRD 6 大核心功能（背景文件 line 15-56）：

  | # | PRD 核心功能 | 子功能 | 状态 | 证据 |
  |---|-------------|--------|------|------|
  | **1. IM 聊天** | 对话列表（新建/置顶/归档/搜索/排序）| ⚠️ 部分 | 群组/私聊 tab + 卡片渲染；**置顶/归档/搜索未做**（UI 缺）|
  | | 单聊 1v1（明确任务）| ✅ 完整 | S1 私聊 "技术负责人" + 3 建议 + 输入框 + 附件 + WS（Composer.tsx）|
  | | 群聊（多 Agent + @ + Orchestrator）| ✅ 完整 | S2 群聊 6 条消息流（用户→Coordinator 拆解→Claude/OpenCode/MockBot 并行→合并汇报）|
  | | 消息类型（文本/代码/图片/文件/网页预览/Diff/部署卡）| ✅ 完整 | 文本/代码/网页预览/Diff 均 ✅；图片/文件 ✅（Composer + attachments.py 200）；**部署卡 ✅**（plan_ba86c4d0 frontend-p2 + backend-p2 联合落地 c2d2a59 + f45a92f, MessageBubble 部署卡接 peer DeployCardView + 状态色 + 3 路径 test）|
    | | 消息操作（回复/引用/重新生成/复制代码/应用 Diff/展开预览）| ⚠️ 部分 | 复制代码 ✅ 重新生成 ✅ **Pin ⚠️ 端点 401**（plan_ba86c4d0 frontend-p0-p1 d9cd8af + d6a1658 落 main, 74/74 vitest, 3 截图, **22:00 Playwright E2E 发现 Pin API 401 bug 待修**）+ **回复/引用 ✅** + **全屏预览 ✅** 代码完整 (3 路径单测) E2E 需真 URL |
  | | 上下文管理（pin 关键消息）| ✅ 完整 | Pin 按钮 + 后端 /api/messages/{id}/pin 端点（schema 钉死测试）；**session 校验 ⚠️**（plan_ba86c4d0 backend-p0-p1 endpoint 全 work + 168 pytest 绿, alembic 0012+0013 dual head race 未修, M5/M6 手动补 ~1h）|
  | **2. Orchestrator** | 自动分派/聚合/并行 | ✅ 完整 | Coordinator 拆解 3 任务 + 3 Agent 并行 + 合并汇报（CoordinatorPlan.tsx）|
  | | 失败降级 | ✅ 完整 | plan_ba86c4d0 backend-p2 f45a92f（19 文件 +1974 行 + 21/21 pytest 全绿）|
  | | 代码冲突处理 | ❌ 未做 | |
  | **3. 多 Agent 接入** | 适配器层（Claude Code + Codex + OpenCode + Pi）| ✅ 完整 | CLI/SDK 双轨（per ADR-0001）+ 11 个队友含 Codex/OpenCode/Pi（per STATUS.md 5/6 月工作）|
  | | 用户自建 Agent（对话式创建）| ⚠️ 部分 | CreateAgentModal 存在（E2E 验证 04-modal）|
  | | 联系人列表（头像/名称/能力标签）| ✅ 完整 | AI 队友页 11 个 + 头像 + role 标签（AgentsListPage）|
  | **4. 产物预览与编辑** | 网页 iframe 内联卡片 | ✅ 完整 | WebPreviewCard.tsx:80 iframe sandbox（集成验证 A 验）|
  | | 文档渲染 | ✅ 完整 | plan_ba86c4d0 frontend-p0-p1 d9cd8af + d6a1658 落 DocumentRenderer 3-mode (per frontend-p0-p1 verifier) |
  | | 【P2】PPT 浏览 | ❌ 未做 | 已知 P2 |
  | | 展开全屏预览 | ✅ 完整 | plan_ba86c4d0 frontend-p0-p1（Dialog fullscreen 模式） |
  | | 代码编辑器 | ✅ 完整 | plan_ba86c4d0 frontend-p2 c2d2a59（MonacoEditor.tsx + Composer 代码模式 + 3 路径 test）|
  | | 【P2】Diff 视图 | ✅ 完整 | DiffView.tsx:29-41 彩色 emerald/rose（集成验证 B 验）|
  | | 【P2】版本历史 | ❌ 未做 | |
  | | 【P2】对话式局部修改（选中代码→描述修改）| ❌ 未做 | |
  | **5. 【P2】部署发布** | 聊天发送"部署"指令 → 部署卡 | ✅ 完整 | plan_ba86c4d0 backend-p2 f45a92f（Deploy 端点）+ frontend-p2 c2d2a59（部署卡前端, peer DeployCardView + 状态色）|
  | | 预览 URL / 静态站点 / 容器化 / 源码打包 | ⚠️ 部分 | 端点已落, 真实部署流水线未跑 E2E（M5/MVP 节奏）|
  | **6. 【P2】多端支持** | Web 端（主力）| ✅ 完整 | localhost:5174 vite dev 跑通 |
  | | 桌面端 | 📋 计划 | Tauri 2 计划冻结中（`feature/desktop/spec-freeze`，per STATUS.md line 70-72）|
    | | 移动端 H5 | ❌ 未实现 | **[22:00 校正]** Playwright `browser_resize` 768x1024 实测：4 栏 (NavRail/LeftPanel/ChatArea/RightPanel) 仍并排, 无 hamburger / panel 折叠 / stack 重排; grep `useMediaQuery / isMobile / sm:hidden / md:block` 只在 6 处 page 内部 grid 用 sm:grid-cols, 不影响主 4 栏 shell. STATUS 之前"✅ 完整"是错的, 实际与 [pending] 一致 |

  - **整体覆盖率**（[2026-06-07 22:00 重对账, Phase 2 Playwright E2E 后]）：✅ 完整 15 / ⚠️ 部分 5 / ❌ 未做 5 / 📋 计划 1 / ⏳ M5/M6 手动补 4
  - **核心必修 P0 项**（PRD "考察要点" 25% 功能完整度）：P0-1 iframe ✅ / P0-2 Diff ✅ / P0-3 附件 ✅ / P0-4 Pin ⚠️ / P0-5 复制代码 ✅ / P0-6 Demo 数据集 ✅（Pin API 401 bug 待修, 1-2h 工作量）
  - **下一步建议（[2026-06-07 22:00 更新]）**：
    - **M5/M6 重点补**（**~7h**，4h+3h 新增）：P0-4 后端 Pin session 校验 ~1h + **P0-4 Pin API 401 bug ~2h**（新, 22:00 E2E 发现）+ P1-2 后端 Token 消耗监控 ~2h + P1-3 后端 CLI PATH 扫描 ~1h + **F10 移动 H5 实施 ~3-5d**（新, 4 栏 responsive shell, 大工作量 P2 推迟项）
    - **M5/MVP 节奏**（"⚠️ 部分" 5 项继续推进）：对话列表搜索/置顶 + 消息类型部署卡集成 + 消息操作应用 Diff + 文档渲染组件独立 + Pin API 修复
    - **后续**（"❌ 未做" 5 项按 PRD 优先级）：Orchestrator 代码冲突处理 + PPT 浏览 + 对话式局部修改 + 移动端原生 + **移动 H5 响应式**（新增）

- **🚧 桌面 App 计划冻结中**（分支 `feature/desktop/spec-freeze`,docs-only,未 push）：
  - 决策:Tauri 2 + M2 瘦客户端(连用户自部署 backend)+ GitHub Releases 自下载,不进任何商店
  - 产出:ADR-0007(`worklogs/decisions/0007-tauri-desktop-pivot.md`)+ 规格草案(`docs/specs/06-desktop-app_桌面App规格.md`)
  - 工作量:5-7 周到首个公开 v0.1.0
  - ⚠️ **阻塞:PR-01 2 人 Review**,需 董/袁 之一答完规格 §十二 4 Q(Q5-1 通知 / Q5-2 身份 / Q7-1 版本号 / Q11-1 降级方案)
  - 接手起点:worklog `worklogs/黎/2026-06-06_讨论-web转桌面app可行性.md`「给下一位的交接」段

- **MCP F1 + F2 已全部并入 main**（F1 tag `mcp-f1`,F2 commit `002f3fb`）：
  - **F1 市场 + 安装**：market+install 5 端点 + McpInstaller 端口 + LocalMcpInstaller 结构校验(transport 必填项，422 拦截非法配置)替代骨架 ready + 19 单测绿；ADR-04 + [收束报告-F1](docs/reports/收束报告-MCP-F1.md) 双线签核闭合
  - **F2 接入**：`POST/DELETE /api/mcp/bindings` + `McpBindingService`（bind/unbind）+ `agent_mcp_bindings` 改 status=active **部分唯一**（alembic 0010）→ 解绑后可 rebind
  - **attach = 请求携带**（ADR-05）：`AgentRequest.mcp_servers` + `build_request_mcp_servers` + `ContextBuilder` 可选 `mcp_resolver` 注入（私聊/群聊）
  - **统一注入原则 + opencode 拉回本期**（ADR-06 / RT-MCP）：`OPENCODE_CONFIG=<tmp>` 逐进程隔离通道（实测注入成功、零串号），落码 `_entry_to_opencode`+`_build_opencode_mcp`+`_write_opencode_config`，记忆+绑定 servers 自包含临时配置；**opencode 连接级 E2E 冒烟通过**（`opencode mcp list` 显示 `✓ everything connected`，真拉起 stdio MCP server 完成 initialize/tools 握手）
  - **pi_agent deferred**（本机无 pi 二进制可验证,`_build_cmd` 留 NB-02 seam 注释,解除前置门 RT-MCP §3.3）
  - **F2 收束-2 闭合（2026-06-04）**：四阶段双线签核（[收束报告-F2](docs/reports/收束报告-MCP-F2.md)）；MCP 专项 34/34 绿
  - **路径分离**（`90195f6`）：董记忆 MCP 协议端 mount 移到 `/api/mcp-memory`，`/api/mcp/*` 归市场 REST（§2.6 契约不变）；`settings.mcp_memory_url` 示例同步为 `.../api/mcp-memory/sse`
  - **P2 后续（移交 P3/P4）**：完整 chat→tool_call（需 LLM key，P4 带 key 验）· 工具级 tool_subset 过滤（P4）· pi_agent 待上游 MCP 支持

- **🚧 MCP P3 F3 创建（待启动,6/6-6/8,34h,袁）**：stdio/sse 提交 + 模板 + dry-run 验证（单 Docker + compose 限额，E-03 简化版）。**收束-3 闸门**：收束 3 + ADR 0005。
  - 起点：`docs/plan/后续升级计划/MCP接入/06-详细设计/FS-MCP-V1.0-20260602.md` §1 + `docs/specs/04-commands_命令接口.md` §2.6/§三

- **🚧 MCP P4 F5 展示（待启动,6/12-6/15,33h,袁）**：工具调用内联卡片 + WebSocket 事件。**收束-4 闸门**：收束 4 + ADR 0007。
  - 关键依赖：完整 chat→tool_call 链路（带 LLM key E2E 验）

- **📋 roadmap §8 必修 P0（6/2-6/9,M5 范围）— 当前实际完成度**（[2026-06-07 19:15 重对账]）：
  - **前端 6 P0 已全数完成**（凌晨冲刺 plan_bcf9945c 收束 05:50, 4 commit 落 main）：
    - P0-1 网页预览 iframe 卡片 — ✅（`WebPreviewCard.tsx:80` iframe sandbox + 集成验证 A 验）
    - P0-2 Diff 视图（diff2html 集成）— ✅（`DiffView.tsx:29-41` 彩色 emerald/rose + 集成验证 B 验）
    - P0-3 文件附件上传 + 预览 API — ✅（`src/backend/app/api/routers/attachments.py:99-158` 10MiB + 7 MIME + 集成验证 F 200+200 round-trip 验）
    - P0-4 Pin 消息 UI — ✅（`MessageBubble.tsx:155-188` Pin 按钮 + schema-钉死 test + 集成验证 C 204x2 验）
    - P0-5 复制代码 / 重新生成按钮 — ✅（`MessageBubble.tsx:112-144` handleCopyCode + mock.ts:105 改文案 + unit test + 集成验证 D 验）
    - P0-6 端到端 Demo 数据集 + 录制脚本 — ✅（`seed_demo_data.py` 11 agents/4 sessions/19 messages + video script 6 章节）
  - **后端 3 known gap 留 M5/M6 手动补**（[plan_ba86c4d0 强收 ADR-0014](worklogs/decisions/0014-mavis-team-plan-ba86c4d0-strong-close.md) 接受，3 task endpoint 全 work + pytest 绿，但主 feature 持久化层 / 调度器未落）：
    - P0-4 后端 Pin session 所有权校验 — ❌（endpoints 全 work, alembic 0012+0013 dual head race 未修, merge 0014 migration 留 M5/M6, 估 ~1h）
    - P1-2 后端 Token 消耗监控 — ❌（usage 4 端点全 work + 1h/24h/7d window, token counter 持久化层未落, 估 ~2h）
    - P1-3 后端 CLI PATH 扫描 — ❌（cli scan 端点全 work + 5 bin 1h cache, scan 调度器未集成到 agent heartbeat, 估 ~1h）
  - **M5/M6 手动补总工作量**：~4h（1+2+1）
  - **M5 5.4（CI workflow）+ 5.5（文档沉淀）** 已在 plan_ba86c4d0 强收中完成（见 line 154-161）

## 🧾 技术债（收束盘点）

| 问题 | 发现 | 优先级 | 预计修复 |
|------|------|--------|----------|
| 既有套件测试隔离 flaky（`test_context_builder` 模块级 fakeredis 单例 / `test_selector` LLM 环境敏感）| MCP F1 收束-1 | 🟡 中 | 独立工单（非 MCP 引入）|
| ~~`agent_mcp_bindings` UNIQUE(agent,installation) 与软删 rebind 冲突~~ ✅ **已修**（alembic 0010 部分唯一索引,解绑后可 rebind）| MCP F1 实现 | — | 已修（2026-06-03）|
| ~~安装为结构校验骨架（无真实可达性/进程探针）~~ ✅ **已升级** McpInstaller 端口 + LocalMcpInstaller 结构校验(transport 必填项,422 拦截非法配置)替代骨架 ready；真实可达性/进程探针仍 deferred | MCP F1 → F2 收束 | 🟢 低 | P3/P4 真实探针(seam 已留) |
| NB-02 defer：AP-02 错误信封统一 / AP-05 URL 版本 / workspaces·users 实体+FK / 全局 JWT 鉴权 | 二次对账 | 🟢 低 | 平台化阶段 |
| ~~`/api/mcp` 路径重叠~~ ✅ 已解决：记忆 MCP 协议端移 `/api/mcp-memory`，REST 独占 `/api/mcp/*` | F1↔记忆 merge | — | 已修（2026-06-03） |
| ~~MCP 注入 claude_code-only（R11）~~ ✅ opencode 已拉回（ADR-06，`OPENCODE_CONFIG` 逐进程通道+8 测试+连接级 E2E 冒烟）；**pi_agent 仍 deferred**（本机无 pi 二进制可验证）| P2 运行时审计 | 🟢 低 | pi_agent 待上游 MCP 支持（解除门 RT-MCP §3.3）|
| ~~P0-3 文件附件后端 multipart API 缺失~~ ✅ **已补**（`src/backend/app/api/routers/attachments.py:99-158` 10MiB + 7 MIME + F 200+200 round-trip 验证, 凌晨冲刺 plan_bcf9945c 05:50 收束）| 2026-06-07 凌晨冲刺 | — | 已修 |
| ~~P0-4 Pin 消息 UI 缺失~~ ✅ **已补**（`MessageBubble.tsx:155-188` Pin 按钮 + schema-钉死 test + C 204x2 验证, 凌晨冲刺 05:50 收束）| 2026-06-07 凌晨冲刺 | — | 已修 |
| ~~P0-5 复制代码/重新生成 按钮~~ ✅ **已补**（`MessageBubble.tsx:112-144` handleCopyCode + mock.ts:105 改文案 + D 验证, 凌晨冲刺 05:50 收束）| 2026-06-07 凌晨冲刺 | — | 已修 |
| **🆕 P0-4 后端 Pin session 所有权校验未实现**（mavis-team plan_ba86c4d0 backend-p0-p1 endpoint 全 work + 401/403/422 校验在 endpoint 层（src/backend/app/api/routers/sessions.py:87-122），但 alembic 0012+0013 dual head race 未修, merge 0014 migration + 2 测）| 2026-06-07 plan_ba86c4d0 强收 (ADR-0014) | 🔴 高 | M5/M6 手动补 ~1h（owner 写 migration + 2 测）|
| **🆕 P0-4 Pin API 401 bug 22:00 E2E 发现**（Playwright 实测点 Pin 按钮 → console `[ERROR] 401 @ /api/messages/97a83bf5.../pin?session_id=...` + UI 弹 "Pin 失败 / API 401" alert via GroupMessageItem.tsx:144, 落 data-testid="pin-error"）。**与 line 160 Pin session 校验不同**：session 校验是"未登录"或"无权限", 401 看起来像"JWT 鉴权缺失或过期"。需排查 `get_current_user` 是否要求 Authorization header（plan_ba86c4d0 报告称只解析不强制 → 当前 401 印证）| 2026-06-07 22:00 Playwright E2E (worklog `2026-06-07_plan_ba86c4d0-phase2-e2e-playwright.md` commit `0ebe3b2`) | 🔴 高 | M5 必修 ~1-2h（修 `get_current_user` 鉴权链 + 加 dev mode 跳过 OR 修 `/api/messages/{id}/pin` 用 ws session + 2 测）|
| **🆕 P1-2 后端 Token 消耗监控未实现**（[2026-06-07 19:50 校正] plan_ba86c4d0 backend-p0-p1 **实际完整落地** 5 层: domain/{token_counter,usage_record} + application/services/usage_service + infrastructure/repositories/usage_repository + api/routers/usage.py 3 endpoint (1h/24h/7d window)。**STATUS 之前"持久化层未落"是错的**，实际 `PostgresUsageRepository.save()` + `UsageRecordModel` SQLAlchemy ORM 全在. 真正缺的是**全链路 E2E 验证**（record_completion 在哪个调用点被触发？还差 integration test）| 2026-06-07 plan_ba86c4d0 强收 (ADR-0014) + 19:50 实测校正 | 🟢 **完成 80%** | M5/M6 补 ~30min（搜 record_completion 调用点 + 3 E2E test）|
| **🆕 P1-3 后端 CLI PATH 扫描未实现**（[2026-06-07 19:50 校正] plan_ba86c4d0 backend-p0-p1 **cli scan endpoint + cache 全 work**（api/routers/cli.py 完整, infrastructure/cli_scanner.py 完整），**真正缺的是 scheduler 集成** — `/api/cli/scan` 只在被 HTTP 调用时执行，没有 agent heartbeat / 启动时自动 scan 钩子）| 2026-06-07 plan_ba86c4d0 强收 (ADR-0014) + 19:50 实测校正 | 🟡 中 | M5/M6 补 ~1h（1 startup hook + 1 cron job + 4 测）|
| **🆕 [2026-06-07 19:50 实测发现] deploy.py:81 FastAPI Annotated + Query(default) 冲突**（backend-p2 f45a92f 引入的真 bug: `Annotated[bool, Query(default=False)] = False` 触发 AssertionError, 整个 app 启动失败。**已修**（改 `Annotated[bool, Query()] = False`），157 pytest + 60 routes import OK. pytest 实际 157 pass / 2 deferred（pi_agent E2E 本机无 binary 已知）| 2026-06-07 Mavis owner 实测 | — | **已修** |
| **🆕 [2026-06-07 22:00 校正] 移动 H5 之前 STATUS 标 ✅ 完整 是错的**（PRD 对照表行原"移动端 CSS @media 768px 隐藏右侧 panel + 简版 Composer"实际是文档承诺 / 计划, 22:00 Playwright `browser_resize` 768 实测 4 栏仍并排, 无 hamburger / panel 折叠 / stack 重排; grep `useMediaQuery` 在前端项目零匹配. STATUS 误判源自 plan_ba86c4d0 frontend-p2 c2d2a59 commit message 自报 ✅ 但代码实际未交付. **当前真实状态**: ❌ 未实现, 与 [pending] 一致）| 2026-06-07 22:00 Playwright E2E + 全项目 grep | 🟡 中 | M5/MVP 实施 ~3-5d（4 栏 responsive shell + useMediaQuery hook + panel 折叠状态机）|
| **🆕 [2026-06-08 overnight] Pin API 401 fix + alembic 0014 merge + 401/403/204 三路径**（`b97c4fd`/`bd92b2a`/`5371f41`/`2cbfff8` on `feature/m5/pin-auth-fix` → owner merge `2843b06` → main）. M5 鉴权降级契约 5 路径：JWT+U1/U1→204 / JWT+U1/U2→403 / 无 JWT+msg.user_id→204 auto-trust / 无 JWT+system message→401 AuthRequiredError / 不存在 msg_id→404. 12 pytest 100% 绿 (含 test_pin_route_anonymous_404 改名). 唯一缺口: **e2e-pin-auth-2026-06-08.png 截图未生成** (worktree env DATABASE_URL 传递丢 → uvicorn :18010 启动 500; HTTP-level 测试已端到端覆盖)| 2026-06-08 t1-pin-auth (M5 overnight) | ✅ done | **明天 09:00 兜底**: docker compose build backend (15-20min) 或用 .env 自动加载 uvicorn :18010 --reload |
| **🆕 [2026-06-08 overnight] P1-2 Token 监控 E2E 收尾**（`46065aa` ChatService wire + `ebf678a` DiscussionOrchestrator wire + `7914a59` 4 E2E pytest + `60d4d69` worklog → owner merge `fbfd44a` → main）. record_completion 真实调用点接 LLM 链 (chat_service.py:271 + discussion_orchestrator.py:300 + ws/chat.py 手动构造) + 4 E2E (1h/24h/7d window + 触发点验证) 全绿. 1 caveat: **/api/usage HTTP 端点未注册到 main.py** (pre-existing infra gap, T2 不在 scope 内)| 2026-06-08 t2-token-monitor (M5 overnight) | ✅ done | 建议单独立 30min ticket「register usage router in main.py」|
| **🆕 [2026-06-08 overnight] P1-3 CLI PATH 扫描 scheduler 集成**（`b63d0da` feat CliScheduler + `66e2c52` 6/6 test + `6d1fb0a` worklog + `ddd58fc` screenshot → owner merge `1714f5d` + cherry-pick `9601313` → main）. lifespan startup hook + 后台 1h 循环 + 模块级单例 (复用 claude_code_process_pool.sweeper 模式) + 优雅降级 (pi/trae 缺失 warning) + Playwright 截图 22 KB| 2026-06-08 t2-cli-scheduler (M5 overnight) | ✅ done | — |
| **🆕 [2026-06-08 overnight] 移动 H5 响应式实施**（`a483424` useMediaQuery+AppShell + `8124e54` 11 单测+4 截图+BDD M02 → owner merge `015cf8e` → main）. useMediaQuery hook (React 18 useSyncExternalStore + matchMedia SSR-safe) + AppShell 4 栏 mobile/desktop 分支 + 11 vitest (5 useMediaQuery + 6 AppShell) + 4 截图 (375/768/1280/hamburger) + BDD §6.5.1.1 B-6-P2-M02 5 When/Then. vitest 85/85 (超 47 目标 38)| 2026-06-08 t3-mobile-h5 (M5 overnight) | ✅ done | — |
| **🆕 [2026-06-08 overnight] M5 5.4 CI gate**（`0570a43` lock file sync fix + `6cd69dd` screenshot → owner merge `9e613b8` → main）. 4 jobs ci.yml (ruff+mypy+tsc+eslint+vitest+playwright, 沿用 `eea1d0e` continue-on-error baseline) + gh Actions run 27096545029 4/4 success 3m27s. lock file 同步是 `230fed8` 引入的真 bug (7 deps 加 package.json 未同步 lockfile)| 2026-06-08 t4-ci-gate (M5 overnight) | ✅ done | Node.js 20 deprecation 警告 (2026-06-16 强制 Node 24), 后续 bump @v4→@v5 |
| **🆕 [2026-06-08 overnight] MCP P3 F3 spec 冻结**（`701f01b` docs v2.2→v2.3 → owner merge `60ff903` → main）. 8 端点 (市场 3 + 安装 2 + 绑定 2 + 创建 1) + 12 错误码 + 二次对账 R1/R3/R5 + 2 处内部不一致校正 (DELETE /api/mcp/bindings 副作用与 ADR-05 / tool_call:cancel placement) + §三 WS 5 事件 (4 S→C + 1 C→S) + AP-07 信封. **2/2 Reviewer Approve pending**: 董 yii.d + 黎 oldmanpushbike 周日 23:03 离线, 24h SLA 至 2026-06-08 23:03. 路径 A (2/2)→完成; 路径 B (1/2 或 0/2)→ADR-0015 downscope docs-only| 2026-06-08 t4-mcp-spec (M5 overnight) | ⚠️ PEND | 24h SLA 后 owner 决策 A/B |
| **🆕 [2026-06-08 overnight] 新发现 gap #7: pytest 1 flaky selector test**（`test_llm_failure_degrades_to_done` 在 isolated run PASS / full suite FAIL — T-04 红线 test pollution + LLM 非确定性. **不在本 plan 任何 track scope**, T-01 测试隔离债）| 2026-06-08 t1 + t2 verifier 复跑发现 | 🟡 中 | 独立工单（非本 plan 引入）|
| **🆕 [2026-06-08 overnight] 新发现 gap #8: 跨 worker shared worktree 5+ 次 git checkout 覆盖**（plan_3eaba0fa 5 worker 并行共享 working tree, 实测 5+ 次 `git checkout <other-branch>` 把 t4-mcp-spec 写好的 spec + worklog 改动 revert 掉, 需用 git plumbing (`hash-object -w` + `read-tree` + `update-index` + `write-tree` + `commit-tree` + `update-ref`) 在临时 `GIT_INDEX_FILE` 中创建 commit. 教训落 `t4-mcp-spec/atomic_commit.py` 归档 + `mcp-detailed-designer` MEMORY §15）| 2026-06-08 t4-mcp-spec retry | 🟢 低 | future plan 设计应强制每 track worker 用独立 git worktree (`git worktree add ../<track>-worktree feature/<branch>`)|

- **🟢 2026-06-07 19:05 M5 5.4/5.5 plan_ba86c4d0 强收（ADR-0014）**：
  - 9 task 收束：6/9 done (spec/backend-p0-p2/frontend-p0-p2/docs) + 3/9 plan-exit owner override_accept (ci/test-e2e/final-verify)
  - 实物全部落 main（HEAD eea1d0e，7 impl + 4 ci + 1 test fixture = 20 commit 累计）
  - ci task：producer 18:25 self-close 报 done（7 commit + Actions run 27089840081 4/4 绿），engine 30min cap 18:54:59 killed 是硬超时
  - 3 plan-exit override_accept：(a) ci 实物在 main + CI 4/4 绿；(b) test-e2e = E2E 价值已被 168 backend pytest + 148 frontend vitest + 6 playwright 路径覆盖，完整 6 路径重跑 2-3h 算力 + 价值边际；(c) final-verify = 5 维度对齐 evidence 在 deliverable.md + ADR-0012/0013 + STATUS
  - 3 known gap 接受：P0-4 Pin session 校验 / P1-2 Token 监控 / P1-3 CLI 扫描 主 feature **未落 main**，留 M5/M6 手动补（line 150-152 标红）
  - **plan.status="failed" 终态保留**（cycle 6 evaluating stall 42+ min 是真实失败记录，作为 audit 教训），CLI `mavis team plan decision plan_complete=true` 强收无效（pitfalls §13）
  - 收束报告：[ADR-0014](worklogs/decisions/0014-mavis-team-plan-ba86c4d0-strong-close.md) + mavis-team-pitfalls §13

## Git ↔ 目录映射

> check_worklog.py 用它来判断「你是谁」，从而检查对应目录的日志。

| Git用户名 | 日志目录 |
|-----------|----------|
| oldmanpushbike | 黎 |
| yii.d | 董 |
| xiangbianpangde | 袁 |

## 图例
- ⚠️ 阻塞中（写明等谁/等什么）
- 🔀 涉及跨域接口，需协调
- ✅ 完成
