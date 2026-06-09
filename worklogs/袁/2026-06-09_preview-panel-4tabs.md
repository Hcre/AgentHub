# 2026-06-09 预览面板 4 tab 真实 UI

**作者**: 袁 (xiangbianpangde)
**分支**: `feature/frontend/preview-tabs` (从 main 切出, 未 push)
**关联**: STATUS.md §🆕 预览面板 4 tab + §⚠️ 缺口 #1 MCP / #5 Deploy 已闭环

---

## 做了什么

Composer "+" 菜单 / 右栏预览面板的 4 个 PreviewMode (`previewModes.ts`: files/diff/deploy/webpage) 全部接真实 UI。
此前 files/webpage 已有雏形, diff/deploy 是 placeholder ("即将到来")。

| tab | 状态 | 实现文件 |
|-----|------|---------|
| 项目文件 files | ✅ 验证可用 | 既有 `FilePreview.tsx` (fsApi.browse/read) |
| 审查 diff | ✅ 新建 | `DiffPanel.tsx` + 后端 `GET /api/fs/git-diff` (skills.py FS_ROUTER) + `fsApi.gitDiff` (fs.ts) |
| 部署 deploy | ✅ 新建 | `api/deploy.ts` + `DeployPanel.tsx` |
| 网页 webpage | ✅ 验证可用 | 既有 `WebPageView` (RightPanel.tsx 内, iframe sandbox) |

### 新增/改动文件
- **新建** `src/frontend/src/api/deploy.ts` — deployApi.list/get/start/remove (对齐 deploy.py DeploymentOut)
- **新建** `src/frontend/src/components/preview/DeployPanel.tsx` — 历史列表 + 4 状态色 + build_logs 折叠 + 删除确认弹窗 + 3s 自动刷新 (building/queued 时)
- **新建** `src/frontend/src/components/preview/DiffPanel.tsx` — 调 fsApi.gitDiff + 复用 DiffView (react-diff-viewer emerald/rose) + staged 切换 + 刷新 + 友好空态
- **改** `src/backend/app/api/routers/skills.py` — FS_ROUTER 加 `GET /api/fs/git-diff` (subprocess `git -C <path> diff [--staged]`, 非 repo/git 缺失/超时 10s → 200 + ok:false 优雅降级, >2MB 截断)
- **改** `src/frontend/src/api/fs.ts` — 加 fsApi.gitDiff + FsGitDiffOut interface
- **改** `src/frontend/src/components/layout/RightPanel.tsx` — ActiveTabContent switch 加 diff/deploy 2 case + sessionId 注入 (activeConversationId ?? activeGroupId)

## 测试证据 (按证据分级)

| 检查 | 结果 |
|------|------|
| tsc --noEmit (frontend) | ✅ 绿 |
| eslint (5 改动文件) | ✅ 绿 (4 处 set-state-in-effect 按项目惯例 disable, 同 CreateAgentModal/ChatView) |
| 后端 app import | ✅ OK (81 routes) |
| live `GET /api/fs/git-diff` 3 路径 | ✅ repo(ok=True 6740 字符) / 非 git(ok=False 降级) / 不存在(404) |
| Playwright 点击测试 + 截图 | ✅ 7 张 `docs/deliverables/screenshots/preview-tabs-0{0..6}-*.png` |

### Playwright 7 截图清单 (均已 ls 验证存在, 360-390KB)
- `preview-tabs-00-menu.png` — "+" 下拉 4 mode
- `preview-tabs-01-diff-empty.png` — diff 空态 (无 workdir)
- `preview-tabs-02-files-empty.png` — files 空态
- `preview-tabs-03-files-tree.png` — **files 真实目录树** (后端 fs/browse 打通)
- `preview-tabs-04-diff-real.png` — **diff 真实 git diff 表格** (注入 workdir 后)
- `preview-tabs-05-webpage.png` — webpage iframe (example.com)
- `preview-tabs-06-deploy-empty.png` — deploy 空态 (isUuid 校验)

## 真 bug 暴露 + 修

- `fs_git_diff` 初版漏 `import os as _os` (函数内用 `_os.path.isdir` 但本文件其他函数都是局部 alias 模式) → 运行时 `NameError`, **live test 发现并修**。pytest 绿 ≠ live 验过, 再次印证三档独立。

## 给下一位的交接 (user 打算新开会话)

**当前状态**: 4 tab 代码全完, tsc+eslint+live 全绿, 7 截图齐. **未 commit, 未 push** (per no-push-without-ask).

**新会话接手起点**:
1. **先 commit** 本分支改动 (6 文件: deploy.ts/DeployPanel/DiffPanel 新建 + skills.py/fs.ts/RightPanel 改). 建议拆 2 commit: `feat(backend): GET /api/fs/git-diff` + `feat(frontend): 预览面板 4 tab 真实 UI`. **commit 前问 user 是否 push**.
2. **deploy 真实数据**: 当前只验了空态 (sqlite dev.db 无 session/迁移). 要真实部署列表需: postgres 起 + alembic upgrade + seed 一个 session + POST /api/deployments 造 1-2 条记录, 再截 `preview-tabs-07-deploy-real.png`.
3. **diff workdir 来源**: 生产路径是聊天会话的 workdir (useCurrentWorkdir → conversation/group.workdir 或 fileWorkdir 兜底). 截图时我用 localStorage 注入 fileWorkdir 走兜底, 真实场景靠 chat session 自带.
4. **剩余缺口** (STATUS §⚠️): P0 #2 Tasks (UI mock→真) 仍待做; P1 #3 Inbox / #9 Agents PATCH / #10 Message DELETE; P2 #4/#7/#8/#11/#12/#13. TD-11 Usage 其实已注册 main.py:124 可关.

**运行环境备忘**:
- vite EACCES 5173/5174 (Windows Hyper-V 占端口) → 用 `npx vite --port 9500 --host 127.0.0.1`
- 后端: `cd src/backend && DATABASE_URL=sqlite+aiosqlite:///./dev.db REDIS_URL=redis://localhost:6379/0 SKILLS_DIR=.agenthub/skills python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` (fs/diff 端点不需 DB; deploy 需真 postgres)
