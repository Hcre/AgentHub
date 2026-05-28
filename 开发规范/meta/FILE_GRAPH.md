# 文件架构图谱 (FILE_GRAPH)

> 本文件是仓库的**文件归类权威**。新增文件前先在此找到对应节点，按节点放置——禁止在仓库根目录随意堆放散文件。
>
> 更新: 2026-05-27 | 维护规则：新增/移动文件或目录时同步更新本图谱。
> 注：规范正文 v2.0 重构（功能点 #34）仅改内容、未增删/移动文件，故本图谱结构不变；conventions/ 各篇现为 ai-workflow 对应步骤的细化，调用图主题统一收拢于 08。

---

## 一、目录树（带职责标注）

```
开发规范/                              # 仓库根：仅放顶层入口文件，不堆散文件
│
├── conventions/                      # 【规范正文】模板核心，开发者日常查阅
│   ├── README-规范导航.md            #   快速索引 + 红线速查（人类入口）
│   ├── CLAUDE-规范导航.md            #   AI 入口：任务→规范定位 + 红线总表 + 去重映射
│   ├── 01-architecture_架构设计规范.md #   分层、依赖、模块边界
│   ├── 02-coding_代码编写规范.md       #   命名、注释、错误处理、安全
│   ├── 03-git_Git协作规范.md          #   分支、提交、PR、合并
│   ├── 04-api_API设计规范.md          #   REST、错误码、版本、安全
│   ├── 05-testing_测试规范.md         #   金字塔、AAA、Mock、覆盖率
│   ├── 06-documentation_文档规范.md   #   README、CHANGELOG、注释
│   └── ai-workflow_AI协作开发流程/  #   方法论（长文拆目录，见 ADR 0005）
│       ├── 01-角色分工与文件体系.md
│       ├── 02-第零步_调研.md
│       ├── 03-第一步_编写计划.md
│       ├── 04-第二步_迭代开发.md
│       ├── 05-完整流程与核心原则.md
│       ├── 06-第三步_收束节点.md       #   功能批次闸门：整理/测试/审计/验证
│       └── 07-汇报.md               #   四档汇报体系（嵌入各流程节点）
│   └── 08-code-understanding_代码理解与图谱规范.md  #   代码知识图谱构建/查询/存储/应用
│
├── docs/                             # 【文档资产】非规范正文的所有文档
│   ├── plan/                         #   【计划+设计】项目计划与功能设计
│   │   ├── 背景.md                   #     为什么做、设计决策
│   │   ├── 开发清单.md                #     功能点列表 + BDD 引用 + 依赖
│   │   └── design/                   #     复杂功能设计文档（五段式）
│   │       ├── README-设计文档说明.md #       设计文档索引与模板
│   │       └── 设计提案-图谱与代码理解规范-v2.md
│   ├── reports/                      #   进度汇报（功能点/周期/阶段，从模板生成）
│   ├── research/                     #   调研文档
│   ├── specs/                        #   BDD 功能规格（00-10，逐个对应规范/功能点）
│   └── templates/                    #   ★模板权威来源（新项目从此复制）
│       ├── README-模板索引.md         #     ★模板索引 + 编写规约
│       ├── BDD规格模板.md
│       ├── CLAUDE模板.md
│       ├── README模板.md
│       ├── STATUS模板.md
│       ├── plan背景模板.md
│       ├── plan开发清单模板.md
│       ├── worklog模板.md
│       ├── 汇报模板.md
│       ├── AI审计报告模板.md
│       ├── 人审计签核模板.md
│       ├── 收束报告模板.md
│       ├── AI协作提示词模板.md
│       ├── AI会话启动模板.md
│       └── 规范文档模板.md
│
├── src/                              # 【示例代码】按规范维度分目录（非产品结构）
│   ├── README-示例代码总览.md        #   组织方式说明（重要：见此文件）
│   ├── architecture/                 #   ← 01 规范：四层架构 + DI
│   ├── coding/                       #   ← 02 规范：命名/错误/安全
│   ├── git/                          #   ← 03 规范：gitignore/hooks 配置
│   ├── api/                          #   ← 04 规范：FastAPI 微服务
│   ├── testing/                      #   ← 05 规范：pytest 单测
│   └── documentation/                #   ← 06 规范：CHANGELOG/docstring
│   └── code-understanding/           #   ← 08 规范：调用图构建/图schema/Cypher查询/CI集成
│
├── worklogs/                         # 【工作日志】每个功能点一份 YYYY-MM-DD_描述.md
│   └── decisions/                    #   ADR 架构决策记录（收束节点产出，见 ADR 0006）
│
├── scripts/                          # 【工具脚本】仪表盘启动等辅助脚本
│   ├── start_server.py               #   本地预览服务器（dashboard 入口）
│   └── 打开仪表盘.bat                 #   双击启动 dashboard
│
├── meta/                             # 【元信息】描述仓库自身的文件
│   └── FILE_GRAPH.md                 #   本文件：文件归类权威
│
├── CLAUDE.md                         # 顶层：AI 项目上下文（仅供 AI 读取，新会话自动加载）
├── README.md                         # 顶层：人类使用指南（仅供人类阅读）
├── STATUS.md                         # 顶层：进度仪表盘数据源（dashboard 解析它）
├── dashboard.html                    # 顶层：可视化进度面板
└── .gitignore                        # 顶层：忽略规则
```

