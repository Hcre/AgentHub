# 工作日志：部署发布真实流水线 + STATUS 剩余功能开发收尾

- **谁**: 袁 (xiangbianpangde)
- **日期**: 2026-06-10
- **分支**: main（本地改动，未 commit/未 push，按 [[no-push-without-ask]]）
- **关联 Spec**: `docs/specs/04-commands` §6.4.4 B-5-P2-DP01 + `docs/plan/06-09-袁-status完成/04-deploy-desktop`

## 目标
完成 STATUS.md 中除「代码冲突处理 / 桌面部署 / 完成文档 / 录制视频」外的所有功能开发。
盘点后真正剩余的非排除功能开发 = **部署发布真实流水线**（⚠️）；另复核了 #11 Memory 编辑（实际已完成，STATUS 失真）与「消息操作」（功能已全实现，仅 E2E 证据 ⚠️）。

## 产出（本地改动，未 commit）

### 1. 部署发布真实流水线（⚠️→✅，PRD §5）
**根因 bug**：`deploy.router` 从未在 `main.py` 注册 —— 前端 `api/deploy.ts` + `DeployPanel` 全在，但
所有 `/api/deployments` 请求 404。这才是部署"两段都缺"的真因，非仅"假 URL"。
- `app/main.py` — 补 `from app.api.routers import ... deploy` + `app.include_router(deploy.router)` + 挂
  `StaticFiles` 于 `/preview`（serve `settings.deploy_root`）。
- `app/infrastructure/deploy/static_host.py`（新）— `StaticHost`：files 落盘 `_assets/deploy/{id}/`
  （路径穿越防护 `_safe_relpath`）+ `write_zip`（package）+ `site_url`/`download_url` + `remove`。
- `app/application/services/deploy_service.py` — `_advance_synchronous` 由"假 URL 桩"改**真实落盘**：
  static_site→`{public_base_url}/preview/{id}/{entry}`（真 200 可访问）；package→真 `site.zip` 下载；
  container→诚实 `E_DEPLOY_CONTAINER_UNSUPPORTED`（无宿主 Docker，不发假 URL）；`delete` 清盘；
  `asyncio.to_thread` 包 IO（CR-12）。
- `app/core/config.py` — `deploy_root` / `public_base_url` + `deploy_root_path` property。
- `DeployPanel.tsx` — 加「新建部署」模态（HTML 编辑 + static_site/package 切换 → `deployApi.start`）。
  **全仓首个 `deployApi.start` 调用方**，闭合"前端零触发"缺口。
- 测试：`tests/test_deploy.py` 19 用例重写为真实落盘断言（含路径穿越 / container 失败 / 清盘）；
  `DeployPanel.test.tsx`（新）3 vitest。

### 2. #11 Memory 编辑（复核 = 早已完成，STATUS 失真订正）
`MemoryPanel` 铅笔→`EditForm`→`memoryStore.updateMemory`→`memoriesApi.update`(PATCH) 全链路本就在
（此前 STATUS"待复核"系只 grep 了 panel 文件，调用其实在 store）。补 `MemoryPanel.edit.test.tsx` 1 回归锁定。

### 3. 附带：4 个陈旧测试对齐当前行为（同 TD-14/TD-17 模式）
- `test_claude_code_runtime` 2 个：`_build_env` 已改为纯 `os.environ.copy()`（proxy 走 `_proxy_url`），
  删旧 env 注入断言。
- `test_mcp_opencode_inject` 2 个：`_write_opencode_config(mcp)` 单参（不再注入 provider/apiKey），
  删旧签名 + provider 断言。

## 验证结果
| 维度 | 结果 |
|------|------|
| 后端 pytest | **375 passed / 3 skipped**（含 deploy 19）|
| 前端 vitest | **143 passed**（含新增 deploy 3 + memory 1）|
| ruff / mypy / tsc / eslint | 全绿（mypy 本次 3 文件 0 err；项目级旧债不在本 scope）|
| live HTTP | static_site→`GET preview_url` **200 + 真 HTML**；package→真 zip **200/212B**；container→failed 诚实 |
| Playwright 真浏览器 | 新建预览→部署 tab→新建→部署→**「已就绪」行 + 真 preview 链接**；deploy 链路 **0 console 错** |
| 截图 | `deploy-served-site-live-2026-06-10.png`（浏览器渲染托管站点）/ `deploy-panel-create-form-2026-06-10.png` / `deploy-panel-ready-row-2026-06-10.png` |

## 关键决策
| 决策 | 原因 | 影响 |
|------|------|------|
| container 诚实标记 unsupported 而非模拟 ready | 无宿主 Docker，发假 URL 是失信 | 行为变更，已更新 STATUS + 测试 |
| package 不再返 preview_url（仅 download_url）| 打包无站点可预览 | 改了 1 条旧断言 |
| 在 8011 起独立后端 + 5273 vite 验证 | 不打断用户 5h 在跑的 :8000 dev 栈 | 验证隔离，PUBLIC_BASE_URL 指向 8011 |
| 不 commit/不 push | 按 [[no-push-without-ask]] | 留给用户审阅后决定 |

## 未完成 / 阻塞
- 「消息操作」仍标 ⚠️：**功能已全实现**（复制/重生成/Pin/回复引用/全屏预览），⚠️ 仅指"需真 URL 的 E2E 证据"，非缺开发。
- 排除项（未做，按目标要求）：代码冲突处理（❌，已有 untracked `conflict.py` 草稿）/ 桌面端 Tauri（📋）/ 文档 / 视频。

## 给下一位的交接
> - 本会话改动**未 commit**。若要落库：先切 feature 分支（`禁止 main 开发`），把 deploy 7 文件 + 4 测试文件 + STATUS + 本 worklog 一起提。
> - `/api/groups` 在 :8011 返 500（2 条 console 错），**与本次无关**（未碰 groups），疑似既有 bug，值得单独排查。
> - 验证用的 8011 后端 / 5273 vite 是临时进程；`_assets/deploy/` 下有几条测试部署产物（gitignored，可删）。
> - 部署"完整真实化"（容器 docker SDK + WS 进度推送 + 聊天指令→部署编排桥接）仍是更大工程，见 `docs/plan/06-09-袁-status完成/04`，本次只做静态托管最小真实闭环。
