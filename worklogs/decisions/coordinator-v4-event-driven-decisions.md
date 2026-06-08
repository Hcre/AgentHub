---
name: coordinator-v4-event-driven
description: v4 协调者调度从轮询改为事件驱动 — 删 PAUSED/ask tool/dispatch budget，保留 resume，replan 破坏性才确认
metadata:
  type: project
  tags: [coordinator, v4, event-driven, scheduling]
---

# v4 协调者：事件驱动调度 + 状态收敛

**日期**：2026-06-08 | **状态**：已决策，未实现 | **关联**：[[coordinator-design-v4]]、[[simplify-step-tools-no-ask-paused]]

经过多轮推敲，敲定 7 项决策。核心是把调度器从「轮询循环」改为「事件驱动」，由此拔掉 v3 复杂度的根。本文逐条记录结论 **+ 为什么**，推理链是这几项决策的真正价值，不记下来就丢了。

---

## 决策 1：调度器从「轮询循环」改为「事件驱动」（核心）

**结论**：orchestrator 不再 `for _ in range(max_steps)` 每圈重扫「谁该派」，改为只在三个事件响应：①任务启动 → 派根节点；②某节点完成 → 派依赖已满足的下游；③用户回话（feed）→ 把回答喂给对应 worker 续干。

**为什么**：

轮询循环有个致命的具体毛病。设 DAG 是 `B(前端) → C(测试)`：

- 第 1 圈：扫描 → B 没干完且无依赖 → 派 B → B 问「用 Markdown 还是 CMS？」→ 进程结束，B 仍「没干完」。
- 第 2 圈：再扫描 → B **还是**「没干完 + 无依赖」→ **又被判定该派** → 又派一个新 B → 又问同样的问题。
- 第 3、4 圈…… 同一个问题问到天荒地老。

轮询循环分不清两种「没干完」：「还没人开始」（该派）和「问了问题正等回答」（别再派）。v3 为了拦住重复派发，被迫引入 PAUSED 当「别重复派」的拦路标记。

**更深的根因**：v3 复杂、实现起来乱的真正原因是「状态 × 模式 × 轮询循环」三者交织的**组合爆炸**。每加一个状态（PAUSED / WAITING / AWAITING_APPROVAL），就要在轮询循环的每一圈、每个模式分支里都问一遍「它现在算不算该派 / 该等 / 该跳过」——n 个状态 × m 个模式 = n×m 个角落要照顾，漏一个就是 bug。

事件驱动把「轮询」这一维直接抽掉：节点「问完问题进程结束」后，**没有任何事件触发**，调度器自然休眠等待，不会重复派发。**因此根本不需要任何「停车标记」**——拦路标记之所以存在，只是为了拦住轮询的重复派发；轮询没了，标记也就没了。

**影响**：`orchestrator.py` 的 `run()` 轮询循环重写为事件处理器；删 `_waiting_node_key`、`_await_feed_and_resume`。

---

## 决策 2：删除 ask tool

**结论**：worker 提问用普通文本输出即可，文本推群聊（跟对话路径 `_stream_one_agent` 同一通道）。

**为什么**：v3 让「提问」变成需要专用 tool + 特殊状态的例外流程。真正的根因只是 `executor._consume` 把 worker 的 TEXT 吞了，于是开了个 `ask` tool 当结构化逃生口。删 ask tool，改 executor 推文本，根因即除。

**影响**：`mcp_step_tools.py` 删 `ask` 定义；`executor.py` 删 `_ASK_TOOL` 检测分支、TEXT 改推群聊。

---

## 决策 3：删除 PAUSED 状态

**结论**：概念上只有两态——**完成 / 没完成**（外加 FAILED 永久失败终态）。删 PAUSED。

**为什么**：见决策 1——事件驱动下不需要「别重复派」的拦路标记。worker「问问题」跟「写代码」对调度器无差别，都是「没完成」。

**影响**：`enums.py` 去掉 `PAUSED`；`fsm.py` 去掉 PAUSED 相关转移；`session_state.py` 的 `StepView` / `PlanView.waiting` 相应调整。

---

## 决策 4：not_done 不算失败

**结论**：worker 流结束但没调 `task_complete` = 「没做完」，不是失败。安静等 feed，**不走 FAILED 重试**。

**为什么**：v3 现状是 `needs_reprompt → _handle_failure → FAILED 重试 3 次`，把「没交卷」当失败。但 worker 流结束可能只是问了问题在等回复（短驻 CLI stdin 关了自然结束）。当失败重试只会让它把同样的问题再问一遍。事件驱动下 not_done 节点没有事件触发，安静停在「没完成」等 feed 即可。

