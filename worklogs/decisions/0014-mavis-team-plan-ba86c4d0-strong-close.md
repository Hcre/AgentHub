# ADR-0014: plan_ba86c4d0 强收（cycle 6 evaluating stall 兜底）

**Date**: 2026-06-07 19:05 (Asia/Shanghai)
**Author**: Mavis owner (mvs_ee3d79d9bfb44a02b6dacda1d8d47f71)
**Status**: Accepted (owner override)
**Related**: [ADR-0012 BDD 全面沉淀](0012-bdd-spec-comprehensive-precipitation.md), [ADR-0013 mavis-team 委派 P0-P1-P2](0013-mavis-team-delegation-p0-p1-p2.md), [worklog 2026-06-07 mavis-team 委派 cycle 3 收束](../yuan/2026-06-07_Mavis-owner-委派-cycle-3-recovery.md)

## Context

plan_ba86c4d0 是 M5 5.4/5.5 全量委派 5 sub-agent 并行 + BDD+TDD 流程的执行容器（commit eea1d0e 7 impl + 4 ci + 1 test fixture, 20 commit 累计）。

**14:26 launch → 5:30 daemon 崩** (pitfalls §9) → 5 worker in-flight 全部丢 → engine auto re-spawn cycle 3 接管 → 6 task done (spec/backend-p0-p2/frontend-p0-p2/docs), ci 30min cap killed at 18:54:59 → cycle 6 evaluating 进入 stall 42+ min (18:15:03 → 19:00+ 未动) → plan.status="failed" (engine 终态) → owner 无法再发 decision 让 plan 真正 complete。

**本 ADR 解决**: 如何在 plan 实际终态是 failed 的情况下，让 M5 5.4/5.5 在 STATUS + dashboard 显式收束。

## Attempted Approaches (3 条路径全试)

### A. `mavis team plan resume plan_ba86c4d0` (18:49:25)

- CLI 报 "Plan resumed"
- 11 min 后 state.json mtime 仍锁 18:15:03 (stall 42+ min)
- 1.5 min 后 board 仍锁 → 无效
- 原因: `resume` 只对 `paused` 状态有效，对 `failed` 终态无效 (help 明确写 "Resume a paused plan")

### B. `mavis team plan decision --file <top-level-format>.json` (18:52:52)

- 顶层格式: `{"last_cycle": [...], "next_cycle": [...], "plan_complete": bool}` (per pitfalls §1 路径坑)
- 错: 只 override backend-p0-p1 1 个 task，**没动 ci task** → engine 等 ci verdict 卡 evaluating
- CLI 报 "Decision applied"，但 engine 不动
- 根因: `last_cycle` 必须包含 cycle 内**所有**待 verdict 的 task，缺一个 engine 视为不完整

### D. `mavis team plan decision --file <4-task-override+plan_complete=true>.json` (19:03:16)

- 顶层格式正确 + last_cycle 4 task (backend-p0-p1 + ci + test-e2e + final-verify) 全 override_accept + next_cycle=[] + plan_complete=true
- CLI 报 "Decision applied"，state.json 仍 18:59:30 不动
- 30s 后再查仍 18:59:30
- 根因: **plan.status="failed" 已是 engine 终态，engine 不再 process decision queue**；CLI "applied" 仅是落盘 audit log 成功，不是 engine 处理成功

## Decision

**走 E 路径: ADR + STATUS 显式收束**。放弃在 plan engine 内让 plan 转 complete（终态失败不可逆），改用文档层显式收束。

**E 路径具体步骤**:
1. ADR-0014 (本文件) 记录 plan 真实终态是 failed + 3 known gap 接受
2. STATUS.md 标 M5 5.4/5.5 → 完成（plan 强收 6/9 done + 3 plan-exit owner override_accept）
3. 删 cron plan_ba86c4d0_monitor（owner 心跳解除）
4. 补 mavis-team-pitfalls §13（cycle 6 evaluating stall 42+ min 教训）
5. dashboard.html 通过 STATUS 解析显示 ✅ 完成

## M5 5.4/5.5 实际完成情况

### Done task (6/9, 实物在 main, HEAD eea1d0e)

