"""FastAPI 应用入口（L4）：装配中间件、路由、异常映射、生命周期。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.mcp_memory import get_mcp_asgi
from app.api.routers import (
    agents,
    attachments,
    groups,
    inbox,
    mcp,
    memories,
    providers,
    proxy,
    sessions,
    skills,
    tasks,
    templates,
)
from app.api.routers.skills import FS_ROUTER
from app.api.ws import router as ws_router
from app.core.config import settings
from app.core.exceptions import (
    AgentHubError,
    DomainError,
    NotFoundError,
    PermissionError,
    ValidationError,
)
from app.core.logging import setup_logging
from app.infrastructure.cache.redis_client import close_redis
from app.infrastructure.llm.claude_code_process_pool import (
    shutdown_pool,
    start_pool_sweeper,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    client = httpx.AsyncClient(timeout=300.0)
    app.state.client = client
    # 长驻 CLI 进程池 idle sweeper（仅 V1 模式下池会被填充，sweeper 始终安全启动）
    if settings.claude_code_long_running:
        start_pool_sweeper()
    yield
    await shutdown_pool()
    await client.aclose()
    await close_redis()


app = FastAPI(
    title="AgentHub API",
    version="0.1.0",
    description="IM 聊天式多 Agent 协作平台 — 后端 API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 异常映射：领域异常 → HTTP ---


@app.exception_handler(NotFoundError)
async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


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


# --- 路由注册 ---

app.include_router(proxy.router)
app.include_router(providers.router)
app.include_router(agents.router)
app.include_router(sessions.router)
app.include_router(groups.router)
app.include_router(memories.router)
app.include_router(tasks.router)
app.include_router(skills.router)
app.include_router(templates.router)  # Agent 模板系统
app.include_router(attachments.router)  # 附件上传/下载（P0-3）
app.include_router(FS_ROUTER)
app.include_router(inbox.router)
app.include_router(mcp.router)  # MCP 市场/安装/绑定 REST（/api/mcp/*，§2.6 冻结契约）
app.include_router(ws_router)
# MCP 记忆协议服务端（SSE）独占 /api/mcp-memory，与上面 /api/mcp REST 分离，
# 避免 mount 通配遮蔽 REST 子路径（原同挂 /api/mcp，靠注册顺序消歧，已分离）。
_mcp_asgi = get_mcp_asgi()
if _mcp_asgi is not None:
    app.mount("/api/mcp-memory", _mcp_asgi)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "service": "agenthub-backend", "version": "0.1.0"}
