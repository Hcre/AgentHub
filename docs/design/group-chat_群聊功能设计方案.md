# 群聊功能设计方案 — @路由模式

> 状态：设计阶段 | 日期：2026-05-25（2026-05-26 增量注入方案更新） | 基于 `docs/explore/group-chat-boundary-and-dependencies.md` 讨论结论
>
> **2026-05-25 代码核验修订**：对照实际代码（`chat_service.py` / `memory_l1.py` / `protocol.py` / `claude_code_runtime.py`）发现多处设计与适配器实现不符，已修正 C1/C2/C3/H1/H2/M2。
>
> **2026-05-26 增量注入方案更新**：M1（system_prompt + `--resume` 双份问题）+ C2（L1 key 一致性）+ H3（三套存储职责重叠）三项一并解决，方案见 §3.4。

### 审查修订记录

| 编号 | 问题 | 处置 |
|------|------|------|
| C1 | CLI Runtime 只取最后一条 user 消息 + system_prompt，`messages` 窗口被丢弃（`claude_code_runtime.py:179`），原设计把群聊历史放进 `messages` 窗口对 CLI 无效 | 已修正 §3.1：群聊上下文只能经 system_prompt 注入；增量注入机制见 §3.4 |
| C2 | §3.1 step1 写 `l1:{session_id}`，step3 读 `l1:{session_id}:{agent_id}`，key 不一致 → per-agent 窗口永远收不到用户消息 | 已解决（2026-05-26）：L1 维持 `l1:{session_id}` 单维度作为「群全貌热缓存」；per-agent 进度由独立 watermark 跟踪，见 §3.4 |
| C3 | 并发多 Agent 流式无发言人归属（`StreamEvent` 无 agent 字段）；`send_and_stream` 是单流，`gather` 不能直接合流 | 已修正：V1 改串行执行；流式事件须带 `sender_agent_id`；并发合流留 M3 |
| H1 | 与 boundary §4.2 冲突：本文档 V1 多 @ 并发，boundary V1 单 @ 串行 spawn | 已统一为 boundary 口径：V1 单/串行，多 Agent 并发归 M3 |
| H2 | §3.2 称「不引入新接口/新文件」不实：per-agent CLI session 需 SessionManager（`claude_code_runtime.py:62` 直接用 `session_id` 当 CLI key，群聊会互相覆盖）；L1 改 per-agent 是破坏性接口变更 | 已修正 §3.2 改动点与工期 |
| M2 | 工期 ~4h 偏低 | 已修正为骨架 ~7h（对齐 boundary §6），不含并发合流 |
| M1 | system_prompt 反复注入增长的群历史与 `--resume` 是否冲突、是否双份 | 已解决（2026-05-26）：sqlite 只含 Agent 自己的对话轮次；system_prompt 只注入「他人发言增量」，两层无重叠。详见 §3.4 |
| H3 | PG / per-agent L1 / CLI sqlite 三套存储职责重叠，per-agent L1 存废 | 已解决（2026-05-26）：PG = 全量真源；L1 = 群全貌热缓存（不切 per-agent）；CLI sqlite = 单 Agent 自言自语；新增 watermark = 每 Agent 进度指针。四者职责无重叠，见 §3.4 |

## 一、范围

本期只实现 **@ 路由模式**（L2），不实现讨论模式（L3/L4）。

```
群组正常对话
├── L1: 消息广播（无 AI 回复）         ← 不单独实现，并入 L2
├── L2: @Agent 直接路由               ← 本期实现
├── L3: @协调者 任务分解              ← M3
└── L4: 多 Agent 并行执行（讨论模式）   ← M3
```

## 二、核心决策

### 2.1 @ 路由 vs 讨论模式 — 共享流水线，仅 Router 不同

两种模式共用同一套 `send_group_message()` 流水线，唯一的差异点在 Router 这一步：

```
ChatService.send_group_message()
  ├─ Pipeline   ← 共享：持久化 + L1 + WS 广播
  ├─ Router     ← 唯一差异：
  │    @ 模式： 正则匹配 @xxx → Agent 表 lookup
  │    讨论模式：遍历群成员 → LLM/规则打分 → 判断谁该回
  │    ↓ 返回 list[TargetAgent]，下游不关心怎么来的
  └─ Executor   ← 共享：对每个 TargetAgent 构造上下文 → adapter.stream()
```

Router 是可替换的一步，不是两个独立流程。V1 实现 @ Router，M3 换成讨论 Router，其余 ~80% 代码不动。

