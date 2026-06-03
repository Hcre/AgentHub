"""McpMarketService（L3）：MCP 市场浏览/搜索/详情用例（F-001/F-002/F-003）。"""

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import NotFoundError
from app.domain.mcp.mcp_server import McpServer
from app.domain.repositories import McpServerRepository


class McpMarketService:
    def __init__(self, server_repo: McpServerRepository) -> None:
        self._repo = server_repo

    async def list_market(
        self,
        *,
        q: str | None = None,
        tag: str | None = None,
        transport: str | None = None,
        official_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[McpServer], int]:
        return await self._repo.list_market(
            q=q,
            tag=tag,
            transport=transport,
            official_only=official_only,
            page=page,
            page_size=page_size,
        )

    async def get_detail(self, mcp_id: UUID) -> McpServer:
        server = await self._repo.get_by_id(mcp_id)
        if server is None:
            raise NotFoundError(f"MCP 不存在: {mcp_id}")
        return server
