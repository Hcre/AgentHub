# CI 状态 — AgentHub

> **目的**：记录 GitHub Actions 工作流的设计、当前覆盖、本地复现方式、故障排查。
>
> 维护者：ci-engineer · 触发条件：`.github/workflows/ci.yml` 变更 / 任务脚本变更

## 一、Badge

```markdown
[![CI](https://github.com/Hcre/AgentHub/actions/workflows/ci.yml/badge.svg)](https://github.com/Hcre/AgentHub/actions/workflows/ci.yml)
```

实时链接：[GitHub Actions · AgentHub CI](https://github.com/Hcre/AgentHub/actions/workflows/ci.yml)

---

## 二、Workflow 总览

| Job | 触发条件 | 步骤 | 缓存 | Artifact | 期望耗时 |
|-----|---------|------|------|----------|---------|
| `backend` | push / PR | ruff lint + ruff format + mypy + pytest（含 cov） | pip | coverage-backend | < 6 min |
| `frontend` | push / PR | tsc + eslint + prettier + vitest + vite build | npm | frontend-dist | < 8 min |
| `e2e` | push / PR（需前两个 job 成功） | vite build + preview + playwright screenshot | npm | playwright-screenshots | < 4 min |
| `ci-status` | 上述三个 job 之后（always） | 汇总到 GitHub Step Summary | — | — | < 10 s |

**总耗时预算**：≤ 15 min（受单 job 15 min timeout 约束，串行总时长 ~ 18 min 已逼近上限，e2e 触发靠 `needs` 等待）。

**concurrency**：同 PR 后续 push 自动取消旧 run（`concurrency.cancel-in-progress: true`），节约 CI 配额。

---

## 三、详细步骤

### 3.1 backend job

| 步骤 | 命令 | 失败信号 |
|------|------|---------|
| ruff lint | `ruff check app/ --config pyproject.toml` | CR-01/12 违规 |
| ruff format | `ruff format --check app/ --config pyproject.toml` | 格式漂移 |
| mypy | `mypy app/` | 类型错误 / 缺签名 |
| pytest | `pytest -q --maxfail=5 --tb=short --cov=app --cov-report=xml` | 测试失败 / 覆盖率 < 80% |

环境变量（与 `src/backend/tests/conftest.py` 默认值一致）：

```yaml
SECRET_KEY: <test only>
DATABASE_URL: sqlite+aiosqlite:///:memory:
LLM_ADAPTER_MODE: mock
ENV: test
```

### 3.2 frontend job

| 步骤 | 命令 | 失败信号 |
|------|------|---------|
| tsc | `npx tsc -b --noEmit` | CR-07 strict / any 违规 |
| eslint | `npx eslint src/ --config eslint.config.js` | no-console / max-lines / no-explicit-any |
| prettier | `npx prettier --check "src/**/*.{ts,tsx,css}"` | 格式漂移 |
| vitest | `npm test -- --reporter=verbose --coverage` | 单测失败 / 覆盖率 < 70% |
| vite build | `npm run build` | 构建错误 |

### 3.3 e2e job

| 步骤 | 命令 | 失败信号 |
|------|------|---------|
| playwright install | `npx playwright install --with-deps chromium` | 浏览器未装 |
| vite build | `npm run build` | 构建错误 |
| vite preview（后台） | `npx vite preview --port 4173 --host 127.0.0.1` | 端口未起 |
| screenshot 抓取 | `node scripts/screenshot_p0_p1.cjs` | 抓取失败（**仅 warning，不阻塞**） |

> 当前 E2E 仅做 screenshot 抓取（[docs/specs/05-testing-strategy_测试策略.md §四 5 个 Core User Stories](./specs/05-testing-strategy_测试策略.md) 的真正 E2E assertion 在 road-map 5.4 后续推进；本 job 先把"基础 pipeline + 产物"立起来）。

### 3.4 ci-status job

汇总三个 job 的 `result`，写 `GITHUB_STEP_SUMMARY`；任一非 success 即 exit 1。

---

## 四、本地复现

一行命令等价于 CI：

```bash
# Windows
scripts/verify.bat

# Linux / macOS
bash scripts/verify.sh
```

如需逐项复刻 CI（更接近 GitHub Actions 环境）：

```bash
# Backend
cd src/backend
python -m pip install -r requirements.txt
ruff check app/ --config pyproject.toml
ruff format --check app/ --config pyproject.toml
mypy app/
pytest -q --cov=app --cov-report=term-missing

# Frontend
cd src/frontend
npm ci
npx tsc -b --noEmit
npx eslint src/ --config eslint.config.js
npx prettier --check "src/**/*.{ts,tsx,css}"
npm test -- --reporter=verbose --coverage
npm run build

# E2E
npx playwright install --with-deps chromium
npm run build
(npx vite preview --port 4173 --host 127.0.0.1 &) && sleep 3
node scripts/screenshot_p0_p1.cjs
```

---

## 五、Cache 策略

| Cache | Key | 命中条件 | 失效条件 |
|-------|-----|---------|---------|
| pip | `agenthub-ci-pip-3.11-<hash(requirements.txt + pyproject.toml)>` | 依赖未变 | requirements / pyproject 变更 |
| npm（actions/setup-node 内置） | `node-modules-<hash(package-lock.json)>` | package-lock 未变 | 依赖新增 / 升级 |

> 不缓存 `node_modules` 之外的 `dist / coverage / playwright-browsers`：dist 由 build 步骤现做，playwright 浏览器由 `playwright install` 显式管理，coverage 是结果非输入。

---

## 六、故障排查

### 6.1 `pytest` 失败

| 现象 | 排查 |
|------|------|
| `SECRET_KEY` 相关 AssertionError | 确认 `tests/conftest.py` 已 import（最早设环境变量）；CI env 已显式注入 |
| 数据库迁移相关 | CI 用 SQLite in-memory；本地如跑 PG migration 失败，先 `alembic downgrade base && alembic upgrade head` |
| 覆盖率 < 80% | 看 `coverage-backend` artifact 的 `coverage.xml`；新功能必须补测（T-03） |

### 6.2 `tsc` / `eslint` 失败

| 现象 | 排查 |
|------|------|
| `verbatimModuleSyntax` 报错 | TS 5+ 严格模式，type import 必须用 `import type` |
| `noUncheckedIndexedAccess` 报错 | 数组下标访问要判 `=== undefined` |
| ESLint `no-explicit-any` | CR-07 零容忍；改用 `unknown` + narrowing |

### 6.3 e2e 截图失败

- 当前为 **warning**，不阻塞 CI。失败排查：
  - `playwright-screenshots` artifact 是否生成
  - `npx vite preview --port 4173` 端口是否被占（CI 唯一 runner，不冲突；本地如冲突先 `netstat -ano | findstr 4173` 杀进程）
  - `scripts/screenshot_p0_p1.cjs` 输出目录 `docs/deliverables/screenshots/` 是否存在

### 6.4 Cache 命中率低 / install 慢

- 看 workflow 日志中的 "Cache hit" / "Cache miss"
- `actions/cache@v4` 输出 `Size of cache` 段
- 如频繁 miss：检查 `hashFiles` 路径是否覆盖所有 lock 文件

---

## 七、扩展计划（roadmap）

| 优先级 | 项 | 来源 | 状态 |
|--------|----|------|------|
| P0 | ✅ 3 jobs（backend / frontend / e2e）+ cache + artifacts + concurrency | 本 PR | 完成 |
| P1 | E2E 增加 assertion（5 Core User Stories [05-testing §四](./specs/05-testing-strategy_测试策略.md)） | roadmap 5.4 | 待办 |
| P1 | Codecov / SonarCloud 集成 | TBD | 待办 |
| P2 | Matrix 多 Python / 多 Node 版本 | 防版本漂移 | 待办 |
| P2 | Required check 强制（branch protection） | 需 Settings → Branches 配置 | 待办（[§九](#九-分支保护-推荐设置)） |
| P3 | Self-hosted runner 加速（Windows E2E） | Windows-only 测 | 待办 |

---

## 八、相关文件

| 路径 | 作用 |
|------|------|
| `.github/workflows/ci.yml` | CI 主工作流（本工程核心） |
| `.github/CODEOWNERS` | 路由 reviewer（PR 自动指派） |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR 模板（checklist + scope + test + risk） |
| `.pre-commit-config.yaml` | 本地钩子（commit 前 ruff + tsc + 分支命名 + worklog） |
| `scripts/verify.bat` / `verify.sh` | 本地一键校验（CI 三个 job 的本地等价物） |
| `scripts/check_*.py` | 分支命名 / worklog / 文档命名 / 密钥 / 死链 |
| `docs/CI-STATUS_CI状态说明.md` | 本文档 |

---

## 九、分支保护（推荐设置）

> GitHub repo → Settings → Branches → Branch protection rules → Add rule → Branch name pattern `main`

勾选：

- [x] **Require a pull request before merging**
- [x] **Require approvals**: 1（跨域接口/数据/架构 2 人）
- [x] **Dismiss stale pull request approvals when new commits are pushed**
- [x] **Require status checks to pass before merging**
  - Required checks: `Backend (pytest + ruff + mypy)` / `Frontend (vitest + eslint + tsc + build)` / `CI Gate Status`
- [x] **Require conversation resolution before merging**
- [x] **Restrict pushes** (只允许 merge 按钮 / 指定人)
- [ ] **Do not allow bypassing the above settings** （建议勾，强制所有 PR 走流程）

未勾选：

- ❌ **Require linear history**（AgentHub 习惯 `--no-ff` 保留里程碑分支，参见 [03-git §三 合并策略](conventions/03-git_Git协作规范.md)）
- ❌ **Include administrators**（admin 信任直推 main；per 项目约定）

---

## 十、变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-07 | v1.0 — 首次落地：3 jobs + cache + artifact + concurrency + 分支保护推荐设置 |