### 2.2 上下文管理边界 — AgentHub 决定「看什么」，CLI 决定「怎么想」

| 能力 | 谁管 | 为什么 |
|------|------|--------|
| **群聊消息持久化** | AgentHub（PG messages 表） | 群聊消息是共享资产，不能散落在各 CLI 的 sqlite |
| **Agent 看什么上下文** | AgentHub（组装 system prompt + 群聊历史窗口） | CLI 不知道群里有谁、前面说了什么 |
| **消息路由（@谁了）** | AgentHub（解析 mentions） | 只有 AgentHub 知道全体成员 |
| **L1 滑动窗口** | AgentHub（Redis） | 统一近程记忆，CLI 无感知 |
| **System prompt 执行** | CLI | AgentHub 只管传什么，不管怎么用 |
| **工具执行** | CLI Harness | 读文件/跑命令/浏览器操作，AgentHub 不拦截 |
| **响应生成** | CLI 内部 | 模型调用/thinking/tool call 循环 |

### 2.3 Agent 响应不循环触发

Agent 的回复只做两件事：落库 + WS 广播到 UI。**不会再次进入 Router 触发新一轮 Agent 调用。** 只有用户发送的新消息才会触发路由。

```
用户: "@AgentA 帮我看看"
  Router → targets = [AgentA]
  AgentA 回复 → persist + WS 广播到 UI → 结束
  ❌ AgentA 的回复不会传给 AgentB 或再次触发 Router
```

### 2.4 消息流 — 一个群对应一个 Session

群聊消息落在一个 `Session(type='group', group_id=group.id)` 下。消息表已有 `sender_agent_id`、`mentions` 字段，天然支持群聊。

## 三、@ 路由流水线

### 3.1 完整流程

```
用户发送群聊消息 "@AgentA 排查一下 @AgentB 给建议"
  │
  ├─ 1. Pipeline
  │    persist Message(session_id, content, mentions=["AgentA","AgentB"]) → PG
  │    L1 append (key=l1:{session_id}，群全貌热缓存，所有人共享一份，最近 N 条)
  │    WS broadcast 到群内所有在线客户端
  │
  ├─ 2. Router.resolve(mentions=[], content=message)
  │    解析 @mention → lookup Agent by name → [AgentA (UUID), AgentB (UUID)]
  │    如果无 @mention → 空列表（当前暂不兜底到协调者）
  │
  ├─ 3. 对每个 TargetAgent 串行执行（V1 不并发；并发流式合流留 M3，见审查 H1/C3）:
  │    │
  │    ├─ ContextBuilder.build_for_agent(group, agent)
  │    │   ↳ 详细机制见 §3.4「上下文注入：增量方案」
  │    │   ↳ 核心：watermark 跟踪该 Agent「上次接触到第几条消息」
  │    │       → 只注入「自上次后他人新发言」(delta)，不重发已看过的
  │    │       → CLI sqlite (--resume) 自动管 Agent 自己的对话轮次
  │    │       → 两层无重叠，解决 M1 双份问题
  │    │
  │    ├─ 组装 system prompt（增量注入示例）：
  │    │   """
  │    │   {agent.persona}                      ← 稳定前缀，prompt cache 友好
  │    │
  │    │   你正在群聊「{group.name}」中回复消息。群聊其他成员：
  │    │   - AgentB (角色: 后端专家)
  │    │   - AgentC (角色: 文案)
  │    │
  │    │   自你上次发言后的新消息（共 3 条）：    ← 动态后缀，仅增量
  │    │   ---
  │    │   AgentB: API 返回 500
  │    │   AgentC: 是不是数据库挂了
  │    │   用户 (@AgentA): 你来看看前端有没有问题
  │    │   ---
  │    │   """
  │    │
  │    ├─ AgentRequest:
  │    │   messages: ⚠️ CLI Runtime 只取最后一条 user 消息，窗口被丢弃（审查 C1）
  │    │   system_prompt: 持久前缀 + delta 注入（见 §3.4）
  │    │   memory: MemoryContext(l1_working=L1 群全貌热缓存)
  │    │
  │    └─ adapter.stream(request) → 流式返回 → 推进 watermark（§3.4 §6）
  │
  └─ 4. 收集响应
       每个 Agent 的回复 → persist Message(sender_agent_id=agent.id) → PG
                        → L1 append (同步进群全貌缓存)
                        → 推进该 Agent 的 watermark 到自己刚发的 message_id
       → WS broadcast 到群内客户端
       ⚠️ 流式事件（StreamingStarted/TEXT）须带 sender_agent_id，前端才能标注气泡（审查 C3）
```

