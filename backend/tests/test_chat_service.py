"""ChatService 流式 + L1 记忆集成测试（MVP 核心路径）。"""

import pytest

from app.application.commands import CreateSessionCommand, SendMessageCommand
from app.application.services import ChatService, SessionService
from app.core.events import InMemoryEventBus
from app.domain.llm.protocol import StreamEventType
from app.infrastructure.cache.memory_l1 import InMemoryL1Store
from app.infrastructure.llm.mock_adapter import MockAdapter
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresMessageRepository,
    PostgresSessionRepository,
)


@pytest.mark.asyncio
async def test_send_and_stream_private(db_session) -> None:  # type: ignore[no-untyped-def]
    from app.domain.entities.agent import Agent

    bus = InMemoryEventBus()

    # 先创建一个 mock agent
    agent_repo = PostgresAgentRepository(db_session)
    agent = Agent(name="test-mock", avatar="🤖", role="tester")
    await agent_repo.save(agent)

    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        bus,
    )
    session = await session_svc.create(
        CreateSessionCommand(type="private", agent_id=agent.id)
    )

    l1 = InMemoryL1Store(window=20)
    chat = ChatService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        PostgresAgentRepository(db_session),
        l1,
        MockAdapter(delay=0),
        bus,
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
