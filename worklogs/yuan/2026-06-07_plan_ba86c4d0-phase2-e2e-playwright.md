# Phase 2 cu + Playwright 联合 E2E F5-F10 (2026-06-07 21:35-21:55)

owner: 袁 (xiangbianpangde) · executor: Mavis · branch: `main` · 续 phase2-e2e-cu.md

## 上下文
Phase 1 (代码验证 + 3 阻塞修复) 完成后，21:30 user 喊继续 F5-F10，cu MCP 焦点漂移无法切回 Chrome，user 21:35 同意切 Playwright MCP 配合。

## 工具组合
- **cu MCP** — 真实桌面截图 (最初用, 焦点漂移)
- **Playwright MCP** — Chrome 自动化 (21:35 切换后主力, 解决了焦点问题)
- 浏览器：`http://127.0.0.1:5174/` (Docker compose 5174→5173, vite proxy → 18000→8000 backend)

## F5 — hover 消息 actions (Pin / 复制 / 回复 / 引用) — 部分通过
**实测结果**：

| Action | 是否在 hover 显示 | 实际点击效果 |
|--------|------------------|-------------|
| 置顶 (Pin) | ✅ 5 消息都有 | ❌ **API 401 Unauthorized** — UI 立刻弹 "Pin 失败 / API 401" alert |
| 回复 (Reply) | ✅ 5 消息都有 | ✅ 完全工作 — 进 reply mode, 显示 quote badge "回复 Coordinator", 取消按钮 OK |
| 复制代码 | ⚠️ 仅在 msg.actions 包含 "复制代码" 时显示 (Claude S2/OpenCode S2/MockBot S2 无 actions 不显示, 用户 md 消息有 6 段含 python code block 自动出现) | ✅ 点击后 "已复制 N 段代码" inline 显示 (P0-5) |
| 引用 | ❌ **未实现 hover 按钮** — "引文小气泡" 只在收到 replyTo 的消息上 render (展示, 非按钮) |

**Bug 1 重大发现**：`/api/messages/{id}/pin?session_id=...` 返回 401，需要修复
- Console: `[ERROR] Failed to load resource: status 401 @ .../api/messages/97a83bf5.../pin?session_id=d0583dfd...`
- Console: `[GroupMessageItem] pin toggle failed: API 401`
- Pin 按钮被 GroupMessageItem.tsx:144 报失败, 落 `data-testid="pin-error"` alert

证据: 截图 `agenthub_f5_hover.png` (S2 群组 6 消息, hover 用户消息顶部显示 📌/↩ 2 个图标)

## F6 — 文档渲染 3-mode — 完全通过
**实测**：Composer 输入多段 markdown (heading 2 / bold / italic / list / inline code / code block / link / blockquote) → Enter 发送。

渲染结果 (snapshot ref):
- `heading "标题二" [level=2] [ref=e505]`
- `strong [ref=e507]: 加粗` / `emphasis [ref=e508]: 斜体`
- `list [ref=e509]` + `listitem [ref=e510, e511]`
- `code [ref=e513]: "\`inline code\`"`
- `code [ref=e515]: "def hello(): print(\"Hello World\")"`
- `link "链接" [ref=e517] [cursor=pointer] /url: https://example.com`
- `blockquote [ref=e518]`
- 额外：`button "复制代码" [ref=e521]` 自动出现 (msg.actions 检测到代码)

8 段全部正确渲染, F6 ✅ 完全工作。

## F7 — 全屏预览 (P1-3) — 代码存在, 触发路径未触达
**状态**：WebPreviewCard 组件 + fullscreen-btn + Dialog 90vh 全部实现 (单元测试 `WebPreviewCard.fullscreen.test.tsx` 覆盖 3 路径)。

**实测**：
- 右下 "新建预览" 按钮 (e87) → 弹 menu, 4 项: 项目文件 / 审查 diff(即将到来) / 部署(即将到来) / 网页(即将到来)
- 项目文件 = 现有 "文件" tab, 显示 "暂无工作目录"
- **无法触达 WebPreviewCard 完整屏**, 因为 mock agent 不发 URL (msg.urls 仅 agent 消息携带, user 消息不会触发)

**结论**：F7 代码层 ✅ 完整, E2E 触发依赖真 URL 注入, 当前 backend mock 数据不产生 URL, 此项已尽 E2E 能力极限。生产环境需真 CLI agent 发 URL 才能完整 E2E 验证。

## F8 — Monaco 编辑器 (P2-1) — 完全通过
**实测**：进入 技术负责人 私聊 (Modal: 会话名"对话 1" + 发起) → Composer 工具栏 5 按钮 (附件/B/</>/表情/@), 点 `</>` (testid=composer-code-toggle, e1036)

