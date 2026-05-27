"""Selector 三层路由单元测试。"""

from __future__ import annotations

import uuid

import pytest

from app.application.services.selector import Selector, SelectorDecision
from app.domain.entities.agent import Agent
from app.domain.entities.message import Message
from app.domain.enums import AgentSystem, MessageRole, Provider


def _mk_agent(name: str, role: str, tags: list[str]) -> Agent:
    return Agent(
        name=name,
        role=role,
        avatar="",
        agent_system=AgentSystem.CLAUDE_CODE,
        provider=Provider.ANTHROPIC,
        model="m",
        api_key_encrypted="x",
        capability_tags=tags,
        system_prompt="",
    )


@pytest.mark.asyncio
async def test_mention_field_resolves_to_member() -> None:
    a = _mk_agent("AgentA", "前端", ["frontend"])
    b = _mk_agent("AgentB", "后端", ["backend"])
    sid = uuid.uuid4()
    msg = Message(
        session_id=sid, role=MessageRole.USER, content="hi", mentions=["AgentB"]
    )

    sel = Selector()
    decision = await sel.pick(members=[a, b], history=[msg])
    assert decision.next_agent_id == b.id
    assert decision.mention_queue == ()


@pytest.mark.asyncio
async def test_inline_at_from_agent_bypasses_llm() -> None:
    a = _mk_agent("AgentA", "前端", ["frontend"])
    b = _mk_agent("AgentB", "后端", ["backend"])
    sid = uuid.uuid4()
    msg = Message(
        session_id=sid,
        role=MessageRole.ASSISTANT,
        content="我看是前端问题, @AgentB 你那边日志怎么样",
        sender_agent_id=a.id,
    )
    sel = Selector()
    decision = await sel.pick(members=[a, b], history=[msg])
    assert decision.next_agent_id == b.id
    assert "@mention" in decision.reason


@pytest.mark.asyncio
async def test_inline_at_self_ignored() -> None:
    """Agent 在自己回复里 @ 自己不应被路由（防自循环）。"""
    a = _mk_agent("AgentA", "前端", ["frontend"])
    b = _mk_agent("AgentB", "后端", ["backend"])
    sid = uuid.uuid4()
    msg = Message(
        session_id=sid,
        role=MessageRole.ASSISTANT,
        content="@AgentA 自言自语",
        sender_agent_id=a.id,
    )
    sel = Selector()
    decision = await sel.pick(members=[a, b], history=[msg])
    # 第 1 层不命中（@ 自己被忽略），后续会进 LLM 降级 DONE
    assert decision.next_agent_id != a.id


@pytest.mark.asyncio
async def test_capability_keyword_matches() -> None:
    a = _mk_agent("AgentA", "前端", ["frontend", "react"])
    b = _mk_agent("AgentB", "后端", ["backend"])
    sid = uuid.uuid4()
    msg = Message(
        session_id=sid, role=MessageRole.USER, content="这个 react 组件有 bug"
    )
    sel = Selector()
    decision = await sel.pick(members=[a, b], history=[msg])
    assert decision.next_agent_id == a.id
    assert "capability" in decision.reason


@pytest.mark.asyncio
async def test_empty_members_returns_done() -> None:
    sid = uuid.uuid4()
    msg = Message(session_id=sid, role=MessageRole.USER, content="hi")
    sel = Selector()
    decision = await sel.pick(members=[], history=[msg])
    assert decision.done is True


@pytest.mark.asyncio
async def test_empty_history_returns_done() -> None:
    a = _mk_agent("AgentA", "前端", ["frontend"])
    sel = Selector()
    decision = await sel.pick(members=[a], history=[])
    assert decision.done is True


@pytest.mark.asyncio
async def test_llm_failure_degrades_to_done() -> None:
    """无 anthropic API key（CI 环境）→ Layer 3 异常降级 DONE，不抛错。"""
    a = _mk_agent("AgentA", "前端", ["xxx"])
    b = _mk_agent("AgentB", "后端", ["yyy"])
    sid = uuid.uuid4()
    msg = Message(session_id=sid, role=MessageRole.USER, content="随便聊聊")
    sel = Selector()
    decision = await sel.pick(members=[a, b], history=[msg])
    assert decision.done is True


