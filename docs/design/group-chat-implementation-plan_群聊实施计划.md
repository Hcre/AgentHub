# 群聊实施计划 — V1 @ 路由 + 讨论模式

> 状态：实施前审查 | 日期：2026-05-26
>
> 基于设计文档：
> - `docs/design/group-chat_群聊功能设计方案.md` — V1 @ 路由 + 增量注入 §3.4
> - `docs/design/group-chat-discussion-mode_群聊讨论模式设计方案.md` — 讨论模式 + Selector
> - `docs/explore/group-chat-boundary-and-dependencies.md` — 模块边界与接口契约

## 一、范围

### 包含

- V1 @ 路由（单 @ / 多 @ 串行）
- 讨论模式（DiscussionOrchestrator + Selector + 回合循环）
- Selector Bypass（Agent 主动 @ 接力）
- 增量上下文注入（ContextBuilder + Watermark）
- `GROUP_CHAT_CONTRACT` 行为契约注入

### 不包含

- 协调者 / 任务分解 / DAG（roadmap 3.2 / 3.4 / 3.5 / 3.6 / 3.7 全部推迟）
- L2 摘要 / L3 Pin 记忆 / L4 RAG
- 角色扮演 / 自治广播 模式（枚举位预留，不实现）
- CLI 保活池 / prompt caching 优化
- 多 Agent 并发流式（V1 串行，M4 再优化）
- 自建 Agent 流程（roadmap 4.3，M4）

## 二、实施分层与顺序

按依赖反向排序（底层先做）。

### Phase 1：协议层改造（1h）

- `domain/llm/protocol.py`
  - `StreamEvent` 加 `sender_agent_id: UUID | None`
  - `AgentRequest` 加 `agent_id: UUID | None`、`group_id: UUID | None`、`is_group_chat: bool`

### Phase 2：基础设施层（2h）

- **新增** `infrastructure/cache/watermark_store.py`
  - `WatermarkStore` ABC + `RedisWatermarkStore` 实现
  - Key：`wm:{group_id}:{agent_id} → message_id`（string），TTL 7 天（对齐 SessionStore）
  - 方法：`get / set / delete / delete_by_group / delete_by_agent`

- `infrastructure/llm/claude_code_runtime.py:62` 改造
  - 私聊：`session_key = str(request.session_id)`
  - 群聊：`session_key = f"{request.session_id}:{request.agent_id}"`
  - 依据 `request.is_group_chat` 区分

### Phase 3：应用层 — 共用组件（4h）

- **新增** `application/services/prompt_templates.py`
  - `GROUP_CHAT_CONTRACT` 常量（见 §四）
  - `format_members(group) -> str` 辅助函数

- **新增** `application/services/context_builder.py`
  - `ContextBuilder.build_for_agent(group, agent, trigger) -> AgentRequest`
    1. 取 watermark
    2. 算 delta（L1 优先 / PG 回退 / 超 `MAX_DELTA` 截断）
    3. 拼 stable_prefix = `persona + GROUP_CHAT_CONTRACT + members`
    4. 返回 `AgentRequest`

### Phase 4：V1 @ 路由实施（3h）

- `application/services/chat_service.py`
  - `_resolve_target_agent`：删抛错，解析 `mentions` → `list[UUID]`
  - `send_and_stream`：串行 for-loop 处理 targets
    - 每个 target：
      - `ctx_builder.build_for_agent()` → `AgentRequest`
      - `adapter.stream()` → 流式 yield
      - 回复完成 → persist + `watermark.set(group.id, target.id, response.message_id)`
  - 死群兜底：targets 为空 → 仅广播用户消息，不调 Agent（**静默**）

### Phase 5：Selector（4h）

