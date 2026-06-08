# t9-usage-router-register (/api/usage router 注册) — 已完成

> **写于**: 2026-06-08 17:55 (Asia/Shanghai)
> **作者**: 袁 (xiangbianpangde, owner per ADR-0008)
> **状态**: ✅ done (commit ca7e33f)
> **关联 track**: t9-usage-router-register（[docs/plan/day2-pipeline-v2/README.md §3](../../docs/plan/day2-pipeline-v2/README.md)）

---

## 背景

overnight plan (`plan_3eaba0fa`) 落 4 端点 + token 监控全栈实现（[STATUS.md line 167-170](../../STATUS.md) + commit `46065aa` ChatService wire + `ebf678a` DiscussionOrchestrator wire + `7914a59` 4 E2E pytest + `60d4d69` worklog），但 main.py 漏 include_router(usage.router)，前端 /api/usage 调用 404。

**新发现 gap**: [STATUS.md line 167-170 已标](../../STATUS.md) "1 caveat: **/api/usage HTTP 端点未注册到 main.py** (pre-existing infra gap, T2 不在 scope 内)"。

---

## 本 track 已落地

### 1. 后端 router 注册（1 行 import + 1 行 include）
- `src/backend/app/main.py`:
  - import list: 加 `usage`
  - `app.include_router(usage.router)  # Token 消耗监控（P1-2，t9 track）`
- router 自带 `prefix="/api/usage"`，不重复加 prefix

### 2. smoke test（3 路径）
- `src/backend/tests/test_usage_router.py` (新文件):
  - `test_usage_router_registered`: 路由表含 `/api/usage`
  - `test_usage_endpoint_reachable`: GET /api/usage → 422 (missing param，证明端点存在)
  - `test_usage_window_validation`: GET /api/usage?window=invalid → 422 (pattern 校验)

### 3. 测试结果
- pytest 3/3 绿（9.99s）
- 回归测试: 9/9 绿 (health + attachments + usage_router)
- 无副作用（不改 usage.py 内部逻辑）

---

## Commit

```
ca7e33f merge: t9 /api/usage router register fix
7f198f0 fix(backend): 注册 /api/usage router (t9-usage-router-register)
```

---

## 验证

- 启动后端: `uvicorn app.main:app --port 18000`
- 访问: `curl http://localhost:18000/api/usage?agent_id=00000000-0000-0000-0000-000000000000&window=1h`
- 期望: 200 + JSON `{window, since, prompt_tokens, completion_tokens, total_tokens, by_session}`

---

## 给下一位的关联

- t6 (Token 监控 UI) 的基础：本 track 已把 3 端点（按 agent / session / 总览缺）挂上
- t6 需补 `GET /api/usage/global` 端点 + 前端 panel（详见 [worklogs/yuan/2026-06-08_t6-token-monitor.md](2026-06-08_t6-token-monitor.md)）
- 前端 TokenMonitorPanel 调 3 端点时，本 track 修的 main.py 注册是前置依赖

## 关联引用

- [docs/plan/day2-pipeline-v2/README.md §3 t9](../../docs/plan/day2-pipeline-v2/README.md)
- [src/backend/app/main.py](../../src/backend/app/main.py) — 注册位置
- [src/backend/app/api/routers/usage.py](../../src/backend/app/api/routers/usage.py) — 路由定义
- [src/backend/tests/test_usage_router.py](../../src/backend/tests/test_usage_router.py) — smoke test
- [STATUS.md line 167-170](../../STATUS.md) — 缺口溯源
- [worklogs/decisions/0015-day2-pipeline-claude-team-mode.md](../../worklogs/decisions/0015-day2-pipeline-claude-team-mode.md) — pipeline 改造
