"""M1#2 会话归档持久化测试（service 层 + repository 落库 + 边界）。

三路径（T-03）：
1. 正常：update archived=True → 落库 → get_by_id 读回 True；翻转 False 同理
2. 边界：新建 session 默认 archived=False
3. 边界：单独 PATCH archived 不破坏 pinned / title / workspace_path
"""

from __future__ import annotations

import base64
import os

os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LLM_ADAPTER_MODE", "mock")
os.environ.setdefault("ENV", "test")

import pytest

import app.infrastructure.db.models  # noqa: F401
from app.application.commands import CreateSessionCommand, UpdateSessionCommand
from app.application.services import SessionService
from app.core.events import InMemoryEventBus
from app.domain.entities.agent import Agent
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresMessageRepository,
    PostgresSessionRepository,
)


async def _make_service(db_session) -> SessionService:  # type: ignore[no-untyped-def]
    return SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )


async def _create_session(db_session):  # type: ignore[no-untyped-def]
    agent = Agent(name="m1-2-archive-agent", avatar="A", role="r")
    await PostgresAgentRepository(db_session).save(agent)
    svc = await _make_service(db_session)
    sess = await svc.create(CreateSessionCommand(type="private", agent_id=agent.id))
    return sess.id


@pytest.mark.asyncio
async def test_archive_set_true_then_false_persists(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 1：archived True → 落库 True；翻转 False → 落库 False。"""
    sess_id = await _create_session(db_session)
    repo = PostgresSessionRepository(db_session)
    svc = await _make_service(db_session)

    resp = await svc.update(UpdateSessionCommand(session_id=sess_id, archived=True))
    assert resp.archived is True
    reloaded = await repo.get_by_id(sess_id)
    assert reloaded is not None and reloaded.archived is True

    resp2 = await svc.update(UpdateSessionCommand(session_id=sess_id, archived=False))
    assert resp2.archived is False
    reloaded2 = await repo.get_by_id(sess_id)
    assert reloaded2 is not None and reloaded2.archived is False


@pytest.mark.asyncio
async def test_new_session_archived_defaults_false(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 2（边界）：新建 session 默认 archived=False。"""
    sess_id = await _create_session(db_session)
    s = await PostgresSessionRepository(db_session).get_by_id(sess_id)
    assert s is not None and s.archived is False


@pytest.mark.asyncio
async def test_archive_preserves_other_fields(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 3（边界）：单独 PATCH archived 不破坏 pinned / title / workspace_path。"""
    sess_id = await _create_session(db_session)
    svc = await _make_service(db_session)

    await svc.update(
        UpdateSessionCommand(
            session_id=sess_id, title="keep", workspace_path="/tmp/keep", pinned=True
        )
    )
    resp = await svc.update(UpdateSessionCommand(session_id=sess_id, archived=True))
    assert resp.archived is True
    assert resp.pinned is True
    assert resp.title == "keep"
    assert resp.workspace_path == "/tmp/keep"
