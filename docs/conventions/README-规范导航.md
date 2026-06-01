# AgentHub 开发规范（👤 人类入口）

> 版本: v3.1 | 2026-05-29
> 本文件是**人类**的规范入口；🤖 AI Agent 请读 [CLAUDE.md](CLAUDE.md)（任务→规范定位 + 红线总表 + 去重映射）。

---

## 规范全集

### 主规范（细化 ai-workflow 各步骤）

| # | 文件 | 关键词 | 红线 |
|---|------|--------|------|
| 01 | [架构设计规范](01-architecture_架构设计规范.md) | 5 层洋葱 / 依赖倒置 / Adapter / FSM | AR-01 ~ AR-06 |
| 02 | [代码编写规范](02-coding_代码编写规范.md) | Python/TS 红线 / 命名 / 错误 / 安全 | CR-01 ~ CR-12 |
| 03 | [Git 协作规范](03-git_Git协作规范.md) | 分支 / 提交 / PR / 合并 | PR-02/03/06/07 摘要 |
| 04 | [API 设计规范](04-api_API设计规范.md) | REST + WS / 错误响应 / Pydantic | AP-01 ~ AP-07 |
| 05 | [测试规范](05-testing_测试规范.md) | 金字塔 / Mock 边界 / Adapter+FSM 必测 | T-01 ~ T-06 |
| 06 | [文档规范](06-documentation_文档规范.md) | 命名 / explore / ADR / worklog | D-01 ~ D-12 |
| 08 | [代码理解与图谱规范](08-code-understanding_代码理解与图谱规范.md) | 双图谱：CodeGraph + Understand-Anything | — |

### AgentHub 特有附录

| 文件 | 用途 |
|------|------|
| [09-boundaries_边界矩阵.md](09-boundaries_边界矩阵.md) | Agent 操作权限矩阵：Always / Ask First / Never |
| [10-process-rules_流程红线全集.md](10-process-rules_流程红线全集.md) | 完整 PR-01 ~ PR-09，03 Git 摘要的扩展 |

### 协作流程方法论

[ai-workflow_AI协作开发流程/](ai-workflow_AI协作开发流程/) 共 7 篇：

```
01-角色分工与文件体系  →  02-第零步_调研  →  03-第一步_编写计划
                                                      ↓
                                                04-第二步_迭代开发
                                                      ↓
                                                05-完整流程与核心原则（PR-01~09 在此）
                                                      ↓
                                                06-第三步_收束节点（四阶段闸门）
                                                      ↓
                                                07-汇报（四档汇报体系）
```

---

## 常用规约一览

- **分支**：`feature/<domain>/<desc>`，禁直 push main
- **提交**：Conventional Commits（`feat:`/`fix:`/`refactor:`/`docs:`/`test:`/`chore:`）
- **验证**：每次 commit 前 `scripts/verify.bat` 或手动 ruff / tsc / eslint / pytest
- **日志**：每次工作后 `worklogs/{你}/YYYY-MM-DD_<desc>.md`，更新根 `STATUS.md`
- **文档**：命名 `{English}_{中文}.md`，pre-push 钩子自动检查
- **依赖安装**：克隆后首装 `pre-commit install --hook-type pre-push && pre-commit install`

---

## 改规范时

1. 改 `NN-*.md` → 同步 `docs/specs/NN-*.md` 规格（若有对应）
2. 红线增删 → 同步 [CLAUDE.md](CLAUDE.md) §2 红线总表 + 本文红线速查
3. 改 §二落地配置 → 同步实际配置（`src/backend/pyproject.toml` / `.pre-commit-config.yaml` / `src/frontend/eslint.config.js`）
4. 改文档命名/分支命名/worklog 路径 → 同步对应 `scripts/check_*.py`
5. 同 PR 内写 worklog + 更 STATUS.md（pre-push 自动校）
