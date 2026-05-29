"""ChatService 流式 + L1 记忆集成测试（MVP 核心路径）。"""

import pytest

from app.application.commands import CreateSessionCommand, SendMessageCommand
from app.application.services import ChatService, SessionService
from app.application.services.context_builder import ContextBuilder
from app.application.services.discussion_orchestrator import DiscussionOrchestrator
from app.application.services.selector import Selector
from app.core.events import InMemoryEventBus
from app.domain.llm.protocol import StreamEventType
from app.infrastructure.cache.memory_l1 import InMemoryL1Store
from app.infrastructure.cache.watermark_store import InMemoryWatermarkStore
from app.infrastructure.llm.mock_adapter import MockAdapter
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresGroupRepository,
    PostgresMessageRepository,
    PostgresSessionRepository,
)


def _build_chat(db_session, *, adapter=None):  # type: ignore[no-untyped-def]
    bus = InMemoryEventBus()
    msg_repo = PostgresMessageRepository(db_session)
    agent_repo = PostgresAgentRepository(db_session)
    group_repo = PostgresGroupRepository(db_session)
    l1 = InMemoryL1Store(window=20)
    wm = InMemoryWatermarkStore()
    ctx = ContextBuilder(msg_repo, agent_repo, l1, wm)
    discussion = DiscussionOrchestrator(
        message_repo=msg_repo,
        agent_repo=agent_repo,
        l1_memory=l1,
        watermarks=wm,
        context_builder=ctx,
        selector=Selector(),
        event_bus=bus,
    )
    chat = ChatService(
        PostgresSessionRepository(db_session),
        msg_repo,
        agent_repo,
        group_repo,
        l1,
        wm,
        ctx,
        discussion,
        adapter or MockAdapter(delay=0),
        bus,
    )
    return chat, l1, wm, bus


@pytest.mark.asyncio
async def test_send_and_stream_private(db_session) -> None:  # type: ignore[no-untyped-def]
    from app.domain.entities.agent import Agent

    # 先创建一个 mock agent
    agent_repo = PostgresAgentRepository(db_session)
    agent = Agent(name="test-mock", avatar="🤖", role="tester")
    await agent_repo.save(agent)

    chat, l1, _wm, bus = _build_chat(db_session)

    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        bus,
    )
    session = await session_svc.create(
        CreateSessionCommand(type="private", agent_id=agent.id)
    )

    events = [
        e async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="你好")
        )
    ]
    assert events[-1].type == StreamEventType.DONE
    assert any(e.type == StreamEventType.TEXT for e in events)

    # L1 记忆应包含 user + assistant 两条
    window = await l1.get_window(session.id)
    assert len(window) == 2
    assert window[0]["role"] == "user"
    assert window[1]["role"] == "assistant"

    # 历史落库
    msgs = await session_svc.list_messages(session.id)
    assert len(msgs) == 2


@pytest.mark.asyncio
async def test_group_at_routing_single_mention(db_session) -> None:  # type: ignore[no-untyped-def]
    """群聊 V1：用户 @ 单个 Agent → 该 Agent 流式回复，watermark 推进。"""
    from app.domain.entities.agent import Agent
    from app.domain.entities.group import Group
    from app.domain.entities.session import Session
    from app.domain.enums import SessionType

    agent_repo = PostgresAgentRepository(db_session)
    coord = Agent(name="协调者", avatar="C", role="coordinator", is_system=True)
    a = Agent(name="AgentA", avatar="A", role="前端")
    b = Agent(name="AgentB", avatar="B", role="后端")
    for ag in (coord, a, b):
        await agent_repo.save(ag)

    group_repo = PostgresGroupRepository(db_session)
    group = Group(
        name="proj-x", coordinator_id=coord.id, member_ids=[a.id, b.id]
    )
    await group_repo.save(group)

    session_repo = PostgresSessionRepository(db_session)
    session = Session(type=SessionType.GROUP, group_id=group.id, title="g")
    await session_repo.save(session)

    chat, _l1, wm, _bus = _build_chat(db_session)

    events = [
        e async for e in chat.send_and_stream(
            SendMessageCommand(
                session_id=session.id, content="@AgentA 帮我看看", mentions=["AgentA"]
            )
        )
    ]
    assert events[-1].type == StreamEventType.DONE
    text_events = [e for e in events if e.type == StreamEventType.TEXT]
    assert text_events, "应有 TEXT 事件"
    assert all(e.sender_agent_id == a.id for e in text_events), (
        "所有 TEXT 事件都应携带 AgentA 的 sender_agent_id"
    )

    # AgentA 的 watermark 应被推进
    assert await wm.get(group.id, a.id) is not None
    # AgentB 未被 @，不该有 watermark
    assert await wm.get(group.id, b.id) is None