---

## 二、引用关系图谱（谁依赖谁）

```
conventions/规范文档 (01-08)  ←──互检──→  docs/specs/BDD规格 (01-08)
        │                                        │
        │ ai-workflow/06-第三步_收束节点          │ 验收标准
        │ （每 N 个功能点触发闸门）                  │
        │ 落地为示例                              │
        ↓                                        ↓
   src/<维度>/  ──对应──→  docs/specs/08-examples.md
                                                 │
docs/templates/ ──复制为──→ 新项目的 CLAUDE/STATUS/README/plan/worklog
        │
        ↓ 实例化
   docs/plan/开发清单.md ──引用──→ docs/specs/*    （功能点 ↔ BDD）
        ↓ 驱动
   STATUS.md ──被解析──→ dashboard.html ──由──→ start_server.py / 打开仪表盘.bat 启动
        ↓ 每个功能点产出
   worklogs/YYYY-MM-DD_*.md
        ↓ 全局总览
   CLAUDE.md（AI 上下文：目录 + 图谱 + 规则 + 任务指南）  ←── 与本 FILE_GRAPH.md 互为索引
```

**关键约束**（修改时必须同步）：
1. 改 `conventions/` 规范 → 同步对应 `docs/specs/` BDD。
2. 新增功能点 → 同时写入 `docs/plan/开发清单.md` 和 `STATUS.md`。
3. `dashboard.html` 只解析 `STATUS.md` 表格，改表头需同步改解析器。
4. 模板的权威来源是 `docs/templates/`，根目录的 `CLAUDE.md`/`STATUS.md` 等是本仓库的实例。

---

## 三、新增文件放哪？（决策树）

```
要新增一个文件，它是……
│
├─ 规范正文（某个开发维度的"应该怎么做"）？
│     → conventions/NN-<name>_<中文名>.md（单文件 > 300 行则拆为目录，见 ADR 0005）
│
├─ 某规范/功能点的验收标准（BDD）？
│     → docs/specs/NN-<name>.md（编号与功能点对齐）
│
├─ 架构/技术选型决策（为什么选 A 不选 B）？
│     → worklogs/decisions/NNNN-<标题>.md（ADR，仅收束节点产出，见 ADR 0006）
│
├─ 项目计划与功能点清单？
│     → docs/plan/背景.md + docs/plan/开发清单.md
│
├─ 复杂功能的设计文档（背景/目标/方案/影响/风险）？
│     → docs/plan/design/设计文档-<功能名>.md
│
├─ 进度汇报（功能点完成 / 收束报告）？
│     → docs/reports/...（模板见 docs/templates/汇报模板.md）
│
├─ 调研笔记？
│     → docs/research/<主题>.md
│
├─ 可复用的文件模板？
│     → docs/templates/<类型>模板.md（并登记到 docs/templates/README-模板索引.md 索引）
│
├─ 规范的可运行示例代码？
│     → src/<对应规范维度>/...（每维度一个子目录 + README-<维度>示例.md）
│
├─ 一次功能点的开发记录？
│     → worklogs/YYYY-MM-DD_<简短描述>.md
│
├─ 工具/辅助脚本（构建、启动、部署）？
│     → scripts/<name>.py|.bat|.sh
│
├─ 描述仓库自身的元信息（图谱、约定）？
│     → meta/<name>.md
│
└─ 项目级入口（每个项目仅一份）？
      → 根目录：CLAUDE.md / README.md / STATUS.md / dashboard.html 等
      ⚠️ 除这些既定入口外，根目录不接受新散文件。
```
