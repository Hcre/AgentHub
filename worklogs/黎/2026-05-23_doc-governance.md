# 工作日志：文档治理体系建立

- **谁**: 黎
- **日期**: 2026-05-23
- **分支**: main
- **关联 Spec**: CLAUDE.md, README.md, docs/explore/README.md

## 目标
建立统一的文档目录结构和命名规范，解决新旧文档版本冲突、队友文档命名格式不一致的问题。

## 产出
- [x] 目录重组 — 决策/ → docs/explore/，旧PRD → docs/archive/
- [x] 命名规范落地 — docs/ 英文_中文，explore/ EXP-NN_/ADR-NN-/作者-
- [x] .agenthub/CLAUDE.md 合并到根 CLAUDE.md，删除重复入口
- [x] 新增 EVOLUTION.md — 项目决策演进日志
- [x] 新增 explore/README.md — 探索文档索引
- [x] 新增 check_docs.py — pre-push 文档结构自动检查
- [x] 重写 doc-sync skill — 三个流程（探索归档/决策落地/例行审查）
- [x] 更新 README.md — 文档约定表格 + 新目录结构
- [x] 发现并修复：pre-commit hooks 从未安装，所有检查从未触发

## 关键决策
| 决策 | 原因 | 影响 |
|------|------|------|
| docs/ 英文_中文命名 | 保证命名可预测，人类和 AI 都能解析 | 所有 docs/ 文件重命名 |
| explore/ 三分类 | EXP=团队报告, ADR=架构决策, 作者-=个人探索 | 19个文件重新归类 |
| check_docs.py pre-push | skill 不能保证合规，需要自动化硬约束 | push 前自动检查命名+路径 |
| 董的非日期文档移入 explore/ | worklogs 只放日志，不放正式文档 | worklogs/董/ 从13个文件减到3个 |

## 未完成 / 阻塞
- [ ] 队友需要知道 hooks 需要 `pre-commit install` 才能生效
- [ ] `check_branch.py` 有 GBK 编码 bug（emoji 输出崩溃），待修

## 给下一位的交接
> 1. 每次克隆仓库后运行 `pre-commit install --hook-type pre-push && pre-commit install`
> 2. 新增探索文档用 `doc-sync` skill 走流程 A
> 3. 改 PRD/架构后走流程 B，别忘了更新 EVOLUTION.md
