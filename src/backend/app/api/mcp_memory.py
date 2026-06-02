"""AgentHub MCP 记忆端点（SSE transport）。

Agent CLI 通过 --mcp-config 连接，调用 save_memory 工具写入 PG。
每次 `build_for_agent()` 已自动检索 + 注入，不提供 get_memory。

mcp 包可选：未安装时 get_mcp_asgi() 返回 None，main.py 跳过 mount。

agent_id 传递方式：
  客户端在 SSE URL 加 ?agent_id=<uuid>，ASGI wrapper 拦截后：
  1. SSE 连接时：解析响应体找到 session_id，写入 session→agent 映射。
  2. POST /messages/ 时：按 session_id 查映射，注入 ContextVar。
  save_memory 工具从 ContextVar 读 agent_id，而非 os.environ（env 字段对 SSE 无效）。
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

try:
    from mcp.server.fastmcp import FastMCP as _FastMCP
    _MCP_AVAILABLE = True
except ImportError:
    _FastMCP = None  # type: ignore[assignment,misc]
    _MCP_AVAILABLE = False
    logger.info("mcp 包未安装，MCP 记忆端点不可用（pip install mcp）")

from app.application.commands import CreateMemoryCommand
from app.application.services.memory_service import MemoryService
from app.infrastructure.db.base import get_session
from app.infrastructure.repositories.memory_repository import PostgresMemoryRepository

# ContextVar：工具函数读 agent_id，由 ASGI wrapper 在请求维度注入
_agent_id_ctx: ContextVar[str] = ContextVar("agenthub_agent_id", default="")

# session_id → agent_id 映射（内存，进程级）
_session_agent_map: dict[str, str] = {}


class _AgentMCPWrapper:
    """ASGI wrapper：从 SSE URL ?agent_id= 提取 agent_id，注入工具上下文。

    FastMCP SSE transport 流程：
      GET /sse?agent_id=X → 响应首个 SSE 事件含 session_id
      POST /messages/?session_id=Y → 工具调用
    wrapper 在 SSE 响应流中找到 session_id 后建立 session→agent 映射，
    POST 时按 session_id 查映射并设置 ContextVar。
    """

    def __init__(self, mcp_asgi: Any) -> None:
        self._app = mcp_asgi

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        qs: str = scope.get("query_string", b"").decode()
        params: dict[str, str] = dict(
            p.split("=", 1) for p in qs.split("&") if "=" in p
        )

        if path.endswith("/sse"):
            agent_id = params.get("agent_id", "")

            async def _intercept_send(event: dict) -> None:
                if event["type"] == "http.response.body" and agent_id:
                    body = event.get("body", b"").decode(errors="ignore")
                    for line in body.splitlines():
                        line = line.strip()
                        if "session_id=" in line:
                            # SSE 数据行格式: "data: /messages/?session_id=<uuid>"
                            sid = line.split("session_id=")[-1].strip()
                            if sid and sid not in _session_agent_map:
                                _session_agent_map[sid] = agent_id
                                logger.debug("MCP session %s → agent %s", sid, agent_id)
                await send(event)

            await self._app(scope, receive, _intercept_send)

        elif "/messages/" in path:
            session_id = params.get("session_id", "")
            agent_id = _session_agent_map.get(session_id, "")
            token = _agent_id_ctx.set(agent_id)
            try:
                await self._app(scope, receive, send)
            finally:
                _agent_id_ctx.reset(token)

        else:
            await self._app(scope, receive, send)


def _build_mcp_app() -> Any | None:
    if not _MCP_AVAILABLE:
        return None

    mcp = _FastMCP("agenthub-memory")

    @mcp.tool()
    async def save_memory(
        name: str,
        description: str,
        memory_type: str,
        content: str,
        group_id: str | None = None,
    ) -> dict:
        """保存用户主动要求的记忆。用户说「记住 xxx」时调用。

        memory_type: facts | preferences | procedures | context
        """
        agent_id_str = _agent_id_ctx.get()
        if not agent_id_str:
            return {"status": "error", "detail": "agent_id not resolved (session not mapped)"}

        try:
            agent_id = UUID(agent_id_str)
        except ValueError:
            return {"status": "error", "detail": f"invalid agent_id: {agent_id_str}"}

        if memory_type not in ("facts", "preferences", "procedures", "context"):
            memory_type = "facts"

        cmd = CreateMemoryCommand(
            name=name,
            description=description,
            memory_type=memory_type,
            content=content,
            source="chat",
            group_id=UUID(group_id) if group_id else None,
        )

        async for db in get_session():
            repo = PostgresMemoryRepository(db)
            svc = MemoryService(repo)
            m = await svc.create(agent_id=agent_id, user_id=agent_id, cmd=cmd)
            await db.commit()
            logger.info("save_memory OK agent=%s name=%s", agent_id_str, name)
            return {"id": str(m.id), "source": "chat", "status": "saved"}

        return {"status": "error", "detail": "db session failed"}

    return _AgentMCPWrapper(mcp.sse_app())


_mcp_asgi = _build_mcp_app()


def get_mcp_asgi() -> Any | None:
    """返回包了 _AgentMCPWrapper 的 ASGI app，供 app.mount() 使用。"""
    return _mcp_asgi
