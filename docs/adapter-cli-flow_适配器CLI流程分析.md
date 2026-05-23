# Adapter → CLI 全场景流程分析

> 版本：v1.3 | 日期：2026-05-23 | 基于 ADR-01 + v4 统一方案
> v1.3: §8 Session 生命周期补充完整前端↔后端↔CLI 交互流程 / §6 权限补充完整检测→通知→重试流程

---

## 一、统一调用链骨架

```
ChatService.send_and_stream(cmd)
  │
  ├─ 1. 持久化 user message (PG messages 表)
  ├─ 2. 写 L1 滑动窗口 (Redis, session_id → list)
  ├─ 3. 发布 MessageSent 事件
  │
  ├─ 4. ContextBuilder.build(session, agent) → AgentRequest
  │     填充基础字段 (messages, memory)
  │     + CLI 增强字段 (identity → --system-prompt / capability + peer → prompt 文本)
  │     注：身份信息走 --system-prompt（CLI 原生），
  │         其他上下文（peer 消息、能力描述）注入 prompt 文本
  │
  └─ 5. llm.stream(request)  ← 多态分派
        │
        ├── ClaudeAdapter (API)     → Anthropic SDK → yield StreamEvent
        └── ClaudeCodeRuntime (CLI) → subprocess    → yield StreamEvent
             │
             ├─ _resolve_session()    ← AgentHub session_id 即 CLI session_id
             ├─ _build_command()      ← --resume or --session-id
             ├─ _spawn()              ← subprocess, per-agent env
             ├─ _read_loop()          ← stdout JSON Lines → StreamEvent（含 stdin 写入）
             └─ _cleanup()            ← on exit/error/timeout
```

---

## 二、场景一：私聊首条消息

**触发**：用户创建 Agent "前端专家"（agent_system=claude_code），发送第一条消息 "创建一个登录页面"

```
ChatService.send_and_stream()
│
├─ messages = [{"role":"user", "content":"创建一个登录页面"}]
│
├─ ContextBuilder:
│   system_prompt = """
│     你是 FrontendAgent，前端开发专家。
│     项目目录: /tmp/agenthub/sessions/{agent_id}/
│     """
│   capability_prompt = None     ← M2: ToolRegistry 未就绪
│   peer_context = None          ← 私聊无群组上下文
│
├─ AgentRequest(
│     messages=messages,
│     system_prompt=system_prompt,      ← 传给 --system-prompt
│   )
│
└─ ClaudeCodeRuntime.stream(request)
      │
      ├─ session_key = str(request.session_id)  ← 直接复用 AgentHub session_id
      │
      ├─ prompt = "创建一个登录页面"             ← 只传用户消息
      │
      ├─ cmd = [
      │     "claude",
      │     "--print",
      │     "--session-id", session_key,   ← 新建 CLI session
      │     "--output-format", "stream-json",
      │     "--verbose",
      │     "--system-prompt", system_prompt, ← 身份注入
      │     "--max-turns", max_turns,
      │   ]
      │
      ├─ env = {
      │     "ANTHROPIC_API_KEY": decrypt(agent.api_key),
      │     "ANTHROPIC_MODEL": agent.model,
      │     "ANTHROPIC_BASE_URL": agent.base_url,
      │   }
      │
      ├─ process = subprocess.Popen(cmd, env=env, stdin=PIPE, stdout=PIPE, stderr=PIPE)
      ├─ process.stdin.write(prompt.encode())  ← stdin 写入，避免命令行长度限制
      ├─ process.stdin.write_eof()
      │
      ├─ for line in process.stdout:
      │     event = _parse_line(line)
      │     yield event
      │
      ├─ process.wait()
      ├─ exit_code == 0 → yield DONE
      │
      └─ ChatService: 落库 assistant message + 写 L1 + 发布 StreamingCompleted
```

**CLI stdout 流 → StreamEvent 映射**：

| CLI JSON Line | StreamEvent |
|---|---|
| `{"type":"system","subtype":"init",...}` | 跳过（可提取 session_id/model/tools 等元信息） |
| `{"type":"assistant","message":{"content":[{"type":"text","text":"好的"}]}}` | `TEXT(seq=0, content="好的")` |
| `{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Write","id":"toolu_1","input":{...}}]}}` | `TOOL_CALL(seq=1, tool_call={name:"Write",...})` |
| `{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"toolu_1","content":"File created."}]}}` | `TOOL_RESULT(seq=2, success=true, content="File created.")` |
| `{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"toolu_2","content":"...was blocked...","is_error":true}]}}` | `TOOL_RESULT(seq=3, success=false, error="...was blocked...")` |
| `{"type":"assistant","message":{"content":[{"type":"text","text":"登录页面已创建"}]}}` | `TEXT(seq=4, content="登录页面已创建")` |
| `{"type":"result","subtype":"success","duration_ms":8500,...}` | `DONE(seq=5, metadata={duration_ms:8500,...})` |
| `{"type":"result","subtype":"error_max_turns","is_error":true,"permission_denials":[...]}` | `DONE(seq=6, metadata={is_error:true, permission_denials:[...]})` |

