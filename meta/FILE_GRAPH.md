# 文件架构图谱 (FILE_GRAPH) — AgentHub

> 本文件是仓库的**文件归类权威**。新增文件前先在此找到对应节点，按节点放置——禁止在仓库根目录随意堆放散文件。
>
> 更新: 2026-05-29 | 维护规则：新增/移动文件或目录时同步更新本图谱。
>
> 本次整合（2026-05-29）：产品代码归入 `src/`（backend/frontend/docker），协作文档归入 `docs/`。`skills/`（通用 Claude Code Skills）与 `.agenthub/`（运行时配置 + 项目专有 skill）保留在**根目录**——Claude Code 只扫描根 `skills/`，docker-compose 挂载根 `.agenthub/skills`。

---

## 一、目录树（带职责标注）

```
AgentHub/                                # 仓库根：仅放顶层入口文件 + meta/scripts/worklogs
│
├── CLAUDE.md                            # 顶层：AI 项目上下文（新会话自动加载）
├── README.md                            # 顶层：人类使用指南
├── STATUS.md                            # 顶层：进度仪表盘数据源
├── dashboard.html                       # 顶层：可视化进度面板
├── .gitignore / .env.example / .pre-commit-config.yaml
│
├── src/                                 # 【产品代码】
│   ├── backend/                         #   FastAPI（5 层洋葱）
│   │   ├── app/
│   │   │   ├── api/                     #     L4：HTTP 路由 + WebSocket
│   │   │   ├── application/             #     L3：Service + Command + DTO
│   │   │   ├── core/                    #     横切：DI 容器、配置加载
│   │   │   ├── domain/                  #     L2：实体 + Task Engine（禁 import 上层）
│   │   │   ├── infrastructure/          #     L1：DB / Redis / LLM Adapter / WS
│   │   │   ├── schemas/                 #     Pydantic v2 IO 模型
│   │   │   └── main.py
│   │   ├── alembic/                     #   数据库迁移（禁手动改表）
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   ├── frontend/                        #   React + TypeScript + Vite
│   │   ├── src/                         #     L5：UI
│   │   ├── public/ prototype/ docs/ 问题/
│   │   ├── package.json + vite.config.ts + tsconfig.*.json
│   │   └── Dockerfile
│   └── docker/                          #   docker-compose + nginx + postgres
│
├── skills/                             # 【通用 Claude Code Skills】根目录（Claude Code 扫描此处）
│   ├── code-review/ deploy/ doc-sync/ feat-complete/ feat-start/
│   ├── git-workflow/ spec-driven-development/ test-claude-adapter/
│   └── 前端统一规范/
│
├── .agenthub/                          # 【运行时配置 + 项目专有 Skill】根目录（docker 挂载 skills/）
│   ├── config.json                      #   运行时配置
│   └── skills/                          #   项目专有（dbs-xhs-title / html-ppt-xhs-post / xhs-interact）
│
├── docs/                               # 【协作文档】
│   ├── conventions/                     #   规范正文（开发者日常查阅）
│   │   ├── README.md                    #     入口索引
│   │   ├── README-规范导航.md            #     人类入口：快速索引 + 红线速查
│   │   ├── CLAUDE-规范导航.md            #     AI 入口：任务→规范定位 + 红线总表
│   │   ├── 01-architecture_架构设计规范.md   #   AR-01~06
│   │   ├── 02-coding_代码编写规范.md         #   CR-01~12
│   │   ├── 03-git_Git协作规范.md            #   PR-02/03
│   │   ├── 04-api_API设计规范.md            #   AP-01~07
│   │   ├── 05-testing_测试规范.md           #   T-01~06
│   │   ├── 06-documentation_文档规范.md     #   D-01~12
│   │   ├── 08-code-understanding_代码理解与图谱规范.md
│   │   ├── 99-boundaries_边界矩阵.md         #   Agent 操作权限矩阵
│   │   ├── 99-process-rules_流程红线全集.md  #   PR-01~09
│   │   └── ai-workflow_AI协作开发流程/        #   方法论（01-07）
│   ├── plan/                            #   项目计划与功能设计
│   │   ├── 背景_PRD_AgentHub_统一方案.md  #     PRD 权威
│   │   ├── 开发清单_roadmap.md            #     功能点列表
│   │   ├── task-assignment_任务分配.md   #     分工
│   │   └── 前端实施计划.md
│   ├── specs/                           #   功能规格
│   │   ├── 00-overview_项目主规格.md
│   │   ├── 01-architecture_架构定义.md
│   │   ├── 01b-architecture-design_分层与数据流.md
│   │   ├── 02-assumptions_假设清单.md
│   │   ├── 03-data-model_数据模型.md
│   │   ├── 04-commands_命令接口.md
│   │   ├── 04b-adapter-cli-flow_适配器CLI流程分析.md
│   │   ├── 04c-adapter-interface_适配器接口规范.md
│   │   ├── 05-testing-strategy_测试策略.md
│   │   └── domains/                     #     domain1-chat / domain2-orchestration / domain3-toolchain
│   ├── design/                          #   复杂功能设计文档（群聊系列）
│   ├── templates/                       #   ★模板权威来源（供新项目复制）
│   ├── reports/                         #   汇报产出 + HTML 渲染产物
│   ├── research/                        #   调研文档
│   ├── explore/                         #   技术探索 + EVOLUTION 演进日志（含个人子目录 黎/董/袁）
│   ├── archive/                         #   历史快照（DEPRECATED_ 前缀）
│   └── DEPLOYMENT-GUIDE_部署测试指南.md   #   运维向
│
├── worklogs/                           # 【工作日志】★按人分子目录
│   ├── 董/ 黎/ 袁/  YYYY-MM-DD_<desc>.md
│   ├── template.md
│   └── decisions/                       #   ADR，文件名 NNNN-<slug>.md
│
├── scripts/                            # 【工具脚本】
│   ├── check_worklog.py / check_docs.py / check_branch.py
│   ├── gen_worklog.py / start_server.py / 打开仪表盘.bat
│   ├── verify.{bat,sh} / deploy.{bat,sh} / code-review.{bat,sh}
│   ├── feat-start.{bat,sh} / feat-complete.{bat,sh}
│   ├── checkpoint.bat / pre-merge-check.sh
│   └── start-backend.sh / start-frontend.sh
│
├── meta/                               # 【元信息】描述仓库自身
│   └── FILE_GRAPH.md                    #   本文件
│
└── _assets/                            # 【本地资产】scraps/草图 + screenshots/截图 + uploads/上传（整目录 gitignored）
```

