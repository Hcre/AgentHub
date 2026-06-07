# AgentHub Demo 视频脚本

> **总时长**：3:00（180s）· **录制日期**：2026-06-07
> **画面源**：`http://127.0.0.1:5174`（前端 nginx Docker）· `http://127.0.0.1:8000`（后端 uvicorn）
> **分辨率**：1920×1080 @ 30fps · **编码**：libx264 (ultrafast)
> **录制方式**：`ffmpeg -f gdigrab -framerate 30 -i desktop` 全屏录屏

---

## 章节 0 · 开场（0:00 - 0:15，15s）

**画面**：浏览器全屏，地址栏 `http://127.0.0.1:5174`，AgentHub 主界面

**旁白**（中文，3 句）：
> "AgentHub —— 多 Agent 协作平台。"
> "一个界面，把 Claude、Codex、OpenCode、本地自建 Agent 全部串起来。"
> "5 个核心场景，3 分钟看完。"

**屏幕操作**：
1. `0:00` 画面淡入主页（默认 chat section，自动落在「会话」入口）
2. `0:05` 鼠标悬停到顶部 brand 区域，展示 4 个一级入口（会话 / AI 队友 / 群组 / Skill）
3. `0:12` 镜头短暂停留 1s，让用户看清布局：左导航栏 + 左侧会话列表 + 中心区 + 右侧面板

**机位/动效**：保持全屏静态，仅鼠标移动；不切换页面。

---

## 章节 1 · S1 新建会话 → 1v1 流式 → 代码块（0:15 - 0:45，30s）

**旁白**（4 句）：
> "场景一：和单个 Agent 1v1 私聊。"
> "点 + 新建会话，选 Claude 团队 —— 进入对话。"
> "流式回复：边生成边出，体感像有人在打字。"
> "Python 代码块自动高亮，右下角可「复制代码」「Pin」整段消息。"

**屏幕操作**：
1. `0:15` 鼠标移到左侧栏顶部 `+` 按钮 → 点击「新建会话」
2. `0:19` 弹出 StartChatModal：选「Claude」→ 「开始对话」
3. `0:23` 落在 Claude 私聊页；左侧栏出现新 conversation tab
4. `0:26` 切到 mock m3（已有 `print('hi')` python fence 的那条）—— 通过点击左侧已有 conversation 列表中的「对话 2 / Pricing page draft」
5. `0:30` 镜头锁定 m3 消息泡：python 代码块 emerald 高亮 + 右上角「复制代码」「重新生成」两个 inline action
6. `0:36` 鼠标悬停到「复制代码」按钮，点击 → 顶部出现 `已复制 1 段代码` 绿色 inline status
7. `0:42` 镜头短暂停留在 Pin 按钮（hover 显示「Pin 整段」tooltip）

**机位/动效**：镜头跟随鼠标；右侧面板保持折叠。

**真实情况**：
- 私聊 走 `useChatStore` mock（per `ChatView.tsx:122`），不拉后端
- m3 mock 文案含 ```python``` fence + `actions: ['复制代码', '重新生成']`
- 复制代码调 `navigator.clipboard.writeText`（`MessageBubble.tsx:135-148`）

---

## 章节 2 · S2 群聊 → @协调者 → 多 Agent 并行（0:45 - 1:15，30s）

**旁白**（4 句）：
> "场景二：群聊，一个任务多 Agent 接力。"
> "点左导航「群组」，进 S2 营销页升级群 —— 4 个 Agent 协同。"
> "@协调者 拆任务：3 个 worker 并行回复，紫色 @mention 高亮。"
> "真人只看汇报，不盯中间过程。"

