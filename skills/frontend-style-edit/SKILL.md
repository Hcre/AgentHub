---
name: frontend-style-edit
description: 前端风格保持型修改 — 接收「截图 + 功能描述 + 界面布局」三件套，定位应修改的文件位置，强制复用现有 UI 原子层与设计 token，避免功能位置漂移与风格不一致。Use when the user provides a screenshot, feature description and layout sketch, and asks to add/modify/migrate an AgentHub frontend page or component.
---

# frontend-style-edit: 风格保持型前端修改

> **核心目标**：用户给**功能描述**（+ 可选的截图/布局/位置）→ **先 grep 找现有同类** → **默认改既有**而非新建 → 复用已有设计系统产出 diff。
> **默认行为**：找不到落点 → 主动搜 + 列候选让用户选；输入不全 → 跑 grep 推断后**直接给方案**而不是卡住等问。
> **对应七重天层级**：L2（注入设计知识）+ L4（以已有组件为模板克隆）——跳过 L1/L3 自由发挥。

---

## 一、适用时机

| 场景 | 触发词举例 |
|------|-----------|
| 新建前端页面 / Modal / 详情页 | "做个 XXX 页面"、"加个 XXX 弹窗" |
| 迁移 / 重构既有功能 | "把 XXX 从 A 挪到 B"、"重构 XXX" |
| 调整 UI 但保持整体风格 | "改一下 XXX 的样式"、"让 XXX 更好看" |
| 对齐某个参考图 | "做成这个截图的样子" |

**不适用的场景**（应改用其他 skill / 直接对话）：
- 纯后端逻辑、API、数据模型 → 走 `skills/feat-start/`
- 改 backend 配套前端 → 走 `skills/feat-start/` 后由本 skill 处理 UI 部分
- 复杂跨域架构变更 → 走 `skills/spec-driven-development/` 先写 spec

---

## 二、输入契约（宽松）

> **唯一必填**是**功能描述**。其他都可选，缺了 skill 主动补。

| # | 输入 | 必填 | 用途 | 缺失时 skill 的处理 |
|---|------|------|------|------------------|
| 1 | **功能描述** | ✓ **必填** | 这一页/组件做什么、给谁用 | — |
| 2 | **截图** | ✗ 可选 | 版式/层级/尺寸参考；**颜色仅作深浅判断** | 跳过视觉解码，**用文字描述+现有同类推断**布局 |
| 3 | **界面布局** | ✗ 可选 | 元素清单：分几个区/每区放什么 | 缺则**先看现有同类组件怎么布局，照葫芦画瓢**；实在不同时再问 1 个澄清问题 |
| 4 | **改动范围** | ✗ 可选 | 新建 / 改既有 / 从 X 迁到 Y | **默认"改既有"**：先 grep 找同类，找到就改它；找不到再列 2-3 个候选让用户选 |
| 5 | **文件位置** | ✗ 可选 | 已知改哪个文件 | 缺则**必跑 grep**，skill 自己定位；定位后告知用户，等确认 |
| 6 | **参考图来源** | ✗ 可选 | "做成 X 网站的样子" | 有截图则参考；纯文字则按本 skill 内置设计系统走 |

**反例输入**（**不直接拒绝**，而是先 grep 推断再问最关键的问题）：
- "加个好看点的页面" ← 描述模糊 → grep 同类 + 问"参考哪类现有页面？"
- "按公司设计规范做" ← 内部规范无指向 → 默认走本 skill 内置设计系统；如指 `skills/a社规范/` 则交叉参考
- "把 xxx 改一下" ← 改什么没说清 → grep 找 `xxx` 的现有实现，问"改哪里：颜色/布局/交互/数据？"

---

## 三、设计系统必读（已就位，禁止另造）

### 3.1 UI 原子层（`src/frontend/src/components/ui/`）

> **强制规则**：新页面/组件必须**优先**从下表选用，且**不要**自造同名组件。

