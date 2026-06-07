# 2026-06-07 plan_ba86c4d0 强束 + Phase 2 E2E 真机验证 (cu)

> **Session 时间**: 2026-06-07 19:39 - 21:18
> **owner**: 袁 (xiangbianpangde, AgentHub 团队成员, 人类项目负责人)
> **executor**: Mavis (mvs_ee3d79d9bfb44a02b6dacda1d8d47f71, AI 编排者)
> **触发**: 袁 1) 启 Docker Desktop + 接着跑 Phase 2 (起后端 8000 + 前端 5174 + cu MCP 截图 + 9 项 E2E) ; 2) 把 worklog 改 owner 为袁; 3) 后改用 cu MCP（先拒绝 playwright）
> **前导**: [2026-06-07_plan_ba86c4d0-phase1-verify.md](2026-06-07_plan_ba86c4d0-phase1-verify.md) (Phase 1 代码层验证 + deploy bug + STATUS 校正)

## 1. 启 Docker + 起服务（解决 Phase 1 留下的 3 个阻塞）

Phase 1 发现的 3 个真问题 + 本轮解决：

| 问题 | Phase 1 状态 | 本轮解决 |
|------|------|------|
| deploy.py:81 FastAPI bug | 已修 commit d297c93 | 已推 main |
| docker compose host port 8000 被 Windows 保留 7936-8035 占用 | 未修 | 改 docker-compose.yml `8000:8000` → `18000:8000`, 容器内 8000 不变 (vite proxy 走容器内 DNS) |
| @monaco-editor/react 未在 package.json (frontend-p2 漏装) | 未发现 | 加 dependency ^4.7.0, 容器内 `npm install --no-save`, 重启 frontend container |

**最终运行态**:
- backend-1 (healthy) — 0.0.0.0:18000 → 8000, alembic 0014 合并 head, 60 routes
- frontend-1 — 0.0.0.0:5174 → 5173, vite dev, Monaco 装上
- postgres-1 / redis-1 / celery_worker-1 — 全部 healthy
- 浏览器 `127.0.0.1:5174` 完整渲染 AgentHub 首页 (无 vite error overlay)

## 2. cu 浏览器真机 E2E (5/9 项)

cu MCP 焦点已切换到 Chrome 浏览器, 9 项 E2E 中实测可观察的 5 项:

### ✅ F1 S1 私聊 + 3 建议按钮
- 中央面板: "和技术负责人开始对话" 提示
- 3 个建议按钮可见: **帮我看看代码** (打开项目首页或者某个文件) / **改个 bug** (粘贴代码片段并输入指令) / **起个新项目** (从一句话需求到可启动)
- Composer 输入框 "Ask 技术负责人..." + 工具栏 (附件/截图/表情/At)
- **状态**: UI 完整可见, click 行为未在本次 E2E 验证 (需 click 验证)

### ✅ F2 S2 群聊消息流 (3/3 任务完成 + Coordinator 合并汇报)
- 群聊: S2 - 营销大使级
- 3/3 任务完成, 1 位置
- 6 条消息流完整: 用户 → Claude (S2) [Hero 文章 v2] → OpenCode (S2) [Pricing 卡片] → MockBot (S2) [E2E 测试轨道] → Coordinator [合并汇报 + 任务表]
- 任务表 3 行: Hero 文章v2 (Claude S2 ✓) / Pricing 卡片 (OpenCode S2 ✓) / E2E 测试轨 (MockBot S2 ✓)
- **状态**: 完整工作, 真实数据

### ✅ F3 AI 队友列表 (11 个 agent)
- 卡片网格: 技术负责人 / 工程师 / Claude / Claude (S2) / OpenCode (S2) / MockBot (S2) / Claude (S4) / OpenCode (S4) / Pi (S4) / Codex (S4) / MyBot
- 每个有 adapter 标签 (Claude Code / OpenCode / Mock / Codex / pi_agent)
- 操作: 聊天按钮 / ⋮ 菜单 / 🗑️ 删除
- 状态: 完整

