# AgentHub

IM 聊天式多 Agent 协作平台。用户通过类飞书聊天界面与 AI Agent 对话，支持单聊、群聊（@mentions 多 Agent）、任务自动分解与并行调度。

> 脚手架基于 `docs/plan/背景_PRD_AgentHub_统一方案.md` 与 `docs/specs/01b-architecture-design_分层与数据流.md` 生成。

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

### Docker 一键启动（推荐）

```bash
cp .env.example .env            # 填入 LLM API Key
cd src/docker
docker compose up --build
```

- 前端：http://localhost:5173
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
```

## 文档

设计文档位于 `docs/`：

- 产品需求：`docs/plan/背景_PRD_AgentHub_统一方案.md`
- 架构设计：`docs/specs/01b-architecture-design_分层与数据流.md`
- 适配器接口契约：`docs/specs/04c-adapter-interface_适配器接口规范.md`
- 技术探索索引：`docs/explore/README.md`
- 项目演进日志：`docs/explore/EVOLUTION.md`