---

## 二、引用关系图谱（谁依赖谁）

```
docs/conventions/规范 (01-08)  ←──互检──→  docs/specs/ (00-05 + domains)
        │                                        │
        │ ai-workflow/06-第三步_收束节点            │ 验收标准
        ↓                                        ↓
  src/backend/ + src/frontend/  ──落地──→  docs/specs/04b-adapter-cli-flow 等实现细化
                                                 │
docs/templates/ ──复制为──→ 新项目的 CLAUDE/STATUS/README/plan/worklog
        │
        ↓ 实例化
   docs/plan/开发清单_roadmap.md ──引用──→ docs/specs/*    （功能点 ↔ 规格）
        ↓ 驱动
   STATUS.md ──被解析──→ dashboard.html ──由──→ scripts/start_server.py 启动
        ↓ 每个功能点产出
   worklogs/{董,黎,袁}/YYYY-MM-DD_*.md    （按人分子目录）
        ↓ 收束节点产出
   worklogs/decisions/NNNN-<slug>.md      （ADR，含 0001-cli-first-pivot 等）
        ↓ 全局总览
   CLAUDE.md（AI 上下文：目录 + 图谱 + 规则 + 任务指南）  ←── 与本 FILE_GRAPH.md 互为索引
```

**关键约束**（修改时必须同步）：
1. 改 `docs/conventions/` 规范 → 同步对应 `docs/specs/` 规格。
2. 新增功能点 → 同时写入 `docs/plan/开发清单_roadmap.md` 和 `STATUS.md` 表格。
3. `dashboard.html` 只解析根 `STATUS.md` 表格（fetch 路径 = `./STATUS.md`），改表头需同步改 dashboard.html 解析器。
4. 模板权威来源是 `docs/templates/`，根目录的 `CLAUDE.md`/`STATUS.md` 等是 AgentHub 自身实例（非给别人复制的模板）。
5. `scripts/check_docs.py` 与 `check_worklog.py` 硬编码了 `worklogs/` 和 `{黎,董,袁}` 成员；新增协作者需同步改脚本。
6. AR/CR/PR 红线分散在 `docs/conventions/01/02/03/99-process-rules`，新增红线必须更新对应条号且红线总表（`docs/conventions/CLAUDE-规范导航.md`）同步刷新。
7. Docker / pre-commit 路径前缀：产品代码在 `src/`，compose 在 `src/docker/`，钩子 `files:` 模式为 `^src/backend/`、`^src/frontend/`。