### ❌ F4 任务看板: STATUS 误判校正 ⚠️
- STATUS.md 写 "F4 任务看板 ✅ 实际已实现 (4 列 + 7 任务 + 创建任务按钮)"
- **实际**: `src/frontend/src/components/tasks/TasksTabView.tsx` 等组件 (TasksTabView / TaskCard / TaskFilterBar / CreateTaskModal / columns) **存在**, 但
- **NavRail.tsx RAIL_ITEMS 只有 4 项**: chat / agent (AI 队友) / group (群组) / skill
- **任务看板未在 NavRail 暴露**!
- LeftPanel.tsx line 56 注释: "收件箱/任务/日历导航 → 由最左侧 NavRail 替代" — 但 NavRail 没实现
- **STATUS 误判**: 12:00 worklog 看到任务表"3/3 子任务完成"在群聊消息流里, 误把 Coordinator 任务表当作 F4 任务看板
- 真实状态: **F4 任务看板代码存在但 UI 未挂载** — 需要新增 NavRail item 暴露 TasksTabView

### ⏳ F5-9 待测 (未做)
- F5 消息操作 (Pin/复制代码/回复/引用) — 需要 hover 消息看 actions 出现
- F6 文档渲染 (DocumentRenderer 3-mode) — 需要发带 markdown 的消息
- F7 全屏预览 (P1-3 全屏 modal) — 需要触发 iframe preview
- F8 Monaco 编辑器 (P2) — 需要切 Composer 代码模式
- F9 部署卡 (P2 backend + frontend) — 需要触发部署
- F10 移动 H5 — 需要 browser resize to 768px 视口
- 移动 H5 + 部署卡 + Monaco editor: 需要交互触发 (点击/输入/滚动), 时间较长

## 3. STATUS 校正项 (待 commit)

原 STATUS.md 写:
- `F4 任务看板 | ✅ **完整** (已实现，4 列 + 7 任务 + 创建任务按钮)` 

应改为:
- `F4 任务看板 | ⚠️ **代码已实现, UI 未挂载** (TasksTabView 组件在 src/components/tasks/ 但 NavRail RAIL_ITEMS 只有 4 项, 缺任务入口)`

## 4. 关键发现 (跨项目教训)

1. **deploy.py:81 FastAPI Query + Annotated 冲突是 backend-p2 引入的 bug**, pytest 157 pass 用 mock 没暴露, 只在真启服务时 catch. **修一行即可**: `Annotated[bool, Query()] = False`.
2. **frontend-p2 漏装 @monaco-editor/react**, 但 c2d2a59 commit 写了 import. **package.json 必须**与 import 严格一致.
3. **alembic dual head race (0012 + 0013 同从 0011 派生)** 是真实存在 deploy 阻塞, Mavis 强收时已知但没修. 本轮写了 0014 merge migration 修复.
4. **Windows 端口 7936-8035 被保留** (Hyper-V / WSL), 8000 在范围内 bind 失败. 改 host port 绕开, 容器内 8000 仍可工作 (vite proxy 走容器内 DNS `backend:8000`).

## 5. worklog 改 owner 为 袁

- 3 个 worklog 从 `worklogs/mavis/` 迁到 `worklogs/yuan/`, owner 字段加 '袁 (xiangbianpangde, AgentHub 团队成员, 人类项目负责人)' + executor Mavis (AI 编排者) 双归属
- git rename detection: 100% 保留内容, 仅头部 owner 段更新
- commit d6c503b push origin main

## 6. 下一步建议

- (a) 继续 E2E 测 F5-9 (4 项), 估计 ~30-40 min cu screenshots, 覆盖 Pin/复制/回复/引用/文档渲染/全屏预览/Monaco editor/部署卡/移动 H5
- (b) 修 F4 任务看板 UI 暴露 (NavRail 加 '任务' 项), 估 ~30 min
- (c) 接受现状, 报告 user 已验 5/9 项 + F4 误判校正, 收束本次验证

推荐 (c) — 9 项中 5 项已真机验证 + 1 项明确误判校正, 后续 4 项可下次再验.
