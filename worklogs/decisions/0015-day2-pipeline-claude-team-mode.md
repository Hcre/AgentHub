# ADR-0015: Day 2 流水线从 mavis team plan engine 迁到 Claude Code team mode

**Date**: 2026-06-08 17:30 (Asia/Shanghai)
**Author**: 袁 (xiangbianpangde, owner)
**Status**: Accepted (per ADR-0008 自主决策授权)
**Related**:
- [ADR-0014 plan_ba86c4d0 强收](0014-mavis-team-plan-ba86c4d0-strong-close.md) — mavis plan engine `plan.status=failed` 不可逆教训
- [ADR-0008 self-governance](0008-self-governance-authorization.md) — owner 自主决策 gate
- [docs/plan/day2-pipeline-v2/](../../docs/plan/day2-pipeline-v2/) — 7 份提示词 v2 全部基于本 ADR 改写

## Context

overnight plan (`plan_3eaba0fa`) 落 19 commit 收 4/5 track（[STATUS.md](../../STATUS.md) line 10 + 166-170）；剩 12 track 等 12:30 启动新流水线。原计划是 mavis team plan engine + Mavis orchestrator（详见 `docs/plan/team-plan-brief-2026-06-08-v2.md`），但有两个新发现让 mavis 路径不再合适：

### 关键发现 1：mavis plan engine 强收无效（[ADR-0014](0014-mavis-team-plan-ba86c4d0-strong-close.md)）

- `mavis team plan decision --file plan_complete=true.json` 只落 audit log，**engine 终态是 failed 不再 process decision queue**
- 30 min cap 硬超时，1 feature per task 是上限
- cycle 6 evaluating stall 42+ min 是真实失败，**无法用 CLI 强收兜底**
- 现实约束：Mavis daemon 5/30 崩 + worker in-flight 全丢 是已知风险（mavis-team-pitfalls §9）

### 关键发现 2：mavis plan engine 跨 worker 共享 working tree 触发覆盖（gap #8）

- plan_3eaba0fa 5 worker 并行共享 working tree，5+ 次 `git checkout <other-branch>` 把 t4-mcp-spec 写好的 spec + worklog 改动 revert 掉
- 教训落 `t4-mcp-spec/atomic_commit.py` 归档 + mcp-detailed-designer MEMORY §15
- **mavis 引擎不强制 worktree 隔离** → 每 worker 必须自觉 `git worktree add`

### 关键发现 3：当前会话即是 Claude Code session

- user message 显式说 "以符合claude code的team mode模式"
- Claude Code 提供 TeamCreate/TeamDelete/TaskCreate/TaskUpdate/SendMessage/CronCreate/CronList 等原生 primitives
- 比 mavis 跨进程 IPC 更原生：**subagent 在同 session context 共享 TaskList**，无 daemon 中间层崩溃风险
- worktree 隔离可由 `isolation: "worktree"` 参数强制（不再依赖 worker 自觉）

## Decision

**Day 2 综合收尾流水线（12 track）从 mavis team plan engine 迁到 Claude Code team mode**。具体 4 项决策：

### 决策 1：TeamCreate + TaskCreate 取代 mavis `team plan new`

- `mavis team plan new --plan-id plan_agenthub-m6-day2-comprehensive-2026-06-08 --brief-file ...` → `TeamCreate team_name="agenthub-day2-team"`
- `mavis team plan decision` 初始化 queue.json / progress.json → 12 次 `TaskCreate` 落 TaskList
- 优势：TaskList 全员可见（owner + subagent），无文件读写竞态；`TaskGet` 直接看单 task 详情

### 决策 2：SendMessage 取代 `mavis communication send`

- `mavis communication send --to <worker> --command prompt --content "..."` → `SendMessage(to=<subagent_name>, content="...")`
- 优势：SendMessage 同 team 内 subagent 互相可达；owner 可收 worker 回报 + worker 可主动 ping owner
- 跨 worker 通信也走 SendMessage（不再依赖 mavis IPC daemon）

### 决策 3：CronCreate 取代 `mavis cron self`

