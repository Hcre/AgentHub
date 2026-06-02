"""ContextBuilder 增量注入单元测试。"""

from __future__ import annotations

import pytest

from app.application.services.context_builder import ContextBuilder
from app.application.services.prompt_templates import GROUP_CHAT_CONTRACT
from app.domain.entities.agent import Agent
from app.domain.entities.group import Group
from app.domain.entities.message import Message
from app.domain.entities.session import Session
from app.domain.enums import MessageRole, SessionType
from app.infrastructure.cache.memory_l1 import InMemoryL1Store
from app.infrastructure.cache.watermark_store import InMemoryWatermarkStore
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresMessageRepository,
)


async def _setup(db_session):  # type: ignore[no-untyped-def]
    agent_repo = PostgresAgentRepository(db_session)
    msg_repo = PostgresMessageRepository(db_session)

    coord = Agent(name="协调者", avatar="C", role="c", is_system=True)
    a = Agent(name="AgentA", avatar="A", role="前端")
    b = Agent(name="AgentB", avatar="B", role="后端")
    for ag in (coord, a, b):
        await agent_repo.save(ag)

    group = Group(name="g", coordinator_id=coord.id, member_ids=[a.id, b.id])

    session = Session(type=SessionType.GROUP, group_id=group.id)
    l1 = InMemoryL1Store(window=20)
    wm = InMemoryWatermarkStore()

    ctx = ContextBuilder(msg_repo, agent_repo, l1, wm)
    return ctx, agent_repo, msg_repo, l1, wm, group, session, a, b


@pytest.mark.asyncio
async def test_group_first_touch_uses_seed_history(db_session) -> None:  # type: ignore[no-untyped-def]
    ctx, _ar, msg_repo, _l1, _wm, group, session, a, _b = await _setup(db_session)

    # 种几条历史
    for i in range(3):
        await msg_repo.save(Message(session_id=session.id, role=MessageRole.USER, content=f"u{i}"))

    trigger = Message(session_id=session.id, role=MessageRole.USER, content="trigger")
    req = await ctx.build_for_agent(session=session, group=group, target_agent=a, trigger=trigger)
    assert req.is_group_chat is True
    assert req.agent_id == a.id
    assert req.group_id == group.id
    # GROUP_CHAT_CONTRACT 应被注入到稳定的 system_prompt
    assert GROUP_CHAT_CONTRACT.split("\n")[0] in req.system_prompt
    # 种子历史走 group_delta_text 字段（拆 delta 后稳定 sp 不含动态内容）
    assert req.group_delta_text is not None
    assert "u0" in req.group_delta_text
    assert "u0" not in req.system_prompt
    # messages 只含 trigger
    assert req.messages == [{"role": "user", "content": "trigger"}]


@pytest.mark.asyncio
async def test_group_delta_only_after_watermark(db_session) -> None:  # type: ignore[no-untyped-def]
    ctx, _ar, msg_repo, _l1, wm, group, session, a, _b = await _setup(db_session)

    # 历史：m0, m1（已被 AgentA 看过），m2, m3（增量）
    msgs = []
    for i in range(4):
        m = Message(session_id=session.id, role=MessageRole.USER, content=f"m{i}")
        await msg_repo.save(m)
        msgs.append(m)
    await wm.set(group.id, a.id, msgs[1].id)  # 看过到 m1

    trigger = Message(session_id=session.id, role=MessageRole.USER, content="new")
    req = await ctx.build_for_agent(session=session, group=group, target_agent=a, trigger=trigger)

    # delta 应只含 m2, m3，不含 m0, m1（拆 delta 后走 group_delta_text）
    assert req.group_delta_text is not None
    assert "m2" in req.group_delta_text
    assert "m3" in req.group_delta_text
    assert "m0" not in req.group_delta_text
    assert "m1" not in req.group_delta_text


@pytest.mark.asyncio
async def test_watermark_dangling_falls_back_to_seed(db_session) -> None:  # type: ignore[no-untyped-def]
    """watermark 指向 PG 不存在的 message_id → 退化为首次接触种子历史。"""
    import uuid

    ctx, _ar, msg_repo, _l1, wm, group, session, a, _b = await _setup(db_session)

    await msg_repo.save(Message(session_id=session.id, role=MessageRole.USER, content="alive"))
    await wm.set(group.id, a.id, uuid.uuid4())  # 不存在的 message_id

    trigger = Message(session_id=session.id, role=MessageRole.USER, content="t")
    req = await ctx.build_for_agent(session=session, group=group, target_agent=a, trigger=trigger)
    # 应使用种子历史回退，而不是返回空 delta（走 group_delta_text）
    assert req.group_delta_text is not None
    assert "alive" in req.group_delta_text


@pytest.mark.asyncio
async def test_private_chat_bypasses_group_contract(db_session) -> None:  # type: ignore[no-untyped-def]
    """私聊路径：不注入 GROUP_CHAT_CONTRACT，messages 用 L1 窗口。"""
    agent_repo = PostgresAgentRepository(db_session)
    msg_repo = PostgresMessageRepository(db_session)
    a = Agent(name="AgentA", avatar="A", role="r", system_prompt="自身 prompt")
    await agent_repo.save(a)

    l1 = InMemoryL1Store(window=20)
    wm = InMemoryWatermarkStore()
    ctx = ContextBuilder(msg_repo, agent_repo, l1, wm)

    session = Session(type=SessionType.PRIVATE, agent_id=a.id)
    await l1.append(session.id, {"role": "user", "content": "前情"})

    trigger = Message(session_id=session.id, role=MessageRole.USER, content="now")
    req = await ctx.build_for_agent(session=session, group=None, target_agent=a, trigger=trigger)
    assert req.is_group_chat is False
    assert req.group_id is None
    assert req.system_prompt == "自身 prompt"
    # 私聊：messages 用 L1 全窗口
    assert any(m["content"] == "前情" for m in req.messages)
