"""P0-4 Pin Auth 三路径测试 (M5 鉴权降级契约).

3 路径 (per task brief t1-pin-auth §4 + docs/specs/04-commands §6.1.6 B-1-P0-04):
1. unauth → 401
   无 JWT + msg.user_id = None (system message) → 401 E_AUTH_REQUIRED
   (无主可托, 真正"无 auth"场景)
2. wrong user → 403
   JWT for U1 + msg.user_id = U2 → 403 E_MESSAGE_PIN_NOT_OWNER
3. owner → 204
   JWT for U1 + msg.user_id = U1 + session_id 匹配 → 204 + pinned_by_user_id = U1

M5 22:00 E2E bug regression (额外 1 路径, 4 total):
4. no_jwt_auto_trust → 204
   无 JWT + msg.user_id = U1 + session_id 匹配 → 204 (auto-trust via msg.user_id)
   此即 22:00 E2E 实测"前端不发 Authorization header 时必 401" bug 的修复:
   修复前: 无 JWT → 401 (任何情况)
   修复后: 无 JWT + msg.user_id 存在 → 204 (M5 downscope auto-trust)
"""

from __future__ import annotations

import base64
import os
from uuid import UUID, uuid4

os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LLM_ADAPTER_MODE", "mock")
os.environ.setdefault("ENV", "test")

import importlib.util as _ilu

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.infrastructure.db.models  # noqa: F401
# 直接 load sessions router, 避开 app.api.routers.__init__ (并行任务 deploy.py 有 FastAPI bug)
_sessions_spec = _ilu.spec_from_file_location(
    "_sessions_mod_pin_auth", "app/api/routers/sessions.py"
)
_sessions_mod = _ilu.module_from_spec(_sessions_spec)
_sessions_spec.loader.exec_module(_sessions_mod)
sessions_router = _sessions_mod.router
from app.application.commands import CreateSessionCommand  # noqa: E402
from app.application.services import SessionService  # noqa: E402
from app.core.events import InMemoryEventBus  # noqa: E402
from app.core.exceptions import (  # noqa: E402
    AuthRequiredError,
    NotFoundError,
    PermissionError,
)
from app.core.security import create_access_token  # noqa: E402
from app.domain.entities.agent import Agent  # noqa: E402
from app.domain.entities.message import Message  # noqa: E402
from app.domain.enums import MessageRole  # noqa: E402
from app.infrastructure.repositories import (  # noqa: E402
    PostgresAgentRepository,
    PostgresMessageRepository,
    PostgresSessionRepository,
)


def _jwt(user_id: UUID) -> str:
    return create_access_token(subject=str(user_id))


