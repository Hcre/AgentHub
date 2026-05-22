# AgentHub — AI 协作入口

> 读完本文档再开始任何工作。约 2 分钟。

## 项目定位

IM 聊天式多 Agent 协作平台。5 层洋葱架构（L1 Infrastructure → L2 Domain → L3 Application → L4 API → L5 Presentation）。技术栈：FastAPI + React/TypeScript + PostgreSQL + Redis + Celery + Docker。

依赖方向：`L5 → L4 → L3 → L2 ← L1`（L1 实现 L2 接口，依赖倒置）。

## 文档索引

按需读取，不要一次性读完。

| 文档 | 何时读 |
|------|--------|
| `docs/PRD_AgentHub.md` | 做任何功能前，了解 User Stories |
| `docs/架构设计_分层与数据流.md` | 写后端逻辑前，查数据流场景 |
| `docs/adapter_interface_spec.md` | 接入新 Agent 系统前 |
| `spec/AgentHub_SPEC_项目主规格.md` | 首次接触，了解全貌 |
| `spec/architecture_架构定义.md` | 做架构决策前 |
| `spec/data-model_数据模型.md` | 改数据库前 |
| `spec/commands_命令接口.md` | 写 API/WS endpoint 前 |
| `spec/boundaries_边界矩阵.md` | 写权限/审批逻辑前 |
| `spec/testing-strategy_测试策略.md` | 写测试前 |
| `spec/roadmap_开发路线图.md` | 领任务前，看当前进度 |
| `spec/domains/` | 深入某个域时读对应文件 |
| `spec/rules/arch-rules_架构红线.md` | 违反 = 方案打回 |
| `spec/rules/code-rules_代码红线.md` | 违反 = CR 不通过 |
| `spec/rules/process-rules_流程红线.md` | 违反 = 流程违规 |

## 行为准则

### 禁止
- 奉承话、空话、猜测 —— 不确定就查代码/文档
- 过度设计 —— 不做 spec 里没写的功能
- 跳过红线 —— rules/ 里任何一条都不能违反
- 裸 print / 裸 SQL / any / console.log 生产路径

### 必须
- 技术决策前横向对比 2-3 个选项
- 质疑与 architecture 或 arch-rules 矛盾的方案
- 增量交付，每步验证
- 自行补充边界条件（参考 boundaries.md）

### 技术约束
- **Python**: FastAPI async + Pydantic v2 + SQLAlchemy ORM + ruff。禁止同步阻塞。
- **TypeScript**: strict mode + Zustand + 组件建议 <200 行 + hooks 抽离
- **SQL**: Alembic migration。禁止手动改表。
- **提交**: Conventional Commits。分支 `feature/<domain>/<desc>`

## 可用 Skills

位于 `skills/` 目录，定义了可复用的 AI 工作流程：

| Skill | 何时用 |
|-------|--------|
| `feat-start` | 开始新功能：读 spec → 建分支 → 更新 STATUS → 生成 worklog 模板 |
| `feat-complete` | 完成功能：跑验证 → 更新 roadmap → 提 PR → 写 worklog |
| `code-review` | CR 自查/互查：对照三大红线逐条检查 |
| `deploy` | 部署项目：docker compose up → 验证 |
| `spec-driven-development` | 新功能无 spec 时，先写规格再写代码 |

每个 Skill 内置检查清单，按步执行。

## 自动化检查

| 检查 | 方式 | 触发时机 |
|------|------|---------|
| ruff (禁 print/同步阻塞) | `verify.bat` / pre-commit | commit |
| eslint (no-console/max-lines) | `verify.bat` / pre-commit | commit |
| tsc typecheck | `verify.bat` / pre-commit | commit |
| 分支命名 (PR-02) | `check_branch.py` / pre-commit | commit |
| **worklog 更新** | `check_worklog.py` / pre-commit | **push** |
| STATUS.md 日期 | `check_worklog.py` / pre-commit | **push** |

push 之前 worklog 检查自动运行，不通过会阻止 push。

## 协作流程

### 每次工作前
1. `git pull` 同步最新代码
2. 读 `STATUS.md` 了解其他人在做什么
3. 读 `spec/roadmap_开发路线图.md` 确认当前进度

### 每次工作后
1. 在自己的 `worklogs/` 目录下写日志（文件名: `YYYY-MM-DD_<简短描述>.md`）
2. 更新 `STATUS.md` 中你那一行（正在做 / 阻塞 / 完成了什么）
3. 如果完成了 roadmap 中的任务，按 PR-08 更新验收状态
4. Commit + Push（feature branch → PR）

### 日志模板
见 `worklogs/template.md`。重点是「给下一位的交接」那一段 —— 让接手的人能无缝继续。

## 目录结构

```
agenthub/
├── .agenthub/           # AI 入口 + 工作日志
│   ├── CLAUDE.md        # ← 你正在读的文件
│   └── worklogs/        # 个人日志 + STATUS.md
├── docs/                # 人类阅读（高频）：PRD、架构
├── spec/                # AI 参考（结构化）：数据模型、API、红线
│   ├── rules/           # 三大红线
│   └── domains/         # 按域拆分
├── skills/              # 可复用 AI 技能
├── backend/app/
│   ├── api/             # L4 路由 + WS
│   ├── application/     # L3 Service + Command + DTO
│   ├── domain/          # L2 实体 + Task Engine
│   └── infrastructure/  # L1 DB / Redis / LLM / WS
├── frontend/src/        # L5 React
├── docker/
└── scripts/             # 自动化脚本
```
