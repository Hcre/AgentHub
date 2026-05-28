# 工作日志：CLAUDE.md 与 README 角色分离

> 日期: 2026-05-27
> 功能点: #30 CLAUDE.md 与 README 角色分离
> 关联 BDD: -

## 做了什么

### 核心原则确立
- **CLAUDE.md = AI 专用**：仅供 AI Agent 在新会话中自动加载，包含项目上下文、目录地图、行为规则、ADR 摘要、常见 AI 任务指南
- **README.md（所有）= 人类专用**：供人类开发者导航和理解项目结构
- 每个 README 文件均标注 `👤 人类参考/阅读` 并指向 AI 去读 CLAUDE.md

### CLAUDE.md 重写
- 新增 "⚠️ 仅供 AI Agent 读取" 声明
- 新增 "目录地图（AI 导航用）" — 每个目录带职责标注
- 新增 "AI 行为规则" — 文件操作/沟通/内容三类规则
- 新增 "常见 AI 任务指南" — 5 个场景（修改规范/新增功能点/新增模板/汇报进度/收束节点）
- 保留模块依赖图谱、关键决策表

### README 全量更新（13 个文件）

| 文件 | 变更 |
|------|------|
| `README.md`（根） | 重写：人类导航 + AI 配合说明 + 目录带 emoji + FAQ |
| `conventions/README.md` | 精简：快速索引 + 四类红线速查 |
| `src/README.md` | 人类参考声明 + 目录索引表格化 |
| `src/7 个子目录 README` | 统一添加 `> **👤 人类参考**` 标注 |
| `docs/plan/design/README.md` | 修正 `docs/decisions/` → `worklogs/decisions/` |
| `docs/reports/README.md` | 补充收束报告档位 |
| `docs/templates/README.md` | 人类参考声明 |

### 7 处残留 `docs/decisions/` 引用修复
- `conventions/01-architecture`、`06-documentation`、`ai-workflow/06-第三步`
- `docs/templates/AI会话启动模板`（2 处）、`AI协作提示词模板`、`汇报模板`

## 验证结果

- 13 个 README 全部更新 ✅
- CLAUDE.md 含完整 AI 导航和行为规则 ✅
- 全仓再无 `docs/decisions/` 残留引用（worklogs 历史记录除外）✅
- CLAUDE.md ↔ README.md 角色声明互指 ✅

## 变更影响

- 涉及文件: 21 个（CLAUDE.md 重写 + 13 README 更新 + 7 处路径修正）
- AI 行为变更：此后 AI 应只参考 CLAUDE.md 的规则行事
- 人类体验变更：README 更友好、导航更清晰

## 给下一位的交接

> CLAUDE.md 是 AI 的唯一权威上下文，README 是人类专属。新增 README 时保持 `👤` 标注；修改 AI 行为规则时只改 CLAUDE.md。