---

## 三、场景二：私聊后续消息（--resume 恢复）

**触发**：同会话中用户接着说 "把按钮颜色改成蓝色"

```
ChatService.send_and_stream()
├─ messages = L1 window = [
│     {"role":"user", "content":"创建一个登录页面"},
│     {"role":"assistant", "content":"好的，登录页面已创建..."},
│     {"role":"user", "content":"把按钮颜色改成蓝色"},
│   ]
│
├─ ContextBuilder: system_prompt 同上（每次注入，冗余但无害）
│
└─ ClaudeCodeRuntime.stream(request)
      │
      ├─ session_key = str(request.session_id)  ← 复用同一个 session_id
      │
      ├─ cmd = [
      │     "claude",
      │     "--resume", session_key,    ← 恢复已有 CLI 会话
      │     "--output-format", "stream-json",
      │     "--verbose",
      │     "--system-prompt", system_prompt,
      │     "--max-turns", max_turns,
      │   ]
      │
      ├─ stdin.write("把按钮颜色改成蓝色")  ← 只传当前消息
      │
      ├─ CLI 内部行为：
      │   1. sqlite 恢复完整历史（首轮 system_prompt + 全部对话）
      │   2. 追加当前消息 "把按钮颜色改成蓝色"
      │   3. 基于完整上下文生成回复
      │
      └─ 后续流程同场景一
```

**关键区别**：`--resume` 让 CLI 自己维护完整对话历史，AgentHub 不需要每轮传全量 messages。

---

## 四、场景三：群聊 —— Coordinator 分解 + Worker 并发执行（M3）

**触发**：用户在群组 "全栈开发组" 发送 "做一个博客系统"

### Phase A: Coordinator 任务分解（API 模式）

```
ChatService.send_and_stream()
├─ 检测：dispatch_mode=auto, 无 @mention
├─ 意图分类 → task_intent=True
│
├─ CoordinatorService.decompose_and_dispatch()
│   │
│   ├─ coordinator_llm.chat_structured(prompt)  ← ClaudeAdapter (API)
│   │     返回 JSON:
│   │     {
│   │       "tasks": [
│   │         {"id":"t1","intent":"ui","desc":"博客首页 UI",
│   │          "suggested_worker":"frontend_agent","deps":[]},
│   │         {"id":"t2","intent":"api","desc":"博客 API",
│   │          "suggested_worker":"backend_agent","deps":[]},
│   │         {"id":"t3","intent":"review","desc":"代码审查",
│   │          "suggested_worker":"reviewer_agent","deps":["t1","t2"]}
│   │       ]
│   │     }
│   │
│   ├─ Harness.validate(plan)
│   │   ├─ detect_cycle(tasks) → False
│   │   └─ route_workers: 校验 worker 可用性 + 负载
│   │
│   ├─ 批量写入 tasks 表（父任务 + 3 个子任务）
│   │
│   └─ 并发执行:
│       await asyncio.gather(
│           execute_subtask(t1, frontend_agent, group_context),
│           execute_subtask(t2, backend_agent, group_context),
│       )
│       # t3 依赖 t1, t2，两者完成后触发
│       await execute_subtask(t3, reviewer_agent, group_context)
```

**Coordinator 为什么用 API 而不用 CLI？** `chat_structured` 需要可靠的 JSON 结构化输出。CLI 的 `--print` 模式下输出无法保证合法 JSON。

### Phase B: Worker 子任务执行（CLI 模式）

