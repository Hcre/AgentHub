# AgentHub

[![CI](https://github.com/Hcre/AgentHub/actions/workflows/ci.yml/badge.svg)](https://github.com/Hcre/AgentHub/actions/workflows/ci.yml)
[![Coverage Backend](https://img.shields.io/badge/backend%20cov-%E2%89%A580%25-brightgreen)](src/backend/pyproject.toml)
[![Coverage Frontend](https://img.shields.io/badge/frontend%20cov-%E2%89%A570%25-brightgreen)](src/frontend/package.json)
[![Conventional Commits](https://img.shields.io/badge/commits-conventional-blue)](CONTRIBUTING.md)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](#)

IM 聊天式多 Agent 协作平台。用户通过类飞书聊天界面与 AI Agent 对话，支持单聊、群聊（@mentions 多 Agent）、任务自动分解与并行调度。

> 脚手架基于 `docs/plan/PRD_AgentHub_统一方案.md` 与 `docs/specs/01b-architecture-design_分层与数据流.md` 生成。
>
> 📘 **贡献者必读**：[CONTRIBUTING.md](CONTRIBUTING.md)（分支 / 提交 / PR / Review 规范）· [docs/CI-STATUS_CI状态说明.md](docs/CI-STATUS_CI状态说明.md)（CI workflow 详情）

## 架构

7 层洋葱模型，后端落地为 5 层（L1 Infrastructure → L2 Domain → L3 Application → L4 API → L5 Presentation）。

```
L5 Presentation   React 18 + TS (src/frontend/)
L4 API Gateway    FastAPI Routers / WS Handlers (src/backend/app/api/)
L3 Application     Service 用例编排 (src/backend/app/application/)
L2 Domain          实体 + Task Engine (FSM/Harness/Coordinator) (src/backend/app/domain/)
L1 Infrastructure  PG / Redis / Celery / LLM Adapter (src/backend/app/infrastructure/)
```

依赖方向：`L5 → L4 → L3 → L2 ← L1`（L1 实现 L2 定义的抽象接口，依赖倒置）。

## 技术栈

| 层 | 选型 |
|----|------|
| 前端 | React 18 + TypeScript (strict) + Vite + Zustand |
| 后端 | FastAPI + Pydantic v2 + SQLAlchemy 2.0 (async) |
| 数据库 | PostgreSQL 16 + pgvector |
| 缓存/队列 | Redis 7 (缓存 + Pub/Sub) + Celery |
| 部署 | Docker Compose + Nginx |

## MVP 范围（Phase 1）

只做这 6 个 P0 功能，其余延后：

1. 项目脚手架（FastAPI + React + Docker Compose）✅ 本脚手架
2. WebSocket 实时通信
3. 会话模型（sessions/messages CRUD）
4. 单 Agent 对接（Claude Code Adapter）
5. 流式输出（SSE → WS → StreamingText）
6. L1 短期记忆（Redis 滑动窗口 20 条）

## 快速开始

### 一行启动（Docker，推荐）

```bash
cp .env.example .env            # 填入 LLM API Key
docker compose -f src/docker/docker-compose.yml up --build -d
```

- 前端：http://localhost:5174
- 后端 API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 本地开发

后端：

```bash
cd src/backend
python -m venv .venv && . .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd src/frontend
npm install
cp .env.example .env
npm run dev
```

### 5 分钟贡献者流程

```bash
# 1. 克隆 + 装钩子（首次必做）
git clone https://github.com/Hcre/AgentHub.git
cd AgentHub
pre-commit install --hook-type pre-push && pre-commit install

# 2. 切分支（格式 feature/<domain>/<desc>）
git checkout -b feature/chat/ws-reconnect

# 3. 改代码 + 写测试 + 写 worklog
#    (worklogs/{你的名字}/YYYY-MM-DD_*.md + 更新 STATUS.md)

# 4. 提交前校验
scripts/verify.bat            # ruff + mypy + tsc + eslint + pytest + vitest

# 5. commit + push + 开 PR（PR 模板在 .github/PULL_REQUEST_TEMPLATE.md）
git commit -m "feat(chat): WS 重连后 message order 保持升序"
git push -u origin feature/chat/ws-reconnect
gh pr create --fill
```

> 详细规范见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 使用手册

### 部署架构

| 组件 | 位置 | 端口 |
|------|------|------|
| PostgreSQL | Docker | 5432 |
| Redis | Docker | 6379 |
| 后端 | 本机 | 8000 |
| 前端 | 本机 | 5173 |

### 服务与端口

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | http://localhost:5173 | Vite dev server |
| backend | http://localhost:8000 | FastAPI；`/docs` Swagger、`/health` 健康检查 |
| postgres | 5432 | pgvector |
| redis | 6379 | 缓存 |

### 日常运维

```bash
# 启动数据库
docker compose -f src/docker/docker-compose.yml up -d postgres redis

# 启动后端（本机，需要访问 CLI 扫描）
cd src/backend
DATABASE_URL=postgresql+asyncpg://agenthub:agenthub_dev_pwd@localhost:5432/agenthub REDIS_URL=redis://localhost:6379/0 uvicorn app.main:app --host 127.0.0.1 --port 8000

# 启动前端（本机）
cd src/frontend && npm run dev

# 停止
docker compose -f src/docker/docker-compose.yml down
docker compose -f src/docker/docker-compose.yml logs -f backend
docker compose -f src/docker/docker-compose.yml down

# 进容器跑迁移 / 测试
docker compose -f src/docker/docker-compose.yml exec backend alembic upgrade head
docker compose -f src/docker/docker-compose.yml exec backend pytest -q
```

> ⚠️ 若启动后见 postgres `Exited(127)` 或前端在 5173：是 Docker Desktop 开机自启的**重组前旧容器**。
> `docker rm -f $(docker ps -aq --filter name=agenthub)` 清掉，再用上面命令重建。

### 部署

```bash
# 一键部署到本地 Docker
scripts/deploy.bat

# 生产部署（Docker Compose + Nginx）
docker compose -f src/docker/docker-compose.yml -f src/docker/docker-compose.prod.yml up -d --build
```

完整部署文档：[docs/DEPLOYMENT-GUIDE_部署测试指南.md](docs/DEPLOYMENT-GUIDE_部署测试指南.md)。

### 校验与提交

```bash
scripts/verify.bat            # ruff + ruff-format + mypy + tsc + eslint（提交前必跑）
pre-commit install --hook-type pre-push && pre-commit install   # 克隆后首装钩子
```

### CI（GitHub Actions）

| Job | 步骤 | 触发 |
|-----|------|------|
| `backend` | ruff + ruff format + mypy + pytest（含 cov ≥ 80%） | push / PR |
| `frontend` | tsc + eslint + prettier + vitest + vite build | push / PR |
| `e2e` | vite build + preview + playwright screenshot | push / PR（前两个成功后） |
| `ci-status` | 汇总，required check | 上述之后 |

- 工作流文件：[`.github/workflows/ci.yml`](.github/workflows/ci.yml)
- 详细步骤 + cache 策略 + 故障排查：[`docs/CI-STATUS_CI状态说明.md`](docs/CI-STATUS_CI状态说明.md)
- PR 模板：[`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md)
- Reviewer 路由：[`.github/CODEOWNERS`](.github/CODEOWNERS)
- 实时状态：[GitHub Actions · AgentHub CI](https://github.com/Hcre/AgentHub/actions/workflows/ci.yml)

> 推荐在 Settings → Branches → main 配置 required check（见 [docs/CI-STATUS_CI状态说明.md §九](docs/CI-STATUS_CI状态说明.md)）。

### 进度看板 dashboard

```bash
python scripts/start_server.py    # 起本地 HTTP（dashboard 需 HTTP，不能 file:// 直开）
# 浏览器开 http://localhost:8000/dashboard.html（或脚本提示的端口）
```
解析根 `STATUS.md` 的按人协作表，展示董/黎/袁的「正在做 / 阻塞 / 本周完成」+ Git↔目录映射。

### 代码图谱（后端）

```bash
python scripts/gen_codegraph.py   # 重建图谱（改后端结构后跑）
```
- 人看：浏览器开 `.understand-anything/graph.html`（分层依赖图，点节点看上下游）或 `docs/CODE-MAP_代码地图.md`；也可在 dashboard「图谱」Tab 内直接查看
- AI 查：`.codegraph/graph.json`（节点/边/缺陷：跨层违规、循环依赖、死代码）

## 目录结构

```
agenthub/
├── README.md           # ← 你正在读的文件（人类入口）
├── CLAUDE.md           # AI/Agent 入口
├── STATUS.md           # 进度仪表盘数据源
├── dashboard.html      # 可视化进度面板
├── src/                # 产品代码
│   ├── backend/        #   L1-L4 FastAPI
│   │   └── app/        #     api/ application/ domain/ infrastructure/ core/ schemas/
│   ├── frontend/       #   L5 React + TypeScript
│   └── docker/         #   Docker Compose + Nginx + Postgres
├── skills/             # 通用 Claude Code Skills（根目录，供 Claude Code 扫描）
├── .agenthub/          # 运行时配置 + 项目专有 Skill（小红书系列；docker 挂载 skills/）
├── docs/               # 协作文档
│   ├── conventions/    #   规范 01-08 + ai-workflow + 99-* 附录
│   ├── plan/           #   PRD / 路线图 / 任务分配
│   ├── specs/          #   功能规格（含 domains/）
│   ├── design/         #   复杂功能设计（群聊系列）
│   ├── templates/      #   ★模板权威（给新项目复制用）
│   ├── reports/        #   汇报产出 + HTML 渲染产物
│   ├── research/       #   调研
│   ├── explore/        #   技术探索 + EVOLUTION 演进日志
│   └── archive/        #   历史版本文档归档（DEPRECATED_ 前缀）
├── worklogs/           # 工作日志（按人分子目录）+ decisions/ ADR
│   ├── 董/ 黎/ 袁/
│   └── decisions/      #   ADR（架构决策记录）
├── meta/FILE_GRAPH.md  # 文件归类权威
└── scripts/            # 自动化脚本（含 check_docs.py / check_worklog.py）
```

### 文档约定

| 目录 | 读者 | 命名规则 | 示例 |
|------|------|----------|------|
| `docs/` 根 | 人类 | `{English}_{中文}.md` | `DEPLOYMENT-GUIDE_部署测试指南.md` |
| `docs/specs/` | Agent | `NN-<name>_<中文>.md` | `03-data-model_数据模型.md` |
| `docs/plan/` | Agent + 人 | 同上 | `开发清单_roadmap.md` |
| `docs/explore/` | 人类 | `EXP-NN_` / 个人子目录 | `EXP-01_架构模式对比矩阵.md` |
| `docs/archive/` | 溯源 | `DEPRECATED_{原名}.md` | `DEPRECATED_PRD_v3.md` |
| `worklogs/{你的名字}/` | 队友 | `YYYY-MM-DD_{描述}.md` | `2026-05-28_修复一致性.md` |
| `worklogs/decisions/` | Agent | `NNNN-<slug>.md` | `0001-cli-first-pivot.md` |

> 所有文档提交前自动检查命名规范（`check_docs.py` pre-push hook）。

## 测试

```bash
cd src/backend && pytest          # 后端单测，覆盖率目标 80%
cd src/frontend && npm run test   # 前端单测

# E2E（Playwright，screenshot 抓取）
cd src/frontend && npx playwright install --with-deps chromium
node scripts/screenshot_p0_p1.cjs
```

测试策略详见：[`docs/specs/05-testing-strategy_测试策略.md`](docs/specs/05-testing-strategy_测试策略.md) · [测试规范](docs/conventions/05-testing_测试规范.md)。

## 文档

设计文档位于 `docs/`：

- 产品需求：`docs/plan/PRD_AgentHub_统一方案.md`
- 架构设计：`docs/specs/01b-architecture-design_分层与数据流.md`
- 适配器接口契约：`docs/specs/04c-adapter-interface_适配器接口规范.md`
- 技术探索索引：`docs/explore/README.md`
- 项目演进日志：`docs/explore/EVOLUTION.md`
- CI 状态说明：`docs/CI-STATUS_CI状态说明.md`
- 贡献者手册：[CONTRIBUTING.md](CONTRIBUTING.md)

## 贡献

欢迎贡献。开始前请读 [CONTRIBUTING.md](CONTRIBUTING.md)（分支命名 / 提交规范 / PR 流程 / Review 规则）。流程红线全集见 [docs/conventions/10-process-rules_流程红线全集.md](docs/conventions/10-process-rules_流程红线全集.md)。