- **新增** `application/services/selector.py`
  - `SelectorDecision` dataclass：`next_agent_id: UUID | None`、`done: bool`
  - `Selector.pick(group, history, last_message) -> SelectorDecision`
    1. `@mention` 检测（含 Agent 自治 @，Bypass 路径，零 LLM）
    2. `capability_tags` 关键词匹配（零 LLM）
    3. Anthropic API Haiku 直调（JSON 强制 schema）
       - `system = SELECTOR_PROMPT_TEMPLATE`
       - `messages = [history_summary]`
       - 用 `tool_use` 强制返回 `{next: uuid} | {done: true}`
    4. 失败降级 → `done = True`（不阻塞用户）

### Phase 6：DiscussionOrchestrator（4h）

- **新增** `application/services/discussion_orchestrator.py`
  - `run_discussion(group, trigger_message)` 异步生成器
    ```
    round = 0
    while round < MAX_ROUND:
        decision = await selector.pick(group, recent_history)
        if decision.done:
            break
        target = await agent_repo.get(decision.next_agent_id)
        req = await ctx_builder.build_for_agent(group, target, trigger_message)
        response_msg = await self._stream_and_persist(target, req)
        await watermark.set(group.id, target.id, response_msg.id)
        round += 1
    ```
  - 人在环中断：由 `ChatService` 在收到新用户消息时取消此 task

- `ChatService.send_and_stream` 顶层 dispatch 分支：
  - `mentions != []` → V1 串行
  - `mentions == [] && group.dispatch_mode == DISCUSSION` → `run_discussion`
  - 其他 → 静默

### Phase 7：协议补丁（1h）

- 配合 Phase 2 CLI session key 改造，确认 `AgentRequest` 在所有调用点正确传入 `is_group_chat`、`agent_id`、`group_id`

### Phase 8：前端（5h）

- `frontend/src/components/chat/ChatView.tsx`
  - 气泡按 `sender_agent_id` 分色渲染
  - `@` 输入下拉（键入 `@` 弹群成员列表，按名过滤）
- `frontend/src/stores/groupStore.ts`
  - `messagesByGroup[id]` 数据通道
- （可选）Selector 评估期间 "Agent 正在思考" 占位

### Phase 9：测试（5h）

- 单元测试
  - `ContextBuilder`：delta 计算 / 边界条件 / watermark 推进
  - `Selector`：@ 命中 / 关键词命中 / LLM 决策 / DONE / 失败降级
  - `DiscussionOrchestrator`：回合循环 / max_round 兜底 / 人在环中断
- 集成测试
  - 真群组建 → @ 路由跑通 → 讨论模式跑通

**总工时：~29h（约 4 个工作日）**

## 三、关键数据流

### V1 @ 路由

```
用户 "@AgentA 排查 @AgentB 给建议"
  → Pipeline (PG + L1 + WS broadcast)
  → ChatService.dispatch
  → mentions != [] → 走 V1
  → for target in [A, B]:
      ContextBuilder.build_for_agent(group, target, trigger)
      adapter.stream() → 流式
      persist + watermark.set
  → 结束
```

### 讨论模式

```
用户 "大家讨论一下后端架构"
  → Pipeline
  → ChatService.dispatch
  → mentions == [] && dispatch_mode == DISCUSSION
  → DiscussionOrchestrator.run_discussion
      round=0:
        Selector.pick → AgentA
        ContextBuilder + stream A
        A 回复中带 "@AgentB 你那边的想法"
        watermark.set(A)
      round=1:
        Selector.pick → Bypass 命中 @AgentB
        stream B
        watermark.set(B)
      round=2:
        Selector.pick → LLM 评估 → DONE
        break
```

## 四、`GROUP_CHAT_CONTRACT` 初版

```
你正在多 Agent 群聊中协作。请遵守以下行为约定：

1. 主动 @ 接力：如果你的回复需要某位成员补充、确认或反驳，
   直接在回复末尾 @ 该成员（如 "@AgentB 你怎么看"）。
   这能让对话自然流转，无需等待外部调度。

2. 简洁优先：不要复述其他成员已说过的内容。
   如无新信息可贡献，可以简短承接或保持沉默。

3. 角色聚焦：发挥你的角色优势，不要越界回答其他成员更擅长的领域。
```

