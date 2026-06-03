"""MCP 仓储抽象接口（L2 定义，L1 实现 —— 依赖倒置 AR-01）。

本期（P1）覆盖市场（server）与安装（installation）；绑定/日志仓储于 P2/P4 增补。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.mcp.mcp_installation import WorkspaceMcpInstallation
from app.domain.mcp.mcp_server import McpServer


class McpServerRepository(ABC):
    @abstractmethod
    async def save(self, server: McpServer) -> None: ...

    @abstractmethod
    async def get_by_id(self, mcp_id: UUID) -> McpServer | None: ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> McpServer | None: ...

    @abstractmethod
    async def exists_by_name(self, name: str) -> bool: ...

    @abstractmethod
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
        """返回 (当前页条目, 总数)。仅列出 status=published（市场可见）。"""
        ...


class McpInstallationRepository(ABC):
    @abstractmethod
    async def save(self, installation: WorkspaceMcpInstallation) -> None: ...

    @abstractmethod
    async def get_by_id(self, installation_id: UUID) -> WorkspaceMcpInstallation | None: ...

    @abstractmethod
    async def find_idempotent(
        self, *, workspace_id: UUID, mcp_id: UUID, args_hash: str
    ) -> WorkspaceMcpInstallation | None:
        """安装幂等键 (workspace_id + mcp_id + args_hash)（F-004）。"""
        ...

    @abstractmethod
    async def exists_instance_name(self, *, workspace_id: UUID, instance_name: str) -> bool:
        """同 workspace 内 instance_name 是否已占用（唯一约束前置校验）。"""
        ...
