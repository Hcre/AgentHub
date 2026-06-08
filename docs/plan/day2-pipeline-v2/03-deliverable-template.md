# 03 · deliverable.md 模板（worker 收尾必写）

```markdown
# Deliverable: <track_id>

**TaskList ID**: <task_id>（来自 TaskCreate 返回）
**status**: done | failed
**started**: <ISO>
**finished**: <ISO>
**duration_min**: <int>
**worktree**: ../wt-<track>（独立 git worktree 路径）
**branch**: feature/<track>

## 文件路径
- 代码改动:
  - <文件 1 相对路径>（<lines> 行改动）
  - <文件 2 相对路径>（<lines> 行改动）
- BDD scenario: `docs/specs/04-commands_命令接口.md` §六 <B-6-P2-T<N>>
- 单测:
  - pytest: <路径>（<N> 测全绿）
  - vitest: <路径>（<N> 测全绿）
- Playwright 截图: `docs/deliverables/screenshots/e2e-<track>-2026-06-09.png`
- worklog: `worklogs/yuan/<YYYY-MM-DD>_<track>.md`

## Commit 清单
- `<hash>` `<type>(<scope>): <msg>`
- `<hash>` `<type>(<scope>): <msg>`

## Merge 状态
- `git merge feature/<track> --no-ff -m "merge: <track> desc"` 已执行
- main HEAD 新增 N commit
- **未 push**（per agent memory `no-push-without-ask.md`：等 user 显式说推）

## TaskUpdate 同步
- TaskUpdate(task_id=<task_id>, status=completed, label=<none|downscope|contract-gap|...>)
- 详见 02-orchestrator §主循环

## SendMessage 报回
- SendMessage(to=<owner-session-id>, content="track=<track_id> status=done duration_min=<N> deliverables=<path>")

## 核心改动（1 段）
<一句话讲最关键的取舍，引用 STATUS / 04-commands / ADR>

## 证据链（1 段）
- pytest 输出: `<N>/<N> 绿`
- vitest 输出: `<N>/<N> 绿`
- Playwright 截图: <路径 + 验证步骤>
- BDD 场景: <B-6-P2-T<N> + When/Then>

## 契约问题（任选）
- CONTRACT_GAP: <如果发现了>
- DOWNSCOPE_TAKEN: <如果接受 §5 downscope 决策，列具体范围>
- SCOPE_EXCEEDED: <如果超时了>
- INNOVATION_GAP: <如果没引用调研素材>
- TEMPLATE_MISSING: <如果模板段缺>
- NAME_MISMATCH: <如果命名不一致>
- WORKTREE_RACE: <如果共享 working tree 触发覆盖>

## STATUS 行
<原行> ⏳→ ✅ + 追加 commit 摘要

## 给下一位的交接
<关键决策 + 引用 + 未解决项 + 30min 内接手者应看什么>
```

## 字段填写要求
- **status**：`done` = 代码 + 测试 + 截图 + commit + merge main + worklog + STATUS + TaskUpdate + SendMessage 全更新完；`failed` = 任一硬约束破
- **duration_min**：从派单到本 deliverable.md 落盘的实际分钟数（> 30 必填 `SCOPE_EXCEEDED`）
- **核心改动**：≤ 200 字，必须引用至少 1 处 STATUS / 04-commands / ADR
- **证据链**：必贴 pytest / vitest 实际输出片段 + Playwright 截图路径
- **契约问题**：空 = 全过；列出对应信号 + 1 句描述
- **TaskList ID**：TaskCreate 返回的 task_id 必填（owner 后续 TaskUpdate / TaskGet 用）
- **SendMessage 报回**：必填，owner 收到后 chain 下一个
