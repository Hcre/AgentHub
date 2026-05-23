# AgentHub

IM 聊天式多 Agent 协作平台。用户通过类飞书聊天界面与 AI Agent 对话，支持单聊、群聊（@mentions 多 Agent）、任务自动分解与并行调度。

> 脚手架基于 `docs/PRD_AgentHub.md` 与 `docs/架构设计_分层与数据流.md` 生成。

## 架构

7 层洋葱模型，后端落地为 5 层（L1 Infrastructure → L2 Domain → L3 Application → L4 API → L5 Presentation）。

```
L5 Presentation   React 18 + TS (frontend/)
L4 API Gateway    FastAPI Routers / WS Handlers (backend/app/api/)
L3 Application     Service 用例编排 (backend/app/application/)
L2 Domain          实体 + Task Engine (FSM/Harness/Coordinator) (backend/app/domain/)
L1 Infrastructure  PG / Redis / Celery / LLM Adapter (backend/app/infrastructure/)
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
cd docker
docker compose up --build
```

- 前端：http://localhost:5173
- 后端 API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 本地开发

后端：

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## 目录结构

```
agenthub/
├── README.md           # ← 你正在读的文件（人类入口）
├── CLAUDE.md           # AI/Agent 入口
├── docs/               # 人类阅读 — 当前权威文档
│   ├── explore/        #   技术探索过程 + ADR + 演进日志
│   └── archive/        #   历史版本文档归档
├── spec/               # Agent 参考 — 结构化规格
│   ├── rules/          #   三大红线
│   └── domains/        #   按域拆分
├── .agenthub/          # AI 协作基础设施
│   └── worklogs/       #   个人工作日志 + STATUS.md
├── skills/             # 可复用 AI 技能
├── frontend/           # L5 React + TypeScript
├── backend/            # L1-L4 FastAPI
│   └── app/
│       ├── api/            # L4 路由 + WS
│       ├── application/    # L3 Service + Command + DTO
│       ├── domain/         # L2 实体 + Task Engine
│       ├── infrastructure/ # L1 DB / Redis / LLM Adapter / WS
│       ├── core/           # 配置 / 安全 / 事件总线
│       └── schemas/        # Pydantic 请求/响应
├── docker/             # Docker Compose + Nginx
└── scripts/            # 自动化脚本（含 check_docs.py）
```

### 文档约定

| 目录 | 读者 | 命名规则 | 示例 |
|------|------|----------|------|
| `docs/` | 人类 | `{English}_{中文}.md` | `PRD_AgentHub_统一方案.md` |
| `docs/explore/` | 人类 | `EXP-NN_` / `ADR-NN-` / `作者-` | `EXP-01_架构模式对比矩阵.md` |
| `docs/archive/` | 溯源 | `DEPRECATED_{原名}.md` | `DEPRECATED_PRD_v3.md` |
| `spec/` | Agent | `{english}_{中文}.md` | `data-model_数据模型.md` |
| `worklogs/` | 队友 | `YYYY-MM-DD_{描述}.md` | `2026-05-23_修复一致性.md` |

> 所有文档提交前自动检查命名规范（`check_docs.py` pre-push hook）。

## 测试

```bash
cd backend && pytest          # 后端单测，覆盖率目标 80%
cd frontend && npm run test   # 前端单测
```

## 文档

设计文档位于 `docs/`：

- 产品需求：`docs/PRD_AgentHub_统一方案.md`
- 架构设计：`docs/architecture-design_架构设计_分层与数据流.md`
- 适配器接口契约：`docs/adapter-interface_适配器接口规范.md`
- 技术探索索引：`docs/explore/README.md`
- 项目演进日志：`docs/explore/EVOLUTION.md`