### 3.2 当前代码现状与改动点

当前 `chat_service.py:175` `_resolve_target_agent()` 直接抛错：`"MVP 仅支持私聊单 Agent"`。需要改：

| 改什么 | 在哪 | 做什么 | 估时 |
|--------|------|------|------|
| `_resolve_target_agent` | `chat_service.py:175` | 删掉抛错 → 解析 `mentions` → 返回 `list[UUID]`，无 mention 时返回空 | 0.5h |
| `send_and_stream` | `chat_service.py:62` | 串行 `for target in targets` 逐个流式（V1 不并发，见 C3）；每个 target 之间推进 watermark | 1h |
| **新建 `ContextBuilder`** | `application/services/context_builder.py`（新文件） | `build_for_agent(group, agent, trigger)` → 取 watermark + 算 delta + 拼 system_prompt（§3.4.2） | 2h |
| **新建 `WatermarkStore`** | `infrastructure/cache/watermark_store.py`（新文件） | Redis 实现 `wm:{group_id}:{agent_id} → message_id`，TTL 7 天（对齐 SessionStore） | 1h |
| `StreamEvent` 加发言人 | `domain/llm/protocol.py` | `sender_agent_id: UUID \| None` 字段（C3）；前端按此标注气泡 | 0.5h |
| CLI session key | `claude_code_runtime.py:62` 附近 | 群聊场景下 key = `{session_id}:{agent_id}`，避免 Agent 间互相覆盖 | 0.5h |
| migration | `alembic/versions/xxx_*.py` | 无（watermark 在 Redis，不涉及 PG schema） | 0h |
| 单元测试 | `tests/unit/test_context_builder.py` 等 | delta 计算 / watermark 推进 / 边界条件覆盖 | 1.5h |

**L1 接口不变**：`L1MemoryStore` 维持 `l1:{session_id}` 单维度，作为群全貌热缓存。不切 per-agent（C2 原以为要切，H3 讨论后判定不必要）。

**总估时**：~7h（不含并发流式合流，留 M3）。对齐 boundary §6 工期。

### 3.3 为什么不对 Agent 过滤上下文

Agent 需要看到群聊全貌才能正确回复：

```
(正确) Agent 看到全部:
  AgentB: 按钮没反应，network 看是 500     ← 前因
  用户 (@AgentA): 你来排查                  ← @ 自己
Agent 回复: 500 说明后端报错，我先检查前端请求参数

(错误) 只给 @ 自己的消息:
  用户 (@AgentA): 你来排查
Agent 回复: 排查什么？我不知道上下文
```

「看全貌」≠「每次重发全量」。Agent 第 N 次被路由时，前 N-1 次看过的消息他已经知道。**真正需要塞进 system_prompt 的，是自上次接触后他人新发言的增量。** 见 §3.4。

### 3.4 上下文注入：增量方案（delta injection）

**问题**：每次路由 Agent 时把「最近 N 条群聊」全量塞进 system_prompt，会有两个问题：

1. token 成本随群聊历史规模线性增长（M1）
2. 与 CLI `--resume` 加载的 sqlite 历史可能重复（M1）

**方案**：只注入「自该 Agent 上次接触群聊后的新发言」。

#### 3.4.1 存储职责划分（解决 H3）

| 存储 | 内容 | 写入时机 | 读取场景 |
|------|------|---------|---------|
| PG `messages` 表 | 全量真源，所有发言永久持久化 | 每条消息落库 | 增量 fallback、审计、UI 历史回看 |
| Redis L1 `l1:{session_id}` | 群全貌热缓存，最近 15-20 条（**单维度，不切 per-agent**） | 每条消息同步 append | 快速取最近消息、UI 实时渲染 |
| CLI sqlite (`--resume`) | 单 Agent 自己的对话轮次：`[触发消息, Agent 答, 触发消息, Agent 答, …]` | CLI 自管 | `claude --resume {key}` 自动加载 |
| Redis `wm:{group}:{agent}` | 每 Agent 进度指针：`last_seen_message_id` | Agent 回复成功后推进 | ContextBuilder 计算 delta |