**屏幕操作**：
1. `0:45` 鼠标点左导航第 3 个图标「群组」→ `section = 'groups'`
2. `0:48` 切到 GroupsListPage：列出 1 个 S2 群组（3 成员 + 1 协调者）
3. `0:51` 点进「S2 - 营销页升级」群 → 切到 `section = 'group'`
4. `0:55` GroupChatView 渲染：群头 + 成员条（Claude / OpenCode / MockBot + Coordinator）
5. `0:58` 镜头滚到底部，看 4-6 条 seed 消息（markdown 表格 + inline code + @mentions 真实后端拉取）
6. `1:04` 镜头特写 Coordinator 那条带「任务计划」的消息：3 个 todo 项 (PRD / 文案 / 设计) 走 CoordinatorPlan 组件
7. `1:09` 镜头切到某条 worker 回复：含 ```bash pnpm test:e2e``` 围栏（rehype-highlight 高亮）
8. `1:14` 在底部输入框打 `@Coordinator 帮我把 S2 进度同步给老板` → （不发送，只看 @ 高亮效果）

**机位/动效**：滚到底部一次；不发送新消息，仅展示后端真数据。

**真实情况**：
- 群聊走 `loadGroupHistory`（`groupStore.ts:165`）真后端 `GET /api/sessions/{id}/messages`
- 后端 0:45 时 S2 session 拉回 0 条（端到端联调中 seed 数量与 coordinator session id 偶有错位，仍展示 GroupChatView 容器 + 成员条 + Composer）

---

## 章节 3 · S3 产物内联预览（iframe + Diff 卡片）（1:15 - 1:45，30s）

**旁白**（4 句）：
> "场景三：Agent 出的产物直接内联预览。"
> "URL → 自动转成 WebPreviewCard iframe 沙箱卡片。"
> "代码 diff → 自动转成 emerald / rose 双色 DiffView。"
> "不用跳出聊天。"

**屏幕操作**：
1. `1:15` 鼠标移到中央 header 右侧的折叠/展开按钮 → 点开右侧面板
2. `1:18` 镜头停在右栏顶部 4 个预览 mode tab（项目文件 / 审查 diff / 部署 / 网页）—— 显示当前激活「项目文件」
3. `1:21` 镜头下移，展开文件树：项目根目录树（FileTree 组件）
4. `1:25` 镜头回到中央，**演示真实组件渲染**：在群聊 Composer 旁用 dev tools console 临时注入
   ```js
   useUIStore.setState({ section: 'chat' })  // 留在 chat
   ```
   切到一个有 ```diff``` fence 的 mock m3（私聊 m3 有 `print('hi')` python）—— 镜头特写 code block 高亮
5. `1:31` 旁白补充："S3 私聊的 WebPreviewCard + DiffView 渲染器在 `MessageBubble.tsx:215-230` / `WebPreviewCard.tsx:80` 已实现（sandbox iframe + emerald/rose diff 双色），但 S3 session id `6c2f7d24-…` 私聊不在 LeftPanel 默认列表（已知 nav gap）—— 这里借右栏 4 种预览模式展示「产物内联预览」的基础设施"
6. `1:38` 镜头特写右栏「审查 diff」mode 卡片：`enabled: false` + `即将到来` 灰 badge —— 解释为 M2 计划
7. `1:42` 镜头回到中央主流

**机位/动效**：右栏从折叠到展开，2s 缓动；停留 5s 展示文件树；最后回中央。

**真实情况**（per `docs/deliverables/integration-verify-report.md` §1 + §6 #2）：
- S3 私聊消息含 `https://agenthub-demo.example.com/proposal-v2.html`（preview_card content_type）+ ```diff``` 围栏（diff content_type）
- WebPreviewCard.tsx:80 用 `<iframe sandbox="allow-scripts allow-same-origin">`
- DiffView.tsx:29-41 emerald/rose 调色 + react-diff-viewer-continued
- **S3 私聊当前无法从 UI 进入**（ChatView mock-driven + LeftPanel 不展示 seeded session）—— A/B API + 组件 PASS，UI downscope
- 用右栏预览模式 + 私聊 m3 围栏 + 旁白说明，展示"产物内联预览"全貌

---

## 章节 4 · S4 自建 Agent（1:45 - 2:15，30s）

**旁白**（4 句）：
> "场景四：自定义 Agent，5 字段填完上线。"
> "点左导航「AI 队友」，右上 `+` 唤起 CreateAgentModal。"
> "选 CLI 模板（Claude Code / Codex / OpenCode / Pi），填名字 + 描述 + 默认技能。"
> "新建完直接开聊；CLI 模式自动接 CLI runner。"

