---
name: doc-sync
description: 文档同步与治理 — 个人探索归档、团队决策落地、旧版本文档归档、文档索引一致性检查。任何涉及 docs/ explore/ archive/ worklogs/decisions/ 的变更都应触发此 skill。
---

# doc-sync: 文档同步与治理

> 确保每次技术探索和团队决策都落在正确的目录、正确的命名、正确的引用。

## 适用时机

- 完成一段技术探索，结论需要归档
- 团队达成设计决策，需要更新 PRD/架构/ADR
- 新增/删除/重命名文档后
- 发现文档引用不一致或过期
- push 前文档检查不通过（待实现 `check_docs.py`）

## 目录职责速查

| 目录 | 职责 | 读者 | 命名规则 |
|------|------|------|----------|
| `docs/` 根 | 当前权威 + 部署等运维文档 | 人类 | `{English}_{中文}.md` |
| `docs/plan/` | PRD / 路线图 / 任务分配 / 设计 | 人类 + Agent | `{name}_{中文}.md` |
| `docs/specs/` | 结构化规格（架构 / 数据 / API / 测试 / 域） | Agent | `NN-{name}_{中文}.md` |
| `docs/explore/` | 技术探索过程 + EVOLUTION 演进日志（ADR 已搬走） | 人类 | 见下文分类 |
| `docs/archive/` | 过期/被取代的版本文档 | 溯源 | `DEPRECATED_{原名}.md` |
| `docs/research/` | 调研笔记 | 人类 | `{name}_{中文}.md` |
| `docs/templates/` | 模板权威（给新项目复制用） | 复制起步 | `{类型}模板.md` |
| `worklogs/{董,黎,袁}/` | 个人每日工作日志 | 队友 | `YYYY-MM-DD_{描述}.md` |
| `worklogs/decisions/` | ADR（架构决策记录）| Agent | `NNNN-{slug}.md` |
| `docs/conventions/` | 规范正文（01-08 + ai-workflow + 99-* 附录） | 全员 | 已固定 |

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
├─ 否 → 只写 worklog（worklogs/{你}/YYYY-MM-DD_{描述}.md）
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
├─ 架构方向 → 写 ADR → worklogs/decisions/NNNN-{slug}.md → 追加 EVOLUTION.md
├─ 产品需求 → 更新 docs/plan/背景_PRD_AgentHub_统一方案.md
├─ 架构设计 → 更新 docs/specs/01-architecture_架构定义.md 或 01b-architecture-design_*.md
├─ 接口契约 → 更新 docs/specs/04c-adapter-interface_*.md 或 04-commands_*.md
├─ 数据模型 → 更新 docs/specs/03-data-model_数据模型.md（+ Alembic migration）
├─ 开发计划 → 更新 docs/plan/开发清单_roadmap.md
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

命名：`NNNN-{英文简述}.md`（4 位数字编号），放入 `worklogs/decisions/`（旧位置 `docs/explore/ADR-*` 已弃用）

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

#### C1. 枚举文件

```bash
ls docs/ && ls docs/explore/ && ls docs/archive/ && ls docs/plan/ && ls docs/specs/ && ls docs/research/ && ls docs/templates/
ls docs/specs/domains/ && ls docs/conventions/
ls worklogs/ && ls worklogs/decisions/ && for d in worklogs/{董,黎,袁}/; do ls "$d"; done
```

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

#### C3. CLAUDE.md 索引一致性

```bash
# 提取 CLAUDE.md 中所有文件路径引用，逐一检查是否存在
grep -oP '`[^`]+\.md`' CLAUDE.md | tr -d '`' | while read f; do
  [ -f "$f" ] || echo "MISSING: $f"
done
```

#### C4. 输出审查报告

```
## doc-sync 审查报告

### 命名违规
- xxx.md — 缺少英文前缀

### 位置错误
- xxx.md — 应在 archive/ 而非 explore/

### 索引缺失
- xxx.md — 未列入 explore/README.md
- CLAUDE.md — 引用了已删除的 xxx.md

### 已修复
- xxx → 重命名为 yyy
```

---

## 文件命名参考

| 所在目录 | 格式 | 正确示例 | 错误示例 |
|----------|------|----------|----------|
| `docs/` 根 | `{English}_{中文}.md` | `DEPLOYMENT-GUIDE_部署测试指南.md` | `PRD_v4.md`、`最终版PRD.md` |
| `docs/plan/` | `{name}_{中文}.md` | `开发清单_roadmap.md`、`背景_PRD_AgentHub_统一方案.md` | `计划.md` |
| `docs/specs/` | `NN-{name}_{中文}.md` | `03-data-model_数据模型.md`、`04c-adapter-interface_适配器接口规范.md` | `数据模型.md` |
| `docs/explore/` | `EXP-{NN}_{中文}.md` | `EXP-01_架构模式对比矩阵.md` | `01_架构.md` |
| `docs/explore/{黎,董,袁}/` | `{en-topic}.md` | `黎/group-chat-boundary-and-dependencies.md` | `cc-haha.md` |
| `docs/archive/` | `DEPRECATED_{原名}.md` | `DEPRECATED_PRD_v3.md` | `old_PRD.md` |
| `worklogs/{你}/` | `YYYY-MM-DD_{描述}.md` | `2026-05-28_修复一致性.md` | `修复一致性.md` |
| `worklogs/decisions/` | `NNNN-{en-slug}.md`（ADR）| `0001-cli-first-pivot.md` | `ADR-01.md` |

## 自检清单

完成后逐条确认：

- [ ] 新增文件命名符合所在目录规则
- [ ] 旧版本文件已移入 archive/ 或删除
- [ ] `docs/explore/README.md` 索引已更新
- [ ] `EVOLUTION.md` 已追加（如果是方向变更）
- [ ] `CLAUDE.md` 文档索引路径全部有效
- [ ] `grep -rn "_v\d\|_final\|_最新" docs/` 无结果（archive/ 除外）
- [ ] `grep -rn "\.html" docs/` 无结果（不应有 HTML 文件）
- [ ] worklogs/ 下无正式文档混入
