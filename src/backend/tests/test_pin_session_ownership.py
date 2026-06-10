"""P0-4 Pin 消息 session 校验测试。

鉴权口径（commit 11b4c6c 起）：pin 是个人偏好，前端无登录流程，故**不强制 JWT、不强制
owner**——只保留 session 归属校验（防把消息 pin 进不属于它的 session）。本文件断言这套
放宽后的契约：
1. owner pin 自己的消息 → 落库 pinned + pinned_by_user_id
2. 非 owner 也能 pin（放宽后无 owner 门槛）
3. session 不匹配 → 422
4. 不存在的 message → 404
5. 匿名 HTTP 请求不被 401 拦截（路由已无 CurrentUser 依赖）
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
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.infrastructure.db.models  # noqa: F401
# 直接 load 文件，避开 app.api.routers.__init__（并行任务 deploy.py 有 FastAPI bug）
import importlib.util as _ilu
_sessions_spec = _ilu.spec_from_file_location("_sessions_mod", "app/api/routers/sessions.py")
_sessions_mod = _ilu.module_from_spec(_sessions_spec)
_sessions_spec.loader.exec_module(_sessions_mod)
sessions_router = _sessions_mod.router
from app.application.commands import (
    CreateSessionCommand,
    PinMessageCommand,
)
from app.application.services import SessionService
from app.core.events import InMemoryEventBus
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import create_access_token
from app.domain.entities.agent import Agent
from app.domain.entities.message import Message
from app.domain.enums import MessageRole
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresMessageRepository,
    PostgresSessionRepository,
)


def _jwt(user_id: UUID) -> str:
    return create_access_token(subject=str(user_id))


@pytest.fixture
def client() -> TestClient:
    """Minimal app with only sessions router（避开 deploy.py 的并行任务 bug）。"""
    app = FastAPI()
    app.include_router(sessions_router)
    return TestClient(app)


async def _setup_session_with_message(db_session, *, user_id: UUID | None, content: str = "hi"):
    """Helper: 创建 agent + session + 1 条 user 消息（带 user_id）。"""
    agent_repo = PostgresAgentRepository(db_session)
    agent = Agent(name=f"agent-{user_id}", avatar="A", role="r")
    await agent_repo.save(agent)
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    sess = await session_svc.create(CreateSessionCommand(type="private", agent_id=agent.id))
    msg_repo = PostgresMessageRepository(db_session)
    msg = Message(
        session_id=sess.id, role=MessageRole.USER, content=content, user_id=user_id
    )
    await msg_repo.save(msg)
    return sess.id, msg.id


@pytest.mark.asyncio
async def test_pin_owner_ok(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 1：U1 pin U1 自己的消息 → 204 + pinned_by_user_id=U1"""
    user_u1 = uuid4()
    sess_id, msg_id = await _setup_session_with_message(db_session, user_id=user_u1)
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    await session_svc.pin_message(
        PinMessageCommand(session_id=sess_id, message_id=msg_id),
        current_user=user_u1,
    )
    after = await PostgresMessageRepository(db_session).get_by_id(msg_id)
    assert after is not None
    assert after.pinned is True
    assert after.pinned_by_user_id == user_u1
    assert after.pinned_at is not None


@pytest.mark.asyncio
async def test_pin_non_owner_allowed(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 2（放宽后）：U1 pin U2 的消息 → 成功（无 owner 门槛）。

    commit 11b4c6c 移除了 owner 校验：pin 是个人偏好，不该有"必须本人"门槛。
    """
    user_u1 = uuid4()
    user_u2 = uuid4()
    sess_id, msg_id = await _setup_session_with_message(db_session, user_id=user_u2)
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    await session_svc.pin_message(
        PinMessageCommand(session_id=sess_id, message_id=msg_id),
        current_user=user_u1,
    )
    after = await PostgresMessageRepository(db_session).get_by_id(msg_id)
    assert after is not None
    assert after.pinned is True
    assert after.pinned_by_user_id == user_u1


@pytest.mark.asyncio
async def test_pin_session_mismatch_422(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 3（边界）：M1 不在 query session_id → 422"""
    user_u1 = uuid4()
    _sess_id, msg_id = await _setup_session_with_message(db_session, user_id=user_u1)
    other_sess_id = uuid4()
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    with pytest.raises(ValidationError) as exc_info:
        await session_svc.pin_message(
            PinMessageCommand(session_id=other_sess_id, message_id=msg_id),
            current_user=user_u1,
        )
    assert "E_MESSAGE_PIN_SESSION_MISMATCH" in str(exc_info.value)


@pytest.mark.asyncio
async def test_pin_nonexistent_404(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 4（边界）：不存在的 message_id → 404"""
    user_u1 = uuid4()
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    with pytest.raises(NotFoundError):
        await session_svc.pin_message(
            PinMessageCommand(session_id=uuid4(), message_id=uuid4()),
            current_user=user_u1,
        )


def test_pin_route_no_auth_required(client: TestClient) -> None:
    """路径 5（HTTP 层）：匿名（无 JWT）请求不被 401 拦截。

    commit 11b4c6c 移除了 pin 路由的 CurrentUser 依赖。这里用 fake service 覆盖
    `get_session_service`，断言匿名 POST 直达 service 并返回 204（证明无鉴权门槛）。
    """
    calls: list[tuple] = []

    class _FakeSvc:
        async def pin_message(self, cmd) -> None:  # type: ignore[no-untyped-def]
            calls.append((cmd.session_id, cmd.message_id))

    from app.api.deps import get_session_service

    client.app.dependency_overrides[get_session_service] = lambda: _FakeSvc()
    try:
        msg_id = uuid4()
        sess_id = uuid4()
        resp = client.post(f"/api/messages/{msg_id}/pin?session_id={sess_id}")
        assert resp.status_code == 204, resp.text
        assert calls == [(sess_id, msg_id)]
    finally:
        client.app.dependency_overrides.clear()
