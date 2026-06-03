"""McpInstallService（L3）：workspace 维度安装用例（F-004/F-005）。

幂等键 (workspace_id + mcp_id + args_hash)。P1 骨架：安装记录即置 ready
（无真实进程拉起）；真实安装/健康检查留 P2+。R1：workspace_id 传 session_id。
"""

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import DomainError, NotFoundError
from app.domain.mcp.mcp_installation import WorkspaceMcpInstallation
from app.domain.mcp.rules import compute_args_hash
from app.domain.repositories import McpInstallationRepository, McpServerRepository


class McpInstallService:
    def __init__(
        self,
        server_repo: McpServerRepository,
        installation_repo: McpInstallationRepository,
    ) -> None:
        self._server_repo = server_repo
        self._install_repo = installation_repo

    async def install(
        self,
        *,
        workspace_id: UUID,
        mcp_id: UUID,
        instance_name: str,
        config_overrides: dict | None = None,
        installed_by: UUID | None = None,
    ) -> WorkspaceMcpInstallation:
        server = await self._server_repo.get_by_id(mcp_id)
        if server is None:
            raise NotFoundError(f"MCP 不存在: {mcp_id}")

        overrides = config_overrides or {}
        args_hash = compute_args_hash(overrides)

        # 幂等：同 workspace + mcp + args_hash → 返回既有安装（F-004 ③）
        existing = await self._install_repo.find_idempotent(
            workspace_id=workspace_id, mcp_id=mcp_id, args_hash=args_hash
        )
        if existing is not None:
            return existing

        # 同 workspace 内 instance_name 唯一（uq 约束前置校验 → 409）
        if await self._install_repo.exists_instance_name(
            workspace_id=workspace_id, instance_name=instance_name
        ):
            raise DomainError(f"E_MCP_NAME_CONFLICT: instance_name 已存在: {instance_name}")

        installation = WorkspaceMcpInstallation(
            workspace_id=workspace_id,
            mcp_id=mcp_id,
            instance_name=instance_name,
            installed_by=installed_by,
            config_overrides=overrides,
            args_hash=args_hash,
        )
        # P1 骨架：无真实进程拉起，直接 ready（真实安装/健康检查 P2+）
        installation.mark_ready()
        await self._install_repo.save(installation)
        return installation
