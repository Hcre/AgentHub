# 流水线提示词包 v2（Day 2 综合收尾 · 12 track · 6 段拆解 · Claude Code team mode）

> **用途**：袁（owner）在另一会话启动一个自驱多 track 流水线，把 12 个未完成项（用户图片直接指出的 2 个 bug + 移动 preview 4 模式 + MCP P3 + F1/F9 + M5 5.3 + 桌面 specs + M6 收尾 + 飞书同步候补）逐一落地，owner 不在场，全靠 Claude Code team mode（TeamCreate / SendMessage / TaskCreate / CronCreate）+ 独立 git worktree 三方守约。
> **生成日期**：2026-06-08（v2 → 2026-06-08 v2-claude-team 改写）
> **配套文件**：本目录下 `01-worker-prompt.md` / `02-orchestrator-prompt.md` / `03-deliverable-template.md` / `04-heartbeat-cron-prompt.md` / `05-owner-kickoff.md` / `06-owner-audit-checklist.md`
> **运行时序**：owner 跑 `05-owner-kickoff.md` → TeamCreate + TaskCreate 12 项 → 派 subagent worker（`01`）→ worker 写 deliverable（`03`）→ CronCreate 20min 守心跳（`04`）→ owner 早上跑 `06` 审计
> **迁移来源**：[ADR-0015](../../../../worklogs/decisions/0015-day2-pipeline-claude-team-mode.md) — 从 mavis team plan engine 迁到 Claude Code team mode

---

## 0. 心智模型（4 条不变量）

1. **不积压** — 每个 track 一退场立刻 chain 下一个；进度实时落 `STATUS.md` + `worklogs/yuan/` + Claude Code 共享 TaskList（owner + worker 全可见）
2. **不越界** — worker 报 `CONTRACT_GAP` / `DOWNSCOPE_TAKEN` / `SCOPE_EXCEEDED` 时 owner 不替它改契约/拆分，只记 STATUS、继续 chain
3. **不黑盒** — 失败 deliverable.md 不删，留作 owner 审计；不写空话 todo
4. **不等人** — worker 退出 → 立刻派下一个；worker 卡死 30 min → cron abort + chain；owner 不在时不主动打扰

---

## 1. Claude Code 原生工具映射（mavis → Claude Code）

> **mavis team plan engine 在 2026-06-07 plan_ba86c4d0 强收时已被验证 `plan.status=failed` 不可逆**（[ADR-0014](../../../../worklogs/decisions/0014-mavis-team-plan-ba86c4d0-strong-close.md)）。本流水线改用 Claude Code 原生 team primitives，理由见 ADR-0015。

| 原 mavis CLI | Claude Code 等价 | 用途 |
|--------------|------------------|------|
| `mavis team plan new` | `TeamCreate` + `TaskCreate`（12 次） | 初始化 team + 12 track 任务 |
| `mavis communication send --to <worker>` | `SendMessage(type=message, recipient=<worker_name>)` | 派单 / worker 回报 |
| `mavis team plan decision` | `TaskUpdate(taskId, status)` | 标 done / failed / blocked |
| `mavis cron self <name> --every 20m` | `CronCreate(cron="*/20 * * * *", prompt="...")` | 心跳监控 |
| `mavis cron list` | `CronList` | 看当前 cron 状态 |
| `docs/plans/_orchestrator/progress.json` | `TaskList` / `TaskGet` | 看每 track 状态 |
| `git checkout <branch>` 共享 working tree | `git worktree add ../wt-<track> feature/<branch>` | 强制 worktree 隔离 |
| worker 跨进程 IPC | `SendMessage` 同 team 内部通信 | 跨 worker 通信 |

> **关键差异**：Claude Code team mode 没有"独立 worker session 派发"概念；每 worker = 一个 subagent，通过 `SendMessage` 派活，TaskList 全员共享。owner 即 team lead。

---

## 2. 一句话项目

**AgentHub Day 2 综合收尾** = 12 个未完成 track（用户图片直接指出 2 bug + STATUS 已知 gap #6-#8 + 移动 preview 4 模式 + MCP P3 闸门 + F1/F9 PRD 必修 + M5 5.3 + 桌面 App specs 解阻塞 + M6 v6 视频/README + 飞书 OAuth）。overnight plan (`plan_3eaba0fa`) 已落 19 commit 收 4/5 track，本 plan 把剩 12 track 全清空。owner 据此 push main 12+ commit，22:30 downscope 闸门。

## 3. 12 track 清单（按依赖拓扑排）

| # | track | 类型 | 优先级 | 必读 scope | 备注 |
|---|-------|------|--------|------------|------|
| 1 | t1-preview-modes | bug fix（图片）| 🔴 最高 | `src/frontend/src/components/preview/previewModes.ts:19-21` | diff/deploy/webpage 3 个 enabled:false |
| 2 | t2-createagent-502 | bug fix（图片）| 🔴 最高 | `src/frontend/src/components/agent/CreateAgentModal.tsx` | 502 → 优雅空状态 |
| 3 | t3-mcp-p3-reviewer | 决策 + 实施 | 🟡 高 | `docs/specs/04-commands_命令接口.md` §2.6 | 22:30 强制 A/B 决策 |
| 4 | t4-f1-s1-suggestion | bug fix | 🟡 高 | `src/frontend/src/components/chat/ChatView.tsx` | 3 建议按钮真接 backend |
| 5 | t5-f9-s2-pin-copy | bug fix | 🟡 高 | `src/frontend/src/components/group/GroupMessageItem.tsx` | 群聊 Pin/复制代码 |
| 6 | t6-m5-5-3-token-ui | 新功能 | 🟡 中 | `/api/usage` 端点 | 监控 UI 暴露 |
| 7 | t7-conversation-list | 新功能 | 🟢 中 | LeftPanel.tsx | 搜索/置顶/归档 |
| 8 | t8-desktop-specs-4q | docs | 🟢 中 | `docs/specs/06-desktop-app_桌面App规格.md` §十二 | 解 黎 blocked |
| 9 | t9-usage-router | bug fix | 🟢 中 | `src/backend/app/main.py` | 30min ticket |
| 10 | t10-m6-finalize | 综合 | 🟢 中 | 视频 + README + M3/M4 inbox | 分散工作量 |
| 11 | t11-feishu-oauth | 候补 | ⚪ 候补 | lark-cli + user OAuth | user-blocked |
| 12 | t12-pin-auth-screenshot | 兜底 | 🟢 低 | e2e 截图缺失 | 修 gap |

