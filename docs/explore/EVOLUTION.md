# AgentHub 项目演进日志

> 记录每次重大方向变更：做了什么决定、为什么、影响了哪些文件。
> 倒序排列（最新在上）。

## 2026-05-30 — 实验 6/6b/7/8 完成：CLAUDE.md 缓存行为确认 + 退路 A 验证通过

- **实验 6**: V1 长驻 spawn 时缓存 CLAUDE.md，同进程不重读。Turn 2 仍读旧版本
- **实验 6b（对照）**: 去掉 `--print`，纯 stream-json 重跑，结论一致
- **实验 7**: Agent 可按绝对路径写 memory（文件确实创建），但同 session 不可见（CLI 缓存 MEMORY.md）
- **实验 8（关键）**: kill + `--resume` 后新进程读到最新 CLAUDE.md ✅，对话历史完整恢复 ✅
- **结论**:
  - "SP 永不变 + CLAUDE.md 热更新"不成立 → 改用 SP 版本 hash 触发重 spawn
  - 退路 A 完整假设链通过：更新文件 → SP hash 变 → kill → `--resume` → 新进程读新文件 + 历史恢复
  - 重 spawn 成本 ~1-2s，仅在上下文确实变化时触发
- **设计文档修正**: `memory-system-design-v1.md` 全面移除"每轮重读""热更新通道""SP 永不变"等被证伪的假设，替换为"spawn 时读取，变更时 kill + --resume 刷新"
- **影响文件**: `cli-memory-boundary-experiments.md` 重写 §八-§十一（3 个新实验 + 9 项结论汇总）；`memory-system-design-v1.md` 待修正

## 2026-05-30 — 记忆系统本地文件方案初版设计

- **决策**: 记忆系统采用本地文件方案（对标 `.claude/` + `/root/.brain/`），明确 DB/文件/Redis 三层存储边界和群聊/CLI 记忆边界
- **原因**:
  - `/root/.brain/` 实践案例验证了文件型 Agent 记忆的可行性
  - Letta 实验证明 grep + markdown（74%）优于专用向量库（68.5%）
  - cc-haha 记忆分析 + 黎 30+ 项目调研 + 本次设计讨论三条线索收敛到同一结论
  - 不需要引入 pgvector/Neo4j/Chroma 等新基础设施
- **核心设计决策**:
  1. Agent CWD 下的 CLAUDE.md + memory/（CLI 自动注入），替代 `.brain/` 设计
  2. CLI System Prompt 三层模型：L1 `<system-reminder>` 自动注入 / L2 `--system-prompt` AgentHub 构建 / L3 Harness 动态
  3. PG 是权威源，CLAUDE.md 是 AgentHub 渲染的运行时副本，memory/ 由 CLI 自管
  4. 群聊记忆（Layer 2 SP 注入）vs CLI 记忆（Layer 1 自动注入 + memory/ 文件）泾渭分明
  5. Phase A 只需 SystemPromptBuilder + AgentFileManager，成本从"完整记忆系统"缩减为"SP 模板 + CWD 管理"
- **影响文件**:
  - `docs/explore/董/记忆/cli-memory-boundary-experiments.md` 新增：5 个实验确认 CLI 三层注入结构和记忆路径隔离
  - `docs/explore/董/记忆/memory-system-design-v1.md` 重构 v2：对齐实验结论，新增 §二 CLI 三层模型、§六 SP 构建模板、附录 B 修正清单
  - `docs/explore/董/记忆/memory-feature-evaluation.md` 更新：新增第 9 项「记忆写入指令」，钩子从 8→4 个，全部对齐实验结论
- **关联**: `ref-cc-haha-memory-arch.md`、`ref-memory-comparison.md`、`../黎/群聊记忆系统高效组织方案.md`

## 2026-05-29 — CLI-only + 长驻 stream-json 方向

- **决策**:
  1. 项目主路径正式 CLI-only，SDK（ClaudeAdapter）降级为测试/降级用，不再演进
  2. 群聊身份错乱方案分阶段：Phase 0 措辞修复 + Phase 0.5 实测验证 + Phase 1 长驻 + stream-json
  3. 记忆系统作为未来参考归档，不进当前 PRD
  4. Phase 0 量化基线通过（身份互串 0/60），Phase 1 推迟；ADR-02 写入以备后续
- **原因**:
  - 当前 ClaudeCodeRuntime「短驻 + resume」模式下，messages 时间交错与 `--resume` 重放冲突无干净解
  - cc-haha 项目验证了长驻 + stream-json 的工程范式，但身份错乱核心（注意力机制）不受进程模型影响，必须先做措辞修复
  - SDK 路径与群聊主流程价值不匹配，双轨维护成本不必要
  - Phase 0.5 V1-V5 全部验证通过，技术假设确认
