# 群聊讨论模式设计方案 — M3

> 状态：设计阶段 | 日期：2026-05-25 | 基于 `docs/explore/group-chat-discussion-mode-options.md` 调研结论的抉择
>
> 前置：V1 @路由模式见 `docs/design/group-chat_群聊功能设计方案.md`；模块边界见 `docs/explore/group-chat-boundary-and-dependencies.md`

## 一、核心判断

调研文档把讨论模式拆成三个独立问题分别投票（上下文过时 / 谁该回 / 是否通知其他 Agent），这是误导。**三者是同一个决策的三个切面**——先定讨论模型，三个问题的答案自动唯一。分别投票还会诱导出互相矛盾的组合（如"放任并发"+"回合内广播"逻辑上冲突）。

两个前提认知：

1. **V1（@路由）不存在这三个问题**——多个 @mention 各自独立回复用户、互不反应，无并发歧义。三个问题只在 M3 讨论模式（Agent 互相反应）才出现。本文档只谈 M3。
2. **AgentHub 的讨论模式是「人在环 IM 群聊」**，不是全自主任务编排。这一点决定了大量业界顾虑不适用（见 §三）。

## 二、抉择结论：流式回合制 + 单选择器循环 + 人在环

```
send_group_message(讨论模式):
  history = 群聊近 N 条消息（共享）
  for round in range(max_round=3):              # 硬上限，防循环
    next = Selector.pick(history, members)       # 1 次廉价 LLM 调用
    if next is DONE: break                        # 选择器同时负责判终止
    resp = adapter.stream(ctx_builder.build(next, history))  # 流式上屏
    history.append(resp)                          # 关键：回写后再选下一个
    if 新用户消息到达: break                       # 人在环：用户随时夺回控制权
```

一个模型，三个切面全解：

| 调研文档的问题 | 本方案的答案 | 落在调研表的哪个选项 |
|------|------|------|
| 上下文过时 | 串行执行，每个 Agent 必看到前面所有人的输出，物理上无并发 | 问题1 **A 回合制** |
| 谁该回 | Selector 即 Router，分层：有 @ 强制路由 → 无 @ 才由 Selector 选 | 问题2 **A+B 分层** |
| 是否通知其他 Agent | 回写 history 后再选下一个 = 回合内广播，但用 V1 已有的「追加历史」原语实现 | 问题3 **B（以 C 的机制落地）** |

### 2.1 互知机制：靠 ContextBuilder 注入，不靠 Agent 互相订阅

Agent 之间的「感知」来自 **ContextBuilder 把共享群聊历史（含上一位 Agent 刚结束的发言）注入下一位 Agent 的 prompt**，而不是 Agent 订阅彼此的 CLI session。

这与 boundary 文档「AgentHub 决定看什么，CLI 决定怎么想」的原则一致：

- 每个 Agent 的 CLI session 仍隔离（`l1:{session_id}:{agent_id}`）
- 跨 Agent 的上下文统一由 ContextBuilder 从 PG 群聊历史拼装注入
- Agent B 看到 A 的发言，是因为 A 的发言已落库并被注入 B 的本轮 prompt，**不是** B 去读 A 的进程

所以「通知其他 Agent」既不引入进程间通信，也不产生循环——它只是「下一轮的上下文里多了上一轮的输出」。

## 三、两个关键洞察（调研文档没接上的）

### 3.1 回合制的「延迟累积 15s」是伪命题——前提是忽略了流式

调研文档把回合制的主要缺点列为「延迟累积（3 Agent × 5s = 15s）」。这个框架假设用户干等到全部说完才拿到价值，**在流式下不成立**：

- 链路本来就是 `adapter.stream()`，A 边说用户边读，B 还没开始
- 这正是真人群聊的体感——人也是一个一个说，不是同时喊
- 真正的延迟代价是**回合间 Selector 的 1-2s 空窗**（这段没有 token 流出）

