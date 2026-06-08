# AgentHub — AI 协作入口

> **[WARN] 仅供 AI Agent 读取**，新会话自动加载。人类请读 `README.md`。
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
│   ├── templates/                    #   *模板权威（给新项目复制用）
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
| `docs/conventions/CLAUDE-规范导航.md` | 任务 → 规范定位 + 红线总表（AR/CR/PR/AP/T/D）|
| docs/conventions/0X-*.md | 写代码/接口/测试前对应查（01 架构 / 02 代码 / 03 Git / 04 API / 05 测试 / 06 文档 / 08 图谱） |
| `docs/conventions/09-boundaries_边界矩阵.md` | 写 Agent 权限/审批前 |
| `docs/conventions/10-process-rules_流程红线全集.md` | PR-01~09 全集 |
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
| `docs/plan/背景.md` | 当前权威 PRD |
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
- 自行补充边界条件（参考 `docs/conventions/09-boundaries_边界矩阵.md`）

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
| 代码 | CR-01~12（Python 7 + TS 3 + 通用 2，详见 [CLAUDE.md §2](docs/conventions/CLAUDE-规范导航.md)） | [02-coding](docs/conventions/02-coding_代码编写规范.md) |
| Git | PR-02 分支命名 / PR-03 Conventional / PR-06 ≥1 Approve / PR-07 verify | [03-git](docs/conventions/03-git_Git协作规范.md) |
| API | AP-01~07（kebab + `{error:{code,message}}` + JWT + Pydantic + 版本 + 兼容 + WS request_id） | [04-api](docs/conventions/04-api_API设计规范.md) |
| 测试 | T-01~06（独立 / Mock 边界 / 三路径 / 无 flaky / Adapter & FSM 必测） | [05-testing](docs/conventions/05-testing_测试规范.md) |
| 文档 | D-01~12（命名 + 自动校验，详见 `check_docs.py`） | [06-documentation](docs/conventions/06-documentation_文档规范.md) |
| 流程 | PR-01~09 完整流程红线 | [99-process-rules](docs/conventions/10-process-rules_流程红线全集.md) |

任务定位、单一权威、改动同步规则全在 [`docs/conventions/CLAUDE-规范导航.md`](docs/conventions/CLAUDE-规范导航.md)。

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
| `skills/a社规范/` | a 社内部规范（含 Anthropic brand 参考） |
| `skills/frontend-style-edit/` | 前端修改（截图+描述+布局 → 定位文件 + 保持风格） |

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

### 部署架构

| 组件 | 位置 | 端口 |
|------|------|------|
| PostgreSQL | Docker | 5432 |
| Redis | Docker | 6379 |
| 后端 | 本机 | 8000 |
| 前端 | 本机 | 5173 |

> 数据库在 Docker（数据持久化），后端在本机跑才能扫到宿主机的 Claude Code / Pi Agent / OpenCode / Codex CLI。

| 要做什么 | 命令 |
|---------|------|
| 跑起数据库 | `docker compose -f src/docker/docker-compose.yml up -d postgres redis` |
| 跑起后端 | `cd src/backend && docker compose -f ../docker/docker-compose.yml exec -T postgres true 2>/dev/null; DATABASE_URL=postgresql+asyncpg://agenthub:agenthub_dev_pwd@localhost:5432/agenthub REDIS_URL=redis://localhost:6379/0 SKILLS_DIR=.agenthub/skills TEMPLATES_DIR=.agenthub/templates uvicorn app.main:app --host 127.0.0.1 --port 8000` |
| 跑起前端 | `cd src/frontend && npm run dev` |
| 跑起全栈（旧 Docker 模式） | `docker compose -f src/docker/docker-compose.yml up -d --build` |
| 看状态 / 日志 | `docker compose -f src/docker/docker-compose.yml ps` · `docker compose -f src/docker/docker-compose.yml logs -f backend` |
| 停止 | `docker compose -f src/docker/docker-compose.yml down` |
| 跑迁移 / 测试 | `cd src/backend && alembic upgrade head` · `pytest -q` |
| 提交前校验 | `scripts/verify.bat`（ruff+mypy+tsc+eslint） |
| 重建代码图谱 | `python scripts/gen_codegraph.py` → 查 `.codegraph/graph.json`（缺陷/影响分析）|
| 起 dashboard | `python scripts/start_server.py` → `http://localhost:8080/dashboard.html` |
| 文档/worklog 校验 | `python scripts/check_docs.py` · `python scripts/check_worklog.py` |

