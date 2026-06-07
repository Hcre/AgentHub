"""P0-4 Pin 消息 session 所有权校验测试。

3 路径（per spec 04-commands §6.1.6）：
1. owner OK — U1 pin U1 自己的消息 → 204 + 落库 pinned_by_user_id=U1
2. other user 403 — U1 pin U2 的消息 → 403
3. anonymous 401 — 无 JWT pin → 401
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
from app.core.exceptions import NotFoundError, PermissionError, ValidationError
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
    """Minimal app with only sessions router（避开 deploy.py 的并行任务 bug）。

    M5 调整: endpoint 不再 401, 改 service 层做 Auto-trust. 此 fixture 增加异常处理映射
    (NotFoundError → 404) + SessionService dependency override (返回 raise NotFoundError 的 mock),
    使 test_pin_route_anonymous_404 (发送非存在 message_id) 能正确得到 404.
    """
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from app.api.deps import get_session_service
    from app.application.services import SessionService
    from app.core.exceptions import NotFoundError, PermissionError

    class _NotFoundService:
        """Mock: 任何 pin/unpin 调用都 raise NotFoundError, 模拟"消息不存在"."""

        async def pin_message(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise NotFoundError("message not found: mock")

        async def unpin_message(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise NotFoundError("message not found: mock")

    app = FastAPI()
    app.include_router(sessions_router)

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(PermissionError)
    async def _forbidden(_: Request, exc: PermissionError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    app.dependency_overrides[get_session_service] = lambda: _NotFoundService()
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
async def test_pin_other_user_403(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 2：U1 pin U2 的消息 → 403 E_MESSAGE_PIN_NOT_OWNER"""
    user_u1 = uuid4()
    user_u2 = uuid4()
    sess_id, msg_id = await _setup_session_with_message(db_session, user_id=user_u2)
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    with pytest.raises(PermissionError) as exc_info:
        await session_svc.pin_message(
            PinMessageCommand(session_id=sess_id, message_id=msg_id),
            current_user=user_u1,
        )
    assert "E_MESSAGE_PIN_NOT_OWNER" in str(exc_info.value)
    after = await PostgresMessageRepository(db_session).get_by_id(msg_id)
    assert after is not None
    assert after.pinned is False
    assert after.pinned_by_user_id is None


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


def test_pin_route_anonymous_404(client: TestClient) -> None:
    """路径 5（HTTP 层, M5 调整）：无 JWT + 不存在的 message → 404 (NotFoundError)。

    22:00 E2E Pin 401 bug fix 后, 行为变化:
    - 之前: 无 JWT → 401 (前端不发 Authorization header 必 401)
    - 现在: 无 JWT + msg 不存在 → 404 (service 层先查 message 拿不到)
    完整 401 路径需要"无 JWT + msg.user_id=None + 存在", 见 test_pin_auth.py::test_unauth_system_msg_http_401
    """
    fake_msg = uuid4()
    fake_sess = uuid4()
    resp = client.post(f"/api/messages/{fake_msg}/pin?session_id={fake_sess}")
    assert resp.status_code == 404, resp.text
