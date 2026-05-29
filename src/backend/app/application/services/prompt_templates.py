"""群聊场景的 system prompt 模板与拼装辅助。

设计依据：
- docs/design/group-chat-discussion-mode_群聊讨论模式设计方案.md §6.4 Selector Bypass
- docs/design/group-chat-implementation-plan_群聊实施计划.md §四 GROUP_CHAT_CONTRACT
"""

from __future__ import annotations

from app.domain.entities.agent import Agent
from app.domain.entities.message import Message

# 群聊行为契约：注入到每个群聊 Agent 的 system_prompt。
# 私聊场景不注入。
GROUP_CHAT_CONTRACT = """你正在多 Agent 群聊中协作。请遵守以下行为约定：

1. 主动 @ 接力：如果你的回复需要某位成员补充、确认或反驳，
   直接在回复末尾 @ 该成员（如 "@AgentB 你怎么看"）。
   这能让对话自然流转，无需等待外部调度。

2. 简洁优先：不要复述其他成员已说过的内容。
   如无新信息可贡献，可以简短承接或保持沉默。

3. 角色聚焦：发挥你的角色优势，不要越界回答其他成员更擅长的领域。
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
    lines = ["以下是自你上次发言后的新群聊消息（按时间顺序）："]
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
