---
name: doc-sync
description: 文档同步与治理 — 个人探索归档、团队决策落地、旧版本文档归档、文档索引一致性检查。任何涉及 docs/ spec/ explore/ archive/ 的变更都应触发此 skill。
---

# doc-sync: 文档同步与治理

> 确保每次技术探索和团队决策都落在正确的目录、正确的命名、正确的引用。

## 角色

你是一个**项目知识库编辑**，不是记录员。记录员只会往后追加，编辑会审查全局、合并重复、修正过期、删除废弃。你的工作是让 AgentHub 的知识体系始终保持干净、准确、对新人友好。

## 为什么重要

在 AI 协作开发中，代码可以随时重写，但**文档是跨会话、跨 Agent 的唯一桥梁**。如果 spec/ 过时，下一个 Agent 会基于错误前提做决策。如果 docs/ 混乱，人类同事和新人无法正确接入系统。

## 适用时机

- 完成一段技术探索，结论需要归档
- 团队达成设计决策，需要更新 PRD/架构/ADR
- 新增/删除/重命名文档后
- 发现文档引用不一致或过期
- push 前文档检查不通过

## 目录职责速查

| 目录 | 职责 | 读者 | 命名规则 |
|------|------|------|----------|
| `docs/` 根 | 当前权威文档（PRD、架构、接口契约） | 人类 | `{English}_{中文}.md` |
| `docs/explore/` | 技术探索过程 + ADR + 演进日志 | 人类 | 见下文分类 |
| `docs/archive/` | 过期/被取代的版本文档 | 溯源 | `DEPRECATED_{原名}.md` |
| `spec/` | 结构化规格（数据模型、API、红线） | Agent | `{english}_{中文}.md` |
| `.agenthub/worklogs/` | 个人每日工作日志 | 队友 | `YYYY-MM-DD_{描述}.md` |

## 执行流程

### 第一步：识别场景

问自己（或问用户）：这次变更属于哪种？

| 场景 | 触发条件 | 去哪个流程 |
|------|----------|------------|
| **A. 个人探索归档** | 刚完成技术调研/踩坑/分析，结论需要留存 | → 流程 A |
| **B. 团队决策落地** | 团队达成共识，需要更新 PRD/架构/ADR | → 流程 B |
| **C. 例行审查** | 不确定文档有没有问题，想全量检查 | → 流程 C |

---

### 流程 A：个人探索归档

#### A1. 确定归属

```
探索结论是否影响项目文档？
├─ 否 → 只写 worklog（.agenthub/worklogs/{你}/YYYY-MM-DD_{描述}.md）
└─ 是 → 写 worklog + 归档到 docs/explore/
```

#### A2. 归档到 explore/

文件命名：`{作者}-{英文主题}.md`

```bash
# 示例
mv 踩坑记录.md docs/explore/dong-claude-code-adapter-pitfalls.md
```

#### A3. 更新 explore/README.md

在「个人探索笔记」表格追加一行：

```markdown
| [文件名](文件名) | 作者 | 主题一句话 |
```

#### A4. 判断是否需要升级

探索结论具备以下条件之一，走流程 B 升级为 EXP 或 ADR：
- 影响了架构方向
- 被团队采纳为设计依据
- 后续工作会反复引用

---

### 流程 B：团队决策落地

#### B1. 识别影响范围

```
这个决策影响了什么？
├─ 架构方向 → 写/更新 ADR → 追加 EVOLUTION.md
├─ 产品需求 → 更新 docs/PRD_AgentHub_统一方案.md
├─ 架构设计 → 更新 docs/architecture-design_*.md
├─ 接口契约 → 更新 docs/adapter-interface_*.md 或 spec/commands_*.md
├─ 数据模型 → 更新 spec/data-model_数据模型.md
├─ 开发计划 → 更新 spec/roadmap_开发路线图.md
└─ 探索结论被正式采纳 → 个人笔记升级为 EXP-NN
```

#### B2. 升级个人探索 → EXP 报告

```
命名: EXP-{下一编号}_{中文描述}.md
更新: docs/explore/README.md 的「团队探索报告」表
```

#### B3. 写 ADR（如果是架构决策）

```markdown
# ADR-{NN}: {标题}

- **日期**: YYYY-MM-DD
- **状态**: 采纳 / 提议 / 已废弃
- **上下文**: 为什么需要做这个决定
- **决策**: 我们选择了什么
- **后果**: 带来的影响（正面和负面）
- **备选方案**: 考虑过但没选的方案及原因
```

命名：`ADR-{NN}-{英文简述}.md`，放入 `docs/explore/`

