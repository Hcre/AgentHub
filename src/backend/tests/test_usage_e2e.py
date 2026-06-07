"""P1-2 Token 消耗监控 E2E 测试（spec 04-commands §6.6 B-5.3-P1-2 全链路 E2E）。

3 路径（per Task brief）：
1. test_usage_1h_window — 发 5 条消息 → record_completion 自动触发 → /api/usage?window=1h
   应看到 5 条 completion 记录（assert sum == 5 completion count）
2. test_usage_24h_window — 同上 + 把记录 created_at 回拨 23h → 1h window 不见
   → 24h window 仍可见 + 把另一批回拨 25h → 24h window 不见
3. test_usage_7d_window — 把记录回拨 6d → 24h window 不见 → 7d window 仍可见
   + 把另一批回拨 8d → 7d window 不见

时间旅行策略：直接 UPDATE usage_records.created_at（避免引入 freezegun）。
E2E 路径走 ChatService.send_and_stream 全栈，验证 record_completion 在 LLM 完成后真触发。
"""

from __future__ import annotations

import base64
import os
from uuid import UUID, uuid4

os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LLM_ADAPTER_MODE", "mock")
os.environ.setdefault("ENV", "test")

import pytest
from sqlalchemy import update

import app.infrastructure.db.models  # noqa: F401
from app.application.commands import CreateSessionCommand, SendMessageCommand
from app.application.services import ChatService, SessionService, UsageService
from app.application.services.context_builder import ContextBuilder
from app.application.services.discussion_orchestrator import DiscussionOrchestrator
from app.application.services.selector import Selector
from app.core.events import InMemoryEventBus
from app.domain.llm.protocol import StreamEventType
from app.domain.usage.usage_record import USAGE_KIND_COMPLETION
from app.infrastructure.cache.memory_l1 import InMemoryL1Store
from app.infrastructure.cache.watermark_store import InMemoryWatermarkStore
from app.infrastructure.db.models import UsageRecordModel
from app.infrastructure.llm.mock_adapter import MockAdapter
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresGroupRepository,
    PostgresMessageRepository,
    PostgresSessionRepository,
    PostgresUsageRepository,
)


def _build_chat_with_usage(db_session, *, adapter=None):  # type: ignore[no-untyped-def]
    """带 UsageService 注入的 ChatService 工厂（与 deps.py.get_chat_service 保持一致）。"""
    bus = InMemoryEventBus()
    msg_repo = PostgresMessageRepository(db_session)
    agent_repo = PostgresAgentRepository(db_session)
    group_repo = PostgresGroupRepository(db_session)
    l1 = InMemoryL1Store(window=20)
    wm = InMemoryWatermarkStore()
    ctx = ContextBuilder(msg_repo, agent_repo, l1, wm)
    usage_svc = UsageService(PostgresUsageRepository(db_session))
    discussion = DiscussionOrchestrator(
        message_repo=msg_repo,
        agent_repo=agent_repo,
        l1_memory=l1,
        watermarks=wm,
        context_builder=ctx,
        selector=Selector(),
        event_bus=bus,
        usage_service=usage_svc,
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
        usage_service=usage_svc,
    )
    return chat, usage_svc, bus