---

## 三、新增文件放哪？（决策树）

```
要新增一个文件，它是……
│
├─ 规范正文（某个开发维度的"应该怎么做"）？
│     → docs/conventions/NN-<name>_<中文名>.md（单文件 > 300 行则拆为目录）
│       如属 AgentHub 特有维度（边界矩阵、流程红线全集），放 99-<name> 附录
│
├─ 某规范/功能点的规格（接口/数据/行为约定）？
│     → docs/specs/NN-<name>_<中文名>.md（编号与功能点对齐）
│       业务域内部细节 → docs/specs/domains/domainN-<name>_<中文名>.md
│
├─ 架构/技术选型决策（为什么选 A 不选 B）？
│     → worklogs/decisions/NNNN-<slug>.md（ADR，收束节点产出）
│
├─ 技术探索/调研笔记（个人或团队）？
│     → 个人探索：docs/explore/{黎,董,袁}/<topic>.md
│     → 团队探索：docs/explore/EXP-NN_<topic>.md（编号制）
│     → 大型调研：docs/research/<主题>_<中文>.md
│
├─ 项目计划/PRD/分工/路线图？
│     → docs/plan/{背景,开发清单,task-assignment,前端实施计划}_*.md
│
├─ 复杂功能设计文档（背景/目标/方案/影响/风险）？
│     → docs/design/<功能名>_<中文>.md
│
├─ 进度汇报（功能点完成 / 收束报告 / HTML 渲染产物）？
│     → docs/reports/<标题>_<中文>.{md,html}
│
├─ 可复用的文件模板（给新项目复制用）？
│     → docs/templates/<类型>模板.md（并登记到 docs/templates/README-模板索引.md）
│
├─ 后端产品代码（API/Service/Domain/Adapter）？
│     → src/backend/app/{api,application,domain,infrastructure}/...
│       严守 AR-01 5 层洋葱：L2 不 import L1/L3/L4；L1 实现 L2 接口
│       新 Agent 系统：只加 src/backend/app/adapters/，禁改 domain/（AR-02）
│
├─ 数据库迁移？
│     → src/backend/alembic/versions/NNNN_<slug>.py（禁手动改表，AR-03）
│
├─ 前端产品代码？
│     → src/frontend/src/{components,hooks,stores,api,...}
│
├─ 一次功能点的开发记录（个人日志）？
│     → worklogs/{董|黎|袁}/YYYY-MM-DD_<简短描述>.md
│       Git 用户名 → 人名 映射见 STATUS.md「Git ↔ 目录映射」表
│
├─ Claude Code Skill（通用 AI 工作流）？
│     → skills/<skill-name>/SKILL.md
│
├─ AgentHub 项目专有 Skill（如小红书相关）？
│     → .agenthub/skills/<skill-name>/...
│
├─ 工具/辅助脚本（构建、启动、校验、部署）？
│     → scripts/<name>.{py,bat,sh}
│       新增 pre-push 校验脚本 → 加到 .pre-commit-config.yaml
│
├─ 历史归档/弃用文档？
│     → docs/archive/DEPRECATED_<原名>.md（DEPRECATED_ 前缀必带）
│
├─ 描述仓库自身的元信息（图谱、约定）？
│     → meta/<name>.md
│
└─ 项目级入口（每个项目仅一份）？
      → 根目录：CLAUDE.md / README.md / STATUS.md / dashboard.html /
                .gitignore / .env.example / .pre-commit-config.yaml
      ⚠️ 除这些既定入口外，根目录不接受新散文件。
```

---

## 四、AgentHub 特有：可复用 Skills 速查

| 何时用 | Skill |
|---|---|
| 开始新功能 | `skills/feat-start/` |
| 完成功能 | `skills/feat-complete/` |
| Git 分支管理 | `skills/git-workflow/` |
| CR 自查/互查 | `skills/code-review/` |
| 文档同步 | `skills/doc-sync/` |
| 部署 | `skills/deploy/` |
| 无 spec 时先写规格 | `skills/spec-driven-development/` |
| ClaudeAdapter 联调 | `skills/test-claude-adapter/` |
| 前端规约 | `skills/前端统一规范/` |