效果 (snapshot):
- `combobox "选择语言" [ref=e1076]` — 右上角 TypeScript 切换
- `textbox "Editor content" [ref=e1095]` — Monaco 编辑区
- `generic [ref=e1098]: "1"` — 行号
- 顶部: "代码模式 · 发送时自动包 ` ```typescript ... ``` `"
- 点击 ↩ "切回普通文本" 按钮 (e1093, testid=composer-code-toggle 同) 切回

证据: 截图 `agenthub_f8_monaco.png` (TypeScript Monaco 编辑区, 行号 1, 语言切换)
F8 ✅ 完整工作。

## F9 — 部署卡 (P2-2) — 代码完整, E2E 未触发
**状态**：DeployCard 组件 + 3 路径 (ready / building / failed) + testid 钉死 (data-testid=deploy-card / deploy-url / deploy-open-btn / deploy-progress / deploy-error-code) (单元测试 `MessageBubble.deploy.test.tsx` 3 case 全过)。

**实测**：私聊发"请帮我部署这个项目到 staging 环境" → 消息成功发出, agent 状态"正在输入..." 持续 30+ 秒不返回 (Claude Code 真 CLI 走 orchestrator → deploy.py:81 已修, 但实际调用链需要 LLM 决定调用 tool)。

**结论**：F9 实现层 ✅ 完整 (3 路径单测过), E2E 触发依赖真 LLM tool call / mock 注入, 不是 UI 问题。

## F10 — 移动 H5 (P2-4) — **未实现 (确认 STATUS [pending])**
**实测**：Playwright `browser_resize` width=768, height=1024 → 截图 `agenthub_f10_mobile.png`

结果：4 面板 (NavRail / LeftPanel / ChatArea / RightPanel) **仍然并排显示**, 无 hamburger menu, 无 panel 折叠, 无 stack 重排。Composer "设置工作目录" 按钮位置重叠。

**代码确认**：
- 全项目 grep `useMediaQuery / isMobile / max-width / sm:hidden / md:block` 只在 6 处 page 内部 grid 用了 `sm:grid-cols-N` (group 列表 / agent 列表 / skill 列表 / coordinator plan), 都不影响主 4 栏 shell
- 无 `useMediaQuery` hook
- 无 mobile-specific layout 组件

F10 ❌ **未实现**, 与 STATUS 标 "P2-4 移动 H5 [pending]" 一致。

## 总结
| F | 功能 | 状态 | 备注 |
|---|------|------|------|
| F1-F4 | Phase 2 已完成 | ✅ (之前 worklog) | — |
| F5 | hover actions | ⚠️ Pin API 401 bug, Reply ✅, 复制 ✅ (条件), 引用未实现 | **需修 Pin API** |
| F6 | 文档渲染 | ✅ 8 段全对 | — |
| F7 | 全屏预览 | ⚠️ 代码 ✅, E2E 需真 URL | — |
| F8 | Monaco | ✅ 完整工作 | — |
| F9 | 部署卡 | ⚠️ 代码 ✅ 3 路径, E2E 需真 LLM tool call | — |
| F10 | 移动 H5 | ❌ **未实现** | 4 栏不响应, 确认 [pending] |

## 工具坑 (新增)
- `mavis mcp call <srv> <tool> '{...}'` PowerShell 单引号 + 中文 + JSON 注入会导致 Invalid JSON, **必须用 `--file args.json`** 方式
- Playwright `browser_press_key` schema 用 `{"key": "Enter"}` 不是 `{"combo": "alt+Tab"}` (cu 用 combo, playwright 用 key)
- Playwright `browser_navigate` URL 用 `http://127.0.0.1:5174/` (不是 localhost, 避免 IPv6)
- Monaco editor 是 `div role="textbox"`, Playwright `browser_type` 报 "Element is not an input" — 用 `fill` 也不行, 需要在 Monaco 模式用 keyboard.type 或在外部切换

## 后续
1. **修 Pin API 401** (重要 bug) — 检查 backend `/api/messages/{id}/pin` 路由 + 认证
2. STATUS §5.4 F10 [pending] 已确认准确, 不需改
3. F7/F9 代码层 OK, 后续如需 E2E 需 mock 注入 msg.urls / msg.deploy

## 截图证据 (4 张)
- `C:\Users\yhn\agenthub_f5_hover.png` — S2 群组 6 消息, hover 显示 📌/↩
- `C:\Users\yhn\agenthub_f8_monaco.png` — 私聊 Monaco TypeScript 模式
- `C:\Users\yhn\agenthub_f10_mobile.png` — 768px 移动端 (未响应)
- (F6 用 snapshot yaml 替代, 8 段 markdown 全 render ref)

## push
未 commit, 待 user review 后一并 commit+push