```
execute_subtask(task, agent, group_context)
│
├─ ContextBuilder.build_for_task(agent, task, group_context)
│   │
│   ├─ system_prompt = """
│   │     你是 FrontendAgent，前端开发专家。
│   │     当前在「全栈开发组」群聊中，你的角色是 member。
│   │
│   │     其他成员：
│   │     - BackendAgent: 后端开发专家，擅长 [python, fastapi, postgresql]
│   │     - ReviewerAgent: 代码审查专家，擅长 [code_review, testing]
│   │
│   │     行为规则：
│   │     - 收到分配的任务时，执行并回复
│   │     - 其他 Agent 的对话不需要你响应
│   │     """                           ← 身份走 --system-prompt
│   │
│   ├─ peer_context = """
│   │     ## 群聊上下文
│   │     **用户**: 做一个博客系统
│   │     **协调者**: 任务已分解：
│   │       - t1 (前端): 博客首页 UI → FrontendAgent
│   │       - t2 (后端): 博客 API → BackendAgent
│   │     **BackendAgent**: API 端点设计完成：
│   │       GET /api/posts, POST /api/posts, GET /api/posts/:id
│   │       响应格式：{id, title, content, created_at}
│   │     """                           ← peer 上下文注入 prompt 文本
│   │
│   └─ capability_prompt = """..."""    ← 能力描述注入 prompt 文本
│
├─ ClaudeCodeRuntime.stream(request)
│   │
│   │  cmd: --system-prompt + --resume
│   │  stdin: peer_context + capability_prompt + task_message
│   │  --resume 维持自己的对话连续性
│   │
│   └─ 产出的 StreamEvent 标注 task_id
│
└─ WS 推送 → 前端任务卡片实时渲染
```

---

## 五、场景四：群聊自由讨论（非任务意图）

**触发**：用户在群组 "全栈开发组" 发送 "我想做一个博客，你们有什么想法？"（讨论意图，非任务指令，无 @mention）

### 5.1 意图分类

消息到达后，ChatService 首先判定处理路径：

```
用户消息: "我想做一个博客，你们有什么想法？"
│
├─ 有 @mention？ → 否 → 不走 direct 路由
│
├─ 意图分类（轻量规则 + LLM 兜底）：
│   │
│   ├─ 任务关键词: "做"、"创建"、"实现"、"帮我"
│   │   → task_intent → Coordinator 分解
│   │
│   ├─ 讨论关键词: "想法"、"建议"、"你们觉得"、"怎么看"
│   │   → discussion_intent → broadcast 讨论模式
│   │
│   └─ 兜底: 非明确任务 → discussion_intent
│
└─ 结果: discussion_intent → 群聊讨论模式
```

### 5.2 讨论模式核心机制：并行通知 + 独立决策

与任务模式不同，讨论模式中**没有 Coordinator 参与**。每个 Agent 独立接收上下文、独立判断是否回应。

```
ChatService.send_and_stream()
│
├─ 1. 持久化 user message + L1 + broadcast WS（所有在线成员立即可见）
│
├─ 2. 判定 intent = discussion
│
├─ 3. 为群组内每个 Agent 并行构建 AgentRequest + 调用 CLI
│   │
│   │   for agent in group.members:          ← 并行，asyncio.gather
│   │       req = ContextBuilder.build_for_discussion(agent, group, user_msg)
│   │       tasks.append(agent_runtime.stream(req))
│   │
│   │   results = await asyncio.gather(*tasks, return_exceptions=True)
│   │
│   └─ 关键：Agent 之间在**同一轮内互相看不到对方的回复**
│      因为并行执行，peer_context 只包含「本轮之前」的历史消息
│
├─ 4. 收集每个 Agent 的响应
│
└─ 5. 逐个保存 + L1 + broadcast WS
```

### 5.3 每个 Agent 收到的上下文

以 Agent "FrontendAgent" 为例：

```
ContextBuilder.build_for_discussion(frontend_agent, group, user_msg)
│
├─ system_prompt:                       ← 身份走 --system-prompt
│   """
│   你是 FrontendAgent，前端开发专家。
│   当前在「全栈开发组」群聊中。
│
│   群组成员：
│   - BackendAgent: 后端开发专家，擅长 [python, fastapi]
│   - ReviewerAgent: 代码审查专家，擅长 [code_review, testing]
│   - Coordinator: 任务协调者，负责任务分解与分配
│
│   行为规则：
│   - 用户在群聊中提问时，基于你的专长给出建议
│   - 如果你没有相关建议，可以不回复
│   - 不要替其他 Agent 回答他们领域的问题
│   """
│
├─ peer_context: None（第一轮没有其他人的回复）
│   后续轮次会包含上一轮其他 Agent 的回复（见 §5.6）
│
├─ messages: L1 window（含当前用户消息）
│
└─ capability_prompt: 工具描述（M3 启用，注入 prompt 文本）
```

**CLI 调用方式**：每个 Agent 走自己的 CLI session（--resume 恢复历史连续性）。