注入位置：`ContextBuilder.build_for_agent` 拼装 stable_prefix 时（`persona` 之后、`members` 之前）。

私聊场景跳过此契约。

## 五、配置与默认值

| 参数 | 默认 | 位置 |
|------|------|------|
| `l1_window_size` | 20 | settings（已存在） |
| `MAX_DELTA` | 50 | settings（新增） |
| `MAX_ROUND` | 3 | settings（新增，本期硬编码；M4 移群组配置） |
| `selector_model` | `claude-haiku-4-5` | settings（新增） |
| `watermark_ttl_seconds` | 604800（7 天） | settings（新增） |
| `dispatch_mode_default` | `AT_ROUTING` | 群组建群时的初值 |

## 六、决策记录

| # | 决策点 | 选定方案 | 备选与放弃理由 |
|---|--------|--------|--------------|
| 1 | 死群兜底 | **静默** | 「选首位 Agent 强制回复」会强行点名，不自然；「兜底协调者」本期无协调者 |
| 2 | `MAX_ROUND` | **3** | 4 容易绕圈；2 太短不足以多视角讨论 |
| 3 | 实施范围 | **V1 + 讨论模式** | 仅 V1 缺多轮反应；仅讨论模式无 @ 基础 |
| 4 | Selector 模型 | **Haiku 4.5** | Sonnet 太贵；选人不需要深度推理 |
| 5 | Selector 调用方式 | **Anthropic API 直调（非 CLI）** | CLI 启动成本高；选人无需 tool use |
| 6 | Watermark 存储 | **Redis** | PG 也可但 Redis 原子 + TTL 更合适，丢失影响小 |
| 7 | L1 是否切 per-agent | **否，维持单维度** | 切 per-agent 会与 PG/sqlite 职责重叠（H3） |
| 8 | 角色扮演 / 自治广播 | **预留枚举位，不实施** | 独立产品线，需要持久角色记忆 / Agent 自决契约 |

## 七、风险与回滚

| 风险 | 应对 |
|------|------|
| Selector LLM 调用频繁，API 成本超预期 | Bypass 路径降低 30-50% 调用；监控调用数，异常时降级到「无 @ 即静默」 |
| 讨论循环 `max_round` 兜底失效 | 三层防线（DONE / max_round / 人在环）+ task cancellation 兜底 |
| Watermark Redis 丢失 → 全员退化首次接触 | 影响小（只是多注入种子历史），无数据丢失；不需特殊回滚 |
| Agent 不遵循 @ 接力契约 | 实测调 `GROUP_CHAT_CONTRACT` 措辞；最差情况退化为 100% Selector 驱动，仍能跑 |
| 前端 `sender_agent_id` 渲染错乱 | 不影响后端逻辑，可单独 hotfix |

**整体回滚**：任何 Phase 失败可独立回退。V1 @ 路由跑通后讨论模式可暂时禁用（`dispatch_mode` 全设 `AT_ROUTING`），不影响群聊基本可用性。

## 八、实施期间的协同

- 每完成一个 Phase，在 `.agenthub/worklogs/STATUS.md` 更新进度
- 实施完成后：
  - 更新 `spec/roadmap_开发路线图.md` M3 章节，标注「3.2 / 3.4-3.7 推迟」
  - `group-chat-discussion-mode_*.md` 文档头部标签从 M3 改为「V1 同期实施，M3 协调者部分推迟」
  - 关闭 V1 设计文档审查表中 M1 / C2 / H3 三项

## 九、参考

| 文档 | 内容 |
|------|------|
| `group-chat_群聊功能设计方案.md` | V1 @ 路由 + 增量注入（§3.4） |
| `group-chat-discussion-mode_群聊讨论模式设计方案.md` | Selector 选人 / 防循环 / Bypass / 模式预留 |
| `group-chat-boundary-and-dependencies.md` | 模块边界与接口契约 |
| `spec/roadmap_开发路线图.md` | 原始 M3 任务清单 |
| `spec/architecture_架构定义.md` | 五层架构 + 上下文三层体系 |
