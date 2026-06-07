# Contributing to AgentHub

> 协作规约的 **快速入口**。完整规范分布在 `docs/conventions/03-git_Git协作规范.md`、`docs/conventions/10-process-rules_流程红线全集.md`、`docs/conventions/CLAUDE-规范导航.md`。
>
> AgentHub 协作档位：**多人 GitHub Flow**（董/黎/袁 + Claude Agent），按业务域分支，main 受保护。

---

## 一、TL;DR（5 分钟看完能上手）

1. **从 main 切分支**：`git checkout main && git pull && git checkout -b feature/<domain>/<short-desc>`
2. **写代码 + 写测试**（TDD 循环：红 → 绿 → 重构）
3. **本地校验**：`scripts/verify.bat`（ruff + mypy + tsc + eslint + pytest + vitest）
4. **写 worklog + 更新 STATUS**：`worklogs/{你的名字}/YYYY-MM-DD_*.md` + `STATUS.md` 你那一行
5. **commit**（Conventional Commits）→ **push 分支** → **开 PR**（用 `.github/PULL_REQUEST_TEMPLATE.md`）
6. **等 CI 全绿 + ≥ 1 Approve** → squash merge

---

## 二、分支命名

格式（pre-push 钩子 `scripts/check_branch.py` 强制）：

```
feature/<domain>/<desc>      # 新功能（默认）
fix/<domain>/<desc>          # Bug 修复
refactor/<domain>/<desc>     # 重构
docs/<desc>                  # 文档
chore/<desc>                 # 工程配置
hotfix/<desc>                # 紧急修复（从 main 切）
```

`<domain>` 取值（commitlint 配 scope-enum 强制）：

`chat` · `orchestration` · `toolchain` · `frontend` · `backend` · `docs` · `ci` · `deps`

**示例**：

```bash
git checkout -b feature/chat/websocket-reconnect
git checkout -b fix/orchestrator/task-fsm-illegal-transition
git checkout -b docs/api-error-code-table
```

> **禁止**：直接在 main 上开发（`scripts/check_branch.py` pre-push 拦截；[PR-02 红线](docs/conventions/03-git_Git协作规范.md)）。

---

## 三、提交规范（Conventional Commits）

格式（commitlint 强制）：

```
<type>(<scope>): <description>      # scope 在 enum 内
```

| type | 用途 | type | 用途 |
|------|------|------|------|
| `feat` | 新功能 | `test` | 测试 |
| `fix` | 修复 | `perf` | 性能 |
| `refactor` | 重构 | `style` | 格式 |
| `docs` | 文档 | `chore` | 工程配置 / 依赖 |

**示例**：

```
feat(chat): WS 重连后 message order 保持升序
fix(orchestration): task FSM 拒绝非法 PENDING→COMPLETED 转换
docs(api): 增补 error code 表
test(backend): 补 mcp_opencode_inject 边界路径
chore(deps): alembic 1.13 → 1.14
```

**反例（被 commitlint / CR 拦截）**：

```
fix bug                            # 太模糊
WIP                                # 禁止
update code                        # 无 type 无 scope
feat: 新增 group + 修复 task FSM    # 一个 commit 跨 3 个域
```

**一个 commit 只做一件事**。跨域 / 跨主题 → 拆 commit，必要时拆 PR。

---

## 四、PR 流程

### 4.1 提 PR 前 checklist

- [ ] 分支命名符合 §二
- [ ] commit message 符合 §三（commitlint 校）
- [ ] `scripts/verify.bat` 本地全绿
- [ ] worklog 已写（`worklogs/{你的名字}/YYYY-MM-DD_*.md`）
- [ ] `STATUS.md` 你那一行已更新
- [ ] roadmap 任务已标 `✅`（如适用）
- [ ] PR 描述用 `.github/PULL_REQUEST_TEMPLATE.md` 填齐（Scope / Test / Risk / Screenshot）

### 4.2 提 PR 后