| 组件 | 变体/Props | 何时用 |
|------|-----------|--------|
| `Avatar` | `initial`/`color`（brand/neutral/sage/clay/rose/blue）/`size`/`online` | 头像、用户/Agent 标识 |
| `Badge` | variant: default/secondary/outline/brand/success/warning/destructive | 标签、状态 |
| `Button` | variant: default/brand/secondary/outline/ghost/destructive/link · size: default/sm/lg/icon/iconSm | 所有按钮 |
| `Card` + `CardHeader`/`CardTitle`/`CardDescription`/`CardContent` | 容器 | 内容卡片 |
| `ContextMenu` | items: `{icon, label, danger?, onClick}[]` | 右键菜单 |
| `Dialog` + `DialogContent` | open/onOpenChange | 弹窗 |
| `Icon` | name: `IconName`（lucide-react 子集，统一入口） | 所有图标（**不要**直接 import lucide） |
| `Input` | 标准 `<input>` Props | 文本输入 |
| `Kbd` | children | 快捷键提示 |
| `Separator` | orientation: horizontal/vertical | 分隔线 |
| `Tabs` + `TabsList` + `TabsTrigger` | 受控 value/onValueChange | 标签页 |
| `Textarea` | 标准 `<textarea>` Props | 多行输入 |
| `WorkspaceBrowser` | （未在 index 导出，按需 import 路径） | 工作区浏览 |

> ⚠️ 引入新 UI 库 / 新的 icon 集 / 新的颜色 token = **红名单**（见 §六）。

### 3.2 设计 token（`src/frontend/src/styles/index.css`）

> **强制规则**：所有颜色/间距/字号/动画**必须**走 token，不允许 hex / px 硬编码。

**主题（4 个，叠加 4 个 accent = 16 组合）：**

| 主题 | 触发方式 | 主要 token |
|------|---------|-----------|
| 浅色 | `<html>` 默认 | `--background 36 36% 87%`、`--foreground 30 24% 9%` |
| 暗色 | `<html class="dark">` | `--background 28 14% 10%`、`--foreground 36 38% 92%` |
| 柔暗 | `<html class="dim">` | `--background 30 10% 18%`、`--foreground 36 24% 90%` |
| Accent | 由 `theme.ts#applyTweaks` 写入 `<html style>` | `--brand`、`--brand-deep`、`--brand-soft` |

Accent 可选：`coral`（珊瑚 / 默认）/ `blue`（靛蓝）/ `sage`（鼠尾草）/ `plum`（梅）。

**色板（最常用，对应 Tailwind 工具类）：**

| 工具类 | 用途 |
|--------|------|
| `bg-background` / `text-foreground` | 页面底色 / 主文本 |
| `bg-card` / `text-card-foreground` | 卡片容器 |
| `bg-muted` / `text-muted-foreground` | 弱化背景 / 次要文本 |
| `bg-popover` | 弹出层底 |
| `border-border` / `border-input` | 描边 |
| `bg-primary` / `text-primary-foreground` | 主操作 |
| `bg-secondary` / `text-secondary-foreground` | 次操作 |
| `bg-accent` / `text-accent-foreground` | 强调 / 悬停 |
| `bg-destructive` / `text-destructive-foreground` | 危险 |
| `bg-brand` / `text-brand-foreground` / `bg-brand-soft` / `bg-brand-deep` | 品牌强调（accent 派生） |
| `ring-ring` | 焦点环 |

**磨砂玻璃工具类：**

| 工具类 | 用途 |
|--------|------|
| `.glass-panel` | 通用面板（透明度 0.66） |
| `.glass-strong` | 弹层/侧栏（0.82） |
| `.glass-soft` | 悬浮卡片（0.50） |

**动效 token（Tailwind `animate-[var(--animate-...)]`）：**

| token | 时长 | 用途 |
|-------|------|------|
| `--animate-fade-in` | 0.3s | 入场淡入 |
| `--animate-slide-in` | 0.25s | 弹层/抽屉 |

**密度（紧凑模式）：** `data-density="compact"` 由 `theme.ts#applyTweaks` 写入。

**字体：** 标题走 `var(--ah-head-font)`（4 种可选：Geist / Source Serif 4 / Instrument Serif / IBM Plex Sans），正文 `Geist`。

### 3.3 业务模块约定（按域分子目录）

```
src/frontend/src/components/
├── ui/         ← 原子层（§3.1）
├── layout/     ← AppShell + Left/Center/Right
├── chat/       ← ChatView, Composer, MessageBubble, ConversationTabs
├── group/      ← 群聊：GroupChatView, GroupComposer, GroupMembersStrip, CoordinatorPlan
├── agent/      ← AgentDetailPage, CreateAgentModal, CustomAgentModal
├── inbox/      ← InboxView
├── tasks/      ← TasksTabView, TaskCard, TaskFilterBar, CreateTaskModal
├── memory/     ← MemoryPanel
├── calendar/   ← CalendarView
├── activity/   ← ActivityFeed
├── settings/   ← ApiKeyManager
├── skills/     ← SkillMarketplacePage
├── tweaks/     ← TweaksPanel
└── views/      ← TabViews
```

