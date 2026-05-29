# Adapter → CLI 全场景流程分析

> 版本：v1.5 | 日期：2026-05-26 | 基于 ADR-01 + v4 统一方案
> v1.5: 重写 §五 群聊讨论模式 —— Selector 串行轮转 + 增量注入（替代旧的并行广播全员）；同步 §十 决策表
> v1.4: 新增 §九 CLI 多模型代理场景（鉴权适配 + 透明转发 + 错误处理）
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
             ├─ _build_env()           ← ANTHROPIC_BASE_URL → 本地代理
             ├─ _spawn()              ← subprocess, per-agent env
             │     │  CLI HTTP 请求 → ProxyHandler
             │     │  ├─ 鉴权适配（解密 api_key → x-api-key）
             │     │  ├─ URL 路由（agent.base_url + path）
             │     │  └─ 流式透明转发
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
      │     "ANTHROPIC_API_KEY": "agenthub-proxy",           ← 占位，真实 key 由代理注入
      │     "ANTHROPIC_MODEL": agent.model,
      │     "ANTHROPIC_BASE_URL": f"http://127.0.0.1:8000/proxy/agents/{agent.id}",  ← 指向本地代理
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

## 五、场景四：群聊讨论模式（Selector 轮转 + 增量注入）

> v1.5 重写。旧版（v1.0–v1.4 §五）描述的是「并行 asyncio.gather 广播全员」模式，已被 `docs/design/group-chat-discussion-mode_群聊讨论模式设计方案.md` 取代。当前实现为 **Selector 程序驱动的串行轮转 + watermark 增量注入**。

**触发**：用户在 `dispatch_mode=DISCUSSION` 的群组中发送 "我想做一个博客，你们有什么想法？"（无 @mention）

### 5.1 ChatService 路径分流

```
ChatService.send_and_stream(cmd)
│
├─ 1. 持久化 user message (PG) + 写 L1 + WS 广播
│
├─ 2. 取 session：session.type == GROUP？
│      └─ 否 → 私聊路径 (§二/三)
│
├─ 3. 取 group：group_repo.get_by_id(session.group_id)
│
├─ 4. 解析 @mention（trigger.mentions）
│      ├─ 非空 → V1 串行执行被 @ 的 Agent（逐个 _stream_one_agent）
│      └─ 空 → 看 group.dispatch_mode
│
├─ 5. dispatch_mode 路由
│      ├─ DISCUSSION → DiscussionOrchestrator.run_discussion
│      ├─ AT_ROUTING + 无 @ → 死群静默（仅广播用户消息）
│      └─ （M3）TASK → Coordinator 分解（见 §四）
│
└─ 6. 流式产出 StreamEvent → WS 推送 → 前端按 sender_agent_id 分色渲染
```

> 注意：当前 `SendMessageCommand.dispatch_mode` 字段被接收但 ChatService 不读取，路由完全由 `group.dispatch_mode` 决定。前端的 dispatch_mode 选择需要先持久化到群组配置（`coordinator_config['dispatch_mode']`）。

### 5.2 DiscussionOrchestrator：回合循环

讨论模式不再并行广播。改为**轮转 + Selector 程序驱动**的回合循环：

```
DiscussionOrchestrator.run_discussion(session, group, trigger):
│
│  pending_mentions: list[UUID] = []       # @ 接力队列
│  already_spoken: set[UUID] = set()       # 本次讨论已发言（Layer 3 用）
│
│  for round_no in range(settings.max_discussion_rounds):   # 默认 3 轮
│      members = load_members(group)                        # coordinator + member_ids
│      history = MessageRepo.list_by_session(session, limit=L1_WINDOW)
│
│      # 决策：pending_mentions 优先于 Selector
│      if pending_mentions:
│          next_id = pending_mentions.pop(0)
│          if next_id in already_spoken: continue           # 跳过已发言
│          decision = SelectorDecision.pick(next_id, reason="@mention queue", ...)
│      else:
│          decision = await Selector.pick(members, history, already_spoken)
│
│      # 合并 Selector 返回的新 mention_queue
│      for mid in decision.mention_queue:
│          if mid not in pending_mentions and mid not in already_spoken:
│              pending_mentions.append(mid)
│
│      if decision.done or decision.next_agent_id is None:
│          return                                            # 自然收敛
│
│      target = AgentRepo.get_by_id(decision.next_agent_id)
│      yield from _stream_one(session, group, target, trigger)
│      already_spoken.add(target.id)
│
│  # 触顶 MAX_ROUND，自然结束
```