- `mavis cron self agenthub-day2-monitor --every 20m --prompt "..."` → `CronCreate cron="*/20 * * * *" prompt="..."`
- 优势：Claude Code 原生 cron 不依赖 mavis daemon 存活；`CronList` 直接看注册状态
- 20 min 心跳频率与原设计一致（12 track 比 overnight 4 track 密，gap #6 经验）

### 决策 4：worktree 隔离强制（修 gap #8）

- 每 subagent worker 启动时 `Agent tool` 传 `isolation: "worktree"` 参数
- Claude Code 自动 `git worktree add ../wt-<track> -b feature/<track>`
- 不共享 working tree 杜绝 5+ 次 git checkout 覆盖 race

## Mavis vs Claude Code 对照表

| 维度 | mavis | Claude Code team mode |
|------|-------|------------------------|
| 任务列表 | `docs/plans/_orchestrator/progress.json` | `TaskList` / `TaskGet` / `TaskUpdate` |
| 派单 | `mavis communication send --to <worker>` | `SendMessage(to=<subagent_name>, content=...)` |
| 派 worker 进程 | `mavis team plan new` (跨 session) | `Agent tool with subagent_type + isolation=worktree` (同 session subagent) |
| 心跳 | `mavis cron self` (依赖 daemon) | `CronCreate` (Claude Code 原生，不依赖 daemon) |
| 状态同步 | 文件 IPC + state.json | TaskList 内存共享 + TaskUpdate 事件 |
| 终态 | `plan.status=failed` 不可逆 | 无"plan 终态"概念，TaskList 持续可改 |
| 崩溃风险 | daemon 5/30 崩 in-flight 全丢 | Claude Code session crash 概率远低，subagent 失败可单独 retry |
| worktree 隔离 | worker 自觉（gap #8 触发 5+ 次覆盖） | `isolation="worktree"` 参数强制 |
| 跨 worker 通信 | mavis IPC daemon | `SendMessage` 同 team 内 subagent |
| owner 中断信号 | `pause.flag` 文件 touch | `pause.flag` 文件 touch + TaskUpdate batch |

## 影响

### 正面

- **plan 终态不可逆风险消除**：Claude Code 无"plan 终态"概念，TaskList 持续可改；即使单 track 失败，owner 决定 downscope 即可
- **崩溃域收窄到单 subagent**：Mavis daemon 崩全丢风险消除；subagent 失败可单独 TaskUpdate retry
- **worktree 隔离强制**：杜绝 gap #8 5+ 次 git checkout 覆盖 race
- **状态共享零开销**：TaskList 内存共享，无文件 IPC 竞态
- **跨 worker 通信原生**：SendMessage 同 team 内 subagent 互相可达，无需 mavis IPC

### 负面 / 后续 TODO

- **subagent 数量限制**：Claude Code 单 session 并行 subagent 数有上限（需查 harness 文档），12 track 不可全并行；保留"按依赖拓扑顺序派"策略
- **SendMessage 跨 session 不可达**：subagent 在不同 Claude Code session 时 SendMessage 不可用；本方案固定在 1 session 内派 12 subagent
- **CronCreate 跨 session 行为**：cron 触发的 prompt 在 owner session 上下文；如 session 结束 cron 失效
- **Mavis plan engine 已写 ADR-0014 沉淀**：mavis 仍是 fallback 路径（长程 daemon-based 任务仍可用 mavis）；本 ADR 只迁 day2-pipeline-v2 这一处

### 后续 roadmap

| 时机 | 任务 | 责任人 |
|------|------|--------|
| 12:30 启动 | 跑 05-owner-kickoff.md → TeamCreate + TaskCreate 12 + CronCreate 20min + 派 t1 worker | owner |
| 12:30-22:30 | 12 track 跑完（按 README §3 顺序 t1-t12）| owner + 12 subagent |
| 22:30 | 闸门评估：剩 ≥3 未 done → 写 ADR NNNN-day2-downscope-2230.md + downscope 7/8/10/11/12 | owner |
| 明早 09:00 | 跑 06-owner-audit-checklist.md → 5 分钟看 4 处 | owner |
| 下次 plan | 把 mavis fallback 路径也用 Claude Code 重写（如有需要）| owner |

## 替代方案

### 方案 B：保持 mavis team plan engine