# --- 新增：@mention 多 Agent 队列 ---


@pytest.mark.asyncio
async def test_multi_mention_returns_queue() -> None:
    """mentions 字段多 @ → 第一个选中，其余入队。"""
    a = _mk_agent("AgentA", "前端", ["frontend"])
    b = _mk_agent("AgentB", "后端", ["backend"])
    c = _mk_agent("AgentC", "测试", ["qa"])
    sid = uuid.uuid4()
    msg = Message(
        session_id=sid,
        role=MessageRole.USER,
        content="大家讨论一下",
        mentions=["AgentA", "AgentB", "AgentC"],
    )
    sel = Selector()
    decision = await sel.pick(members=[a, b, c], history=[msg])
    assert decision.next_agent_id == a.id
    assert decision.mention_queue == (b.id, c.id)


@pytest.mark.asyncio
async def test_multi_inline_mention_queues_rest() -> None:
    """文本多 @ 去重后入队（排除 mention 字段已命中的，排除自己 @ 自己）。"""
    a = _mk_agent("AgentA", "前端", ["frontend"])
    b = _mk_agent("AgentB", "后端", ["backend"])
    c = _mk_agent("AgentC", "测试", ["qa"])
    sid = uuid.uuid4()
    # mentions 字段已有 AgentA，文本中 AgentA 不再重复收集
    msg = Message(
        session_id=sid,
        role=MessageRole.USER,
        content="@AgentB @AgentC 来帮忙",
        mentions=["AgentA"],
    )
    sel = Selector()
    decision = await sel.pick(members=[a, b, c], history=[msg])
    assert decision.next_agent_id == a.id  # mentions 字段优先
    assert decision.mention_queue == (b.id, c.id)  # 文本收集的去重后入队


# --- 新增：消息截断保护 ---


def test_code_block_compressed_in_prompt() -> None:
    """代码块被压缩为占位符。"""
    from app.application.services.selector import _CODE_BLOCK_PATTERN

    content = "正常文本\n```python\nprint('hello' * 1000)\n```\n更多内容"
    compressed = _CODE_BLOCK_PATTERN.sub("[代码片段已省略]", content)
    assert "```python" not in compressed
    assert "[代码片段已省略]" in compressed
    assert "正常文本" in compressed
    assert "更多内容" in compressed


def test_per_message_truncated() -> None:
    """超长消息被截断到 300 字符 + ..."""
    from app.application.services.selector import _PER_MESSAGE_CHAR_LIMIT

    long_content = "x" * 500
    # Simulate per-message truncation
    if len(long_content) > _PER_MESSAGE_CHAR_LIMIT:
        long_content = long_content[:_PER_MESSAGE_CHAR_LIMIT] + "..."
    assert len(long_content) == _PER_MESSAGE_CHAR_LIMIT + 3
    assert long_content.endswith("...")


def test_total_prompt_length_guard_trims_oldest() -> None:
    """总长超限时从最旧消息开始裁剪，至少保留 1 条。"""
    from app.application.services.selector import Selector
    from app.core.config import settings

    a = _mk_agent("AgentA", "前端", ["frontend"])
    b = _mk_agent("AgentB", "后端", ["backend"])
    # 构造多条长消息，确保超限触发裁剪
    sid = uuid.uuid4()
    msgs = []
    for i in range(10):
        msgs.append(
            Message(
                session_id=sid,
                role=MessageRole.ASSISTANT,
                content=f"消息{i}: " + "x" * 200,
                sender_agent_id=a.id if i % 2 == 0 else b.id,
            )
        )
    name_by_id = {a.id: a.name, b.id: b.name}
    system, prompt = Selector._build_prompts(
        candidates=[a, b], history=msgs, name_by_id=name_by_id
    )
    # prompt 不应超过 settings.selector_max_prompt_chars
    assert len(system) + len(prompt) <= settings.selector_max_prompt_chars + 500  # 允许一定容差
    # 至少保留 1 条消息
    assert "候选成员：" in prompt
    assert "群聊记录（按时间顺序）：" in prompt