**防循环三件套**：
1. **Selector DONE**（主力）—— LLM 判断讨论已收敛
2. **MAX_ROUND 硬上限**（默认 3，`settings.max_discussion_rounds`）
3. **人在环中断** —— 用户发新消息时 WS 进入新一次 `send_and_stream`，前一个生成器自然终止

### 5.3 Selector：三层路由（程序驱动，零~一次 LLM）

`Selector.pick(members, history, already_spoken)` 按优先级三层决策：

```
Layer 1 — @mention 直达（零 LLM）
│
│  扫描 history[-1]（即上一轮发言）
│    1. 用户消息：直接读 last.mentions 字段
│    2. Agent 自治 @：用正则 r"@([A-Za-z0-9_一-龥\-]+)" 扫文本，
│       排除 sender 自己（不能 @ 自己触发自己）
│  多个 @ → 第一个直达，其余进 mention_queue（接力队列）
│
│  返回：SelectorDecision(next=first, reason="@mention=...", mention_queue=(rest,))
│
Layer 2 — capability_tags 关键词匹配（零 LLM）
│
│  对每个 candidate（排除 last.sender_agent_id）：
│    hit_count = sum(1 for tag in agent.capability_tags
│                       if tag.lower() in last.content.lower())
│  best = argmax(hit_count) where hit_count > 0
│
│  返回：SelectorDecision(next=best, reason="capability hit=N")
│
Layer 3 — LLM 评估（廉价模型一次调用，强制 tool_use JSON）
│
│  candidates = [a for a in members if a.id not in already_spoken]
│  若全部已发言 → finish("all spoken in this round")
│
│  Provider 路由（settings.selector_provider）：
│    - deepseek (默认) → DeepSeek V4 Flash, OpenAI 兼容 API
│    - anthropic       → Haiku
│    - openai          → GPT
│
│  Tool schema：
│    select_next_speaker(
│      decision: "next" | "done",
│      agent_name?: str,        # decision=next 时必填，须是候选人之一
│      reason?: str
│    )
│
│  Prompt 优化（防止 history 过长撑爆上下文）：
│    Layer A: ```代码块``` → "[代码片段已省略]"
│    Layer B: 单条 > 300 字符 → 截断 "..."
│    Layer C: 总长 > settings.selector_max_prompt_chars (默认 4000)
│             → 从最旧开始丢弃，保留 ≥1 条
│
│  失败降级（key 缺失/网络异常/响应非法）→ finish，不阻塞用户
```

### 5.4 @mention 接力：用户 @ 多人 与 Agent 自治 @

```
情况 A：用户 @多人（dispatch_mode=DISCUSSION）
─────────────────────────────────────────────
用户: "@AgentA @AgentB 你们看看这个方案"
↓ trigger.mentions = ["AgentA", "AgentB"]

ChatService._handle_group:
  targets = _resolve_mentions(["AgentA", "AgentB"], group)
  ↓ [A, B] 非空 → V1 串行：逐个 _stream_one_agent（不走 Selector）

注：当前实现里，「用户 @ 多人 + DISCUSSION 模式」走的是
ChatService 的简单串行路径，不走 DiscussionOrchestrator。
mention_queue 机制主要服务于 Agent 自治 @ 接力链路。


情况 B：用户无 @，Agent 自治 @ 接力
─────────────────────────────────────────────
用户: "我想做一个博客"
↓ trigger.mentions = []

ChatService → DiscussionOrchestrator.run_discussion

round 0:
  Selector.pick → Layer 3 LLM 选 FrontendAgent
  FrontendAgent 回复末尾写: "@BackendAgent 需要后端配合"
  watermark.set(group, Frontend, msg_id)

round 1:
  Selector.pick:
    Layer 1 扫 history[-1].content 命中 @BackendAgent
    （sender=Frontend 自己排除掉，BackendAgent 通过）
    → SelectorDecision(next=Backend, reason="@mention=...")
  _stream_one(BackendAgent)

round 2:
  ... 直到 Selector DONE 或触顶 MAX_ROUND
```

### 5.5 ContextBuilder：watermark 增量注入

群聊每个 Agent 维护独立 **watermark**（Redis: `wm:{group_id}:{agent_id}` → message_id，TTL 7 天）。

