# AgentHub 前端 — 总览交接文档

> 给接手前端的同学。读完约 5 分钟。
> 当前状态：前端实施计划 **§1–6 + §7.3 视觉打磨已完成**，**§7.1/7.2（真实 API/WS 联调）待后端就绪后接入**。
> 现在是 **mock 驱动的可演示前端**：所有数据来自 `src/data/`，无网络请求。

---

## 一、运行

```bash
cd frontend
npm install
npm run dev          # 开发服务器 http://localhost:5173（被占则自动 5174）
npm run build        # tsc -b && vite build → dist/
npm run lint         # eslint
npm run format       # prettier --write
```

容器部署（生产构建 + nginx）：`docker compose -f ../docker/docker-compose.yml up -d --build frontend` → http://localhost:5173

**验收 Gate（每次改完跑）：** `npx tsc -b`(0 错) · `npx eslint .`(0) · `npm run format:check` · `npm run build`

---

## 二、技术栈与红线

- Vite 8 + React 19 + TypeScript 6（strict）+ Tailwind v4 + Zustand 5 + lucide-react
- **CR-07**：`tsc --noEmit` 零错误，禁 `any`
- **CR-09**：组件建议 <200 行（大视图已拆子组件）
- **CR-11**：禁 `console.log`（eslint 拦）
- 密钥不留存明文（API Key 仅透传，前端 store 不存）
- 提交：Conventional Commits

---

## 三、目录结构

```
frontend/
├── prototype/              # v0 原型（只读 UX 参考，勿改）
├── index.html              # 入口（已引入 Google Fonts）
├── src/
│   ├── main.tsx / App.tsx  # 入口 + applyTweaks 主题副作用
│   ├── styles/index.css    # Tailwind + 设计 token（light/dim/dark）+ glass + 动效
│   ├── types/index.ts      # 所有领域类型（与后端 schema 对齐处）
│   ├── lib/                # cn / id / date / theme(accent+应用)
│   ├── data/               # ⚠️ mock 数据：mock.ts / groups.ts / extra.ts
│   ├── stores/             # Zustand：ui / chat / task / group / inbox / agent
│   └── components/
│       ├── ui/             # 设计系统原语（Button/Avatar/Badge/Card/Dialog/Tabs/Icon...）
│       ├── layout/         # AppShell + LeftPanel + CenterPanel + RightPanel
│       ├── chat/ group/ tasks/ activity/ calendar/ inbox/ agent/ views/ tweaks/
│       └── group/HANDOFF.md   # 群聊专项交接（含 MOCK 接缝细节）
└── docs/                   # ⚠️ 被 .gitignore 排除（见第六节）：实施计划 / 转换方案
```

---

## 四、状态管理与 API 接入点（§7.1/7.2 路线）

所有 store 现在从 `src/data/` 初始化、action 内是纯前端逻辑。**接真实 API 时只改 store 内部，组件不动**（action 签名已稳定）。对照 PRD §6。

| Store | 文件 | 现状（mock） | 接入目标 |
|-------|------|------|---------|
| `useUIStore` | uiStore.ts | 纯 UI 路由/主题，**无需接后端** | — |
| `useAgentStore` | agentStore.ts | agents+profiles seed | `GET/POST/PATCH/DELETE /api/agents`（§6.1）：createAgent/updateConfig/removeAgent 内发请求 |
| `useChatStore` | chatStore.ts | send 后 setTimeout 假回复 | `WS /ws/sessions/{id}`（§6.3）：send 改发 WS，回复由推送 append |
| `useTaskStore` | taskStore.ts | seed mock tasks | `GET/POST /api/tasks`（§6.4） |
| `useGroupStore` | groupStore.ts | **MOCK SEAM** `simulateGroupReply` | 见 `components/group/HANDOFF.md`（§6.2，协调者编排） |
| `useInboxStore` | inboxStore.ts | seed mock inbox | `GET /api/inbox`（§6.5）；resolve=批准/驳回，串群聊 requiresApproval 审批流 |

**关键耦合点：** 群聊「需批准」消息 → 收件箱审批 → 批准后后端执行 → 派发方案批量建任务进看板。这条链现在各段是 mock，接后端时要打通（详见 group/HANDOFF.md）。

---

## 五、设计系统与主题

- 设计 token 在 `src/styles/index.css`：`:root`(浅) / `.dim`(柔暗) / `.dark`(深) 三套 HSL 变量；`bg-brand`/`glass-panel` 等可直接用。
- 主题/强调色/密度/字体由 `lib/theme.ts applyTweaks()` 写到 `<html>`，用户用右下 **Tweaks 面板**（`components/tweaks/TweaksPanel.tsx`）调。
- 新增图标：`types/index.ts` 的 `IconName` 加名字 + `components/ui/Icon.tsx` 的 MAP 加映射（两处）。
- 新增 accent：`lib/theme.ts` 的 `ACCENTS` 加一项。
- 头像渐变/字体栈见 `ui/Avatar.tsx`、`lib/theme.ts`。

---

## 六、已知简化 / 待优化（接手前先看）

- **`frontend/docs/` 被 .gitignore 排除** —— `前端实施计划.md`、`前端Phase0_转换方案.md` 不在 git 里。要共享给团队需把 `.gitignore` 里的 `docs/` 行去掉再提交，或移到仓库根 `docs/`。
- Tweaks 设置不持久化（刷新回默认）——如需：uiStore 包 `zustand/middleware` 的 `persist`。
- 新建 agent 不出现在任务负责人下拉 / 群组成员（这俩仍读 `data/mock` 的种子 agents，未走 agentStore）。
- 群聊：派发按钮、@mention 多选/补全、消息持久化未做（group/HANDOFF.md 有清单）。
- 收件箱批准/驳回仅前端移除，未回写群聊/触发执行。
- 日历事件只读；中心区 channels/files 两个 Tab 仍占位；对话式创建 agent 未做。
- 设置不持久、glass 档位（frosted/solid）未做。

---

## 七、延伸阅读

- 每个 Phase 的细节与交接：`worklogs/袁/2026-05-23_Phase*.md`
- 群聊专项：`src/components/group/HANDOFF.md`
- 需求权威：`docs/PRD_AgentHub_v4_统一方案.md`；API：`docs/adapter_interface_spec.md`
- 原型参考（只读）：`frontend/prototype/`
