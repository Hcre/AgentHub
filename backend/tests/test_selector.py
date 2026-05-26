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
    assert decision == SelectorDecision.pick(
        b.id, reason=decision.reason
    ) or decision.next_agent_id == b.id


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
    assert "inline" in decision.reason


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
