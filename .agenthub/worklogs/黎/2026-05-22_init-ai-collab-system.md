# 工作日志：初始化 AI 协作体系

- **谁**: 黎
- **日期**: 2026-05-22
- **分支**: main
- **关联 Spec**: 无

## 目标
建立项目仓库的 AI 协作规范体系：文档分层、规则精简、CLAUDE 入口、工作日志系统、自动化验证。

## 产出
- [x] 将外部 `spec/` 整合到 repo 内，建立 `docs/`(人读) + `spec/`(AI读) 双轨
- [x] 精简三大规则文件：arch-rules 8→6, code-rules 16→12, process-rules 9→9
- [x] 重写 `.agenthub/CLAUDE.md` 作为 AI 统一入口（文档索引 + 行为准则 + 协作流程）
- [x] 建立 `worklogs/` 目录 + `template.md` + `STATUS.md`，三人名已填
- [x] 复制 `skill/spec-driven-development` 到 `skills/`
- [x] 增强 ruff（T20禁print + ASYNC禁同步阻塞 + SIM + RUF）
- [x] 新增 ESLint 配置（no-console + max-lines 提示）
- [x] 新增 `.pre-commit-config.yaml`（ruff/eslint/tsc/分支命名检查）
- [x] 新增 `scripts/verify.sh` + `scripts/verify.bat`（一键跑全部检查）
- [x] 删除外部 `D:/AgentHub/spec/`

## 关键决策
| 决策 | 原因 | 影响 |
|------|------|------|
| docs/ vs spec/ 分层 | docs 给人读叙事文，spec 给 AI 读结构化数据 | 新文档需判断归属 |
| 规则 33→25 条 | 删除重复（AR-07/CR-08/CR-16）、过严（CR-09降级/CR-12删除）、非协作（PR-04删除） | 减少无意义告警 |
| SubAgent 不定死 | 三人各自组织，灵活性优先 | 等出现混乱再约定 |
| STATUS.md 各自维护自己的行 | 无专人管理费用，改自己的行冲突概率极低 | 需每个人遵守 |

## 未完成 / 阻塞
- [ ] ESLint 需 `cd frontend && npm install` 安装依赖后才能生效
- [ ] pre-commit 钩子需各自机器 `pre-commit install` 激活
- [ ] 核心 Skills 未创建（feat-start/feat-complete/code-review）— P2
- [ ] import-linter 未配（arch-rules 依赖方向自动检查）

## 给下一位的交接
> 董和袁 pull 之后：1) 在 `frontend/` 执行 `npm install` 装 ESLint；2) 在项目根执行 `pre-commit install` 激活钩子；3) 把自己的名字行填上当前任务。已经可以开始 MVP 开发了，按 `spec/roadmap_开发路线图.md` 选任务。
