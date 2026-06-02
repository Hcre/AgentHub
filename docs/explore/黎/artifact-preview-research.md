# M4 产物预览与编辑 — 调研报告

> 调研时间: 2026-05-31
> 调研目标: 学习 open-design / open-codesign 等项目的 artifact 预览、内联编辑、Diff 视图、版本历史实现方式

## 调研项目

| 项目 | Stars | 许可 | 定位 |
|------|-------|------|------|
| [nexu-io/open-design](https://github.com/nexu-io/open-design) | ~40k | Apache 2.0 | Claude Design 开源替代，本地优先 |
| [OpenCoworkAI/open-codesign](https://github.com/OpenCoworkAI/open-codesign) | — | MIT | Electron 桌面应用，BYOK 多模型 |
| [AIO Hub Canvas](https://deepwiki.com/miaotouy/aio-hub) | — | — | Tauri + Monaco Editor 协作开发环境 |

---

## 一、沙盒预览 (iframe srcdoc)

### 核心模式

```html
<iframe
  sandbox="allow-scripts allow-same-origin"
  srcdoc="<完整的 HTML 内容>"
/>
```

**关键设计决策**:
- **`srcdoc` 而非 `src`**: 内容直接注入，不走网络请求，完全本地隔离
- **`sandbox` 白名单**: 只开 `allow-scripts`（CDN/字体/内联 script）+ `allow-same-origin`，阻止 cookie、localStorage、表单提交
- **独立 origin**: iframe 内部无法访问宿主 DOM/Cookie，安全由浏览器保证
- **Vendored runtime**: open-codesign 在 `packages/runtime` 打包 React 18 + Babel，离线运行 JSX 组件

### 流式渲染 (open-design 方式)

```
Agent stdout JSON-line stream
  → daemon 解析 text delta
  → SSE events 推送浏览器
  → 客户端逐 chunk 追加 iframe.srcdoc
  → 实时 typewriter 渐进渲染
```

### 预览池优化

open-codesign 保持最近 5 个设计的 iframe 在内存存活，切换零延迟。

---

## 二、内联预览卡片 → 全屏展开

```
Agent 回复包含 <artifact> 标记
  → MessageBubble 内渲染缩略卡片（sandbox iframe, ~300-400px 高）
  → 点击卡片 → Dialog/Sheet 全屏模式
  → 完整 iframe + 工具栏（设备切换 / 导出 / 评论 / 代码视图）
  → 可切换：预览模式 / 代码编辑模式
```

**卡片工具栏**: [预览] [代码] [下载] [全屏]
**全屏工具栏**: 设备切换 (Desktop/Tablet/Phone) + 导出 (HTML/PDF/PNG/ZIP) + 评论 + 版本历史

---

## 三、代码编辑器方案对比

| 方案 | 适用场景 | 代表项目 |
|------|---------|---------|
| Monaco Editor | 开发者向，完整代码补全/错误提示/diff | AIO Hub |
| Inspect + Comment Pin + Diff | 设计者向，轻量修改 | open-codesign |
| Files Panel (只读) | 产物查看 | open-design |

### Monaco Editor 集成要点 (AIO Hub)

- `@monaco-editor/react` 按需懒加载
- Agent 通过 `search/replace block` 协议修改代码：
  - `read_canvas_file` — 带行号读取
  - `apply_canvas_diff` — 搜索/替换块，先验证搜索块存在再应用
  - `write_canvas_file` — 完整覆盖
  - `commit_changes` — 写入磁盘 + Git commit
- Monaco diff editor 展示修改前/后对比

---

## 四、Diff 视图 / 版本历史

### open-design 方式

- 每次 Agent 修改生成 `<artifact>`，写入 `.od/projects/<id>/` 新版本文件
- JSONL 会话历史记录每条消息关联文件 hash
- 前端用 `diff2html` 渲染 side-by-side

### AIO Hub 方式 (内建 Git)

- 内建 Git service，每次 Agent 写入自动 commit
- commit message 关联对话轮次
- Monaco diff editor 渲染对比

### 对 AgentHub 的建议

**轻量方案 (M4)**:
- `artifact_versions` 表，每次修改存 JSON blob
- 前端 `diff2html` 或 Monaco diff editor 渲染

**完整方案 (P2)**:
- CLI working directory = git repo，直接用 git 管理版本
- 前端调 `GET /api/sessions/:id/artifacts/:id/versions` 获取历史

---

## 五、对话式局部修改

### 方式 A: DOM 定位 (适合 HTML 产物)

```
用户在预览 iframe 点击元素
  → data-codesign-id 定位 DOM 节点
  → 弹窗输入修改描述
  → 取该节点 HTML + 描述 → 构造 prompt
  → Agent 用 str_replace 修改源文件
  → 更新沙箱预览
```

### 方式 B: 代码选中 (适合通用产物)

```
用户在 Monaco Editor 选中代码行
  → 右键 "AI 修改" → 输入描述
  → prompt: "修改选中代码: ```{code}``` → {描述}"
  → Agent 返回 diff
  → Monaco diff editor 展示 → 用户确认/拒绝
```

---

## 六、对 AgentHub M4 的适配分析

### 已有能力

| 能力 | 位置 | 缺口 |
|------|------|------|
| 流式消息 (WS text/done) | `chat.py` → `chatStore.applyStreamEvent` | 无 `artifact` 事件类型 |
| Markdown 渲染 | `MessageBubble.tsx` react-markdown | 无 artifact 卡片 |
| 附件展示 | `MessageBubble.tsx` attachment block | 无 iframe 预览 |
| 文件浏览 | `WorkspaceBrowser` | 不支持预览 |
| `ToolResult.artifact` 字段 | `protocol.py:67` | 已预留未使用 |
| `OutputFile` 类型 | `types/index.ts` | 有 `OutputKind: 'doc'\|'diff'` |

### 推荐实施顺序

**Step 1 — Artifact 事件 + 内联卡片**
- `StreamEventType` 新增 `ARTIFACT`
- `StreamEvent` 新增 `artifact: { type, content, files }`
- `MessageBubble` 新增 `ArtifactCard`（缩略 iframe, 300px 高, 工具栏）

**Step 2 — 全屏预览 + 代码视图**
- `ArtifactPreviewModal`: Dialog fullscreen, 左侧文件树 + 右侧 iframe/Monaco
- Monaco Editor 按需懒加载 (`@monaco-editor/react`)

**Step 3 — P2 Diff + 版本历史**
- `artifact_versions` 表
- diff2html 或 Monaco diff editor

**Step 4 — P2 对话式局部修改**
- iframe postMessage 通信实现 DOM 定位
- 或 Monaco 选中 + 右键 AI 修改

### 技术选型

| 功能 | 推荐 | 理由 |
|------|------|------|
| 网页预览 | `iframe srcdoc` + `sandbox` | 浏览器原生，零依赖 |
| 代码编辑 | Monaco Editor | 成熟、diff 内置、按需加载 |
| Diff 视图 | Monaco diff editor | 与编辑器统一 |
| 文档渲染 | react-markdown (已有) | 复用 |
| 跨 iframe 通信 | `window.postMessage` | 标准 API |
| 版本存储 | `artifact_versions` 表 | 够用，不引入 git 复杂度 |