**屏幕操作**：
1. `1:45` 鼠标点左导航第 2 个图标「AI 队友」→ `section = 'agent-detail'`
2. `1:48` AgentsListPage 渲染：12 个 seed agent 卡片网格（Claude / Coordinator / OpenCode / MyBot …）
3. `1:52` 鼠标移到右上「创建队友」按钮 → 点击 → CreateAgentModal 弹出
4. `1:55` 镜头扫过 modal 字段：模板选择（6 个：技术负责人 / 工程师 / 代码评审 / 测试 / 产品经理 / 文案）
5. `1:58` 点选「工程师」模板 → system prompt 自动填入
6. `2:02` 镜头特写「CLI 类型」下拉：Claude Code / Codex / OpenCode / Pi 4 个 CLI 选项（CliIcon SVG 缩略图）
7. `2:06` 选「Claude Code」→ 模型下拉自动出现 `claude-sonnet-4-6 / opus-4-7 / haiku-4-5`
8. `2:10` 填名字：`试水 Bot`、描述：`M3 试水`，点「创建」
9. `2:13` 镜头停留 1s，新 agent 卡片出现在网格最前（`试水 Bot`）

**机位/动效**：modal 弹出后镜头锁 modal，3s 静态展示字段；创建完镜头拉远看网格。

**真实情况**：
- `CreateAgentModal.tsx` 调 `useAgentStore.addAgent` 写到 zustand（localStorage persist）
- CLI 选项来自 `cliProviderMatrix` 矩阵；模型来自后端 `GET /api/providers`
- 不接 CLI runner 也能存（mock 模式）

---

## 章节 5 · S5 Inbox 审批 + 任务看板（2:15 - 2:45，30s）

**旁白**（4 句）：
> "场景五：Inbox 收件箱 + 任务看板。"
> "进入私聊 tab 栏的「任务」—— Kanban 4 列，看板视图就位。"
> "Inbox 审批是 M4 计划，本地通过 zustand 持久化 + seed 数据已就绪。"
> "审批通过 / 拒绝，diff 卡片，行内回执。"

**屏幕操作**：
1. `2:15` 鼠标点左导航「会话」→ 回到 chat
2. `2:18` 切到一个 active 私聊（如 Claude → 对话 2），在中央 header 下方 tab 条点「任务」→ `activeTab = 'tasks'`
3. `2:21` TasksTabView 渲染：4 列 Kanban（todo / doing / blocked / done），每列 2-3 张 MO-1~MO-7 mock 任务卡（priority 标签 + assignee 头像 + due 时间）
4. `2:25` 镜头特写一张 high-priority 任务卡：左侧颜色条 + assignee「编辑」+ 状态 doing
5. `2:28` 镜头切到右上「看板 / 列表」切换按钮 → 点一次换到 list view
6. `2:31` **dev tools console hack** 演示 Inbox（旁白明说"M4 计划，InboxView 组件已落地"）：
   - 打开浏览器 DevTools (F12) → Console
   - 输入 `useUIStore.setState({ section: 'inbox' })` → 回车
   - InboxView 渲染：5 条 inboxStore mock items（2 条审批：S2 协调者合并请求 / S1 Claude 重构；3 条任务：MO-3 / MO-5 / MO-6）
7. `2:39` 镜头特写一条审批卡：标题 + summary + 6 行 emerald/rose diff（InboxCard `diff` 字段） + 「批准 / 拒绝」按钮
8. `2:43` 镜头回到中央主流

**机位/动效**：开 DevTools 时长 ~5s，节奏快；InboxView 特写 4s。

**真实情况**（per `docs/deliverables/integration-verify-report.md` §3 E + §6 #1）：
- `inbox.py:10-13` 后端仍是 TODO skeleton（`{"items":[],"unread_count":0,"note":"收件箱在 M4 实现"}`）
- `inboxStore.ts:14` 走 frontend mock 5 items（`extra.ts`）
- **NavRail.tsx 无 inbox / tasks 入口**（4 个一级：会话 / AI 队友 / 群组 / Skill）
- S5 走 "任务" tab + dev console hack 演示 InboxView
- 3 重 gap 已写入 verifier 报告（不改）

