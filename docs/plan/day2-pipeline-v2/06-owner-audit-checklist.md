# 06 · owner 早上 5 分钟审计清单

每天早上读这 4 处：

## 1. `STATUS.md` — 12 track 进度表
看 ⏳/✅/❌ 分布。
- 全 ✅ + TaskList 全 completed → 流水线 done
- 单 track ❌ → 看 TaskGet(task_id) 失败原因
- 连续 ≥3 track ❌ → 停下来跟 worker 开会
- 22:30 downscope 触发 → 看 ADR NNNN-day2-downscope-2230.md 决策路径

## 2. Claude Code `TaskList` — 每 track 状态
```
# 通过 Claude Code session 直接调用
TaskList  # 看所有 task + status + label + updated_at
```
重点看：
- `duration_min`（在 deliverable.md）：> 30 必有 `SCOPE_EXCEEDED` 标注
- `failed` 状态 track：必带 `label` 字段（`CONTRACT_GAP` / `INNOVATION_GAP` / `TEMPLATE_MISSING` / `NAME_MISMATCH` / `SCOPE_EXCEEDED` / `WORKTREE_RACE`）
- `downscope_taken`：标 ✅ 但范围缩了，审 deliverable.md 缩了哪些

## 3. `worklogs/yuan/<今日>*.md` — 关键决策 + 引用
每个 ✅ track 都应有对应 worklog。重点扫：
- 关键决策段（每 track 1-3 条 ADR 引用 + STATUS / 04-commands 引用）
- 调研素材引用（验证 `INNOVATION_GAP` 不是空标）
- 契约问题（验证 `CONTRACT_GAP` 累积没炸）
- 给下一位的交接（确保接手者能继续）

## 4. `docs/plans/_orchestrator/failures.md`（若存在）— 失败 track 汇总
失败 track 自动追加的清单。审：
- 是否同一类问题连续出（如 NAME_MISMATCH 反复）→ 提示词本身要改
- 是否 `CONTRACT_GAP` 累积到 ≥3 → 停下来跟 worker 开会，决定先补契约
- 是否 `WORKTREE_RACE` 触发 → 检查 01-worker-prompt.md §4.4 worktree 隔离是否被绕过

## 决策树

| 现象 | 动作 |
|------|------|
| 全 ✅ + TaskList 空 | 流水线 done。审 `deliverable.md` 抽样 3-5 个，确认质量 |
| 单 track ❌（CONTRACT_GAP / INNOVATION_GAP） | 标 todo 留给开发阶段补，流水线继续 |
| 连续 3 track ❌ | **停下来**，跟 worker 开会（review 失败原因 + 决定改提示词 or 拆 track） |
| 整体卡住（30 min 内无 TaskUpdate） | TaskUpdate 当前 in_progress → pending + label=scope-exceeded + 派下一个 |
| `INNOVATION_GAP` ≥ 5 | 检查 `调研/` 目录是否可读；不可读 → 修路径后只重跑失败的 |
| `WORKTREE_RACE` ≥ 1 | 强制 01 §4.4 worktree 隔离，重跑失败 track |
| 22:30 downscope 触发 | 看 ADR NNNN-day2-downscope-2230.md 决策路径，审保留 1-6 + 9 是否合理 |
| t3 MCP P3 A/B 决策 | 路径 A → 验 alembic 0006；路径 B → 验 ADR-0015 docs-only |
| t11 飞书 OAuth user-blocked | 不阻塞；标 ADR-0016 `feishu-oauth-deferred` |

## 早会 5 分钟模板
```
[日期] Day 2 流水线日报
- 完成: <N>/12（<track 名列表>）
- 失败: <N>/12（<track + 原因>）
- downscope 触发: <yes/no, 哪些 track>
- CONTRACT_GAP 累积: <N>
- WORKTREE_RACE 触发: <N>
- 整体进度: <%>
- t3 MCP P3 决策: <A/B 路径 + commit hash>
- t11 飞书 OAuth: <已同步 / 延后>
- 今日决策: <需要 owner 拍板的事，若无则 "无">
```

## 验收清单（明早 09:00）

- [ ] main HEAD ≥ +12 commit（覆盖 12 track），全部 verify 过
- [ ] pytest 175/175 绿（168 + 7 新增）
- [ ] vitest 100/100 绿（85 + 15 新增）
- [ ] 8+ 张新 Playwright 截图落 `docs/deliverables/screenshots/`
- [ ] 4 preview 模式全 enabled:true（Track 1 验收）
- [ ] CreateAgentModal 无 502 错（Track 2 验收）
- [ ] S1 私聊 3 建议按钮真响应（Track 4 验收）
- [ ] S2 群聊 Pin/复制代码真可用（Track 5 验收）
- [ ] M5 5.3 Token 监控 UI 暴露（Track 6 验收）
- [ ] 桌面 App specs 4 Q 答完（Track 8 验收）
- [ ] MCP P3 F3 路径 A 或 B 决策落地（Track 3 验收）
- [ ] /api/usage router 已注册（Track 9 验收）
- [ ] M6 v6 视频 + README + inbox 视觉补（Track 10 验收）
- [ ] 飞书云文档同步（Track 11 验收 或 ADR-0016 defer）
- [ ] e2e-pin-auth 截图兜底（Track 12 验收）
- [ ] `docs/reports/test-report-2026-06-09.html` 已落盘
- [ ] 飞书云文档同步（`test-report-2026-06-09-feishu.md`）
- [ ] STATUS.md / worklog 全部同步，无 10min+ 滞后
- [ ] TaskList 全 completed（除 t11 候补/已 downscope）
- [ ] 无未处理 verifier FAIL