```
ClaudeCodeRuntime.stream(request):
  ├─ session_key = f"{group_session_id}:{agent_id}"  ← 群聊中每个 Agent 独立 CLI session
  │
  ├─ prompt = user_message  (+ peer_context if exists)
  │
  └─ cmd = ["claude", "--resume", session_key,
             "--output-format", "stream-json",
             "--system-prompt", system_prompt,
             "--max-turns", max_turns]
  └─ stdin.write(prompt)
```

### 5.4 Agent 响应的三种情况

| 情况 | Agent 行为 | Adapter 产出 | ChatService 处理 |
|------|-----------|-------------|-----------------|
| **有建议** | 生成文本回复 | TEXT × N → DONE | 落库 + L1 + broadcast WS |
| **无建议** | CLI 输出 "暂无建议" 或空回复 | TEXT("暂无") → DONE | 落库（可折叠展示） |
| **超时未响应** | 60s 无输出 | asyncio.wait_for 超时 | 不落库，仅日志 |

### 5.5 并发执行与前端渲染

```
时间线：
  t=0    用户消息广播到群聊（所有人可见）
  t=0    asyncio.gather 并行启动 3 个 Agent CLI
  │
  ├─ t=2s   FrontendAgent 开始流式输出:
  │         "建议用 React + Tailwind，响应式设计，组件库推荐 shadcn/ui..."
  │         → WS push: {agent: "FrontendAgent", text: "建议用 React..."}
  │
  ├─ t=3s   BackendAgent 开始流式输出:
  │         "后端推荐 FastAPI + PostgreSQL，需要用户认证、文章 CRUD、评论系统..."
  │         → WS push: {agent: "BackendAgent", text: "后端推荐 FastAPI..."}
  │
  └─ t=60s  ReviewerAgent 超时无响应 → 跳过

前端 ChatView 渲染：
┌─────────────────────────────────────────┐
│ 用户: 我想做一个博客，你们有什么想法？     │
│                                         │
│ ┌─ FrontendAgent ─────────────────────┐ │
│ │ 建议用 React + Tailwind，响应式设计， │ │
│ │ 组件库推荐 shadcn/ui...              │ │
│ └──────────────────────────────────────┘ │
│                                         │
│ ┌─ BackendAgent ──────────────────────┐ │
│ │ 后端推荐 FastAPI + PostgreSQL...     │ │
│ └──────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### 5.6 多轮讨论：peer_context 的累积

用户继续追问：

```
第二轮：用户 → "前端用什么状态管理比较好？"

ContextBuilder.build_for_discussion(backend_agent, group, user_msg_2):
│
├─ identity_prompt: 同上
│
├─ peer_context: """                    ← 本轮新增：上一轮的 Agent 回复
│     ## 上一轮群聊讨论
│     **FrontendAgent**: 建议用 React + Tailwind，组件库推荐 shadcn/ui
│     **BackendAgent**: 后端推荐 FastAPI + PostgreSQL，需要用户认证
│     """
│
└─ messages: L1 window（含两轮对话）
```

**关键**：peer_context 让每个 Agent 在第二轮能看到第一轮其他人说了什么，从而给出更有针对性的回复。

```
BackendAgent 第二轮收到的完整 prompt:
"""
## 你的身份
你是 BackendAgent，后端开发专家。
...

## 上一轮群聊讨论
**FrontendAgent**: 建议用 React + Tailwind，组件库推荐 shadcn/ui
**BackendAgent**: 后端推荐 FastAPI + PostgreSQL，需要用户认证

用户：前端用什么状态管理比较好？
"""
```

BackendAgent 看到前一轮 FrontendAgent 提到 shadcn/ui 后，可能回应：
"前端用 shadcn/ui 的话，状态管理推荐 Zustand，轻量且和 React 配合好..."

### 5.7 LoopGuard：防止 Agent 互相聊死

```
场景：Agent 之间的回复可能触发连锁反应

FrontendAgent: "建议用 React + Tailwind"
  → BackendAgent: "React 不错，需要我提供什么 API？"
    → FrontendAgent: "需要用户登录和文章 CRUD 的接口文档"
      → BackendAgent: "好的，我先设计 API 端点..."
        → FrontendAgent: "接口文档收到，字段设计有什么建议？"
          → ... 无限循环
```

LoopGuard 机制：

```python
class LoopGuard:
    def __init__(self, max_consecutive_agent_messages: int = 5):
        self.max_consecutive = max_consecutive

    def should_auto_respond(self, recent_messages: list[Message]) -> bool:
        """检查是否应该自动触发 Agent 回复。"""
        consecutive = 0
        for msg in reversed(recent_messages):
            if msg.role == "assistant" and msg.sender_type == "agent":
                consecutive += 1
            else:
                break  # 遇到 user 消息 → 重置计数

        return consecutive < self.max_consecutive
        # >= 5 条连续 Agent 消息 → 停止自动回复，等待用户介入
