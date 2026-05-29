# AgentHub 流程红线

> 版本: v2.1 | 违反 = 流程违规

## PR-01：接口先行，冻结后变更需 2 人 Review

L4 API 层 endpoint 路径 + Request/Response Schema 在实现前冻结。

## PR-02：分支命名规范

```
feature/<domain>/<desc>
示例: feature/chat/websocket-endpoint
      feature/orchestration/task-fsm
      feature/toolchain/diff-preview
```

禁止直接 push 到 main。

## PR-03：Conventional Commits

```
feat: 新功能
fix: 修复
refactor: 重构
docs: 文档
test: 测试
chore: 工程配置
```

禁止 `fix bug`、`update code`、`WIP`。

## PR-04：Agent 写文件必经审批

所有 Worker Agent 对 src/ 的写操作：
1. 生成 unified diff
2. 推送审批卡片到聊天窗口
3. 用户 APPROVE 后才应用

## PR-05：每里程碑结束全员集成测试

按 PRD §九 成功闸门逐项检查。不通过项记录为下个 M 优先。

## PR-06：PR 至少 1 人 Review 才能合并

- 域内变更：同域 1 人
- 跨域接口变更：2 人（含被影响域成员）

## PR-07：代码提交前跑验证

```bash
# 后端
ruff check src/backend/app/
pytest --cov=app --cov-fail-under=80

# 前端
npx tsc --noEmit
npx eslint src/frontend/src/
npm test -- --coverage
```

不通过不能提交 PR。

## PR-08：修改代码后更新项目进度

每次完成一个任务的代码实现后，必须同步更新 `docs/plan/开发清单_roadmap.md` 中对应该任务的验收状态：

- 任务完成并验证通过 → 标记 `✅`
- 在任务下方追加一行 `> 完成: YYYY-MM-DD, 备注: <关键决策/遗留问题>`
- 如果实现中做出与 SPEC 不同的决策 → 同步更新对应的 SPEC 文件

## PR-09：SPEC 和代码同步

- 任何架构变更 → 先更新 `docs/specs/01-architecture_架构定义.md`
- 任何数据模型变更 → 先更新 `docs/specs/03-data-model_数据模型.md` + 生成 Alembic migration
- 任何 API 变更 → 先更新 `docs/specs/04-commands_命令接口.md`
- M1-M5 每个里程碑结束 → 更新 `docs/specs/00-overview_项目主规格.md` 中的状态