- **影响文件**:
  - `docs/explore/董/group-chat-pipeline-proposal.md` v2 → v3.1
  - `docs/explore/董/cli-streamjson-feasibility-test.md` Phase 0.5 验证 + V5
  - `docs/explore/董/memory-system-future.md` cc-haha 记忆系统参考
  - `docs/explore/董/ADR-02-phase1-long-running-cli.md` Phase 1 实施 ADR
  - `scripts/feasibility/phase0_baseline.py` 量化基线脚本
  - 待办 spec 同步：`spec/architecture_架构定义.md` 双轨改 CLI 主、`CLAUDE.md` 同步、`roadmap` 新增任务
- **参考**: 与用户 黎 的 2026-05-29 设计讨论；cc-haha 上下文管理 / 记忆系统分析

## 2026-05-25 — 群组创建功能全栈落地

- **决策**: 按 `docs/design/group-creation_群组创建功能设计方案.md` 全栈实现群组 CRUD(创建+重命名+删除)
- **原因**: Phase 4 群聊基础依赖群组数据；协调者自动创建 + 成员管理为 M3 编排打底
- **影响文件**: backend/app/(infrastructure/domain/application/api 共 9 文件), frontend/src/(api/store/component 共 8 文件), migration 0003
- **类型**: feat

## 2026-05-23 — 文档治理体系建立

- **决策**: 统一文档目录结构 — docs/（人类入口）+ spec/（Agent入口），explore/ 和 archive/ 纳入 docs/ 管理
- **原因**: 技术方向变更后新旧文档混存、版本号混乱、队友个人文档和项目文档边界模糊
- **影响文件**: 决策/ → docs/explore/，删除 .html 冗余，PRD v3 → archive/，docs/ 文件统一 英文_中文 命名
- **参考**: 本次讨论中 黎 确定的结构方案

## 2026-05-23 — 架构精简：Celery 移除、12 表→6 表

- **决策**: 摘除 Celery，用 `asyncio.gather` 替代任务编排；数据库从 12 表精简为 6 表
- **原因**: MVP 阶段无需分布式任务队列，单进程异步足够；12 表过度设计，6 表覆盖核心场景
- **影响文件**: `docs/specs/01-architecture_架构定义.md`、`docs/specs/03-data-model_数据模型.md`、`docs/conventions/09-boundaries_边界矩阵.md`、`docs/plan/开发清单_roadmap.md`
- **参考**: PRD v4 统一方案

## 2026-05-23 — CLI-first 双轨架构确立

- **决策**: [ADR-01](../../worklogs/decisions/0001-cli-first-pivot.md) — Agent 接入从纯 API 模式转向 CLI 优先的双轨架构（LLMAdapter + AgentRuntime）
- **原因**: Claude Code CLI 子进程模式在工具链完整性、代码生成质量上优于纯 API；保留 SDK 路径供轻量调用
- **影响文件**: `claude_adapter.py` 重写、新增 `claude_code_runtime.py`、`domain/llm/protocol.py` 扩展

## 2026-05-22 — ClaudeAdapter 完整实现

- **决策**: ClaudeAdapter 支持 5 种 StreamEvent 解析（text/thinking/tool_call/tool_result/request_approval），注入 L1 记忆，增加指数退避重试
- **原因**: MVP 需要完整的 LLM 流式交互体验，不只是文本生成
- **影响文件**: `claude_adapter.py`、`chat_service.py`、`protocol.py`

## 2026-05-22 — M2 域1（IM 聊天）完成

- **决策**: 会话 CRUD + WebSocket 实时通信 + 流式输出 + L1 短期记忆交付
- **原因**: MVP Phase 1 的 6 个 P0 功能中完成了前 5 个
- **影响文件**: `sessions.py`、`chat.py`（WS）、`chat_service.py`、`chatStore.ts`

## 2026-05-22 — AI 协作体系初始化

- **决策**: 建立 worklog + STATUS.md + Skills + pre-commit 自动检查的协作流程
- **原因**: 多人协作需要明确的交接机制和质量门禁
- **影响文件**: `worklogs/`、`skills/`、`scripts/check_worklog.py`、`CLAUDE.md`

## 2026-05-21 — 项目脚手架初始化

- **基线**: 5 层洋葱架构（L1 Infrastructure → L5 Presentation），FastAPI + React/TypeScript + PostgreSQL + Redis + Docker Compose
- **依赖方向**: L5 → L4 → L3 → L2 ← L1（依赖倒置）
- **参考**: `architecture-design_架构设计_分层与数据流.md`
