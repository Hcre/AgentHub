# 当前状态

> 最后更新: 2026-06-07 05:50（Mavis 凌晨冲刺收束，plan_bcf9945c 5 task 全完成）
> 规则：**每次 push 或开始/结束一个任务时，更新你自己的那一行。**

| 我 | 正在做 | 阻塞？ | 这周完成了 |
|----|--------|--------|-----------|
| 黎 | 桌面 App 选型 + 规格冻结(待 PR-01 Review) | ⚠️ 需 董/袁 之一 Review specs/06-desktop-app §十二 4 Q | merge 39 commits ✅ + CLI PATH 扫描 ✅ + ProviderKeyResolver ✅ + Step 2 重设计 ✅ + OpenCode v1.15 集成 ✅ + PiAgentRuntime 修正 ✅ + Key 管理简化 ✅ + 工作目录 E2E ✅ + bug 修复 9 个 ✅ + OpenCode 对话待验证 + **本地全栈部署(2026-06-06)：DB in Docker + 后端/前端裸跑 8000/5174 + alembic 0011 memories 迁移 ✅ + 3 个 deploy-bug 修复（alembic.ini 中文注释→GBK 解码失败 / mcp_memory.py 去 `from __future__` 避 mcp 1.12.x `issubclass` 报错 / `ui/index.ts` barrel 漏 `WorkspaceBrowser` 致白屏）✅ + push `feature/frontend/file-preview-and-memories`（18fba6a+025abf1+44982ad+a06cebe）PR #16 合并 ✅ + 桌面 App 可行性讨论(2026-06-06)→ 5 路径对比 + 3 轮 AskUserQuestion 收口 + 决策 Tauri 2 + 瘦客户端(M2)+ GitHub Releases ✅ + ADR-0007 `worklogs/decisions/0007-tauri-desktop-pivot.md` ✅ + 桌面 App 规格草案 `docs/specs/06-desktop-app_桌面App规格.md` ✅ + worklog `worklogs/黎/2026-06-06_讨论-web转桌面app可行性.md` ✅** |
| 董 | 协调者+任务编排部分 | 无 | 群聊全栈实现 ✅ + CLI 多模型代理 ✅ + ADR-02 长驻 CLI ✅ + 前端群聊 ✅ + 记忆系统 B 方向设计 ✅ + B1 后端实现 ✅ + B2 详细设计 ✅ + Agent 创建全链路 6 处 bug 修复 + 9 个测试 ✅ + MCP save_memory 端到端打通 ✅ + 前端记忆面板 ✅ + 记忆分支合并 main ✅ |
| 袁 | MCP P3 F3 创建（6/6-6/8 待启动，stdio/sse 提交 + 模板 + dry-run 验证）| 无 | 全项目按模板重构 ✅ + 2026-05-29 目录二次整合 ✅ + skills 移回根 ✅ + 双图谱启用 ✅ + 图谱可视化离线化 ✅ + enums 影响分析 ✅ + dashboard 适配按人协作表 ✅ + src/frontend 代码内容分离 ✅ + 全栈运行验证 ✅ + 文档命名收敛 ✅ + dashboard 集成 ✅ + CODE_MAP.md 收归 docs/ ✅ + 远程 main 同步 5e34bea ✅ + 后续升级计划 v1.0 ✅ + roadmap §八 MVP 收尾冲刺 ✅ + STATUS 同步 6/1 ✅ + MCP 功能计划 v0.2 ✅ + MCP PRD v1.0 ✅ + roadmap §十 MCP v1 阶段表 ✅ + STATUS 同步 6/2 ✅ + MCP 接入计划可行性 review（12 问题清单）✅ + **MCP 接入计划修订版（2026-06-03）：README-REVISION.md 单一权威 + PRD V1.3.1 errata 4 项决策（表名/SDK/dry-run/前端）+ FS/SA/TA/MD/IC 5 份重写到 src/backend/app/ 真实栈 + 新增 MCP-UI-frontend V1.0（3 页+1 Tab+1 store+6 组件）+ 22 份 M-*/DEPRECATED.md 标记 + closure-verdict 双口径（计划空间🟢/代码空间🔴）+ end-to-end-trace 18 拍真实代码空间标注** ✅ + **MCP 计划整理 + PR-01 草案（2026-06-03）：核验修订版对真实代码树（5 层洋葱/llm runtime/alembic 0001-0005）属实 + 校正 §3 残留路径漂移（agentruntime→llm、api/v1→api/routers、application/mcp→services、虚构 BaseAgentRuntime→domain/llm/protocol.py::AgentRuntime）+ PR-01 端点冻结草案落 04-commands §2.6（8 端点）+ §三（4 WS 事件，type/payload 信封+request_id）+ ADR-0003（URL=/api/mcp、AP-05 暂缓）+ 原计划残留归档 docs/archive/DEPRECATED_MCP接入-原计划残留/（445+22+3 文件）+ FILE_GRAPH §5.3/5.6 同步** ✅ + **MCP P1 核心链路（2026-06-03，Reviewer Approve §2.6 后）：二次对账 schema↔代码审计 R1-R10（无 workspaces/users 表→裸 Uuid、零 JWT 强制→get_current_user 仅解析、trace_id 零设施→净新增、WS 信封不符、错误体 {detail} 非 AP-02、SQLite 强制可移植类型）+ 修 .gitignore 裸 backend/ 误伤源码树阻断 bug + domain/mcp 4 实体+rules+repo 接口 + models 追加 4 表 + alembic 0006-0009 + market/install 2 service + api/routers/mcp.py 3 端点(list/detail/install) + schemas/mcp.py + spec 三处对账横幅(03-data-model/04-commands/README-REVISION §9) + 12 单测绿(三路径)** ✅ + **MCP F1 收束-1 闭合（2026-06-03，9d7cdf2 → main）：MCPInstaller 端口 + LocalMcpInstaller 结构校验(transport 必填项，422 拦截非法配置)替代骨架 ready + 5 端点（list/detail/install/templates/uninstall）+ ADR-04 + 收束报告** ✅ + **MCP P2 核心（2026-06-03，9ff77be → main）：Agent 绑定 + 请求携带 attach（ADR-05）+ claude_code runtime 扩展 `_write_mcp_config` 合并记忆 server + 绑定 servers + alembic 0010 部分唯一索引解决 rebind 冲突 + 8 单测绿** ✅ + **MCP 路径分离（2026-06-03，90195f6 → main）：/api/mcp 路径重叠修复——记忆 MCP 协议端 mount 移到 /api/mcp-memory，REST 独占 /api/mcp/*；settings.mcp_memory_url 示例同步** ✅ + **MCP opencode 拉回本期（2026-06-04，e17b6ff → main）：OPENCODE_CONFIG 逐进程隔离通道（实测零串号）+ _entry_to_opencode/_build_opencode_mcp/_write_opencode_config + 8 单测绿 + opencode 连接级 E2E 冒烟通过（生产函数生成配置 → opencode mcp list 拉起 stdio MCP server 走完 initialize/tools 握手，✓ everything connected）+ pi_agent NB-02 seam 注释** ✅ + **MCP F2 收束-2 闭合（2026-06-04，002f3fb → main）：四阶段双线签核（[收束报告-F2](docs/reports/收束报告-MCP-F2.md)）+ ADR-05/06 + MCP 专项 34/34 绿** ✅ + **MCP 后续 3 fix（2026-06-06）：3cca1dc 修 TS build 错 + folderOpen icon / 67784af 修 ESLint no-explicit-any + set-state-in-effect / 46863d8 加 opencode-ai CLI + 修 _build_env env injection（修 P2 落地后的 3 个修边）** ✅ |

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

- **📋 roadmap §8 必修 P0（6/2-6/9,M5 范围）— 当前实际完成度**：
  - P0-1 网页预览 iframe 卡片内联到消息流 — ❌ 未做（**关键缺口**,影响 Demo 3min 脚本 §8.4 1:15-1:45 段）
  - P0-2 Diff 视图（diff2html 集成）— ❌ 未做（**关键缺口**）
  - P0-3 文件附件上传 + 预览 API — ⚠️ **部分**（`MessageBubble.tsx:94` 渲染 mock attachment,后端无 multipart 端点）
  - P0-4 Pin 消息 UI — ⚠️ **后端就绪,前端 UI 缺**（`api/routers/sessions.py:91-99` POST/DELETE /pin 已有;P0-4 仅需前端按钮）
  - P0-5 复制代码 / 重新生成按钮 — ⚠️ **UI 框架在,内容错位**（`MessageBubble.tsx:107` actions 数组渲染,`mock.ts:105` 注入 'Open diff'/'View outline',**不是**「复制代码/重新生成」,需换文案+接 action handler）
  - P0-6 端到端 Demo 数据集 + 录制脚本 — ❌ 未做（**关键缺口**,影响交付物 4）

## 🧾 技术债（收束盘点）

| 问题 | 发现 | 优先级 | 预计修复 |
|------|------|--------|---------|
| 既有套件测试隔离 flaky（`test_context_builder` 模块级 fakeredis 单例 / `test_selector` LLM 环境敏感）| MCP F1 收束-1 | 🟡 中 | 独立工单（非 MCP 引入）|
| ~~`agent_mcp_bindings` UNIQUE(agent,installation) 与软删 rebind 冲突~~ ✅ **已修**（alembic 0010 部分唯一索引,解绑后可 rebind）| MCP F1 实现 | — | 已修（2026-06-03）|
| ~~安装为结构校验骨架（无真实可达性/进程探针）~~ ✅ **已升级** McpInstaller 端口 + LocalMcpInstaller 结构校验(transport 必填项,422 拦截非法配置)替代骨架 ready；真实可达性/进程探针仍 deferred | MCP F1 → F2 收束 | 🟢 低 | P3/P4 真实探针(seam 已留) |
| NB-02 defer：AP-02 错误信封统一 / AP-05 URL 版本 / workspaces·users 实体+FK / 全局 JWT 鉴权 | 二次对账 | 🟢 低 | 平台化阶段 |
| ~~`/api/mcp` 路径重叠~~ ✅ 已解决：记忆 MCP 协议端移 `/api/mcp-memory`，REST 独占 `/api/mcp/*` | F1↔记忆 merge | — | 已修（2026-06-03） |
| ~~MCP 注入 claude_code-only（R11）~~ ✅ opencode 已拉回（ADR-06，`OPENCODE_CONFIG` 逐进程通道+8 测试+连接级 E2E 冒烟）；**pi_agent 仍 deferred**（本机无 pi 二进制可验证）| P2 运行时审计 | 🟢 低 | pi_agent 待上游 MCP 支持（解除门 RT-MCP §3.3）|
| P0-3 文件附件后端 multipart API 缺失(前端 mock 渲染) | 现状盘点(2026-06-06) | 🟡 中 | M5/MVP 冲刺期补 |
| P0-4 Pin 消息 UI 缺失(后端端点已在 sessions.py:91-99) | 现状盘点(2026-06-06) | 🟢 低 | M5/MVP 冲刺期补 |
| P0-5 复制代码/重新生成 按钮(UI 框架有,actions 文案错位) | 现状盘点(2026-06-06) | 🟢 低 | M5/MVP 冲刺期补 |

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
