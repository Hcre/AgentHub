# 2026-06-10 v2-status 5 步真实验证 + 2 个 M4 真 bug 修复

> 作者: 袁 (xiangbianpangde) · 分支: feature/v2-status/m1-m3-m4-impl · 基线 9bb588a

## 背景

承接 `docs/reports/test-report-2026-06-10-v2-status.html` §9「下会话必做」5 步：把前一会话「代码已落但单测/真实接口未跑」的诚实缺口补齐。

## 做了什么（按 5 步）

### 1. DB + 迁移（✅）
- postgres/redis 容器已在跑（host:15432）。DB `alembic_version=0024`，`sessions.archived` 列 + `ix_sessions_archived` 索引已在库；0024 即 head，无 pending。

### 2. 补 6 套单测（✅ 全绿）
新增 4 个测试文件 / 6 套逻辑：
- `tests/test_session_archived.py` — M1#2 归档持久化（3 路径）
- `tests/test_static_host.py` — M4 路径穿越（4）+ 静态托管落盘/真 zip/remove（4）
- `tests/test_fs_endpoints_v2.py` — M3-B pptx 三路径（400/404/415）+ M3-C 非 git 降级（is_git=False / 404）
- `tests/test_agent_draft.py` — M1#4 启发式抽取（role/skills/降级/截断）

并修复 **4 例被 M4 异步改造打破的 deploy 回归**：`start()` 改 `asyncio.create_task` 后返回 `queued`，旧测期望同步 `ready` + 旧假域名 URL。改为 `_drain_background()` 排空后台任务再断言 + 真 `/preview/` URL 断言；另把 1 例靠时序侥幸通过的 list 测试也改确定性（避免 flaky）。

全后端套现状：本期 6 套 + deploy 全绿；另 **12 例历史既存失败**（test_chat_service / test_pi_agent_e2e / test_pin_session_ownership，隔离运行同样失败，与 v2-status 无关）。

### 3. 起前端 + E2E（⛔→部分）
- vite 起在 3000（5173/5180 落 Windows winnat 保留端口区，EACCES），代理指向 live 后端 8200。
- **M1#1 真浏览器验过**：36 会话回灌左栏 + 三栏渲染 + 无白屏 → 截图 `docs/deliverables/screenshots/v2-live-m1-1-three-panel.png`。
- **M1#3 消息操作 E2E 阻塞**：发送按钮 gated on 在线 agent + WS + 工作目录；离线 agent 环境点发送 0 网络请求、不渲染消息气泡 → spec 核心断言无法通过。**不补假图**。

### 4. M4 部署链路 live 验证（✅ 真闭环，过程查出 2 bug）
查出并修复 2 个真 bug（M4 此前 API 完全不可用）：
1. **`main.py` 从未 `include_router(deploy.router)`** → 所有 `/api/deployments` 返 404，部署 API 整条不可达。
2. **`deploy_service.start()` 后台 `asyncio.create_task` 复用请求作用域 session** → 请求返回即关闭，后台首个 `save` 失败、部署**永久卡 queued**、`/preview` 永远 404。改为后台开独立 `session_factory()` session（沿用 `coordinator_run` / `ws` 既有范式），并加可注入 `bg_session_factory` 让单测能复用同一 in-memory session 断言落库。

修复后 live 验证通过：
- static_site: POST → `ready`，`GET /preview/{id}/index.html` 返 **200 + 真实 HTML**（真浏览器打开截图 `v2-live-m4-deployed-preview.png`）。
- package: POST → `ready`，download_url 返**真 zip**（容器内校验含 app.js + index.html）。

### 5. 整理 + commit（⏳ 等推）
本地 commit 完成，**等 user 显式说推才 push**（MEMORY 禁擅自 push）。

## 给下一位的交接
- M1#3 / M3-A/B/C 完整 UI E2E 需：在线 agent（claude_code CLI 可达）+ 工作目录 + python-pptx 装进运行环境。
- 2 个 M4 bug 的源码已改（main.py + deploy_service.py），live 容器是 `docker cp` 临时验证的；正式生效需重建镜像或源码入构建链。
- 待落 ADR-0019（M4 router 未挂 + 后台 session 生命周期修复）。