```

**生效流程**：

```
消息序列：                      LoopGuard.check()
  user: "你们有什么想法"         → count=0 ✓ 触发讨论
  FrontendAgent: "建议..."       → count=1 ✓ 仍可自动回复
  BackendAgent: "推荐..."        → count=2 ✓ 仍可自动回复
  FrontendAgent: "补充..."       → count=3 ✓ 仍可自动回复
  BackendAgent: "再补充..."      → count=4 ✓ 仍可自动回复
  ReviewerAgent: "建议..."       → count=5 ✗ 停止自动回复
  ── 系统注入 ──
  [系统]: "讨论活跃，如需继续请发送消息"
```

### 5.8 Adapter 关键差异：讨论 vs 任务

| 维度 | 讨论模式 | 任务模式（Coordinator） |
|------|---------|----------------------|
| 入口 | 意图分类 → discussion | 意图分类 → task |
| 是否触发 Coordinator | 否 | 是 |
| Agent 调用方式 | 并行 `asyncio.gather` 通知全体 | 先分解 → 再有向 dispatch |
| Agent 是否必须回复 | 否（可选沉默） | 是（分配的任务必须执行） |
| peer_context | 上一轮全体 Agent 回复 | 仅相关 Agent 的上下文 |
| 超时处理 | 静默跳过 | 任务标记 FAILED，触发重试/升级 |
| 前端渲染 | 消息气泡流 | 任务卡片 + 流式输出 |

---

## 六、场景五：权限处理（完整流程）

**重要前提**：`--print` 模式是**非交互式**的。CLI 不会弹交互式权限确认，也不产生独立的 `type: "permission"` 事件。阻断后直接结束此次调用。

### 6.1 实际 CLI 行为

```
危险操作被阻断时的 stdout 序列：

{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"rm -f /tmp/build"}}]}}
↓
{"type":"user","message":{"content":[{"type":"tool_result","content":"...was blocked. For security, Claude Code may only remove files from...","is_error":true}]}}
↓  （Agent 可能换个方式重试）
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"find ... -delete"}}]}}
↓
{"type":"user","message":{"content":[{"type":"tool_result","content":"...was blocked...","is_error":true}]}}
↓  （max_turns 耗尽）
{"type":"result","subtype":"error_max_turns","is_error":true,
 "permission_denials":[
   {"tool_name":"Bash","tool_use_id":"call_1","tool_input":{"command":"rm -f /tmp/build"}},
   {"tool_name":"Bash","tool_use_id":"call_2","tool_input":{"command":"find ... -delete"}}
 ]}
```

### 6.2 完整交互流程

```
CLI stdout: result with permission_denials
  │
  ├─ ClaudeCodeRuntime._parse_line()
  │   解析到 result.is_error=true + permission_denials=[...]
  │   → yield StreamEvent(type=DONE, metadata={permission_denials: [...], is_error: true})
  │
  ▼
ChatService.send_and_stream()
  │
  ├─ 收到 DONE event → 检测 metadata.permission_denials 非空
  │
  ├─ 额外 emit StreamEvent(type=REQUEST_APPROVAL):
  │   {
  │     type: "request_approval",
  │     seq: N+1,
  │     content: "以下操作被安全策略阻断",
  │     metadata: {
  │       denied_ops: [                          ← 从 permission_denials 提取
  │         {tool: "Bash", input: "rm -f /tmp/build"},
  │         {tool: "Bash", input: "find ... -delete"}
  │       ],
  │       session_id: "abc-123",
  │       message_id: "msg-456",                 ← 对应的 assistant message ID
  │     }
  │   }
  │
  ├─ 落库 assistant message（status=BLOCKED，标记为被阻断）
  │
  └─ WS push → 前端
        │
        ▼