- **CI 自动跑**：`.github/workflows/ci.yml`（backend + frontend + e2e 3 个 job）
- **等 Review**：至少 1 Approve；跨域接口 / 数据 / 架构变更需 2 人（含被影响域 owner，[PR-06](docs/conventions/10-process-rules_流程红线全集.md)）
- **CI 必须全绿**（branch protection 推荐配置：[docs/CI-STATUS_CI状态说明.md §九](CI-STATUS_CI状态说明.md)）

### 4.3 合并策略

| 场景 | 策略 |
|------|------|
| 功能分支细碎 commit 多 | **Squash Merge**（AgentHub 默认） |
| 阶段性大里程碑（M1/M2/M3 结束） | `merge --no-ff` 保留分支历史 |
| 紧急 hotfix | `merge --ff-only`（必须线性） |

> **禁止**：`git push --force` 到 main / develop / 共享 feature 分支。

---

## 五、Review 规则

| 维度 | 要点 |
|------|------|
| **描述三段** | 做了什么 / 为什么 / 怎么验证（命令 + 截图） |
| **变更量** | 单 PR < 500 行；超过须拆分（[03-git §三 反模式](docs/conventions/03-git_Git协作规范.md)） |
| **自审** | 合并前 `git diff origin/main...HEAD` 通读一遍 |
| **Review 重点** | 逻辑 > 风格；非阻塞建议用 `nit:` 前缀 |
| **跨域变更** | 必须加被影响域 owner 为 reviewer（PR-06） |
| **合并后** | 立即删除功能分支（GitHub 可配置自动） |

---

## 六、Worklog + STATUS（每日）

**为什么必做**：[pre-push 钩子 `scripts/check_worklog.py`](docs/conventions/06-documentation_文档规范.md) 强制 — 不写不让推。

**写什么**（`worklogs/{你的名字}/YYYY-MM-DD_<简短描述>.md`，模板见 `worklogs/template.md`）：

```markdown
# YYYY-MM-DD — <一句话>

## 今日完成
- ...

## 决策
- ADR 链接 / 简短理由

## 阻塞
- 无 / 描述

## 下一位接手
- 当前进度 + 关键文件 + 注意事项
```

**STATUS.md**（根目录）：把你那一行（"正在做 / 阻塞 / 本周完成"）同步更新。

> 未在 `STATUS.md` 「Git ↔ 目录映射」表的协作者，push 前先在表里加行（pre-push 校验靠这张表识别 worklog 所在子目录）。

---

## 七、本地钩子（首次克隆后必装）

```bash
pre-commit install --hook-type pre-push
pre-commit install
```

**钩子清单**（详见 `.pre-commit-config.yaml`）：

| 阶段 | 钩子 | 作用 |
|------|------|------|
| commit-msg | commitlint | Conventional Commits + scope-enum |
| pre-push | ruff / ruff-format | 后端 lint + format |
| pre-push | eslint | 前端 lint |
| pre-push | tsc | 前端类型检查 |
| pre-push | branch-name | 分支命名 `feature/<domain>/<desc>` |
| pre-push | worklog-check | worklog + STATUS 更新 |
| pre-push | doc-check | 文档命名 + CLAUDE 引用 + hooks 装机 |
| pre-push | secret-scan | 密钥泄露扫描 |
| pre-push | dead-links | 文档死链检查 |

> **绕过钩子 = 流程违规**（[PR-10 红线](docs/conventions/03-git_Git协作规范.md)）。确有特殊原因需 `--no-verify`，先在 PR 描述里写明。

---

## 八、测试

| 层级 | 命令 | 覆盖目标 |
|------|------|---------|
| 后端单测 | `cd src/backend && pytest -q` | ≥ 80%（行）/ 70%（分支） |
| 前端单测 | `cd src/frontend && npm test` | ≥ 70% |
| E2E | `cd src/frontend && npx playwright install --with-deps chromium && node scripts/screenshot_p0_p1.cjs` | 5 Core User Stories（roadmap 5.4 推进中） |
| Lint 全套 | `scripts/verify.bat` | 0 error |