**四者职责无重叠**：
- PG 是真源
- L1 是 PG 最近段的 cache（性能优化，不是真源）
- CLI sqlite 只含 Agent 自己说过的话（不含他人）
- watermark 只是指针（不存消息内容）

#### 3.4.2 Delta 计算流程

```python
# ContextBuilder.build_for_agent(group, agent, trigger_message)

# 1. 取该 Agent 的水位
wm: UUID | None = await wm_store.get(group.id, agent.id)

# 2. 算 delta
if wm is None:
    # 首次接触：给一段种子历史（默认 N=20，PRD 热上下文窗口）
    delta = await msg_repo.recent(group.session_id, limit=settings.l1_window_size)
else:
    # 优先走 L1 热缓存
    window = await l1.get_window(group.session_id)
    if window and window[0].id <= wm:
        # wm 落在窗口内 → 从 L1 过滤即可
        delta = [m for m in window if m.id > wm]
    else:
        # wm 在窗口外（Agent 沉默很久） → 回退 PG
        delta = await msg_repo.after(group.session_id, wm)

# 3. delta 上限保护
if len(delta) > MAX_DELTA:  # 默认 50
    summary_placeholder = f"[省略 {len(delta) - MAX_DELTA} 条更早消息]"
    delta = [summary_placeholder] + delta[-MAX_DELTA:]
    # L2 摘要落地后此处接 L2.summarize() 替代占位符（非本期）

# 4. 拼装 system prompt
return SystemPrompt(
    stable_prefix=agent.persona + format_members(group),  # cache 友好
    dynamic_delta=format_delta(delta),                     # 仅增量
    trigger=trigger_message.content,
)
```

#### 3.4.3 Watermark 推进规则

**关键不变量**：watermark 必须在 Agent 回复成功后推进，且要覆盖到「Agent 自己刚发的 message_id」。

```python
async def route_to_agent(group, agent, trigger):
    sys_prompt = await ctx_builder.build_for_agent(group, agent, trigger)
    
    # 记录本次注入到哪条（用于失败重试 + 后续推进基准）
    injection_high_water = trigger.id
    
    response_msg = await adapter.stream_and_persist(request)  # 可能失败
    
    if response_msg.ok:
        # 推进到 Agent 自己刚发的消息（≥ injection_high_water）
        await wm_store.set(group.id, agent.id, response_msg.id)
    # 失败不推进，下次重试拿到相同 delta
```

**为什么推进到「自己刚发的」而非「注入的最后一条」**：Agent 自己的发言也算「已看过」，下次再被路由时不应该再把自己上轮的话塞进 delta。

#### 3.4.4 与 CLI sqlite 不冲突（解决 M1）

两层「对话链」完全互补：

| 层 | 维护方 | 内容 | 示例（AgentA 视角） |
|----|--------|------|---------------------|
| CLI sqlite (`--resume`) | CLI 自管 | AgentA 自己的对话轮次 | `[trigger#1, A答#1, trigger#2, A答#2, ...]` |
| system_prompt delta | AgentHub 注入 | 其他人在 AgentA 沉默期间说的话 | `[B 说的, C 说的, 用户说的]` |

**两层在 token 层面不重叠**：
- sqlite 里没有 B/C 的发言（CLI 看不到群里别人）
- delta 里没有 A 自己说的话（watermark 推过 A 的回复）

**M1 双份问题消失**：因为根本没有重叠机会。

#### 3.4.5 边界条件

| 场景 | 处理 |
|------|------|
| Agent 首次接触群聊（wm 空） | 给 N=20 条种子历史 |
| Agent 沉默很久，delta 超 50 条 | 截断 + 占位符；L2 摘要落地后替换 |
| Agent 被移除群 | 删除 watermark + 清理 CLI sqlite |
| Agent 重新加入群 | watermark 空，走首次接触路径 |
| Agent persona 修改 | watermark 无需重置（增量逻辑与 persona 内容正交） |
| Redis watermark 丢失 | 退化为首次接触（再给 N 条种子），无数据丢失 |
| 群组归档/删除 | 级联清理 watermark + L1 + 关联 CLI sqlite |

#### 3.4.6 收益与代价

**收益**：
- token 成本随增量（而非历史）增长 → 长群仍便宜
- prompt cache 命中率最大化：`agent.persona + 成员列表` 稳定不变，可被 Anthropic 服务端 cache
- M1 / C2 / H3 一并解决（见审查表）

