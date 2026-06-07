"""P1-2 Token 消耗监控测试（spec 04-commands §6.6 B-5.3-P1-2）。

3 路径：
1. record 计数 — record_completion + record_user_message 写入
2. 按 agent 聚合 — aggregate_by_agent 正确求和
3. 按 session 聚合 — aggregate_by_session 正确求和
"""

from __future__ import annotations

import base64
import os
from uuid import UUID

os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LLM_ADAPTER_MODE", "mock")
os.environ.setdefault("ENV", "test")

from uuid import uuid4 as _uuid4

import pytest

import app.infrastructure.db.models  # noqa: F401
from app.application.services import UsageService
from app.domain.usage import TokenCounter
from app.infrastructure.repositories import PostgresUsageRepository


@pytest.mark.asyncio
async def test_record_counters_basic(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 1：record_completion + record_user_message 写入 → 落库 2 行。"""
    svc = UsageService(PostgresUsageRepository(db_session))
    session_id = _uuid4()
    user_msg_id = _uuid4()
    agent_msg_id = _uuid4()
    agent_id = _uuid4()

    # user 消息
    user_recs = await svc.record_user_message(
        session_id=session_id, message_id=user_msg_id, content="hello world"
    )
    assert len(user_recs) == 1
    assert user_recs[0].kind == "prompt"
    assert user_recs[0].tokens > 0
    assert user_recs[0].agent_id is None

    # agent 消息
    comp_recs = await svc.record_completion(
        session_id=session_id,
        message_id=agent_msg_id,
        agent_id=agent_id,
        content="hi there",
        metadata={"token_usage": 42},  # provider 模拟
        model="mock",
    )
    assert len(comp_recs) == 1
    assert comp_recs[0].kind == "completion"
    assert comp_recs[0].tokens == 42  # 优先用 metadata
    assert comp_recs[0].agent_id == agent_id
    assert comp_recs[0].model == "mock"

    await db_session.commit()


@pytest.mark.asyncio
async def test_aggregate_by_agent(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 2：aggregate_by_agent 正确按 agent 求和 + by_session 分组。"""
    repo = PostgresUsageRepository(db_session)
    svc = UsageService(repo)
    agent_id = _uuid4()
    sess1, sess2 = _uuid4(), _uuid4()

    # 在 sess1 写 2 completion + 1 prompt
    for _ in range(2):
        await svc.record_completion(
            session_id=sess1, message_id=_uuid4(), agent_id=agent_id,
            content="x", metadata={"token_usage": 100}, model="mock",
        )
    await svc.record_user_message(session_id=sess1, message_id=_uuid4(), content="y")

    # 在 sess2 写 1 completion
    await svc.record_completion(
        session_id=sess2, message_id=_uuid4(), agent_id=agent_id,
        content="x", metadata={"token_usage": 50}, model="mock",
    )

    result = await svc.aggregate_by_agent(agent_id, window_name="24h")
    assert result["agent_id"] == str(agent_id)
    assert result["window"] == "24h"
    # prompt 记录的 agent_id=None（在 BDD §6.6 里 user 消息 agent_id 为空），
    # 所以本查询不返回 prompt 计数（per-agent 完成聚合）
    assert result["completion_tokens"] == 250  # 100*2 + 50
    assert result["total_tokens"] == 250 + result["prompt_tokens"]
    # by_session 应该按 total desc 排序
    by_session = result["by_session"]
    assert len(by_session) == 2
    assert by_session[0]["session_id"] == str(sess1)  # 200 > 50
    assert by_session[0]["completion"] == 200
    assert by_session[1]["session_id"] == str(sess2)
    assert by_session[1]["completion"] == 50

    await db_session.commit()


@pytest.mark.asyncio
async def test_aggregate_by_session(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 3：aggregate_by_session 正确按 session 求和 + by_agent 分组。"""
    repo = PostgresUsageRepository(db_session)
    svc = UsageService(repo)
    session_id = _uuid4()
    agent1, agent2 = _uuid4(), _uuid4()

    # agent1: 3 completion + 1 prompt
    for _ in range(3):
        await svc.record_completion(
            session_id=session_id, message_id=_uuid4(), agent_id=agent1,
            content="a", metadata={"token_usage": 20}, model="mock",
        )
    await svc.record_user_message(session_id=session_id, message_id=_uuid4(), content="hi")

    # agent2: 1 completion
    await svc.record_completion(
        session_id=session_id, message_id=_uuid4(), agent_id=agent2,
        content="b", metadata={"token_usage": 30}, model="mock",
    )

    result = await svc.aggregate_by_session(session_id, window_name="24h")
    assert result["session_id"] == str(session_id)
    assert result["completion_tokens"] == 90  # 20*3 + 30
    by_agent = result["by_agent"]
    assert len(by_agent) == 2
    by_agent_id = {b["agent_id"]: b for b in by_agent}
    assert by_agent_id[str(agent1)]["completion"] == 60
    assert by_agent_id[str(agent2)]["completion"] == 30

    await db_session.commit()


@pytest.mark.asyncio
async def test_token_counter_estimates_cjk_and_ascii() -> None:
    """附加：estimate_tokens 对中英文混合做估算。"""
    counter = TokenCounter()
    pure_ascii = "a" * 40
    pure_cjk = "你" * 30
    mixed = "hi 你好 world"
    assert counter.count_user_message(
        session_id=UUID(int=1), message_id=UUID(int=2), content=pure_ascii
    )[0].tokens > 0
    assert counter.count_user_message(
        session_id=UUID(int=1), message_id=UUID(int=2), content=pure_cjk
    )[0].tokens > 0
    assert counter.count_user_message(
        session_id=UUID(int=1), message_id=UUID(int=2), content=mixed
    )[0].tokens > 0
    assert counter.count_user_message(
        session_id=UUID(int=1), message_id=UUID(int=2), content=""
    ) == []