```
ContextBuilder.build_for_agent(session, group, target_agent, trigger):
│
├─ delta = _compute_delta(session_id, group_id, agent_id):
│   │
│   │  wm = WatermarkStore.get(group, target_agent)
│   │
│   ├─ wm is None（首次接触）
│   │     seed = MessageRepo.list_by_session(session, limit=L1_WINDOW=20)
│   │     return _maybe_truncate(seed)
│   │
│   ├─ wm 命中
│   │     注：_extract_delta_from_l1 当前永远返回 None
│   │     （L1 缓存只存 role/content 字典，无 message_id 无法做 delta）
│   │     ↓
│   │     delta = MessageRepo.list_after(session, wm, limit=MAX_DELTA+1)
│   │     ↓
│   │     若 delta 为空 → wm 在 PG 不存在（被删除或失效）
│   │       → fallback 到种子历史（warning 日志）
│   │     若 delta 非空 → _maybe_truncate（默认 MAX_DELTA=50）
│   │
│   └─ _maybe_truncate：超长则取最近 N + 记录 truncated_count
│
├─ members_block = format_members(load_members(group), target_agent)
│      （列出其他成员名 + 角色，不含 target 自己）
│
├─ persona = target_agent.system_prompt or f"你是 {target_agent.name}。"
│
├─ delta_block = format_delta(delta.messages, agent_name_by_id)
│      格式：
│      ┌── 自上次发言后的新群聊消息（按时间顺序）：
│      │ ---
│      │ FrontendAgent: 建议用 React + Tailwind...
│      │ BackendAgent: 推荐 FastAPI...
│      │ 用户 (@FrontendAgent): 状态管理用什么？
│      │ ---
│      └──
│
├─ truncated_hint = "[省略了更早的 N 条群聊消息]" if truncated > 0
│
├─ system_prompt = "\n\n".join([
│      persona,
│      GROUP_CHAT_CONTRACT,        # 主动 @ 接力 / 简洁优先 / 角色聚焦
│      members_block,
│      truncated_hint + delta_block,
│   ])
│
└─ AgentRequest(
     messages=[{role: "user", content: trigger.content}],   ← 仅 trigger 单条
     system_prompt=system_prompt,
     memory=MemoryContext(l1_working=window),
     agent_id=target_agent.id,
     group_id=group.id,
     is_group_chat=True,
   )

流式完成（_stream_one 末尾）→ WatermarkStore.set(group, target, assistant_msg.id)
```

**关键差异**（vs 旧版 peer_context 设计）：

| 维度 | 旧版（v1.4 §5.6） | 新版（v1.5） |
|------|-------------------|--------------|
| 上下文容器 | peer_context（拼到 prompt 文本） | system_prompt 的 delta_block |
| 历史范围 | 上一轮所有 Agent 的回复 | 自该 Agent 上次发言后的全量增量 |
| 状态存储 | 无（每轮临时拼） | Redis watermark（按 group×agent） |
| 缓存友好 | 否 | 是（system_prompt 前缀稳定，cache 命中率高） |
| messages 内容 | L1 window 全量 | 仅 trigger.content 单条 |

### 5.6 ClaudeCodeRuntime：群聊 session key

```
_compute_session_key(request):
  if request.is_group_chat and request.agent_id is not None:
      return f"{session_id}:{agent_id}"     # 每 Agent 独立 sqlite
  return str(session_id)                     # 私聊单 Agent 占用整个 session
```

每个 Agent 拥有自己的 CLI session 目录：

```
session abc-123 (DISCUSSION 群聊)
├─ ~/.claude/sessions/abc-123:frontend-uuid/   FrontendAgent 视角
├─ ~/.claude/sessions/abc-123:backend-uuid/    BackendAgent 视角
└─ ~/.claude/sessions/abc-123:reviewer-uuid/   ReviewerAgent 视角

每次 _stream_one(AgentX):
  cmd = ["claude", "--print",
         "--resume", f"{session_id}:{agent_id}",   # 首次失败 → fallback --session-id
         "--system-prompt", <persona + CONTRACT + members + delta>,
         "--output-format", "stream-json", "--verbose",
         "--permission-mode", "acceptEdits",
         "--max-turns", "10"]
  stdin: trigger.content
```

CLI sqlite 中只保留该 Agent 自己的 turns（自身的 prompt + 自己说过的话）。**别人发言通过 system_prompt 的 delta_block 整段注入**，不混入 messages。

### 5.7 完整时间线：3 个 Agent 讨论

