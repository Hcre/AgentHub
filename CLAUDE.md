# AgentHub — AI 协作入口

> **⚠️ 仅供 AI Agent 读取**，新会话自动加载。人类请读 `README.md`。
> 读完本文档再开始任何工作，约 2 分钟。每个功能点完成后更新「当前状态」。

---

## 项目定位

IM 聊天式多 Agent 协作平台。**5 层洋葱架构**（L1 Infrastructure → L2 Domain → L3 Application → L4 API → L5 Presentation），依赖方向 `L5 → L4 → L3 → L2 ← L1`（L1 实现 L2 接口，依赖倒置）。

技术栈：FastAPI + React/TypeScript + PostgreSQL + Redis + Docker。LLM 接入：**SDK/CLI 双轨**（`LLMAdapter` + `AgentRuntime`），**CLI 优先**（见 [`worklogs/decisions/0001-cli-first-pivot.md`](worklogs/decisions/0001-cli-first-pivot.md)）。

---

## 目录索引

```
AgentHub/
├── CLAUDE.md README.md STATUS.md dashboard.html   # 顶层入口
├── src/                              # 【产品代码】
│   ├── backend/app/                  #   5 层洋葱：api/ application/ core/ domain/ infrastructure/ schemas/
│   ├── frontend/src/                 #   React + TypeScript
│   └── docker/                       #   docker-compose + nginx + postgres
├── skills/                          # 【通用 Claude Code Skills】（根目录，供 Claude Code 扫描）
├── .agenthub/                       # 【运行时配置 + 项目专有 Skill】config.json + skills/ (xhs 系列)
├── docs/                            # 【协作文档】
│   ├── conventions/                  #   规范 01-08 + ai-workflow/ + 99-* 附录
│   ├── plan/                         #   PRD / 路线图 / 任务分配
│   ├── specs/                        #   功能规格（含 domains/）
│   ├── design/                       #   复杂功能设计（群聊系列）
│   ├── templates/                    #   ★模板权威（给新项目复制用）
│   ├── reports/                      #   汇报产出 + HTML 渲染
│   ├── research/                     #   调研
│   ├── explore/                      #   技术探索 + EVOLUTION 演进日志
│   └── archive/                      #   历史快照（DEPRECATED_ 前缀）
│   ├── plan/后续升级计划/MCP接入/    #   MCP 接入修订版（单一权威入口 README-REVISION.md）
├── worklogs/                         # 【工作日志】按人分子目录 + decisions/ ADR
│   ├── {董,黎,袁}/
│   └── decisions/
├── meta/FILE_GRAPH.md               # 【元信息】文件归类权威
├── scripts/                         # 工具脚本（check_*.py / verify / deploy / ...）
└── _assets/                         # 本地资产（scraps/screenshots/uploads，gitignored）
```

按需读取，不要一次性读完。

| 文档 | 何时读 |
|------|--------|
| `meta/FILE_GRAPH.md` | 新增/移动文件前（决策树） |
| `docs/conventions/CLAUDE.md` | 任务 → 规范定位 + 红线总表（AR/CR/PR/AP/T/D）|
| docs/conventions/0X-*.md | 写代码/接口/测试前对应查（01 架构 / 02 代码 / 03 Git / 04 API / 05 测试 / 06 文档 / 08 图谱） |
| `docs/conventions/99-boundaries_边界矩阵.md` | 写 Agent 权限/审批前 |
| `docs/conventions/99-process-rules_流程红线全集.md` | PR-01~09 全集 |
| `docs/conventions/ai-workflow_AI协作开发流程/` | 流程方法论（调研→计划→开发→收束→汇报） |
| `docs/specs/00-overview_项目主规格.md` | 首次接触，了解全貌 |
| `docs/specs/01-architecture_架构定义.md` | 做架构决策前 |
| `docs/specs/01b-architecture-design_分层与数据流.md` | 写后端逻辑前查数据流 |
| `docs/specs/03-data-model_数据模型.md` | 改数据库前 |
| `docs/specs/04-commands_命令接口.md` | 写 API/WS endpoint 前 |
| `docs/specs/04b-adapter-cli-flow_适配器CLI流程分析.md` | CLI 模式完整调用链 |
| `docs/specs/04c-adapter-interface_适配器接口规范.md` | 接入新 Agent 系统前 |
| `docs/specs/05-testing-strategy_测试策略.md` | 写测试前（含 E2E 5 条 Core User Stories）|
| `docs/specs/02-assumptions_假设清单.md` | 理解隐含假设前提 |
| docs/specs/domains/ | 深入某个域时读对应文件（domain1-chat / domain2-orchestration / domain3-toolchain） |
| `docs/plan/开发清单_roadmap.md` | 领任务前，看当前进度 |
| `docs/plan/背景_PRD_AgentHub_统一方案.md` | 当前权威 PRD |
| `docs/plan/task-assignment_任务分配.md` | 分工 |
| docs/explore/ | 技术探索文档 → `docs/explore/README.md` 索引 + `docs/explore/EVOLUTION.md` 演进日志 |
| `docs/archive/` | 历史版本归档 |
| `worklogs/decisions/0001-cli-first-pivot.md` | 双轨架构决策记录 |

