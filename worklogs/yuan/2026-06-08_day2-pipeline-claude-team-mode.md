# 2026-06-08 Day 2 Pipeline 改造 + t8/t9 落地 - session 总结

> **写于**: 2026-06-08 18:45 (Asia/Shanghai)
> **作者**: 袁 (xiangbianpangde, owner per ADR-0008)
> **会话时长**: 17:30 - 18:45 (75 min)
> **目的**: 记录本 session 3 大交付 + t6/t7/t10/t12 移交计划

---

## 本 session 完成 (3 track + 1 架构改造)

### 1. Day 2 流水线 mavis → Claude Code team mode 改造 (commit 8a32930)
- 7 份 `docs/plan/day2-pipeline-v2/{README, 01-06}.md` 全部改写
- mavis CLI primitives → Claude Code 原生（TeamCreate / TaskCreate / SendMessage / CronCreate / CronList）
- ADR-0015 记录迁移决策 + mavis plan engine 强收无效教训
- 仍保留: 4 条不变量 + 7 失败信号 + 30 min cap + 22:30 闸门 + worktree 强制隔离

### 2. t8-desktop-specs-4q 桌面 App specs §十二 4 Q 答完 (commit 58465e0)
- 黎之前 blocked 在 PR-01 闸门（[STATUS.md line 113-114](../../STATUS.md)）
- 4 Q 答稿: Q5-1 通知 v0.1 stub + v0.2 真实 / Q5-2 JWT 体系 + 内存 token / Q7-1 v0.1.0-desktop-preview 30 天 preview / Q11-1 PWA 降级
- 7 条新 AC（AC-5.2.x/7.1.x/11.1.x）
- 交接 worklog: `worklogs/黎/2026-06-08_桌面specs-4q-answered.md`
- 仍需董/黎 Reviewer Approve 才能转正式

### 3. t9-usage-router-register /api/usage router 注册修复 (commit ca7e33f)
- `src/backend/app/main.py`: import list 加 usage + `app.include_router(usage.router)`
- 3 路径 smoke test: `src/backend/tests/test_usage_router.py`
- 9/9 绿 (health + attachments + usage_router)
- 30 min 准时 ticket，commit + merge 一次性完成

---

## t6/t7/t10/t12 移交（未完成）

### t6-m5-5-3-token-ui (Token 监控 UI) — 已写实施计划
- **当前**: TODO 注释已加到 `usage_service.py`
- **下一步**: 详见 `worklogs/yuan/2026-06-08_t6-token-monitor.md`（8 步实施计划）
- **预计工时**: 2-3 h（后端 1h + 前端 1h + E2E 1h）

### t7-conversation-list-features (搜索/置顶/归档) — 未开始
- 状态: 已知 PRD "部分" 标项，需后端 alembic + 前端
- 工时: 4-6 h
- 下次 session 起点: `LeftPanel.tsx` + `sessions.py` + alembic 0015

### t10-m6-finalize (M6 v6 视频 + README + M3/M4 inbox 视觉) — 未开始
- 状态: 分散大工作量
- 拆 3 子 track: v6 视频 (Playwright 重录) + README (5 张截图) + M3/M4 inbox 视觉补
- 工时: 6-8 h

### t12-pin-auth-screenshot (e2e 兜底截图) — 未开始
- 状态: 需 docker build backend 15-20 min + uvicorn :18010 + Playwright
- 工时: 30 min
- 步骤: `docker compose -f src/docker/docker-compose.yml up -d --build backend` → uvicorn --reload → Playwright

### t3-mcp-p3-reviewer (PEND 24h SLA) — 需董/黎 Reviewer Approve
- 状态: 24h SLA 至 2026-06-08 23:03
- 22:30 强制 A/B 决策: A=alembic 0006 / B=ADR-0015 docs-only
- 下次 session: 路径 A → 4 测 + alembic + McpServerCreate dry-run

### t11-feishu-oauth — user-blocked
- 状态: 等 user OAuth `https://open.feishu.cn/page/cli?user_code=8Q6R-NK2R`
- 不阻塞主收束，候补

---

## Commit 流水（本 session）

```
8a32930 merge: day2-pipeline-v2 改 Claude Code team mode + ADR-0015
439a17b docs(plan): day2-pipeline-v2 改造为 Claude Code team mode
58465e0 merge: t8 desktop specs 4 Q 答完 + 交接 worklog
5de64f9 docs(specs): 06-desktop §十二 4 Q 答完 (t8-desktop-specs-4q, 袁 owner 答稿)
ca7e33f merge: t9 /api/usage router register fix
7f198f0 fix(backend): 注册 /api/usage router (t9-usage-router-register)
```

Main HEAD = `ca7e33f` (ahead of origin/main by 5 commits, **未 push** per `no-push-without-ask.md`)

---

## 关键不变量（遵守）

1. **worktree 隔离** — 每 track 独立 worktree（修 gap #8 教训）
2. **不主动 push** — commit + merge main，user 显式说推才推
3. **30 min cap** — 单 track ≤ 30 min，超就 SCOPE_EXCEEDED + 拆
4. **不写 emoji** — CLAUDE.md 红线
5. **Python 禁同步阻塞** — repo 必须 async
6. **pre-commit hook 必过** — 不要 `--no-verify`
7. **BDD+TDD 双循环** — 04-commands §六 + 05-testing §二点五

---

## 给下一位的具体动作

1. **进 session 先读**: 本文件 + `worklogs/yuan/2026-06-08_t6-token-monitor.md` + `worklogs/decisions/0015-day2-pipeline-claude-team-mode.md`
2. **状态确认**: `git log --oneline -10` (main HEAD = ca7e33f, 5 新 commit, ahead of origin/main)
3. **下个 track 决策**:
   - 快速推进: t9 已 done，t6 next gate（按 day2-pipeline-v2/README §3 顺序）
   - 大工作量: t10 (M6 finalize) 拆 3 子 track 跑
   - 等决策: t3 (MCP P3 SLA) 等董/黎 Reviewer Approve
4. **PUSH 前**: 必问 user（per `no-push-without-ask.md`）

---

## 关联引用

- [STATUS.md](../../STATUS.md) — 袁那行 line 10 已含本 session 摘要
- [开发清单_roadmap.md](../../docs/plan/开发清单_roadmap.md) — 路线图进度
- [docs/plan/day2-pipeline-v2/](../../docs/plan/day2-pipeline-v2/) — 7 份 v2 提示词
- [worklogs/decisions/0015-day2-pipeline-claude-team-mode.md](../../worklogs/decisions/0015-day2-pipeline-claude-team-mode.md) — 架构迁移决策
- [worklogs/yuan/2026-06-08_t6-token-monitor.md](2026-06-08_t6-token-monitor.md) — t6 实施计划
- [worklogs/yuan/2026-06-08_t9-usage-router.md](2026-06-08_t9-usage-router.md) — t9 已完成
- [worklogs/黎/2026-06-08_桌面specs-4q-answered.md](../黎/2026-06-08_桌面specs-4q-answered.md) — t8 交接 worklog
