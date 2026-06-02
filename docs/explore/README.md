# explore/ — 技术探索文档索引

> 这里存放「为什么选这条路」的过程记录，不是当前权威文档。
> 当前生效的规格在 `docs/specs/`，规范在 `docs/conventions/`，计划在 `docs/plan/`。
> 项目方向变更时间线见 [EVOLUTION.md](EVOLUTION.md)。

## 目录结构

```
docs/explore/
├── README.md              ← 你在读的文件
├── EVOLUTION.md           ← 项目决策演进日志
├── ADR-NN-*.md            ← 架构决策记录（团队级）
├── EXP-NN_*.md            ← 技术探索报告（团队级）
└── 董/                    ← 董的个人探索
    ├── claude-code-haha-analysis.md
    ├── sendmessage-flow-analysis.md
    ├── claude-code-adapter-pitfalls.md
    ├── cc-haha-multi-model-analysis.md
    ├── 01-Agent-CRUD-补全设计.md
    └── CLI多模型代理方案.md
```

## 分类

| 层级 | 位置 | 命名 | 含义 |
|------|------|------|------|
| 团队 | explore/ 根 | `EXP-NN_{中文}.md` | 团队技术探索报告，经评审后编号 |
| 团队 | explore/ 根 | `ADR-NN-{en-slug}.md` | 架构决策记录，影响项目方向 |
| 个人 | `explore/{你}/` | 自由命名 `.md` | 个人技术探索笔记，放入自己的子目录 |

## 团队探索报告

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

## 进行中的探索

| 文件 | 主题 | 状态 |
|------|------|------|
| [group-chat-boundary-and-dependencies](黎/EXP-12_group-chat-boundary-and-dependencies.md) | 群聊模块边界、依赖分析与接口契约 | 讨论中 |

## 架构决策记录

| 文件 | 决策摘要 |
|------|----------|
| [ADR-01-cli-first-pivot.md](../../worklogs/decisions/0001-cli-first-pivot.md) | CLI优先双轨架构：SDK/CLI 双路径，CLI 为主 |

## 个人探索

### 董/
| 文件 | 主题 |
|------|------|
| [claude-code-haha-analysis](董/claude-code-haha-analysis.md) | Claude Code 行为分析 |
| [sendmessage-flow-analysis](董/sendmessage-flow-analysis.md) | SendMessage 流程分析 |
| [claude-code-adapter-pitfalls](董/claude-code-adapter-pitfalls.md) | Claude Code 适配器踩坑记录 |
| [cc-haha-multi-model-analysis](董/cc-haha-multi-model-analysis.md) | 多模型代理方案分析 |
| [01-Agent-CRUD-补全设计](董/01-Agent-CRUD-补全设计.md) | Agent CRUD 补全设计 |
| [CLI多模型代理方案](董/CLI多模型代理方案.md) | CLI 多模型代理方案 |

## 文档生命周期

```
个人探索笔记                    团队评审通过              EXP 编号报告
(黎/xxx.md 或 董/xxx.md) ──→ 影响架构/PRD ────────→ (EXP-NN_xxx.md)
                                │
                                ├── 落地为正式决策 → worklogs/decisions/NNNN-xxx.md (ADR)
                                ├── 更新规格/规范 → docs/specs/ 或 docs/conventions/
                                └── 旧版 → docs/archive/
```

## 规则

1. **个人探索**：在自己的子目录（`黎/` `董/` `袁/`）下自由创建 `.md` 文件
2. **升级为团队报告**：经评审后，用 `EXP-{下一编号}_{中文描述}.md` 放到 explore/ 根，更新本 README
3. **新 ADR**：用 `worklogs/decisions/{NNNN}-{英文简述}.md`，更新 EVOLUTION.md（旧 `ADR-NN-` 已迁出 explore）
4. **过时 PRD/规格不进 explore**：直接进 `docs/archive/`（DEPRECATED_ 前缀）
5. **接口契约/当前规格不进 explore**：放 `docs/specs/`；规范放 `docs/conventions/`
