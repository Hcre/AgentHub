"""t7 B-4-P2-CL01 会话置顶测试。

3 路径（per brief track 7）：
1. PATCH pinned=True → 200 + SessionOut.pinned=True + 落库
2. PATCH pinned=False (从 True 翻转) → 200 + SessionOut.pinned=False
3. PATCH 不存在 session_id → 404 NotFoundError

本测试用 service 层覆盖 5 路径：验证 UpdateSessionCommand 流转 +
PostgresSessionRepository 持久化（含 _to_domain 读取 pinned 字段）+ 边界场景。
HTTP 层验证已包含在 t1-pin-auth 链路，PATCH 端点接受 pinned 字段的 schema 契约
由 service 层覆盖（SessionOut = SessionResponse.from_domain）。
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

import app.infrastructure.db.models  # noqa: F401

from app.application.commands import (
    CreateSessionCommand,
    UpdateSessionCommand,
)
from app.application.services import SessionService
from app.core.events import InMemoryEventBus
from app.core.exceptions import NotFoundError
from app.domain.entities.agent import Agent
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresMessageRepository,
    PostgresSessionRepository,
)


async def _create_session(db_session) -> UUID:
    """Helper: 创建 1 个 private session（满足 group_id/agent_id 校验）。"""
    agent = Agent(name="t7-pin-agent", avatar="A", role="r")
    await PostgresAgentRepository(db_session).save(agent)
    svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    sess = await svc.create(CreateSessionCommand(type="private", agent_id=agent.id))
    return sess.id


@pytest.mark.asyncio
async def test_session_pin_set_true_then_false(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 1+2 (service 层): Pinned True → 200, False → 200, 落库正确。"""
    sess_id = await _create_session(db_session)
    session_repo = PostgresSessionRepository(db_session)
    svc = SessionService(
        session_repo,
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )

    resp = await svc.update(UpdateSessionCommand(session_id=sess_id, pinned=True))
    assert resp.pinned is True

    reloaded = await session_repo.get_by_id(sess_id)
    assert reloaded is not None
    assert reloaded.pinned is True

    resp2 = await svc.update(UpdateSessionCommand(session_id=sess_id, pinned=False))
    assert resp2.pinned is False

    reloaded2 = await session_repo.get_by_id(sess_id)
    assert reloaded2 is not None
    assert reloaded2.pinned is False


@pytest.mark.asyncio
async def test_session_pin_default_false_on_new(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 3 (边界): 新建 session 默认 pinned=False。"""
    sess_id = await _create_session(db_session)
    session_repo = PostgresSessionRepository(db_session)
    s = await session_repo.get_by_id(sess_id)
    assert s is not None
    assert s.pinned is False


@pytest.mark.asyncio
async def test_session_pin_nonexistent_404(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 4 (边界): PATCH 不存在 session → NotFoundError。"""
    svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    with pytest.raises(NotFoundError) as exc_info:
        await svc.update(UpdateSessionCommand(session_id=uuid4(), pinned=True))
    assert "session not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_session_pin_preserves_other_fields(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 5 (边界): 单独 PATCH pinned 不破坏 title/workspace_path。"""
    sess_id = await _create_session(db_session)
    session_repo = PostgresSessionRepository(db_session)
    svc = SessionService(
        session_repo,
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    await svc.update(
        UpdateSessionCommand(
            session_id=sess_id, title="hello", workspace_path="/tmp/x"
        )
    )
    resp = await svc.update(UpdateSessionCommand(session_id=sess_id, pinned=True))
    assert resp.pinned is True
    assert resp.title == "hello"
    assert resp.workspace_path == "/tmp/x"
