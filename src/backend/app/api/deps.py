"""依赖注入：组装各层（架构文档 §6.3）。

FastAPI Depends 链：DB Session → Repository → Service。
LLM 适配器与 L1 记忆为进程级单例。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import (
    AgentService,
    ChatService,
    GroupService,
    SessionService,
)
from app.application.services.context_builder import ContextBuilder
from app.application.services.discussion_orchestrator import DiscussionOrchestrator
from app.application.services.selector import Selector
from app.core.events import EventBus, get_event_bus
from app.domain.llm.protocol import UnifiedAgent
from app.infrastructure.cache.memory_l1 import L1MemoryStore, RedisL1Store
from app.infrastructure.cache.redis_client import get_redis
from app.infrastructure.cache.watermark_store import RedisWatermarkStore, WatermarkStore
from app.infrastructure.db.base import get_session
from app.infrastructure.llm.factory import build_adapter
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresGroupRepository,
    PostgresMessageRepository,
    PostgresSessionRepository,
)

DbSession = Annotated[AsyncSession, Depends(get_session)]


# --- 进程级单例 ---


@lru_cache
def get_llm_adapter() -> UnifiedAgent:
    return build_adapter()


def get_l1_memory() -> L1MemoryStore:
    return RedisL1Store(get_redis())


def get_watermark_store() -> WatermarkStore:
    return RedisWatermarkStore(get_redis())


def get_bus() -> EventBus:
    return get_event_bus()


# --- 仓储（请求级，绑定当前 DB session）---


def get_agent_repo(session: DbSession) -> PostgresAgentRepository:
    return PostgresAgentRepository(session)


def get_group_repo(session: DbSession) -> PostgresGroupRepository:
    return PostgresGroupRepository(session)


def get_session_repo(session: DbSession) -> PostgresSessionRepository:
    return PostgresSessionRepository(session)


def get_message_repo(session: DbSession) -> PostgresMessageRepository:
    return PostgresMessageRepository(session)


# --- Service ---


def get_agent_service(
    repo: Annotated[PostgresAgentRepository, Depends(get_agent_repo)],
    bus: Annotated[EventBus, Depends(get_bus)],
) -> AgentService:
    return AgentService(repo, bus)


def get_group_service(
    group_repo: Annotated[PostgresGroupRepository, Depends(get_group_repo)],
    agent_repo: Annotated[PostgresAgentRepository, Depends(get_agent_repo)],
    bus: Annotated[EventBus, Depends(get_bus)],
) -> GroupService:
    return GroupService(group_repo, agent_repo, bus)


def get_session_service(
    session_repo: Annotated[PostgresSessionRepository, Depends(get_session_repo)],
    message_repo: Annotated[PostgresMessageRepository, Depends(get_message_repo)],
    bus: Annotated[EventBus, Depends(get_bus)],
) -> SessionService:
    return SessionService(session_repo, message_repo, bus)


def get_chat_service(
    session_repo: Annotated[PostgresSessionRepository, Depends(get_session_repo)],
    message_repo: Annotated[PostgresMessageRepository, Depends(get_message_repo)],
    agent_repo: Annotated[PostgresAgentRepository, Depends(get_agent_repo)],
    group_repo: Annotated[PostgresGroupRepository, Depends(get_group_repo)],
    bus: Annotated[EventBus, Depends(get_bus)],
) -> ChatService:
    l1 = get_l1_memory()
    wm = get_watermark_store()
    ctx = ContextBuilder(message_repo, agent_repo, l1, wm)
    discussion = DiscussionOrchestrator(
        message_repo=message_repo,
        agent_repo=agent_repo,
        l1_memory=l1,
        watermarks=wm,
        context_builder=ctx,
        selector=Selector(),
        event_bus=bus,
    )
    return ChatService(
        session_repo,
        message_repo,
        agent_repo,
        group_repo,
        l1,
        wm,
        ctx,
        discussion,
        get_llm_adapter(),
        bus,
    )


# 供 WebSocket 处理器手动构造 Service（WS 不走 Depends 链）
async def build_chat_service_for_ws() -> AsyncIterator[ChatService]:
    async for session in get_session():
        msg_repo = PostgresMessageRepository(session)
        agent_repo = PostgresAgentRepository(session)
        group_repo = PostgresGroupRepository(session)
        l1 = get_l1_memory()
        wm = get_watermark_store()
        ctx = ContextBuilder(msg_repo, agent_repo, l1, wm)
        bus = get_event_bus()
        discussion = DiscussionOrchestrator(
            message_repo=msg_repo,
            agent_repo=agent_repo,
            l1_memory=l1,
            watermarks=wm,
            context_builder=ctx,
            selector=Selector(),
            event_bus=bus,
        )
        yield ChatService(
            PostgresSessionRepository(session),
            msg_repo,
            agent_repo,
            group_repo,
            l1,
            wm,
            ctx,
            discussion,
            get_llm_adapter(),
            bus,
        )
