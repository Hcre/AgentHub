"""依赖注入：组装各层（架构文档 §6.3）。

FastAPI Depends 链：DB Session → Repository → Service。
LLM 适配器与 L1 记忆为进程级单例。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import (
    AgentService,
    ChatService,
    GroupService,
    McpInstallService,
    McpMarketService,
    MemoryService,
    SessionService,
)
from app.application.services.context_builder import ContextBuilder
from app.application.services.discussion_orchestrator import DiscussionOrchestrator
from app.application.services.memory_selector import MemorySelector
from app.application.services.selector import Selector
from app.core.events import EventBus, get_event_bus
from app.core.security import decode_access_token
from app.domain.llm.protocol import UnifiedAgent
from app.infrastructure.cache.memory_l1 import L1MemoryStore, RedisL1Store
from app.infrastructure.cache.redis_client import get_redis
from app.infrastructure.cache.watermark_store import RedisWatermarkStore, WatermarkStore
from app.infrastructure.db.base import get_session
from app.infrastructure.llm.factory import build_adapter
from app.infrastructure.mcp import LocalMcpInstaller
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresGroupRepository,
    PostgresMcpInstallationRepository,
    PostgresMcpServerRepository,
    PostgresMemoryRepository,
    PostgresMessageRepository,
    PostgresSessionRepository,
)

logger = logging.getLogger(__name__)

DbSession = Annotated[AsyncSession, Depends(get_session)]

# JWT 仅解析、不强制（R3：全库当前无鉴权强制，成员校验无 membership 模型暂缺）
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UUID | None:
    """解析 Bearer JWT，返回 sub 作 user_id（无/非法 token → None，不抛 401）。"""
    if creds is None:
        return None
    try:
        payload = decode_access_token(creds.credentials)
        sub = payload.get("sub")
        return UUID(str(sub)) if sub else None
    except Exception:
        # JWT 失效/格式错按未登录处理（R3：本期不强制鉴权）
        logger.debug("JWT 解析失败，按匿名处理")
        return None


CurrentUser = Annotated["UUID | None", Depends(get_current_user)]


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


def get_mcp_server_repo(session: DbSession) -> PostgresMcpServerRepository:
    return PostgresMcpServerRepository(session)


def get_mcp_installation_repo(session: DbSession) -> PostgresMcpInstallationRepository:
    return PostgresMcpInstallationRepository(session)


def get_mcp_market_service(
    repo: Annotated[PostgresMcpServerRepository, Depends(get_mcp_server_repo)],
) -> McpMarketService:
    return McpMarketService(repo)


@lru_cache
def get_mcp_installer() -> LocalMcpInstaller:
    return LocalMcpInstaller()  # 无状态，进程级单例


def get_mcp_install_service(
    server_repo: Annotated[PostgresMcpServerRepository, Depends(get_mcp_server_repo)],
    install_repo: Annotated[PostgresMcpInstallationRepository, Depends(get_mcp_installation_repo)],
) -> McpInstallService:
    return McpInstallService(server_repo, install_repo, get_mcp_installer())


def get_memory_repo(session: DbSession) -> PostgresMemoryRepository:
    return PostgresMemoryRepository(session)


def get_memory_service(
    repo: Annotated[PostgresMemoryRepository, Depends(get_memory_repo)],
) -> MemoryService:
    return MemoryService(repo)


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
    memory_repo: Annotated[PostgresMemoryRepository, Depends(get_memory_repo)],
    bus: Annotated[EventBus, Depends(get_bus)],
) -> ChatService:
    l1 = get_l1_memory()
    wm = get_watermark_store()
    mem_selector = MemorySelector(memory_repo)
    ctx = ContextBuilder(message_repo, agent_repo, l1, wm, memory_selector=mem_selector)
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
        mem_repo = PostgresMemoryRepository(session)
        l1 = get_l1_memory()
        wm = get_watermark_store()
        mem_selector = MemorySelector(mem_repo)
        ctx = ContextBuilder(msg_repo, agent_repo, l1, wm, memory_selector=mem_selector)
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