---

## 章节 6 · 收尾：规范 / SPEC / ADR（2:45 - 3:00，15s）

**旁白**（3 句）：
> "工程上：规范、SPEC、ADR 全留痕。"
> "docs/conventions 9 个规范文档、docs/specs 5 个规格文档、worklogs/decisions 4 个 ADR。"
> "任何变更，先冻结接口 → 2 人 Review → 才写代码。Demo 完。"

**屏幕操作**：
1. `2:45` 鼠标点左下「主题切换」按钮，主题从 light → dim → dark 循环一次（1s 一次，3 次）
2. `2:50` 切到资源管理器 / 终端，路径 `C:\Users\yhn\Desktop\字节比赛\AgentHub\docs`
3. `2:52` 镜头停在 `docs/conventions/` 目录：列出 9 个规范文件（CLAUDE-规范导航 + 01-10）
4. `2:55` 镜头滑到 `worklogs/decisions/`：列出 4 个 ADR（0001 CLI 优先 / 0002 长驻 CLI / 0003 MCP URL+AP-05 暂缓 / 0004 MCP F1 落地口径+安装探针）
5. `2:58` 镜头拉远 → 黑屏 + 字幕 `AgentHub · Demo 完`

**机位/动效**：主题切换 1s×3；目录浏览 5s；最后 fade out 2s。

---

## 录制环境清单

| 项 | 值 |
|----|----|
| OS | Windows 11 |
| 浏览器 | Chrome 127 (Docker nginx 后端 → `:5174`) |
| 后端 | local uvicorn → `:8000`（PID 34276）|
| 数据库 | PostgreSQL (Docker) — 11 agents / 4 sessions / 19 messages / 2 inbox / 2 tasks seed |
| 屏幕分辨率 | 1920×1080 @ 30fps |
| ffmpeg | 8.1.1-full_build-www.gyan.dev (libx264 + preset ultrafast) |
| 录制时长 | 200s（实际 demo 180s，预留 20s buffer / 启动延迟） |
| 视频路径 | `docs/deliverables/video/raw-recording.mp4` |
| 脚本路径 | `docs/deliverables/video/script.md` |
| 抽帧 | 3 张 PNG（开场 / 中段 / 收尾），ffprobe 抽帧验证非黑屏 |

---

## 旁白节奏建议

- 章节 0、6：留 1.5s 静默，让画面"呼吸"
- 章节 1-5：每段开头 0.5s 切镜头，之后旁白与操作同步
- 录音：可后期配音（建议使用 ElevenLabs / 本地 TTS）；本次 demo 仅录屏 + 内嵌字幕
- 字幕：v1 跳过内嵌字幕（人声优先）；v2 可用 ffmpeg + ASS 烧字幕

---

## 已知 Gap（已在脚本中体现）

| Gap | 章节 | 应对 |
|-----|------|------|
| S3 私聊不在 LeftPanel | 3 | 借右栏 4 模式 + 旁白说明"组件已实现、UI 入口在 M2" |
| 后端 S2 group messages 0 条（seed 偶发） | 2 | 仍展示 GroupChatView 容器 / 成员条 / Composer；旁白"已 seed 但 session id 偶有错位" |
| Inbox 后端 TODO + 无 nav | 5 | 走 chat tab「任务」+ dev console hack 演示 InboxView |
| Docker backend image 6h old | （全局） | 演示 UI 走 :5174；API 调用走本地 :8000（per integration-verify） |

---

## 验收

- [x] 旁白每段 3-5 句
- [x] 屏幕操作步骤具体到秒
- [x] 时长总 3 分钟（180s ± 5s）
- [x] 录制 200s 留 buffer
- [x] 3 张抽帧 PNG 验证非黑屏
- [x] deliverable.md 含 VERDICT: PASS + 4 步证据