```
群组成员: [FrontendAgent, BackendAgent, ReviewerAgent]
dispatch_mode = DISCUSSION
MAX_ROUND = 3

t=0  user → "我想做一个博客"
       ChatService: 落库 + L1 + WS 广播
       → group.dispatch_mode == DISCUSSION + 无 @ → DiscussionOrchestrator

──────────── round 0 ────────────
t=0  Selector.pick:
       Layer 1: 无 @ → skip
       Layer 2: "博客" 无明显能力匹配 → skip
       Layer 3: LLM (DeepSeek V4 Flash) → tool_use: {decision:"next", agent_name:"FrontendAgent"}
     → next = FrontendAgent

t=1  _stream_one(FrontendAgent):
       ContextBuilder: wm=None → 种子 [user_msg]
       system_prompt = persona + CONTRACT + members + delta(user_msg)
       CLI --resume abc-123:Frontend-uuid（首次→fallback --session-id）
       stream → "建议 React + Tailwind，后端要给 API。@BackendAgent 你来设计"
       WS 推送（sender_agent_id=Frontend-uuid，前端用蓝色气泡）
       watermark.set(group, Frontend, msg_F.id)

──────────── round 1 ────────────
t=4  Selector.pick:
       Layer 1: history[-1] 是 Frontend 消息，扫到 @BackendAgent
       → next = BackendAgent

t=5  _stream_one(BackendAgent):
       ContextBuilder: wm=None (Backend 首次)
       system_prompt 包含 delta=[user_msg, Frontend 的回复]
       stream → "FastAPI + PostgreSQL，要不要审一下？@ReviewerAgent"
       watermark.set(group, Backend, msg_B.id)

──────────── round 2 ────────────
t=9  Selector.pick:
       Layer 1: 上一条含 @ReviewerAgent → next = Reviewer

t=10 _stream_one(ReviewerAgent):
       ContextBuilder: wm=None (Reviewer 首次)
       system_prompt 包含 delta=[user_msg, Frontend, Backend]
       stream → "整体合理。前端考虑 SSR，后端注意鉴权"
       watermark.set(group, Reviewer, msg_R.id)

──────────── round 3 == MAX_ROUND ────────────
t=13 触顶硬上限，循环退出（日志 INFO "讨论达到 max_round=3"）

前端 ChatView：
  user → Frontend 气泡 → Backend 气泡 → Reviewer 气泡

──────────── 用户追问 ────────────
t=20 user → "前端用什么状态管理？"
       新一次 send_and_stream，前面的 generator 已结束

       round 0: Selector → Layer 3 LLM → FrontendAgent
       ContextBuilder:
         wm = msg_F.id（上次 Frontend 发言的 id）
         delta = list_after(session, msg_F.id)
               = [Backend, Reviewer, 用户新消息]   ← 增量！
       system_prompt 注入这 3 条 delta（前缀 persona+CONTRACT+members 命中 prompt cache）
```

### 5.8 Agent 响应的三种情况

| 情况 | Selector 行为 | Adapter 产出 | ChatService 处理 |
|------|--------------|-------------|-----------------|
| **有发言** | next=Agent | TEXT × N → DONE | 落库 + L1 + WS + 推 watermark |
| **Selector LLM 判 done** | finish("llm done: …") | 不调用 Adapter | 循环退出 |
| **触顶 MAX_ROUND** | 不再调用 | 不调用 Adapter | INFO 日志后返回 |
| **Adapter 抛异常** | n/a | StreamingFailed 事件 | raise 给上层 ChatService（WS rollback + 推 error） |
| **CLI 权限被阻断** | n/a | DONE w/ permission_denials | 额外 emit REQUEST_APPROVAL（同私聊 §六） |

### 5.9 失败降级速查

| 场景 | 行为 |
|------|------|
| Selector LLM API Key 缺失（client 初始化失败） | finish("init failed")，不阻塞用户 |
| Selector LLM 调用异常（网络/限流） | finish(reason="llm error: {ExceptionClass}") |
| LLM 返回不带 tool_use / tool_calls | finish("no tool_use" / "no tool_calls") |
| LLM 选了不存在的候选名 | finish("unknown candidate: {name}") + warning |
| LLM 返回非法 decision 值 | finish("invalid decision: {raw}") |
| watermark 在 PG 不存在（消息被删） | fallback 种子历史 + warning |
| pending_mentions 中 agent 不存在 | continue 出队，下一位 |
| pending_mentions 中 agent 已发言 | continue 出队，下一位 |
| 群组成员为空 | finish("members empty") |
| history 为空 | finish("history empty") |