- 优势：mavis 已写 ADR-0014 沉淀（pitfalls §13）+ owner_takeover_discovery 自验证机制熟
- 不选原因：(a) plan.status=failed 不可逆，5/30 daemon 崩 in-flight 全丢；(b) worktree 隔离靠 worker 自觉，gap #8 已踩过；(c) user message 显式要求 Claude Code team mode

### 方案 C：单 session 串行（不 team mode）

- 优势：零架构依赖，最简单
- 不选原因：(a) 12 track 串行 10h+ 跑不完，22:30 必 downscope；(b) 没法利用 subagent 并行加速；(c) 中途崩溃全重来

### 方案 D：自建 orchestrator（用 LangGraph / CrewAI / AutoGen）

- 优势：完全可控，可定制
- 不选原因：(a) Claude Code 原生 primitives 已覆盖 80% 需求；(b) 自建需 1-2 周开发 + 长期维护；(c) user 偏好"用现成工具不造轮子"

## 实施清单

1. ✅ 改写 `docs/plan/day2-pipeline-v2/README.md` — 加 §1 Claude Code 原生工具映射表
2. ✅ 改写 `01-worker-prompt.md` — `mavis communication send` → `SendMessage` + `TaskUpdate`
3. ✅ 改写 `02-orchestrator-prompt.md` — `mavis team plan new` → `TeamCreate` + `TaskCreate` + 伪代码重写
4. ✅ 改写 `03-deliverable-template.md` — 加 `TaskList ID` + `SendMessage 报回` 段
5. ✅ 改写 `04-heartbeat-cron-prompt.md` — `mavis cron self` → `CronCreate` + 行为对齐
6. ✅ 改写 `05-owner-kickoff.md` — 启动序列重写为 TeamCreate/TaskCreate/CronCreate
7. ✅ 改写 `06-owner-audit-checklist.md` — 审计源 `progress.json` → `TaskList`
8. ✅ 写本 ADR-0015 落档
9. ⏳ commit 7 文件 + 本 ADR → push main（per agent memory `merge-to-main-approved.md` 常驻 merge main 权限 + `no-push-without-ask.md` 默认不 push）

## 给下一位的交接

- **接手起点**：`docs/plan/day2-pipeline-v2/05-owner-kickoff.md` — owner 12:30 启动时把那段 prompt 整段发给 Claude Code session
- **关键不变量**：
  1. TaskList 全员可见 → subagent 报回 owner 时附带 task_id
  2. worktree 隔离强制 → 每 subagent 启动必须 `isolation="worktree"`
  3. 30 min cap 硬超时 → 1 feature per task 安全，3+ features 高风险
- **常见陷阱**：
  - 跨 subagent 共享 working tree 会触发 gap #8 race（必须 worktree 隔离）
  - 22:30 闸门是硬闸门，不要等到 23:00 才评估
  - t11 飞书 OAuth 是 user-blocked，不阻塞主收束
  - 失败 deliverable.md 不删，留作 owner 审计
- **失败恢复**：如 day2-pipeline-v2 流水线中途崩（如 subagent 死锁），owner 重启 session 跑 `mavis team plan resume` 等价物 = TaskList 状态恢复（TaskList 持久化在 Claude Code session context）

## References

- [STATUS.md](../../STATUS.md) line 10 + 166-170 — overnight 19 commit 收 4/5 track
- [开发清单_roadmap.md §六/§八/§▶接手指引](../../docs/plan/开发清单_roadmap.md)
- [docs/plan/day2-pipeline-v2/](../../docs/plan/day2-pipeline-v2/) — 7 份 v2 提示词
- [ADR-0014 mavis plan ba86c4d0 强收](0014-mavis-team-plan-ba86c4d0-strong-close.md) — 教训源头
- [ADR-0008 self-governance](0008-self-governance-authorization.md) — owner 自主决策 gate 流程
- agent memory `no-push-without-ask.md` — 默认不 push
- agent memory `merge-to-main-approved.md` — 袁授权常驻 merge main
- agent memory `feedback-30min-task-scope.md` — 30 min cap 拆分
- agent memory `feedback-mavis-cron-self.md` — 长程 plan cron self 监控
- mavis-team-pitfalls.md §9/§13 — daemon 崩 / plan.status 强收无效