**代价**：
- 新增 1 张 Redis key family（`wm:*`）+ 1 个 Repository
- ContextBuilder 抽象层（之前是 ChatService 内联拼 prompt）
- 推进 watermark 的事务管理（必须在持久化 Agent 回复成功后）

## 四、CLI Session 隔离

### 4.1 同群不同 Agent，会话分开

```
L1 热缓存（不切 per-agent，群全貌共享）:
  私聊:  l1:{session_id}
  群聊:  l1:{session_id}              ← 同私聊，单维度

Watermark（每 Agent 进度指针，见 §3.4）:
  群聊:  wm:{group_id}:{agent_id} → last_seen_message_id

CLI session key（每 Agent 独立 sqlite）:
  私聊:  {session_id}
  群聊:  {session_id}:{agent_id}      ← 避免群内 Agent 互相覆盖
```

3 个群组 × 5 个 Agent = 15 个 CLI session。每个 ~几百 KB sqlite，存储成本可忽略。

### 4.2 级联清理

```python
# Agent 从群里移除
await wm_store.delete(group_id, agent_id)
await cli_session_manager.cleanup(f"{session_id}:{agent_id}")

# Agent 被全局删除
await wm_store.delete_by_agent(agent_id)            # 该 Agent 在所有群的 watermark
await cli_session_manager.cleanup_by_agent(agent_id)

# 群组被删除
await wm_store.delete_by_group(group_id)            # 群内所有 Agent 的 watermark
await l1_store.clear(group.session_id)              # 群全貌缓存
await cli_session_manager.cleanup_by_session(session_id)
```

L1 单维度后，「Agent 被删除」**不需要清 L1**（L1 记的是群消息，不是 Agent 私有数据）。只有「群被删除」才清 L1。

## 五、前端交互

### 5.1 @ 输入

- 输入框键入 `@` → 弹出群成员下拉列表
- 支持继续输入过滤（按名匹配）
- 回车或点击选中 → `@AgentName` 插入消息文本
- 发送时 `mentions: ["AgentName"]` 随消息传给后端

复刻现有 `src/frontend/src/components/chat/ChatView.tsx` 的输入区，加 `@` 触发逻辑。

### 5.2 消息渲染

- 已有 `sender_agent_id` 字段，消息气泡加 `Agent 名 + 颜色标记` 区分发言人
- 群聊视图复用 ChatView，数据源从 `groupStore.messagesByGroup[id]` 取

## 六、边界条件

| 场景 | 处理 |
|------|------|
| 消息无 @mention | Router 返回空列表 → 无 Agent 回复 → 消息只广播到 UI |
| @ 的 Agent 不存在 | 跳过该 mention（不报错），对存在的 Agent 正常路由 |
| @ 的 Agent 离线（status=offline） | 照常路由（离线=未登录，不影响 CLI 执行） |
| 并发中某 Agent 调用失败 | 不影响其他 Agent，失败结果单独处理 |
| 群组无成员 | Router 返回空列表 |
| 空消息（纯空格） | 422 |

## 七、后续: 讨论模式（M3）

讨论模式在 @ 路由基础上，只替换 Router 这一步：

```python
# @ 模式 Router (V1)
async def resolve(self, mentions, content, group):
    return [await agent_repo.get_by_name(m) for m in mentions]

# 讨论模式 Router (M3)
async def resolve(self, mentions, content, group):
    targets = []
    for member in group.members:
        if await self._should_respond(member, content, group):
            targets.append(member)
    return targets  # 可能 0~N 个
```

`_should_respond()` 的实现选项：
- A) 规则打分：关键词匹配 + Agent 角色标签
- B) LLM 判断：每条消息让一个轻量 LLM 判断"谁该回"
- C) 协调者调度：由协调者 Agent 决定分配给谁

讨论模式要解决的额外问题：
- **上下文过时**：Agent A 回复快，Agent B 回复慢 → B 的回复基于"A 还没说话"的旧上下文 → 可能矛盾
- **需要回复确认**：讨论模式下 Agent 回复后，是否需要用户确认才生效？
- 这些留到 M3 阶段单独设计

## 八、参考

| 文档 | 内容 |
|------|------|
| `docs/explore/group-chat-boundary-and-dependencies.md` | 群聊依赖分析与模块边界 |
| `docs/design/group-creation_群组创建功能设计方案.md` | 群组创建（前置功能，已实现） |
| `docs/specs/01-architecture_架构定义.md` | 五层架构 |
| `docs/specs/04-commands_命令接口.md` | Session 创建与消息发送 API |
