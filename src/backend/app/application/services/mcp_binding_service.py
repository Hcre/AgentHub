"""McpBindingService（L3）：Agent↔MCP 绑定用例（F-008~F-011）。

绑定/解绑 + 请求携带 config 构建（P2 决策：attach 经 AgentRequest.mcp_servers，
非运行时有状态；见 ADR-05）。解绑软删，下次 stream 自动不再携带（F-011）。
"""

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import DomainError, NotFoundError
from app.domain.mcp.mcp_binding import AgentMcpBinding
from app.domain.mcp.rules import build_mcp_config_entry
from app.domain.repositories import (
    McpBindingRepository,
    McpInstallationRepository,
    McpServerRepository,
)


class McpBindingService:
    def __init__(
        self,
        binding_repo: McpBindingRepository,
        installation_repo: McpInstallationRepository,
        server_repo: McpServerRepository,
    ) -> None:
        self._binding_repo = binding_repo
        self._install_repo = installation_repo
        self._server_repo = server_repo

    async def bind(
        self,
        *,
        agent_id: UUID,
        installation_id: UUID,
        tool_subset: list[str] | None = None,
    ) -> AgentMcpBinding:
        installation = await self._install_repo.get_by_id(installation_id)
        if installation is None:
            raise NotFoundError(f"MCP 安装不存在: {installation_id}")
        # 同 (agent, installation) 至多 1 条 active（部分唯一）→ 重复绑定 409
        if await self._binding_repo.find_active(agent_id=agent_id, installation_id=installation_id):
            raise DomainError(f"E_MCP_BINDING_CONFLICT: 已绑定: {installation_id}")

        binding = AgentMcpBinding(
            agent_id=agent_id,
            installation_id=installation_id,
            tool_subset=tool_subset or [],
        )
        await self._binding_repo.save(binding)
        # 副作用：无需主动 attach——下次 stream 经 build_request_mcp_servers 携带（请求携带）
        return binding

    async def unbind(self, binding_id: UUID) -> None:
        binding = await self._binding_repo.get_by_id(binding_id)
        if binding is None:
            raise NotFoundError(f"MCP 绑定不存在: {binding_id}")
        binding.unbind()  # 软删
        await self._binding_repo.save(binding)

    async def build_request_mcp_servers(self, agent_id: UUID) -> list[dict]:
        """构建 agent 的 MCP config 条目（请求携带 → runtime 写 .mcp.json）。

        遍历 active 绑定 → installation → server，序列化为 MCP 2025-06-18 条目。
        """
        entries: list[dict] = []
        for binding in await self._binding_repo.list_active_by_agent(agent_id):
            installation = await self._install_repo.get_by_id(binding.installation_id)
            if installation is None:
                continue
            server = await self._server_repo.get_by_id(installation.mcp_id)
            if server is None:
                continue
            merged = {**server.config_json, **installation.config_overrides}
            entries.append(
                build_mcp_config_entry(installation.instance_name, str(server.transport), merged)
            )
        return entries
