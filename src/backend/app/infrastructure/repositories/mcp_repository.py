"""PostgresMcpServerRepository / PostgresMcpInstallationRepository（实现 L2 接口）。

二次对账：tag 过滤在 Python 侧做（tags 存 JSON，跨 PG/SQLite 无可移植包含查询）；
市场规模小，先求正确（MVP），效率优化留后续。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import (
    McpBindingStatus,
    McpInstallStatus,
    McpServerStatus,
    McpTransport,
)
from app.domain.mcp.mcp_binding import AgentMcpBinding
from app.domain.mcp.mcp_installation import WorkspaceMcpInstallation
from app.domain.mcp.mcp_server import McpServer
from app.domain.repositories import (
    McpBindingRepository,
    McpInstallationRepository,
    McpServerRepository,
)
from app.infrastructure.db.models import (
    AgentMcpBindingModel,
    McpServerModel,
    WorkspaceMcpInstallationModel,
)


def _server_to_domain(m: McpServerModel) -> McpServer:
    return McpServer(
        id=m.id,
        name=m.name,
        slug=m.slug,
        description=m.description,
        transport=McpTransport(m.transport),
        config_schema=dict(m.config_schema or {}),
        config_json=dict(m.config_json or {}),
        args_hash=m.args_hash,
        version=m.version,
        latest=m.latest,
        official=m.official,
        tags=list(m.tags or []),
        status=McpServerStatus(m.status),
        created_by=m.created_by,
        dry_run_result=m.dry_run_result,
        dry_run_at=m.dry_run_at,
        install_count=m.install_count,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _server_to_model(s: McpServer) -> McpServerModel:
    return McpServerModel(
        id=s.id,
        name=s.name,
        slug=s.slug,
        description=s.description,
        transport=str(s.transport),
        config_schema=s.config_schema,
        config_json=s.config_json,
        args_hash=s.args_hash,
        version=s.version,
        latest=s.latest,
        official=s.official,
        tags=s.tags,
        status=str(s.status),
        created_by=s.created_by,
        dry_run_result=s.dry_run_result,
        dry_run_at=s.dry_run_at,
        install_count=s.install_count,
    )


def _install_to_domain(m: WorkspaceMcpInstallationModel) -> WorkspaceMcpInstallation:
    return WorkspaceMcpInstallation(
        id=m.id,
        workspace_id=m.workspace_id,
        mcp_id=m.mcp_id,
        installed_by=m.installed_by,
        instance_name=m.instance_name,
        config_overrides=dict(m.config_overrides or {}),
        args_hash=m.args_hash,
        status=McpInstallStatus(m.status),
        error_code=m.error_code,
        error_message=m.error_message,
        created_at=m.created_at,
        updated_at=m.updated_at,
        last_health_check_at=m.last_health_check_at,
    )


def _install_to_model(i: WorkspaceMcpInstallation) -> WorkspaceMcpInstallationModel:
    return WorkspaceMcpInstallationModel(
        id=i.id,
        workspace_id=i.workspace_id,
        mcp_id=i.mcp_id,
        installed_by=i.installed_by,
        instance_name=i.instance_name,
        config_overrides=i.config_overrides,
        args_hash=i.args_hash,
        status=str(i.status),
        error_code=i.error_code,
        error_message=i.error_message,
        last_health_check_at=i.last_health_check_at,
    )


class PostgresMcpServerRepository(McpServerRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, server: McpServer) -> None:
        existing = await self._s.get(McpServerModel, server.id)
        if existing is None:
            self._s.add(_server_to_model(server))
        else:
            existing.name = server.name
            existing.slug = server.slug
            existing.description = server.description
            existing.transport = str(server.transport)
            existing.config_schema = server.config_schema
            existing.config_json = server.config_json
            existing.args_hash = server.args_hash
            existing.version = server.version
            existing.latest = server.latest
            existing.official = server.official
            existing.tags = server.tags
            existing.status = str(server.status)
            existing.dry_run_result = server.dry_run_result
            existing.dry_run_at = server.dry_run_at
            existing.install_count = server.install_count
        await self._s.flush()

    async def get_by_id(self, mcp_id: UUID) -> McpServer | None:
        m = await self._s.get(McpServerModel, mcp_id)
        return _server_to_domain(m) if m else None

    async def get_by_slug(self, slug: str) -> McpServer | None:
        stmt = select(McpServerModel).where(McpServerModel.slug == slug)
        m = (await self._s.execute(stmt)).scalars().first()
        return _server_to_domain(m) if m else None

    async def exists_by_name(self, name: str) -> bool:
        stmt = select(McpServerModel.id).where(McpServerModel.name == name)
        return (await self._s.execute(stmt)).first() is not None

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
        # 市场仅暴露已发布；其余过滤 SQL 可做的下推，tag 在 Python 侧
        stmt = select(McpServerModel).where(McpServerModel.status == str(McpServerStatus.PUBLISHED))
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                McpServerModel.name.ilike(like) | McpServerModel.description.ilike(like)
            )
        if transport:
            stmt = stmt.where(McpServerModel.transport == transport)
        if official_only:
            stmt = stmt.where(McpServerModel.official.is_(True))
        stmt = stmt.order_by(McpServerModel.install_count.desc(), McpServerModel.name.asc())

        rows = (await self._s.execute(stmt)).scalars().all()
        servers = [_server_to_domain(m) for m in rows]
        if tag:
            servers = [s for s in servers if tag in s.tags]
        total = len(servers)
        start = max(page - 1, 0) * page_size
        return servers[start : start + page_size], total

    async def list_templates(self) -> list[McpServer]:
        stmt = (
            select(McpServerModel)
            .where(
                McpServerModel.status == str(McpServerStatus.PUBLISHED),
                McpServerModel.official.is_(True),
            )
            .order_by(McpServerModel.name.asc())
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_server_to_domain(m) for m in rows]


class PostgresMcpInstallationRepository(McpInstallationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, installation: WorkspaceMcpInstallation) -> None:
        existing = await self._s.get(WorkspaceMcpInstallationModel, installation.id)
        if existing is None:
            self._s.add(_install_to_model(installation))
        else:
            existing.instance_name = installation.instance_name
            existing.config_overrides = installation.config_overrides
            existing.args_hash = installation.args_hash
            existing.status = str(installation.status)
            existing.error_code = installation.error_code
            existing.error_message = installation.error_message
            existing.last_health_check_at = installation.last_health_check_at
        await self._s.flush()

    async def get_by_id(self, installation_id: UUID) -> WorkspaceMcpInstallation | None:
        m = await self._s.get(WorkspaceMcpInstallationModel, installation_id)
        return _install_to_domain(m) if m else None

    async def find_idempotent(
        self, *, workspace_id: UUID, mcp_id: UUID, args_hash: str
    ) -> WorkspaceMcpInstallation | None:
        stmt = select(WorkspaceMcpInstallationModel).where(
            WorkspaceMcpInstallationModel.workspace_id == workspace_id,
            WorkspaceMcpInstallationModel.mcp_id == mcp_id,
            WorkspaceMcpInstallationModel.args_hash == args_hash,
        )
        m = (await self._s.execute(stmt)).scalars().first()
        return _install_to_domain(m) if m else None

    async def exists_instance_name(self, *, workspace_id: UUID, instance_name: str) -> bool:
        stmt = select(WorkspaceMcpInstallationModel.id).where(
            WorkspaceMcpInstallationModel.workspace_id == workspace_id,
            WorkspaceMcpInstallationModel.instance_name == instance_name,
        )
        return (await self._s.execute(stmt)).first() is not None

    async def has_active_bindings(self, installation_id: UUID) -> bool:
        stmt = select(AgentMcpBindingModel.id).where(
            AgentMcpBindingModel.installation_id == installation_id,
            AgentMcpBindingModel.status == str(McpBindingStatus.ACTIVE),
        )
        return (await self._s.execute(stmt)).first() is not None

    async def delete(self, installation_id: UUID) -> None:
        m = await self._s.get(WorkspaceMcpInstallationModel, installation_id)
        if m is not None:
            await self._s.delete(m)
            await self._s.flush()


def _binding_to_domain(m: AgentMcpBindingModel) -> AgentMcpBinding:
    return AgentMcpBinding(
        id=m.id,
        agent_id=m.agent_id,
        installation_id=m.installation_id,
        tool_subset=list(m.tool_subset or []),
        status=McpBindingStatus(m.status),
        created_at=m.created_at,
        updated_at=m.updated_at,
        unbound_at=m.unbound_at,
    )


class PostgresMcpBindingRepository(McpBindingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, binding: AgentMcpBinding) -> None:
        existing = await self._s.get(AgentMcpBindingModel, binding.id)
        if existing is None:
            self._s.add(
                AgentMcpBindingModel(
                    id=binding.id,
                    agent_id=binding.agent_id,
                    installation_id=binding.installation_id,
                    tool_subset=binding.tool_subset,
                    status=str(binding.status),
                    unbound_at=binding.unbound_at,
                )
            )
        else:
            existing.tool_subset = binding.tool_subset
            existing.status = str(binding.status)
            existing.unbound_at = binding.unbound_at
        await self._s.flush()

    async def get_by_id(self, binding_id: UUID) -> AgentMcpBinding | None:
        m = await self._s.get(AgentMcpBindingModel, binding_id)
        return _binding_to_domain(m) if m else None

    async def find_active(self, *, agent_id: UUID, installation_id: UUID) -> AgentMcpBinding | None:
        stmt = select(AgentMcpBindingModel).where(
            AgentMcpBindingModel.agent_id == agent_id,
            AgentMcpBindingModel.installation_id == installation_id,
            AgentMcpBindingModel.status == str(McpBindingStatus.ACTIVE),
        )
        m = (await self._s.execute(stmt)).scalars().first()
        return _binding_to_domain(m) if m else None

    async def list_active_by_agent(self, agent_id: UUID) -> list[AgentMcpBinding]:
        stmt = select(AgentMcpBindingModel).where(
            AgentMcpBindingModel.agent_id == agent_id,
            AgentMcpBindingModel.status == str(McpBindingStatus.ACTIVE),
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_binding_to_domain(m) for m in rows]