前端渲染审批卡片:
┌──────────────────────────────────────────────────────┐
│ ┌─ FrontendAgent ──────────────────────────────────┐ │
│ │ 操作被安全策略阻断                                 │ │
│ │                                                  │ │
│ │ 被阻断的操作:                                     │ │
│ │   ⚠️ Bash: rm -f /tmp/build (1)                  │ │
│ │   ⚠️ Bash: find ... -delete (2)                  │ │
│ │                                                  │ │
│ │ 这些操作涉及系统级删除，已自动拦截。                 │ │
│ │                                                  │ │
│ │ [信任并重试]  [换个安全方式]  [忽略]               │ │
│ └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
        │
        ├─ 用户点击「信任并重试」
        │   │
        │   │  WS: {action: "approve", message_id: "msg-456"}
        │   │  ─────────────────────────────────────▶
        │   │
        │   │  ChatService.handle_human_decision(APPROVE):
        │   │    1. 保存用户决策到 message metadata
        │   │    2. 用原 AgentRequest 重新调用 ClaudeCodeRuntime
        │   │    3. CLI cmd: --resume abc-123 \
        │   │               --permission-mode bypassPermissions    ← 放开权限
        │   │               --system-prompt "上一轮的操作用户已批准"
        │   │    4. stdin: (原始任务 prompt)
        │   │    5. 覆盖之前的 BLOCKED 消息为 STREAMING → 继续执行
        │   │
        │   └─ 用户点击「换个安全方式」
        │       │
        │       │  WS: {action: "reject", message_id: "msg-456",
        │       │       feedback: "请用安全的方式删除，不要用 rm"}
        │       │  ─────────────────────────────────────▶
        │       │
        │       │  ChatService.handle_human_decision(REJECT):
        │       │    1. 保存用户决策 + feedback
        │       │    2. 重新调用 ClaudeCodeRuntime
        │       │    3. CLI cmd: --resume abc-123 \
        │       │               --system-prompt "上一个方案被拒绝了"
        │       │    4. stdin: "被拒绝。请用不涉及 rm -rf 的安全方式重新实现。"
        │       │               + feedback
        │       │    5. CLI 基于反馈换一个工具/方式执行
        │       │
        │       └─ 用户点击「忽略」
        │            消息卡片折叠，不重新执行
```

### 6.3 StreamEvent 映射（更新）

在 §二的事件映射表基础上，permission_denials 场景新增两条映射：

| CLI JSON Line | StreamEvent |
|---|---|
| `{"type":"user","message":{"content":[{"type":"tool_result","is_error":true,"content":"...was blocked..."}]}}` | `TOOL_RESULT(seq, success=false, error="...was blocked...")` |
| `{"type":"result","subtype":"error_max_turns","is_error":true,"permission_denials":[...]}` | `DONE(seq, metadata={is_error:true, permission_denials:[...]})` → ChatService 额外 emit `REQUEST_APPROVAL` |

### 6.4 预设模式

Agent 创建时可选的 `permission_mode`，不是每轮调用的参数，而是 Agent 级别的默认值：

| Agent `permission_mode` | CLI `--permission-mode` | 行为 |
|---|---|---|
| `"acceptEdits"`（推荐默认） | `--permission-mode acceptEdits` | 文件编辑自动通过，Bash/git 等危险操作被阻断 |
| `"bypassPermissions"` | `--permission-mode bypassPermissions` | 全自动（仅用于被信任的 Agent） |

### 6.5 为什么不在 --print 模式下尝试 stdin 交互式审批

CLI 的交互式权限确认需要**交互式 stdin**（`y/n` + Enter），但 `--print` 模式：
- 阻断后立即结束 `result` 消息，不等待 stdin 输入
- stdin 在 `--print` 模式下用于一次性传入消息，不是用于交互

所以审批只能走「检测阻断 → 通知用户 → 用户确认 → 重新调用 + bypassPermissions」的路径。

---

## 七、场景六：异常处理

### 7.1 CLI 进程崩溃

```
process.poll() → 1 (非零)
│
├─ stderr = process.stderr.read()
├─ yield StreamEvent(
│     type=ERROR,
│     content="CLI 进程异常退出",
│     metadata={"exit_code": 1, "stderr": stderr[-500:]}
│   )
└─ CLI session 文件可能损坏，下次 --resume 可能失败需 fallback --session-id
```

### 7.2 执行超时

```
Timer: request.params.timeout (default 300s)
│
├─ process.send_signal(signal.SIGTERM)
├─ await asyncio.sleep(5)          ← 优雅退出窗口
├─ if process.poll() is None:
│     process.kill()                ← SIGKILL
│
├─ yield StreamEvent(type=ERROR, content="执行超时 (300s)")
└─ SessionStore.touch(session_id)  ← 保留 session 供重试
```

### 7.3 stdout 解析容错

```python
for line in process.stdout:
    line = line.strip()
    if not line:
        continue
    try:
        data = json.loads(line)
        yield self._map_to_event(data)
    except json.JSONDecodeError:
        logger.warning(f"CLI 非 JSON 输出: {line[:200]}")
        continue  # 不崩溃，跳过异常行