**TDD 循环**：红（写失败测试）→ 绿（最小实现）→ 重构。功能点的 BDD 场景（`docs/specs/04-commands §六`）逐条转测试用例。

**Adapter / FSM 必测路径**（[T-05 / T-06](docs/conventions/05-testing_测试规范.md)）：

- Adapter：成功 / 限流 / 超时 / API key 失效 / 流式中断
- FSM：合法转换 / 非法拒绝 / 幂等键去重 / 边界条件

---

## 九、接口 / 数据 / 架构变更（PR-01 / PR-09）

| 改动 | 必做 |
|------|------|
| **API endpoint** | 先冻结 `docs/specs/04-commands_命令接口.md` → 2 人 Review Approve → 才实现 |
| **数据模型** | 改 `docs/specs/03-data-model_数据模型.md` + 生成 Alembic migration（`alembic revision --autogenerate -m "..."`） |
| **架构** | 改 `docs/specs/01-architecture_*.md` → 再写代码 |
| **新 Agent 系统** | [01-architecture §4.2 AR-02 流程](docs/conventions/01-architecture_架构设计规范.md) + ADR（`worklogs/decisions/NNNN-*.md`） |
| **里程碑结束** | 更新 `docs/specs/00-overview_项目主规格.md` 状态表 |

> 改 spec 与改代码是 **同一次 PR**，按顺序 commit（spec 在前，代码在后），便于 review。

---

## 十、常见反模式（来自 03-git §四）

### ❌ 巨型 PR

`PR: 重构 chat 域 + 加 orchestration + 修 toolchain + 改文档（+3200 -1800，47 文件）`
→ 无法 Review，出问题难 bisect。
✅ 拆 3 个聚焦单主题 PR，各 15 分钟可审完。

### ❌ 模糊提交

`git commit -m "fix"` / `"WIP"` / `"改了些东西"`
→ 3 个月后 `git log` 成天书。
✅ `fix(chat): WS 重连后 message order 错乱` + body 写动机。

### ❌ 跨 scope 提交

`feat: 新增 group + 修复 task FSM + 改前端样式`
→ 一次 commit 牵动 3 个域。
✅ 拆成 3 个 commit，scope 各自独立。

### ❌ 在 main 上开发

直接在 main 上 commit → pre-push 校验拦截（PR-02），白浪费工作。
✅ 工作前先 `git checkout -b feature/<domain>/<desc>`。

---

## 十一、遇到问题

| 场景 | 找谁 / 看哪 |
|------|------------|
| 后端代码 / API / 数据模型 | `backend-developer` agent · `docs/conventions/02-coding_*.md` |
| 前端组件 / 样式 | `frontend-developer` agent · `docs/conventions/02-coding_*.md` |
| 文档 / SPEC / ADR | `docs-writer` agent · `docs/conventions/06-documentation_*.md` |
| CI / workflow / verify 脚本 | `ci-engineer` agent · `docs/CI-STATUS_CI状态说明.md` |
| 测试 / E2E | `fullstack-tester` agent · `docs/conventions/05-testing_*.md` |
| 流程红线 / 不确定怎么走 | `docs/conventions/10-process-rules_流程红线全集.md` |
| Bug / 阻塞 | 工作群同步 → STATUS.md 标 ⚠️ |

---

## 十二、关联文档

- [README.md](README.md) — 项目入口
- [CLAUDE.md](CLAUDE.md) — AI/Agent 入口
- [docs/conventions/03-git_Git协作规范.md](docs/conventions/03-git_Git协作规范.md) — 本规范的完整版
- [docs/conventions/10-process-rules_流程红线全集.md](docs/conventions/10-process-rules_流程红线全集.md) — PR-01~09 完整流程红线
- [docs/CI-STATUS_CI状态说明.md](docs/CI-STATUS_CI状态说明.md) — CI workflow 详细说明
- [docs/plan/开发清单_roadmap.md](docs/plan/开发清单_roadmap.md) — 当前任务进度
- [STATUS.md](STATUS.md) — 协作仪表盘数据源