**强制规则**：新增/迁移功能**必须**落到上述对应域子目录；禁止创建 `pages/`, `v2/`, `new/`, `temp/` 之类游离目录。

### 3.4 状态 / 数据 / 工具

| 层 | 路径 | 约定 |
|----|------|------|
| 状态 | `src/frontend/src/stores/<domain>Store.ts` | Zustand slice 模式，新 store 命名 `<domain>Store` |
| API 客户端 | `src/frontend/src/api/<domain>.ts` | 一域一文件，复用 `api/client.ts` |
| WS | `src/frontend/src/hooks/use<Domain>WebSocket.ts` | 一域一钩子 |
| 工具 | `src/frontend/src/lib/{cn,date,id,theme}.ts` | 不自造 util，先查 lib/ |
| 类型 | `src/frontend/src/types/index.ts` | 集中 |

---

## 四、四段式处理流程（强制执行）

> **核心原则**：**先找，再问，再改**。每一步都不要跳过。

### 阶段 0：先找（必跑，**任何任务第一步**）

> 即使用户给了文件位置，也要跑一遍 grep 确认没漏掉同类。

**必跑命令**（任选，按需组合）：

```bash
# 1. 看域分布
ls src/frontend/src/components/

# 2. 看最可能命中域的内容
ls src/frontend/src/components/<候选域>/

# 3. 按功能词 grep
grep -rln "<功能关键词>" src/frontend/src/

# 4. 看路由/页面级入口（如有 router）
grep -rln "<页面名/路由名>" src/frontend/src/
```

**输出"三选一"的候选清单**（让用户从 1/2/3 里选，或确认"都不是，新建"）：

```
我搜到以下 3 个候选最可能命中你的需求：

  [1] src/frontend/src/components/<A>/<X>.tsx   ← 既有，最近一次改动：<date>
      └─ 已含 <相关 selector / 组件名>
  [2] src/frontend/src/components/<B>/<Y>.tsx   ← 风格相似但功能不同
      └─ 可作为模板
  [3] 无既有 — 该功能确实是新建域
      └─ 建议放 components/<C>/<Name>.tsx

请回 1/2/3，或纠正。
```

**找不到的兜底**（描述模糊、grep 没命中）：

```
我猜你想改的地方可能在这 2-3 个里，但拿不准。补充一个最关键的：
- 你想"调整风格"还是"加新功能"？
- 这部分是给谁用的（私聊/群聊/设置/全局）？

如不便回答，我会按 "modify nearest existing" 的兜底策略继续。
```

### 阶段 1：视觉解码（**仅当有截图时**）

> 跳过若无截图，文字描述 + 现有同类组件作为视觉参考。

按以下顺序输出（**不复制颜色**）：

```
[布局] N 列 / 顶部 X 高度 / Y 个区
[主区] <元素 1>（占据 N×M）/ <元素 2>（在右侧/底部）
[交互] <按钮/输入/Tab 位置>，<悬停/激活态描述>
[层级] 强调：<哪些是大字号/品牌色>，弱化：<哪些是 muted>
[密度] 紧凑 / 常规 / 宽松（看 padding 与 gap）
```

### 阶段 2：现有素材定位（必跑，**继承 §三 必读**）

在阶段 0 候选基础上细化：

```
1. 落点文件：<路径>
2. 可复用组件：<ui/ 原子 1>、<ui/ 原子 2>、<业务组件 X>
3. 数据来源：<store 名> 的 <action/selector> / <api 文件> 的 <endpoint> / <hook 名>
```

**若无可复用**：先看**最近一次创建**的同类业务组件作为模板，**不要**直接拍脑袋建目录。

### 阶段 3：改写规则（强制约束清单）

每条改动必须**逐条**对应下表：