### 5.10 Adapter 关键差异：讨论 vs 任务

| 维度 | 讨论模式（当前实现） | 任务模式（M3 Coordinator，规划） |
|------|---------------------|----------------------|
| 入口 | dispatch_mode=DISCUSSION + 无 @ | dispatch_mode=AT_ROUTING + 任务关键词 |
| 调度方式 | Selector 串行轮转（每轮选 1） | Coordinator 分解 + 并发 dispatch |
| Agent 是否必须回复 | 否（Selector DONE 即停） | 是（被分配任务必须执行） |
| 上下文注入 | system_prompt + watermark delta | task_brief + peer_context |
| Coordinator 参与 | 不参与（仅当 member 出现时才被 Selector 选中） | 主导分解、有向 dispatch |
| 防循环 | MAX_ROUND=3 + Selector DONE | 任务依赖 DAG + cycle detect |
| 超时处理 | 单 Agent 异常 → 循环 raise | 任务标 FAILED → 重试/升级 |
| 前端渲染 | 按 sender_agent_id 分色的消息流 | 任务卡片 + 流式输出 |

### 5.11 与旧版（peer_context 并行广播）的对比

旧版（v1.0–v1.4）的「并行 asyncio.gather 通知全员」存在三个问题，促成了 v1.5 重构：

1. **LLM 成本失控**：每条用户消息触发 N 个 Agent 并发（N=群规模），即使大多数 Agent 无关
2. **回复噪声大**：所有 Agent 同时回应，互相看不到对方观点，输出冗余
3. **顺序不可控**：网络抖动决定先后，无法体现「主答 + 补充」的协作语义

新版以 Selector 程序驱动**每轮选 1 个最合适的发言人**，配合 watermark 增量注入：
- LLM 调用 ≤ MAX_ROUND（默认 3）次廉价模型 + 0~N 次目标 Agent
- @ 接力机制让 Agent 显式发起协作，对话路径可观测
- 缓存友好：system_prompt 前缀稳定，CLI prompt cache 命中率高

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

## 九、场景八：CLI 多模型代理

### 9.1 问题

Claude Code CLI 默认向 `https://api.anthropic.com` 发送 Anthropic Messages API 格式请求。要让 CLI 使用 DeepSeek、Kimi、GLM 等第三方模型，有两个障碍：

1. **鉴权不兼容**：CLI 固定使用 `x-api-key` header，第三方端点可能是 Bearer Token 或其他鉴权方式
2. **协议差异**：部分 Provider（GPT、Qwen）不提供 Anthropic 兼容端点，只支持 OpenAI Chat 格式

### 9.2 方案：内置透明代理

所有 CLI 流量统一经过 AgentHub 进程内的 ProxyHandler，不直连第三方。

#### 代理架构

```
Claude Code CLI (子进程)
    │  ANTHROPIC_BASE_URL = http://127.0.0.1:8000/proxy/agents/{agent_id}
    │  ANTHROPIC_API_KEY  = "agenthub-proxy"  (占位)
    │  ANTHROPIC_MODEL    = "deepseek-v4-pro"
    ▼
┌──────────────────────────────────────────────────────────────┐
│  ProxyHandler (AgentHub 进程内)                              │
│                                                              │
│  handle(agent_id, path, request):                            │
│    1. agent_repo.get_by_id(agent_id) → Agent 实体            │
│    2. decrypt(agent.api_key_encrypted) → 真实 API Key         │
│    3. 鉴权适配：forward_headers["x-api-key"] = real_key       │
│    4. target_url = f"{agent.base_url}/{path}"                │
│    5. httpx.stream(method, target_url, headers, body)        │
│    6. StreamingResponse(aiter_raw()) → 字节级透明回传         │
│                                                              │
│  ★ 不解析请求体/响应体 — 字节级透传                            │
│  ★ 过滤 hop-by-hop headers（host, transfer-encoding 等）      │
└──────────────────────────┬───────────────────────────────────┘
                           │ 真实 x-api-key + 原样 body
                           ▼
第三方 API (https://api.deepseek.com/anthropic/v1/messages)
```

### 9.3 场景 A：Agent 创建与代理配置

**触发**：用户通过 API 创建一个使用 DeepSeek 的 Agent

