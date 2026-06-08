# 05 · owner 一次性指令（你 12:30 启动流水线时给我）

```
我要跑一个 Day 2 综合收尾流水线，改 12 个 track。你是 owner（Claude Code session 兼 team lead）。

请执行：
1. 读 STATUS.md + docs/plan/开发清单_roadmap.md + docs/specs/04-commands_命令接口.md §六
2. 读 worklogs/decisions/0008-self-governance-authorization.md + 0015-day2-pipeline-claude-team-mode.md
3. TeamCreate agenthub-day2-team（description: "AgentHub Day 2 12-track 综合收尾流水线"）
4. TaskCreate 12 次（按 docs/plan/day2-pipeline-v2/README.md §3 顺序，1 task per track）
5. CronCreate 20 min 心跳（cron="*/20 * * * *"，prompt 见 docs/plan/day2-pipeline-v2/04-heartbeat-cron-prompt.md）
6. 用 Agent tool 派第一个 subagent worker（t1-preview-modes，🔴 最高）：
   - subagent_type="general-purpose"
   - isolation="worktree"（独立 ../wt-t1-preview-modes）
   - prompt = 01-worker-prompt.md 完整内容 + 派单追加段（track 名 + 时间 + worktree 路径 + 回报方式）
7. 一直跑，直到 TaskList 全 completed 或 user touch pause.flag
8. owner = 我（袁 / xiangbianpangde），只在以下情况打断：
   - 整体 done
   - 连续 3 track 失败
   - CONTRACT_GAP 累积 ≥ 3
   - 22:30 强制 downscope 闸门触发
   - t3 MCP P3 Reviewer SLA 决策（22:30 强制 A/B）
   - t11 飞书 OAuth user-blocked
   其他时候我只读 STATUS + worklog

worker 提示词在 docs/plan/day2-pipeline-v2/01-worker-prompt.md
orchestrator 主循环伪代码在 docs/plan/day2-pipeline-v2/02-orchestrator-prompt.md
deliverable.md 模板在 docs/plan/day2-pipeline-v2/03-deliverable-template.md
heartbeat 提示词在 docs/plan/day2-pipeline-v2/04-heartbeat-cron-prompt.md
审计清单在 docs/plan/day2-pipeline-v2/06-owner-audit-checklist.md

开跑。
```

## 启动前 30 秒自检
- [ ] `git status` 干净（避免 worker 改文件跟你的本地变更冲突）
- [ ] `git log --oneline -3` 显示 main HEAD 包含 overnight 4 track + finalize 收束（`a597e31` 之后）
- [ ] `git config user.name` = `xiangbianpangde`（袁）
- [ ] baseline 测通过: `cd src/backend && python -m pytest tests/ -q` → 168/168 绿
- [ ] baseline 测通过: `cd src/frontend && npx vitest run` → 85/85 绿
- [ ] `STATUS.md` 当下行格式正确（已知 gap #1-#8 + overnight 收束段齐全）
- [ ] `worklogs/yuan/` 目录存在且可写

## 启动后守 5 分钟
- [ ] `TeamCreate agenthub-day2-team` 成功（owner 看到 team 在 TaskList 上下文）
- [ ] `TaskCreate` 12 次全部完成（TaskList 显示 12 track + 各自 task_id）
- [ ] `CronCreate` 20 min 心跳注册成功（用 `CronList` 能看到 agenthub-day2-monitor）
- [ ] 第一个 subagent 已派出（Agent tool 返回的 session id 记录在 STATUS 袁那行）
- [ ] 独立 worktree 已创建: `git worktree list` 包含 `../wt-t1-preview-modes`

全过就关电脑睡觉。
