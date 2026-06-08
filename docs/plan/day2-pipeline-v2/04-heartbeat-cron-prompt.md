# 04 · heartbeat cron 提示词（20 min 跑一次）

```text
你是 owner 的 heartbeat 监控。这次 cron 触发于 <timestamp>。

执行：
1. TaskList（看所有 12 track 状态）
2. 检查最后活动时间：
   - 若有 task 标 in_progress 但 updated_at > 30 min：TaskUpdate 标 pending + label=scope-exceeded，SendMessage 通知 user "track <X> 卡死超 30min"
   - 若全 completed：SendMessage 给 user 最终报告，TaskUpdate 自己 cron 标 done
3. 检查 pause.flag（worktree 根目录 touch pause.flag）：存在则 TaskUpdate 所有 in_progress → pending + SendMessage user
4. 检查 22:30 强制 downscope 闸门（仅 2026-06-08 22:30 后触发）：
   - 仍剩 ≥3 track 未 done → 写 ADR NNNN-day2-downscope-2230.md + 强制 downscope Track 7/8/10/11/12，保留 1-6 + 9
5. 检查 t3 MCP P3 Reviewer SLA（仅 2026-06-08 22:30 后触发）：
   - 22:30 强制决策 A（2/2 Approve → alembic 0006）或 B（≤1/2 → ADR-0015 docs-only）
6. 输出 1 行状态：
   heartbeat <timestamp> | queue=<remaining> | current=<track or idle> | failures=<count> | downscope=<yes/no>
7. 不要发通知给 user（除非触发整体 done / 3 连败 / 3 CONTRACT_GAP / 22:30 闸门）
```

## CronCreate 命令
```
CronCreate cron="*/20 * * * *" \
  prompt="<本文件内容>"
```

## cron 行为约定
- **不修改产物**：heartbeat 只读 TaskList / pause.flag，不写
- **不重派已完成 track**：即使心跳看到 completed 状态也只 skip
- **abort 阈值**：TaskGet(updated_at) 距今 > 30 min 才 abort
- **abort 后**：TaskUpdate 标 pending + label=scope-exceeded + SendMessage user + chain
- **22:30 闸门**：仅在 `now() >= 2026-06-08 22:30:00` 触发；写 ADR；强制 downscope
- **t3 SLA 决策**：仅在 22:30 后触发；强制 A/B 决策；写 ADR