```
POST /api/agents
{
  "name": "DeepSeek代理测试",
  "agent_system": "claude_code",
  "model": "deepseek-v4-pro",
  "base_url": "https://api.deepseek.com/anthropic",
  "api_key": "sk-你的DeepSeek API Key"
}
│
├─ L4: AgentCreateRequest → CreateAgentCommand
├─ L3: AgentService.create()
│   ├─ encrypt_secret("sk-xxx") → api_key_encrypted (AES-256-GCM 密文)
│   ├─ Agent(base_url="https://api.deepseek.com/anthropic", ...)
│   └─ agent_repo.save(agent)
│
├─ L1: INSERT INTO agents:
│   │ agent_system  = "claude_code"
│   │ model         = "deepseek-v4-pro"
│   │ base_url      = "https://api.deepseek.com/anthropic"
│   │ api_key_encrypted = "<AES-256-GCM 密文>"   ← 永不落盘为明文
│
└─ 响应: AgentOut（不包含 api_key 和 base_url）
```

**关键**：`api_key` 只在内存中短暂存在。L3 加密后，明文丢弃。代理时 L1 解密 → 注入 header → 用完丢弃。

### 9.4 场景 B：CLI 启动 + 代理转发（正常流）

**触发**：用户在该 Agent 的会话中发送消息 "帮我写一个登录页面"

```
ChatService.send_and_stream()
│
├─ ContextBuilder.build() → AgentRequest
│
├─ factory.build_adapter_for_agent(agent)
│   │ agent.agent_system == CLAUDE_CODE
│   │
│   └─ ClaudeCodeRuntime(
│         model="deepseek-v4-pro",
│         agent_id="<UUID>",
│         proxy_base="http://127.0.0.1:8000",
│       )
│
└─ ClaudeCodeRuntime.stream(request)
      │
      ├─ _build_env():
      │   env["ANTHROPIC_API_KEY"]  = "agenthub-proxy"     ← 占位
      │   env["ANTHROPIC_MODEL"]    = "deepseek-v4-pro"
      │   env["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:8000/proxy/agents/<UUID>"
      │
      ├─ cmd = ["claude", "--print", "--session-id", session_key,
      │         "--output-format", "stream-json", "--verbose",
      │         "--system-prompt", system_prompt]
      │
      ├─ subprocess.Popen(cmd, env=env, stdin=PIPE, stdout=PIPE)
      ├─ stdin.write("帮我写一个登录页面")
      ├─ stdin.write_eof()
      │
      │   ─── CLI 内部发 HTTP 请求 ───
      │   POST http://127.0.0.1:8000/proxy/agents/<UUID>/v1/messages
      │   Headers:
      │     x-api-key: agenthub-proxy           ← 占位
      │     anthropic-version: 2023-06-01
      │     content-type: application/json
      │   Body (Anthropic Messages 格式):
      │     {
      │       "model": "deepseek-v4-pro",
      │       "max_tokens": 16000,
      │       "messages": [{"role": "user", "content": "帮我写一个登录页面"}],
      │       "system": "你是 FrontendAgent，前端开发专家...",
      │       "stream": true
      │     }
      │   ──────────────────────────▶
      │
      │   ProxyHandler.handle(agent_id="UUID", path="v1/messages", request):
      │     ├─ agent = agent_repo.get_by_id(UUID)
      │     │   → base_url = "https://api.deepseek.com/anthropic"
      │     │   → api_key_encrypted = "<密文>"
      │     ├─ real_key = decrypt(api_key_encrypted) → "sk-xxx"
      │     ├─ target_url = "https://api.deepseek.com/anthropic/v1/messages"
      │     ├─ forward_headers = {**req.headers, "x-api-key": "sk-xxx"}
      │     │   (替换占位 key 为真实 key)
      │     ├─ httpx.stream("POST", target_url, headers, body)
      │     │        ─────────────────────────────────────▶
      │     │        第三方 API 返回 Anthropic 格式流式响应
      │     │        ◀─────────────────────────────────────
      │     └─ StreamingResponse(upstream.aiter_raw())   ← 字节级透明回传
      │
      │   CLI 收到 Anthropic 格式响应 ← 完全无感知，以为在调 Anthropic 官方 API
      │   ──────────────────────────
      │
      ├─ for line in process.stdout:
      │     event = _parse_line(line)
      │     yield event
      │
      └─ yield DONE
```

### 9.5 场景 C：Anthropic 兼容端点（pass-through）

当 Provider 提供 Anthropic 原生兼容端点时（DeepSeek、Kimi、GLM），代理做**纯透明转发**：