---

## 引用关系（改一处要同步哪些）

```
docs/conventions/规范 (01-08)  ←──互检──→  docs/specs/ (00-05 + domains)
        │                                     │
        │ ai-workflow/06-第三步_收束节点         │ 验收标准
        ↓                                     ↓
  src/backend/ + src/frontend/  ──落地──→  docs/specs/04b/04c (实现细化)

docs/plan/开发清单_roadmap.md ──驱动──→ STATUS.md ──被解析──→ dashboard.html
                                                     ↑
                          scripts/check_worklog.py 读 STATUS 的 Git↔人映射

每功能点完成产出 → worklogs/{你的名字}/YYYY-MM-DD_*.md
收束节点产出      → worklogs/decisions/NNNN-<slug>.md (ADR)
```

**关键约束**（修改时必须同步）：
1. 改 `docs/conventions/` 规范 → 同步对应 `docs/specs/` 规格
2. 新增功能点 → 同时写入 `docs/plan/开发清单_roadmap.md` 和根 `STATUS.md`
3. 改架构 → 先改 `docs/specs/01-architecture` → 再实现（PR-09）
4. 改数据模型 → 先改 `docs/specs/03-data-model` + Alembic migration（CR-03 + PR-09）
5. 改 API → 先冻结 `docs/specs/04-commands` → 2 人 Review → 才实现（PR-01）

---

## 行为准则

### 禁止
- 奉承话、空话、猜测 —— 不确定就查代码/文档
- 过度设计 —— 不做 spec 里没写的功能
- 跳过红线 —— `docs/conventions/` 任一条红线都不能违反
- 裸 `print` / 裸 SQL / `any` / `console.log` 生产路径

### 必须
- 技术决策前横向对比 2-3 个选项
- 质疑与 `docs/conventions/01-architecture` 或 AR-01~06 矛盾的方案
- 增量交付，每步验证
- 自行补充边界条件（参考 `docs/conventions/99-boundaries_边界矩阵.md`）

### 技术约束
- **Python**: FastAPI async + Pydantic v2 + SQLAlchemy ORM + ruff。禁同步阻塞（CR-12）
- **TypeScript**: strict mode + Zustand + 组件建议 < 200 行 + hooks 抽离（CR-07~09）
- **SQL**: Alembic migration。禁手动改表（CR-03）
- **提交**: Conventional Commits。分支 `feature/<domain>/<desc>`（PR-02/03）

---

## 红线速查（违反 = 打回）

| 维度 | 红线 | 详见 |
|------|------|------|
| 架构 | AR-01 5 层洋葱 / AR-02 新 Agent 只加 Adapter / AR-03 Harness 无 LLM / AR-04 Agent 不直通 / AR-05 FSM 事件溯源 / AR-06 system-model 解耦 | [01-architecture](docs/conventions/01-architecture_架构设计规范.md) |
| 代码 | CR-01~12（Python 7 + TS 3 + 通用 2，详见 [CLAUDE.md §2](docs/conventions/CLAUDE.md)） | [02-coding](docs/conventions/02-coding_代码编写规范.md) |
| Git | PR-02 分支命名 / PR-03 Conventional / PR-06 ≥1 Approve / PR-07 verify | [03-git](docs/conventions/03-git_Git协作规范.md) |
| API | AP-01~07（kebab + `{error:{code,message}}` + JWT + Pydantic + 版本 + 兼容 + WS request_id） | [04-api](docs/conventions/04-api_API设计规范.md) |
| 测试 | T-01~06（独立 / Mock 边界 / 三路径 / 无 flaky / Adapter & FSM 必测） | [05-testing](docs/conventions/05-testing_测试规范.md) |
| 文档 | D-01~12（命名 + 自动校验，详见 `check_docs.py`） | [06-documentation](docs/conventions/06-documentation_文档规范.md) |
| 流程 | PR-01~09 完整流程红线 | [99-process-rules](docs/conventions/99-process-rules_流程红线全集.md) |