| 维度 | 必须 | 禁止 |
|------|------|------|
| UI 组件 | 从 `components/ui/` 选 | 自造 Button/Card/Modal |
| 颜色 | `bg-brand` / `text-foreground` / `bg-card` 等 | 硬编码 hex、`style={{ color: }}` |
| 字体 | 标题 `var(--ah-head-font)`（默认走 Tailwind h1-h3） | hardcode `'Geist'` |
| 间距 | Tailwind 标准档（`p-2/4/6`、`gap-2/3/4`） | 自定义 px |
| 圆角 | `rounded-md` / `rounded-lg` / `rounded-xl` | 自定义 `border-radius: 13px` |
| 阴影 | `shadow-sm` / `shadow` / `shadow-lg` | 新写 box-shadow |
| 玻璃 | `.glass-panel` / `.glass-strong` / `.glass-soft` | 新写 `backdrop-filter` |
| 动画 | `animate-[var(--animate-fade-in)]` 等 | 新写 keyframes |
| 主题 | 浅/dim/dark 都要通 | 只在浅色下看 |
| 图标 | `<Icon name="..." />` | 直接 `import { X } from 'lucide-react'` |
| 状态 | 既有 store 复用 / 新建遵循同模式 | 引入 Redux/Jotai/Recoil |
| 路径 | `components/<对应域>/` | 新建 `pages/`, `v2/`, `views-new/` |

---

## 五、改动范围判定（**默认改既有**）

> **总原则**：能改就不建，能并就不分，能迁就不复制。

| 用户意图 | 默认动作 | 兜底 |
|----------|---------|------|
| 描述模糊 / 没指明 | **改既有**（阶段 0 grep 找到的最近同类） | 找不到再问 |
| "加个新页面" | 落到 `components/<对应域>/` 新建 | 域不明确时反问 1 个澄清问题 |
| "改一下 xxx 页面" | 直接编辑 `components/<对应域>/<X>.tsx` | 文件不存在 → 反问"是不是叫别的名字" |
| "把 xxx 挪到 yyy" | 旧文件删除 + 新文件落点；**同步**改 store/API/路由引用 | 涉及路由的还要检查 `App.tsx` / `TabViews.tsx` |
| "拆 / 合 / 重构" | 拆出去的子组件放同目录；不要跨域散落 | 拆出 >3 文件要写设计文档 |
| 用户明确说"新建" | 走新建，但**先**确认 §四·阶段 0 没漏掉既有 | — |

**禁止**的命名（即使"新建"）：
- ❌ `XxxV2.tsx` / `XxxNew.tsx` / `XxxFinal.tsx` / `Xxx最新.tsx` —— 改原文件
- ❌ `pages/` / `views-new/` / `_temp/` —— 落到 `components/<域>/`
- ❌ 与 ui/ 原子同名（`Button.tsx` / `Card.tsx` 等）—— 撞名会让人困惑
- ❌ 与其他域组件同名（`Modal.tsx` 而不是 `CreateAgentModal.tsx`）—— 不带上下文

---

## 六、风格红名单（违反 = 退回）

- ❌ 引入新 UI 库（Material-UI / Ant Design / Chakra / shadcn 等）
- ❌ 引入新 icon 集（绕过 `<Icon>` 直接用 lucide/heroicons/radix-icons）
- ❌ 新增全局 CSS 变量 / 改 `styles/index.css` 已有 token
- ❌ 改 `lib/theme.ts` 的 4 主题结构 / accent 定义
- ❌ 在 AppShell 三栏结构外另起 layout（必须落入 Left/Center/Right 之一或弹层）
- ❌ `style={{ color: '...' }}` / `style={{ background: '...' }}` 这类 inline 颜色
- ❌ Tailwind v4 之外的任意 CSS 工具（`@apply` 自定义类 / 独立 .css 文件）
- ❌ `console.log` / `print` / 调试性注释代码块
- ❌ 任意 `any`（CR-09）
- ❌ 组件超过 200 行不拆（CR-09）

---

## 七、收束动作（每个功能点完成时必跑）

```markdown
## 收束本功能点
- [ ] 跑 `scripts/verify.bat`（ruff + mypy + tsc + eslint）→ 贴结果
- [ ] 跑 `python scripts/check_docs.py` → 贴结果
- [ ] 列出本次新增/修改的 5 个核心文件，每个 1 句话说明
- [ ] 在 `worklogs/黎/YYYY-MM-DD_<slug>.md` 写交接日志
- [ ] 在根 `STATUS.md` 更新自己那行
- [ ] 提 PR（标题走 Conventional Commits：`feat(frontend): ...`）
- [ ] **不要**做下一步，等我确认
```