**影响**：`orchestrator.py` 的 `_settle`：`needs_reprompt → _handle_failure` 那条路删除，改为「不做任何转移，等 feed」。

---

## 决策 5：resume 机制必须保留（纠正 v4 文档的错误）

**结论**：resume（`pending_answer` 注入 + CLI `--resume`）原样保留。v4 文档 §13.1 把 resume 错列进「步 2.5 删除」清单（出现在两处：Orchestrator 状态行「仍含 PAUSED/`_feed_event`/resume（步 2.5 删）」和步 2.5 行「删 ask tool + PAUSED 态 + resume 机制」），**两处都要改**。

**为什么**：resume 是 worker 续上下文的**唯一手段**，是 feed 能成立的前提。feed 的本质就是「让 worker 接着上次干」——删了 resume，feed 就退化成「重开一个什么都不记得的 worker」，用户的回答喂给它也接不上之前的进度。

该删的只是 ask tool（提问协议），不是 resume（续上下文机制）。前者是 v3 给「提问」开的特殊后门，该堵；后者是任何「派出去 → 等回答 → 接着干」流程绕不开的。[[simplify-step-tools-no-ask-paused]] 当初删的也只是显式的 `PAUSED → RUNNING` 转移，它的替代方案（`feed → executor.run(--resume)`）本身就依赖 `--resume`。

**补充澄清（防实现走偏）**：事件驱动简化的是**控制流**（没轮询、没模式分支），不是说每节点只剩 1 bit。节点仍需记两样**数据**（非状态、非模式）：**resume 句柄**（CLI session id，feed 时 `--resume` 要用）、**依赖关系**（派下游前要知道上游完成没）。别把 resume 句柄包装成一个新状态，否则刚拔掉的组合爆炸根又种回去。

---

## 决策 6：replan 破坏性才确认

**结论**：replan（执行期改计划）要 cancel 正在跑的 worker 或丢弃已完成成果时，**先出 diff 求用户确认**；纯新增节点 / 只改还没开始的 PENDING 节点 → 直接换图，群聊通报即可。

**为什么**：cancel 在飞 worker / 丢 COMPLETED 成果是难逆转操作。而触发 replan 的只是 decide 的一次 LLM 分类，误判（把「后端顺便用下 Go 的库」读成「后端换成 Go」）会白杀在飞 worker。按「难逆转动作先确认」原则，破坏性 replan 必须有闸门。

**关键**：「要不要确认」这个判断由 **Harness 确定性计算**（diff 出哪些 RUNNING 会被取消、哪些 COMPLETED 成果被丢），**不靠 LLM 再赌一次**。LLM 只负责生成新计划，「这个新计划破不破坏」由代码客观裁定。

**影响**：`orchestrator.py` 的 `on_replan(new_tasks)`：先算 diff，破坏性则群聊发确认请求（复用 feed/done，无新通道）。

---

## 决策 7：取消 step dispatch budget

**结论**：原 v4 §6.8/§9.5 的「每 step 最多 3 次 dispatch，超了 FAILED」机械截断，取消。

**为什么**：dispatch budget 想区分「转了很多轮没产出」和「问了问题在等」，但决策 2–4 删了 ask 信号后，budget 无法区分这两者，会误杀正常多轮提问的 worker（初次 + 两次 feed = 3 次，还没开始干活就被判失控）。worker 失控改靠：Planner 从 transcript 自然判断 + wall-clock 超时兜底（截「一轮太久」）。

**影响**：删 `node.dispatch_count` 截断逻辑；§9.5 改为 wall-clock + Planner 判断。

---

## 决策一览

| # | 决策 | 一句话 |
|---|------|--------|
| 1 | 事件驱动 over 轮询 | 拔掉 v3「状态×模式×轮询」组合爆炸的根 |
| 2 | 删 ask tool | worker 普通文本提问即可，根因是 executor 吞文本 |
| 3 | 删 PAUSED | 概念两态：完成 / 没完成 + FAILED |
| 4 | not_done 不算失败 | 没交卷 = 没做完，安静等 feed |
| 5 | resume 保留 | 续上下文机制，feed 的前提；resume 句柄是数据不是状态 |
| 6 | replan 破坏性才确认 | diff 由 Harness 算，要 cancel RUNNING 才弹确认 |
| 7 | 取消 dispatch budget | 改靠 Planner 判断 + wall-clock 兜底 |
