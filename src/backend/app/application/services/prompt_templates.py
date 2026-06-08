"""群聊场景的 system prompt 模板与拼装辅助。

设计依据：
- docs/design/group-chat-discussion-mode_群聊讨论模式设计方案.md §6.4 Selector Bypass
- docs/design/group-chat-implementation-plan_群聊实施计划.md §四 GROUP_CHAT_CONTRACT
- docs/explore/董/记忆/memory-system-design-v3.md §六 注入格式
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.entities.agent import Agent
from app.domain.entities.memory import Memory
from app.domain.entities.message import Message

# 群聊行为契约：注入到每个群聊 Agent 的 system_prompt。
# 私聊场景不注入。
MEMORY_TOOL_CONTRACT = """# Memory
使用 save_memory 工具保存用户主动要求记住的内容（用户说「记住」「记一下」时调用）。
已有记忆会自动注入到对话中，无需主动查找。
不要用 Write 工具写本地 memory 目录，记忆由系统统一管理。"""

GROUP_CHAT_CONTRACT = """你正在多 Agent 群聊中协作。请遵守以下行为约定：

1. 身份确认：每条消息前缀标注了发言人身份。你只代表你自己发言，
   不要替其他成员说话，不要模仿他人的语癖或口头禅。

2. 可选择 @ 接力：如果你的回复需要某位成员补充、确认或反驳，
   直接在回复末尾 @ 该成员（如 "@AgentB 你怎么看"）。
   这能让对话自然流转，无需等待外部调度。

3. 简洁优先：不要复述其他成员已说过的内容。
   如无新信息可贡献，可以简短承接或保持沉默。

4. 角色聚焦：发挥你的角色优势，不要越界回答其他成员更擅长的领域。
"""


def format_members(members: list[Agent], current_agent: Agent) -> str:
    """渲染群成员列表，标识当前 Agent。"""
    if not members:
        return "群聊成员：暂无其他成员。"
    lines = ["群聊其他成员："]
    for m in members:
        if m.id == current_agent.id:
            continue
        role = m.role or "未指定"
        lines.append(f"- {m.name}（角色：{role}）")
    if len(lines) == 1:
        return "群聊成员：仅有你一人。"
    return "\n".join(lines)


def format_delta(delta: list[Message], agent_name_by_id: dict) -> str:
    """渲染群聊增量消息（按时间正序）。

    参数 agent_name_by_id：{agent_id: name} 映射，用于把 sender_agent_id 渲染成 name。
    用户消息渲染为 "用户" + 可选 mentions。
    """
    if not delta:
        return ""
    lines = [
        "以下是自你上次发言后的新群聊消息（按时间顺序）：",
        "每条消息前缀「发言人: 」标注了该消息的发送者身份，据此区分各成员的发言。",
    ]
    lines.append("---")
    for msg in delta:
        speaker = _render_speaker(msg, agent_name_by_id)
        lines.append(f"{speaker}: {msg.content}")
    lines.append("---")
    return "\n".join(lines)


def _render_speaker(msg: Message, agent_name_by_id: dict) -> str:
    if msg.sender_agent_id is not None:
        return agent_name_by_id.get(msg.sender_agent_id, "未知 Agent")
    if msg.mentions:
        return f"用户 (@{' @'.join(msg.mentions)})"
    return "用户"


# --- 记忆注入渲染（V3 <agenthub-reminder>）---

_TYPE_LABEL = {
    "facts": "事实",
    "preferences": "偏好",
    "procedures": "流程",
    "context": "上下文",
}

_DRIFT_GUARD = """\
⚠️ 记忆反映保存时的状态，可能已过时。采纳前必须主动验证：
- 文件路径 → 先检查文件是否存在
- 函数名或配置项 → 先 grep 确认
- 项目状态（「正在做 X」）→ 先检查当前代码/文档
- 记忆说「X 存在」≠「X 现在还存在」
如果用户要求忽略记忆中的内容，以用户指令为准，不要引用记忆来反驳。"""


def render_agenthub_reminder(memories: list[Memory]) -> str:
    """渲染 <agenthub-reminder> 块，含漂移防御和时间警告。"""
    if not memories:
        return ""

    pinned = [m for m in memories if m.pinned]
    others = [m for m in memories if not m.pinned]

    lines = [
        "<agenthub-reminder>",
        "以下是与当前对话相关的记忆。",
        "",
        _DRIFT_GUARD,
    ]

    if pinned:
        lines += ["", "━━━ PINNED ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        for m in pinned:
            lines += [
                f"📌 [{m.name}] — {_TYPE_LABEL.get(m.memory_type, m.memory_type)}，{_age_label(m.created_at)}保存",
                f"**摘要**: {m.description}",
                f"**内容**: {m.content}",
                "",
            ]

    if others:
        lines += ["━━━ 相关记忆 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        for m in others:
            warn = _age_warning(m.created_at)
            lines.append(
                f"📄 [{m.name}] — {_age_label(m.created_at)}保存"
            )
            if warn:
                lines.append(warn)
            lines += [
                f"**类型**: {_TYPE_LABEL.get(m.memory_type, m.memory_type)}",
                f"**摘要**: {m.description}",
                f"**内容**: {m.content}",
                "",
            ]

    lines.append("</agenthub-reminder>")
    return "\n".join(lines)


def _age_label(dt: datetime) -> str:
    delta = _days_ago(dt)
    if delta == 0:
        return "今天"
    if delta == 1:
        return "昨天"
    return f"{delta} 天前"


def _age_warning(dt: datetime) -> str:
    days = _days_ago(dt)
    if days >= 30:
        return "⚠️ 已保存超过 30 天，强烈建议验证。"
    if days >= 2:
        return "⚠️ 已保存超过 2 天，可能已过时。"
    return ""


def _days_ago(dt: datetime) -> int:
    now = datetime.now(UTC)
    aware = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
    return (now - aware).days