```
CLI 请求 → ProxyHandler:
  │
  │  请求体：Anthropic Messages 格式（Model、Messages、System、Stream 等）
  │  请求头：x-api-key (占位)、anthropic-version、content-type
  │
  ├─ 替换 x-api-key: "agenthub-proxy" → "sk-real-deepseek-key"
  ├─ 过滤 hop-by-hop headers
  ├─ URL 拼接: https://api.deepseek.com/anthropic + /v1/messages
  │
  └─ 原样转发 → 第三方以 Anthropic 格式理解和响应 → 原样回传

请求体和响应体：零改动，字节级透传
```

| Provider | Anthropic 端点 | 鉴权 | 需要协议转换 |
|----------|---------------|------|:---:|
| DeepSeek | `api.deepseek.com/anthropic` | x-api-key | 否 |
| Kimi | `api.moonshot.cn/anthropic` | x-api-key | 否 |
| 智谱 GLM | `open.bigmodel.cn/api/anthropic` | x-api-key | 否 |
| MiniMax | 内置 | x-api-key | 否 |
| Ollama | `localhost:11434` | 无需 | 否 |
| LM Studio | `localhost:1234` | 无需 | 否 |
| OpenAI (GPT-4o) | `api.openai.com/v1` | Bearer | **需要** |
| 百炼 (Qwen) | `dashscope.aliyuncs.com/compatible-mode` | Bearer | **需要** |

### 9.6 场景 D：错误处理

#### Agent 不存在

```
CLI → POST /proxy/agents/nonexistent-id/v1/messages
│
├─ agent_repo.get_by_id("nonexistent-id") → None
└─ Response: 404 {"error": "agent not found"}

CLI stdout:
{"type":"result","subtype":"error_during_execution","is_error":true,...}
→ StreamEvent(ERROR, "Claude CLI 退出码 1: HTTP 404...")
```

#### API Key 未配置

```
agent.api_key_encrypted == "" 或 为空
│
└─ Response: 400 {"error": "agent has no api_key"}

→ 前端提示：Agent 配置缺少 API Key
```

#### 第三方 API 超时

```
httpx.stream() → ReadTimeout (300s)
│
├─ StreamingResponse 中断
├─ CLI 收到不完整响应 → exit code != 0
└─ StreamEvent(ERROR, "Claude CLI 退出码 1: ...")
```

#### 第三方返回错误

```
DeepSeek API → HTTP 401 Unauthorized
│
├─ ProxyHandler: upstream.status_code → StreamingResponse(401, body=error)
├─ CLI 收到 401 → stdout: error result
└─ StreamEvent(ERROR, "Claude CLI 退出码 1: HTTP 401...")

★ 代理不做错误转换 — 上游错误原样透传给 CLI
```

### 9.7 场景 E：后续扩展 — 协议转换

当接入 GPT、Qwen 等不提供 Anthropic 兼容端点的 Provider 时，在 ProxyHandler 中叠加协议转换：

```
CLI 请求 (Anthropic 格式)
│
├─ ProxyHandler:
│   ├─ 判断 api_format == "openai_chat"
│   ├─ transform.anthropic_to_openai_chat(body)
│   │   ├─ system → messages[0] {role:"system", content:"..."}
│   │   ├─ tools[].input_schema → tools[].function.parameters
│   │   └─ content blocks → string content
│   ├─ 转发到 OpenAI API (https://api.openai.com/v1/chat/completions)
│   ├─ transform.openai_chat_to_anthropic(sse_chunks)
│   │   ├─ choices[0].delta.content → content_block_delta text
│   │   ├─ choices[0].delta.tool_calls → content_block_start/delta tool_use
│   │   └─ finish_reason → message_delta stop_reason
│   └─ StreamingResponse(Anthropic SSE 格式)
│
└─ CLI 收到 Anthropic 格式流式响应（无感知）
```

当前阶段不实现：GPT/Qwen 覆盖范围小，Anthropic SSE 和 OpenAI SSE 事件结构差异大，测试矩阵复杂。DeepSeek/Kimi/GLM 的 Anthropic 兼容端点已覆盖主流需求。

### 9.8 代理关键设计决策