→ 优化方向是「压缩 Selector 空窗」（快模型 + 有 @ 时跳过 Selector），**不是**放弃回合制。回合制本身在流式 UI 下体感良好。

### 3.2 「60-66% 失败率」吓人，但不适用于本产品

research 文档引用 AutoGen/MetaGPT/ChatDev 全广播多 Agent 的 60-66% 失败率。这个数字来自**全自主任务闭环**（Agent 自己把整个活干完，无人介入）。

AgentHub 讨论模式是**人在环群聊**：用户全程在场，既是终止条件，也是纠偏力。人在环把失败面砍掉一大半——Agent 跑偏，用户下一句话就拉回来了。这是 research 文档提到、options 文档没接上的关键限定。

## 四、判死的选项（不要浪费工程量）

| 选项 | 判死理由 |
|------|---------|
| 问题1-B 等齐再发 | 严格劣于流式串行，无任何场景需要。删 |
| 问题1-C 放任并发 | 最诱人的「V1.5 偷懒路径」，实为陷阱——制造矛盾/冗余，再逼你上协调者汇总擦屁股。**要做多 Agent 互相反应，就串行做** |
| 问题1-D 协调者汇总 | 现阶段过度设计，多一次 LLM hop 还丢对话感。用户想要总结 → 让协调者作为普通一轮发言即可。V3+ 再议 |
| 问题2-D 全员自决 | 噪声不可控（YES AND 置信度自选仍在校准期），不契合 IM 群聊 |
| 问题3-D 结构化传递 | CrewAI 任务委托范式，丢上下文，不契合「聊天」形态 |

保留备用（非本期）：问题2-C 协调者调度——当讨论需要**任务分解**而非单纯多视角讨论时启用，与 L3 Coordinator 合流，属 L3/L4 范畴。

## 五、对现有文档的两处修正

### 5.1 修正 V1 设计 §2.1：不止「换 Router」，而是「外套循环」

V1 文档称「两种模式共用流水线，唯一差异在 Router，~80% 代码不动」——**乐观了**。

讨论模式不是替换 Router，是在 Router+Executor 外面套一个**带终止条件的循环**。控制流从「单次 pass」变成「loop」，`send_group_message` 本身要改：

```
V1 @路由：   Pipeline → Router(→list) → Executor(并发 gather) → 收集
M3 讨论：    Pipeline → loop{ Selector(→1个|DONE) → Executor(单个) → 回写 } → 收集
```

Executor / ContextBuilder / Pipeline 确实不变，但**新增外层回合循环**是真实成本，别低估。建议把 Selector 视为「每轮只选一人、且能返回 DONE 的 Router」。

### 5.2 修正 V1 设计 §2.3：单向 → 受控回环

V1 写「Agent 回复不再进入 Router」。M3 必须打破这条——讨论模式的本质就是 Agent 输出回写后触发下一轮选择。

这不矛盾，但要在文档显式标注：**V1 单向；M3 引入受控回环（`max_round` 兜底 + Selector DONE）**。否则接手者会误以为「不回环」是不可逾越的红线。

## 六、架构落地（叠加在 boundary 文档的模块边界上）

```
┌──────────────────────────────────────────────────────────┐
│              DiscussionOrchestrator（新增，薄）             │
│   send_group_message 中按 dispatch_mode 分流，承载回合循环   │
│                                                            │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐  ┌──────┐ │
│  │ Pipeline │   │ Selector │   │ContextBuilder│  │ Exec │ │
│  │ 落库+广播 │   │ 选下一人  │   │ 注入共享历史  │  │stream│ │
│  │ (不变)   │   │ /DONE    │   │ (不变)       │  │(不变)│ │
│  └──────────┘   └────┬─────┘   └──────────────┘  └──────┘ │
│                      │  回合循环：pick→build→stream→回写      │
└──────────────────────┴─────────────────────────────────────┘
```

