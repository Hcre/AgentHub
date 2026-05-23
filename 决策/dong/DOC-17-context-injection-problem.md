# DOC-17 上下文注入问题：起源、探索与决策

> 版本：v1.0 | 日期：2026-05-23

---

## 一、问题起源

在实现 Claude Adapter 双轨架构（DOC-15）过程中，我们完成了：

- `LLMAdapter`（API 轨）+ `AgentRuntime`（CLI 轨）的接口拆分
- `ClaudeCodeRuntime` 的 CLI 进程管理 + stream-json 事件解析
- 利用 `--resume <session-id>` 实现 CLI 自带的对话持久化
- per-agent 路由（根据 `agent_system` 字段选择适配器）

**冒烟测试通过：** 私聊场景下，CLI `--resume` 成功维持多轮对话上下文，Agent 能记住之前的对话内容。

然而当我们从私聊推进到群聊场景时，发现了根本性的架构缺口。

## 二、问题分析

### 2.1 CLI --resume 的能力边界

Claude Code CLI 的 `--resume` 机制工作原理：

```
Session A (Agent-前端)          Session B (Agent-后端)
┌──────────────────┐            ┌──────────────────┐
│ user: 做一个登录页  │            │ user: 写登录API    │
│ assistant: 好的... │            │ assistant: 好的... │
│ user: 改一下样式   │            │ user: 加个JWT验证  │
│ assistant: ...    │            │ assistant: ...    │
└──────────────────┘            └──────────────────┘
     ↑ 各自独立                       ↑ 各自独立
     互相看不到对方的消息
```

每个 Agent 的 CLI session 是**隔离的**。`--resume` 只恢复自己的对话历史，不知道其他 Agent 说了什么。

### 2.2 群聊场景的实际需求

```
AgentHub 群聊 Session（5个 Agent）
┌────────────────────────────────────────────────┐
│ user:     "做一个带认证的博客系统"                  │
│ 协调者:    "分解任务：前端→登录页，后端→API，..."     │
│ 后端Agent: "API 设计完成，路由如下..."              │
│ 前端Agent: "我需要后端提供的接口文档来对接"   ← 需要看到后端的消息 │
│ user:     "@前端Agent 先用 mock 数据"             │
│ 前端Agent: "好的，mock 数据..."                   │
└────────────────────────────────────────────────┘
```

前端 Agent 被调用时，必须看到：
1. **其他 Agent 的消息**（后端 Agent 说了什么）
2. **协调者的任务分解**（自己负责什么）
3. **用户对其他 Agent 的指令**（可能影响自己的工作）
4. **@自己的消息**（需要响应）

仅靠 `--resume` 自己的历史，完全无法满足。

### 2.3 自定义能力注入

AgentHub 作为平台，需要给 Agent 注入平台级能力：

| 需注入内容 | CLI 自带？ | 说明 |
|-----------|----------|------|
| AgentHub skill 定义 | 否 | 平台自定义技能，非 CLI 内置 |
| AgentHub 工具描述 | 否 | memory_retrieve、task_create 等平台工具 |
| Agent 身份与角色 | 部分 | `--system-prompt` 可注入，但群聊中的角色关系需额外说明 |
| 项目规格/规则 | 部分 | CLI 能读 CLAUDE.md，但 AgentHub 层面的规格是动态的 |

### 2.4 问题总结

```
私聊模式：--resume 够用，上下文注入需求低
群聊模式：--resume 不够，必须注入其他 Agent 的消息 + 平台能力
API 模式：本来就无状态，所有上下文都需要显式传入
```

三种模式对上下文的需求差异巨大，但共用同一个 `AgentRequest` 接口。

## 三、探索过的方案

### 方案 A：StructuredContext 全量替换（DOC-16 原方案）

**思路：** 定义 6 层结构体，完全替换 AgentRequest。

```python
class StructuredContext(BaseModel):
    identity: IdentityContext        # 身份
    conversation: ConversationContext # 对话
    capabilities: CapabilityContext   # 工具+技能
    memory: MemoryContext            # 记忆
    project: ProjectContext          # 项目
    params: CallParams              # 参数
```

**优点：**
- 结构清晰，各层 ownership 明确
- 适配器只管格式化，不管组装

**问题：**
- 破坏性变更——protocol.py、ChatService、所有适配器、所有测试全部要改
- MemoryContext 与 protocol.py 已有定义重复
- MVP 阶段 6 层中只有 2-3 层有实际数据源，其余是空壳
- 群聊字段（peers/coordinator）属于 M3 范围，提前定义无法验证
- CLI 格式化尾部加了"请基于以上上下文给出回复"引导语，多余且可能干扰模型

### 方案 B：AgentRequest 渐进扩展

**思路：** 不替换，在 AgentRequest 上加字段。

```python
class AgentRequest(BaseModel):
    # ... 现有字段不动 ...
    identity_prompt: str | None = None     # 身份描述（群聊用）
    peer_messages: list[dict] = []         # 其他 Agent 的消息（群聊用）
    pinned_messages: list[dict] = []       # Pin 的消息
    tool_descriptions: list[dict] = []     # 平台工具描述
```