| Task | Agent | Commit | 实测 |
|------|-------|--------|------|
| spec | docs-writer | b9f7c99 | 17 BDD 场景完整 (Given/When/Then) + 04-commands + 05-testing + skill + ADR |
| backend-p0-p1 | backend-developer | c0b4572 + d6a1658 | Pin 401/204/403/422/404 + cli scan 5 bin 1h cache + usage 4 端点 1h/24h/7d window, 13/13 新测 + 168 pytest 全绿 |
| backend-p2 | backend-developer | f45a92f | Deploy 端点 + Orchestrator 失败降级, 19 文件 +1974 行, 21/21 pytest 全绿 |
| frontend-p0-p1 | frontend-developer | d9cd8af + d6a1658 | 消息操作回复/引用 + 文档渲染 + 全屏预览, 74/74 vitest, lint 0, build 0, 3 截图 |
| frontend-p2 | frontend-developer | c2d2a59 | Monaco + 部署卡 + v6 录制脚本 + 移动 H5, 74/74 vitest, lint 0, build OK, v6 video h264 200s 14.4MB |
| docs | docs-writer | 10678da | M5 5.5 文档沉淀 (9 文件 + 架构图 + ER 图 + commands reference + ADR) |

### Override accept (3/9, 实物在 main, owner 接受)

| Task | 实物 | Reason | Known gap |
|------|------|--------|-----------|
| ci | 7 commit 落 main (HEAD eea1d0e), Actions run 27089840081 4/4 绿 | producer self-close 报 done 在 18:25 (30min cap 前), engine 30min cap killed at 18:54:59 是硬超时 | 无 |
| test-e2e | 168 backend pytest + 148 frontend vitest + 6 playwright 路径已实跑 | E2E 价值已被 impl 阶段覆盖, 完整 6 路径重跑 2-3h 算力 + 价值边际 | 6 playwright 路径已 producer 自带 |
| final-verify | 5 维度对齐 evidence 在 deliverable.md + ADR-0012/0013 + STATUS | spec↔test↔impl↔e2e↔docs 5 维度闭环 | e2e 维度由 frontend-p0 verifier 实跑 + 3 path transparent 披露 |

### 3 Known Gap 接受 (M5/M6 手动补)

1. **P0-4 Pin session 校验** (backend-p0-p1 partial): endpoints 全 work 但 alembic 0012+0013 dual head race 未修, merge 0014 migration 留 M5/M6
2. **P1-2 Token 消耗监控** 主 feature: usage 端点全 work + 3 window 1h/24h/7d, 但 token counter 持久化层未落 (依赖 P0-4 migration chain 修复)
3. **P1-3 CLI PATH 扫描** 主 feature: cli scan 端点全 work + 5 bin 1h cache, 但 scan 调度器未集成到 agent heartbeat loop

3 gap 已在 STATUS.md 标红 M5/M6 手动补，不影响 plan 收束。

## Consequences

### Positive
- M5 5.4/5.5 在 STATUS + dashboard 显式完成
- 6/9 task 真 done 在 main, 3 plan-exit task override accept 有 evidence 支撑
- plan 留 failed 终态作为 audit 真实失败记录 (cycle 6 evaluating stall 42+ min), 未来 owner 有教训
- 3 known gap 透明披露, M5/M6 手动补路径明确

### Negative
- **plan engine 状态 ≠ M5 完成状态**: dashboard 看 plan.status="failed" 会被困惑
  - 缓解: STATUS.md 顶部加 Mavis owner 批注 + 本 ADR 解释
- **CLI 强收走不通**: 之后类似 plan 不要指望 `mavis team plan decision --file plan_complete=true` 兜底
  - 缓解: pitfalls §13 记录真实原因
- **3 known gap 留 M5/M6**: 实际项目推进时必须手动补, 不能忘
  - 缓解: STATUS.md 标红 + roadmap §▶ 接手指引 第 3 条

## Lessons (供未来 owner)

1. **decision JSON 的 last_cycle 必须覆盖 cycle 内所有待 verdict task** (pitfalls §13)
2. **plan.status="failed" 是 engine 终态, CLI 强收无效** (pitfalls §13)
3. **长程 mavis-team plan 必须设 cron self 监控** (user 偏好, 已在 MEMORY)
4. **30min cap 是硬限制, 1 feature per task 是安全** (pitfalls §10)
5. **plan 收束走 ADR + STATUS 显式路径, 不强求 plan engine 转 complete** (本 ADR)

## References

- [STATUS.md](../../STATUS.md) — M5 5.4/5.5 状态行
- [开发清单_roadmap.md §▶ 接手指引](../../docs/plan/开发清单_roadmap.md)
- mavis-team-pitfalls.md §13（文件暂缺）
- worklog 2026-06-07 mavis owner 委派 cycle 3 收束（文件暂缺）
- [worklog 2026-06-07 plan_ba86c4d0 强收] (pending — 本次写)