```

### 7.4 spawn 失败

```
subprocess.Popen raises FileNotFoundError
│
└─ yield StreamEvent(
      type=ERROR,
      content="claude CLI 未安装。请运行: npm install -g @anthropic-ai/claude-code"
    )
```

---

## 八、场景七：Session 生命周期（完整流程）

### 8.1 存储关系

```
AgentHub session_id = CLI session_id（同一个 UUID，无需映射）

存储位置                    内容                          负责方
─────────────────────────────────────────────────────────────────
PG sessions 表              id/type/title/agent_id/group_id   AgentHub
PG messages 表              每条消息 + session_id             AgentHub
CLI 磁盘                    ~/.claude/sessions/{id}/         CLI 内部
  ├── transcript.jsonl      完整对话历史（含 tool_use）
  ├── messages.json         消息列表
  └── meta.json             会话元信息
```

**为什么不需要 SessionStore 映射层？** AgentHub session_id（UUID）直接传给 CLI 的 `--session-id` / `--resume`。CLI 原生支持任意字符串作为 session identifier。前端已有完整的 REST API 查 PG，不需要额外映射表。

### 8.2 创建 Session

```
前端                                      后端                                    CLI
  │                                         │                                      │
  │  POST /api/sessions                     │                                      │
  │  {type:"private", agent_id: X}          │                                      │
  │  ─────────────────────────────────────▶ │                                      │
  │                                         │  1. INSERT INTO sessions             │
  │                                         │     → session_id = UUID-abc-123      │
  │                                         │  2. CLI 暂不创建（等首条消息）         │
  │                                         │                                      │
  │  201 {id:"abc-123", type:"private",     │                                      │
  │       agent_id:X, title:"前端开发讨论"}   │                                      │
  │  ◀───────────────────────────────────── │                                      │
  │                                         │                                      │
  │  【SessionList 自动刷新，显示新会话】      │                                      │
```

### 8.3 发送首条消息

```
前端                                      后端                                    CLI
  │                                         │                                      │
  │  WS /ws/sessions/abc-123                │                                      │
  │  {"content": "帮我写个登录页"}            │                                      │
  │  ─────────────────────────────────────▶ │                                      │
  │                                         │  1. 持久化 user message (PG)          │
  │                                         │  2. 写 L1 Redis                       │
  │                                         │  3. 构造 AgentRequest                 │
  │                                         │  4. ClaudeCodeRuntime.stream()        │
  │                                         │     │                                  │
  │                                         │     ├─ cmd = [                        │
  │                                         │     │    "claude",                    │
  │                                         │     │    "--print",                   │
  │                                         │     │    "--session-id", "abc-123",   │  ← 首次创建
  │                                         │     │    "--system-prompt", "...",     │
  │                                         │     │    "--output-format", "stream-json",│
  │                                         │     │  ]                              │
  │                                         │     ├─ spawn ──────────────────────────▶│
  │                                         │     │         CLI 创建                  │
  │                                         │     │         ~/.claude/sessions/abc-123/│
  │                                         │     ├─ stdin.write("帮我写个登录页")    │
  │                                         │     │         ──────────────────────▶│
  │                                         │     │                                  │ 开始推理
  │  ← TEXT/THINKING/TOOL_CALL 逐事件推送 ←─│─────│── stdout JSON Lines ────────────│
  │                                         │     │                                  │
  │  ← DONE (duration_ms=8500, ...)         │     │  进程退出                         │
  │                                         │  5. 落库 assistant message (PG)        │
  │                                         │  6. 写 L1 Redis                       │
  │                                         │  7. 发布 StreamingCompleted            │
