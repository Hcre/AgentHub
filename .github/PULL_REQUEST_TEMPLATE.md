<!-- AgentHub PR Template — 与 docs/conventions/03-git_Git协作规范.md PR-01~09 / 10-process-rules 流程红线对齐 -->

## 概述

<!-- 一句话讲清这个 PR 在做什么，以及为什么要做。链接到对应 issue / SPEC / ADR。 -->

> **做什么**：
>
> **为什么**：
>
> **关联**：
> - Issue: #
> - SPEC / ADR: `docs/specs/...` · `worklogs/decisions/NNNN-...md`
> - Roadmap 任务: `docs/plan/开发清单_roadmap.md` §X.Y

---

## Scope（变更范围）

<!-- 勾选所有适用的。混勾时 PR 拆分（[03-git §三 反模式](docs/conventions/03-git_Git协作规范.md)）。 -->

- [ ] Backend（`src/backend/` — L1-L4）
- [ ] Frontend（`src/frontend/` — L5）
- [ ] Database（`src/backend/alembic/` — 含 migration）
- [ ] API（`docs/specs/04-commands_命令接口.md` — 需先冻结）
- [ ] Architecture（`docs/specs/01-architecture*` — 需先改 spec 再实现）
- [ ] Data Model（`docs/specs/03-data-model_数据模型.md` + Alembic）
- [ ] Documentation（`docs/` `README.md` `CONTRIBUTING.md`）
- [ ] CI（`.github/workflows/` `.pre-commit-config.yaml`）
- [ ] Skill / Harness（`skills/` `.harness/` `.agenthub/`）

---

## 类型（type）

<!-- commitlint 强制 scope 在 enum 内：chat / orchestration / toolchain / frontend / backend / docs / ci / deps -->

- [ ] `feat` — 新功能
- [ ] `fix` — Bug 修复
- [ ] `refactor` — 重构（无新功能/无 bug 修复）
- [ ] `perf` — 性能
- [ ] `test` — 测试
- [ ] `docs` — 文档
- [ ] `chore` — 工程配置 / 依赖
- [ ] `style` — 格式

**scope（必填，kebab-case）**：`chat` / `orchestration` / `toolchain` / `frontend` / `backend` / `docs` / `ci` / `deps`

---

## Checklist（PR 提交前必过）

### 工程红线（自动检查）

- [ ] `scripts/verify.bat` 在本地全绿（ruff + mypy + tsc + eslint）
- [ ] 分支命名符合 `feature/<domain>/<desc>`（`scripts/check_branch.py` pre-push 校）
- [ ] 提交符合 Conventional Commits + `scope-enum`（commitlint 校）
- [ ] 无 `WIP` / `fix bug` / `update code` 等模糊 commit
- [ ] worklog 已写 `worklogs/{你的名字}/YYYY-MM-DD_*.md`
- [ ] `STATUS.md` 自己的行已更新（正在做 / 阻塞 / 本周完成）
- [ ] `docs/plan/开发清单_roadmap.md` 对应任务状态已更新（PR-08）

### 代码质量（自审）

- [ ] 变更量 < 500 行（[03-git §三 反模式](docs/conventions/03-git_Git协作规范.md)；超过须说明）
- [ ] 一个 commit 只做一件事（`git log origin/main...HEAD` 自查）
- [ ] 无无关改动（`git diff origin/main...HEAD` 已通读）
- [ ] 无 `print` / `console.log` 在生产路径（CR-01 / eslint no-console）
- [ ] 无 `any` 类型（CR-07：TS 严格）
- [ ] 无同步阻塞调用（CR-12：FastAPI async）
- [ ] 无未审批的密钥/`.env` 入库（`scripts/check_secrets.py` 兜底）

### 接口 / 数据 / 架构（PR-01 / PR-09）

- [ ] **API 变更**：`docs/specs/04-commands_命令接口.md` 已冻结，2 人 Review Approve
- [ ] **数据模型变更**：Alembic migration 已生成 + `docs/specs/03-data-model_数据模型.md` 已同步
- [ ] **架构变更**：先改 `docs/specs/01-architecture_*.md`，再写代码
- [ ] **新 Agent 系统**：[01 §4.2 AR-02 流程](docs/conventions/01-architecture_架构设计规范.md) + ADR 已写

### 测试（红线 T-01~06）

- [ ] 单测已加（happy path + 边界 + 异常，至少 3 路径）
- [ ] FSM / Adapter 必测路径已覆盖（[05-testing §一](docs/conventions/05-testing_测试规范.md)）
- [ ] 本地 `pytest` 全绿 + `vitest run` 全绿
- [ ] 无 flaky test（本地连跑 3 次稳定）
- [ ] E2E Playwright 截图（如适用，已附在 PR / `docs/deliverables/screenshots/`）

---

## Test（怎么验证）

<!-- 描述本地验证步骤 + CI 期望结果。Reviewer 照着跑能复现。 -->

### 本地命令

```bash
# 1. ruff + mypy + tsc + eslint
scripts/verify.bat

# 2. 后端单测
cd src/backend && pytest -q

# 3. 前端单测
cd src/frontend && npm test

# 4. E2E（可选）
cd src/frontend && npx playwright install --with-deps chromium
node scripts/screenshot_p0_p1.cjs
```

### 期望结果

- [ ] `pytest` 全绿，覆盖率 ≥ 80%
- [ ] `vitest` 全绿（当前 47+ 用例）
- [ ] `ruff` / `mypy` / `tsc` / `eslint` 0 error
- [ ] 3 个 GitHub Actions job 全绿（`backend` `frontend` `e2e`）

---

## Risk（风险与回滚）

<!-- 红色 PR 必填：影响哪些模块 / 数据 / 用户路径 / 性能 / 安全。回滚一行命令说清。 -->

- **影响面**：
- **回滚方式**：`git revert <sha>` / 关闭 feature flag / 删 Alembic migration
- **是否需要 feature flag**：是 / 否
- **是否需要 DB migration**：是 / 否（若 "是"，已 down 测过 `alembic downgrade -1`）
- **是否影响 WS 连接 / 长驻进程**：是 / 否

---

## Screenshot / Evidence（证据）

<!-- UI / 前端 / 视觉相关变更必填；其他类型可写日志/JSON/CLI 输出摘录。 -->

- 截图：见 `docs/deliverables/screenshots/<name>.png`
- 日志：见 PR 评论 / `worklogs/{你的名字}/YYYY-MM-DD_*.md`
- 命令输出：

  ```text
  $ pytest -q
  47 passed in 8.2s

  $ npm test
   ✓ 47 tests passed
  ```

---

## Reviewer 路由

<!-- 默认由 CODEOWNERS 自动指派。跨域变更（API / 数据 / 架构）必须 ≥ 2 人，含被影响域 owner（PR-06）。 -->

- [ ] 域内 1 人（同域 owner）
- [ ] 跨域 2 人（含被影响域 owner）—— 接口 / 数据 / 架构
- [ ] AI 协作产物人工复核（如果 commit 中有 `Co-authored-by: ... <noreply@anthropic.com>`）

---

## 备注

<!-- 任何 Reviewer 应当知道但不属于上述分类的信息：已知遗留问题、未完成子任务、替代方案对比、Trade-off。 -->