任务定位、单一权威、改动同步规则全在 [`docs/conventions/CLAUDE.md`](docs/conventions/CLAUDE.md)。

---

## 可用 Skills

| Skill | 何时用 |
|-------|--------|
| `skills/feat-start/` | 开始新功能：读 spec → 建分支 → 更新 STATUS → 生成 worklog 模板 |
| `skills/feat-complete/` | 完成功能：跑 verify → 更新 roadmap → 提 PR → 写 worklog |
| `skills/git-workflow/` | Git 分支管理：同步 main / diff 审查 / 合并前检查 |
| `skills/code-review/` | CR 自查/互查：对照 AR/CR/PR 红线逐条 |
| `skills/doc-sync/` | 文档同步：个人探索归档 / 团队决策落地 / 例行审查 |
| `skills/deploy/` | 部署项目：docker compose up → 验证 |
| `skills/spec-driven-development/` | 新功能无 spec 时先写规格再写代码 |
| `skills/test-claude-adapter/` | ClaudeAdapter 联调 |
| `skills/前端统一规范/` | 前端规约 |

每个 Skill 内置检查清单，按步执行。AgentHub 项目专有 Skill（xhs/dbs 系列）在 `.agenthub/skills/`。

---

## 自动化检查

| 检查 | 方式 | 触发时机 |
|------|------|---------|
| ruff（禁 print / 同步阻塞 / 安全 / 注释代码块） | `verify.bat` + pre-commit | commit |
| eslint（no-console / max-lines / no-explicit-any） | `verify.bat` + pre-commit | commit |
| tsc typecheck | `verify.bat` + pre-commit | commit |
| commitlint（Conventional Commits + scope-enum） | pre-commit | commit-msg |
| gitleaks（密钥扫描） | pre-commit | commit |
| **worklog 更新** | `scripts/check_worklog.py` + pre-commit | **push** |
| 根 STATUS.md 日期 | `scripts/check_worklog.py` + pre-commit | **push** |
| **分支命名 `feature/<domain>/<desc>`** | `scripts/check_branch.py` + pre-commit | **push** |
| **文档命名合规（D-05~10）** | `scripts/check_docs.py` + pre-commit | **push** |
| **hooks 已安装（D-12）** | `scripts/check_docs.py` + pre-commit | **push** |
| CLAUDE.md 路径有效（D-11）| `scripts/check_docs.py` + pre-commit | **push** |

> **首次克隆后必装**：`pre-commit install --hook-type pre-push && pre-commit install`
> 否则以上所有检查都不会触发。

---

## 使用手册（操作速查）

> 详细人向手册见 `README.md` §使用手册；下表是 AI 高频操作命令。

| 要做什么 | 命令 |
|---------|------|
| 跑起全栈 | `docker compose -f src/docker/docker-compose.yml up -d --build` |
| 看状态 / 日志 | `docker compose -f src/docker/docker-compose.yml ps` · `... logs -f backend` |
| 停止 | `docker compose -f src/docker/docker-compose.yml down` |
| 跑迁移 / 测试 | `... exec backend alembic upgrade head` · `... exec backend pytest -q` |
| 提交前校验 | `scripts/verify.bat`（ruff+mypy+tsc+eslint） |
| 重建代码图谱 | `python scripts/gen_codegraph.py` → 查 `.codegraph/graph.json`（缺陷/影响分析）|
| 起 dashboard | `python scripts/start_server.py` → `http://localhost:8000/dashboard.html` |
| 文档/worklog 校验 | `python scripts/check_docs.py` · `python scripts/check_worklog.py` |

**端口**：frontend 5174 · backend 8000（`/docs` `/health`）· postgres 5432 · redis 6379。
**排错**：启动见 postgres `Exited(127)` 或前端在 5173 → 是开机自启的旧容器，`docker rm -f $(docker ps -aq --filter name=agenthub)` 清掉重建。

---

## 工作流程

> 流程全文见 `docs/conventions/ai-workflow_AI协作开发流程/`（01-07 共 7 篇）。

