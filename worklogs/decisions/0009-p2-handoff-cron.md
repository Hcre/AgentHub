# 0009 明天 10 点兜底启动 P2 接力（plan_bc385bbe → MCP P3/P4）

- **日期**: 2026-06-06 23:31 (Asia/Shanghai)
- **触发方**: 用户口头指令「明天 10 点还没来报备，直接开始 p2 的开发（按同样流程）」
- **生效**: cron `p2-handoff-watch` 在 2026-06-07 10:00 Asia/Shanghai 触发

## 决策

- **触发条件**：2026-06-07 10:00 时，如果用户未到岗报备（root session 过去 1h 无 user 消息），自动启动 P2 接力
- **P2 范围（推断）**：MCP P3 F3 创建（6/7-6/9，34h，agent=mcp-developer）+ MCP P4 F5 展示（6/12-6/15，33h，agent=mcp-developer 或 coder）
  - 推断依据：
    - 「按同样流程」= 复制 plan_bc385bbe 结构（coder/verifier/general 编排 + 4 并发 + 12 cycle）
    - 题目「多 Agent 接入」/「minimax 全模态」= MCP 工具调用 + AI 多模态能力 = P4 F5 工具展示的天然场景
    - 袁本人在推 MCP P3/P4，但「P2」是 mavis team plan 接力术语
  - 若用户接管后异议：cycle decision 调整
- **P2 plan 路径**：`C:\Users\yhn\Desktop\字节比赛\AgentHub\.mavis\plans\plan-p2-handoff.yaml`
- **沿用 plan_bc385bbe 的工程规范**（per decisions/0008 自决授权）

## 触发时 owner 动作（cron prompt 内置）

1. 检查用户到岗：root session 自己过去 1h 有无 user 消息
2. 跑 `mavis team plan status plan_bc385bbe --human`
3. 写 P2 接力 plan.yaml（任务改成 MCP P3 + P4）
4. 启动 `mavis team plan run plan-p2-handoff.yaml --no-wait`
5. 把 P2 plan_id append 到 STATUS.md 「⏭️ 进行中交接」段
6. 写 `0010-plan-bc385bbe-p2-handoff.md` ADR 记录这次接力的实际触发 + 范围微调
7. 给用户发 alert（如果他在线会收到；不在线就发 IM 兜底）
8. 删自己：`mavis cron delete mavis p2-handoff-watch`

## 兜底

- 若 P2 plan.yaml 启动失败：fallback = 给用户发 IM 提示「P2 接力失败，请手动接管」
- 若用户 10:30 仍无消息 + plan_bc385bbe 还在跑：等 plan done 后立即启 P2，不打断用户
- cron TTL 14d（防 cron 永久残留）

## 关联

- decisions/0008（自决授权 + 上下文清理）
- agent memory「mavis team plan 多 worker 共享 git worktree」→ P2 plan 启动时强提示 worker 用 git worktree add 隔离