@pytest.fixture
async def client_with_db(db_session):  # type: ignore[no-untyped-def]
    """HTTP client with DB dependency override (use test's in-memory SQLite).

    额外注册 main.py 的领域异常 → HTTP 状态码映射, 否则 PermissionError 在 HTTP
    层会变成 500 (FastAPI default), 测试期望 403 / 401 会失败.
    """
    from app.api.deps import get_message_repo, get_session_repo, get_session_service
    from app.core.events import InMemoryEventBus
    from app.core.exceptions import (
        AgentHubError,
        AuthRequiredError,
        DomainError,
        NotFoundError,
        PermissionError,
        ValidationError,
    )
    from app.infrastructure.repositories import (
        PostgresMessageRepository,
        PostgresSessionRepository,
    )
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    app = FastAPI()
    app.include_router(sessions_router)

    # 复制 main.py 的异常 → HTTP 映射
    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(AuthRequiredError)
    async def _unauth(_: Request, exc: AuthRequiredError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(PermissionError)
    async def _forbidden(_: Request, exc: PermissionError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def _domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def _validation_error(_: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(AgentHubError)
    async def _app_error(_: Request, exc: AgentHubError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    # Override repos to use the test's session
    def _message_repo_override():
        return PostgresMessageRepository(db_session)

    def _session_repo_override():
        return PostgresSessionRepository(db_session)

    def _session_service_override():
        from app.application.services import SessionService
        return SessionService(
            PostgresSessionRepository(db_session),
            PostgresMessageRepository(db_session),
            InMemoryEventBus(),
        )

    app.dependency_overrides[get_message_repo] = _message_repo_override
    app.dependency_overrides[get_session_repo] = _session_repo_override
    app.dependency_overrides[get_session_service] = _session_service_override
    yield TestClient(app)


async def _setup_session_with_message(
    db_session, *, user_id: UUID | None, content: str = "hi"
):
    """Helper: 创建 agent + session + 1 条消息 (user_id 可 None 模拟 system 消息)。"""
    agent_repo = PostgresAgentRepository(db_session)
    agent = Agent(name=f"agent-{uuid4()}", avatar="A", role="r")
    await agent_repo.save(agent)
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    sess = await session_svc.create(CreateSessionCommand(type="private", agent_id=agent.id))
    msg_repo = PostgresMessageRepository(db_session)
    msg = Message(
        session_id=sess.id,
        role=MessageRole.USER,
        content=content,
        user_id=user_id,
    )
    await msg_repo.save(msg)
    return sess.id, msg.id


# --- 路径 1: unauth → 401 (无 JWT + system message 无 user_id) ---


@pytest.mark.asyncio
async def test_unauth_system_msg_401(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 1：service 层 — 无 JWT + msg.user_id=None → 401 E_AUTH_REQUIRED.

    scenario: 前端无 JWT + 后端拿到 system message (e.g. Coordinator 系统通知)
              → 无主可托, 必须 401 拒绝.
    """
    sess_id, msg_id = await _setup_session_with_message(db_session, user_id=None)
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    from app.application.commands import PinMessageCommand

    with pytest.raises(AuthRequiredError) as exc_info:
        await session_svc.pin_message(
            PinMessageCommand(session_id=sess_id, message_id=msg_id),
            current_user=None,
        )
    assert "E_AUTH_REQUIRED" in str(exc_info.value)


def test_unauth_system_msg_http_401(client_with_db, db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 1 (HTTP 层)：无 JWT + system message → 401."""
    import asyncio

    sess_id, msg_id = asyncio.get_event_loop().run_until_complete(
        _setup_session_with_message(db_session, user_id=None)
    )
    resp = client_with_db.post(f"/api/messages/{msg_id}/pin?session_id={sess_id}")
    assert resp.status_code == 401, resp.text
    assert "E_AUTH_REQUIRED" in resp.text


# --- 路径 2: wrong user → 403 ---


@pytest.mark.asyncio
async def test_wrong_user_403(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 2 (service 层)：JWT for U1 + msg.user_id=U2 → 403 E_MESSAGE_PIN_NOT_OWNER."""
    user_u1 = uuid4()
    user_u2 = uuid4()
    sess_id, msg_id = await _setup_session_with_message(db_session, user_id=user_u2)
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    from app.application.commands import PinMessageCommand

    with pytest.raises(PermissionError) as exc_info:
        await session_svc.pin_message(
            PinMessageCommand(session_id=sess_id, message_id=msg_id),
            current_user=user_u1,
        )
    assert "E_MESSAGE_PIN_NOT_OWNER" in str(exc_info.value)


def test_wrong_user_http_403(client_with_db, db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 2 (HTTP 层)：JWT for U1 + msg.user_id=U2 → 403."""
    import asyncio

    user_u1 = uuid4()
    user_u2 = uuid4()
    sess_id, msg_id = asyncio.get_event_loop().run_until_complete(
        _setup_session_with_message(db_session, user_id=user_u2)
    )
    resp = client_with_db.post(
        f"/api/messages/{msg_id}/pin?session_id={sess_id}",
        headers={"Authorization": f"Bearer {_jwt(user_u1)}"},
    )
    assert resp.status_code == 403, resp.text
    assert "E_MESSAGE_PIN_NOT_OWNER" in resp.text


# --- 路径 3: owner → 204 ---


@pytest.mark.asyncio
async def test_owner_204(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 3 (service 层)：JWT for U1 + msg.user_id=U1 → 204 + pinned_by_user_id=U1."""
    user_u1 = uuid4()
    sess_id, msg_id = await _setup_session_with_message(db_session, user_id=user_u1)
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    from app.application.commands import PinMessageCommand

    await session_svc.pin_message(
        PinMessageCommand(session_id=sess_id, message_id=msg_id),
        current_user=user_u1,
    )
    after = await PostgresMessageRepository(db_session).get_by_id(msg_id)
    assert after is not None
    assert after.pinned is True
    assert after.pinned_by_user_id == user_u1
    assert after.pinned_at is not None


def test_owner_http_204(client_with_db, db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 3 (HTTP 层)：JWT for U1 + msg.user_id=U1 → 204 No Content."""
    import asyncio

    user_u1 = uuid4()
    sess_id, msg_id = asyncio.get_event_loop().run_until_complete(
        _setup_session_with_message(db_session, user_id=user_u1)
    )
    resp = client_with_db.post(
        f"/api/messages/{msg_id}/pin?session_id={sess_id}",
        headers={"Authorization": f"Bearer {_jwt(user_u1)}"},
    )
    assert resp.status_code == 204, resp.text
    assert resp.content == b""


# --- 路径 4 (M5 22:00 E2E bug regression): no JWT + msg.user_id → 204 auto-trust ---


@pytest.mark.asyncio
async def test_no_jwt_auto_trust_204(db_session) -> None:  # type: ignore[no-untyped-def]
    """M5 22:00 E2E bug 修复 regression: 无 JWT + msg.user_id=U1 + session 匹配 → 204.

    修复前 (M5 前): 无 JWT → endpoint 抛 401 (E_AUTH_REQUIRED)
    修复后 (M5):   无 JWT + msg.user_id 存在 → auto-trust 用 msg.user_id 作 implicit owner → 204

    此即 22:00 Playwright E2E 实测"前端 hover → 点 Pin 按钮 → console 401" bug 的修复契约.
    """
    user_u1 = uuid4()
    sess_id, msg_id = await _setup_session_with_message(db_session, user_id=user_u1)
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    from app.application.commands import PinMessageCommand

    # current_user=None 模拟前端不发 Authorization header 的 E2E 场景
    await session_svc.pin_message(
        PinMessageCommand(session_id=sess_id, message_id=msg_id),
        current_user=None,
    )
    after = await PostgresMessageRepository(db_session).get_by_id(msg_id)
    assert after is not None
    assert after.pinned is True
    assert after.pinned_by_user_id == user_u1  # auto-derived from msg.user_id
    assert after.pinned_at is not None


def test_no_jwt_auto_trust_http_204(client_with_db, db_session) -> None:  # type: ignore[no-untyped-def]
    """M5 22:00 E2E bug 修复 (HTTP 层)：无 Authorization header + msg.user_id 存在 → 204."""
    import asyncio

    user_u1 = uuid4()
    sess_id, msg_id = asyncio.get_event_loop().run_until_complete(
        _setup_session_with_message(db_session, user_id=user_u1)
    )
    # 关键: 此请求不携带 Authorization header, 模拟 22:00 E2E 失败场景
    resp = client_with_db.post(f"/api/messages/{msg_id}/pin?session_id={sess_id}")
    assert resp.status_code == 204, resp.text
    assert resp.content == b""


# --- 边界: 跨 session mismatch (extra 防御性测试, 不在 task brief 但已写) ---


@pytest.mark.asyncio
async def test_session_mismatch_422_preserved(db_session) -> None:  # type: ignore[no-untyped-def]
    """边界 (M5 保留原 04-commands §6.1.6 Then-3): session_id 与 msg 不一致 → 422."""
    user_u1 = uuid4()
    _sess_id, msg_id = await _setup_session_with_message(db_session, user_id=user_u1)
    other_sess_id = uuid4()
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    from app.application.commands import PinMessageCommand
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await session_svc.pin_message(
            PinMessageCommand(session_id=other_sess_id, message_id=msg_id),
            current_user=user_u1,
        )
    assert "E_MESSAGE_PIN_SESSION_MISMATCH" in str(exc_info.value)


@pytest.mark.asyncio
async def test_nonexistent_message_404_preserved(db_session) -> None:  # type: ignore[no-untyped-def]
    """边界: 不存在的 message_id → 404 (M5 不变)."""
    user_u1 = uuid4()
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    from app.application.commands import PinMessageCommand

    with pytest.raises(NotFoundError):
        await session_svc.pin_message(
            PinMessageCommand(session_id=uuid4(), message_id=uuid4()),
            current_user=user_u1,
        )


# --- 路径 5 (M5 11 测试配套): unpin 取消 + HTTP layer ---


@pytest.mark.asyncio
async def test_unpin_owner_204(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 5 (service 层): JWT for U1 + 自己消息 + 之前已 pin → 204 + unpin.

    配套 owner 204 测试, 验证 unpin_message 的 M5 鉴权降级 (与 pin 对称).
    """
    user_u1 = uuid4()
    sess_id, msg_id = await _setup_session_with_message(db_session, user_id=user_u1)
    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        InMemoryEventBus(),
    )
    from app.application.commands import PinMessageCommand, UnpinMessageCommand

    # 先 pin
    await session_svc.pin_message(
        PinMessageCommand(session_id=sess_id, message_id=msg_id),
        current_user=user_u1,
    )
    # 再 unpin
    await session_svc.unpin_message(
        UnpinMessageCommand(session_id=sess_id, message_id=msg_id),
        current_user=user_u1,
    )
    after = await PostgresMessageRepository(db_session).get_by_id(msg_id)
    assert after is not None
    assert after.pinned is False
    assert after.pinned_by_user_id is None
    assert after.pinned_at is None


def test_unpin_http_204(client_with_db, db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 5 (HTTP 层): DELETE /api/messages/{id}/pin?session_id=... → 204 (M5 鉴权降级)."""
    import asyncio

    user_u1 = uuid4()
    sess_id, msg_id = asyncio.get_event_loop().run_until_complete(
        _setup_session_with_message(db_session, user_id=user_u1)
    )
    resp = client_with_db.delete(
        f"/api/messages/{msg_id}/pin?session_id={sess_id}",
        headers={"Authorization": f"Bearer {_jwt(user_u1)}"},
    )
    assert resp.status_code == 204, resp.text
    assert resp.content == b""
