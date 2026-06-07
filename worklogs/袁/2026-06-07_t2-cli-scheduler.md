# 工作日志: P1-3 CLI PATH 扫描 scheduler 集成

- **谁**: 袁
- **日期**: 2026-06-07 ~ 06-08
- **分支**: feature/m5/cli-scheduler
- **关联 Spec**: docs/specs/04-commands §6.7 B-5.4-P1-3

## 目标

把 CLI PATH 扫描从「手动 endpoint」升级到「lifespan startup 立即扫 + 后台 1h 循环」。

## 产出

- [x] commit b63d0da — feat(backend): cli_scanner scheduler 集成
  - 新增 `app/infrastructure/cli_scheduler.py` (237 行)
  - 修改 `app/main.py` lifespan + include_router
  - 修改 `app/api/routers/cli.py` 路由读缓存
  - 注册 cli router
- [x] commit 66e2c52 — test(backend): cli scheduler 4 路径 + 2 附加 (208 行)
- [ ] commit (deferred) — chore(backend): 截图 (因 engine 70min kill 砍)

## 验证结果

| 工具 | 结果 |
|------|------|
| pytest tests/test_cli_scheduler.py | **6/6 PASSED** (test_cli_scan_first_run / cache_hit / cache_expired / missing_graceful / lifespan_loop / reset) |
| pytest 全量 | 162 pass + 3 fail (3 失败均为 t1-pin-auth / pi_agent_e2e 跨任务 deferred，与本 task 无关) |
| ruff check 5 文件 | **All checks passed** (修复 5 项: RUF100×2, SIM105, SIM117, F401) |
| mypy 3 文件 | **0 errors** (其余 114 错在 selector.py / claude_adapter.py 等 baseline 历史债) |
| 端到端 smoke | 本地 uvicorn 18002 启动 + `curl /api/cli/scan` work；docker 18000 跑旧 image 不带 cli router（deferred rebuild） |
| Playwright 截图 | ❌ **deferred** — task killed by 70min cap |

## 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| 用 `asyncio.create_task` 后台循环，不用 APScheduler/celery beat | 已有 `claude_code_process_pool.sweeper` 同款模式，无新依赖，跟项目习惯一致 | 代码风格统一，测试 mock time.monotonic 易 |
| TTL 用 `time.monotonic` 差值，不用 `time.time` | 避免系统时钟回拨导致缓存"永不刷新" | 时间穿越测试更可靠 |
| 路由 `now()` 同步读缓存，`force_refresh()` 异步 | HTTP 端点走同步路径，最坏情况兜底 force_refresh | 高并发下多请求只走一次重扫 |
| 优雅降级：bin 缺失 warning 而不 raise | 单 bin 缺失不该阻塞 startup_scan | 测试用 caplog 验 ≥2 条 warning |
| `try-except Exception` 全部用 `contextlib.suppress` 风格 (after ruff fix) | 满足 ruff SIM105 | 代码更紧凑 |

## 未完成 / 阻塞

- [ ] **Playwright 截图 `docs/deliverables/screenshots/e2e-cli-scan-2026-06-08.png`** — 70min engine cap
  - 原因：docker 18000 跑旧 image，前端没专门 CLI 状态页，screenshot 价值边际低
  - 解决方案：rebuild docker image 或后续在 settings 页加 CLI bin 卡片后补
- [ ] **3rd commit (chore) 把截图落盘** — 同上

## 给下一位的交接

> 时间紧的 plan 中，**这个 task 的"Playwright 截图"环节可以安全降级**：
> 1. 后端 scheduler 集成已完成，6/6 pytest + ruff + mypy 全绿
> 2. `/api/cli/scan` 端点可用，本地 uvicorn 实测正常
> 3. 前端无 CLI 状态 UI，screenshot 仅能展示 JSON 响应或通用 page，价值边际低
> 4. 若要补：先 `docker compose build backend` 把新 cli router 打进 image，再 Playwright 访问 `/api/cli/scan` 截 JSON

### Race 教训（已落 agent MEMORY.md）
- 跨 task 并行跑时，shared worktree 中其他 agent 切分支会 `git reset --hard` 覆盖你
- 防御：每完成 1 步立即 commit，不要在 working tree 留 diff
- 恢复：`git reflog` 找 SHA → `git reset --hard <sha>`
- 强烈推荐用 `git worktree add <isolated-path> feature/<branch>` 隔离

### 已有先例（同 plan 其他 t1/t2/t3）
- t1-pin-auth-fix: 169 pytest pass + 3 commit + Playwright 截图 deferred
- t2-token-monitor: 169/173 pytest + 4 commit
- t3-mobile-h5: 已 merge main (015cf8e)
- t4-cli-scheduler (本 task): 162/168 pytest (含本 task 6) + 2 commit pushed + screenshot deferred
