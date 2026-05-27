# 工作日志：decisions 移入 worklog + 约束节点决策总结规则

> 日期: 2026-05-27
> 功能点: #29 decisions 移入 worklog + 约束节点决策总结规则
> 关联 BDD: -

## 做了什么

### 物理移动
- `docs/decisions/` → `worklogs/decisions/`（5 个历史 ADR 随迁，内容不变）

### 新规则（ADR 0006）
- **决策仅在一批功能点完成后（收束节点）通过 worklog 整理并提升为 ADR**
- 日常开发的技术取舍只记在 worklog 的"关键决策"段，不即时创建 ADR
- ADR 从独立文档流变为 worklog 体系的子集，编号与收束节点对齐
- 理由：提高决策质量（经实践验证后再判断）、减少噪音、增强追溯性

### 同步更新
- `worklogs/decisions/0006-约束节点决策总结.md` — 新建 ADR 记录此规则
- `meta/FILE_GRAPH.md` — 目录树删 `docs/decisions/`，增 `worklogs/decisions/`；决策树更新 ADR 落点
- `CLAUDE.md` — 目录结构 + 关键决策表同步
- `STATUS.md` — 新增 #29 功能点
- `docs/plan/开发清单.md` — 新增 #29 功能点

## 验证结果

- `worklogs/decisions/` 含 6 个 ADR（0001-0006）✅
- 全仓再无 `docs/decisions/` 路径引用 ✅
- FILE_GRAPH.md / CLAUDE.md / STATUS.md / 开发清单.md 四文件路径一致 ✅

## 变更影响

- ADR 创建流程变更：即时创建 → 收束节点批量整理提升
- 文件路径变更：所有引用 `docs/decisions/` 的外部文档需更新（本项目内已全部更新）
- 收束节点流程新增"决策整理"环节（待后续更新 `06-第三步_收束节点.md`）

## 给下一位的交接

> 此后新的 ADR 只在收束节点时创建。日常开发中的取舍记在 worklog 的"关键决策"段即可——收束时判断哪些值得提升为永久 ADR。