@pytest.mark.asyncio
async def test_group_at_routing_multi_mention_serial(db_session) -> None:  # type: ignore[no-untyped-def]
    """群聊 V1：多 @ 串行执行，每个 Agent 各自落库 + 推 watermark。"""
    from app.domain.entities.agent import Agent
    from app.domain.entities.group import Group
    from app.domain.entities.session import Session
    from app.domain.enums import SessionType

    agent_repo = PostgresAgentRepository(db_session)
    coord = Agent(name="协调者", avatar="C", role="coordinator", is_system=True)
    a = Agent(name="AgentA", avatar="A", role="前端")
    b = Agent(name="AgentB", avatar="B", role="后端")
    for ag in (coord, a, b):
        await agent_repo.save(ag)

    group = Group(name="g2", coordinator_id=coord.id, member_ids=[a.id, b.id])
    await PostgresGroupRepository(db_session).save(group)

    session = Session(type=SessionType.GROUP, group_id=group.id, title="g")
    await PostgresSessionRepository(db_session).save(session)

    chat, _l1, wm, _bus = _build_chat(db_session)
    events = [
        e async for e in chat.send_and_stream(
            SendMessageCommand(
                session_id=session.id,
                content="@AgentA @AgentB 一起看下",
                mentions=["AgentA", "AgentB"],
            )
        )
    ]
    senders = {e.sender_agent_id for e in events if e.sender_agent_id}
    assert senders == {a.id, b.id}, "两个 Agent 都应该有发言"

    assert await wm.get(group.id, a.id) is not None
    assert await wm.get(group.id, b.id) is not None


@pytest.mark.asyncio
async def test_group_no_mention_silent(db_session) -> None:  # type: ignore[no-untyped-def]
    """死群兜底：无 @ + AT_ROUTING 模式 → 静默，无 Agent 响应。"""
    from app.domain.entities.agent import Agent
    from app.domain.entities.group import Group
    from app.domain.entities.session import Session
    from app.domain.enums import DispatchMode, SessionType

    agent_repo = PostgresAgentRepository(db_session)
    coord = Agent(name="协调者", avatar="C", role="c", is_system=True)
    a = Agent(name="AgentA", avatar="A", role="r")
    for ag in (coord, a):
        await agent_repo.save(ag)

    group = Group(name="g3", coordinator_id=coord.id, member_ids=[a.id])
    group.set_dispatch_mode(DispatchMode.AT_ROUTING)  # 显式降级
    await PostgresGroupRepository(db_session).save(group)
    session = Session(type=SessionType.GROUP, group_id=group.id, title="g")
    await PostgresSessionRepository(db_session).save(session)

    chat, _l1, wm, _bus = _build_chat(db_session)
    events = [
        e async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="大家好")
        )
    ]
    assert events == []
    assert await wm.get(group.id, a.id) is None


@pytest.mark.asyncio
async def test_group_invalid_mention_skipped(db_session) -> None:  # type: ignore[no-untyped-def]
    """@ 不存在的 Agent → 跳过；非群成员 Agent → 跳过。"""
    from app.domain.entities.agent import Agent
    from app.domain.entities.group import Group
    from app.domain.entities.session import Session
    from app.domain.enums import SessionType

    agent_repo = PostgresAgentRepository(db_session)
    coord = Agent(name="协调者", avatar="C", role="c", is_system=True)
    a = Agent(name="AgentA", avatar="A", role="r")
    outsider = Agent(name="Outsider", avatar="X", role="r")
    for ag in (coord, a, outsider):
        await agent_repo.save(ag)

    group = Group(name="g4", coordinator_id=coord.id, member_ids=[a.id])
    await PostgresGroupRepository(db_session).save(group)
    session = Session(type=SessionType.GROUP, group_id=group.id, title="g")
    await PostgresSessionRepository(db_session).save(session)

    chat, _l1, _wm, _bus = _build_chat(db_session)
    events = [
        e async for e in chat.send_and_stream(
            SendMessageCommand(
                session_id=session.id,
                content="@AgentA @Outsider @NotExist 测试",
                mentions=["AgentA", "Outsider", "NotExist"],
            )
        )
    ]
    senders = {e.sender_agent_id for e in events if e.sender_agent_id}
    # 只有 AgentA 被有效路由
    assert senders == {a.id}
