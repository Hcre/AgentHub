---
name: simplify-step-tools
description: 删除 ask tool + PAUSED 态 + resume 机制 — worker 提问走正常文本流，任务状态收敛为 DONE/NOT DONE
metadata:
  type: project
  tags: [coordinator, v3, simplification]
---

# 简化：删除 ask tool + PAUSED 态 + resume 机制

**日期**：2026-06-08 | **状态**：已决策，未实现（列为步 2.5）

## 背景

步 3 实现了完整的 ask/waiting/feed/resume 链路：

- `ask` MCP tool → worker 调用后触发 RUNNING → PAUSED
- `_feed_event` + `_waiting_node_key` → Orchestrator 挂起等外部信号
- 显式 resume → `_transition(PAUSED → RUNNING)` → 重新 dispatch

## 问题

1. **PAUSED 是过度设计**。Worker 问问题、等答案、跟人讨论——全是「还没做完」的自然组成部分。不需要 Harness 层面多一个状态
2. **`ask` tool 是多余的**。Worker 完全能正常说话——对话路径的 `_stream_one_agent` 输出直接推 WebSocket 进群聊。是执行路径的 `executor._consume` 把文本吞了，然后开了个 `ask` tool 作为结构化逃生口
3. **显式 resume 是把 worker 内部的正常状态升格成了 Harness 的状态变更**。跟人的工作方式相反——你问我问题，我不需要把你标记为「暂停」，等你回答后再标记为「运行」

## 决定

| 删除 | 替代 |
|------|------|
| `ask` MCP tool | Worker 正常说话。文本推群聊，跟 respond 路径一样 |
| PAUSED 态 | 任务状态只有两种：DONE（COMPLETED）和 NOT DONE（其他所有） |
| `_feed_event` / `_waiting_node_key` | Planner 从 transcript 自然看到 worker 在等回复 |
| 显式 resume（PAUSED → RUNNING 转移） | `feed(step)` → 重新 executor.run(node)（`--resume` 恢复上下文） |
| `task_complete` 的完成闸门 | 保留。唯一的结构化信号 |

Worker 流结束但没调 `task_complete` → `WorkerOutcome(status="not_done")`。不是失败，就是没做完。Harness 不做任何假设。

## 影响范围

- `executor.py`：删 `_ASK_TOOL` 检测；worker TEXT 事件推 ws_manager.broadcast 到群聊
- `orchestrator.py`：删 PAUSED 处理、`_feed_event`、`_await_feed_and_resume`；`_settle` 中 waiting 分支删除
- `mcp_step_tools.py`：删 `ask` tool 定义
- `dag.py` / `fsm.py`：删 PAUSED 状态枚举
- 步 2 spec：`feed` 语义从「唤醒 PAUSED step」改为「重新派发该 step 的 worker」

## 不在此范围

- `task_complete` tool 保留不动
- 完成闸门（没调 task_complete → needs_reprompt）保留不动
- 验收反向网保留不动
- 步 2 的多轮讨论 / SessionState 升级 / 执行态路由收口不受影响——步 2 的 `feed` 语义已经按新定义（重新派发 worker）