```
第零步 调研 → 第一步 计划（含预设收束节点）→ 第二步 迭代开发（每功能点循环）
                                                ↓
                                      扫描仓库 → 实现(TDD) → 可观测验证
                                      → 审查 diff → 人确认 → 更新记录 → commit
                                                ↓
                                      【AI 汇报】必做（默认对话内联）
                                                ↓
                                      【收束节点】人触发 / AI 闸门拦截
                                      四阶段：整理→测试→审计→验证 → ADR + 收束报告
```

### 每次工作前
1. `skills/git-workflow/` 检查分支 + 同步 main（不要在 main 上开发）
2. 读根 `STATUS.md` 了解其他人在做什么
3. 读 `docs/plan/开发清单_roadmap.md` 确认当前进度

### 每次工作后
1. 在 `worklogs/{你的名字}/` 下写日志（`YYYY-MM-DD_<简短描述>.md`，模板见 `worklogs/template.md`）
2. 更新根 `STATUS.md` 中你那一行（正在做 / 阻塞 / 完成了什么）
3. 完成 roadmap 任务 → 按 PR-08 更新验收状态
4. Commit + Push（feature branch → PR）

### 日志模板
见 `worklogs/template.md`。重点是「给下一位的交接」那一段 —— 让接手的人能无缝继续。

---

## 当前状态

- **进度**：见根 `STATUS.md`（dashboard.html 解析此文件可视化）
- **架构**：5 层洋葱（src/backend/app/{api,application,core,domain,infrastructure,schemas}）+ CLI/SDK 双轨适配器
- **规范**：v3.0（按通用开发规范模板对齐 + AgentHub 特化红线）
- **ADR**：`worklogs/decisions/`（0001 CLI 优先 / 0002 长驻 CLI / 0003 MCP URL+AP-05 暂缓）
- **协作**：董 / 黎 / 袁 三人 + Claude Agent，按业务域分支
- **🚧 MCP 接入（进行中，下一会话做代码开发）**：计划已整理冻结草案（2026-06-03，docs-only，分支 `feature/mcp/pr01-freeze-and-plan-cleanup`，未 push）。**接手起点 + 落地约定 → `docs/plan/开发清单_roadmap.md` §十「▶ 接手指引」**。前置红线：`docs/specs/04-commands` §2.6 需 2 人 Review Approve（PR-01）后才能写代码。

---

## 常见任务速查

| 用户说 | AI 做什么 |
|--------|----------|
| "加新功能 X" | 04 API 接口冻结（PR-01）→ 02 代码 → 05 测试 → 03 Git 提交 |
| "改架构 / 加新 Adapter" | 01 §4.2 AR-02 流程 + ADR（worklogs/decisions/） |
| "改数据库" | 01 AR-05 FSM + 02 CR-03 Alembic + docs/specs/03-data-model |
| "改 API endpoint" | 04 + PR-01 接口先行 2 人 Review + PR-09 SPEC 同步 |
| "写测试" | 05 测试规范 + Adapter/FSM 必测路径 |
| "提 PR / 合并" | 03 Git + 99-process-rules PR-06/07 |
| "新 Agent 系统" | 01 §4.2 + docs/specs/04c-adapter-interface |
| "写文档 / 移动文件" | 06 文档 + meta/FILE_GRAPH §三 决策树 |
| "Agent 操作权限" | 99-boundaries 边界矩阵 |
| "调用图 / 影响分析 / 代码地图" | 查 `docs/CODE-MAP_代码地图.md`（后端模块全景 + 入口表）；AI 查 `.codegraph/graph.json`（节点/边/缺陷）；人看 `.understand-anything/graph.html`（浏览器交互，dashboard「图谱」Tab 内嵌）；重建跑 `python scripts/gen_codegraph.py`。规范见 `docs/conventions/08-code-understanding_*` |
| "汇报" | 更新 worklog + STATUS（必做）→ 功能点汇报对话内联不落盘 |
| "收束" | 人触发，按 ai-workflow/06 四阶段（整理→测试→审计→验证）→ ADR + 收束报告 `docs/reports/` |
| "新增/移动文件" | 先查 meta/FILE_GRAPH §三 决策树 → 操作 → 同步 FILE_GRAPH → 汇报 |

---

## AI 产出文件写入规则

> **每次产出文件前查 `docs/conventions/06-documentation_文档规范.md` §三「文档放哪」决策表 + §三附「Git→人名映射」**。不知道自己是谁？跑 `git config user.name` 对照映射表。