#### B4. 归档旧版本

如果本次更新取代了现有文档：
- 旧文件移到 `docs/archive/`
- 加 `DEPRECATED_` 前缀
- 如果用新版本完全替代旧版本，旧版可以删除（git 历史保留）

#### B5. 追加 EVOLUTION.md

在 `docs/explore/EVOLUTION.md` 顶部追加：

```markdown
## YYYY-MM-DD — {决策一句话摘要}
- **决策**: {具体决定}
- **原因**: {为什么}
- **影响文件**: {文件路径列表}
```

#### B6. 更新 CLAUDE.md 索引

检查 `CLAUDE.md` 文档索引表：
- 新增的文档是否已列入
- 已删除/归档的文档是否已移除
- 每个路径是否指向存在的文件

---

### 流程 C：例行审查

#### C1. 枚举文件（强制机械式，不能跳过）

**先 ls，再做判断。** 对每个文件标注状态：

```bash
# 枚举所有文档目录
ls docs/ && ls docs/explore/ && ls docs/archive/
ls spec/ && ls spec/domains/ && ls spec/rules/
ls .agenthub/worklogs/ && for d in .agenthub/worklogs/*/; do ls "$d"; done
```

为每个文件标记状态，形成清单（内部用）：

```
文档文件清单：
docs/PRD_AgentHub_统一方案.md        → 评估过 / 不用改
docs/DEPLOYMENT-GUIDE_部署测试指南.md → 评估过 / 要改（路径过期）
spec/data-model_数据模型.md          → 评估过 / 不用改
...
```

**漏一个不行**——这是审查最容易翻车的地方。

#### C2. 逐目录检查

**docs/ 根：**

| 检查项 | 方法 |
|--------|------|
| 命名合规 | 所有 `.md` 文件名匹配 `{English}_{中文}.md` |
| 无版本号 | 文件名不含 `_v\d+`、`_final`、`_最新` |
| 无废弃文件 | 过时文档是否已移入 archive/ |
| 无 .html | 不应有 HTML 文件（markdown 为源） |

**docs/explore/：**

| 检查项 | 方法 |
|--------|------|
| 命名合规 | EXP 用 `EXP-NN_中文.md`，ADR 用 `ADR-NN-en.md`，个人用 `作者-en.md` |
| README 同步 | 每个文件是否在 README.md 索引表中 |
| EVOLUTION 时效 | 最近一次重大决策是否已记录 |

**docs/archive/：**

| 检查项 | 方法 |
|--------|------|
| DEPRECATED 前缀 | 所有文件以 `DEPRECATED_` 开头 |
| 无重复 | 同一文档不存在多份归档 |

**worklogs/：**

| 检查项 | 方法 |
|--------|------|
| 日期前缀 | 日志文件以 `YYYY-MM-DD_` 开头 |
| 无文档混入 | worklogs 下不应有 PRD/ADR/EXP 等正式文档 |
| STATUS.md | 日期为绝对日期，每人在一行 |

#### C3. 交叉引用一致性

不只检查 CLAUDE.md，**检查所有文档之间的交叉引用**：

