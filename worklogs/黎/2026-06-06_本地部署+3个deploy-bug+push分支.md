# 2026-06-06 本地全栈部署 + 3 个 deploy-bug + push file-preview 分支

## 做了什么

1. **本地全栈部署** — DB（Postgres + Redis）在 Docker，前/后端本地裸跑（按 start.bat 同款思路但分开跑）
   - 后端：`src/backend/.venv` 装好 → alembic upgrade head → `uvicorn app.main:app --host 0.0.0.0 --port 8000`
   - 前端：`npm install` → `npm run dev`（Vite 5173 被 wslrelay 占，自动跳 5174）
   - 端到端：后端 `/health` 200、Swagger `/docs` 200、前端代理 `/api/agents` 返回真实数据 ✅

2. **修 3 个 deploy-time bug**（实际 commit 已落 HEAD，详见下方）
   - `src/backend/alembic.ini` 中文注释 → Windows GBK locale 解码失败 → 改英文
   - `src/backend/app/api/mcp_memory.py` 拿掉 `from __future__ import annotations` — mcp 1.12.4 `Tool.from_function()` 用 `inspect.signature()` 拿到的注解是字符串，`issubclass("str", Context)` 抛 `TypeError: issubclass() arg 1 must be a class`。本文件加注释说明原因
   - `src/frontend/src/components/ui/index.ts` barrel 漏 `export { WorkspaceBrowser }` → `StartChatModal` 加载失败 → React 卸载整树 → 白屏。补桶导出

3. **push `feature/frontend/file-preview-and-memories` 分支**（2 个 commit）
   - `025abf1 feat(backend): add memories table migration (alembic 0011) + skills router`
   - `18fba6a feat(frontend): file preview (fs browse + tree + read) + right panel rewrite`
   - 推到 `https://github.com/Hcre/AgentHub.git`，PR 链接已生成
   - 0011 迁移 `Running upgrade 0010 -> 0011, create memories table` ✅

## 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| 前端跑 5174 不强占 5173 | 5173 被 `wslrelay`（Docker Desktop WSL2 桥接，PID 33352）占着，杀它会破坏 Docker Desktop | 与 docker-compose.yml 端口一致（5174），但与 start.bat 不一致 |
| alembic.ini 注释改英文 | Windows locale 强制 GBK，alembic 用 `configparser.read(..., encoding="locale")` 没法绕 | 文件功能 0 影响，留一行注释解释 |
| mcp_memory.py 单文件去 future | 仅这一处受 mcp 库 inspect 行为影响；其它文件继续用 future 注解 | 维持项目统一规范，仅例外一处 |
| `mcp_memory.py` 改动放到现有分支 | 跟它一起进 HEAD 比单开分支简单；已是 main HEAD 的一部分 | 后续谁 review 这分支会同时看到 |
| `TaskStop` 杀 npm 不彻底 → 用 PowerShell `Stop-Process` | npm wrapper 退了，Vite node 子进程残留（同时出现 5174/5175/5176 三个孤儿 Vite） | 重启 Vite 前必须先按 PID 清干净 |

## 文件变更

| 文件 | 动作 |
|------|------|
| `src/backend/alembic.ini` | 中文注释改英文 |
| `src/backend/app/api/mcp_memory.py` | 去 `from __future__ import annotations` + 注释 |
| `src/frontend/src/components/ui/index.ts` | 加 `WorkspaceBrowser` 桶导出 |
| `src/backend/alembic/versions/0011_create_memories.py` | 新增（0010 → 0011） |
| `src/backend/app/api/routers/skills.py` | +110/-4（已属 HEAD 内的用户工作） |
| `src/frontend/src/api/fs.ts` | 新增 |
| `src/frontend/src/components/layout/previewContext.ts` | 新增 |
| `src/frontend/src/components/preview/{FilePreview,FileTree,previewModes}.tsx` | 新增 |
| `src/frontend/src/components/{layout/RightPanel,layout/AppShell,layout/...}/*` | 多个（已属 HEAD 内的用户工作） |
| `worklogs/黎/2026-06-06_*.md` | 本文 |

## 踩坑速记

- **alembic + Windows 中文 locale**：`PYTHONUTF8=1` / `LANG=C.UTF-8` 都不顶用（Windows 没这个 locale），唯一干净办法是去掉文件里的非 ASCII
- **mcp 库 issubclass 报错**：见上 mcp_memory.py 注释根因，mcp 1.12.x 用了 `from __future__ import annotations` 的项目需在工具函数上避免 future 注解
- **Vite 残留进程**：npm run dev 退出时 Vite 不一定跟着死，TaskStop 不可靠，重启前 `Get-NetTCPConnection | Select OwningProcess` 看 PID
- **git bash 转 `/F /PID` 为路径**：Windows 上 `taskkill` 必须走 PowerShell，不能用 bash 直接调
- **5173 被 wslrelay 占**：docker-compose 跑过前端容器后端口被 Docker Desktop WSL2 桥接残留；不要 `Stop-Process wslrelay`，会破坏整个 Docker Desktop

## 给下一位的交接

- 全栈当前状态：DB in Docker（5432/6379），后端 PID 56148 在 8000，Vite PID 7128 在 5174
- 0011 迁移已跑，`/api/agents/{id}/memories` 端到端 200
- 重启后端/前端的标准流程：PowerShell `Stop-Process -Id <uvi_PID>,<vite_PID>` → 重新起两个 background 任务
- 分支 `feature/frontend/file-preview-and-memories` 已在 origin，等 PR review
- 部署相关的 alembic.ini/mcp_memory.py 改动**已经是我做的版本**（在你 push 之前我修了，但 commit 是你做的工作流的一部分，所以都在 HEAD 里）。git log 看 `025abf1`/`18fba6a` 两个 commit 是混合的（包含我的 fix 周围的其他用户工作）
