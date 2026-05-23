# explore/ — 技术探索文档索引

> 这里存放「为什么选这条路」的过程记录，不是当前权威文档。
> 当前生效的规格在 `docs/` 根目录和 `spec/`。
> 项目方向变更时间线见 [EVOLUTION.md](EVOLUTION.md)。

## 分类

| 前缀 | 含义 | 示例 |
|------|------|------|
| `EXP-NN_` | 团队技术探索报告（编号） | `EXP-01_架构模式对比矩阵.md` |
| `ADR-NN-` | 架构决策记录 | `ADR-01-cli-first-pivot.md` |
| `dong-` / `黎-` | 个人探索笔记 | `dong-claude-code-haha-analysis.md` |

## 文件清单

### 架构决策记录

| 文件 | 决策摘要 |
|------|----------|
| [ADR-01-cli-first-pivot.md](ADR-01-cli-first-pivot.md) | CLI优先双轨架构：SDK/CLI 双路径，CLI 为主 |

### 团队探索报告

| 编号 | 文件 | 主题 |
|------|------|------|
| EXP-01 | [架构模式对比矩阵](EXP-01_架构模式对比矩阵.md) | Agent 架构模式横向对比 |
| EXP-02 | [编排器设计模式](EXP-02_编排器设计模式.md) | 任务编排器设计方案 |
| EXP-03 | [状态管理与故障恢复](EXP-03_状态管理与故障恢复.md) | Agent 状态机与故障恢复策略 |
| EXP-04 | [关键指标数据](EXP-04_关键指标数据.md) | 系统关键指标定义 |
| EXP-05 | [技术栈与框架](EXP-05_技术栈与框架.md) | 技术选型对比分析 |
| EXP-06 | [IM聊天式Agent交互模式](EXP-06_IM聊天式Agent交互模式.md) | 聊天式交互设计 |
| EXP-07 | [ClaudeCode vs Codex对比](EXP-07_ClaudeCode_vs_Codex对比.md) | CLI 运行时选型对比 |
| EXP-08 | [PageIndex技术影响分析](EXP-08_PageIndex技术影响分析.md) | PageIndex 技术引入影响 |
| EXP-09 | [Claude Adapter设计](EXP-09_claude-adapter-design.md) | 双轨适配器架构设计 |
| EXP-10 | [结构化上下文设计](EXP-10_structured-context-design.md) | Agent 上下文结构设计 |
| EXP-11 | [上下文注入问题](EXP-11_context-injection-problem.md) | 上下文注入方案分析 |

### 个人探索笔记

| 文件 | 作者 | 主题 |
|------|------|------|
| [dong-claude-code-haha-analysis](dong-claude-code-haha-analysis.md) | 董 | Claude Code 行为分析 |
| [dong-sendmessage-flow-analysis](dong-sendmessage-flow-analysis.md) | 董 | SendMessage 流程分析 |
| [dong-claude-code-adapter-pitfalls](dong-claude-code-adapter-pitfalls.md) | 董 | Claude Code 适配器踩坑记录 |

## 文档生命周期

```
个人探索笔记                 团队评审通过              EXP 编号报告
(dong-xxx.md)  ────────→  影响架构/PRD   ────────→  (EXP-NN_xxx.md)
                              │
                              ├── 落地为正式决策 → ADR-NN-xxx.md
                              ├── 更新 docs/ 根文件 → docs/xxx.md
                              └── 旧版 → docs/archive/
```

## 规则

1. **新探索报告**：用 `EXP-{下一编号}_{中文描述}.md`，更新本 README
2. **新 ADR**：用 `ADR-{下一编号}-{英文简述}.md`，更新本 README + EVOLUTION.md
3. **个人探索**：用 `{作者}-{英文主题}.md`，有结论后评审是否升级为 EXP
4. **过时 PRD/规格不进 explore**：直接进 `docs/archive/`
5. **接口契约/当前规格不进 explore**：放 `docs/` 根或 `spec/`
