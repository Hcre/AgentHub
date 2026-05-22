# 工作日志：Claude Adapter 完整实现

- **谁**: 黎
- **日期**: 2026-05-22
- **分支**: main（直接提交，非破坏性重构）
- **关联 Spec**: `docs/adapter_interface_spec.md` v0.2, `docs/DOC-15-claude-adapter-design.md` v1.1

## 目标

审查 DOC-15 设计方案后，根据裁决结果：反向更新 spec、实现 ClaudeAdapter 完整功能、补充测试。

## 产出

- [x] `backend/app/infrastructure/llm/claude_adapter.py` — 重写，支持 5 种事件（TEXT/THINKING/TOOL_CALL/ERROR/DONE）、memory 注入 system_prompt、指数退避重试（3 次）、完整 token_usage
- [x] `backend/app/core/config.py` — 新增 `max_tokens`/`max_tool_turns`/`claude_cli_timeout`
- [x] `backend/app/application/services/chat_service.py` — 使用 `settings.max_tokens` 替代 `getattr` hack
- [x] `docs/adapter_interface_spec.md` — v0.2：接口从 `send_message()` 精简为 `stream()` + `chat_structured()`
- [x] `docs/DOC-15-claude-adapter-design.md` — v1.1：加差异说明 + 所有未实现章节标 [Mx 待实现]
- [x] `backend/tests/test_claude_adapter.py` — 10 个测试全通过，adapter 覆盖率 84%

## 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| `stream()` 胜出，废弃 spec v0.1 的 `send_message()` | 代码已冻结并全链路联通，改名无收益且有风险 | spec 反向更新 |
| `_prompt_builder.py` 内联为模块函数 | 逻辑简单（<30 行），独立文件过度设计 | 减少文件数 |
| `_build_tool_definitions()` 暂返回空 | ToolRegistry（M3）未实现，传无效 tools 会 API 报错 | M3 时对接 |
| THINKING 解析已实现但触发未接入 | Agent 实体缺 `thinking_enabled` 字段 | M2 Agent settings 扩展时接入 |

## 未完成 / 阻塞

- [ ] `claude_cli_adapter.py` — M2 待实现
- [ ] `_build_tool_definitions()` 需要 ToolRegistry — M3 待实现
- [ ] THINKING 触发需要 Agent settings 扩展 — M2 待实现
- [ ] Tool Loop 编排（ChatService 多轮 tool_use） — M3 待实现

## 给下一位的交接

> **下一步**：域 2 的 M2 剩余工作是 `ClaudeCliAdapter`（子进程模式）和 Agent settings 扩展（thinking_enabled）。
> 
> **注意事项**：
> 1. `claude_adapter.py` 的事件解析遍历的是 Anthropic SDK 低层事件（`async for event in stream`），不是高层 `text_stream`。如果 SDK 版本升级事件类型名可能变化。
> 2. `_build_system_prompt()` 的 memory 拼装顺序是 l3(project) → l2(summary) → l4(rag)，这是刻意的——项目上下文最稳定放最前面。
> 3. 测试用 `_mock_obj()` 工厂构造 SDK 事件，如果需要加新测试直接参考 `_make_mock_text_events()`。