| 组件 | 状态 | 职责 | 输入 → 输出 |
|------|------|------|------|
| `DiscussionOrchestrator` | **新增** | 承载回合循环 + 终止判定 + 人在环中断 | `(message, session)` → 多条 Agent 回复（流式） |
| `Selector` | **新增**（≈ 单选 Router） | 每轮选 1 人或 DONE | `(history, members)` → `TargetAgent \| DONE` |
| `ContextBuilder` | 复用 | 注入共享历史（含本轮已发言） | `ContextRequest` → `AgentRequest` |
| `Executor` | 复用 | `adapter.stream()` | `(agent, AgentRequest)` → `AsyncIterator[StreamEvent]` |
| `Pipeline` | 复用 | 落库 + WS 广播 | `message` → 持久化 + 广播 |

`DiscussionOrchestrator` 建议为独立薄类，避免把循环塞进 `ChatService.send_group_message` 撑大该方法（也可先内联、有复杂度再抽，二者皆可）。

### 6.1 Selector vs 协调者：为什么独立

**Selector 独立于所有 Agent，包括协调者。** 两者职责不同：

| | Selector | Coordinator Agent |
|------|----------|-------------------|
| 是什么 | 路由函数 | 一个 Agent(有自己的 CLI session) |
| 做什么 | 决定下一轮谁发言 | 被选中时参与讨论/分解任务 |
| 模型 | 廉价(Haiku),选人不需要深度推理 | Opus/Sonnet,深度推理 |
| 参与讨论 | 否 | 是 |

协调者兼任 Selector 的后果：协调者的 CLI session 里混杂「选人逻辑」和「自己的发言」，既当裁判又当运动员。Selector 应保持无状态、无 session、不参与讨论。

Coordinator Agent **可以被 Selector 选中发言**，但不能是 Selector 本身。

### 6.2 Selector 选人逻辑

```
Selector.pick(history, members):
  │
  ├─ 1. @mention（确定性，跳过 LLM）
  │     例: AgentA 说 "@AgentB 你觉得呢" → 强制选 AgentB
  │     例: 用户发了 "等着 @前端专家 的结论" → 强制选前端专家
  │
  ├─ 2. 关键词/能力标签匹配（零成本兜底）
  │     "这个按钮点不了" → 匹配 capability_tags:["前端"] → 选前端专家
  │
  ├─ 3. LLM 评估（廉价，Haiku）
  │     Prompt 包含:
  │     - 完整群聊 history（含本轮已发言）
  │     - 每个成员的 name/role/capability_tags
  │     - 已发言过的成员（allow_repeat_speaker=False 排除）
  │     - 收敛判断指引：
  │       """
  │       判断以下群聊记录是否已得出结论或自然收敛。
  │       如果有成员明确在等另一个成员的回复，选那个人。
  │       如果讨论在重复已有观点、未引入新信息，返回 DONE。
  │       如果讨论已收敛，返回 DONE。
  │       否则返回最应该发言的成员名字。
  │       """
  │     → 输出: next_speaker | DONE
  │
  └─ 4. 所有条件不命中 → DONE

特殊情况：无明确指向
  消息没有 @ 任何人，关键词也没匹配到 → 进入 LLM 评估层
  LLM 判断：这条消息是在等特定的人回答，还是讨论已经说完了？
  "好的，明白了" → DONE
  "我也觉得这个方案可行" → DONE（认同，无需继续）
  "这个 bug 需要看下" → 可能选前端专家（靠 LLM 语义判断）
```

### 6.3 停不下来的问题

**主力防线是 Selector DONE，不是 max_round。**

LLM prompt 里要求判断「讨论是否已收敛」——讨论质量高则继续选人，兜圈子则 DONE。`max_round` 只兜底极端情况。

**用户在环时讨论不会受限：**

用户新消息到达 → `round` 计数清零，讨论续命。用户的"继续讨论"、"AgentB 你也说说"都是有效的延长信号。`max_round` 只约束 Agent 自言自语的最大轮数。

**Agent 等待另一个 Agent：**