```

### 8.4 用户关闭页面后重新打开（查询与恢复）

```
前端                                      后端                                    CLI
  │                                         │                                      │
  │  GET /api/sessions?type=private         │                                      │
  │  ─────────────────────────────────────▶ │                                      │
  │                                         │  SELECT * FROM sessions              │
  │                                         │  WHERE type='private'                │
  │                                         │                                      │
  │  [                                      │                                      │
  │    {id:"abc-123", title:"前端开发讨论"},   │                                      │
  │    {id:"def-456", title:"后端API设计"}     │                                      │
  │  ]                                      │                                      │
  │  ◀───────────────────────────────────── │                                      │
  │                                         │                                      │
  │  【用户点击「前端开发讨论」】               │                                      │
  │                                         │                                      │
  │  GET /api/sessions/abc-123/messages     │                                      │
  │  ─────────────────────────────────────▶ │                                      │
  │                                         │  SELECT * FROM messages              │
  │                                         │  WHERE session_id = 'abc-123'        │
  │                                         │  ORDER BY created_at                 │
  │                                         │                                      │
  │  [                                      │                                      │
  │    {role:"user", content:"帮我写个登录页"},│                                      │
  │    {role:"assistant", content:"好的..."}  │                                      │
  │  ]                                      │                                      │
  │  ◀───────────────────────────────────── │                                      │
  │                                         │                                      │
  │  【ChatView 加载历史消息到界面】           │                                      │
  │                                         │                                      │
  │  WS /ws/sessions/abc-123                │                                      │
  │  {"content": "把按钮颜色改成蓝色"}         │                                      │
  │  ─────────────────────────────────────▶ │                                      │
  │                                         │  ClaudeCodeRuntime.stream()          │
  │                                         │  cmd = --resume abc-123              │  ← 恢复已有会话
  │                                         │  ──────────────────────────────────▶│
  │                                         │         CLI 从 sqlite 恢复完整历史     │
  │                                         │         加载首轮 system_prompt        │
  │                                         │         加载全部对话消息               │
  │                                         │         追加当前消息                  │
  │  ← 流式响应 ←───────────────────────────│─────│── 基于完整上下文生成回复 ────────│
```

### 8.5 删除 Session

```
前端                                      后端                                    CLI
  │                                         │                                      │
  │  DELETE /api/sessions/abc-123           │                                      │
  │  ─────────────────────────────────────▶ │                                      │
  │                                         │  1. PG 软删除 session                │
  │                                         │  2. 异步清理:                        │
  │                                         │     rm -rf ~/.claude/sessions/abc-123/  ←──▶
  │                                         │                                      │
  │  204 No Content                         │                                      │
  │  ◀───────────────────────────────────── │                                      │
```

### 8.6 生命周期总结

```
创建 Session     POST /api/sessions   → PG INSERT → session_id (UUID)
首条消息         WS → --session-id    → CLI 创建 ~/.claude/sessions/{id}/
后续消息         WS → --resume        → CLI 从 sqlite 恢复完整上下文
重开页面         GET /api/sessions    → PG SELECT → 前端渲染会话列表
                GET …/messages       → PG SELECT → 加载历史消息
删除 Session     DELETE /api/sessions → PG 标记删除 + rm CLI 磁盘文件
清理（惰性）     定期任务             → 清理过期 PG session + 孤儿 CLI 文件
```

---

## 九、设计决策速查表

| 决策 | 理由 |
|------|------|
| 私聊首条：`--session-id`（新建） | 初始化 CLI 会话 |
| 私聊后续：`--resume` + 只传当前消息 | CLI 自己管历史，AgentHub 不传全量 messages |
| 身份信息走 `--system-prompt` | CLI 原生支持，不污染 user prompt |
| 其他上下文（peer/capability）注入 prompt 文本 | 非身份信息，拼入 stdin 传入 |
| 群聊 Worker：`--resume` + 每轮注入 peer_context | 自身对话用 resume，别人消息每轮增量注入 |
| Coordinator：API 模式 `chat_structured` | 需要可靠的结构化 JSON 输出 |
| 群聊讨论：并行通知全体 Agent | Agent 独立决策是否回复，互不阻塞 |
| 讨论轮次：peer_context 只含本**轮之前**的消息 | 并行执行中 Agent 互相看不到同轮回复 |
| session_id 直接复用 AgentHub session UUID | 无需额外映射层，CLI 原生支持 UUID |
| 超时保留 session / 崩溃删除 session | 超时可能是正常任务过大，崩溃=状态损坏不可恢复 |
| WS 断开立即 kill，不保留进程 | --resume 已保证可恢复 |
| LoopGuard：连续 5 条 Agent 消息停止触发 | 防止 Agent 互相聊死，等用户介入 |
| 讨论超时 Agent 静默跳过 | 讨论非强制任务，沉默是合法行为 |
| 群聊 session_id 格式：`{group_session}:{agent_id}` | 同一群聊中每个 Agent 独立 CLI session |
| 权限：预设 acceptEdits + 检测 permission_denials | --print 模式无交互式提示，阻断后通知用户重试 |

---

## 十、相关文档

| 文档 | 内容 |
|------|------|
| `ADR-01-cli-first-pivot.md` | 架构决策：API→CLI 重心转移 |
| `PRD_AgentHub_v4_统一方案.md` §三 | 接口签名 + 双轨定义 |
| `DOC-15-claude-adapter-design.md` | 双轨架构详细设计 |
| `DOC-17-context-injection-problem.md` | CLI 上下文注入问题分析 |