```bash
# 1. CLAUDE.md 引用的文件是否存在
grep -oP '`[^`]+\.md`' CLAUDE.md | tr -d '`' | while read f; do
  [ -f "$f" ] || echo "MISSING: $f"
done

# 2. README.md 引用的文档路径是否存在
grep -oP 'docs/[^)\s]+\.md' README.md | while read f; do
  [ -f "$f" ] || echo "MISSING in README: $f"
done

# 3. docs/ 内所有 .md 互相引用的一致性
#    如果 A.md 提到「详见 B.md」，B.md 必须存在
grep -rnh "详见\|参考\|参见\|see\|refer" docs/ spec/ | grep -oP '(docs|spec)/[^)\s\n]+\.md' | sort -u | while read f; do
  [ -f "$f" ] || echo "BROKEN REF: $f"
done
```

#### C4. 未更新文件检查

**检查"应该被更新但没更新"的文档。** 用 git log 找出最近变更，判断波及范围：

```bash
# 最近 7 天变更过的文档
git log --oneline --since="7 days ago" --name-only -- 'docs/' 'spec/' '*.md' | grep '\.md$' | sort -u
```

对照变更影响矩阵，逐一判断：
- 改了 API 路由 → `spec/commands_命令接口.md` 更新了吗？
- 改了数据模型 → `spec/data-model_数据模型.md` 更新了吗？
- 改了架构 → `docs/architecture-design_*.md` 更新了吗？
- 改了部署流程 → `docs/DEPLOYMENT-GUIDE_*.md` 更新了吗？

#### C5. 有文件无文档检查

```bash
# 检查 backend/app/api/routers/ 下是否有新增路由未在 spec/commands 中记录
ls backend/app/api/routers/ | grep -v __pycache__ | grep -v __init__
# 手动对照 spec/commands_命令接口.md 是否覆盖了所有路由

# 检查是否有散落 .md 未录入索引
find . -maxdepth 2 -name "*.md" -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/archive/*" -not -path "*/.claude/*" | sort
```

#### C6. 输出审查报告

```
## doc-sync 审查报告

### 文件清单（逐文件标注）
- docs/xxx.md → 不用改
- docs/yyy.md → 要改（原因）
...

### 命名违规
- xxx.md — 缺少英文前缀

### 位置错误
- xxx.md — 应在 archive/ 而非 explore/

### 交叉引用断裂
- CLAUDE.md → 引用了已删除的 zzz.md
- docs/aaa.md → 引用「详见 bbb.md」但 bbb.md 不存在

### 未更新文件
- spec/commands_*.md — 新增了 proxy 路由但未记录
- docs/DEPLOYMENT-GUIDE — 启动流程已变更但未同步

### 已修复
- xxx → 重命名为 yyy
```

---

## 文件命名参考

| 所在目录 | 格式 | 正确示例 | 错误示例 |
|----------|------|----------|----------|
| `docs/` | `{English}_{中文}.md` | `PRD_AgentHub_统一方案.md` | `PRD_v4.md`、`最终版PRD.md` |
| `docs/explore/` | `EXP-{NN}_{中文}.md` | `EXP-01_架构模式对比矩阵.md` | `01_架构.md` |
| `docs/explore/` | `ADR-{NN}-{en-slug}.md` | `ADR-01-cli-first-pivot.md` | `ADR_v1.md` |
| `docs/explore/` | `{作者}-{en-topic}.md` | `dong-sendmessage-flow-analysis.md` | `cc-haha.md` |
| `docs/archive/` | `DEPRECATED_{原名}.md` | `DEPRECATED_PRD_v3.md` | `old_PRD.md` |
| `spec/` | `{english}_{中文}.md` | `data-model_数据模型.md` | `数据模型.md` |
| `worklogs/` | `YYYY-MM-DD_{描述}.md` | `2026-05-23_修复一致性.md` | `修复一致性.md` |

## 特殊情况

**worklog 与 explore 的边界模糊时**：个人踩坑/分析过程 → worklog 即可。结论被团队采纳或后续会反复引用 → 同时归档到 explore/。

**命名规则有歧义时**：优先保证与同目录现有文件风格一致，而非死守规则。

**多个文档需同步更新时**：先改优先级最高的（外部读者最先看的），再改内部索引。即使中途被打断，最关键的文档也已对齐。

**冲突无法自动判断时**：列出冲突项让用户决定。这是唯一需要用户介入的情况，其他都自己拍板。

**review 发现之前的同步漏了东西**：修掉，不要说"那不是这次的事"。

## 变更摘要

完成所有修改后，按此格式输出摘要：

```
## 文档同步完成

### 新增
- docs/explore/xxx.md — 原因

### 更新
- docs/PRD_xxx.md — 原因

### 归档
- xxx.md → docs/archive/DEPRECATED_xxx.md — 原因

### 索引更新
- CLAUDE.md — 新增 xxx 引用
- docs/explore/README.md — 追加 xxx
```

## 自检清单

完成后逐条确认：

- [ ] C1 逐文件标注完成，每个文件都有「评估过/要改/不用改」标签
- [ ] 新增文件命名符合所在目录规则
- [ ] 旧版本文件已移入 archive/ 或删除
- [ ] `docs/explore/README.md` 索引已更新
- [ ] `EVOLUTION.md` 已追加（如果是方向变更）
- [ ] `CLAUDE.md` 文档索引路径全部有效
- [ ] 交叉引用无断裂：任意文档的「详见/参考 xxx.md」目标文件存在
- [ ] 未更新文件检查：git log 最近变更波及的文档均已同步
- [ ] `grep -rn "_v\d+\|_final\|_最新" docs/ spec/` 无结果（archive/ 除外）
- [ ] `grep -rn "\.html" docs/` 无结果
- [ ] `grep -rn "今天\|昨天\|刚刚\|最近\|上次" docs/ explore/` 无相对时间残留
- [ ] worklogs/ 下无正式文档混入
- [ ] 每一步都有实际文件修改，不只是"建议"或"描述"
