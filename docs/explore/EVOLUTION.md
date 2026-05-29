# AgentHub 项目演进日志

> 记录每次重大方向变更：做了什么决定、为什么、影响了哪些文件。
> 倒序排列（最新在上）。

## 2026-05-23 — 文档治理体系建立

- **决策**: 统一文档目录结构 — docs/（人类入口）+ spec/（Agent入口），explore/ 和 archive/ 纳入 docs/ 管理
- **原因**: 技术方向变更后新旧文档混存、版本号混乱、队友个人文档和项目文档边界模糊
- **影响文件**: 决策/ → docs/explore/，删除 .html 冗余，PRD v3 → archive/，docs/ 文件统一 英文_中文 命名
- **参考**: 本次讨论中 黎 确定的结构方案

## 2026-05-23 — 架构精简：Celery 移除、12 表→6 表

- **决策**: 摘除 Celery，用 `asyncio.gather` 替代任务编排；数据库从 12 表精简为 6 表
- **原因**: MVP 阶段无需分布式任务队列，单进程异步足够；12 表过度设计，6 表覆盖核心场景
- **影响文件**: `docs/specs/01-architecture_架构定义.md`、`docs/specs/03-data-model_数据模型.md`、`docs/conventions/99-boundaries_边界矩阵.md`、`docs/plan/开发清单_roadmap.md`
- **参考**: PRD v4 统一方案

## 2026-05-23 — CLI-first 双轨架构确立

- **决策**: [ADR-01](ADR-01-cli-first-pivot.md) — Agent 接入从纯 API 模式转向 CLI 优先的双轨架构（LLMAdapter + AgentRuntime）
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
