# 工作日志：Claude Adapter 设计审查与架构决策

- **谁**: 董（成员2，域2 DRI — Agent 与编排层）
- **日期**: 2026-05-22
- **分支**: feature/domain2/claude-adapter-impl
- **关联 Spec**: `docs/adapter_interface_spec.md`, `docs/DOC-15-claude-adapter-design.md` v1.2
- **分工依据**: `docs/task_assignment_v3.md` — 域2 负责 Agent CRUD/Adapter/Coordinator/TaskEngine，接受域1（黎）支援 Agent 详情页前端（2.3）和对话式创建组件（2.4）

## 目标

审查 Claude Adapter 设计方案，解决 API vs CLI 模式的关键架构问题。

## 产出

- [x] 审查 DOC-15 双轨架构设计 — 确认 LLMAdapter(API) + AgentRuntime(CLI) 分离方案
- [x] **ADR-01 架构决策** — 从 API 重心转向 CLI 优先，CLI Runtime 作为 P0 实现
- [x] 分析 cc-haha 与 AgentPipe — 确认 `--resume` 维持长对话 > 每次新建进程传全量历史
- [x] 分析 CLI 模式上下文传输问题 — 发现 memory 体系被绕过，设计增强字段方案
- [x] 分析 Session 存储 — 确认 AgentHub session_id = CLI session_id，砍掉 SessionStore 映射层
- [x] 分析 Permission 机制 — 确认 `--print` 非交互模式下的检测+重试方案

## 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| CLI 优先而非 API | 自建 Harness 需 95h+，CLI 自带完整工具生态零成本 | M2 可交付，6h 实现 |
| 双轨而非强行融合 | API(无状态 HTTP) 与 CLI(有状态进程) 本质不同 | 两个独立基类，互不拖累 |
| 砍掉 SessionStore | AgentHub session UUID 直接作为 CLI session_id | 少维护一层映射 |
| identity 走 --system-prompt，其余走 stdin | CLI 原生支持 system_prompt，身份与非身份信息分离 | 更清晰的上下文组装 |
| Permission 事后检测 | --print 模式非交互，阻断后通知用户重试 | 不依赖 stdin 交互式审批 |

## 未完成 / 阻塞

- [ ] agent_system 字段需落地到 Agent 实体 — M2 待实现
- [ ] permission_mode 字段需落地到 Agent 实体 — M2 待实现

## 给下一位的交接

> **域2 分工**（参考 `docs/task_assignment_v3.md` §四、§五）：
> - 董（本人）：Adapter 实现（2.1）+ Agent CRUD 后端（2.2）+ 后续 Coordinator/TaskEngine（2.5-2.12）
> - 黎（支援域2）：Agent 详情页前端（2.3）+ 对话式创建组件（2.4） — M2 并行，不阻塞
>
> **下一步**：adapter-cli-flow-analysis.md 已有完整 7 场景流程，黎可直接以此为依据实现 ClaudeCodeRuntime。
>
> **注意事项**：
> 1. 不要试图在 --print 模式做 stdin 交互式审批（无效）
> 2. Session 不需要额外映射层，AgentHub PG sessions 表就是唯一真相源
> 3. agent_system 字段是工厂路由关键（ANTHROPIC_API / CLAUDE_CODE），需与 Agent 实体扩展（黎负责）对齐
