# 2026-06-08 t6-m5-5-3-token-ui 完整实施 (Token 监控 UI 暴露)

> **写于**: 2026-06-08 19:35 (Asia/Shanghai)
> **作者**: 袁 (xiangbianpangde, owner per ADR-0008)
> **会话**: 19:21 - 19:35 (14 min)
> **目的**: 按 worklogs/yuan/2026-06-08_t6-token-monitor.md 8 步计划全栈实施
> **关联 track**: t6-m5-5-3-token-ui ([docs/plan/day2-pipeline-v2/README.md §3](../../docs/plan/day2-pipeline-v2/README.md))

---

## 0. 起点

session 起点：t1/t2/t4 cherry-pick 完成（19:18），next gate 是 t6。
worklog 2026-06-08_t6-token-monitor.md 已有 8 步实施计划 + 完整代码片段。**直接照 plan 实施**。

---

## 1. 实施明细

### Step 1: Domain Repository 抽象接口
- `src/backend/app/domain/repositories/usage_repository.py`: 加 2 abstract method
  - `async def sum_global(self, window: UsageWindow) -> dict[str, int]`
  - `async def group_by_agent_global(self, window: UsageWindow, top_n: int = 10) -> list[dict]`

### Step 2: Postgres Repository 实现
- `src/backend/app/infrastructure/repositories/usage_repository.py`: 复用既有 `_bucket_sum` helper
  - `sum_global`: `where_clauses=[created_at >= window.since]`（不限 agent/session）
  - `group_by_agent_global`: GROUP BY agent_id + ORDER BY total DESC + LIMIT top_n

### Step 3: Service 编排
- `src/backend/app/application/services/usage_service.py`: 加 `aggregate_global(window_name, top_n)` method
  - 返回结构对齐既有 `aggregate_by_agent/aggregate_by_session` 契约：`{window, since, prompt_tokens, completion_tokens, total_tokens, by_agent}`
  - 替换既有 TODO 注释

### Step 4: Router 端点
- `src/backend/app/api/routers/usage.py`: 加 `@router.get("/global")`
  - Query: `window: str = "24h"`, `top_n: int = 10, ge=1, le=100`
  - 调用 `svc.aggregate_global(window_name=window, top_n=top_n)`

### Step 5: pytest (3 路径)
- 新文件 `src/backend/tests/test_usage_global.py`
  - `test_usage_global_1h` (async, db_session): 5 records → 60 total
  - `test_usage_global_top_n` (async, db_session): 12 records → top 10
  - `test_usage_global_window_validation` (sync, TestClient): window=invalid → 422
- **结果**: 3/3 绿 (pytest output: "3 passed in 6.83s")

### Step 6: TokenMonitorPanel 组件
- 新文件 `src/frontend/src/components/settings/TokenMonitorPanel.tsx`
  - props: `{ open, onOpenChange }`
  - 内嵌 Dialog + 3 卡片（1h/24h/7d） + 加载/错误态 + 关闭按钮
  - useEffect 调 `/api/usage/global?window={1h|24h|7d}` 3 端点
  - data-testid 锚点：`usage-card-1h/24h/7d` / `usage-error` / `usage-loading`

### Step 7: NavRail 入口
- `src/frontend/src/components/layout/NavRail.tsx`:
  - import `{ TokenMonitorPanel }` (line 9)
  - RAIL_ITEMS 加 `{ key: 'usage', icon: 'activity', label: '用量' }` (无 section, 弹模态)
  - 加 `useState<usageOpen>` (line 31)
  - onClick handler 分流: 有 section 走 setSection, key='usage' 走 setUsageOpen(true)
  - JSX 加 `<TokenMonitorPanel open={usageOpen} onOpenChange={setUsageOpen} />`
- icon 选 'activity'（MAP 中无 'chart'，activity 是 lucide 标准 metrics 替身）

### Step 8: vitest (3 路径)
- 新文件 `src/frontend/src/components/settings/__tests__/TokenMonitorPanel.test.tsx`
  - `renders 3 cards with window labels (1h/24h/7d)` — 锁 3 data-testid
  - `fetches /api/usage/global?window=1h|24h|7d on open` — 锁 3 端点 URL
  - `displays total_tokens for each card after fetch resolves` — 锁 3 卡片都展示 total
- **结果**: 3/3 绿 (vitest output: "3 tests passed 44ms")

### Step 9: 04-commands §六 BDD 冻结
- `docs/specs/04-commands_命令接口.md` 加 §6.4.8 B-4-P2-T6
  - 场景 ID / 入口 / Given / When / Then-1~3 / 实现位置 / 测试
  - 引用 backend + frontend 文件位置

