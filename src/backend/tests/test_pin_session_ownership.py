"""P0-4 Pin 消息 session 归属校验测试。

设计现状（repo-wide，main 与本分支一致，见 sessions.py pin_message 注释）：
Pin 是个人偏好（只影响自己视图），**不强制鉴权、不强制 owner 校验**，仅保留
session 归属校验（防越权访问别人 session 的消息）。故原「other user 403」「anonymous
401」两条针对的是已废弃的强制鉴权契约，分别改为「任意 user 可 pin（无 owner 门槛）」
与移除（HTTP 层鉴权契约已不存在，服务层覆盖足够）。

当前路径：
1. owner OK — U1 pin 自己的消息 → 落库 pinned_by_user_id=U1
2. 任意 user 可 pin — U1 pin U2 的消息 → 成功（无 owner 校验，记 pinned_by=U1）
3. session 不匹配 → 422
4. 不存在 message → 404
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
    PinMessageCommand,
)
from app.application.services import SessionService
from app.core.events import InMemoryEventBus
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.agent import Agent
from app.domain.entities.message import Message
from app.domain.enums import MessageRole
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresMessageRepository,
    PostgresSessionRepository,
)


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
async def test_pin_other_user_allowed(db_session) -> None:  # type: ignore[no-untyped-def]
    """路径 2（现设计）：U1 pin U2 的消息 → 成功（无 owner 校验，pinned_by=U1）。

    Pin 是个人偏好，repo-wide 已去掉 owner 门槛（见模块 docstring）。
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

# 注：原 test_pin_route_anonymous_401（HTTP 层无 JWT → 401）测的是已废弃的强制
# 鉴权契约（repo-wide pin 现不强制鉴权，见模块 docstring），随之移除。服务层
# 4 条路径已覆盖当前契约。
