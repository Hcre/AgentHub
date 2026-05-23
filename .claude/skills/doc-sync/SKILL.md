---
name: doc-sync
description: Synchronize project documentation — review docs/, spec/, worklogs/, 决策/ for consistency, outdated references, and conflicts. Update CLAUDE.md doc index. Use after any design decision, architecture change, or feature milestone.
---

# doc-sync: 文档同步审查

> 本 skill 是 neat-freak 的项目级定制版，聚焦 AgentHub 特定的文档结构。

## 适用时机

- 完成设计决策后（新增/修改 ADR、PRD 版本迭代）
- 完成里程碑后（M2→M3 等）
- 新增/删除/重命名文档后
- 发现文档间引用不一致时
- `STATUS.md` 或 `CLAUDE.md` 过期时

## 执行流程

### 第一步：盘查文件清单

强制机械枚举，不凭记忆：

```bash
# 逐一列出四个目录
ls docs/
ls spec/ && ls spec/domains/ && ls spec/rules/
ls 决策/
ls .agenthub/worklogs/ && ls .agenthub/worklogs/黎/
```

确认 `CLAUDE.md`、`README.md`、`.agenthub/worklogs/STATUS.md` 存在。

### 第二步：docs/ 审查

对 `docs/` 下每个文件逐条检查：

| 检查项 | 方法 |
|--------|------|
| PRD 版本 | 当前权威 PRD 是否为 v4？旧版本是否标记废弃？ |
| 架构文档 | 是否引用了 Celery/LiteLLM/12 表？→ 需更新 |
| ADR 文件 | 是否在 `docs/`？（应在 `决策/`） |
| 废弃文档 | 是否仍在 `docs/` 而非 `决策/`？ |
| 交叉引用 | 文档内链接是否指向存在的文件？ |
| 版本头 | 每个设计文档是否有版本号+日期？ |
| 过时引用 | `grep -n "Celery\|LiteLLM\|task_events\|task_artifacts\|PRD v1\|PRD v2" docs/*.md` → 有则修复 |

**权威文档清单（这些必须在 docs/，其余移入 决策/）**：
- `PRD_AgentHub_v4_统一方案.md`
- `adapter-cli-flow-analysis.md`
- `DOC-15-claude-adapter-design.md`
- `adapter_interface_spec.md`
- `架构设计_分层与数据流.md`
- `task_assignment_v3.md`

### 第三步：spec/ 审查

对 `spec/` 下每个文件：

| 检查项 | 方法 |
|--------|------|
| architecture | 技术栈是否含 Celery/LiteLLM？→ 改为 Redis + 双轨 SDK/CLI |
| architecture | AgentRuntime 接口是否 `stream() + kill() + send_decision()`？ |
| architecture | 审批模式是否描述了 `permission_denials` 检测 + `bypassPermissions` 重试？ |
| data-model | 是否有「12 表→6 表」警告头？ |
| commands | 环境变量是否包含 `CLAUDE_CLI_TIMEOUT`、`AGENT_WORKSPACE_DIR`？ |
| commands | 是否有 `GET /api/sessions/{id}/history` 端点？ |
| roadmap | 里程碑日期是否匹配 v4（M2: 5/23-27, M3: 5/28-6/1...）？ |
| boundaries | 权限边界是否包含了 CLI 代理模式的说明？ |
| testing | 是否包含 `ClaudeCodeRuntime` 的测试策略？ |

### 第四步：worklogs/ 审查

| 检查项 | 方法 |
|--------|------|
| STATUS.md | 日期是否为绝对日期（不写「今天」）？ |
| STATUS.md | 每人的「正在做」「阻塞」「完成了」是否更新？ |
| 个人 worklog | `ls .agenthub/worklogs/黎/` 最新日志日期是否在 3 天内？ |
| template.md | 是否存在？ |

### 第五步：决策/ 审查

| 检查项 | 方法 |
|--------|------|
| 文件数 | 是否与 CLAUDE.md 的统计一致？ |
| 命名 | ADR 文件是否以 `ADR-` 前缀命名？其余是否保持原名？ |

### 第六步：CLAUDE.md 更新

检查 CLAUDE.md 文档索引表：

- 每行路径指向的文件是否真实存在
- 是否有新增文档未列入索引
- 是否有已废弃/移走的文档仍在索引中
- 技术栈描述是否与当前一致（Celery 已摘除、双轨架构已体现）

### 第七步：自检清单

- [ ] `grep -rn "Celery" docs/ spec/` 只出现在历史/废弃文档或明确标注「已移除」的上下文
- [ ] `grep -rn "LiteLLM" docs/ spec/` 同上
- [ ] `grep -rn "PRD v1\|PRD v2" docs/` 不出现在当前权威文档中
- [ ] `grep -rn "今天\|昨天\|最近\|上周" docs/ spec/ .agenthub/worklogs/` 清零
- [ ] `grep -rn "task_events\|task_artifacts" docs/` 不出现在当前权威文档中
- [ ] `CLAUDE.md` 的文档索引每行都指向存在的文件
- [ ] `STATUS.md` 的日期为 `2026-05-XX` 格式
- [ ] docs/ 只有最终设计文档，决策过程文档在 决策/

### 第八步：输出变更摘要

```
## doc-sync 完成

### docs/ 变更
- xxx — 更新xxx引用

### spec/ 变更
- xxx — 摘除Celery

### worklogs/ 变更
- 更新 STATUS.md 日期

### 决策/ 变更
- 移入 xxx（废弃文档）

### CLAUDE.md
- 更新文档索引
```

## 参考

本 skill 基于 neat-freak 的精简版，移除了 Agent 记忆系统操作（AgentHub 不使用 memory 文件）。如果想做全局级的目录结构整理，使用全局 neat-freak。
