# 通用开发规范 — 使用指南

> **👤 本文件供人类阅读**。AI Agent 请阅读 `CLAUDE.md`。
> 约 3 分钟读完。本文件夹是一套通用开发规范的**项目模板**，可直接复制到新项目中使用。

---

## 这是什么

一套适用于各类软件项目的通用开发规范 + AI 协作开发流程。覆盖 6 个核心维度（架构/代码/Git/API/测试/文档）+ 代码理解与图谱 + AI 协作流程。复制本文件夹到你的项目根目录，即可获得：

- **开发规范**（`conventions/`）— 8 份规范文档，覆盖开发全生命周期
- **文件模板库**（`docs/templates/`）— 14 个模板（worklog/CLAUDE/STATUS/BDD/审计/收束/...），新项目开箱即用
- **项目骨架**（`docs/plan/`）— 背景文档 + 开发清单 + 设计文档模板
- **进度仪表盘**（`STATUS.md` + `dashboard.html`）— 可视化追踪项目进度
- **AI 上下文**（`CLAUDE.md`）— AI 助手自动加载的项目信息
- **可运行示例**（`src/`）— 每个规范维度都有对应的 Python 示例代码

---

## 快速开始（新项目）

### 1. 复制模板

```bash
# 方式一：复制整个文件夹
cp -r 开发规范/ my-new-project/

# 方式二：只复制核心文件
cp -r 开发规范/conventions/ my-new-project/
cp 开发规范/CLAUDE.md 开发规范/STATUS.md 开发规范/dashboard.html my-new-project/
cp -r 开发规范/docs/templates/ 开发规范/docs/plan/ my-new-project/
mkdir my-new-project/worklogs my-new-project/src
```

### 2. 初始化为你的项目

| 步骤 | 做什么 | 改哪个文件 |
|------|--------|-----------|
| 1 | 改项目名 | `CLAUDE.md` — 标题和概述 |
| 2 | 写背景 | `docs/plan/背景.md` — 为什么做、关键决策 |
| 3 | 定功能点 | `docs/plan/开发清单.md` — 你的功能点列表 |
| 4 | 初始化状态 | `STATUS.md` — 更新功能点状态 |
| 5 | 确认规范 | 读 `conventions/README-规范导航.md`，确认哪些规范适用 |

### 3. 按流程推进

阅读 `conventions/ai-workflow_AI协作开发流程/` 了解 AI 协作开发的完整流程：

```
调研 → 编写计划 → 迭代开发 → 收束节点（质量闸门）
```

---

## 如何与 AI 配合使用

本项目的核心设计理念：**人读 README，AI 读 CLAUDE.md**。

| 对象 | 读什么 | 为什么 |
|------|--------|--------|
| 👤 你（人类） | `README.md`（本文件） | 导航、理解结构、知道要改什么 |
| 🤖 AI 助手 | `CLAUDE.md` | 新会话自动加载，获得项目上下文 |
| 两者都需要时 | `STATUS.md`、`docs/plan/开发清单.md` | 共同的事实源 |

**使用建议**：
- 每次新开 AI 会话时，AI 会自动读取 `CLAUDE.md` — 你不用重复解释项目结构
- 当 AI 不知道文件放哪时，让它查 `meta/FILE_GRAPH.md`（文件归类权威）
- 需要汇报进度时，AI 会从 `STATUS.md` + `开发清单.md` + `worklogs/` 自动提取数据
- 每完成 3 个功能点，AI 会触发"收束节点"做整理/测试/审计/验证

---

## 目录结构

```
开发规范/                          # 项目根
├── conventions/                  # 📋 开发规范（你要遵守的规则）
│   ├── README.md                 #    → 从这里开始：快速索引 + 红线速查
│   ├── 01-architecture_架构设计规范.md
│   ├── 02-coding_代码编写规范.md
│   ├── 03-git_Git协作规范.md
│   ├── 04-api_API设计规范.md
│   ├── 05-testing_测试规范.md
│   ├── 06-documentation_文档规范.md
│   ├── 08-code-understanding_代码理解与图谱规范.md
│   └── ai-workflow_AI协作开发流程/
│
├── docs/
│   ├── templates/                # 📄 文件模板（新项目从此复制）
│   ├── specs/                    # ✅ BDD 验收标准
│   ├── plan/                     # 📐 项目计划 + 设计文档
│   ├── reports/                  # 📊 进度汇报
│   └── research/                 # 🔬 调研文档
│
├── src/                          # 💻 可运行示例代码（按规范维度组织）
├── worklogs/                     # 📝 工作日志（每个功能点一份）
│   └── decisions/                # 📋 架构决策记录（重大取舍的永久存档）
├── scripts/                      # 🔧 工具脚本（启动仪表盘等）
├── meta/
│   └── FILE_GRAPH.md             # 🗺️ 文件归类权威 — "新文件放哪"决策树
│
├── CLAUDE.md                     # 🤖 AI 自动加载的项目上下文
├── README.md                     # 👤 本文件 — 人类使用指南
├── STATUS.md                     # 📊 项目进度数据源
└── dashboard.html                # 📈 可视化进度面板（浏览器打开）
```

---

## 常见问题

**Q: 怎么打开仪表盘？**
A: 双击 `scripts/打开仪表盘.bat`（自动启动服务并打开浏览器），或运行 `python scripts/start_server.py`。**不能**直接用 `file://` 协议打开（dashboard 需要通过 HTTP 请求读取 `STATUS.md`）。

**Q: 规范太严格，能删减吗？**
A: 可以。`conventions/` 中的每条规则都可以调整。建议先通读 `conventions/README-规范导航.md` 的红线速查，标出不适用的规则，团队讨论后修改。

**Q: 只有我一个人开发，也需要这些吗？**
A: 需要。`CLAUDE.md` 让 AI 助手在不同会话中保持一致性。明天的你不会记得今天为什么做某个决策——`worklogs/` 和 `STATUS.md` 帮你记住。

**Q: 怎么更新规范？**
A: 直接修改 `conventions/` 下的对应文件，提交 commit。如果是重大变更，在收束节点时写一份 ADR 到 `worklogs/decisions/`。

**Q: 想新增一种文件模板，放哪？**
A: 放到 `docs/templates/`，然后在 `docs/templates/README-模板索引.md` 的索引表中登记。其他文件的放置规则见 `meta/FILE_GRAPH.md` 的决策树。

**Q: AI 读了这个文件夹，为什么还是不知道怎么做？**
A: 确保 `CLAUDE.md` 存在且内容准确。AI 最需要的信息：目录结构、模块依赖、关键决策、当前状态。检查这几项是否都有。
