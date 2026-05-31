# Git 协作规范 — AgentHub

> **本规范是 [ai-workflow 第二步·迭代开发 §2.6 Git 提交](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md) 的细化**，展开提交格式、分支策略与 Review 流程。
>
> AgentHub 协作档位：**多人 GitHub Flow**（董/黎/袁 三人 + Claude Agent），按业务域分支（`feature/<domain>/<desc>`），main 受保护。所有 push 触发 pre-push 钩子（worklog / 分支命名 / 文档命名校验）。

---

## 一、红线（必守）

| # | 红线 | 怎么自动抓 |
|---|------|-----------|
| **PR-02** | 分支命名 `feature/<domain>/<desc>` 格式；禁直接 push `main` | `scripts/check_branch.py` (pre-push) + GitHub 分支保护 |
| **PR-03** | 提交符合 Conventional Commits（`type(scope): desc`） | `commitlint` + commit-msg hook |
| **PR-06** | 合入需至少 1 人 Review；跨域接口变更需 2 人（含被影响域成员） | GitHub 分支保护 + CR |
| **PR-07** | 提交前跑 `verify.{bat,sh}`：ruff + pytest（cov ≥80）+ tsc + eslint | pre-commit + CI |
| — | 一个 commit 只做一件事，禁 `WIP`/`fix`/`update code` 等模糊提交 | commitlint + CR |
| — | 禁 `git push --force` 到 `main`/`develop`/共享 feature 分支 | GitHub 分支保护 |
| **PR-10** | **AI Agent 不得自主 push / merge**。可以在分支上 commit，等用户明确指令再 push/merge/切回 main/删分支。 | 人工确认 |

> 完整 PR-01 ~ PR-09 流程红线见 [99-process-rules_流程红线全集](99-process-rules_流程红线全集.md)。

---

## 二、落地：提交与 PR 的可复制配置

**AgentHub `.pre-commit-config.yaml`（已挂载，新增钩子追加即可）**：

```yaml
repos:
  - repo: https://github.com/alessandrojcm/commitlint-pre-commit-hook
    rev: v9.16.0
    hooks:
      - id: commitlint
        stages: [commit-msg]
  - repo: local
    hooks:
      - id: check-branch
        name: 校分支命名 feature/<domain>/<desc>
        entry: python scripts/check_branch.py
        language: system
        stages: [pre-push]
      - id: check-worklog
        name: 校 worklog + STATUS 更新
        entry: python scripts/check_worklog.py
        language: system
        stages: [pre-push]
      - id: check-docs
        name: 校文档命名 + CLAUDE 引用 + hooks 装机
        entry: python scripts/check_docs.py
        language: system
        stages: [pre-push]
```

**首次克隆后必装**：
```bash
pre-commit install --hook-type pre-push && pre-commit install
```

**`commitlint.config.js`：**
```js
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'scope-enum': [2, 'always', ['chat', 'orchestration', 'toolchain', 'frontend', 'backend', 'docs', 'ci', 'deps']],
  },
};
```

**GitHub 分支保护**（Settings → Branches → main）：
- Require PR before merging
- Require 1 approval（跨域变更 2 人，手动加 reviewer）
- Require status checks: `verify` / `pre-commit`
- Restrict force push
- Restrict deletion

---

## 三、决策表

### 分支命名（kebab-case，业务域作 scope）

| 模式 | 用途 | 示例 |
|------|------|------|
| `feature/<domain>/<desc>` | 新功能（**默认**） | `feature/chat/websocket-endpoint`、`feature/orchestration/task-fsm` |
| `fix/<domain>/<desc>` | Bug 修复 | `fix/toolchain/diff-preview-empty` |
| `refactor/<domain>/<desc>` | 重构 | `refactor/chat/extract-message-service` |
| `docs/<desc>` | 文档 | `docs/api-error-code-table` |
| `chore/<desc>` | 工程配置 | `chore/align-with-conventions` |
| `hotfix/<desc>` | 紧急修复（从 main 切） | `hotfix/jwt-leak` |

**`<domain>` 取值**：`chat` / `orchestration` / `toolchain` / `frontend` / `backend` / `docs` / `ci` / `deps`（commitlint 配 scope-enum 强制）。

### 提交 type