Agent 自己的回复里 @ 另一个 Agent → Selector 的 @mention 规则自动处理。不需要特殊逻辑：

```
AgentA: "应该是前端的问题，需要 @AgentB 确认后端 API 是否正常"
  → Selector 命中规则 1（@AgentB）→ 选 AgentB
  → round 照常计数，但这是有效对话，不是空转
  → AgentB 回复后，Selector 判断下一步
```

**三条防线叠加：**

| 防线 | 机制 | 触发条件 |
|------|------|---------|
| 1. Selector DONE | LLM 判断讨论收敛 | 讨论自然结束/无新信息 |
| 2. max_round | 硬上限（默认 3-4） | Agent 持续发言超过上限 |
| 3. 人在环 | 用户消息中断循环 | 用户任何时候说话 |

### 6.4 Selector Bypass：让 Agent 自治接力

> **回应的设计担忧**：每轮经 Selector 是否让群聊体感僵硬、像被点名发言？

**核心机制**：Selector 不是每轮都要做 LLM 评估。§6.2 的分层路由里，第 1 层 @mention 路径**完全跳过 LLM**，是直接确定性路由。这条路径既覆盖用户的 @，也覆盖 **Agent 自己在回复里 @ 下一个 Agent** 的情况。

```
AgentA: "应该是前端的问题，@AgentB 你那边看下接口返回"
  → Selector 命中 @mention 规则 → 跳过 LLM 评估 → 直接路由 B
  → B 立即接话，零调度延迟感
```

**激活条件**：Agent 必须**主动** @ 接力，而不是回完一段就停。这需要在 Agent system_prompt 模板里显式鼓励（见 §十 待解项）：

```
你在群聊中发言时，如果讨论需要某位成员补充或回应，
直接在回复末尾 @ 该成员（如 "@AgentB 你怎么看"）。
这能让对话自然流转，无需等待外部调度。
```

**预期效果**：实际 Selector LLM 评估介入率从 100% 降到 30-50%（主要在 Agent 没主动交接、讨论方向歧义时），其余轮次走 @ 接力，体感接近自由群聊。

**Selector 的兜底定位**：保留 Selector 不是为了"每轮都管"，而是为了：

- 真正歧义（无 @、无关键词命中）时做仲裁
- 讨论收敛判定（DONE）—— 这是 Agent 自治做不到的（LLM 没有"群体讨论结束了"的视角）
- max_round 兜底
- 防止 Agent 自治退化为 heliox 式自由广播的死群/echo/N×LLM 成本问题

### 6.5 模式扩展性预留

当前 M3 只实现「任务讨论」模式，但架构上必须留出口，避免后续产品形态（角色扮演、闲聊群）被迫推翻 M3 实现。

**字段层面**：

```python
class DispatchMode(Enum):
    AT_ROUTING = "at"             # V1：仅 @ 路由
    DISCUSSION = "discussion"      # M3：任务讨论（本文档实现）
    ROLEPLAY = "roleplay"          # 预留：角色扮演（非本期）
    FREE_BROADCAST = "broadcast"   # 预留：自治广播闲聊（非本期）
```

不要写成 `bool discussion_mode`——一旦写死，后续加模式必须改表 + 改判断逻辑。

**Selector prompt 模板化**：

不要把「判断讨论是否已收敛」这种任务讨论专用措辞写死在代码里。Selector 取 prompt 时按 `dispatch_mode` 选模板：

```python
SELECTOR_PROMPTS = {
    DispatchMode.DISCUSSION: TASK_DISCUSSION_TEMPLATE,
    # ROLEPLAY/FREE_BROADCAST 留空，后续填入
}
```

**max_round 放群组配置**：

任务讨论默认 3-4，角色扮演可能需要 10+。硬编码到代码会阻塞后续模式扩展。放 `groups.discussion_config` JSON 字段。

**不在本期实现的模式**：

