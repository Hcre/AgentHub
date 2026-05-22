# 工作日志：初始化 AI 协作体系

- **谁**: 黎
- **日期**: 2026-05-22
- **分支**: main
- **关联 Spec**: 无

## 目标
建立项目仓库的 AI 协作规范体系：文档分层、规则精简、CLAUDE 入口、工作日志系统。

## 产出
- [ ] 将外部 `spec/` 整合到 repo 内，建立 `docs/`(人读) + `spec/`(AI读) 双轨
- [ ] 精简三大规则文件：arch-rules 8→6, code-rules 16→12, process-rules 9→9
- [ ] 重写 `.agenthub/CLAUDE.md` 作为 AI 统一入口（文档索引 + 行为准则 + 协作流程）
- [ ] 建立 `worklogs/` 目录 + `template.md` + `STATUS.md`
- [ ] 复制 `skill/spec-driven-development` 到 `skills/`

## 关键决策
| 决策 | 原因 | 影响 |
|------|------|------|
| docs/ vs spec/ 分层 | docs 给人读叙事文，spec 给 AI 读结构化数据 | 新文档需判断归属 |
| 规则 33→25 条 | 删除重复（AR-07/CR-08）、过严（CR-09/CR-12）、非协作（PR-04） | 减少无意义告警 |
| SubAgent 不定死 | 三人各自组织，灵活性优先 | 等出现混乱再约定 |
| STATUS.md 各自维护自己的行 | 无专人管理费用，改自己的行冲突概率极低 | 需每个人遵守 |

## 未完成 / 阻塞
- [ ] 删除外部 `D:/AgentHub/spec/` 目录 — 等用户确认
- [ ] `STATUS.md` 中三人名字待填
- [ ] Rule 自动化脚本未配（ruff/eslint/pre-commit）
- [ ] 核心 Skills 未创建（feat-start/feat-complete/code-review）

## 给下一位的交接
> 下次工作前先 `git pull`，STATUS.md 里填上自己的名字和当前任务。配好 ruff/eslint/pre-commit 后可以开始 MVP 开发。