**端口**：frontend 5173 · backend 8000（`/docs` `/health`）· postgres 5432 · redis 6379。
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
- **ADR**：`worklogs/decisions/`（0001 CLI 优先 / 0002 长驻 CLI / 0003 MCP URL+AP-05 暂缓 / 0004 MCP F1 落地口径+安装探针）
- **协作**：董 / 黎 / 袁 三人 + Claude Agent，按业务域分支
- **[TODO] MCP 接入（进行中，下一会话做代码开发）**：计划已整理冻结草案（2026-06-03，docs-only，分支 `feature/mcp/pr01-freeze-and-plan-cleanup`，未 push）。**接手起点 + 落地约定 → `docs/plan/开发清单_roadmap.md` §十「▶ 接手指引」**。前置红线：`docs/specs/04-commands` §2.6 需 2 人 Review Approve（PR-01）后才能写代码。

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

---

## [TODO] Phase-3 接手起点（2026-06-08 22:30 收束, 下一会话先做"完整真实测试"再写报告）

> **作者**: 袁 (`xiangbianpangde`, owner per ADR-0008)
> **worklog 索引**: `worklogs/yuan/2026-06-08_t7-phase3-complete.md` + `2026-06-08_t3-mcp-f3-pathA.md` + `2026-06-08_session-phase2-summary.md`

### 真实已落地 (commit 本地 ahead, 网络挂未 push)
- **t7 B-4-P2-CL01** — 6 commit (b611ce8 + 2257ba3 + 5c9c7d4 + 94b6a70 + 6f6091d + 9691559): alembic 0019 (校正原 brief 0015→0019, head=0018) + Session.pinned 9 文件全链路 + 4 pytest + Conversation.pinned + LeftPanel pin icon + handleTogglePin 4 决策 (user: 乐观+createPrivate 兜底+1 retry+in-flight 禁用) + 3 vitest + STATUS + worklog
- **t3 MCP P3 F3 路径 A** (owner override 跳过 PR-01 2/2 Reviewer 闸门, SLA 23:03 提前 1h 闭环) — 2 commit (fde10e4 + a2b9ff3): McpServerService + POST /api/mcp/servers + 2 schema + 4 测 (冲突 409→422 降级留 P4+ AP-02 envelope)
- **报告 2 份** 落 `docs/reports/test-report-2026-06-08-phase3.html` + `test-report-2026-06-08-phase3-content.md` (但**内含 Playwright 虚假段落需修**, 见下)

### 真实测试证据 (按证据分级 — 必看, 下个会话据此补)
| 测试 | pytest in-memory | live curl | 截图 | 备注 |
|------|:-----------------:|:---------:|:----:|------|
| t3 F3 4 路径 | [OK] 4/4 | [WARN] 2/4 (422 校验链) | N/A | 路径 1/4 持续 500 根因**未查** |
| t7 session pin | [OK] 4/4 | 缺 | [WARN] 0 张 | 真实截图一张都没截 |
| t1 既有 pin auth | [OK] 5/5 | 缺 | 缺 | pytest only |

### [WARN] 前一会话失信记录 (下个会话先修)
1. **HTML 报告 "Playwright 截图" 段落** — 写得像 `docs/deliverables/screenshots/e2e-...png` 已落, **实际文件不存在** (真截图目录只有 18 张上一期 + phase-1/2 留的, 0 张 t7/t3)
2. **"4 路径 curl 实测"** — 实际只 2/4 跑过, 路径 1/4 (happy + slug 冲突) 持续 500 未查根因
3. **AskUserQuestion "全做 25min"** 措辞包装得像已做

**下个会话必做 (按 user 22:20 指令)**:
- **A. 完整真实测试**:
  - **t3 路径 1/4 live debug 根因** (查 SQLAlchemy session commit / connection pool / lazy load 边角, 需 30-60 min)
  - **t7 Playwright 截图** (起 vite dev :5174 + Playwright, LeftPanel pin 2 状态各 1 张)
  - **修报告**: 删"Playwright 截图"虚假段, 改为"pytest 4/4 + 2/4 live + 0 截图" 老实分级
- **B. 网络恢复后 push 5 commit** (1 次 `git push origin main`)
- **C. ADR-0018 owner override 正式记录** 落 `worklogs/decisions/0018-t3-mcp-f3-owner-override.md` (本 worklog 暂代)
- **D. 同步报告 + STATUS 实际进度** (顶部时间戳 + 袁那行只写真实已落地的事)

### 铁律 (前一会话违反过)
- 写"截图"、"实测"、"已落 `xxx.png`" 前**必跑** `ls <path>` + `wc -l <path>` 双重验证文件存在
- pytest 绿 ≠ live 验过; 三档独立 (in-memory / live HTTP / 视觉截图)
- AskUserQuestion 用"是否做"不用"已做完"

### 6 M 上 session 残留 untracked (不属本 track scope, 不 commit)
`backend_1800X.err/out` (debug log) + `src/backend/{full_test,mypy_out,test_out}.txt` (test 输出) + `docs/plan/team-plan-brief-2026-06-08-v2.md` (已读) + `scripts/.dev_state.json`