**优点：**
- 零破坏性，新字段全有默认值
- 现有代码不需要改动

**问题：**
- AgentRequest 会逐渐膨胀为 God Object
- 字段之间缺乏结构化分组，不知道哪些是给 API 用的、哪些是给 CLI 用的
- 语义不清——`messages` 是自己的历史，`peer_messages` 是别人的历史，`pinned_messages` 又是另一种历史

### 方案 C：AgentRequest + 可选 StructuredContext（推荐）

**思路：** 保留 AgentRequest 作为基础接口，新增 StructuredContext 作为可选增强字段。

```python
class AgentRequest(BaseModel):
    request_id: str
    session_id: UUID
    messages: list[dict]
    system_prompt: str | None = None
    memory: MemoryContext | None = None
    available_tools: list[str] = []
    max_tokens: int = 16000
    temperature: float = 0.7

    # 增强上下文（群聊/复杂场景渐进启用）
    context: StructuredContext | None = None
```

适配器行为：
- `context is None` → 走现有逻辑（私聊，简单模式）
- `context is not None` → 使用结构化上下文（群聊，复杂模式）

```
ChatService 组装策略：

私聊：
  AgentRequest(messages=window, system_prompt=agent.system_prompt)
  # context=None，CLI 用 --resume 维持历史

群聊：
  AgentRequest(
      messages=window,
      context=StructuredContext(
          identity=...,           # 你是谁，群里还有谁
          conversation=...,       # 其他 Agent 的消息
          capabilities=...,       # 平台工具/技能
          memory=...,             # 复用已有 MemoryContext
      )
  )
  # CLI 用 --resume 维持自己的历史
  # + context 注入其他人的消息
```

**优点：**
- 零破坏性——现有代码不改
- 渐进引入——私聊不用 context，群聊才启用
- MemoryContext 复用 protocol.py 已有定义，不重复
- 群聊字段只在 M3 实际实现时才填充，不提前空跑

**问题：**
- 适配器需要处理两条路径（有/无 context）
- 长期可能需要统一为单一路径

## 四、CLI 群聊的上下文注入策略

方案 C 下，CLI 群聊调用时的实际行为：

```
ClaudeCodeRuntime.stream(request):
  if request.context:
      # 群聊模式：把其他 Agent 消息 + 身份描述拼入 prompt 前缀
      prompt = self._build_group_prompt(request.context) + "\n\n" + user_message
      # --resume 仍然恢复自己的对话连续性
      # 但每次把"群聊新增消息"注入到本轮 prompt 中
  else:
      # 私聊模式：只传用户消息，--resume 维持全部上下文
      prompt = user_message
```

这样做到了：
- **自己的历史**：--resume 自动维持
- **别人的消息**：每轮注入增量（只注入上次调用以来的新消息）
- **平台能力**：通过 context.capabilities 注入工具/技能描述

## 五、与 API 模式的对比

| 维度 | API 模式（LLMAdapter） | CLI 模式（AgentRuntime） |
|------|----------------------|------------------------|
| 对话历史 | 每次全量传入 messages | --resume 自动恢复 + 增量注入其他人消息 |
| 身份 | system_prompt 参数 | --system-prompt 参数 |
| 工具 | function calling（SDK 原生） | 文本描述注入 prompt |
| 记忆 | system_prompt 拼接 L2/L4 | CLI 自带 memory 机制 + L2/L4 文本注入 |
| 会话状态 | 无状态 | 有状态（子进程 + 磁盘持久化） |

## 六、决策与下一步

### 决策

采用 **方案 C**：AgentRequest + 可选 StructuredContext。

### 实施节奏

| 阶段 | 内容 | 时间 |
|------|------|------|
| M2（当前） | 私聊跑通，不引入 StructuredContext | 已完成 |
| M3-前期 | 定义 StructuredContext 子结构体（identity/conversation/capabilities） | M3 |
| M3-中期 | ChatService 群聊路径组装 context | M3 |
| M3-后期 | ClaudeCodeRuntime 消费 context，实现群聊注入 | M3 |

### 需要修正的文档

- **DOC-16**：方案从"全量替换"改为"可选增强"；删除重复的 MemoryContext 定义；删除尾部引导语；群聊字段标注 M3 范围
- **DOC-15**：补充 CLI 群聊的上下文注入策略说明

---

## 附录：验证记录

### 私聊 --resume 验证（2026-05-22）

```
第1轮：claude --print --session-id <uuid> "我叫小明"
→ "记住了，小明"

第2轮：claude --print --resume <uuid> "我叫什么名字？"
→ "你叫小明"

结论：CLI session 持久化正常工作，私聊不需要额外上下文注入。
```

### ClaudeCodeRuntime 冒烟测试（2026-05-23）

```
Session ID: 9be71812-c21d-41fd-b1c2-210c54ccbc2f

第1轮 (fallback 新建): "我叫小明，请记住"
→ 正常响应，cost=$0.19，7749ms

第2轮 (resume): "我叫什么名字？"
→ "你叫小明"，cost=$0.07，2494ms

结论：resume fallback 机制正常，多轮对话维持成功。
```