| 决策 | 原因 |
|------|------|
| 所有 CLI 流量走代理，不直连 | 鉴权机制不兼容（x-api-key vs Bearer），直连前提不可靠 |
| URL 路径编码 agent_id | 无需自定义 header，CLI 零改动 |
| 字节级透明转发（aiter_raw） | 不解析请求/响应体，对 Anthropic 兼容 Provider 零适配成本 |
| 协议转换后置 | 覆盖 80%+ Provider（DeepSeek/Kimi/GLM），GPT/Qwen ROI 低 |
| 代理与 AgentHub 同进程 | 延迟 <1ms，无需额外服务 |
| API Key 占位 → 代理注入 | API Key 只在代理内存中短暂存在为明文,落库永远是密文 |

---

## 十、设计决策速查表

| 决策 | 理由 |
|------|------|
| 私聊首条：`--session-id`（新建） | 初始化 CLI 会话 |
| 私聊后续：`--resume` + 只传当前消息 | CLI 自己管历史，AgentHub 不传全量 messages |
| 身份信息走 `--system-prompt` | CLI 原生支持，不污染 user prompt |
| 其他上下文（peer/capability）注入 prompt 文本 | 非身份信息，拼入 stdin 传入 |
| 群聊 Agent：`--resume` + system_prompt 注入 watermark delta | 自身对话由 CLI session 管理，他人发言走 system_prompt（cache 友好） |
| Coordinator：API 模式 `chat_structured` | 需要可靠的结构化 JSON 输出 |
| **群聊讨论：Selector 串行轮转**（v1.5 取代旧并行广播） | LLM 成本可控、对话顺序可观测、协作语义清晰 |
| **Selector 三层路由（@mention → capability → LLM）** | 程序优先于 LLM，多数轮次零 LLM 决策 |
| **Selector LLM：DeepSeek V4 Flash 默认 + tool_use 强制 JSON** | 廉价 + 可靠结构化输出，prompt 长度有三层裁剪 |
| **讨论防循环：MAX_ROUND(3) + Selector DONE + 用户新消息中断** | 三重保险防 Agent 互相聊死 |
| **ContextBuilder：watermark 增量注入** | 每 Agent 跟踪「上次发言点」，仅注入 delta 而非全量 |
| **群聊 messages 仅含 trigger 单条** | 历史通过 system_prompt 的 delta_block 注入，CLI session 自管自身 turn |
| session_id 直接复用 AgentHub session UUID | 无需额外映射层，CLI 原生支持 UUID |
| 超时保留 session / 崩溃删除 session | 超时可能是正常任务过大，崩溃=状态损坏不可恢复 |
| WS 断开立即 kill，不保留进程 | --resume 已保证可恢复 |
| 讨论中 Agent 异常即终止循环 | 单 Agent 失败影响整体观感，宁可显式报错 |
| 群聊 session_id 格式：`{group_session_id}:{agent_id}` | 同一群聊中每个 Agent 独立 CLI sqlite，互不覆盖 |
| 权限：预设 acceptEdits + 检测 permission_denials | --print 模式无交互式提示，阻断后通知用户重试 |
| **代理**：所有 CLI 流量走内置代理 | 鉴权不兼容（x-api-key vs Bearer），统一适配 |
| **代理**：URL 路径编码 agent_id | 无需自定义 header，CLI 零改动 |
| **代理**：字节级透明转发（aiter_raw） | 覆盖 Anthropic 兼容 Provider，零适配成本 |
| **代理**：协议转换后置 | DeepSeek/Kimi/GLM 已覆盖 80% 场景 |
| **代理**：API Key 占位 → 代理注入 | 明文只在代理内存中短暂存在，落库永远是密文 |

---

## 十一、相关文档

| 文档 | 内容 |
|------|------|
| `ADR-01-cli-first-pivot.md` | 架构决策：API→CLI 重心转移 |
| `PRD_AgentHub_v4_统一方案.md` §三 | 接口签名 + 双轨定义 |
| `DOC-15-claude-adapter-design.md` | 双轨架构详细设计 |
| `DOC-17-context-injection-problem.md` | CLI 上下文注入问题分析 |
| `CLI多模型代理方案.md` | CLI 多模型代理方案设计（含 ProxyHandler + 路由 + 鉴权适配） |
| `cc-haha-multi-model-analysis.md` | cc-haha 多模型支持机制深度分析 |
| `docs/design/group-chat_群聊功能设计方案.md` | 群聊总体设计（watermark + 增量注入） |
| `docs/design/group-chat-discussion-mode_群聊讨论模式设计方案.md` | 讨论模式设计（Selector 三层路由 + 防循环） |
| `docs/design/group-chat-implementation-plan_群聊实施计划.md` | 群聊分阶段实施计划 |