**跳过条件**：overnight 4 track 已 done（Pin auth / Token 监控 / CLI scheduler / 移动 H5 响应式 / CI gate / MCP P3 F3 spec 冻结 — 后者走 t3 决策）。

---

## 4. 硬约束（6 段提示词共享）

- **单独成文**：6 份独立文件，不交叉引用细节（只引契约/ADR/STATUS 链接）
- **引用不重写**：schema 字段 → 引用 `docs/specs/04-commands_命令接口.md`；决策 → 引用 `worklogs/decisions/`
- **track 名/字段名/事件名与 `docs/specs/04-commands` §2.6 字面一致**
- **worktree 隔离**（修 gap #8）：每 track 必 `git worktree add ../wt-<track> feature/<branch>`，**不共享 working tree**
- **commit 风格**：Conventional Commits，scope 必填（`fix(frontend): ...` / `feat(backend): ...` / `docs: ...`）
- **每 commit 必过 pre-commit hook**（不要 `--no-verify`）
- **中文文件名，正文 ≤ 300 行**
- **用 Read/Write/Edit，不用 PowerShell Get-Content**（cp936 损坏 UTF-8）
- **真功能自验证**：
  - BDD 必写（Given/When/Then）到 `docs/specs/04-commands_命令接口.md` §六
  - 单测必写（pytest + vitest）+ 必跑通
  - Playwright E2E 截图必落 `docs/deliverables/screenshots/e2e-<track>-2026-06-09.png`
- **不重写契约/PRD/ADR**（发现需改 = deliverable.md 标 `CONTRACT_GAP`）
- **单 session 不超 30 min**（超即 deliverable.md 标 `SCOPE_EXCEEDED`，owner 拆）
- **per CLAUDE.md 工程红线**：不写 emoji / Python 禁同步阻塞 / TS 禁 `any` / 禁裸 `print` / 禁裸 SQL

---

## 5. 失败信号（写入 deliverable.md + TaskUpdate 同步）

| 信号 | 含义 | orchestrator 动作 |
|------|------|--------------------|
| `SCOPE_EXCEEDED` | 30 min 内写不完 | TaskUpdate status=completed + label=failed；chain 下一个（owner 拆） |
| `CONTRACT_GAP` | 发现需改契约/PRD/ADR | TaskUpdate label=contract-gap；记 STATUS，不修，chain；累计 ≥3 停 |
| `DOWNSCOPE_TAKEN` | 接受 §5 downscope 决策 | TaskUpdate status=completed label=downscope；记 deliverable，chain |
| `INNOVATION_GAP` | 无任何调研素材引用 | TaskUpdate label=innovation-gap；记 STATUS，chain（不阻塞） |
| `TEMPLATE_MISSING` | 模板段缺失 | TaskUpdate status=completed label=failed；chain |
| `NAME_MISMATCH` | 模块名/字段名与 contracts 不一致 | TaskUpdate status=completed label=failed；chain |
| `WORKTREE_RACE` | 共享 working tree 触发覆盖 | TaskUpdate status=pending → 重派 + 强 worktree 隔离 + chain |

---

## 6. 一次性启动 vs 每日审计

- **12:30 启动**：owner 跑 `05-owner-kickoff.md` → TeamCreate `agenthub-day2-team` + TaskCreate 12 track + CronCreate 20min 心跳 + 派 `t1-preview-modes` worker subagent
- **次日早上审计**：owner 跑 `06-owner-audit-checklist.md` → 5 分钟看 4 处文件
- **3 连败 / 整体 done / CONTRACT_GAP ≥ 3**：orchestrator 主动 SendMessage 给 owner
- **22:30 强制 downscope 闸门**：仍剩 ≥3 track 未 done → 强制 downscope Track 7/8/10/11/12，保留 1-6 + 9

---

## 7. 必读资源（每个 worker 启动时 Read）

1. `STATUS.md`（项目状态 + Git↔人名映射 + 已知 gap #1-#8 + overnight 收束段）
2. `docs/plan/开发清单_roadmap.md` §1/§6/§8 + §▶接手指引
3. `docs/conventions/CLAUDE-规范导航.md`（AR/CR/PR/AP/T/D 红线速查）
4. `docs/specs/04-commands_命令接口.md` §六（17 BDD 场景 + 新加 12 个 track 场景）
5. `docs/conventions/05-testing_测试规范.md` §二点五（BDD+TDD 双循环）
6. `docs/reports/test-report-2026-06-08.html`（overnight 报告参考样式）
7. `worklogs/yuan/2026-06-07_t2-cli-scheduler.md` + `2026-06-08_t3-mobile-h5.md` + `2026-06-08_mcp-p3-f3-spec-freeze-reviewer-pending.md`（最近 worklog 风格）
8. `git log --oneline -20` 了解最近上下文
9. `git config user.name` 确认身份（应为 xiangbianpangde → 袁）

任何修改前先看邻近文件 + 同 commit 风格。