**附 3 张截图**（人工 / 浏览器各截一次，1 分钟成本）：
- 浅色主题
- 暗色主题（`<html class="dark">`）
- 柔暗主题（`<html class="dim">`）

---

## 八、检查清单

### 开工前（**最关键**）
- [ ] **已 grep 找过同类**（§四·阶段 0），给用户 1-2 个候选
- [ ] 已确认改动范围 = **改既有**（默认）or 新建（仅当确有需要）
- [ ] 如有截图，已完成视觉解码；如无，已用文字描述 + 现有同类推断布局

### 写代码中
- [ ] UI 组件全部从 `components/ui/` 引入
- [ ] 颜色全部走 token（`bg-` / `text-` / `border-` 工具类）
- [ ] 间距/圆角/阴影走 Tailwind 标准档
- [ ] 玻璃面板走 `.glass-panel` / `.glass-strong` / `.glass-soft`
- [ ] 图标走 `<Icon name="..." />`
- [ ] 状态走既有 store 或新建同模式 store
- [ ] 浅/dim/dark 三主题都通
- [ ] **没有**新增游离目录 / `V2` 副本 / 跨域散落

### 收束前
- [ ] `grep -rn "#[0-9a-fA-F]\{3,6\}" src/frontend/src/components/<本次目录>/` → 0 命中（除注释）
- [ ] `grep -rn "style={{.*color" src/frontend/src/components/<本次目录>/` → 0 命中
- [ ] `scripts/verify.bat` 全绿
- [ ] **附浅/dark/dim 三主题截图**（可由浏览器/手动截；如实在截不到，至少在 dim 主题下肉眼过一遍）
- [ ] worklog + STATUS 已更新
- [ ] PR 已开

---

## 十、典型场景示例（输入稀疏下的处理）

> 下表展示**用户原话 → skill 第一动作**的对照。skill 不应"卡住等补全"，应**主动搜+推断+列候选**。

| 用户原话 | skill 第一动作 |
|---------|---------------|
| "把 inbox 重做一下" | grep → 找到 `InboxView.tsx` → 反问"重做指：视觉/功能/数据？" 同时给出基于现有 Inbox 的视觉改造草案 |
| "加个设置面板" | grep → 发现已有 `settings/ApiKeyManager.tsx` + `tweaks/TweaksPanel.tsx` → 问"是扩展 ApiKeyManager 还是新页面？" |
| "聊天里加个未读数" | grep `unread\|未读` → 命中 `chat/ConversationTabs.tsx` → 改它，不新建 |
| "在 xxx 右边加个侧边栏" | grep `<xxx>` 定位 → 看 AppShell 三栏结构 → 问"用 RightPanel 还是新弹层？" |
| "整个 UI 风格换成深色" | grep `dark\|dim` → 找到 TweaksPanel + theme.ts → 改 theme.ts（不新建主题） |
| "做个新功能：xxx" | grep `xxx` → 无命中 → 列 2-3 个最相似业务组件做参考 → 问"放哪个域" |
| "截图：[图] 做成这样" | 视觉解码 + grep → 给 3 候选 → 选 → 改 |
| "截图：[图] 加个这样的弹窗" | 视觉解码 + grep `Dialog` + 找到 `CreateAgentModal.tsx` 为模板 → 改 / 新建 `<New>Modal.tsx` |
| "把 a 挪到 b" | grep a 出现位置（含引用）→ 列出 a → b 的所有引用 → 给迁移清单 → 等确认 → 改 |
| "重构 xxx 拆分" | 找到 xxx → 评估拆分边界（同域 vs 跨域）→ 跨域要写设计文档 |

---

## 九、与其他 skill 的边界

| Skill | 关系 |
|-------|------|
| `skills/feat-start/` | 上游：先 `feat-start` 建分支、写 worklog 模板；再调用本 skill 做 UI |
| `skills/code-review/` | 下游：收束前用 `code-review` 跑红线自检（特别 CR-07/08/09 + D-02） |
| `skills/spec-driven-development/` | 上游：跨域/复杂功能先 `spec-driven-development` 写 spec |
| `skills/a社规范/` | 平行：a 社内部规范（含 Anthropic brand 参考）独立维护，需要时手动交叉参考 |
| `skills/doc-sync/` | 收束后：动到 docs/ 时用 `doc-sync` 同步 |
| `frontend-design`（系统 skill） | 灵感来源：本 skill 把它的"拒绝 AI 模板"哲学落到本项目约束 |
