"""代理路由：CLI → AgentHub Proxy → 第三方 API。

CLI 子进程的 ANTHROPIC_BASE_URL 设为 http://127.0.0.1:8000/proxy/agents/{agent_id}，
所有 API 请求经此路由转发到 Agent 配置的 Provider。
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.base import get_session
from app.infrastructure.llm.proxy.handler import ProxyHandler
from app.infrastructure.repositories import PostgresAgentRepository

router = APIRouter(prefix="/proxy", tags=["proxy"])


@router.api_route(
    "/agents/{agent_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
async def proxy_request(
    agent_id: str,
    path: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    client: httpx.AsyncClient = request.app.state.client
    handler = ProxyHandler(PostgresAgentRepository(db))
    return await handler.handle(agent_id, path, request, client)
