# 群聊身份错乱问题分析

> 日期：2026-05-28 | 触发：喵娘 / 技术负责人 / 协调者身份混淆

## 一、现象

截图中的身份错乱表现为三类：

1. **身份互串**：「喵娘」自称「技术负责人」，「技术负责人」自称「协调者-cch」
2. **口吻传染**：所有 Agent 都在句末加「喵~」，说明某个 Agent 的 persona 污染了其他 Agent
3. **自己 @ 自己**：「喵娘: @喵娘 麻烦你准备一下推荐清单」

## 二、当前链路（逐层追踪）

### 2.1 调用入口

DiscussionOrchestrator 或 ChatService 对每个目标 Agent 调 `ContextBuilder.build_for_agent()`。

```python
# context_builder.py:67-76
if group is not None:
    return await self._build_group(
        session=session, group=group,
        target_agent=target_agent, trigger=trigger,
    )
```

### 2.2 system_prompt 组装（_build_group）

```python
# context_builder.py:98 — 身份定义
persona = target_agent.system_prompt or f"你是 {target_agent.name}。"

# context_builder.py:107-117 — 拼接顺序
system_prompt = "\n\n".join([
    persona,              # ① 身份（最弱的位置）
    GROUP_CHAT_CONTRACT,  # ② 行为契约
    members_block,        # ③ 其他成员列表
    delta_block,          # ④ 增量群聊消息（可能非常长）
])
```

### 2.3 GROUP_CHAT_CONTRACT（当前版本）

```
你正在多 Agent 群聊中协作。请遵守以下行为约定：

1. 主动 @ 接力：...
2. 简洁优先：...
3. 角色聚焦：发挥你的角色优势，不要越界...
```

**问题**：此契约完全没有向 Agent 确认「你是谁」。LLM 看到的身份声明只有最上面一句 `persona`。

### 2.4 成员列表渲染

```python
# prompt_templates.py:28-40
def format_members(members: list[Agent], current_agent: Agent) -> str:
    lines = ["群聊其他成员："]
    for m in members:
        if m.id == current_agent.id:
            continue        # 正确：跳过了自己
        role = m.role or "未指定"
        lines.append(f"- {m.name}（角色：{m.role or '未指定'}）")
```

这里的 `members` 来自 `_load_members()`：

```python
# context_builder.py:212-219
async def _load_members(self, group: Group) -> list[Agent]:
    ids = list({*group.member_ids, group.coordinator_id})  # ← 包含了协调者
```

### 2.5 增量消息渲染

```python
# prompt_templates.py:43-57
def format_delta(delta, agent_name_by_id):
    lines = ["以下是自你上次发言后的新群聊消息（按时间顺序）："]
    for msg in delta:
        speaker = _render_speaker(msg, agent_name_by_id)
        lines.append(f"{speaker}: {msg.content}")
```

`agent_name_by_id` 由 `ContextBuilder._build_group:99` 计算：
```python
agent_name_by_id = {m.id: m.name for m in members}
```

---

## 三、根因分析

### 根因 1：身份声明窒息

以「喵娘」为例，完整 system_prompt 结构：

```
┌─ ① persona ─────────────────────┐
│ 你是 喵娘。                       │  ← 只有这一句告诉 LLM "你是谁"
└──────────────────────────────────┘
┌─ ② GROUP_CHAT_CONTRACT ─────────┐
│ 你正在多 Agent 群聊中协作...      │  ← 没有重申身份
└──────────────────────────────────┘
┌─ ③ members_block ───────────────┐
│ 群聊其他成员：                    │
│ - 技术负责人（角色：技术负责人）    │  ← 其他 Agent 的 name/role
│ - 协调者-cch（角色：Coordinator） │
└──────────────────────────────────┘
┌─ ④ delta_block ─────────────────┐
│ 技术负责人: 大家好喵～...          │  ← 带 name 前缀的消息
│ 协调者-cch: 好的，我是协调者...    │
│ 用户: 你们自我介绍一下              │
└──────────────────────────────────┘
```

**LLM 实际读完这段 prompt 后得到的认知**：
- 前面一句「你是 喵娘」轻松被后面几百字的增量消息淹没
- 后面大量出现「技术负责人: xxx」这种带冒号的发言格式
- LLM 会认为「技术负责人」是一个重要角色，加上「技术负责人」说的内容很丰富
- 在多轮对话中逐渐忘记自己应该以「喵娘」身份说话

**对比**：如果 Claude Code CLI 的 `--system-prompt` 是这样设计的：
```
你是喵娘，一个可爱猫娘助手。你的身份是喵娘，不是技术负责人，不是协调者-cch。
你说话时要以"喵娘"的身份，语气要像猫娘，句末可以加"喵"。

当前你在群聊中，群聊其他成员：
- 技术负责人: 负责技术决策
- 协调者-cch: 负责拆分任务

以下是群聊消息，每条前面标注了发言人名字。请注意区分：带名字的是别人说的，不带名字的才是你自己说的。
```

**现在的 prompt 和推荐的 prompt 之间差了什么**：
- 身份声明只有一句 vs 应该多次强调
- 没有告诉 LLM 如何分辨自己和他人的发言
- 成员列表角色/名字和增量消息里的名字虽然一致，但没有明确标注"这些是别人"

### 根因 2：成员列表包含了协调者

`_load_members` 同时包含了普通成员和协调者。但 DiscussionOrchestrator 已经从候选名单里排除了协调者。ContextBuilder 的成员列表也应该保持一致。

### 根因 3：persona 依赖 Agent 创建时的 system_prompt

如果 Agent 创建时没写 `system_prompt`，`persona` 退化为 `f"你是 {target_agent.name}。"`——这实在太弱了。

### 根因 4：「喵~」口吻传染

当「技术负责人」在第一轮回复中说了「喵~大家好呀」，这个消息进入了 delta_block。下一轮「喵娘」收到的增量消息里包含这句。LLM 读到「技术负责人」用猫娘口吻说话，就会认为群里的交流风格就是这样的，于是自己也开始模仿。

---

## 四、修复建议（优先级排序）

| 优先级 | 修复 | 位置 |
|--------|------|------|
| P0 | 强化身份提示：persona 改为 `"你的名字是 {name}，身份是 {role}。注意：群聊消息中带「发言人名字:」前缀的都是别人的发言，不要把它们当成你自己的发言。"` | `context_builder.py:98` |
| P0 | GROUP_CHAT_CONTRACT 第 1 条改为身份确认规则 | `prompt_templates.py:15` |
| P1 | `_load_members` 排除协调者（与 DiscussionOrchestrator 一致） | `context_builder.py:213` |
| P1 | `format_delta` 在消息列表开头加提示：「以下每条消息前面的「名字:」是该消息的发言人，不是你。你只需要理解内容后以自己身份回复。」 | `prompt_templates.py:51` |
| P2 | 创建 Agent 时默认填充有意义的 system_prompt | Agent 创建 API |