async def _backdate_records(db_session, *, hours: int) -> None:
    """把当前 session 内所有 usage_records 的 created_at 统一回拨 N 小时（测试用）。"""
    from datetime import UTC, datetime, timedelta

    new_ts = datetime.now(UTC) - timedelta(hours=hours)
    await db_session.execute(
        update(UsageRecordModel).values(created_at=new_ts)
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_usage_1h_window(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 1：1h window — 发 5 条消息 → record_completion 自动触发 5 次
    → /api/usage?window=1h 看到 5 条 completion。
    """
    from app.domain.entities.agent import Agent

    agent = Agent(name="usage-mock-1h", avatar="U", role="usage")
    await PostgresAgentRepository(db_session).save(agent)

    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    session = await session_svc.create(CreateSessionCommand(type="private", agent_id=agent.id))

    chat, usage_svc, _bus = _build_chat_with_usage(db_session)

    # 发 5 条消息
    for i in range(5):
        events = [
            e
            async for e in chat.send_and_stream(
                SendMessageCommand(session_id=session.id, content=f"msg-{i}")
            )
        ]
        assert events[-1].type == StreamEventType.DONE

    # 1h window 应见 5 completion
    result = await usage_svc.aggregate_by_session(session.id, window_name="1h")
    assert result["session_id"] == str(session.id)
    assert result["window"] == "1h"
    assert result["completion_tokens"] > 0
    by_agent = result["by_agent"]
    assert len(by_agent) == 1
    assert by_agent[0]["completion"] > 0
    # 直查 DB：5 条 prompt + 5 条 completion
    from sqlalchemy import select as _select

    rows = (
        await db_session.execute(
            _select(UsageRecordModel).where(UsageRecordModel.session_id == session.id)
        )
    ).scalars().all()
    completion_rows = [r for r in rows if r.kind == USAGE_KIND_COMPLETION]
    prompt_rows = [r for r in rows if r.kind == "prompt"]
    assert len(completion_rows) == 5
    assert len(prompt_rows) == 5


@pytest.mark.asyncio
async def test_usage_24h_window(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 2：24h window — 发 5 条后回拨 23h → 24h window 仍可见
    + 把另一批回拨 25h → 24h window 不见。
    """
    from app.domain.entities.agent import Agent

    # 准备：发 5 条（在 1h 窗口内）
    agent1 = Agent(name="usage-mock-24h-recent", avatar="U", role="usage")
    await PostgresAgentRepository(db_session).save(agent1)
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    session1 = await session_svc.create(
        CreateSessionCommand(type="private", agent_id=agent1.id)
    )

    chat1, usage_svc1, _bus1 = _build_chat_with_usage(db_session)
    for i in range(5):
        events = [
            e
            async for e in chat1.send_and_stream(
                SendMessageCommand(session_id=session1.id, content=f"recent-{i}")
            )
        ]
        assert events[-1].type == StreamEventType.DONE

    # 把 session1 的记录回拨 23h（仍在 24h 窗口内）
    from sqlalchemy import update as _update, select as _select
    from datetime import UTC, datetime, timedelta

    # 校验：session1 共有 10 条（5 prompt + 5 completion）
    sess1_rows = (
        await db_session.execute(
            _select(UsageRecordModel).where(UsageRecordModel.session_id == session1.id)
        )
    ).scalars().all()
    assert len(sess1_rows) == 10
    assert sum(1 for r in sess1_rows if r.kind == "prompt") == 5
    assert sum(1 for r in sess1_rows if r.kind == USAGE_KIND_COMPLETION) == 5

    await db_session.execute(
        _update(UsageRecordModel)
        .where(UsageRecordModel.session_id == session1.id)
        .values(created_at=datetime.now(UTC) - timedelta(hours=23))
    )

    # 1h window 不见
    result_1h = await usage_svc1.aggregate_by_session(session1.id, window_name="1h")
    assert result_1h["completion_tokens"] == 0

    # 24h window 仍见
    result_24h = await usage_svc1.aggregate_by_session(session1.id, window_name="24h")
    assert result_24h["completion_tokens"] > 0
    assert len(result_24h["by_agent"]) == 1
    assert result_24h["by_agent"][0]["completion"] > 0

    # 再发 5 条到 session2 → 回拨 25h（24h 窗口外）
    agent2 = Agent(name="usage-mock-24h-old", avatar="U", role="usage")
    await PostgresAgentRepository(db_session).save(agent2)
    session2 = await session_svc.create(
        CreateSessionCommand(type="private", agent_id=agent2.id)
    )
    chat2, usage_svc2, _bus2 = _build_chat_with_usage(db_session)
    for i in range(5):
        events = [
            e
            async for e in chat2.send_and_stream(
                SendMessageCommand(session_id=session2.id, content=f"old-{i}")
            )
        ]
        assert events[-1].type == StreamEventType.DONE

    # 把 session2 的记录回拨 25h
    await db_session.execute(
        _update(UsageRecordModel)
        .where(UsageRecordModel.session_id == session2.id)
        .values(created_at=datetime.now(UTC) - timedelta(hours=25))
    )

    # 24h window 不见 session2（25h 外）
    result_s2_24h = await usage_svc2.aggregate_by_session(session2.id, window_name="24h")
    assert result_s2_24h["completion_tokens"] == 0

    # 24h window 仍见 session1（23h 内）
    result_s1_24h_again = await usage_svc1.aggregate_by_session(session1.id, window_name="24h")
    assert result_s1_24h_again["completion_tokens"] > 0


@pytest.mark.asyncio
async def test_usage_7d_window(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 3：7d window — 发 5 条后回拨 6d → 7d 仍可见 + 24h 不见
    + 把另一批回拨 8d → 7d 也不见。
    """
    from app.domain.entities.agent import Agent
    from sqlalchemy import update as _update
    from datetime import UTC, datetime, timedelta

    # session1: 5 条 → 回拨 6d（7d 内 / 24h 外）
    agent1 = Agent(name="usage-mock-7d-in", avatar="U", role="usage")
    await PostgresAgentRepository(db_session).save(agent1)
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    session1 = await session_svc.create(
        CreateSessionCommand(type="private", agent_id=agent1.id)
    )
    chat1, usage_svc1, _bus1 = _build_chat_with_usage(db_session)
    for i in range(5):
        events = [
            e
            async for e in chat1.send_and_stream(
                SendMessageCommand(session_id=session1.id, content=f"week-ago-{i}")
            )
        ]
        assert events[-1].type == StreamEventType.DONE

    await db_session.execute(
        _update(UsageRecordModel)
        .where(UsageRecordModel.session_id == session1.id)
        .values(created_at=datetime.now(UTC) - timedelta(days=6))
    )

    # 24h window 不见
    result_24h = await usage_svc1.aggregate_by_session(session1.id, window_name="24h")
    assert result_24h["completion_tokens"] == 0

    # 7d window 仍见
    result_7d = await usage_svc1.aggregate_by_session(session1.id, window_name="7d")
    assert result_7d["completion_tokens"] > 0
    assert len(result_7d["by_agent"]) == 1
    assert result_7d["by_agent"][0]["completion"] > 0

    # session2: 5 条 → 回拨 8d（7d 外）
    agent2 = Agent(name="usage-mock-7d-out", avatar="U", role="usage")
    await PostgresAgentRepository(db_session).save(agent2)
    session2 = await session_svc.create(
        CreateSessionCommand(type="private", agent_id=agent2.id)
    )
    chat2, usage_svc2, _bus2 = _build_chat_with_usage(db_session)
    for i in range(5):
        events = [
            e
            async for e in chat2.send_and_stream(
                SendMessageCommand(session_id=session2.id, content=f"two-weeks-{i}")
            )
        ]
        assert events[-1].type == StreamEventType.DONE

    await db_session.execute(
        _update(UsageRecordModel)
        .where(UsageRecordModel.session_id == session2.id)
        .values(created_at=datetime.now(UTC) - timedelta(days=8))
    )

    # 7d window 也不见
    result_s2_7d = await usage_svc2.aggregate_by_session(session2.id, window_name="7d")
    assert result_s2_7d["completion_tokens"] == 0


@pytest.mark.asyncio
async def test_record_completion_triggered_in_chat_service(db_session) -> None:  # type: ignore[no-untyped-def]
    """附加：验证 record_completion 触发点真在 ChatService LLM 完成路径上 —
    一次 send_and_stream 后 UsageRecord 表里应该出现 1 条 prompt + 1 条 completion。
    """
    from app.domain.entities.agent import Agent
    from sqlalchemy import select

    agent = Agent(name="usage-trigger-check", avatar="U", role="usage")
    await PostgresAgentRepository(db_session).save(agent)
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    session = await session_svc.create(CreateSessionCommand(type="private", agent_id=agent.id))

    chat, _usage_svc, _bus = _build_chat_with_usage(db_session)
    events = [
        e
        async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="trigger check")
        )
    ]
    assert events[-1].type == StreamEventType.DONE

    # 直查 DB：应见 1 prompt + 1 completion
    rows = (
        await db_session.execute(
            select(UsageRecordModel).where(UsageRecordModel.session_id == session.id)
        )
    ).scalars().all()
    assert len(rows) == 2
    kinds = {r.kind for r in rows}
    assert "prompt" in kinds
    assert USAGE_KIND_COMPLETION in kinds
    completion = next(r for r in rows if r.kind == USAGE_KIND_COMPLETION)
    assert completion.agent_id == agent.id
    assert completion.tokens > 0
    assert completion.model == "mock"  # MockAdapter DONE 事件 metadata 携带 model