---

## 2. 验证汇总

```bash
# Backend
cd src/backend && pytest tests/test_usage_global.py -v
# 3 passed in 6.83s OK

# Frontend
cd src/frontend && npx vitest run src/components/settings/__tests__/TokenMonitorPanel.test.tsx
# 1 passed (3 tests) 44ms OK

# 全套 vitest
cd src/frontend && npx vitest run
# 20 files | 19 passed | 1 failed (pre-existing WebPreviewCard gap, 与本 session 无关)
# 105 tests | 103 passed | 2 failed (同 pre-existing)
# 新增 3 全过 OK
```

---

## 3. 关键 commit

```
67d9a64 docs(specs): 04-commands §6.4.8 B-4-P2-T6 Token 监控 BDD 场景
85a411c feat(frontend): TokenMonitorPanel + NavRail 用量入口 (t6 B-4-P2-T6)
2fd2392 feat(backend): /api/usage/global 全平台 Token 聚合 (t6 B-4-P2-T6)
```

main HEAD = `67d9a64`，ahead of origin/main = 15 commit（**未 push** per no-push-without-ask）。

---

## 4. 关键不变量（遵守）

1. **commit-per-task** — backend 1 commit + frontend 1 commit + docs 1 commit（3 颗粒）
2. **BDD+TDD 双循环** — backend 1 spec + 1 test + 1 impl；frontend 1 spec + 1 test + 1 impl
3. **不写 emoji** — commit message + 代码无 emoji
4. **Python 禁同步阻塞** — 新 method 全 async
5. **TypeScript 禁 `any`** — UsageResp 用 interface
6. **pre-commit hook 必过** — 没碰过 `--no-verify`
7. **30 min cap** — 14 min 完成，远低于 cap
8. **不主动 push** — 15 commit ahead of origin

---

## 5. 经验教训

1. **worklog 先行** — 前一会话已写 8 步实施计划 + 完整代码片段，本 session 几乎照搬实施，节省 30+min 调研
2. **复用既有 helper** — Postgres impl 复用 `_bucket_sum` 私有方法，仅 2 个新 method，无需重复
3. **icon 选择** — 实施时发现 MAP 中无 'chart'，改用 'activity'（语义接近，lucide 标准）
4. **DDL 风险回避** — 不需新 alembic migration（沿用既有 UsageRecordModel），降低风险

---

## 6. 给下一位的关键交接

- **t6 完整落地** OK，3 commit + 6 new tests 全过
- **STATUS.md 待同步**（顶部时间戳 + 袁那行追加 3 commit 摘要）
- **next gate**：t12 (30min) 或 t7 (60min) — t12 风险低、产出实物（截图）
- **距 22:30 downscope 闸门 ~2.5h**，可推 t12 + 部分 t7
- **2 个 WebPreviewCard fullscreen 测试失败 = pre-existing gap**，属 t10 M3/M4 inbox 视觉补范围，本 session 不修
- **未做**：t7 搜索/置顶/归档（4-6h scope，60min downscope 仅搜索+置顶）/ t10 v6 视频（workload 大，2h+）

---

## 7. 关联引用

- [STATUS.md](../../STATUS.md) line 3 顶部时间戳 + line 9-10 袁那行
- [worklogs/yuan/2026-06-08_t1t2t4-harvest.md](2026-06-08_t1t2t4-harvest.md) — t1/t2/t4 cherry-pick 收尾
- [worklogs/yuan/2026-06-08_day2-pipeline-claude-team-mode.md](2026-06-08_day2-pipeline-claude-team-mode.md) — Day 2 pipeline 起点
- [docs/plan/day2-pipeline-v2/README.md §3 t6](../../docs/plan/day2-pipeline-v2/README.md) — t6 brief
- [docs/specs/04-commands §6.4.8](../../docs/specs/04-commands_命令接口.md) — B-4-P2-T6 BDD 场景
- src/backend/app/api/routers/usage.py — /api/usage/global 端点
- src/backend/app/application/services/usage_service.py — aggregate_global method
- src/backend/app/domain/repositories/usage_repository.py — 抽象接口
- src/backend/app/infrastructure/repositories/usage_repository.py — Postgres impl
- src/backend/tests/test_usage_global.py — backend 3 测
- src/frontend/src/components/settings/TokenMonitorPanel.tsx — 监控 panel
- src/frontend/src/components/layout/NavRail.tsx — 用量入口
- src/frontend/src/components/settings/__tests__/TokenMonitorPanel.test.tsx — frontend 3 测
