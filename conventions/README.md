# AgentHub 开发规范

> 版本: v1.0 | 2026-05-26
> 来源: `spec/rules/` 三大红线 + `CLAUDE.md` + `spec/architecture_架构定义.md` + `frontend/HANDOFF.md` + 项目协作流程

本文件夹是 AgentHub 项目通用开发规范的**统一入口**，适用于所有开发者（人类 & AI Agent）。`spec/rules/` 中的原始红线文件仍为权威来源，本文件夹是其结构化整理。

---

## 快速索引

| 文档 | 关键词 | 何时读 |
|------|--------|--------|
| [01-architecture_架构规范](01-architecture_架构规范.md) | 分层、依赖倒置、模块边界 | 开始写后端逻辑前 |
| [02-code_代码规范](02-code_代码规范.md) | Python/TS 红线 | 写任何代码前 |
| [03-process_流程规范](03-process_流程规范.md) | 分支、提交、PR、Review | 领任务 / 提 MR 前 |
| [04-testing_测试规范](04-testing_测试规范.md) | 测试金字塔、覆盖目标、Mock | 写测试前 |
| [05-git_协作规范](05-git_协作规范.md) | 分支管理、同步、合并 | 开始工作 / 合并前 |
| [06-boundaries_边界矩阵](06-boundaries_边界矩阵.md) | Always/AskFirst/Never | 写权限逻辑前 |
| [07-tech-stack_技术栈](07-tech-stack_技术栈.md) | 选型、版本、约束 | 新人入职 / 选型决策 |

---

## 红线速查

以下 3 条违反任一条 = 方案打回 / CR 不通过 / 流程违规：

### 架构红线（6 条）
1. **AR-01**: 5 层洋葱 `L5->L4->L3->L2<-L1`，L2 不能 import 任何上层
2. **AR-02**: 新 Agent 系统只加 Adapter，禁止改 `domain/`
3. **AR-03**: Harness 不含 LLM 调用
4. **AR-04**: Agent 间不直接通信（仅 Blackboard + Coordinator）
5. **AR-05**: Task 状态变更必须走 FSM + 事件溯源
6. **AR-06**: Agent system 与 model 解耦

### 代码红线（12 条）
1. **CR-01**: 禁裸 `print()` -> `logging`
2. **CR-02**: 禁裸 SQL 拼接 -> 参数化
3. **CR-03**: 数据库变更必须走 Alembic Migration
4. **CR-04**: API 端点必须有异常处理
5. **CR-05**: API 输入必须 Pydantic v2 校验
6. **CR-06**: 外部 API 调用必须有超时+重试+熔断
7. **CR-07**: TS strict mode 零错误，禁 `any`
8. **CR-08**: React render 中禁异步函数
9. **CR-09**: 组件超过 200 行建议拆分
10. **CR-10**: 禁硬编码密钥/Token -> 环境变量
11. **CR-11**: 禁遗留调试代码（print/console.log/注释代码块）
12. **CR-12**: 禁同步阻塞在 async 上下文

### 流程红线（9 条）
1. **PR-01**: 接口先行，变更需 2 人 Review
2. **PR-02**: 分支 `feature/<domain>/<desc>`
3. **PR-03**: Conventional Commits
4. **PR-04**: Agent 写文件必经审批
5. **PR-05**: 每里程碑结束全员集成测试
6. **PR-06**: PR 至少 1 人 Review
7. **PR-07**: 提交前跑验证（ruff/pytest/tsc/eslint）
8. **PR-08**: 修改代码后更新 roadmap
9. **PR-09**: SPEC 和代码同步

---

## 项目约定

- **分支**: `feature/<domain>/<desc>`，禁止直接 push main
- **提交**: Conventional Commits（`feat:`/`fix:`/`refactor:`/`docs:`/`test:`/`chore:`）
- **验证**: 每次 commit 前 `verify.bat` 或手动跑 ruff/tsc/eslint
- **日志**: 每次工作后在 `worklogs/` 目录写日志，更新 `STATUS.md`
- **文档**: 命名规范 `{English}_{中文}.md`，pre-push hook 自动检查
