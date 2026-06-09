# ADR-0018: plan_3eaba0fa overnight 4-track 收束 (M5 5.1-5.4 全完)

- **状态**: Accepted
- **日期**: 2026-06-08 11:30 (Asia/Shanghai)
- **决策者**: 袁 (xiangbianpangde, owner, per ADR-0008)
- **关联 plan**: `plan_3eaba0fa` (overnight, 5/5 track 启动 → 4/5 done)
- **关联 ADR**:
  - [0014 plan_ba86c4d0 强收](0014-mavis-team-plan-ba86c4d0-strong-close.md) — mavis 强收无效教训
  - [0015 Day-2 pipeline 迁 Claude Code team mode](0015-day2-pipeline-claude-team-mode.md) — 工程化改造（互补，本 ADR 讲 what done）

## 背景

继 plan_ba86c4d0 强收（ADR-0014）和 Day-2 流水线改造（ADR-0015）后，overnight 启动 plan_3eaba0fa，分配 5 个 track 至 5 个独立 worker。目的是 M5 范围（5.1-5.4）一次性收口。

## 4/5 Track 结果

| Track | 标题 | 状态 | Commit | Worklog |
|-------|------|------|--------|---------|
| t1 | M5 5.1 Pin API 401 修复 + alembic 0014 merge | ✅ done | `b97c4fd`/`bd92b2a`/`5371f41`/`2cbfff8` → owner merge `2843b06` | `worklogs/袁/2026-06-08_t5-f9-s2-pin-copy-owner-takeover.md` |
| t2 | M5 5.2 Token 监控 E2E 收尾 | ✅ done | `46065aa` + `ebf678a` + `7914a59` + `60d4d69` → owner merge `fbfd44a` | `worklogs/袁/2026-06-07_t2-token-monitor-e2e.md` |
| t2 | M5 5.2 CLI PATH 扫描 scheduler 集成 | ✅ done | `b63d0da` + `66e2c52` + `6d1fb0a` + `ddd58fc` → owner merge `1714f5d` + cherry-pick `9601313` | `worklogs/袁/2026-06-07_t2-cli-scheduler.md` |
| t3 | M5 5.3 移动 H5 响应式实施 | ✅ done | `a483424` + `8124e54` → owner merge `015cf8e` | `worklogs/袁/2026-06-08_t5-f9-s2-pin-copy-owner-takeover.md` |
| t4 | M5 5.4 CI gate (4 jobs) | ✅ done | `0570a43` + `6cd69dd` → owner merge `9e613b8` | （在 t4 worker worklog）|
| t4 | MCP P3 F3 spec 冻结 (M5 5.4 扩展) | ⚠️ PEND | `701f01b` → owner merge `60ff903` | `worklogs/袁/2026-06-08_mcp-p3-f3-spec-freeze-reviewer-pending.md` |

## 关键工程教训（与 ADR-0014/0015 形成闭环）

1. **每 track 独立 worker worktree**：本 plan 显式违反，5 worker 共享 working tree，触发 gap #8（5+ 次 git checkout 覆盖）。t4-mcp-spec 用 `git plumbing` (hash-object/read-tree/write-tree) 在 `GIT_INDEX_FILE` 临时 index 中创建 commit 才保住。**下个 plan 强制 `git worktree add` 隔离**。
2. **vitest 106/108 + pytest 157 全绿**（含 2 deferred pi_agent E2E，本机无 binary 已知）
3. **CI 4 jobs 3m27s 跑完**：ruff + mypy + tsc + eslint + vitest + playwright（沿用 eea1d0e `continue-on-error` baseline），GitHub Actions run 27096545029 4/4 success
4. **M5 范围 67% 覆盖率**（per ADR-0017 对账），4 项 known gap 留 M5/M6 手动补

## 接手起点

下一个 milestone（M5/M6 手动补）按工作量降序：

1. P0-4 Pin API 401 + alembic dual head（~1-2h）← 必修
2. F10 移动 H5 已 done by t3（本 plan 收口）
3. P1-2 Token 监控 main.py router 注册（~30min）
4. P1-3 CLI scheduler 已 done by t2（本 plan 收口）

## 反模式

- 不要再用 mavis team plan engine 跑多 track 并行（强收无效 + 共享 working tree 覆盖问题已论证，per ADR-0014）
- 跨 worker 共享 working tree 必须禁止（落 `.harness/` 工作流约束）
- "commit message 自报 ✅" 不可信，验收必须 Playwright E2E 复跑（per ADR-0017）