- **ROLEPLAY**：需要持久角色记忆（L2/L3）、场景描述消息类型、不同 UX
- **FREE_BROADCAST**：需要 Agent 自治契约（act.md 风格 prompt）、N×LLM 成本控制、echo 容忍机制

这两个是独立产品线，不要塞进 M3。但**枚举值现在就要预留**，0 成本。

## 七、触发与切换

| 场景 | 行为 |
|------|------|
| `@单个 Agent` | 直连，单 Agent 回复（V1 行为，**始终保留**——逃生口，用户随时拿回确定性控制） |
| 群组 `dispatch_mode=DISCUSSION` 且无定向 @ | 进讨论循环 |
| 群组 `dispatch_mode=ROLEPLAY` / `FREE_BROADCAST` | 非本期实现，预留枚举值（见 §6.5） |
| `@协调者`（M3+） | 走 L3 任务分解（本文档范围外） |
| 讨论循环进行中，新用户消息到达 | 中断当前循环，按新消息重新路由（人在环优先级最高） |
| 讨论循环中，Agent 在回复末尾 @ 下一个 Agent | 走 Selector Bypass 路径（§6.4）—— 跳过 LLM 评估直接路由 |

## 八、防循环三件套

详见 §6.3。三条防线叠加：

1. **Selector DONE**（主力）— 讨论收敛时自然终止
2. **max_round**（保底，默认 3-4）— 硬上限兜底
3. **人在环**（最高优先级）— 用户随时中断循环，且用户新消息将 `round` 清零

## 九、边界条件

| 场景 | 处理 |
|------|------|
| Selector LLM 调用失败 | 降级到关键词规则；规则也无命中 → 结束本轮（不阻塞用户） |
| 群组无成员 / 仅 1 成员 | 退化为单 Agent 直连，不启动循环 |
| 某 Agent 本轮 stream 失败 | 该轮跳过，记录错误，继续选下一人（不中断整个讨论） |
| 连续 max_round 轮无人被选 | 直接结束，消息只广播到 UI |
| 讨论中 Agent 被删除 | 从 members 移除，下一轮 Selector 不再可选该 Agent |
| 用户在循环中途 @ 某人 | 视为新用户消息 → 中断循环 → 强制路由该 Agent |

## 十、留给实现阶段的待解问题

已解决:
- ~~Selector 的选人逻辑~~ → §6.2 已定义分层路由
- ~~Selector 是否交给协调者~~ → §6.1 已裁决：独立

仍待确定:
1. **Selector 的 prompt 精确措辞与 few-shot**——「讨论是否已收敛」需调校
2. **回合间空窗的 UX**——是否显示「XX 正在思考」占位
3. **历史窗口 N 的取值**——讨论轮次叠加后截断策略（与 L1 滑动窗口对齐）
4. **是否需要发言前确认**——讨论模式 Agent 发言是否要用户确认才落库（倾向「不需要」）
5. **Agent system_prompt 模板设计**——鼓励主动 @ 接力（见 §6.4），让 Selector LLM 介入率从 100% 降到 30-50%。需调校措辞，避免 Agent 过度 @（变成无意义点名）或反过来不敢 @（退化为 100% Selector 驱动）
6. **Selector LLM 调用与 Speaker 流式的 overlap**——上一个 Agent 流式接近尾声时提前启动 Selector 评估当前 history，让 Selector 延迟对用户不可见。是否实现 overlap 视实测延迟决定

## 十一、参考

| 文档 | 内容 |
|------|------|
| `docs/design/group-chat_群聊功能设计方案.md` | V1 @路由模式（前置） |
| `docs/explore/group-chat-discussion-mode-options.md` | 三问题方案对比（本抉择的输入） |
| `docs/explore/group-chat-discussion-mode-research.md` | 业界调研（AutoGen/CrewAI/Slack/OpenClaw） |
| `docs/explore/group-chat-boundary-and-dependencies.md` | 模块边界与接口契约 |
| `spec/domains/domain2-orchestration_域2-Agent编排.md` | M3 编排任务清单 |