| type | 用途 | type | 用途 |
|------|------|------|------|
| `feat` | 新功能 | `test` | 测试 |
| `fix` | 修复 | `perf` | 性能 |
| `refactor` | 重构 | `style` | 格式 |
| `docs` | 文档 | `chore` | 构建/依赖/工程配置 |

### 合并策略

| 场景 | 策略 |
|------|------|
| 功能分支细碎 commit 多 | **Squash Merge**（AgentHub 默认） |
| 阶段性大里程碑（M1/M2/M3 结束） | `merge --no-ff` 保留分支历史，便于回溯 |
| 紧急 hotfix | `merge --ff-only`（必须线性） |

### PR 约束

| 项 | 要点 |
|----|------|
| 描述三段 | 做了什么 / 为什么 / 怎么验证（含命令 + 截图/日志） |
| 变更量 | 单 PR < 500 行；超过拆分 |
| 提交前自审 | `git diff origin/main...HEAD` 确认无无关改动 |
| Review 重点 | 逻辑 > 风格；非阻塞建议用 `nit:` 前缀 |
| 跨域变更 | 加被影响域 owner 为 reviewer（落实 PR-06） |
| 后续操作 | 合并后立即删除功能分支（GitHub 自动启用） |

### 多人协作（AgentHub 现实）

- **每次工作前**：`/git-workflow` skill → 同步 main + 检查分支
- **每次工作后**：`worklogs/{你的名字}/YYYY-MM-DD_<desc>.md` + 更新 `STATUS.md` 你那行
- Git 用户名 → 人名映射见 `STATUS.md` 「Git ↔ 目录映射」表
- 未在映射表中的协作者：push 前先在 `STATUS.md` 加行（pre-push 校验靠这张表识别 worklog 所在子目录）

---

## 四、反模式

### ❌ 巨型 PR
`PR: 重构 chat 域 + 加 orchestration + 修 toolchain + 改文档（+3200 -1800，47 文件）` → 无法 Review，出问题难 bisect。
✅ 拆 3 个聚焦单主题 PR，各 15 分钟可审完。

### ❌ 模糊提交
`git commit -m "fix"` / `"WIP"` / `"改了些东西"` → 3 个月后 `git log` 成天书。
✅ `fix(chat): WS 重连后 message order 错乱` + body 写动机，`git log --grep="fix(chat)"` 可检索。

### ❌ 跨 scope 提交
`feat: 新增 group + 修复 task FSM + 改前端样式` → 一次 commit 牵动 3 个域，难回滚。
✅ 拆成 3 个 commit，scope 各自独立。

### ❌ 在 main 上开发
直接在 main 上 commit → pre-push 校验拦截（PR-02），白浪费工作。
✅ 工作前先 `/git-workflow` skill 创建 feature 分支。

---

## 五、检查清单

- [ ] 从最新 `main` 切分支，分支名符合 `<type>/<domain>/<desc>` 格式（pre-push 已校）
- [ ] commit message 符合 Conventional Commits + 在 scope-enum 内（commitlint 已校）
- [ ] 每个 commit 只做一件事，无 `WIP`
- [ ] PR 描述含：做了什么 / 为什么 / 怎么验证（命令 + 证据）
- [ ] PR 变更量 < 500 行（或已说明合并理由）
- [ ] 至少 1 Approve；跨域变更含 2 人（被影响域 owner）
- [ ] 未对共享分支 force push
- [ ] 合并后已删除功能分支
- [ ] worklog 已写、`STATUS.md` 已更新（pre-push 已校）
- [ ] 若有 roadmap 任务完成，已按 PR-08 更新验收状态

---

## 六、关联

| 方向 | 链接 |
|------|------|
| 细化自 | [ai-workflow 第二步 §2.6 Git 提交](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md) |
| 完整流程红线 | [99-process-rules_流程红线全集](99-process-rules_流程红线全集.md)（PR-01~09） |
| 验证证据要求 | [ai-workflow §2.2 可观测验证](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md) |
| Skill: 分支同步与合并前检查 | `skills/git-workflow/` |
| Skill: 完成功能（含 push 前自动校验） | `skills/feat-complete/` |

---

## 更新记录

| 日期 | 版本 | 变更说明 |
|------|------|---------|
| 2026-05-28 | v3.0 | 按模板骨架重写；红线对齐 AgentHub PR-02/03/06/07；新增按业务域分支命名 + scope-enum + 多人协作约定（worklog 按人分目录 + Git↔目录映射） |
